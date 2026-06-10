from sqlalchemy import create_engine, Column, Integer, String, DateTime, Numeric, Text, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/recon_db"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    side = Column(String, nullable=False)  # source / dest
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    temp_path = Column(String, nullable=False)
    status = Column(String, default="uploaded")
    detected_columns = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MappedRecord(Base):
    __tablename__ = "mapped_records"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)
    side = Column(String, nullable=False)

    txn_datetime = Column(DateTime(timezone=False), nullable=True)
    amount = Column(Numeric(18, 4), nullable=True)

    # store all mapped refs safely as JSON
    references = Column(JSON, nullable=False)

    # deterministic string version for matching/grouping
    ref_key = Column(Text, nullable=False)

    # store original mapped column names + values (only mapped cols, not full row)
    mapped_payload = Column(JSON, nullable=False)

    source_row_num = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReconRun(Base):
    __tablename__ = "recon_runs"

    id = Column(Integer, primary_key=True, index=True)
    source_upload_id = Column(Integer, nullable=False)
    dest_upload_id = Column(Integer, nullable=False)
    tol_amount = Column(Numeric(18, 4), nullable=False)
    tol_time_minutes = Column(Integer, nullable=False)
    status = Column(String, default="running")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReconMatch(Base):
    __tablename__ = "recon_matches"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("recon_runs.id"), nullable=False)

    layer = Column(String, nullable=False)
    source_record_id = Column(Integer, nullable=True)
    dest_record_id = Column(Integer, nullable=True)

    match_type = Column(String, nullable=True)
    confidence_score = Column(Numeric(10, 4), nullable=True)
    reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


def init_db():
    Base.metadata.create_all(bind=engine)