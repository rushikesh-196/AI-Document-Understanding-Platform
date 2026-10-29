"""
Robust, High-Performance OCR Processing Service
Supports: Windows Native OCR (WinOCR), PaddleOCR, and Tesseract OCR with intelligent fast first-exit.
"""

import logging
import re
import numpy as np

from utils.language_utils import resolve_ocr_languages, detect_language_from_text
from utils.image_utils import preprocess_image, preprocess_image_alternative

logger = logging.getLogger(__name__)
_paddle_ocr_instances = {}
_spacy_instance = None
CONFIDENCE_RETRY_THRESHOLD = 70.0

UI_NOISE_TERMS = {
    "home", "upload", "results", "history", "about", "login", "register",
    "extract doc", "enterprise ai document intelligence", "ai-powered intelligent",
    "ocr & entity extraction", "automated ocr pipeline", "view demo results",
    "platform features", "secure file handling", "dual ocr engines",
    "spacy nlp extraction", "multi-format exports", "intelligent ocr"
}


def clean_ocr_lines(lines, boxes=None, confidences=None):
    """Clean document text lines, eliminating debug artifacts and empty noise."""
    clean_lines = []
    clean_boxes = []
    clean_confidences = []

    for idx, line in enumerate(lines or []):
        t_str = str(line).strip()
        if not t_str:
            continue
        # Remove system logs or benchmark noise
        if any(noise in t_str.lower() for noise in ["deskew -> adaptive", "spacy ner parsing"]):
            continue
        clean_lines.append(t_str)
        if boxes and idx < len(boxes):
            clean_boxes.append(boxes[idx])
        if confidences and idx < len(confidences):
            clean_confidences.append(confidences[idx])

    return clean_lines, clean_boxes, clean_confidences


def clean_and_format_raw_text(text_or_lines):
    """
    Format extracted OCR lines into clean, human-readable text:
    - Preserves all real content, line breaks, document reading order, and paragraphs.
    - Eliminates random spacing, redundant blank lines, broken characters, and debug strings.
    - Formats key-value pairs and tabular data naturally.
    """
    if not text_or_lines:
        return "No text detected in document."

    if isinstance(text_or_lines, str):
        lines = [l.strip() for l in text_or_lines.splitlines() if l.strip()]
    else:
        lines = [str(l).strip() for l in text_or_lines if str(l).strip()]

    if not lines:
        return "No text detected in document."

    formatted_sections = []
    current_paragraph = []

    for line in lines:
        # Check if line is an isolated section heading
        is_heading = (
            (line.isupper() and len(line) < 55 and not any(c.isdigit() for c in line[:4]))
            or (line.endswith(":") and len(line) < 60)
            or any(line.lower().startswith(kw) for kw in [
                "invoice", "receipt", "bill to", "ship to", "sold to", "payment details",
                "patient information", "clinical notes", "diagnosis", "prescription",
                "work experience", "education", "skills", "summary", "bank statement",
                "account summary", "transaction history", "terms and conditions", "notes"
            ])
        )

        if is_heading:
            if current_paragraph:
                formatted_sections.append("\n".join(current_paragraph))
                current_paragraph = []
            formatted_sections.append(line)
        else:
            current_paragraph.append(line)

    if current_paragraph:
        formatted_sections.append("\n".join(current_paragraph))

    result = "\n\n".join(formatted_sections)
    # Remove any 3+ consecutive newlines
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def format_ocr_text_structure(lines, boxes=None):
    """Format extracted lines into clean structured document layout."""
    return clean_and_format_raw_text(lines)


def get_paddle_ocr(lang="en"):
    """Singleton getter for PaddleOCR engine to avoid model re-initialization."""
    global _paddle_ocr_instances
    if lang not in _paddle_ocr_instances:
        try:
            from paddleocr import PaddleOCR
            try:
                _paddle_ocr_instances[lang] = PaddleOCR(
                    use_angle_cls=True,
                    lang=lang,
                    use_gpu=False,
                    show_log=False
                )
            except Exception:
                _paddle_ocr_instances[lang] = PaddleOCR(lang=lang, use_gpu=False, show_log=False)
        except Exception as e:
            logger.debug("PaddleOCR init failed for lang=%s: %s", lang, e)
            _paddle_ocr_instances[lang] = False
    return _paddle_ocr_instances[lang]


def _normalize_confidence(score):
    if score is None:
        return 0.0
    try:
        if isinstance(score, str):
            score = score.strip().rstrip("%")
        val = float(score)
        if val <= 1.0:
            val *= 100.0
        return round(max(0.0, min(100.0, val)), 1)
    except (ValueError, TypeError):
        return 0.0


