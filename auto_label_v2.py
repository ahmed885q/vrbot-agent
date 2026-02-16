"""
VRBOT Auto-Label Script v2
===========================
يشغّل best.pt على الصور ويحفظ التسميات كملفات YOLO txt
ثم يرفعها على Roboflow بمكتبة roboflow الرسمية.

الاستخدام:
    python auto_label_v2.py

المتطلبات:
    pip install ultralytics roboflow
"""

import os
import glob
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    print("❌ ultralytics مو مثبت. شغّل: pip install ultralytics")
    exit(1)

try:
    from roboflow import Roboflow
except ImportError:
    print("❌ roboflow مو مثبت. شغّل: pip install roboflow")
    exit(1)

# ============================================
# ⚙️ الإعدادات
# ============================================

MODEL_PATH = r"C:\Users\manso\vrbot-agent\models\best.pt"
IMAGES_DIR = r"C:\Users\manso\vrbot-agent\dataset\screenshots"
LABELS_DIR = r"C:\Users\manso\vrbot-agent\dataset\labels"  # مجلد التسميات

# Roboflow
API_KEY = "uwA6un1dJmhKwxbbN1Wg"  # ⚠️ غيّره لو جددت المفتاح
WORKSPACE = "vrbot"
PROJECT = "vrbot-detection"

CONFIDENCE_THRESHOLD = 0.50  # خفضناه شوي عشان نلقط أكثر
MAX_IMAGES = 0  # 0 = الكل

# ============================================
# 🚀 الكود
# ============================================

def main():
    print("=" * 60)
    print("🤖 VRBOT Auto-Label Script v2")
    print("=" * 60)

    # تحميل الموديل
    print(f"📦 تحميل الموديل: {MODEL_PATH}")
    if not os.path.exists(MODEL_PATH):
        print(f"❌ الموديل مو موجود!")
        exit(1)
    model = YOLO(MODEL_PATH)
    class_names = model.names
    print(f"✅ الموديل جاهز - {len(class_names)} classes")

    # إنشاء مجلد التسميات
    os.makedirs(LABELS_DIR, exist_ok=True)

    # جمع الصور
    images = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.png")))
    if MAX_IMAGES > 0:
        images = images[:MAX_IMAGES]

    print(f"📸 عدد الصور: {len(images)}")
    print(f"🎯 Confidence: {CONFIDENCE_THRESHOLD}")
    print("-" * 60)

    # ===== الخطوة 1: تشغيل YOLO وحفظ التسميات كـ txt =====
    print("\n📍 الخطوة 1: تشغيل YOLO على الصور...")

    labeled_count = 0
    skipped_count = 0
    total_detections = 0

    for i, img_path in enumerate(images):
        img_name = os.path.basename(img_path)
        base_name = os.path.splitext(img_name)[0]

        # تشغيل الموديل
        results = model(img_path, conf=CONFIDENCE_THRESHOLD, verbose=False)
        result = results[0]

        if len(result.boxes) == 0:
            print(f"  [{i+1}/{len(images)}] ⏭️  {img_name} - لا عناصر")
            skipped_count += 1
            continue

        # حفظ التسميات بصيغة YOLO (class_id x_center y_center width height)
        img_h, img_w = result.orig_shape
        label_path = os.path.join(LABELS_DIR, f"{base_name}.txt")

        labels_info = {}
        with open(label_path, "w") as f:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = box.conf[0].item()
                cls_id = int(box.cls[0].item())
                cls_name = class_names[cls_id]

                # YOLO format: normalized center x, center y, width, height
                x_center = ((x1 + x2) / 2) / img_w
                y_center = ((y1 + y2) / 2) / img_h
                width = (x2 - x1) / img_w
                height = (y2 - y1) / img_h

                f.write(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                total_detections += 1
                labels_info[cls_name] = labels_info.get(cls_name, 0) + 1

        labels_str = ", ".join(f"{k}({v})" for k, v in labels_info.items())
        det_count = sum(labels_info.values())
        print(f"  [{i+1}/{len(images)}] ✅ {img_name} - {det_count} عنصر: {labels_str}")
        labeled_count += 1

    print(f"\n📊 نتيجة الخطوة 1:")
    print(f"  ✅ صور مع تسميات: {labeled_count}")
    print(f"  ⏭️  بدون عناصر: {skipped_count}")
    print(f"  🏷️  إجمالي التسميات: {total_detections}")

    if labeled_count == 0:
        print("❌ ما لقى أي عنصر! جرّب تنزّل الـ threshold.")
        exit(1)

    # ===== الخطوة 2: رفع على Roboflow =====
    print("\n" + "=" * 60)
    print("📍 الخطوة 2: رفع الصور + التسميات على Roboflow...")
    print("=" * 60)

    rf = Roboflow(api_key=API_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)

    success_count = 0
    fail_count = 0

    for i, img_path in enumerate(images):
        img_name = os.path.basename(img_path)
        base_name = os.path.splitext(img_name)[0]
        label_path = os.path.join(LABELS_DIR, f"{base_name}.txt")

        # تخطي الصور بدون تسميات
        if not os.path.exists(label_path):
            continue

        try:
            project.upload(
                image_path=img_path,
                annotation_path=label_path,
                split="train",
                overwrite=True,
                tag_names=["auto-labeled"],
                batch_name="auto-label-batch",
            )
            success_count += 1
            print(f"  [{success_count}] ✅ {img_name}")

        except Exception as e:
            fail_count += 1
            print(f"  ❌ {img_name}: {str(e)[:80]}")

    # ===== الملخص =====
    print("\n" + "=" * 60)
    print("📊 الملخص النهائي:")
    print(f"  📸 إجمالي الصور: {len(images)}")
    print(f"  🏷️  صور مع تسميات: {labeled_count}")
    print(f"  ✅ رُفعت بنجاح: {success_count}")
    print(f"  ❌ فشل الرفع: {fail_count}")
    print(f"  🏷️  إجمالي العناصر: {total_detections}")
    print("=" * 60)
    print("\n👉 الحين روح Roboflow > Annotate")
    print("   راجع التسميات وعدّل الأغلاط")
    print("   بعدها أنشئ Version 2 ودرّب!")


if __name__ == "__main__":
    main()