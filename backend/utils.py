import hashlib
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def clean_mapped_dataframe(df: pd.DataFrame, mapping: dict, side: str) -> list:
    """
    Clean and format a raw DataFrame using the provided column mapping.

    Returns a list of dicts ready for DB insertion.

    Mapping structure:
    {
      "source": {"datetime": "col", "amount": "col", "references": ["col1", ...]},
      "dest":   {"datetime": "col", "amount": "col", "references": ["col1", ...]},
      "date_mode": "date" | "datetime",   # optional, default "datetime"
      "date_format": "%d/%m/%Y"           # optional, for ambiguous dates
    }
    """
    m = mapping[side]

    date_col = m["datetime"]
    amount_col = m["amount"]
    ref_cols = m.get("references", [])

    date_mode = mapping.get("date_mode", "datetime")   # "date" or "datetime"
    date_format = mapping.get("date_format", None)      # e.g. "%d/%m/%Y"

    # All mapped columns
    all_mapped_cols = [date_col, amount_col] + ref_cols
    remaining_cols = [c for c in df.columns if c not in all_mapped_cols]

    df = df.copy()

    # ── Drop fully blank rows (all mapped columns empty) ──────────────────
    df = df.dropna(subset=all_mapped_cols, how="all")

    # ── 1. Datetime formatting ─────────────────────────────────────────────
    if date_format:
        try:
            df["txn_datetime"] = pd.to_datetime(
                df[date_col], format=date_format, errors="coerce"
            )
        except Exception:
            df["txn_datetime"] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        df["txn_datetime"] = pd.to_datetime(df[date_col], errors="coerce")

    if date_mode == "date":
        # Keep only date portion — normalize to midnight
        df["txn_datetime"] = df["txn_datetime"].dt.normalize()
    else:
        # Datetime mode — floor to minute (ignore seconds per spec)
        df["txn_datetime"] = df["txn_datetime"].dt.floor("min")

    # ── 2. Amount cleaning ────────────────────────────────────────────────
    df["amount_clean"] = (
        df[amount_col]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.strip()
    )
    df["amount_clean"] = pd.to_numeric(df["amount_clean"], errors="coerce")

    # ── 3. References cleaning ────────────────────────────────────────────
    # IMPORTANT: do NOT lowercase — preserve original case, just strip whitespace
    for col in ref_cols:
        s = df[col].copy()
        # Convert floats that are integers (e.g. 12345.0 -> "12345")
        s = s.apply(
            lambda x: str(int(x)) if isinstance(x, float) and not pd.isna(x) and x == int(x)
            else (str(x).strip() if pd.notna(x) else "")
        )
        df[col] = s.str.strip()

    # ── Drop rows where datetime or amount is null ─────────────────────────
    df = df.dropna(subset=["txn_datetime", "amount_clean"])

    logger.info(f"[{side}] Cleaned rows: {len(df)}")

    # ── Build structured records ──────────────────────────────────────────
    records = []
    for idx, row in df.iterrows():
        refs = {}
        for col in ref_cols:
            val = str(row[col]).strip()
            if val and val.lower() != "nan":
                refs[col] = val

        rem = {}
        for c in remaining_cols:
            val = row[c]
            if pd.notna(val):
                rem[str(c)] = str(val)

        # Deterministic checksum based on side + datetime + amount + refs
        base_str = f"{side}|{row['txn_datetime']}|{row['amount_clean']}|"
        for k in sorted(refs.keys()):
            base_str += f"{k}:{refs[k]}|"

        checksum = hashlib.md5(base_str.encode("utf-8")).hexdigest()

        records.append({
            "source_row_num": int(idx),
            "txn_datetime": row["txn_datetime"].to_pydatetime() if pd.notna(row["txn_datetime"]) else None,
            "amount": float(row["amount_clean"]) if pd.notna(row["amount_clean"]) else 0.0,
            "references": refs,
            "remaining_columns": rem,
            "checksum": checksum,
        })

    return records