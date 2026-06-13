import pandas as pd
import sys

sys.path.append(r"d:\Library\Documents\Projects\Internship\Recon\backend")
from matching_engine import MatchingEngine

src_file = r"d:\Library\Documents\Projects\Internship\Recon\uploads\Many_source_Template (1).xlsx"
dest_file = r"d:\Library\Documents\Projects\Internship\Recon\uploads\manytomany_dest_Template (1).xlsx"

src_df = pd.read_excel(src_file)
dest_df = pd.read_excel(dest_file)

src_df['datetime'] = pd.to_datetime(src_df['Modified_DateTime'], errors='coerce')
src_df['amount'] = pd.to_numeric(src_df['CASHIER_CREDIT'], errors='coerce').fillna(0)
src_df['ref_1'] = src_df['CREDIT_CARD_SUPPLEMENT'].astype(str)
src_df['ref_2'] = src_df['Modified_Card'].astype(str)

dest_df['datetime'] = pd.to_datetime(dest_df['Modified_DateTime'], errors='coerce')
dest_df['amount'] = pd.to_numeric(dest_df['Net Amount'], errors='coerce').fillna(0)
dest_df['ref_1'] = dest_df['Modified_Card'].astype(str)
dest_df['ref_2'] = dest_df['Transaction_Description'].astype(str)

for df in [src_df, dest_df]:
    df['row_id'] = range(len(df))

mapping = {
    "source": {"references": ["ref_1", "ref_2"]},
    "dest": {"references": ["ref_1", "ref_2"]}
}
engine = MatchingEngine(tol_amount=10, tol_time=10, mapping=mapping) # 10 mins

print("Running full ReconciliationEngine pipeline...")
result = engine.run_all_layers(src_df, dest_df, skip_llm=True)

print("\n--- RESULTS ---")
for layer, data in result['layers'].items():
    print(f"{layer}: {data['count']} matches")

