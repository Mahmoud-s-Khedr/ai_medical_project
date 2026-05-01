

import io
import logging
import numpy as np
from PIL import Image

from django.conf import settings
from django.db import connection

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# ── your existing Medicine model ──────────────────────────────────────────────
# Adjusted the import path to match your actual api app
from api.models import Medicine

# ── OCR pipeline (paste Cell-B code here or import from its module) ───────────
# If you saved Cell-B as  ai/ocr_pipeline.py  just do:
#   from ai.ocr_pipeline import try_rotations_and_ocr
# Otherwise paste the functions here.
from ai.ocr_pipeline import try_rotations_and_ocr   # ← CHANGE IF NEEDED

logger = logging.getLogger(__name__)

# ── Load YOLO model for Cropping before OCR ───────────────────────────────────
import os
try:
    from ultralytics import YOLO
    # YOLO_MODEL_PATH will default to 'drug_detector.pt' from your Jupyter training output
    YOLO_MODEL_PATH = getattr(settings, "YOLO_MODEL_PATH", "drug_detector.pt")
    if os.path.exists(YOLO_MODEL_PATH):
        logger.info(f"Loading trained YOLO model from {YOLO_MODEL_PATH}")
        yolo_model = YOLO(YOLO_MODEL_PATH)
    else:
        logger.warning(f"YOLO model not found at {YOLO_MODEL_PATH}. Full image OCR will be used.")
        yolo_model = None
except ImportError:
    logger.warning("ultralytics package not installed. YOLO detection disabled.")
    yolo_model = None

# ── tuneable constants (override in settings.py if you like) ──────────────────
FUZZY_BACKEND   = getattr(settings, "FUZZY_BACKEND",   "rapidfuzz")   # "pg_trgm" | "rapidfuzz"
MAX_CANDIDATES  = getattr(settings, "OCR_MAX_CANDIDATES", 5)           # how many matches to return
MIN_SCORE       = getattr(settings, "OCR_MIN_SCORE", 0.30)             # 0..1 — drop results below this


def _pil_to_cv2_rgb(pil_img: Image.Image) -> np.ndarray:
    """PIL Image → uint8 numpy array in RGB order (what the OCR pipeline expects)."""
    pil_img = pil_img.convert("RGB")
    return np.array(pil_img, dtype=np.uint8)


def _ocr_tokens_from_image(image_rgb: np.ndarray) -> list[str]:
    """
    Runs YOLOv8 object detection to crop bounding boxes of medicines,
    then runs the OCR pipeline on the cropped regions.
    Falls back to the full image if no boxes are found.
    """
    import cv2
    from ai.ocr_pipeline import enhance_image_for_ocr   # ← CHANGE IF NEEDED
    
    crops = []
    # 1. Run YOLO inference to detect specific drug boxes
    if yolo_model is not None:
        results = yolo_model(image_rgb)
        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
            for box in boxes:
                x1, y1, x2, y2 = map(int, box)
                if x2 > x1 and y2 > y1:
                    crop_img = image_rgb[y1:y2, x1:x2]
                    crops.append(crop_img)
                    
    # 2. Fallback to full image if YOLO didn't find any bounding boxes
    if not crops:
        logger.debug("No YOLO boxes detected or model disabled. Using full image.")
        crops = [image_rgb]

    all_candidates = []
    
    # 3. Run OCR on each region (YOLO crops, or the full image)
    for crop_img in crops:
        best_text, best_conf, angle, engine = try_rotations_and_ocr(crop_img, debug=False)

        logger.debug("OCR result | text=%r conf=%.2f angle=%s engine=%s",
                     best_text, best_conf, angle, engine)

        if best_text:
            tokens = [t.strip() for t in best_text.split() if len(t.strip()) >= 2]
            full = " ".join(tokens)
            all_candidates.extend([full] + tokens)

    # 4. dedupe, preserve order
    candidates = list(dict.fromkeys(all_candidates))
    return candidates



def _search_pg_trgm(query: str, limit: int) -> list[dict]:
    """
    Uses PostgreSQL's trigram similarity (pg_trgm extension).
    Searches the `name_en` column (since OCR text is mostly English).
    Returns list of dicts: {id, name, score}
    """
    sql = """
        SELECT
            id,
            name_en                              AS name,
            similarity(lower(name_en), lower(%s)) AS score
        FROM api_medicine                     -- Actual table name in the DB
        WHERE similarity(lower(name_en), lower(%s)) > %s
        ORDER BY score DESC
        LIMIT %s;
    """
    with connection.cursor() as cur:
        cur.execute(sql, [query, query, MIN_SCORE, limit])
        rows = cur.fetchall()

    return [{"id": r[0], "name": r[1], "score": round(float(r[2]), 4)} for r in rows]



