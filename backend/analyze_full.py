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
src_df['ref_Modified_Card'] = src_df['Modified_Card'].astype(str)

dest_df['datetime'] = pd.to_datetime(dest_df['Modified_DateTime'], errors='coerce')
dest_df['amount'] = pd.to_numeric(dest_df['Net Amount'], errors='coerce').fillna(0)
dest_df['ref_Modified_Card'] = dest_df['Modified_Card'].astype(str)

for df in [src_df, dest_df]:
    df['row_id'] = range(len(df))

mapping = {
    "source": {"references": ["ref_Modified_Card"]},
    "dest": {"references": ["ref_Modified_Card"]}
}
engine = MatchingEngine(tol_amount=10, tol_time=10, mapping=mapping) # 10 mins

print("Running full ReconciliationEngine pipeline...")
result = engine.run_all_layers(src_df, dest_df, skip_llm=True)

print("\n--- RESULTS ---")
for layer, data in result['layers'].items():
    print(f"{layer}: {data['count']} matches")

