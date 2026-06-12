"""
Test script to verify:
1. Matching engine produces consistent results on multiple runs
2. The same inputs produce the same outputs deterministically
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from parsers import read_any_file
from utils import clean_mapped_dataframe
from matching_engine import MatchingEngine

def recs_to_df(records):
    rows = []
    for i, r in enumerate(records):
        row = {
            "record_id": i,
            "datetime": r["txn_datetime"],
            "amount": r["amount"],
            **r["references"],
        }
        rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def run_once(src_path, dest_path, mapping):
    src_raw = read_any_file(src_path)
    dest_raw = read_any_file(dest_path)

    src_records = clean_mapped_dataframe(src_raw, mapping, "source")
    dest_records = clean_mapped_dataframe(dest_raw, mapping, "dest")

    src_df = recs_to_df(src_records)
    dest_df = recs_to_df(dest_records)

    engine_mapping = {
        "source": {"references": mapping["source"]["references"]},
        "dest": {"references": mapping["dest"]["references"]}
    }

    engine = MatchingEngine(tol_amount=10, tol_time=10, mapping=engine_mapping)
    result = engine.run_all_layers(src_df, dest_df, skip_llm=True)

    return {
        "total_src": len(src_df),
        "total_dest": len(dest_df),
        "total_matched": result["total_matched"],
        "unmatched_src": len(result["unmatched_src"]),
        "unmatched_dest": len(result["unmatched_dest"]),
        "layers": {k: v["count"] for k, v in result["layers"].items()},
    }


def main():
    src_path = r"uploads/Many_source_Template (1).xlsx"
    dest_path = r"uploads/manytomany_dest_Template (1).xlsx"

    mapping = {
        "source": {
            "datetime": "Modified_DateTime",
            "amount": "CASHIER_CREDIT",
            "references": ["CREDIT_CARD_SUPPLEMENT", "Modified_Card"]
        },
        "dest": {
            "datetime": "Modified_DateTime",
            "amount": "Value_of_Sale",
            "references": ["Transaction_Description", "Modified_Card"]
        },
        "date_mode": "datetime",
        "date_format": ""
    }

    print("=" * 60)
    print("CONSISTENCY TEST: Running 3 times with same data")
    print("=" * 60)

    results = []
    for i in range(3):
        r = run_once(src_path, dest_path, mapping)
        results.append(r)
        print(f"\nRun {i+1}:")
        print(f"  Source rows: {r['total_src']}")
        print(f"  Dest rows:   {r['total_dest']}")
        print(f"  Matched:     {r['total_matched']}")
        print(f"  Unmatched src: {r['unmatched_src']}")
        print(f"  Unmatched dest:{r['unmatched_dest']}")
        for layer, count in r["layers"].items():
            if count > 0:
                print(f"    {layer}: {count}")

    print("\n" + "=" * 60)
    all_same = all(r["total_matched"] == results[0]["total_matched"] for r in results)
    print(f"CONSISTENCY CHECK: {'PASS ✓' if all_same else 'FAIL ✗'}")
    if not all_same:
        print(f"  Matched values: {[r['total_matched'] for r in results]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