def _search_rapidfuzz(query: str, limit: int) -> list[dict]:
    """
    Pulls medicine names from the ORM and scores them with rapidfuzz.
    Works with any database. Fast enough for catalogs up to ~200k rows.
    """
    from rapidfuzz import fuzz, process as rfprocess


    qs = Medicine.objects.values("id", "name_en")

    choices     = {str(m["id"]): m["name_en"] for m in qs if m["name_en"]}
    choice_vals = list(choices.values())
    choice_keys = list(choices.keys())

    # WRatio handles partial matches, abbreviations, and case differences well
    matches = rfprocess.extract(
        query,
        choice_vals,
        scorer=fuzz.WRatio,
        limit=limit * 3,          # fetch extra, we'll filter by MIN_SCORE below
        score_cutoff=MIN_SCORE * 100,
    )
    # matches → list of (matched_string, score_0_100, index)

    results = []
    seen_ids = set()
    for matched_name, score_100, idx in matches:
        med_id  = choice_keys[idx]
        score   = score_100 / 100.0
        if score < MIN_SCORE or med_id in seen_ids:
            continue
        seen_ids.add(med_id)
        results.append({"id": int(med_id), "name": matched_name, "score": round(score, 4)})
        if len(results) >= limit:
            break

    return results


#  UNIFIED SEARCH ENTRY-POINT

def fuzzy_search_medicines(query: str, limit: int = MAX_CANDIDATES) -> list[dict]:
    """
    Given a text query, return up to `limit` medicines ranked by
    lexical (character-level) similarity to the query.
    """
    if not query or not query.strip():
        return []

    query = query.strip()

    if FUZZY_BACKEND == "pg_trgm":
        return _search_pg_trgm(query, limit)
    else:
        return _search_rapidfuzz(query, limit)


#  THE VIEW
class OCRMedicineSearchView(APIView):
    """
    POST /api/uploads/ocr-search/

    Multipart form:
        image   (file, required)   — photo of the medicine / prescription
        top_k   (int, optional)    — how many candidates to return (default 5)

    Response 200:
    {
        "ocr_raw_text": "Panadol Extra ...",
        "ocr_tokens":   ["Panadol Extra", "Panadol", "Extra"],
        "matches": [
            {"id": 42, "name": "Panadol Extra", "score": 0.94},
            {"id": 7,  "name": "Panadol",       "score": 0.81},
            ...
        ]
    }
    """
    parser_classes  = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # ── 1. Validate uploaded file ─────────────────────────────────────────
        image_file = request.FILES.get("image")
        if image_file is None:
            return Response(
                {"error": "No image provided. Send a multipart field named 'image'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        top_k = int(request.data.get("top_k", MAX_CANDIDATES))
        top_k = min(max(top_k, 1), 20)   # clamp 1..20

        # ── 2. Decode image ───────────────────────────────────────────────────
        try:
            pil_img   = Image.open(io.BytesIO(image_file.read()))
            image_rgb = _pil_to_cv2_rgb(pil_img)
        except Exception as exc:
            logger.exception("Image decode failed")
            return Response(
                {"error": f"Cannot decode image: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── 3. OCR ────────────────────────────────────────────────────────────
        try:
            tokens = _ocr_tokens_from_image(image_rgb)
        except Exception as exc:
            logger.exception("OCR pipeline failed")
            return Response(
                {"error": f"OCR processing failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not tokens:
            return Response(
                {
                    "ocr_raw_text": "",
                    "ocr_tokens":   [],
                    "matches":      [],
                    "message":      "OCR could not extract any text from the image.",
                },
                status=status.HTTP_200_OK,
            )

        ocr_raw_text = tokens[0]   # first element is the full joined string

        # ── 4. Fuzzy DB search ────────────────────────────────────────────────
        # Strategy: try each token separately and merge results, deduplicated,
        # keeping the highest score per medicine.
        seen: dict[int, dict] = {}
        for token in tokens:
            for hit in fuzzy_search_medicines(token, limit=top_k):
                med_id = hit["id"]
                if med_id not in seen or hit["score"] > seen[med_id]["score"]:
                    seen[med_id] = hit

        # Sort by score descending, return top_k
        matches = sorted(seen.values(), key=lambda x: x["score"], reverse=True)[:top_k]

        # ── 5. Return ─────────────────────────────────────────────────────────
        return Response(
            {
                "ocr_raw_text": ocr_raw_text,
                "ocr_tokens":   tokens,
                "matches":      matches,
            },
            status=status.HTTP_200_OK,
        )

