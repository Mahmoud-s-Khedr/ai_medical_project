from __future__ import annotations

import logging
import warnings
from functools import lru_cache
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)
_TESSERACT_NOT_FOUND_LOGGED = False


def enhance_image_for_ocr(img: np.ndarray) -> np.ndarray:
    """Prepare a crop for OCR by denoising, improving contrast, and upscaling."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img.copy()
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    h, w = gray.shape[:2]
    largest_side = max(h, w)
    if largest_side < 900:
        scale = max(2, int(900 / largest_side))
        gray = cv2.resize(gray, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    return gray


def rotate_bound(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])

    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    matrix[0, 2] += (new_w / 2) - center[0]
    matrix[1, 2] += (new_h / 2) - center[1]

    return cv2.warpAffine(img, matrix, (new_w, new_h), borderMode=cv2.BORDER_REPLICATE)


@lru_cache(maxsize=1)
def _easyocr_reader() -> Any | None:
    try:
        import easyocr
    except ImportError:
        logger.info("easyocr is not installed; skipping EasyOCR engine")
        return None

    warnings.filterwarnings(
        "ignore",
        message="'pin_memory' argument is set as true but no accelerator is found.*",
        category=UserWarning,
    )
    return easyocr.Reader(["en"], gpu=False)


def _run_easyocr(img: np.ndarray) -> tuple[str, float]:
    reader = _easyocr_reader()
    if reader is None:
        return "", 0.0

    try:
        results = reader.readtext(img, detail=1, paragraph=False)
    except Exception:
        logger.exception("EasyOCR failed")
        return "", 0.0

    texts: list[str] = []
    confidences: list[float] = []
    for _bbox, text, confidence in results:
        text = str(text).strip()
        if text:
            texts.append(text)
            confidences.append(float(confidence))

    if not texts:
        return "", 0.0

    return " ".join(texts), sum(confidences) / len(confidences)


def _run_tesseract(img: np.ndarray, psm_modes: tuple[str, ...] = ("7",)) -> tuple[str, float]:
    global _TESSERACT_NOT_FOUND_LOGGED
    try:
        import pytesseract
    except ImportError:
        logger.info("pytesseract is not installed; skipping Tesseract engine")
        return "", 0.0

    best_text = ""
    best_conf = 0.0
    whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_. "

    for psm in psm_modes:
        config = f"--psm {psm} --oem 3 -c tessedit_char_whitelist={whitelist}"
        try:
            text = pytesseract.image_to_string(img, config=config).strip()
            data = pytesseract.image_to_data(
                img,
                config=config,
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.pytesseract.TesseractNotFoundError:
            if not _TESSERACT_NOT_FOUND_LOGGED:
                logger.warning("Tesseract binary not found on PATH; Tesseract OCR disabled.")
                _TESSERACT_NOT_FOUND_LOGGED = True
            return "", 0.0
        except Exception:
            logger.exception("Tesseract failed")
            continue

        confidences = []
        for raw_conf in data.get("conf", []):
            try:
                conf = float(raw_conf)
            except (TypeError, ValueError):
                continue
            if conf >= 0:
                confidences.append(conf / 100.0)

        conf = sum(confidences) / len(confidences) if confidences else 0.0
        if text and conf >= best_conf:
            best_text = " ".join(text.split())
            best_conf = conf

    return best_text, best_conf


def try_rotations_and_ocr(
    crop: np.ndarray,
    debug: bool = False,
    angles: tuple[int, ...] = (0, -10, 10),
    early_exit_confidence: float = 0.92,
    skip_tesseract_if_easyocr_confident: float = 0.88,
    use_tesseract: bool = True,
    tesseract_psms: tuple[str, ...] = ("7",),
    easyocr_fast_stop_confidence: float = 0.94,
    stats: dict[str, int] | None = None,
) -> tuple[str, float, int, str]:
    """
    Run OCR over several rotations and return:
    (best_text, confidence_0_to_1, best_angle, engine_name).
    """
    best_text = ""
    best_conf = 0.0
    best_angle = 0
    best_engine = ""

    # Preprocess once, then rotate the enhanced grayscale image per angle.
    # This avoids repeated denoise/CLAHE/resize work on CPU.
    processed_base = enhance_image_for_ocr(crop)

    def _is_phrase_like(text: str) -> bool:
        tokens = [tok for tok in text.split() if any(ch.isalnum() for ch in tok)]
        return len(tokens) >= 2 and sum(1 for tok in tokens if len(tok) >= 3) >= 2

    for angle in angles:
        if stats is not None:
            stats["angles_used"] = stats.get("angles_used", 0) + 1
        processed = rotate_bound(processed_base, angle) if angle else processed_base

        easy_text, easy_conf = _run_easyocr(processed)
        if stats is not None:
            stats["engine_calls"] = stats.get("engine_calls", 0) + 1
        engine_results = [("easyocr", (easy_text, easy_conf))]
        if use_tesseract and not (easy_text and easy_conf >= skip_tesseract_if_easyocr_confident):
            engine_results.append(("tesseract", _run_tesseract(processed, psm_modes=tesseract_psms)))
            if stats is not None:
                stats["engine_calls"] = stats.get("engine_calls", 0) + 1

        for engine, (text, conf) in engine_results:
            if debug:
                logger.debug("OCR candidate | angle=%s engine=%s conf=%.3f text=%r", angle, engine, conf, text)
            if text and conf >= best_conf:
                best_text = text
                best_conf = conf
                best_angle = angle
                best_engine = engine
        if easy_text and easy_conf >= easyocr_fast_stop_confidence and _is_phrase_like(easy_text):
            if easy_conf >= best_conf:
                best_text = easy_text
                best_conf = easy_conf
                best_angle = angle
                best_engine = "easyocr"
            break
        if best_conf >= early_exit_confidence:
            break

    return best_text, round(float(best_conf), 4), best_angle, best_engine
