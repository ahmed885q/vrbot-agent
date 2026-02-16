import os, glob
from ultralytics import YOLO
from roboflow import Roboflow

MODEL_PATH = r"C:\Users\manso\vrbot-agent\models\best.pt"
IMAGES_DIR = r"C:\Users\manso\vrbot-agent\dataset\screenshots"
LABELS_DIR = r"C:\Users\manso\vrbot-agent\dataset\labels"

model = YOLO(MODEL_PATH)
names = model.names
print(f"Classes: {len(names)}")

# حفظ _classes.txt
with open(os.path.join(LABELS_DIR, "_classes.txt"), "w") as f:
    for i in range(max(names.keys()) + 1):
        f.write(f"{names.get(i, 'unknown')}\n")
print("_classes.txt saved!")

# إعادة الرفع
rf = Roboflow(api_key="uwA6un1dJmhKwxbbN1Wg")
project = rf.workspace("vrbot").project("vrbot-detection")

labels = sorted([f for f in glob.glob(os.path.join(LABELS_DIR, "*.txt")) if "_classes" not in f])
for i, lbl in enumerate(labels):
    base = os.path.splitext(os.path.basename(lbl))[0]
    img = os.path.join(IMAGES_DIR, f"{base}.png")
    if not os.path.exists(img): continue
    try:
        project.upload(image_path=img, annotation_path=lbl, split="train", overwrite=True)
        print(f"[{i+1}] OK {base}")
    except Exception as e:
        print(f"[{i+1}] FAIL {base}: {e}")
