import os
import json
import uuid
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, SessionLocal, UploadedFile, MappedRecord, ReconRun
from parsers import read_any_file
from utils import clean_mapped_dataframe

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

JOBS = {}

init_db()


@app.post("/upload")
async def upload(source: UploadFile = File(...), dest: UploadFile = File(...)):
    db = SessionLocal()
    try:
        def save_file(file: UploadFile, side: str):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{side}_{timestamp}_{file.filename}"
            path = os.path.join(UPLOAD_DIR, filename)

            with open(path, "wb") as f:
                f.write(file.file.read())

            sample_df = read_any_file(path).head(5)

            rec = UploadedFile(
                side=side,
                filename=file.filename,
                file_type=os.path.splitext(file.filename)[1].lower(),
                temp_path=path,
                detected_columns=sample_df.columns.tolist(),
                status="uploaded"
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)

            return {
                "upload_id": rec.id,
                "columns": sample_df.columns.tolist(),
                "path": path
            }

        src_info = save_file(source, "source")
        dest_info = save_file(dest, "dest")

        return {
            "source_upload_id": src_info["upload_id"],
            "dest_upload_id": dest_info["upload_id"],
            "source_columns": src_info["columns"],
            "dest_columns": dest_info["columns"]
        }

    finally:
        db.close()


@app.post("/ingest-mapped")
def ingest_mapped(
    source_upload_id: int = Form(...),
    dest_upload_id: int = Form(...),
    mapping: str = Form(...)
):
    db = SessionLocal()
    try:
        mapping_dict = json.loads(mapping)

        def ingest_one(upload_id: int, side: str):
            upload_rec = db.query(UploadedFile).filter(UploadedFile.id == upload_id).first()
            if not upload_rec:
                raise Exception(f"Upload {upload_id} not found")

            df = read_any_file(upload_rec.temp_path)
            df = clean_mapped_dataframe(df, mapping_dict, side)

            rows = []
            for idx, row in df.iterrows():
                refs = {
                    col: row[col]
                    for col in mapping_dict[side]["references"]
                }

                rows.append(
                    MappedRecord(
                        upload_id=upload_id,
                        side=side,
                        txn_datetime=row["txn_datetime"].to_pydatetime(),
                        amount=float(row["amount_clean"]),
                        references=refs,
                        ref_key=" | ".join(str(v) for v in refs.values()),
                        mapped_payload={
                            mapping_dict[side]["datetime"]: str(row[mapping_dict[side]["datetime"]]),
                            mapping_dict[side]["amount"]: str(row[mapping_dict[side]["amount"]]),
                            **refs
                        },
                        source_row_num=int(idx)
                    )
                )

            db.bulk_save_objects(rows)
            upload_rec.status = "mapped"
            db.commit()

        ingest_one(source_upload_id, "source")
        ingest_one(dest_upload_id, "dest")

        return {"status": "mapped"}

    finally:
        db.close()


@app.post("/reconcile_async")
def reconcile_async(
    background_tasks: BackgroundTasks,
    source_upload_id: int = Form(...),
    dest_upload_id: int = Form(...),
    tol_amount: float = Form(...),
    tol_time: int = Form(...)
):
    db = SessionLocal()
    try:
        run = ReconRun(
            source_upload_id=source_upload_id,
            dest_upload_id=dest_upload_id,
            tol_amount=tol_amount,
            tol_time_minutes=tol_time,
            status="running"
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        JOBS[str(run.id)] = {"progress": 0, "status": "running"}

        background_tasks.add_task(
            run_reconciliation_from_db,
            run.id,
            source_upload_id,
            dest_upload_id,
            tol_amount,
            tol_time
        )

        return {"job_id": str(run.id)}

    finally:
        db.close()


@app.get("/progress/{job_id}")
def progress(job_id: str):
    return JOBS.get(job_id, {"progress": 0, "status": "not_found"})