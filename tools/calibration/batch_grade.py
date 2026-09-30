import os
import cv2
import numpy as np
import sys
import json
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

def order_points(pts):
    pts = pts.reshape(4, 2).astype("float32")
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_warp(image, pts):
    rect = order_points(pts)
    tl, tr, br, bl = rect
    maxW = max(int(np.linalg.norm(br - bl)), int(np.linalg.norm(tr - tl)))
    maxH = max(int(np.linalg.norm(tr - br)), int(np.linalg.norm(tl - bl)))
    if maxW <= 0 or maxH <= 0: return None
    dst = np.array([[0,0], [maxW-1,0], [maxW-1,maxH-1], [0,maxH-1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxW, maxH))

def detect_document_contour(frame):
    h, w = frame.shape[:2]
    img_area = h * w
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    def _find_quad(binary_img, min_ratio=0.08, max_ratio=0.98, poly_eps=0.02):
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        closed = cv2.morphologyEx(binary_img, cv2.MORPH_CLOSE, kernel)
        edges = cv2.Canny(closed, 30, 120)
        edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < img_area * min_ratio or area > img_area * max_ratio: continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, poly_eps * peri, True)
            if len(approx) == 4: return approx
        return None

    # Try Strategy 1: Otsu
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contour = _find_quad(otsu)
    strategy = "Otsu"

    # Strategy 2: Adaptive
    if contour is None:
        adapt = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10)
        contour = _find_quad(adapt, poly_eps=0.03)
        strategy = "Adaptive"

    # Strategy 3: Sobel
    if contour is None:
        sobelx = cv2.Sobel(blur, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(blur, cv2.CV_64F, 0, 1, ksize=3)
        sobel = np.uint8(np.clip(np.sqrt(sobelx**2 + sobely**2), 0, 255))
        _, sobel_bin = cv2.threshold(sobel, 30, 255, cv2.THRESH_BINARY)
        contour = _find_quad(sobel_bin, min_ratio=0.05, poly_eps=0.04)
        strategy = "Sobel"

    return contour, strategy

def batch_process(image_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    images = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    results = []

    print(f"Batch processing {len(images)} images in {image_dir}...")
    
    for img_name in images:
        path = os.path.join(image_dir, img_name)
        img = cv2.imread(path)
        if img is None: continue

        print(f"Processing {img_name}...", end=" ", flush=True)
        contour, strategy = detect_document_contour(img)
        
        if contour is not None:
            warped = four_point_warp(img, contour)
            if warped is not None:
                warp_name = f"warped_{img_name}"
                warp_path = os.path.join(output_dir, warp_name)
                cv2.imwrite(warp_path, warped)
                
                abs_warp_path = os.path.abspath(warp_path)
                hi_path = str(ENGINE_DIR / 'hi.py')
                os.system(f'python "{hi_path}" "{abs_warp_path}" --silent')
                
                results.append({
                    "image": img_name,
                    "status": "Success",
                    "strategy": strategy,
                    "warped_file": warp_name
                })
                print(f"[OK] Strategy: {strategy}")
            else:
                results.append({"image": img_name, "status": "Warp Failed", "strategy": strategy})
                print("[FAILED] Warp error")
        else:
            results.append({"image": img_name, "status": "Not Found", "strategy": "N/A"})
            print("[FAILED] No document found")

    return results

if __name__ == "__main__":
    image_folder = str(REPO_ROOT / "anh")
    processed_folder = str(REPO_ROOT / "anh" / "processed")
    final_results = batch_process(image_folder, processed_folder)
    
    print("\n" + "="*50)
    print(f"{'IMAGE':<20} | {'STATUS':<10} | {'STRATEGY':<10}")
    print("-"*50)
    for res in final_results:
        print(f"{res['image']:<20} | {res['status']:<10} | {res['strategy']:<10}")
    print("="*50)
    print(f"Done. Processed images saved in {processed_folder}")
