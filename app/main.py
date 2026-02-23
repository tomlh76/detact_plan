from __future__ import annotations

import os

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse

# Import your existing logic
from detect_plan import find_fab_plan_pages, PlanCandidate

APP_NAME = "detect_plan_fab_service"
MAX_PDF_MB = float(os.getenv("MAX_PDF_MB", "35"))
TOP_K = int(os.getenv("TOP_K", "5"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "1.0"))

app = FastAPI(title=APP_NAME)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.post("/detect_plan_fab_raw")
async def detect_plan_fab_raw(request: Request) -> JSONResponse:
    """
    Receive a raw PDF buffer as request body (Content-Type: application/pdf) and return JSON.
    """
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/pdf" not in ctype:
        raise HTTPException(status_code=415, detail="Content-Type must be application/pdf")

    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Empty body.")
    if len(data) > MAX_PDF_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (>{MAX_PDF_MB}MB).")

    with tempfile.TemporaryDirectory() as td:
        tmp_pdf = Path(td) / "input.pdf"
        tmp_pdf.write_bytes(data)

        try:
            best_page, candidates = find_fab_plan_pages(tmp_pdf, top_k=TOP_K, min_score=MIN_SCORE)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Processing error: {type(e).__name__}: {e}")

    payload: Dict[str, Any] = {
        "best_page": best_page,
        "top_k": TOP_K,
        "min_score": MIN_SCORE,
        "candidates": [
            {
                "page": c.page,
                "score": round(float(c.score), 4),
                "median_len": round(float(c.median_len), 4),
                "long_line_ratio": round(float(c.long_line_ratio), 6),
                "non_axial_ratio": round(float(c.non_axial_ratio), 6),
                "ocr_excerpt": c.ocr_excerpt,
            }
            for c in candidates
        ],
    }
    return JSONResponse(content=payload)


@app.post("/detect_plan_fab")
async def detect_plan_fab(pdf: UploadFile = File(...)) -> JSONResponse:
    """
    Receive a PDF file as multipart/form-data and return detected plan pages as JSON.
    """
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF (.pdf).")

    # Read bytes (buffer)
    data = await pdf.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > MAX_PDF_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (>{MAX_PDF_MB}MB).")

    # Write to a temp file for PyMuPDF
    with tempfile.TemporaryDirectory() as td:
        tmp_pdf = Path(td) / "input.pdf"
        tmp_pdf.write_bytes(data)

        try:
            best_page, candidates = find_fab_plan_pages(tmp_pdf, top_k=TOP_K, min_score=MIN_SCORE)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Processing error: {type(e).__name__}: {e}")

    payload: Dict[str, Any] = {
        "best_page": best_page,
        "top_k": TOP_K,
        "min_score": MIN_SCORE,
        "candidates": [
            {
                "page": c.page,
                "score": round(float(c.score), 4),
                "median_len": round(float(c.median_len), 4),
                "long_line_ratio": round(float(c.long_line_ratio), 6),
                "non_axial_ratio": round(float(c.non_axial_ratio), 6),
                "ocr_excerpt": c.ocr_excerpt,
            }
            for c in candidates
        ],
    }
    return JSONResponse(content=payload)