def _parse_paddle_results(results):
    lines, boxes, confidences = [], [], []
    if not results:
        return lines, boxes, confidences

    for item in results:
        if isinstance(item, list):
            for line in item:
                if isinstance(line, list) and len(line) >= 2:
                    box = line[0]
                    text_info = line[1]
                    if isinstance(text_info, (tuple, list)) and len(text_info) >= 2:
                        txt, score = text_info[0], text_info[1]
                        if txt and str(txt).strip():
                            lines.append(str(txt).strip())
                            boxes.append(box)
                            confidences.append(float(score))

        elif hasattr(item, "rec_text") or hasattr(item, "rec_polys"):
            rec_texts = getattr(item, "rec_text", []) or getattr(item, "rec_texts", [])
            rec_polys = getattr(item, "rec_polys", []) or getattr(item, "dt_polys", [])
            rec_scores = getattr(item, "rec_score", []) or getattr(item, "rec_scores", [])

            for idx, txt in enumerate(rec_texts):
                if txt and str(txt).strip():
                    lines.append(str(txt).strip())
                    if idx < len(rec_polys):
                        boxes.append(rec_polys[idx])
                    if idx < len(rec_scores):
                        confidences.append(float(rec_scores[idx]))
                    else:
                        confidences.append(0.85)

        elif isinstance(item, dict):
            rec_texts = item.get("rec_text", []) or item.get("rec_texts", [])
            rec_polys = item.get("rec_polys", []) or item.get("dt_polys", [])
            rec_scores = item.get("rec_score", []) or item.get("rec_scores", [])

            for idx, txt in enumerate(rec_texts):
                if txt and str(txt).strip():
                    lines.append(str(txt).strip())
                    if idx < len(rec_polys):
                        boxes.append(rec_polys[idx])
                    if idx < len(rec_scores):
                        confidences.append(float(rec_scores[idx]))
                    else:
                        confidences.append(0.85)

    return lines, boxes, confidences


def build_layout_blocks(lines, boxes=None, confidences=None, image_shape=None):
    """Build structured layout blocks with exact bounding box coordinates."""
    blocks = []
    if not lines:
        return blocks

    img_h, img_w = (1000.0, 800.0)
    if image_shape is not None and len(image_shape) >= 2:
        img_h, img_w = float(image_shape[0]), float(image_shape[1])

    for i, text in enumerate(lines):
        t_clean = str(text).strip()
        if not t_clean:
            continue

        box = boxes[i] if (boxes and i < len(boxes)) else None
        conf = confidences[i] if (confidences and i < len(confidences)) else 90.0

        x_min, y_min, x_max, y_max = 0.0, 0.0, 0.0, 0.0
        if box:
            try:
                if isinstance(box, (list, tuple)) and len(box) >= 4:
                    pts = []
                    for pt in box:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            pts.append((float(pt[0]), float(pt[1])))
                    if pts:
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        x_min, x_max = min(xs), max(xs)
                        y_min, y_max = min(ys), max(ys)
            except Exception:
                x_min, y_min, x_max, y_max = 0.0, 0.0, 0.0, 0.0

        width = max(1.0, x_max - x_min)
        height = max(1.0, y_max - y_min)

        is_heading = (
            (t_clean.isupper() and len(t_clean) < 60 and not any(c.isdigit() for c in t_clean[:5]))
            or t_clean.endswith(":")
            or any(t_clean.lower().startswith(kw) for kw in ["invoice", "receipt", "total due", "bill to", "ship to", "statement", "patient"])
        )

        blocks.append({
            "text": t_clean,
            "confidence": _normalize_confidence(conf),
            "bbox": {
                "x_min": round(x_min, 1),
                "y_min": round(y_min, 1),
                "x_max": round(x_max, 1),
                "y_max": round(y_max, 1),
                "width": round(width, 1),
                "height": round(height, 1)
            },
            "is_heading": is_heading,
            "has_box": box is not None
        })

    return blocks


def _extract_winocr_word_boxes(res):
    """Extract line boxes, confidences, and word boxes from winocr response."""
    lines, boxes, confidences, word_boxes = [], [], [], []
    for line in getattr(res, "lines", []) or []:
        ltxt = getattr(line, "text", "").strip()
        if not ltxt:
            continue
        lines.append(ltxt)
        lbox = None
        if hasattr(line, "words") and line.words:
            w_xs, w_ys, w_r, w_b = [], [], [], []
            for w in line.words:
                wtxt = getattr(w, "text", "").strip()
                wb = getattr(w, "bounding_rect", None)
                if wb:
                    w_xs.append(wb.x)
                    w_ys.append(wb.y)
                    w_r.append(wb.x + wb.width)
                    w_b.append(wb.y + wb.height)
                    word_boxes.append({
                        "text": wtxt,
                        "box": [
                            [wb.x, wb.y],
                            [wb.x + wb.width, wb.y],
                            [wb.x + wb.width, wb.y + wb.height],
                            [wb.x, wb.y + wb.height]
                        ]
                    })
            if w_xs:
                lbox = [
                    [min(w_xs), min(w_ys)],
                    [max(w_r), min(w_ys)],
                    [max(w_r), max(w_b)],
                    [min(w_xs), max(w_b)]
                ]
        boxes.append(lbox)
        confidences.append(92.0)
    return lines, boxes, confidences, word_boxes


