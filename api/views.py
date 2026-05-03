from __future__ import annotations

import io
import logging
import os
import re
import time
from time import perf_counter
from typing import Any

import numpy as np
from django.conf import settings
from django.db.models import Case, IntegerField, Q, When
from PIL import Image
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from .permissions import IsAdminOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.ocr_pipeline import try_rotations_and_ocr

from .models import Medicine, MedicineHistoryEntry
from .search import search_medicines_ranked
from .serializers import MedicineHistoryEntrySerializer, MedicineSerializer

logger = logging.getLogger(__name__)

_MEDICINE_CACHE: dict[str, Any] = {
    "loaded_at": 0.0,
    "ttl_seconds": 300,
    "items": [],
}

_DEFAULT_OCR_STOPWORDS = {
    "a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with",
}


def _ocr_angles() -> tuple[int, ...]:
    raw = str(getattr(settings, "OCR_FAST_ANGLE_SET", getattr(settings, "OCR_ROTATION_ANGLES", "0,-10,10")))
    try:
        parsed = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError:
        logger.warning("Invalid OCR_FAST_ANGLE_SET/OCR_ROTATION_ANGLES=%r; using defaults", raw)
        return (0, -10, 10)
    return parsed or (0, -10, 10)


def _tesseract_psms() -> tuple[str, ...]:
    raw = str(getattr(settings, "OCR_TESSERACT_PSMS", "7"))
    parsed = tuple(chunk.strip() for chunk in raw.split(",") if chunk.strip())
    return parsed or ("7",)


def _max_upload_bytes() -> int:
    # Falls back to 8 MB unless overridden in Django settings.
    return int(getattr(settings, "OCR_MAX_UPLOAD_BYTES", 8 * 1024 * 1024))


def _load_yolo_model() -> Any | None:
    model_path = getattr(settings, "YOLO_MODEL_PATH", "drug_detector.pt")
    if not os.path.exists(model_path):
        logger.warning("YOLO model not found at %s. Full image OCR will be used.", model_path)
        return None

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.warning("ultralytics is not installed. YOLO detection disabled.")
        return None

    try:
        return YOLO(model_path)
    except Exception:
        logger.exception("Failed to load YOLO model from %s. Full image OCR will be used.", model_path)
        return None


yolo_model = _load_yolo_model()


def _pil_to_rgb_array(pil_img: Image.Image) -> np.ndarray:
    return np.array(pil_img.convert("RGB"), dtype=np.uint8)


def _resize_for_ocr(image_rgb: np.ndarray) -> np.ndarray:
    max_dimension = int(getattr(settings, "OCR_MAX_DIMENSION", 1600))
    h, w = image_rgb.shape[:2]
    largest = max(h, w)
    if largest <= max_dimension:
        return image_rgb
    scale = max_dimension / float(largest)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resampling = getattr(Image, "Resampling", Image).BILINEAR
    return np.array(Image.fromarray(image_rgb).resize((new_w, new_h), resample=resampling), dtype=np.uint8)


def _box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    denom = (area_a + area_b - inter_area)
    return (inter_area / denom) if denom > 0 else 0.0


