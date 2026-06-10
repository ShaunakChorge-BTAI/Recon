import pandas as pd


def clean_mapped_dataframe(df, mapping, side):
    m = mapping[side]

    keep_cols = [m["datetime"], m["amount"], *m["references"]]
    keep_cols = list(dict.fromkeys(keep_cols))

    df = df[keep_cols].copy()

    df["txn_datetime"] = pd.to_datetime(df[m["datetime"]], errors="coerce").dt.floor("min")
    df["amount_clean"] = (
        df[m["amount"]]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    df["amount_clean"] = pd.to_numeric(df["amount_clean"], errors="coerce")

    for col in m["references"]:
        df[col] = df[col].astype(str).str.strip().str.lower()

    df = df.dropna(subset=["txn_datetime", "amount_clean"] + m["references"])

    return df