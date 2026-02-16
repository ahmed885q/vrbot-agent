"""
VRBOT Re-Label & Upload v3
============================
1. يحذف الصور القديمة من Roboflow (الـ 161 المشكلة)
2. يشغّل الموديل الجديد best.pt على الصور
3. يرفع الصور + التسميات الجديدة بطريقة صحيحة

الاستخدام:
    python relabel_upload.py

المتطلبات:
    pip install ultralytics roboflow Pillow
"""

import os
import glob
import json
import time
from ultralytics import YOLO
from roboflow import Roboflow

# ============================================
# الإعدادات
# ============================================
MODEL_PATH = r"C:\Users\manso\vrbot-agent\models\best.pt"
IMAGES_DIR = r"C:\Users\manso\vrbot-agent\dataset\screenshots"
NEW_LABELS_DIR = r"C:\Users\manso\vrbot-agent\dataset\labels_v3"

API_KEY = "uwA6un1dJmhKwxbbN1Wg"
WORKSPACE = "vrbot"
PROJECT = "vrbot-detection"

CONFIDENCE = 0.40  # اقل شوي عشان نلقط أكثر
MAX_IMAGES = 0  # 0 = الكل

# ============================================

def main():
    print("=" * 60)
    print("VRBOT Re-Label & Upload v3")
    print("=" * 60)

    # === الخطوة 1: تحميل الموديل ===
    print("\n[1/3] Loading model...")
    model = YOLO(MODEL_PATH)
    names = model.names
    print(f"  Model: {len(names)} classes")

    # إنشاء مجلد التسميات الجديدة
    os.makedirs(NEW_LABELS_DIR, exist_ok=True)

    # حفظ _classes.txt
    classes_path = os.path.join(NEW_LABELS_DIR, "_classes.txt")
    max_id = max(names.keys())
    with open(classes_path, "w", encoding="utf-8") as f:
        for i in range(max_id + 1):
            f.write(f"{names.get(i, 'unknown')}\n")
    print(f"  Saved _classes.txt ({max_id + 1} classes)")

    # === الخطوة 2: تسمية الصور بالموديل الجديد ===
    print(f"\n[2/3] Labeling images with new model (conf={CONFIDENCE})...")

    images = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.png")))
    if MAX_IMAGES > 0:
        images = images[:MAX_IMAGES]

    labeled = 0
    skipped = 0
    total_dets = 0

    for i, img_path in enumerate(images):
        img_name = os.path.basename(img_path)
        base = os.path.splitext(img_name)[0]

        results = model(img_path, conf=CONFIDENCE, verbose=False)
        result = results[0]

        if len(result.boxes) == 0:
            skipped += 1
            continue

        img_h, img_w = result.orig_shape
        label_path = os.path.join(NEW_LABELS_DIR, f"{base}.txt")

        det_count = 0
        with open(label_path, "w") as f:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cls_id = int(box.cls[0].item())

                xc = ((x1 + x2) / 2) / img_w
                yc = ((y1 + y2) / 2) / img_h
                w = (x2 - x1) / img_w
                h = (y2 - y1) / img_h

                f.write(f"{cls_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
                det_count += 1

        total_dets += det_count
        labeled += 1

        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(images)}...")

    print(f"  Done! Labeled: {labeled}, Skipped: {skipped}, Total detections: {total_dets}")

    # === الخطوة 3: رفع على Roboflow ===
    print(f"\n[3/3] Uploading to Roboflow...")
    print(f"  This will OVERWRITE existing images.")

    rf = Roboflow(api_key=API_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)

    label_files = sorted([f for f in glob.glob(os.path.join(NEW_LABELS_DIR, "*.txt"))
                          if "_classes" not in f])

    ok = 0
    fail = 0

    for i, lbl_path in enumerate(label_files):
        base = os.path.splitext(os.path.basename(lbl_path))[0]
        img_path = os.path.join(IMAGES_DIR, f"{base}.png")

        if not os.path.exists(img_path):
            continue

        try:
            project.upload(
                image_path=img_path,
                annotation_path=lbl_path,
                split="train",
                overwrite=True,
            )
            ok += 1
            if ok % 20 == 0:
                print(f"  Uploaded {ok}...")
        except Exception as e:
            fail += 1
            if fail <= 3:
                print(f"  FAIL {base}: {str(e)[:80]}")

    print(f"\n{'='*60}")
    print(f"DONE!")
    print(f"  Images labeled: {labeled}")
    print(f"  Uploaded OK: {ok}")
    print(f"  Failed: {fail}")
    print(f"  Total detections: {total_dets}")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"  1. Go to Roboflow > Annotate > review labels")
    print(f"  2. Create Version 4")
    print(f"  3. Train on Colab with version(4)")


if __name__ == "__main__":
    main()