def _extract_crops(image_rgb: np.ndarray) -> tuple[list[np.ndarray], dict[str, int]]:
    meta = {"crop_count_raw": 0, "crop_count_used": 0}
    if yolo_model is None:
        meta["crop_count_raw"] = 1
        meta["crop_count_used"] = 1
        return [image_rgb], meta

    try:
        results = yolo_model(image_rgb)
    except Exception:
        logger.exception("YOLO inference failed. Falling back to full image OCR.")
        meta["crop_count_raw"] = 1
        meta["crop_count_used"] = 1
        return [image_rgb], meta

    candidates: list[tuple[tuple[int, int, int, int], float, int]] = []
    h_img, w_img = image_rgb.shape[:2]
    for result in results:
        boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None else []
        confs = result.boxes.conf.cpu().numpy() if (result.boxes is not None and result.boxes.conf is not None) else []
        for idx, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box)
            pad_x = max(4, int((x2 - x1) * 0.03))
            pad_y = max(4, int((y2 - y1) * 0.03))
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w_img, x2 + pad_x)
            y2 = min(h_img, y2 + pad_y)
            if x2 > x1 and y2 > y1:
                conf = float(confs[idx]) if idx < len(confs) else 0.0
                area = (x2 - x1) * (y2 - y1)
                candidates.append(((x1, y1, x2, y2), conf, area))
    meta["crop_count_raw"] = len(candidates)

    if not candidates:
        meta["crop_count_used"] = 1
        return [image_rgb], meta

    candidates.sort(key=lambda item: (item[1], item[2]), reverse=True)
    use_dedup = bool(getattr(settings, "OCR_ENABLE_CROP_DEDUP", True))
    iou_threshold = float(getattr(settings, "OCR_CROP_DEDUP_IOU_THRESHOLD", 0.50))
    max_crops = max(1, int(getattr(settings, "OCR_MAX_CROPS", 3)))

    kept: list[tuple[int, int, int, int]] = []
    for box, _conf, _area in candidates:
        if use_dedup and any(_box_iou(box, existing) >= iou_threshold for existing in kept):
            continue
        kept.append(box)
        if len(kept) >= max_crops:
            break

    if not kept:
        meta["crop_count_used"] = 1
        return [image_rgb], meta

    crops = [image_rgb[y1:y2, x1:x2] for (x1, y1, x2, y2) in kept]
    meta["crop_count_used"] = len(crops)
    return crops, meta


def _ocr_tokens_from_image(image_rgb: np.ndarray) -> tuple[list[str], dict[str, Any]]:
    candidates: list[str] = []
    best_meta: dict[str, Any] = {
        "confidence": 0.0,
        "angle": 0,
        "engine": "",
        "crop_count_raw": 0,
        "crop_count_used": 0,
        "angles_used": 0,
        "engine_calls": 0,
    }
    angles = _ocr_angles()
    early_exit_confidence = float(getattr(settings, "OCR_EARLY_EXIT_CONFIDENCE", 0.90))
    easyocr_fast_stop_confidence = float(getattr(settings, "OCR_EASYOCR_FAST_STOP_CONFIDENCE", 0.94))
    skip_tesseract_if_easyocr_confident = float(
        getattr(settings, "OCR_SKIP_TESSERACT_IF_EASYOCR_CONFIDENT", 0.88)
    )
    use_tesseract = bool(getattr(settings, "OCR_USE_TESSERACT", False))
    tesseract_psms = _tesseract_psms()
    stats: dict[str, int] = {"angles_used": 0, "engine_calls": 0}
    crops, crop_meta = _extract_crops(image_rgb)
    best_meta["crop_count_raw"] = crop_meta["crop_count_raw"]
    best_meta["crop_count_used"] = crop_meta["crop_count_used"]

    for crop in crops:
        best_text, best_conf, angle, engine = try_rotations_and_ocr(
            crop,
            debug=False,
            angles=angles,
            early_exit_confidence=early_exit_confidence,
            easyocr_fast_stop_confidence=easyocr_fast_stop_confidence,
            skip_tesseract_if_easyocr_confident=skip_tesseract_if_easyocr_confident,
            use_tesseract=use_tesseract,
            tesseract_psms=tesseract_psms,
            stats=stats,
        )
        if best_conf >= best_meta["confidence"]:
            best_meta = {"confidence": best_conf, "angle": angle, "engine": engine}
        if not best_text:
            continue

        normalized_candidates = _prepare_ocr_candidates(best_text)
        if normalized_candidates:
            candidates.extend(normalized_candidates)
    best_meta["crop_count_raw"] = crop_meta["crop_count_raw"]
    best_meta["crop_count_used"] = crop_meta["crop_count_used"]
    best_meta["angles_used"] = stats["angles_used"]
    best_meta["engine_calls"] = stats["engine_calls"]
    return list(dict.fromkeys(candidates)), best_meta


