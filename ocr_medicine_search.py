from __future__ import annotations

import io
import logging
import os
from typing import Any

import numpy as np
from PIL import Image

from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.ocr_pipeline import try_rotations_and_ocr
from api.models import Medicine

logger = logging.getLogger(__name__)

FUZZY_BACKEND = getattr(settings, "FUZZY_BACKEND", "rapidfuzz")
MAX_CANDIDATES = getattr(settings, "OCR_MAX_CANDIDATES", 5)
MIN_SCORE = getattr(settings, "OCR_MIN_SCORE", 0.30)
MEDICINE_NAME_FIELD = getattr(settings, "OCR_MEDICINE_NAME_FIELD", "name_en")
MEDICINE_TABLE = getattr(settings, "OCR_MEDICINE_TABLE", "api_medicine")
YOLO_MODEL_PATH = getattr(settings, "YOLO_MODEL_PATH", "drug_detector.pt")


def _load_yolo_model() -> Any | None:
    if not os.path.exists(YOLO_MODEL_PATH):
        logger.warning("YOLO model not found at %s. Full image OCR will be used.", YOLO_MODEL_PATH)
        return None

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.warning("ultralytics is not installed. YOLO detection disabled.")
        return None

    logger.info("Loading trained YOLO model from %s", YOLO_MODEL_PATH)
    return YOLO(YOLO_MODEL_PATH)


yolo_model = _load_yolo_model()


def _pil_to_rgb_array(pil_img: Image.Image) -> np.ndarray:
    return np.array(pil_img.convert("RGB"), dtype=np.uint8)


def _extract_crops(image_rgb: np.ndarray) -> list[np.ndarray]:
    if yolo_model is None:
        return [image_rgb]

    crops: list[np.ndarray] = []
    try:
        results = yolo_model(image_rgb)
    except Exception:
        logger.exception("YOLO inference failed. Falling back to full image OCR.")
        return [image_rgb]

    h_img, w_img = image_rgb.shape[:2]
    for result in results:
        boxes = result.boxes.xyxy.cpu().numpy()
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            pad_x = max(4, int((x2 - x1) * 0.03))
            pad_y = max(4, int((y2 - y1) * 0.03))
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w_img, x2 + pad_x)
            y2 = min(h_img, y2 + pad_y)
            if x2 > x1 and y2 > y1:
                crops.append(image_rgb[y1:y2, x1:x2])

    return crops or [image_rgb]


def _ocr_tokens_from_image(image_rgb: np.ndarray) -> list[str]:
    candidates: list[str] = []
    for crop in _extract_crops(image_rgb):
        best_text, best_conf, angle, engine = try_rotations_and_ocr(crop, debug=False)
        logger.debug(
            "OCR result | text=%r conf=%.2f angle=%s engine=%s",
            best_text,
            best_conf,
            angle,
            engine,
        )
        if not best_text:
            continue

        tokens = [token.strip() for token in best_text.split() if len(token.strip()) >= 2]
        if tokens:
            candidates.extend([" ".join(tokens), *tokens])

    return list(dict.fromkeys(candidates))


def _search_pg_trgm(query: str, limit: int) -> list[dict[str, Any]]:
    sql = f"""
        SELECT
            id,
            {MEDICINE_NAME_FIELD} AS name,
            similarity(lower({MEDICINE_NAME_FIELD}), lower(%s)) AS score
        FROM {MEDICINE_TABLE}
        WHERE similarity(lower({MEDICINE_NAME_FIELD}), lower(%s)) > %s
        ORDER BY score DESC
        LIMIT %s;
    """
    with connection.cursor() as cur:
        cur.execute(sql, [query, query, MIN_SCORE, limit])
        rows = cur.fetchall()

    return [{"id": row[0], "name": row[1], "score": round(float(row[2]), 4)} for row in rows]


def _search_rapidfuzz(query: str, limit: int) -> list[dict[str, Any]]:
    from rapidfuzz import fuzz
    from rapidfuzz import process as rfprocess

    medicines = Medicine.objects.values("id", MEDICINE_NAME_FIELD)
    choices = {
        str(medicine["id"]): medicine[MEDICINE_NAME_FIELD]
        for medicine in medicines
        if medicine.get(MEDICINE_NAME_FIELD)
    }
    choice_vals = list(choices.values())
    choice_keys = list(choices.keys())

    matches = rfprocess.extract(
        query,
        choice_vals,
        scorer=fuzz.WRatio,
        limit=limit * 3,
        score_cutoff=MIN_SCORE * 100,
    )

    results: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for matched_name, score_100, idx in matches:
        med_id = int(choice_keys[idx])
        score = score_100 / 100.0
        if med_id in seen_ids:
            continue
        seen_ids.add(med_id)
        results.append({"id": med_id, "name": matched_name, "score": round(score, 4)})
        if len(results) >= limit:
            break

    return results


def fuzzy_search_medicines(query: str, limit: int = MAX_CANDIDATES) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []

    if FUZZY_BACKEND == "pg_trgm":
        return _search_pg_trgm(query, limit)

    return _search_rapidfuzz(query, limit)


class OCRMedicineSearchView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        image_file = request.FILES.get("image")
        if image_file is None:
            return Response(
                {"error": "No image provided. Send a multipart field named 'image'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            top_k = int(request.data.get("top_k", MAX_CANDIDATES))
        except (TypeError, ValueError):
            return Response({"error": "top_k must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        top_k = min(max(top_k, 1), 20)

        try:
            pil_img = Image.open(io.BytesIO(image_file.read()))
            image_rgb = _pil_to_rgb_array(pil_img)
        except Exception as exc:
            logger.exception("Image decode failed")
            return Response({"error": f"Cannot decode image: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tokens = _ocr_tokens_from_image(image_rgb)
        except Exception as exc:
            logger.exception("OCR pipeline failed")
            return Response({"error": f"OCR processing failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not tokens:
            return Response(
                {
                    "ocr_raw_text": "",
                    "ocr_tokens": [],
                    "matches": [],
                    "message": "OCR could not extract any text from the image.",
                },
                status=status.HTTP_200_OK,
            )

        seen: dict[int, dict[str, Any]] = {}
        for token in tokens:
            for hit in fuzzy_search_medicines(token, limit=top_k):
                med_id = hit["id"]
                if med_id not in seen or hit["score"] > seen[med_id]["score"]:
                    seen[med_id] = hit

        return Response(
            {
                "ocr_raw_text": tokens[0],
                "ocr_tokens": tokens,
                "matches": sorted(seen.values(), key=lambda item: item["score"], reverse=True)[:top_k],
            },
            status=status.HTTP_200_OK,
        )

