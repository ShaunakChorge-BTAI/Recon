"""
One-time migration script to add new columns to existing SQLite/PostgreSQL database.
Run once after updating database.py schema.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "recon.db")

print(f"Migrating: {db_path}")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# ─── history_table ────────────────────────────────────────────────
cur.execute("PRAGMA table_info(history_table)")
existing = [row[1] for row in cur.fetchall()]
print("history_table existing cols:", existing)

history_new = [
    ("source_filename", "TEXT"),
    ("dest_filename", "TEXT"),
    ("date_mode", "TEXT"),
    ("date_format", "TEXT"),
    ("total_source", "INTEGER DEFAULT 0"),
    ("total_dest", "INTEGER DEFAULT 0"),
    ("total_matched", "INTEGER DEFAULT 0"),
    ("total_unmatched", "INTEGER DEFAULT 0"),
    ("layer0_count", "INTEGER DEFAULT 0"),
    ("layer1_count", "INTEGER DEFAULT 0"),
    ("layer2_count", "INTEGER DEFAULT 0"),
    ("layer3_count", "INTEGER DEFAULT 0"),
    ("layer4_count", "INTEGER DEFAULT 0"),
    ("layer5_count", "INTEGER DEFAULT 0"),
    ("layer0_time_sec", "REAL DEFAULT 0"),
    ("layer1_time_sec", "REAL DEFAULT 0"),
    ("layer2_time_sec", "REAL DEFAULT 0"),
    ("layer3_time_sec", "REAL DEFAULT 0"),
    ("layer4_time_sec", "REAL DEFAULT 0"),
    ("layer5_time_sec", "REAL DEFAULT 0"),
    ("total_duration_sec", "REAL DEFAULT 0"),
    ("excel_path", "TEXT"),
    ("completed_at", "TIMESTAMP"),
]

for col, typ in history_new:
    if col not in existing:
        sql = f"ALTER TABLE history_table ADD COLUMN {col} {typ}"
        cur.execute(sql)
        print(f"  Added: {col}")
    else:
        print(f"  Skip: {col} (exists)")

# ─── reconciled_table ─────────────────────────────────────────────
cur.execute("PRAGMA table_info(reconciled_table)")
rec_existing = [row[1] for row in cur.fetchall()]
print("reconciled_table existing cols:", rec_existing)

reconciled_new = [
    ("source_datetime", "TIMESTAMP"),
    ("source_amount", "NUMERIC"),
    ("source_refs", "TEXT"),
    ("dest_datetime", "TIMESTAMP"),
    ("dest_amount", "NUMERIC"),
    ("dest_refs", "TEXT"),
]

for col, typ in reconciled_new:
    if col not in rec_existing:
        cur.execute(f"ALTER TABLE reconciled_table ADD COLUMN {col} {typ}")
        print(f"  Added to reconciled_table: {col}")
    else:
        print(f"  Skip: {col} (exists)")

# ─── uploaded_files ───────────────────────────────────────────────
cur.execute("PRAGMA table_info(uploaded_files)")
up_existing = [row[1] for row in cur.fetchall()]

if "row_count" not in up_existing:
    cur.execute("ALTER TABLE uploaded_files ADD COLUMN row_count INTEGER")
    print("  Added: row_count to uploaded_files")

# ─── unreconciled_table ───────────────────────────────────────────
cur.execute("PRAGMA table_info(unreconciled_table)")
unrec_existing = [row[1] for row in cur.fetchall()]
if "run_id" not in unrec_existing:
    cur.execute("ALTER TABLE unreconciled_table ADD COLUMN run_id INTEGER")
    print("  Added: run_id to unreconciled_table")

# ─── exclude_table ────────────────────────────────────────────────
cur.execute("PRAGMA table_info(exclude_table)")
exc_existing = [row[1] for row in cur.fetchall()]
for col, typ in [("side", "TEXT"), ("run_id", "INTEGER")]:
    if col not in exc_existing:
        cur.execute(f"ALTER TABLE exclude_table ADD COLUMN {col} {typ}")
        print(f"  Added: {col} to exclude_table")

conn.commit()
conn.close()
print("\nMigration complete!")