def _normalized_stopwords() -> set[str]:
    raw = str(getattr(settings, "OCR_TOKEN_STOPWORDS", ",".join(sorted(_DEFAULT_OCR_STOPWORDS))))
    parsed = {normalize for normalize in (item.strip().lower() for item in raw.split(",")) if normalize}
    return parsed or set(_DEFAULT_OCR_STOPWORDS)


def _normalize_ocr_token(token: str) -> str:
    stripped = re.sub(r"(^[^\w]+|[^\w]+$)", "", token.strip().lower())
    return re.sub(r"\s+", " ", stripped).strip()


def _prepare_ocr_candidates(raw_text: str) -> list[str]:
    min_token_len = int(getattr(settings, "OCR_MIN_TOKEN_LENGTH", 3))
    stopwords = _normalized_stopwords()
    normalized_tokens = [_normalize_ocr_token(chunk) for chunk in raw_text.split()]
    normalized_tokens = [token for token in normalized_tokens if token]
    if not normalized_tokens:
        return []

    phrase_token = " ".join(normalized_tokens)
    filtered_tokens: list[str] = []
    for token in normalized_tokens:
        if len(token) < min_token_len:
            continue
        if token in stopwords:
            continue
        if re.fullmatch(r"\d+", token):
            continue
        filtered_tokens.append(token)

    return [phrase_token, *filtered_tokens]


def _load_medicine_index() -> list[tuple[int, str]]:
    now = time.time()
    ttl = int(getattr(settings, "OCR_MEDICINE_CACHE_TTL_SECONDS", _MEDICINE_CACHE["ttl_seconds"]))
    cached_items = _MEDICINE_CACHE["items"]
    if cached_items and (now - _MEDICINE_CACHE["loaded_at"]) < ttl:
        return cached_items

    rows = list(Medicine.objects.values_list("id", "trade_name"))
    _MEDICINE_CACHE["items"] = rows
    _MEDICINE_CACHE["loaded_at"] = now
    _MEDICINE_CACHE["ttl_seconds"] = ttl
    logger.info("OCR medicine index refreshed: count=%s ttl_seconds=%s", len(rows), ttl)
    return rows


def _fuzzy_search_medicines(
    query: str,
    limit: int,
    query_weight: float = 1.0,
    length_penalty_strength_multiplier: float = 1.0,
) -> list[dict[str, Any]]:
    ranked = search_medicines_ranked(
        query,
        limit=limit,
        query_weight=query_weight,
        length_penalty_strength_multiplier=length_penalty_strength_multiplier,
    )
    return ranked


def _confidence_tier(ocr_confidence: float, top_score: float) -> str:
    low_threshold = float(getattr(settings, "OCR_LOW_CONFIDENCE_THRESHOLD", 0.72))
    high_threshold = float(getattr(settings, "OCR_HIGH_CONFIDENCE_THRESHOLD", 0.85))

    combined = (float(ocr_confidence) * 0.55) + (float(top_score) * 0.45)
    if combined >= high_threshold:
        return "high"
    if combined >= low_threshold:
        return "medium"
    return "low"


def _response_action(tier: str) -> str:
    return "retake_photo" if tier == "low" else "show_results"


