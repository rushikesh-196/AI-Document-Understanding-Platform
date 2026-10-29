"""
Language detection and OCR language mapping for English, Hindi, and Marathi.
"""

import re

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
LATIN_RE = re.compile(r"[A-Za-z]")

LANG_LABELS = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "multilingual": "English + Hindi + Marathi",
    "mixed": "Mixed (English + Hindi + Marathi)",
}

# Tesseract language codes
TESSERACT_LANG_MAP = {
    "en": "eng",
    "hi": "hin",
    "mr": "mar",
    "multilingual": "eng+hin+mar",
    "mixed": "eng+hin+mar",
}

# WinOCR BCP-47 tags (Windows language packs)
WINOCR_LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "mr": "mr",
    "multilingual": "en",
    "mixed": "en",
}

# PaddleOCR language codes
PADDLE_LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "mr": "en",  # Marathi not in PaddleOCR — fallback to English model
    "multilingual": "en",
    "mixed": "en",
}


def normalize_lang_choice(lang_choice):
    if not lang_choice:
        return "multilingual"
    lang = lang_choice.lower().strip()
    if lang in ("en", "eng", "english"):
        return "en"
    if lang in ("hi", "hin", "hindi"):
        return "hi"
    if lang in ("mr", "mar", "marathi"):
        return "mr"
    if lang in ("multilingual", "multi", "auto"):
        return "multilingual"
    return "multilingual"


def detect_language_from_text(text):
    """Detect dominant document language from OCR text."""
    if not text or not text.strip():
        return "en"

    sample = text[:8000]
    devanagari = len(DEVANAGARI_RE.findall(sample))
    latin = len(LATIN_RE.findall(sample))
    total = devanagari + latin

    if total == 0:
        return "en"
    if devanagari == 0:
        return "en"
    if latin == 0:
        # Distinguish Hindi vs Marathi heuristically via common words
        mr_markers = len(re.findall(
            r"(\u0924\u0941\u092e\u094D\u0939\u093E\u0932\u093E|\u092E\u0939\u093E\u0930\u093E\u0937\u094D\u091F\u094D\u0930|\u092A\u0941\u0923\u0947|\u0930\u093E\u091C\u094D\u092F)",
            sample
        ))
        hi_markers = len(re.findall(
            r"(\u092D\u093E\u0930\u0924|\u0939\u093F\u0902\u0926\u0940|\u0906\u0927\u093E\u0930|\u092A\u0948\u0928|\u0917\u093E\u0902\u0927\u0940|\u0926\u093F\u0932\u094D\u0932\u0940)",
            sample
        ))
        if mr_markers > hi_markers:
            return "mr"
        if hi_markers > 0:
            return "hi"
        return "hi"

    dev_ratio = devanagari / total
    if dev_ratio > 0.85:
        return detect_language_from_text(re.sub(r"[A-Za-z0-9@.\-+]", "", sample)) or "hi"
    if dev_ratio > 0.15:
        return "mixed"
    return "en"


def resolve_ocr_languages(lang_choice, detected_lang=None):
    """
    Resolve OCR language settings from user choice and optional detected language.
    Returns dict with tesseract, paddle, and winocr codes plus label.
    """
    choice = normalize_lang_choice(lang_choice)

    if choice == "multilingual" and detected_lang:
        effective = detected_lang
    elif choice == "multilingual":
        effective = "multilingual"
    else:
        effective = choice

    return {
        "choice": choice,
        "effective": effective,
        "label": LANG_LABELS.get(effective, LANG_LABELS["mixed"]),
        "tesseract": TESSERACT_LANG_MAP.get(effective, "eng+hin+mar"),
        "paddle": PADDLE_LANG_MAP.get(effective, "en"),
        "winocr": WINOCR_LANG_MAP.get(effective, "en"),
    }
