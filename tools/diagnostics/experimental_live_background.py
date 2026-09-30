"""REJECTED experiment: not imported by production code.

    Keep denoising, local sigma=30 filtering and all thresholds unchanged.
    Soft blur changed Part I answers. Diagnostic comparison only.
"""
import cv2


def global_background(gray):
    h, w = gray.shape[:2]
    small_w, small_h = max(1, w // 4), max(1, h // 4)
    small = cv2.resize(gray, (small_w, small_h), interpolation=cv2.INTER_AREA)
    filtered = cv2.GaussianBlur(small, (0, 0), sigmaX=120 * small_w / w,
                                sigmaY=120 * small_h / h)
    return cv2.resize(filtered, (w, h), interpolation=cv2.INTER_LINEAR)
