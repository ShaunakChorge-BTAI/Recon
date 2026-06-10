import io
import os
import csv
import pandas as pd
import pdfplumber


def read_any_file(file_path: str) -> pd.DataFrame:
    lower = file_path.lower()

    if lower.endswith(".csv"):
        return pd.read_csv(file_path)

    if lower.endswith(".xlsx"):
        return pd.read_excel(file_path, engine="openpyxl")

    if lower.endswith(".xls"):
        return pd.read_excel(file_path, engine="xlrd")

    if lower.endswith(".pdf"):
        return read_pdf_as_dataframe(file_path)

    if lower.endswith(".txt"):
        return read_txt_as_dataframe(file_path)

    raise Exception(f"Unsupported file type: {file_path}")


def read_pdf_as_dataframe(file_path: str) -> pd.DataFrame:
    rows = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                rows.extend(table)

    if not rows:
        raise Exception("No tabular data found in PDF")

    header = rows[0]
    data = rows[1:]
    return pd.DataFrame(data, columns=header)


def read_txt_as_dataframe(file_path: str) -> pd.DataFrame:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        sample = f.read(4096)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample)
            return pd.read_csv(file_path, sep=dialect.delimiter)
        except Exception:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            return pd.DataFrame({"text_line": lines})