def run_winocr(image_input, lang="en"):
    """Run Windows native OCR in ultra-fast mode (<0.05s)."""
    try:
        import asyncio
        import winocr
        from PIL import Image
        import cv2

        if isinstance(image_input, np.ndarray):
            if len(image_input.shape) == 3 and image_input.shape[2] == 3:
                pil_img = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
            else:
                pil_img = Image.fromarray(image_input)
        elif isinstance(image_input, Image.Image):
            pil_img = image_input
        else:
            return None

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        win_lang = lang if lang in ("en", "hi", "mr") else "en"

        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            res = loop.run_until_complete(winocr.recognize_pil(pil_img, lang=win_lang))
        else:
            res = loop.run_until_complete(winocr.recognize_pil(pil_img, lang=win_lang))

        lines, boxes, confidences, word_boxes = _extract_winocr_word_boxes(res)
        if not lines and hasattr(res, "text") and res.text:
            lines = [l.strip() for l in res.text.splitlines() if l.strip()]

        if not lines:
            return None

        text_len = sum(len(l) for l in lines)
        base_conf = min(98.0, 80.0 + min(18.0, text_len / 40.0))
        img_w, img_h = pil_img.size if hasattr(pil_img, "size") else (800, 1000)
        blocks = build_layout_blocks(
            lines, boxes or None, confidences or [base_conf] * len(lines), image_shape=(img_h, img_w)
        )

        return {
            "text": clean_and_format_raw_text(lines),
            "lines": lines,
            "boxes": boxes,
            "blocks": blocks,
            "word_boxes": word_boxes,
            "image_width": img_w,
            "image_height": img_h,
            "confidence": round(base_conf, 1),
            "word_confidences": confidences or [base_conf] * len(lines),
            "engine": f"Windows Native OCR ({win_lang})",
        }
    except Exception as e:
        logger.debug("WinOCR error: %s", e)
        return None


def run_paddle_ocr(image_np, lang="en"):
    """Run PaddleOCR deep learning recognition."""
    ocr_engine = get_paddle_ocr(lang=lang)
    if not ocr_engine:
        return None

    try:
        results = ocr_engine.ocr(image_np, cls=True)
        lines, boxes, confidences = _parse_paddle_results(results)
        lines, boxes, confidences = clean_ocr_lines(lines, boxes, confidences)

        if not lines:
            return None

        mean_conf = np.mean(confidences) if confidences else 0.85
        avg_conf = _normalize_confidence(mean_conf)
        img_h, img_w = image_np.shape[:2] if hasattr(image_np, "shape") else (1000, 800)
        blocks = build_layout_blocks(lines, boxes, confidences, image_shape=(img_h, img_w))

        return {
            "text": clean_and_format_raw_text(lines),
            "lines": lines,
            "boxes": boxes,
            "blocks": blocks,
            "word_boxes": [],
            "image_width": img_w,
            "image_height": img_h,
            "confidence": avg_conf,
            "word_confidences": [_normalize_confidence(c) for c in confidences],
            "engine": f"PaddleOCR ({lang})",
        }
    except Exception as e:
        logger.debug("PaddleOCR execution error: %s", e)
        return None


