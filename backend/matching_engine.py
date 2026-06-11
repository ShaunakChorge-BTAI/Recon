import asyncio
import json
import logging
import re
import time

import httpx
import numpy as np
import pandas as pd
from rapidfuzz.process import extractOne


class MatchingEngine:
    def __init__(self, tol_amount, tol_time, mapping):
        self.tol_amount = float(tol_amount)
        self.tol_time_minutes = int(tol_time)
        self.tol_time = pd.Timedelta(minutes=tol_time)

        self.src_refs = mapping["source"]["references"]
        self.dest_refs = mapping["dest"]["references"]

    # ============================================================
    # HELPERS
    # ============================================================
    def _normalize_ref_key(self, key):
        """Always return group keys as tuple."""
        if isinstance(key, tuple):
            return key
        return (key,)

    def _prepare_df(self, df: pd.DataFrame, ref_cols):
        """
        Defensive cleanup without changing business logic:
        - parse datetime
        - ignore seconds globally -> floor to minute
        - amount numeric
        - remove nulls in critical columns
        """
        df = df.copy()

        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce").dt.floor("min")

        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

        needed = list(ref_cols) + ["datetime", "amount"]
        needed = [c for c in needed if c in df.columns]

        if needed:
            df = df.dropna(subset=needed)

        return df

    def _rename_dest_refs(self, dest: pd.DataFrame) -> pd.DataFrame:
        rename_map = dict(zip(self.dest_refs, self.src_refs))
        return dest.rename(columns=rename_map)

    def _make_json_safe(self, df: pd.DataFrame):
        """Convert dataframe rows into JSON-safe list of dicts."""
        safe_rows = []
        for _, row in df.iterrows():
            safe_row = {}
            for k, v in row.to_dict().items():
                safe_row[k] = str(v)
            safe_rows.append(safe_row)
        return safe_rows

    def _build_llm_prompt(self, src_json, dest_json):
        return f"""
You are a financial reconciliation engine.

Match transactions between SOURCE and DEST.

STRICT RULES:
- Amount must match EXACTLY or within tolerance
- Datetime difference must be within tolerance
- References can be fuzzy
- Group rows if needed (subset matching allowed)
- Ignore seconds in datetime; compare only up to minute precision

SOURCE:
{json.dumps(src_json, indent=2)}

DEST:
{json.dumps(dest_json, indent=2)}

OUTPUT STRICT JSON:
[
  {{
    "match_type": "one-to-one|one-to-many|many-to-one|many-to-many",
    "source_indices": [0],
    "dest_indices": [1,2],
    "confidence_score": 0.95,
    "reason": "..."
  }}
]

Return [] if no match.
"""

    def _parse_llm_json(self, text):
        """
        Parse LLM JSON safely even if wrapped in markdown / extra text.
        """
        if not text:
            return []

        cleaned = text.strip()

        # remove code fences if any
        cleaned = re.sub(r"^```json", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^```", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            pass

        first = cleaned.find("[")
        last = cleaned.rfind("]")
        if first != -1 and last != -1 and last > first:
            snippet = cleaned[first:last + 1]
            try:
                parsed = json.loads(snippet)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []

        return []

    # ============================================================
    # LAYER 0 — SELF KNOCK
    #
    # Strict rules:
    # - all mapped columns must match
    # - null not allowed
    # - exactly one-to-one only
    # - one positive + one negative
    # - sum(amount) == 0
    # ============================================================
    def layer0_self_knock(self, df: pd.DataFrame):

        group_cols = self.src_refs + ["datetime"]

        df_clean = self._prepare_df(df, self.src_refs)

        if df_clean.empty:
            return pd.DataFrame()

        grp = df_clean.groupby(group_cols)["amount"]

        size = grp.transform("size")
        total = grp.transform("sum")
        pos_count = grp.transform(lambda x: (x > 0).sum())
        neg_count = grp.transform(lambda x: (x < 0).sum())

        mask = (
            (size == 2) &
            (total.round(2) == 0) &
            (pos_count == 1) &
            (neg_count == 1)
        )

        return df_clean[mask].copy()

    # ============================================================
    # LAYER 1 — EXACT MATCH
    #
    # Exact on:
    # - mapped refs
    # - datetime
    # - amount
    #
    # Returns flattened row-level matches with _x / _y
    # ============================================================
    def layer1_exact(self, src: pd.DataFrame, dest: pd.DataFrame):

        src_work = self._prepare_df(src, self.src_refs)
        dest_work = self._prepare_df(dest, self.dest_refs)

        if src_work.empty or dest_work.empty:
            return pd.DataFrame()

        dest_work = self._rename_dest_refs(dest_work)

        cols = self.src_refs + ["datetime", "amount"]

        src_grouped = {}
        for _, row in src_work.iterrows():
            key = tuple(row[c] for c in cols)
            src_grouped.setdefault(key, []).append(row)

        dest_grouped = {}
        for _, row in dest_work.iterrows():
            key = tuple(row[c] for c in cols)
            dest_grouped.setdefault(key, []).append(row)

        rows = []

        common_keys = set(src_grouped.keys()) & set(dest_grouped.keys())

        for key in common_keys:
            for s_row in src_grouped[key]:
                s_dict = s_row.to_dict()

                for d_row in dest_grouped[key]:
                    d_dict = d_row.to_dict()

                    rows.append({
                        **{f"{k}_x": v for k, v in s_dict.items()},
                        **{f"{k}_y": v for k, v in d_dict.items()},
                    })

        return pd.DataFrame(rows)

    # ============================================================
    # LAYER 2 — TOLERANCE MATCH
    #
    # Rules:
    # - refs must match
    # - amount within tolerance
    # - datetime within tolerance
    # - seconds ignored
    #
    # Optimized:
    # - block by ref group
    # - sort destination amounts
    # - binary search amount window
    # ============================================================
    def layer2_tolerance(self, src: pd.DataFrame, dest: pd.DataFrame):

        src_work = self._prepare_df(src, self.src_refs)
        dest_work = self._prepare_df(dest, self.dest_refs)

        if src_work.empty or dest_work.empty:
            return pd.DataFrame()

        dest_work = self._rename_dest_refs(dest_work)

        # Build destination lookup by ref key
        dest_groups = {}
        for ref_key, grp in dest_work.groupby(self.src_refs, observed=True, sort=False):
            ref_key = self._normalize_ref_key(ref_key)
            grp2 = grp.sort_values("amount").reset_index(drop=True).copy()
            grp2["_amount_np"] = grp2["amount"].to_numpy()
            dest_groups[ref_key] = grp2

        matches = []

        for ref_key, s_grp in src_work.groupby(self.src_refs, observed=True, sort=False):
            ref_key = self._normalize_ref_key(ref_key)

            d_grp = dest_groups.get(ref_key)
            if d_grp is None or d_grp.empty:
                continue

            d_amounts = d_grp["_amount_np"]

            for _, s_row in s_grp.iterrows():
                s_amt = s_row["amount"]
                s_dt = s_row["datetime"]

                lo_amt = s_amt - self.tol_amount
                hi_amt = s_amt + self.tol_amount

                left = np.searchsorted(d_amounts, lo_amt, side="left")
                right = np.searchsorted(d_amounts, hi_amt, side="right")

                if left >= right:
                    continue

                candidates = d_grp.iloc[left:right]

                time_mask = (candidates["datetime"] - s_dt).abs() <= self.tol_time
                candidates = candidates[time_mask]

                if candidates.empty:
                    continue

                s_dict = s_row.to_dict()

                for _, d_row in candidates.iterrows():
                    d_dict = d_row.drop(labels=["_amount_np"], errors="ignore").to_dict()

                    matches.append({
                        **{f"{k}_x": v for k, v in s_dict.items()},
                        **{f"{k}_y": v for k, v in d_dict.items()},
                    })

        return pd.DataFrame(matches)

    # ============================================================
    # LAYER 3 — SUBSET / GROUP MATCH
    #
    # Same business logic preserved:
    # 1. group src by refs + datetime and sum(amount)
    # 2. group dest by refs + datetime and sum(amount)
    # 3. refs must match
    # 4. grouped amount within tolerance
    # 5. grouped datetime within tolerance
    # 6. expand matched grouped buckets back to row-level
    #
    # Optimized:
    # - no full global merge
    # - per-ref-key matching only
    # - datetime window search using binary search
    # - expand only matched buckets
    # ============================================================
    def layer3_subset(self, src: pd.DataFrame, dest: pd.DataFrame):

        src_work = self._prepare_df(src, self.src_refs)
        dest_work = self._prepare_df(dest, self.dest_refs)

        if src_work.empty or dest_work.empty:
            return pd.DataFrame()

        cols = self.src_refs
        dest_work = self._rename_dest_refs(dest_work)

        # Group source / dest by refs + datetime
        s = (
            src_work.groupby(cols + ["datetime"], observed=True, sort=False)["amount"]
            .sum()
            .reset_index()
        )

        d = (
            dest_work.groupby(cols + ["datetime"], observed=True, sort=False)["amount"]
            .sum()
            .reset_index()
        )

        if s.empty or d.empty:
            return pd.DataFrame()

        # Row lookup for expansion back to row-level
        src_rows_by_bucket = {}
        for _, row in src_work.iterrows():
            ref_key = tuple(row[c] for c in cols)
            bucket_key = (ref_key, row["datetime"])
            src_rows_by_bucket.setdefault(bucket_key, []).append(row)

        dest_rows_by_bucket = {}
        for _, row in dest_work.iterrows():
            ref_key = tuple(row[c] for c in cols)
            bucket_key = (ref_key, row["datetime"])
            dest_rows_by_bucket.setdefault(bucket_key, []).append(row)

        # Grouped dest lookup by refs
        dest_group_map = {}
        for ref_key, grp in d.groupby(cols, observed=True, sort=False):
            ref_key = self._normalize_ref_key(ref_key)
            grp_sorted = grp.sort_values("datetime").reset_index(drop=True).copy()
            grp_sorted["_dt_ns"] = grp_sorted["datetime"].astype("int64")
            dest_group_map[ref_key] = grp_sorted

        tol_ns = self.tol_time.value
        matched_bucket_pairs = []

        # Match grouped buckets
        for ref_key, s_grp in s.groupby(cols, observed=True, sort=False):
            ref_key = self._normalize_ref_key(ref_key)

            d_grp = dest_group_map.get(ref_key)
            if d_grp is None or d_grp.empty:
                continue

            d_times = d_grp["_dt_ns"].to_numpy()
            s_grp = s_grp.sort_values("datetime").reset_index(drop=True)

            for _, s_row in s_grp.iterrows():
                s_dt = s_row["datetime"]
                s_amt = s_row["amount"]

                if pd.isna(s_dt):
                    continue

                s_ns = s_dt.value
                lo_ns = s_ns - tol_ns
                hi_ns = s_ns + tol_ns

                left = np.searchsorted(d_times, lo_ns, side="left")
                right = np.searchsorted(d_times, hi_ns, side="right")

                if left >= right:
                    continue

                candidates = d_grp.iloc[left:right]

                amt_mask = (candidates["amount"] - s_amt).abs() <= self.tol_amount
                candidates = candidates[amt_mask]

                if candidates.empty:
                    continue

                src_bucket_key = (ref_key, s_dt)

                for _, d_row in candidates.iterrows():
                    dest_bucket_key = (ref_key, d_row["datetime"])
                    matched_bucket_pairs.append((src_bucket_key, dest_bucket_key))

        if not matched_bucket_pairs:
            return pd.DataFrame()

        # Expand matched grouped buckets to row-level
        final_rows = []

        for src_bucket_key, dest_bucket_key in matched_bucket_pairs:
            src_block = src_rows_by_bucket.get(src_bucket_key, [])
            dest_block = dest_rows_by_bucket.get(dest_bucket_key, [])

            if not src_block or not dest_block:
                continue

            for s_row in src_block:
                s_dict = s_row.to_dict()

                for d_row in dest_block:
                    d_dict = d_row.to_dict()

                    final_rows.append({
                        **{f"{k}_x": v for k, v in s_dict.items()},
                        **{f"{k}_y": v for k, v in d_dict.items()},
                    })

        return pd.DataFrame(final_rows)

    # ============================================================
    # LAYER 4 — FUZZY MATCH
    #
    # Rules preserved:
    # - fuzzy refs
    # - exact amount
    # - datetime within tolerance
    # - seconds ignored
    # - nulls not allowed
    #
    # Optimized:
    # - block by exact amount first
    # - time window before fuzzy
    # - batch source processing
    # ============================================================
    def layer4_fuzzy(self, src: pd.DataFrame, dest: pd.DataFrame):

        src_cols = [c for c in self.src_refs if c in src.columns]
        dest_cols = [c for c in self.dest_refs if c in dest.columns]

        if not src_cols or not dest_cols:
            return pd.DataFrame()

        src_work = self._prepare_df(src, src_cols)
        dest_work = self._prepare_df(dest, dest_cols)

        if src_work.empty or dest_work.empty:
            return pd.DataFrame()

        src_work[src_cols] = src_work[src_cols].astype(str)
        dest_work[dest_cols] = dest_work[dest_cols].astype(str)

        src_work["ref"] = src_work[src_cols].agg(" ".join, axis=1)
        dest_work["ref"] = dest_work[dest_cols].agg(" ".join, axis=1)

        # Block by exact amount
        dest_amount_map = {}
        for amt, grp in dest_work.groupby("amount", sort=False):
            grp_sorted = grp.sort_values("datetime").reset_index(drop=True)
            dest_amount_map[amt] = grp_sorted

        matches = []

        for i in range(0, len(src_work), 10000):
            batch = src_work.iloc[i:i + 10000]

            for _, s in batch.iterrows():
                candidate_dest = dest_amount_map.get(s["amount"])
                if candidate_dest is None or candidate_dest.empty:
                    continue

                lo = s["datetime"] - self.tol_time
                hi = s["datetime"] + self.tol_time

                cand = candidate_dest[
                    (candidate_dest["datetime"] >= lo) &
                    (candidate_dest["datetime"] <= hi)
                ]

                if cand.empty:
                    continue

                cand_refs = cand["ref"].tolist()
                result = extractOne(s["ref"], cand_refs, score_cutoff=80)

                if result is None:
                    continue

                match_text, score, local_idx = result
                d = cand.iloc[local_idx]

                try:
                    time_diff = abs(s["datetime"] - d["datetime"])
                    amt_diff = abs(s["amount"] - d["amount"])
                except Exception:
                    continue

                if (
                    score >= 80 and
                    amt_diff == 0 and
                    time_diff <= self.tol_time
                ):
                    matches.append({
                        **{f"{k}_x": v for k, v in s.to_dict().items()},
                        **{f"{k}_y": v for k, v in d.to_dict().items()},
                        "score": score
                    })

        return pd.DataFrame(matches)

    # ============================================================
    # LAYER 5 — LLM MATCHING
    #
    # Async + chunked + logged
    # ============================================================
    def layer5_llm(self, src: pd.DataFrame, dest: pd.DataFrame):
        """
        Sync wrapper so run_job() can remain synchronous.
        """
        try:
            return asyncio.run(self._layer5_llm_async(src, dest))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self._layer5_llm_async(src, dest))
            finally:
                loop.close()

    async def _layer5_llm_async(self, src: pd.DataFrame, dest: pd.DataFrame):

        SRC_CHUNK_SIZE = 40
        DEST_CHUNK_SIZE = 120
        MAX_CONCURRENCY = 3
        MAX_RETRIES = 2

        timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0)

        use_src_cols = self.src_refs + ["datetime", "amount"]
        use_dest_cols = self.dest_refs + ["datetime", "amount"]

        src_work = self._prepare_df(src, self.src_refs)
        dest_work = self._prepare_df(dest, self.dest_refs)

        src_work = src_work[use_src_cols].copy()
        dest_work = dest_work[use_dest_cols].copy()

        if src_work.empty or dest_work.empty:
            logging.info("🔹 Layer5 skipped → source or destination empty after preparation")
            return pd.DataFrame()

        src_work = src_work.reset_index().rename(columns={"index": "__abs_src_idx"})
        dest_work = dest_work.reset_index().rename(columns={"index": "__abs_dest_idx"})

        logging.info(
            f"🔹 Layer5 input prepared | src_rows={len(src_work)} | dest_rows={len(dest_work)}"
        )

        src_chunks = [
            src_work.iloc[i:i + SRC_CHUNK_SIZE].copy().reset_index(drop=True)
            for i in range(0, len(src_work), SRC_CHUNK_SIZE)
        ]

        dest_chunks = [
            dest_work.iloc[j:j + DEST_CHUNK_SIZE].copy().reset_index(drop=True)
            for j in range(0, len(dest_work), DEST_CHUNK_SIZE)
        ]

        logging.info(
            f"🔹 Layer5 chunking | src_chunks={len(src_chunks)} | dest_chunks={len(dest_chunks)} "
            f"| src_chunk_size={SRC_CHUNK_SIZE} | dest_chunk_size={DEST_CHUNK_SIZE}"
        )

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        matched_src_abs = set()
        matched_dest_abs = set()

        accepted_output_rows = []

        async with httpx.AsyncClient(timeout=timeout) as client:
            for si, src_chunk in enumerate(src_chunks, start=1):

                src_chunk_unmatched = src_chunk[~src_chunk["__abs_src_idx"].isin(matched_src_abs)].copy()
                if src_chunk_unmatched.empty:
                    logging.info(f"🔹 Layer5 src_chunk {si}/{len(src_chunks)} skipped (all source rows already matched)")
                    continue

                tasks = []

                for dj, dest_chunk in enumerate(dest_chunks, start=1):
                    dest_chunk_unmatched = dest_chunk[~dest_chunk["__abs_dest_idx"].isin(matched_dest_abs)].copy()
                    if dest_chunk_unmatched.empty:
                        continue

                    chunk_label = f"S{si}/{len(src_chunks)}-D{dj}/{len(dest_chunks)}"

                    tasks.append(
                        self._call_llm_chunk(
                            client=client,
                            semaphore=semaphore,
                            src_chunk=src_chunk_unmatched,
                            dest_chunk=dest_chunk_unmatched,
                            chunk_label=chunk_label,
                            max_retries=MAX_RETRIES,
                        )
                    )

                if not tasks:
                    continue

                chunk_outputs = await asyncio.gather(*tasks, return_exceptions=True)

                chunk_results = []
                for item in chunk_outputs:
                    if isinstance(item, Exception):
                        logging.error(f"❌ Layer5 async chunk task failure: {item}")
                        continue
                    if item:
                        chunk_results.extend(item)

                accepted_pairs = self._accept_chunk_matches(
                    chunk_results,
                    matched_src_abs,
                    matched_dest_abs
                )

                accepted_output_rows.extend(
                    self._expand_llm_pairs_to_rows(accepted_pairs)
                )

        logging.info(
            f"✅ Layer5 final accepted matches → src_matched={len(matched_src_abs)} | "
            f"dest_matched={len(matched_dest_abs)} | output_rows={len(accepted_output_rows)}"
        )

        return pd.DataFrame(accepted_output_rows)

    async def _call_llm_chunk(self, client, semaphore, src_chunk, dest_chunk, chunk_label, max_retries=2):
        """
        One async LLM chunk call.
        Returns parsed matches enriched with absolute index maps.
        """
        async with semaphore:
            start = time.time()

            src_prompt_df = src_chunk.drop(columns=["__abs_src_idx"], errors="ignore").copy()
            dest_prompt_df = dest_chunk.drop(columns=["__abs_dest_idx"], errors="ignore").copy()

            src_json = self._make_json_safe(src_prompt_df)
            dest_json = self._make_json_safe(dest_prompt_df)

            prompt = self._build_llm_prompt(src_json, dest_json)

            logging.info(
                f"🔹 Layer5 chunk {chunk_label} started | "
                f"src_rows={len(src_prompt_df)} | dest_rows={len(dest_prompt_df)}"
            )

            attempt = 0
            while True:
                try:
                    attempt += 1

                    res = await client.post(
                        "https://ollama.osourceglobal.com:11434/api/generate",
                        json={
                            "model": "qwen2.5:14b",
                            "prompt": prompt,
                            "stream": False
                        }
                    )

                    payload = res.json()
                    raw_text = payload.get("response", "[]")
                    matches = self._parse_llm_json(raw_text)

                    elapsed = time.time() - start
                    logging.info(
                        f"✅ Layer5 chunk {chunk_label} completed | "
                        f"attempt={attempt} | llm_matches={len(matches)} | time={round(elapsed, 2)} sec"
                    )

                    src_abs_map = src_chunk["__abs_src_idx"].tolist()
                    dest_abs_map = dest_chunk["__abs_dest_idx"].tolist()

                    enriched = []
                    for m in matches:
                        enriched.append({
                            "chunk_label": chunk_label,
                            "match_type": m.get("match_type", "unknown"),
                            "source_indices": m.get("source_indices", []),
                            "dest_indices": m.get("dest_indices", []),
                            "confidence_score": m.get("confidence_score", 0.7),
                            "reason": m.get("reason", ""),
                            "src_abs_map": src_abs_map,
                            "dest_abs_map": dest_abs_map,
                            "src_chunk": src_chunk,
                            "dest_chunk": dest_chunk,
                        })

                    return enriched

                except Exception as e:
                    if attempt <= max_retries:
                        wait_secs = 1.5 * attempt
                        logging.warning(
                            f"⚠️ Layer5 chunk {chunk_label} retry {attempt}/{max_retries} "
                            f"after error: {e} | waiting {wait_secs} sec"
                        )
                        await asyncio.sleep(wait_secs)
                        continue

                    elapsed = time.time() - start
                    logging.error(
                        f"❌ Layer5 chunk {chunk_label} failed after retries | "
                        f"time={round(elapsed, 2)} sec | error={e}"
                    )
                    return []

    def _accept_chunk_matches(self, chunk_results, matched_src_abs, matched_dest_abs):
        """
        Greedy global dedupe:
        reject a candidate if any source or dest row is already used.
        """
        accepted = []

        for m in chunk_results:
            src_loc = m.get("source_indices", [])
            dest_loc = m.get("dest_indices", [])

            src_abs_map = m.get("src_abs_map", [])
            dest_abs_map = m.get("dest_abs_map", [])

            try:
                src_abs_indices = [src_abs_map[i] for i in src_loc if i < len(src_abs_map)]
                dest_abs_indices = [dest_abs_map[i] for i in dest_loc if i < len(dest_abs_map)]
            except Exception:
                continue

            if not src_abs_indices or not dest_abs_indices:
                continue

            if any(i in matched_src_abs for i in src_abs_indices):
                continue

            if any(i in matched_dest_abs for i in dest_abs_indices):
                continue

            matched_src_abs.update(src_abs_indices)
            matched_dest_abs.update(dest_abs_indices)

            accepted.append({
                "match_type": m.get("match_type", "unknown"),
                "confidence_score": m.get("confidence_score", 0.7),
                "reason": m.get("reason", ""),
                "src_abs_indices": src_abs_indices,
                "dest_abs_indices": dest_abs_indices,
                "src_chunk": m.get("src_chunk"),
                "dest_chunk": m.get("dest_chunk"),
            })

        return accepted

    def _expand_llm_pairs_to_rows(self, accepted_pairs):
        rows = []

        for item in accepted_pairs:
            src_chunk = item["src_chunk"]
            dest_chunk = item["dest_chunk"]
            match_type = item["match_type"]
            score = item["confidence_score"]
            reason = item["reason"]

            src_rows = src_chunk[src_chunk["__abs_src_idx"].isin(item["src_abs_indices"])]
            dest_rows = dest_chunk[dest_chunk["__abs_dest_idx"].isin(item["dest_abs_indices"])]

            if src_rows.empty or dest_rows.empty:
                continue

            for _, s in src_rows.iterrows():
                s_dict = s.drop(labels=["__abs_src_idx"], errors="ignore").to_dict()

                for _, d in dest_rows.iterrows():
                    d_dict = d.drop(labels=["__abs_dest_idx"], errors="ignore").to_dict()

                    rows.append({
                        **{f"{k}_x": v for k, v in s_dict.items()},
                        **{f"{k}_y": v for k, v in d_dict.items()},
                        "score": score,
                        "match_type": match_type,
                        "reason": reason,
                        "index_x": s["__abs_src_idx"],
                        "index_y": d["__abs_dest_idx"],
                    })

        return rows

    # ============================================================
    # LAYER 0 — DEST SIDE SELF KNOCK
    # Same logic as layer0_self_knock but applied to dest df
    # ============================================================
    def layer0_self_knock_dest(self, df: pd.DataFrame):
        group_cols = self.dest_refs + ["datetime"]
        df_clean = self._prepare_df(df, self.dest_refs)

        if df_clean.empty:
            return pd.DataFrame()

        grp = df_clean.groupby(group_cols)["amount"]

        size = grp.transform("size")
        total = grp.transform("sum")
        pos_count = grp.transform(lambda x: (x > 0).sum())
        neg_count = grp.transform(lambda x: (x < 0).sum())

        mask = (
            (size == 2) &
            (total.round(2) == 0) &
            (pos_count == 1) &
            (neg_count == 1)
        )

        return df_clean[mask].copy()

    # ============================================================
    # ORCHESTRATOR — run_all_layers
    # Runs all layers in sequence, tracks timing, returns results
    # ============================================================
    def run_all_layers(
        self,
        src_df: pd.DataFrame,
        dest_df: pd.DataFrame,
        progress_callback=None,
        skip_llm: bool = False,
    ) -> dict:
        """
        Run all matching layers in sequence.

        Returns:
        {
          "layers": {
            "Self Knock": {"matches": DataFrame, "count": int, "time_sec": float},
            "Exact Match": {...},
            ...
          },
          "unmatched_src": DataFrame,
          "unmatched_dest": DataFrame,
          "total_matched": int,
        }
        """
        import time

        def push(msg, pct, extra=None):
            if progress_callback:
                payload = {"status": msg, "progress": pct}
                if extra:
                    payload.update(extra)
                progress_callback(payload)

        results = {}
        src_work = src_df.copy()
        dest_work = dest_df.copy()
        total_matched = 0

        def drop_matched_src(df, matches):
            if matches.empty or "record_id_x" not in matches.columns:
                return df
            ids = matches["record_id_x"].dropna().tolist()
            return df[~df["record_id"].isin(ids)]

        def drop_matched_dest(df, matches):
            if matches.empty or "record_id_y" not in matches.columns:
                return df
            ids = matches["record_id_y"].dropna().tolist()
            return df[~df["record_id"].isin(ids)]

        # ── Layer 0: Self Knock ───────────────────────────────
        push("Running Layer 0: Self Knock...", 10)
        t0 = time.time()
        l0_src = self.layer0_self_knock(src_work)
        l0_dest = self.layer0_self_knock_dest(dest_work)
        # Combine: pairs within src and within dest
        l0_combined = pd.concat([l0_src, l0_dest], ignore_index=True)
        t0_time = round(time.time() - t0, 2)
        count0 = len(l0_src) + len(l0_dest)
        results["Self Knock"] = {"matches": l0_combined, "raw_src": l0_src, "raw_dest": l0_dest, "count": count0, "time_sec": t0_time}
        # Remove self-knocked rows from further processing
        if not l0_src.empty and "record_id" in l0_src.columns:
            src_work = src_work[~src_work["record_id"].isin(l0_src["record_id"].tolist())]
        if not l0_dest.empty and "record_id" in l0_dest.columns:
            dest_work = dest_work[~dest_work["record_id"].isin(l0_dest["record_id"].tolist())]
        total_matched += count0
        push("Layer 0 done", 18, {"layer": "Self Knock", "count": count0, "time_sec": t0_time})

        # ── Layer 1: Exact Match ──────────────────────────────
        push("Running Layer 1: Exact Match...", 25)
        t1 = time.time()
        l1 = self.layer1_exact(src_work, dest_work)
        t1_time = round(time.time() - t1, 2)
        count1 = len(l1)
        results["Exact Match"] = {"matches": l1, "count": count1, "time_sec": t1_time}
        src_work = drop_matched_src(src_work, l1)
        dest_work = drop_matched_dest(dest_work, l1)
        total_matched += count1
        push("Layer 1 done", 35, {"layer": "Exact Match", "count": count1, "time_sec": t1_time})

        # ── Layer 2: Tolerance Match ──────────────────────────
        push("Running Layer 2: Tolerance Match...", 42)
        t2 = time.time()
        l2 = self.layer2_tolerance(src_work, dest_work)
        t2_time = round(time.time() - t2, 2)
        count2 = len(l2)
        results["Tolerance Match"] = {"matches": l2, "count": count2, "time_sec": t2_time}
        src_work = drop_matched_src(src_work, l2)
        dest_work = drop_matched_dest(dest_work, l2)
        total_matched += count2
        push("Layer 2 done", 52, {"layer": "Tolerance Match", "count": count2, "time_sec": t2_time})

        # ── Layer 3: Subset Match ─────────────────────────────
        push("Running Layer 3: Subset Match...", 58)
        t3 = time.time()
        l3 = self.layer3_subset(src_work, dest_work)
        t3_time = round(time.time() - t3, 2)
        count3 = len(l3)
        results["Subset Match"] = {"matches": l3, "count": count3, "time_sec": t3_time}
        src_work = drop_matched_src(src_work, l3)
        dest_work = drop_matched_dest(dest_work, l3)
        total_matched += count3
        push("Layer 3 done", 68, {"layer": "Subset Match", "count": count3, "time_sec": t3_time})

        # ── Layer 4: Fuzzy Match ──────────────────────────────
        push("Running Layer 4: Fuzzy Match...", 74)
        t4 = time.time()
        l4 = self.layer4_fuzzy(src_work, dest_work)
        t4_time = round(time.time() - t4, 2)
        count4 = len(l4)
        results["Fuzzy Match"] = {"matches": l4, "count": count4, "time_sec": t4_time}
        src_work = drop_matched_src(src_work, l4)
        dest_work = drop_matched_dest(dest_work, l4)
        total_matched += count4
        push("Layer 4 done", 83, {"layer": "Fuzzy Match", "count": count4, "time_sec": t4_time})

        # ── Layer 5: LLM Match ────────────────────────────────
        count5, t5_time = 0, 0.0
        if not skip_llm:
            push("Running Layer 5: LLM Match...", 88)
            t5 = time.time()
            try:
                l5 = self.layer5_llm(src_work, dest_work)
                t5_time = round(time.time() - t5, 2)
                count5 = len(l5)
                results["LLM Match"] = {"matches": l5, "count": count5, "time_sec": t5_time}
                src_work = drop_matched_src(src_work, l5)
                dest_work = drop_matched_dest(dest_work, l5)
                total_matched += count5
            except Exception as e:
                logging.warning(f"Layer 5 (LLM) skipped: {e}")
                results["LLM Match"] = {"matches": pd.DataFrame(), "count": 0, "time_sec": 0.0}
            push("Layer 5 done", 95, {"layer": "LLM Match", "count": count5, "time_sec": t5_time})
        else:
            logging.info("Layer 5 (LLM) skipped — skip_llm=True")
            results["LLM Match"] = {"matches": pd.DataFrame(), "count": 0, "time_sec": 0.0}

        push("Reconciliation complete!", 100)

        return {
            "layers": results,
            "unmatched_src": src_work,
            "unmatched_dest": dest_work,
            "total_matched": total_matched,
        }