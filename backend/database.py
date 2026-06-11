from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime,
    Numeric, Text, JSON, ForeignKey, Float
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

import os
from sqlalchemy.exc import OperationalError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.normpath(os.path.join(BASE_DIR, "recon.db"))

DATABASE_URL = os.environ.get("DATABASE_URL")
connect_args = {}

if not DATABASE_URL:
    pg_url = "postgresql+psycopg2://recon:recon@192.168.202.135:5432/recon_db"
    try:
        temp_engine = create_engine(pg_url, pool_pre_ping=True)
        with temp_engine.connect() as conn:
            DATABASE_URL = pg_url
        temp_engine.dispose()
    except Exception:
        DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH}"

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    side = Column(String, nullable=False)           # source / dest
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    temp_path = Column(String, nullable=False)
    status = Column(String, default="uploaded")
    detected_columns = Column(JSON, default=list)
    row_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UnreconciledRecord(Base):
    __tablename__ = "unreconciled_table"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)
    run_id = Column(Integer, nullable=True)         # set after reconcile run
    side = Column(String, nullable=False)           # source / dest

    txn_datetime = Column(DateTime(timezone=False), nullable=True)
    amount = Column(Numeric(18, 4), nullable=True)

    # All mapped refs as JSON {"ref1": "val1", ...}
    references = Column(JSON, nullable=False)

    # All unmapped/remaining columns as JSON
    remaining_columns = Column(JSON, nullable=False)

    checksum = Column(String, nullable=False)
    source_row_num = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HistoryTable(Base):
    __tablename__ = "history_table"

    id = Column(Integer, primary_key=True, index=True)
    source_upload_id = Column(Integer, nullable=False)
    dest_upload_id = Column(Integer, nullable=False)

    # File info
    source_filename = Column(String, nullable=True)
    dest_filename = Column(String, nullable=True)

    # Tolerance settings
    tol_amount = Column(Numeric(18, 4), nullable=False)
    tol_time_minutes = Column(Integer, nullable=False)
    date_mode = Column(String, default="datetime")   # "date" or "datetime"
    date_format = Column(String, nullable=True)       # e.g. "%d/%m/%Y"

    # Run counts
    total_source = Column(Integer, default=0)
    total_dest = Column(Integer, default=0)
    total_matched = Column(Integer, default=0)
    total_unmatched = Column(Integer, default=0)

    # Per-layer match counts
    layer0_count = Column(Integer, default=0)
    layer1_count = Column(Integer, default=0)
    layer2_count = Column(Integer, default=0)
    layer3_count = Column(Integer, default=0)
    layer4_count = Column(Integer, default=0)
    layer5_count = Column(Integer, default=0)

    # Per-layer timing (seconds)
    layer0_time_sec = Column(Float, default=0.0)
    layer1_time_sec = Column(Float, default=0.0)
    layer2_time_sec = Column(Float, default=0.0)
    layer3_time_sec = Column(Float, default=0.0)
    layer4_time_sec = Column(Float, default=0.0)
    layer5_time_sec = Column(Float, default=0.0)

    total_duration_sec = Column(Float, default=0.0)

    status = Column(String, default="running")  # running / completed / failed
    excel_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ReconciledRecord(Base):
    __tablename__ = "reconciled_table"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("history_table.id"), nullable=False)

    layer_matched = Column(String, nullable=False)  # e.g. "Self Knock", "Exact Match"
    match_type = Column(String, nullable=True)       # one-to-one, one-to-many, etc.

    # Source record info
    source_record_id = Column(Integer, nullable=True)
    source_datetime = Column(DateTime(timezone=False), nullable=True)
    source_amount = Column(Numeric(18, 4), nullable=True)
    source_refs = Column(JSON, nullable=True)

    # Dest record info
    dest_record_id = Column(Integer, nullable=True)
    dest_datetime = Column(DateTime(timezone=False), nullable=True)
    dest_amount = Column(Numeric(18, 4), nullable=True)
    dest_refs = Column(JSON, nullable=True)

    confidence_score = Column(Numeric(10, 4), nullable=True)
    reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExcludeRecord(Base):
    __tablename__ = "exclude_table"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("unreconciled_table.id"), nullable=False)
    side = Column(String, nullable=True)
    run_id = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def init_db():
    Base.metadata.create_all(bind=engine)