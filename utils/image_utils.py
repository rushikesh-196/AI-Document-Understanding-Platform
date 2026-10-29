"""
OpenCV Image Preprocessing Utilities
Optimized for high-speed, high-accuracy OCR on images and document scans.
"""

import cv2
import numpy as np
from PIL import Image

TARGET_DPI = 300
ASSUMED_SOURCE_DPI = 200
MIN_OCR_WIDTH = 1000
MAX_OCR_DIM = 2000


def _to_bgr(image_input):
    if isinstance(image_input, str):
        img_bgr = cv2.imread(image_input)
    elif isinstance(image_input, Image.Image):
        img_bgr = cv2.cvtColor(np.array(image_input.convert("RGB")), cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        img_bgr = image_input.copy()
    else:
        raise ValueError("Unsupported image input format")

    if img_bgr is None:
        raise ValueError("Could not decode image")

    if len(img_bgr.shape) == 2:
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)
    elif img_bgr.shape[2] == 4:
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)

    return img_bgr


def resize_to_target_dpi(img_bgr, target_dpi=TARGET_DPI, assumed_dpi=ASSUMED_SOURCE_DPI):
    """Scale image toward optimal dimension for OCR without massive memory overhead."""
    h, w = img_bgr.shape[:2]

    # Downscale if image is overly large (>2000px)
    if max(h, w) > MAX_OCR_DIM:
        scale = MAX_OCR_DIM / float(max(h, w))
        target_w = int(w * scale)
        target_h = int(h * scale)
        return cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)

    # Upscale if image is too small for OCR (<1000px)
    if w < MIN_OCR_WIDTH:
        scale = MIN_OCR_WIDTH / float(w)
        target_w = int(w * scale)
        target_h = int(h * scale)
        return cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

    return img_bgr


def sharpen_image(gray_img):
    """Unsharp masking for crisp text edges."""
    blurred = cv2.GaussianBlur(gray_img, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(gray_img, 1.4, blurred, -0.4, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def deskew_image(gray_img):
    """Detect text skew angle and rotate image straight."""
    try:
        _, binary = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(binary > 0))
        if coords.shape[0] < 50:
            return gray_img

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5 or abs(angle) > 45:
            return gray_img

        h, w = gray_img.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            gray_img, matrix, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated
    except Exception:
        return gray_img


def detect_document_boundary(img_bgr):
    """
    Detect document contour bounding box to crop out non-document background.
    """
    try:
        h, w = img_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 30, 150)

        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img_bgr

        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for c in contours:
            area = cv2.contourArea(c)
            if (0.25 * w * h) <= area < (0.98 * w * h):
                x, y, cw, ch = cv2.boundingRect(c)
                pad = 10
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(w, x + cw + pad)
                y2 = min(h, y + ch + pad)
                return img_bgr[y1:y2, x1:x2]

        return img_bgr
    except Exception:
        return img_bgr


def _primary_pipeline(gray):
    """Ultra-fast bilateral filter + CLAHE contrast + deskew + sharpen (takes <10ms)."""
    denoised = cv2.bilateralFilter(gray, d=5, sigmaColor=40, sigmaSpace=40)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    deskewed = deskew_image(enhanced)
    sharpened = sharpen_image(deskewed)
    return sharpened


def _alternative_pipeline(gray):
    """Adaptive thresholding pipeline for degraded or noisy documents."""
    denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=60, sigmaSpace=60)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    deskewed = deskew_image(enhanced)

    adaptive = cv2.adaptiveThreshold(
        deskewed, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=25,
        C=10,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    morphed = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel, iterations=1)
    sharpened = sharpen_image(morphed)
    return sharpened


def preprocess_image(image_input, pipeline="primary", crop_boundary=False):
    """
    Optimized preprocessing pipeline:
    1. BGR conversion
    2. Optional document boundary crop
    3. Optimal scaling
    4. Fast contrast enhancement & deskew
    Returns 3-channel BGR image suitable for OCR.
    """
    img_bgr = _to_bgr(image_input)
    if crop_boundary:
        img_bgr = detect_document_boundary(img_bgr)
    img_bgr = resize_to_target_dpi(img_bgr)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    if pipeline == "alternative":
        processed_gray = _alternative_pipeline(gray)
    else:
        processed_gray = _primary_pipeline(gray)

    return cv2.cvtColor(processed_gray, cv2.COLOR_GRAY2BGR)


def preprocess_image_alternative(image_input):
    """Alternative preprocessing for low-confidence OCR retry."""
    return preprocess_image(image_input, pipeline="alternative", crop_boundary=False)