class MedicineViewSet(viewsets.ModelViewSet):
    serializer_class = MedicineSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = Medicine.objects.all()
        search = self.request.query_params.get("search", "").strip()
        if search:
            limit = int(getattr(settings, "SEARCH_COMBINED_TOP_K", 200))
            ranked = search_medicines_ranked(search, limit=limit, query_weight=1.0)
            ranked_ids = [item["medicine"].id for item in ranked]
            if not ranked_ids:
                return queryset.none()
            order_expr = Case(
                *[When(pk=medicine_id, then=idx) for idx, medicine_id in enumerate(ranked_ids)],
                output_field=IntegerField(),
            )
            queryset = queryset.filter(pk__in=ranked_ids).order_by(order_expr)
        return queryset

    @action(detail=True, methods=["get"], url_path="interactions", permission_classes=[IsAuthenticated])
    def interactions(self, request, pk=None):
        """
        Returns all medicines that may conflict with this medicine:
        - same_active_ingredient: same ingredient → duplication / overdose risk (HIGH)
        - similar_active_ingredient: related ingredient → drug interaction risk (MEDIUM)
        """
        medicine = self.get_object()
        conflicts: list[dict] = []
        seen_ids: set[int] = {medicine.pk}

        # ── 1. Same active ingredient ─────────────────────────────────────────
        if medicine.active_ingredient.strip():
            same_qs = Medicine.objects.filter(
                active_ingredient__iexact=medicine.active_ingredient
            ).exclude(pk=medicine.pk)

            for med in same_qs:
                seen_ids.add(med.pk)
                conflicts.append({
                    "conflict_type": "same_active_ingredient",
                    "risk_level": "high",
                    "conflict_reason": (
                        f"Contains the same active ingredient: {medicine.active_ingredient}. "
                        "Taking both may cause duplication or overdose."
                    ),
                    "matched_ingredient": medicine.active_ingredient,
                    "medicine": MedicineSerializer(med).data,
                })

        # ── 2. Similar / interacting active ingredients ───────────────────────
        if medicine.similar_active_ingredients.strip():
            raw_ingredients = re.split(r"[,;\n]+", medicine.similar_active_ingredients)
            parsed = [i.strip() for i in raw_ingredients if len(i.strip()) >= 3]

            for ingredient in parsed:
                similar_qs = Medicine.objects.filter(
                    active_ingredient__icontains=ingredient
                ).exclude(pk__in=seen_ids)

                for med in similar_qs:
                    seen_ids.add(med.pk)
                    conflicts.append({
                        "conflict_type": "similar_active_ingredient",
                        "risk_level": "medium",
                        "conflict_reason": (
                            f"Contains a similar or interacting ingredient: {ingredient}. "
                            "Consult a pharmacist before combining."
                        ),
                        "matched_ingredient": ingredient,
                        "medicine": MedicineSerializer(med).data,
                    })

        return Response({
            "medicine": MedicineSerializer(medicine).data,
            "interaction_notes": medicine.interaction_notes,
            "similarity_risk_symptoms": medicine.similarity_risk_symptoms,
            "switching_note": medicine.switching_note,
            "total_conflicts": len(conflicts),
            "conflicts": conflicts,
        })


