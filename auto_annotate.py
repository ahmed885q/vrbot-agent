"""
VRBOT Auto-Annotator
Uses existing YOLOv8s model (best.pt) to auto-annotate images on Roboflow.

Usage:
    python auto_annotate.py

Requirements:
    pip install ultralytics roboflow requests
"""

import os
import json
import glob
from ultralytics import YOLO
from roboflow import Roboflow

# ═══ CONFIG ═══
MODEL_PATH = "models/best.pt"  # Your existing v5 model
ROBOFLOW_API_KEY = "uwA6un1dJmhKwxbbN1Wg"
ROBOFLOW_PROJECT = "vrbot-detection"
ROBOFLOW_WORKSPACE = "vrbot"
CONFIDENCE_THRESHOLD = 0.4  # Minimum confidence to include

# ═══ STEP 1: Load Model ═══
print("Loading YOLO model...")
model = YOLO(MODEL_PATH)
class_names = model.names
print(f"✅ Model loaded — {len(class_names)} classes")

# ═══ STEP 2: Connect to Roboflow ═══
print("\nConnecting to Roboflow...")
rf = Roboflow(api_key=ROBOFLOW_API_KEY)
project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)
print(f"✅ Connected to {ROBOFLOW_PROJECT}")

# ═══ STEP 3: Find unannotated images ═══
# Option A: Use local screenshots
SCREENSHOT_DIRS = [
    "debug_screenshots",
    "dataset/screenshots",
]

local_images = []
for d in SCREENSHOT_DIRS:
    if os.path.exists(d):
        for ext in ["*.png", "*.jpg", "*.jpeg"]:
            local_images.extend(glob.glob(os.path.join(d, ext)))

print(f"\nFound {len(local_images)} local images")

if not local_images:
    print("❌ No images found! Make sure debug_screenshots/ or dataset/screenshots/ exists")
    print("   Or add your screenshot folder path to SCREENSHOT_DIRS above")
    exit(1)

# ═══ STEP 4: Run inference and upload ═══
annotated = 0
skipped = 0
errors = 0

for i, img_path in enumerate(local_images):
    filename = os.path.basename(img_path)
    print(f"\n[{i+1}/{len(local_images)}] {filename}")
    
    try:
        # Run YOLO inference
        results = model(img_path, conf=CONFIDENCE_THRESHOLD, verbose=False)
        result = results[0]
        
        boxes = result.boxes
        if len(boxes) == 0:
            print(f"  ⚠️  No detections — skipping")
            skipped += 1
            continue
        
        # Format annotations
        detections = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = class_names[cls_id]
            
            # Convert to center format (Roboflow uses this)
            img_h, img_w = result.orig_shape
            cx = ((x1 + x2) / 2) / img_w
            cy = ((y1 + y2) / 2) / img_h
            w = (x2 - x1) / img_w
            h = (y2 - y1) / img_h
            
            detections.append({
                "class": cls_name,
                "confidence": conf,
                "x": cx,
                "y": cy,
                "width": w,
                "height": h,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2
            })
        
        det_summary = {}
        for d in detections:
            name = d["class"]
            det_summary[name] = det_summary.get(name, 0) + 1
        
        print(f"  ✅ {len(detections)} detections: {det_summary}")
        
        # Upload image with annotations to Roboflow
        # Format: class_name cx cy w h (Roboflow accepts names)
        annotation_str = ""
        for d in detections:
            annotation_str += f"{d['class']} {d['x']:.6f} {d['y']:.6f} {d['width']:.6f} {d['height']:.6f}\n"
        
        # Save temp annotation file
        ann_path = img_path.rsplit(".", 1)[0] + ".txt"
        with open(ann_path, "w") as f:
            f.write(annotation_str)
        
        # Upload to Roboflow
        project.upload(
            image_path=img_path,
            annotation_path=ann_path,
            split="train"
        )
        
        annotated += 1
        print(f"  📤 Uploaded to Roboflow")
        
        # Cleanup temp annotation
        if os.path.exists(ann_path):
            os.remove(ann_path)
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        errors += 1

# ═══ SUMMARY ═══
print(f"\n{'='*50}")
print(f"  Auto-Annotation Complete!")
print(f"{'='*50}")
print(f"  ✅ Annotated: {annotated}")
print(f"  ⚠️  Skipped (no detections): {skipped}")
print(f"  ❌ Errors: {errors}")
print(f"  📊 Total: {len(local_images)}")
print(f"\nNow go to Roboflow → Annotate → Review the auto-annotations")
print(f"Fix any mistakes manually, then Generate a new version!")
