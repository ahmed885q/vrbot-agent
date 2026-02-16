"""
VRBOT Auto-Label Script
=======================
يشغّل best.pt على الصور ويرفع التسميات على Roboflow تلقائياً.

الاستخدام:
    python auto_label_roboflow.py

المتطلبات:
    pip install ultralytics roboflow requests

ملاحظة: غيّر API_KEY قبل التشغيل!
"""

import os
import json
import glob
import requests
import base64
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    print("❌ ultralytics مو مثبت. شغّل: pip install ultralytics")
    exit(1)

# ============================================
# ⚙️ الإعدادات - عدّل حسب حاجتك
# ============================================

# مسار الموديل
MODEL_PATH = r"C:\Users\manso\vrbot-agent\models\best.pt"

# مجلد الصور الجديدة
IMAGES_DIR = r"C:\Users\manso\vrbot-agent\dataset\screenshots"

# Roboflow API
API_KEY = "uwA6un1dJmhKwxbbN1Wg"  # ⚠️ غيّره لو جددت المفتاح
WORKSPACE = "vrbot"
PROJECT = "vrbot-detection"

# Confidence threshold - بس التسميات فوق هالنسبة بترتفع
CONFIDENCE_THRESHOLD = 0.65

# كم صورة يسمّي (0 = الكل)
MAX_IMAGES = 0

# ============================================
# 🚀 الكود الرئيسي
# ============================================

def load_model(model_path):
    """تحميل موديل YOLOv8"""
    print(f"📦 تحميل الموديل: {model_path}")
    if not os.path.exists(model_path):
        print(f"❌ الموديل مو موجود: {model_path}")
        exit(1)
    model = YOLO(model_path)
    print(f"✅ الموديل جاهز - {len(model.names)} classes")
    return model


def detect_image(model, image_path, conf_threshold):
    """تشغيل الموديل على صورة واحدة"""
    results = model(image_path, conf=conf_threshold, verbose=False)
    result = results[0]

    detections = []
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf = box.conf[0].item()
        cls_id = int(box.cls[0].item())
        cls_name = model.names[cls_id]

        detections.append({
            "class": cls_name,
            "confidence": round(conf, 3),
            "x_min": round(x1),
            "y_min": round(y1),
            "x_max": round(x2),
            "y_max": round(y2),
            "width": round(x2 - x1),
            "height": round(y2 - y1),
            "x_center": round((x1 + x2) / 2),
            "y_center": round((y1 + y2) / 2),
        })

    return detections, result.orig_shape  # (height, width)


def upload_annotation_to_roboflow(image_path, detections, img_shape, api_key, workspace, project):
    """رفع صورة + تسمياتها على Roboflow"""
    img_height, img_width = img_shape

    # تحويل الصورة لـ base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    # تحويل التسميات لصيغة Roboflow
    annotations = []
    for det in detections:
        # Roboflow يبي النسب (0-1) مو البكسلات
        x_center_norm = det["x_center"] / img_width
        y_center_norm = det["y_center"] / img_height
        width_norm = det["width"] / img_width
        height_norm = det["height"] / img_height

        annotations.append({
            "label": det["class"],
            "x": x_center_norm,
            "y": y_center_norm,
            "width": width_norm,
            "height": height_norm,
        })

    # رفع الصورة مع التسميات
    image_name = os.path.basename(image_path)

    upload_url = f"https://api.roboflow.com/dataset/{project}/upload"

    params = {
        "api_key": api_key,
        "name": image_name,
        "split": "train",
        "overwrite": "true",
    }

    # رفع الصورة
    response = requests.post(
        upload_url,
        params=params,
        data=image_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    if response.status_code == 200:
        result = response.json()
        image_id = result.get("id", "")

        # رفع التسميات (Annotation)
        if annotations and image_id:
            annotation_url = f"https://api.roboflow.com/dataset/{project}/annotate/{image_id}"
            annotation_data = {
                "name": image_name,
                "annotation": json.dumps({
                    "image": {
                        "width": img_width,
                        "height": img_height,
                    },
                    "annotations": [
                        {
                            "label": ann["label"],
                            "coordinates": {
                                "x": ann["x"] * img_width,
                                "y": ann["y"] * img_height,
                                "width": ann["width"] * img_width,
                                "height": ann["height"] * img_height,
                            }
                        }
                        for ann in annotations
                    ]
                }),
            }

            ann_response = requests.post(
                annotation_url,
                params={"api_key": api_key},
                json=annotation_data,
            )
            return ann_response.status_code == 200

        return True
    else:
        print(f"  ❌ خطأ في الرفع: {response.status_code} - {response.text[:100]}")
        return False


def main():
    print("=" * 60)
    print("🤖 VRBOT Auto-Label Script")
    print("=" * 60)

    # تحميل الموديل
    model = load_model(MODEL_PATH)

    # جمع الصور
    image_extensions = ["*.png", "*.jpg", "*.jpeg"]
    images = []
    for ext in image_extensions:
        images.extend(glob.glob(os.path.join(IMAGES_DIR, ext)))

    images.sort()

    if MAX_IMAGES > 0:
        images = images[:MAX_IMAGES]

    print(f"📸 عدد الصور: {len(images)}")
    print(f"🎯 Confidence Threshold: {CONFIDENCE_THRESHOLD}")
    print("-" * 60)

    # إحصائيات
    total_detections = 0
    successful_uploads = 0
    failed_uploads = 0
    skipped_images = 0  # صور بدون أي detections

    for i, image_path in enumerate(images):
        image_name = os.path.basename(image_path)

        # تشغيل الموديل
        detections, img_shape = detect_image(model, image_path, CONFIDENCE_THRESHOLD)

        if len(detections) == 0:
            print(f"  [{i+1}/{len(images)}] ⏭️  {image_name} - ما لقى شي (skipped)")
            skipped_images += 1
            continue

        total_detections += len(detections)

        # عرض التسميات
        labels_summary = {}
        for d in detections:
            labels_summary[d["class"]] = labels_summary.get(d["class"], 0) + 1
        labels_str = ", ".join(f"{k}({v})" for k, v in labels_summary.items())

        # رفع على Roboflow
        success = upload_annotation_to_roboflow(
            image_path, detections, img_shape,
            API_KEY, WORKSPACE, PROJECT
        )

        if success:
            print(f"  [{i+1}/{len(images)}] ✅ {image_name} - {len(detections)} عنصر: {labels_str}")
            successful_uploads += 1
        else:
            print(f"  [{i+1}/{len(images)}] ❌ {image_name} - فشل الرفع")
            failed_uploads += 1

    # الملخص
    print("\n" + "=" * 60)
    print("📊 الملخص النهائي:")
    print(f"  📸 إجمالي الصور: {len(images)}")
    print(f"  ✅ نجح الرفع: {successful_uploads}")
    print(f"  ❌ فشل الرفع: {failed_uploads}")
    print(f"  ⏭️  بدون عناصر: {skipped_images}")
    print(f"  🏷️  إجمالي التسميات: {total_detections}")
    print(f"  📈 متوسط عناصر/صورة: {total_detections / max(successful_uploads, 1):.1f}")
    print("=" * 60)
    print("\n👉 الحين روح Roboflow > Annotate وعدّل الأغلاط يدوي")
    print("   بعدها أنشئ Version 2 ودرّب من جديد!")


if __name__ == "__main__":
    main()
