from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re

import fitz  # PyMuPDF
import numpy as np
import cv2
import pytesseract

# --- CONFIGURATION DES MOTS-CLÉS ---
POS_KW = {
    "DESSINE": 4.0, "DEMANDEUR": 2.5, "CLIENT": 2.0, "APPAREIL": 1.5,
    "DOSSIER": 1.0, "ECHELLE": 2.0, "INDICE": 1.0, "TOL": 1.0,
    "NUANCE": 0.5, "SECTION": 0.5, "COUPE": 0.5,
}

NEG_KW = {
    "CALCUL": 2.0, "CONTRAINTE": 2.0, "DONNEES PREVISIONNELLES": 2.0,
    "INJECTER": 1.0, "ETANCHEITE": 1.0, "DIAGRAMME": 1.0,
}


@dataclass
class PlanCandidate:
    page: int  # 1-indexed
    score: float
    median_len: float
    long_line_ratio: float
    non_axial_ratio: float
    ocr_excerpt: str


def render_page_np(page: fitz.Page, zoom: float = 1.2, max_w: int = 1400) -> np.ndarray:
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if img.shape[2] == 4:
        img = img[:, :, :3]
    h, w = img.shape[:2]
    if w > max_w:
        s = max_w / w
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img


def line_features(gray: np.ndarray) -> dict:
    edges = cv2.Canny(gray, 60, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 110, minLineLength=80, maxLineGap=10)

    if lines is None:
        return dict(line_count=0, median_len=0.0, long_line_ratio=0.0, non_axial_ratio=0.0)

    lens, angs = [], []
    for x1, y1, x2, y2 in lines[:, 0]:
        dx, dy = x2 - x1, y2 - y1
        lens.append(math.hypot(dx, dy))
        a = abs(math.degrees(math.atan2(dy, dx))) % 180
        if a > 90: a = 180 - a
        angs.append(a)

    lens, angs = np.array(lens), np.array(angs)
    axial = (angs < 8) | (np.abs(angs - 90) < 8)

    return dict(
        line_count=len(lens),
        median_len=float(np.median(lens)),
        long_line_ratio=float((lens > 400).mean()),
        non_axial_ratio=float(1.0 - axial.mean()),
    )


def ocr_titleblock_text(page: fitz.Page, zoom: float = 2.5) -> str:
    img = render_page_np(page, zoom=zoom, max_w=2200)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape[:2]

    # Zone du cartouche (Bas-Droite)
    crop = gray[int(h * 0.55):h, int(w * 0.42):w]
    if crop.shape[1] < 1200:
        s = 1200 / crop.shape[1]
        crop = cv2.resize(crop, (1200, int(crop.shape[0] * s)), interpolation=cv2.INTER_CUBIC)

    crop = cv2.GaussianBlur(crop, (3, 3), 0)
    _, thr = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    try:
        txt = pytesseract.image_to_string(thr, lang="fra", config="--oem 1 --psm 6", timeout=12)
    except:
        txt = ""
    return " ".join(txt.upper().split())


def keyword_score(text: str) -> float:
    s = sum(text.count(kw) * w for kw, w in POS_KW.items())
    s -= sum(text.count(kw) * w for kw, w in NEG_KW.items())
    return s


def plan_score(line_feat: dict, ocr_text: str) -> float:
    score = max(0.0, (220.0 - line_feat["median_len"]) / 40.0)
    score -= line_feat["long_line_ratio"] * 6.0
    score += min(2.0, line_feat["non_axial_ratio"] * 10.0)
    score += keyword_score(ocr_text)
    return score


def find_fab_plan_pages(pdf_path: str | Path, top_k: int = 3, min_score: float = 3.0) -> tuple[
    int | None, list[PlanCandidate]]:
    """
    Analyse le PDF et ne retourne QUE les pages avec un score >= min_score.
    """
    doc = fitz.open(pdf_path)
    all_candidates: list[PlanCandidate] = []

    for i in range(len(doc)):
        page = doc[i]
        img = render_page_np(page)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        lf = line_features(gray)
        ocr_txt = ocr_titleblock_text(page)
        score = plan_score(lf, ocr_txt)

        all_candidates.append(
            PlanCandidate(
                page=i + 1,
                score=score,
                median_len=lf["median_len"],
                long_line_ratio=lf["long_line_ratio"],
                non_axial_ratio=lf["non_axial_ratio"],
                ocr_excerpt=ocr_txt[:140],
            )
        )

    # 1. Filtrage strict sur le score
    filtered = [c for c in all_candidates if c.score >= min_score]

    # 2. Tri par score décroissant
    filtered.sort(key=lambda c: c.score, reverse=True)

    # 3. Limitation au top_k
    final_candidates = filtered[:top_k]

    best_page = final_candidates[0].page if final_candidates else None

    return best_page, final_candidates


# --- EXECUTION ---
if __name__ == "__main__":
    # Paramètre min_score réglé sur 1.0 comme demandé
    best, candidates = find_fab_plan_pages("plan5.pdf", top_k=5, min_score=3.0)

    if not candidates:
        print("[-] Aucune page n'a atteint le score minimum de 2.0.")
    else:
       # print(f"[+] Meilleure page détectée : {best}")
       # print("-" * 30)
        for c in candidates:
            print(f"Page {c.page:02d} | Score: {c.score:5.2f} | OCR: {c.ocr_excerpt[:60]}...")
