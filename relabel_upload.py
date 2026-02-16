from ultralytics import YOLO
from roboflow import Roboflow
import os, glob

MODEL_PATH = r"C:\Users\manso\vrbot-agent\models\best.pt"
IMAGES_DIR = r"C:\Users\manso\vrbot-agent\dataset\screenshots"
LABELS_DIR = r"C:\Users\manso\vrbot-agent\dataset\labels_v3"

os.makedirs(LABELS_DIR, exist_ok=True)
model = YOLO(MODEL_PATH)
names = model.names
print(f"Model: {len(names)} classes")

with open(os.path.join(LABELS_DIR, "_classes.txt"), "w") as f:
    for i in range(max(names.keys())+1):
        f.write(f"{names.get(i,'unknown')}\n")

images = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.png")))
labeled = 0
for img_path in images:
    base = os.path.splitext(os.path.basename(img_path))[0]
    results = model(img_path, conf=0.40, verbose=False)
    r = results[0]
    if len(r.boxes) == 0: continue
    h, w = r.orig_shape
    with open(os.path.join(LABELS_DIR, f"{base}.txt"), "w") as f:
        for box in r.boxes:
            x1,y1,x2,y2 = box.xyxy[0].tolist()
            cid = int(box.cls[0].item())
            f.write(f"{cid} {((x1+x2)/2)/w:.6f} {((y1+y2)/2)/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}\n")
    labeled += 1

print(f"Labeled: {labeled}/{len(images)}")

rf = Roboflow(api_key="uwA6un1dJmhKwxbbN1Wg")
project = rf.workspace("vrbot").project("vrbot-detection")
ok = 0
for lbl in sorted(glob.glob(os.path.join(LABELS_DIR, "*.txt"))):
    if "_classes" in lbl: continue
    base = os.path.splitext(os.path.basename(lbl))[0]
    img = os.path.join(IMAGES_DIR, f"{base}.png")
    if not os.path.exists(img): continue
    try:
        project.upload(image_path=img, annotation_path=lbl, split="train", overwrite=True)
        ok += 1
        if ok % 20 == 0: print(f"Uploaded {ok}...")
    except: pass
print(f"Done! Uploaded: {ok}")