class MedicineHistoryViewSet(viewsets.ModelViewSet):
    serializer_class = MedicineHistoryEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            MedicineHistoryEntry.objects.select_related("medicine")
            .filter(user=self.request.user)
        )
        status_filter = self.request.query_params.get("status")
        if status_filter in {"current", "past"}:
            queryset = queryset.filter(status=status_filter)

        start_date_from = self.request.query_params.get("start_date_from")
        if start_date_from:
            queryset = queryset.filter(start_date__gte=start_date_from)
        start_date_to = self.request.query_params.get("start_date_to")
        if start_date_to:
            queryset = queryset.filter(start_date__lte=start_date_to)

        end_date_from = self.request.query_params.get("end_date_from")
        if end_date_from:
            queryset = queryset.filter(end_date__gte=end_date_from)
        end_date_to = self.request.query_params.get("end_date_to")
        if end_date_to:
            queryset = queryset.filter(end_date__lte=end_date_to)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OCRMedicineSearchView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        req_started = perf_counter()
        decode_started = None
        ocr_started = None
        search_started = None

        image_file = request.FILES.get("image")
        if image_file is None:
            return Response(
                {"error": "No image provided. Send a multipart field named 'image'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload_limit = _max_upload_bytes()
        incoming_size = getattr(image_file, "size", None)
        if incoming_size is not None and incoming_size > upload_limit:
            logger.warning(
                "OCR upload rejected: size=%s max=%s user_id=%s",
                incoming_size,
                upload_limit,
                request.user.id,
            )
            return Response(
                {"error": f"Uploaded image exceeds size limit ({upload_limit} bytes)."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        try:
            top_k = int(request.data.get("top_k", getattr(settings, "OCR_MAX_CANDIDATES", 5)))
        except (TypeError, ValueError):
            return Response({"error": "top_k must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        top_k = min(max(top_k, 1), 20)

        try:
            decode_started = perf_counter()
            image_bytes = image_file.read()
            Image.MAX_IMAGE_PIXELS = 40_000_000  # ~40 MP — reject decompression bombs
            pil_img = Image.open(io.BytesIO(image_bytes))
            pil_img.load()  # force full decode so PIL catches corrupt/bomb images early
            image_rgb = _pil_to_rgb_array(pil_img)
            image_rgb = _resize_for_ocr(image_rgb)
        except Exception:
            logger.exception("Image decode failed")
            return Response({"error": "Cannot decode the provided image."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ocr_started = perf_counter()
            tokens, meta = _ocr_tokens_from_image(image_rgb)
        except Exception:
            logger.exception("OCR pipeline failed")
            return Response({"error": "OCR processing failed. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        search_started = perf_counter()

        if not tokens:
            tier = "low"
            action = _response_action(tier)
            message = "Could not confidently read medicine text. Please retake the photo in good light and focus."
            logger.info(
                "ocr_search_result user_id=%s tier=%s action=%s ocr_conf=%.4f top_score=%.4f matches=%s reason=no_tokens",
                request.user.id,
                tier,
                action,
                float(meta["confidence"]),
                0.0,
                0,
            )
            decode_ms = ((ocr_started - decode_started) * 1000.0) if (decode_started and ocr_started) else 0.0
            ocr_ms = ((search_started - ocr_started) * 1000.0) if ocr_started else 0.0
            total_ms = (perf_counter() - req_started) * 1000.0
            logger.warning(
                (
                    "ocr_search_timing user_id=%s decode_ms=%.1f ocr_ms=%.1f search_ms=%.1f total_ms=%.1f "
                    "tokens=%s matches=%s crop_count_raw=%s crop_count_used=%s angles_used=%s engine_calls=%s"
                ),
                request.user.id,
                decode_ms,
                ocr_ms,
                0.0,
                total_ms,
                0,
                0,
                meta.get("crop_count_raw", 0),
                meta.get("crop_count_used", 0),
                meta.get("angles_used", 0),
                meta.get("engine_calls", 0),
            )
            return Response(
                {
                    "ocr_confidence": meta["confidence"],
                    "matched_items": [],
                    "match_confidence_tier": tier,
                    "action_hint": action,
                    "message": message,
                    "processing_time_ms": round(total_ms, 1),
                },
                status=status.HTTP_200_OK,
            )

        seen: dict[int, dict[str, Any]] = {}
        phrase_token = tokens[0]
        phrase_hits: list[dict[str, Any]] = []
        phrase_top_score = 0.0
        if " " in phrase_token:
            phrase_hits = _fuzzy_search_medicines(
                phrase_token,
                limit=top_k,
                query_weight=1.25,
                length_penalty_strength_multiplier=1.0,
            )
            for hit in phrase_hits:
                med_id = hit["medicine"].id
                seen[med_id] = hit
            if phrase_hits:
                phrase_top_score = max(float(hit.get("score", 0.0)) for hit in phrase_hits)

        phrase_gate = float(getattr(settings, "OCR_RESULT_FLOOR", 0.60))
        phrase_ok = bool(phrase_hits) and phrase_top_score >= phrase_gate
        strong_phrase_threshold = float(getattr(settings, "OCR_PHRASE_STRONG_SCORE", 0.85))
        for idx, token in enumerate(tokens):
            if idx == 0:
                continue
            query_weight = 1.0
            penalty_multiplier = 1.0
            if phrase_ok and " " in phrase_token:
                query_weight = 0.90
                penalty_multiplier = 1.15
                if phrase_top_score >= strong_phrase_threshold:
                    query_weight = 0.80
                    penalty_multiplier = 1.25
            elif not phrase_ok:
                query_weight = 0.85
                penalty_multiplier = 1.35
            for hit in _fuzzy_search_medicines(
                token,
                limit=top_k,
                query_weight=query_weight,
                length_penalty_strength_multiplier=penalty_multiplier,
            ):
                med_id = hit["medicine"].id
                if med_id not in seen or hit["_rank_score"] > seen[med_id]["_rank_score"]:
                    seen[med_id] = hit

        result_floor = float(getattr(settings, "OCR_RESULT_FLOOR", 0.60))
        matches = [item for item in seen.values() if float(item.get("score", 0.0)) >= result_floor]
        matches = sorted(matches, key=lambda item: item["_rank_score"], reverse=True)

        top_score = float(matches[0]["score"]) if matches else 0.0
        tier = _confidence_tier(float(meta["confidence"]), top_score)
        action = _response_action(tier)
        low_tier_cap = int(getattr(settings, "OCR_LOW_CONFIDENCE_MAX_RESULTS", 2))
        if tier == "low":
            top_k = min(top_k, low_tier_cap)
        matches = matches[:top_k]
        include_match_debug = bool(getattr(settings, "OCR_INCLUDE_MATCH_DEBUG", True))
        serialized_matches: list[dict[str, Any]] = []
        for item in matches:
            medicine = item["medicine"]
            payload = MedicineSerializer(medicine).data
            payload["name"] = medicine.trade_name
            payload["score"] = item["score"]
            if include_match_debug:
                payload["_rank_score"] = item["_rank_score"]
                payload["matched_query"] = item["matched_query"]
                payload["debug_length_factor"] = item["_debug_length_factor"]
                payload["debug_length_ratio"] = item["_debug_length_ratio"]
                payload["debug_query_length"] = item["_debug_query_len"]
                payload["debug_matched_length"] = item["_debug_match_len"]
            serialized_matches.append(payload)

        message = ""
        if tier == "low":
            message = "Low confidence result. Please retake the photo in brighter light and ensure the name is centered."

        logger.info(
            (
                "ocr_search_result user_id=%s tier=%s action=%s ocr_conf=%.4f top_score=%.4f "
                "matches=%s tokens=%s low_confidence=%s retake=%s no_result=%s"
            ),
            request.user.id,
            tier,
            action,
            float(meta["confidence"]),
            top_score,
            len(matches),
            len(tokens),
            int(tier == "low"),
            int(action == "retake_photo"),
            int(not matches),
        )

        decode_ms = ((ocr_started - decode_started) * 1000.0) if (decode_started and ocr_started) else 0.0
        ocr_ms = ((search_started - ocr_started) * 1000.0) if ocr_started else 0.0
        search_ms = (perf_counter() - search_started) * 1000.0 if search_started else 0.0
        total_ms = (perf_counter() - req_started) * 1000.0
        logger.warning(
            (
                "ocr_search_timing user_id=%s decode_ms=%.1f ocr_ms=%.1f search_ms=%.1f total_ms=%.1f "
                "tokens=%s matches=%s crop_count_raw=%s crop_count_used=%s angles_used=%s engine_calls=%s"
            ),
            request.user.id,
            decode_ms,
            ocr_ms,
            search_ms,
            total_ms,
            len(tokens),
            len(serialized_matches),
            meta.get("crop_count_raw", 0),
            meta.get("crop_count_used", 0),
            meta.get("angles_used", 0),
            meta.get("engine_calls", 0),
        )

        return Response(
            {
                "ocr_confidence": meta["confidence"],
                "matched_items": serialized_matches,
                "match_confidence_tier": tier,
                "action_hint": action,
                "message": message,
                "processing_time_ms": round(total_ms, 1),
            },
            status=status.HTTP_200_OK,
        )
