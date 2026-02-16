import os, glob
from ultralytics import YOLO
from roboflow import Roboflow

MODEL_PATH = r"C:\Users\manso\vrbot-agent\models\best.pt"
IMAGES_DIR = r"C:\Users\manso\vrbot-agent\dataset\screenshots"
XML_DIR = r"C:\Users\manso\vrbot-agent\dataset\xml_labels_v4"
CONFIDENCE = 0.40

def make_xml(img_name, img_w, img_h, boxes):
    LT, GT = chr(60), chr(62)
    NO, NC = LT+"name"+GT, LT+"/name"+GT
    l = []
    l.append(LT+"annotation"+GT)
    l.append(f"  {LT}filename{GT}{img_name}{LT}/filename{GT}")
    l.append(f"  {LT}size{GT}")
    l.append(f"    {LT}width{GT}{img_w}{LT}/width{GT}")
    l.append(f"    {LT}height{GT}{img_h}{LT}/height{GT}")
    l.append(f"    {LT}depth{GT}3{LT}/depth{GT}")
    l.append(f"  {LT}/size{GT}")
    for cn, x1, y1, x2, y2, cf in boxes:
        l.append(f"  {LT}object{GT}")
        l.append(f"    {NO}{cn}{NC}")
        l.append(f"    {LT}bndbox{GT}")
        l.append(f"      {LT}xmin{GT}{int(x1)}{LT}/xmin{GT}")
        l.append(f"      {LT}ymin{GT}{int(y1)}{LT}/ymin{GT}")
        l.append(f"      {LT}xmax{GT}{int(x2)}{LT}/xmax{GT}")
        l.append(f"      {LT}ymax{GT}{int(y2)}{LT}/ymax{GT}")
        l.append(f"    {LT}/bndbox{GT}")
        l.append(f"  {LT}/object{GT}")
    l.append(LT+"/annotation"+GT)
    return "\n".join(l)

model = YOLO(MODEL_PATH)
names = model.names
print(f"Model: {len(names)} classes")
os.makedirs(XML_DIR, exist_ok=True)
images = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.png")))
labeled = 0
for i, img_path in enumerate(images):
    base = os.path.splitext(os.path.basename(img_path))[0]
    r = model(img_path, conf=CONFIDENCE, verbose=False)[0]
    if len(r.boxes) == 0: continue
    h, w = r.orig_shape
    boxes = [(names.get(int(b.cls[0].item()),"unk"), *b.xyxy[0].tolist(), float(b.conf[0])) for b in r.boxes]
    with open(os.path.join(XML_DIR, f"{base}.xml"), "w") as f:
        f.write(make_xml(os.path.basename(img_path), w, h, boxes))
    labeled += 1
    if (i+1) % 50 == 0: print(f"  {i+1}/{len(images)}...")
print(f"Labeled: {labeled}/{len(images)}")

rf = Roboflow(api_key="uwA6un1dJmhKwxbbN1Wg")
project = rf.workspace("vrbot").project("vrbot-detection")
ok = 0
for x in sorted(glob.glob(os.path.join(XML_DIR, "*.xml"))):
    base = os.path.splitext(os.path.basename(x))[0]
    img = os.path.join(IMAGES_DIR, f"{base}.png")
    if not os.path.exists(img): continue
    try:
        project.upload(image_path=img, annotation_path=x, split="train", overwrite=True)
        ok += 1
        if ok % 20 == 0: print(f"  Uploaded {ok}...")
    except: pass
print(f"Done! Uploaded: {ok}")