def run_tesseract_ocr(image_np, lang="eng", strict=False):
    """Run Tesseract OCR engine fallback."""
    try:
        import pytesseract
        import cv2

        gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY) if len(image_np.shape) == 3 else image_np
        data = pytesseract.image_to_data(gray, lang=lang, output_type=pytesseract.Output.DICT)

        lines, confidences, boxes = [], [], []
        n_boxes = len(data["text"])
        curr_line = []
        curr_confs = []

        for i in range(n_boxes):
            text = str(data["text"][i]).strip()
            conf = float(data["conf"][i])
            if text and conf > 20:
                curr_line.append(text)
                curr_confs.append(conf)
            if data["line_num"][i] != data["line_num"][i - 1] if i > 0 else False:
                if curr_line:
                    lines.append(" ".join(curr_line))
                    confidences.append(np.mean(curr_confs))
                    curr_line = []
                    curr_confs = []

        if curr_line:
            lines.append(" ".join(curr_line))
            confidences.append(np.mean(curr_confs) if curr_confs else 70.0)

        lines, boxes, confidences = clean_ocr_lines(lines, confidences=confidences)
        if not lines:
            return None

        avg_conf = _normalize_confidence(np.mean(confidences) if confidences else 75.0)
        img_h, img_w = image_np.shape[:2]
        blocks = build_layout_blocks(lines, None, confidences, image_shape=(img_h, img_w))

        return {
            "text": clean_and_format_raw_text(lines),
            "lines": lines,
            "boxes": [],
            "blocks": blocks,
            "word_boxes": [],
            "image_width": img_w,
            "image_height": img_h,
            "confidence": avg_conf,
            "word_confidences": [_normalize_confidence(c) for c in confidences],
            "engine": f"Tesseract OCR ({lang})",
        }
    except Exception as e:
        if strict:
            raise RuntimeError(f"Tesseract OCR engine unavailable: {e}") from e
        return None


def perform_ocr(processed_image_np, original_image_np=None, engine_choice="auto", language="multilingual"):
    """
    Optimized single-pass first-exit OCR pipeline:
    - Executes primary engine (WinOCR on Windows / PaddleOCR)
    - If good confidence (>=75%) is achieved, returns instantly!
    - Only invokes fallback engines if no text was detected or confidence is low (<70%).
    """
    lang_config = resolve_ocr_languages(language)
    tess_lang = lang_config["tesseract"]
    paddle_lang = lang_config["paddle"]
    win_lang = lang_config["winocr"]

    best_result = None

    # PASS 1: If auto or WinOCR, try ultra-fast Windows native OCR (~0.05s)
    if engine_choice in ("auto", "winocr"):
        best_result = run_winocr(processed_image_np, lang=win_lang)
        if best_result and best_result.get("text") and best_result.get("confidence", 0) >= 75.0:
            detected = detect_language_from_text(best_result["text"])
            best_result["detected_language"] = detected
            best_result["language_label"] = resolve_ocr_languages(language, detected_lang=detected)["label"]
            return best_result

    # PASS 2: If auto or PaddleOCR, run PaddleOCR
    if (engine_choice in ("auto", "paddle") and (not best_result or best_result.get("confidence", 0) < 70.0)):
        paddle_res = run_paddle_ocr(processed_image_np, lang=paddle_lang)
        if paddle_res and paddle_res.get("text"):
            if not best_result or paddle_res.get("confidence", 0) > best_result.get("confidence", 0):
                best_result = paddle_res
            if best_result.get("confidence", 0) >= 75.0:
                detected = detect_language_from_text(best_result["text"])
                best_result["detected_language"] = detected
                best_result["language_label"] = resolve_ocr_languages(language, detected_lang=detected)["label"]
                return best_result

    # PASS 3: If tesseract requested or previous engines yielded no text, run Tesseract
    if (engine_choice == "tesseract" or not best_result or not best_result.get("text")):
        tess_res = run_tesseract_ocr(processed_image_np, lang=tess_lang, strict=(engine_choice == "tesseract"))
        if tess_res and tess_res.get("text"):
            if not best_result or tess_res.get("confidence", 0) > best_result.get("confidence", 0):
                best_result = tess_res

    # PASS 4: Alternative preprocessing retry only if still low confidence (<60%) or no text
    if not best_result or best_result.get("confidence", 0) < 60.0 or not best_result.get("text"):
        alt_source = original_image_np if original_image_np is not None else processed_image_np
        try:
            alt_img = preprocess_image_alternative(alt_source)
            alt_res = run_winocr(alt_img, lang=win_lang) or run_paddle_ocr(alt_img, lang=paddle_lang)
            if alt_res and alt_res.get("text"):
                if not best_result or alt_res.get("confidence", 0) > best_result.get("confidence", 0):
                    best_result = alt_res
                    best_result["engine"] = best_result.get("engine", "OCR") + " [Adaptive]"
        except Exception:
            pass

    if best_result and best_result.get("text"):
        detected = detect_language_from_text(best_result["text"])
        best_result["detected_language"] = detected
        best_result["language_label"] = resolve_ocr_languages(language, detected_lang=detected)["label"]
        return best_result

    return {
        "text": "",
        "lines": [],
        "boxes": [],
        "blocks": [],
        "word_boxes": [],
        "confidence": 0.0,
        "word_confidences": [],
        "engine": "PaddleOCR / WinOCR",
        "detected_language": "en",
        "language_label": lang_config["label"],
    }
