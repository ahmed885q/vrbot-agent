import os, glob
from PIL import Image
from ultralytics import YOLO
from roboflow import Roboflow

MODEL_PATH = r"C:\Users\manso\vrbot-agent\models\best.pt"
IMAGES_DIR = r"C:\Users\manso\vrbot-agent\dataset\screenshots"
LABELS_DIR = r"C:\Users\manso\vrbot-agent\dataset\labels"
XML_DIR = r"C:\Users\manso\vrbot-agent\dataset\xml_labels"
API_KEY = "uwA6un1dJmhKwxbbN1Wg"
WORKSPACE = "vrbot"
PROJECT = "vrbot-detection"
TAG = chr(60) + "name" + chr(62)
CTAG = chr(60) + "/name" + chr(62)

def yolo_to_voc_xml(image_path, label_path, class_names, xml_path):
    img = Image.open(image_path)
    img_w, img_h = img.size
    img_name = os.path.basename(image_path)
    objects = []
    with open(label_path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) < 5: continue
            cid = int(p[0])
            xc,yc,w,h = float(p[1]),float(p[2]),float(p[3]),float(p[4])
            xmin = max(0, int((xc-w/2)*img_w))
            ymin = max(0, int((yc-h/2)*img_h))
            xmax = min(img_w, int((xc+w/2)*img_w))
            ymax = min(img_h, int((yc+h/2)*img_h))
            cn = class_names.get(cid, f"class_{cid}")
            objects.append((cn, xmin, ymin, xmax, ymax))
    L = ["<annotation>"]
    L.append(f"  <filename>{img_name}</filename>")
    L.append(f"  <size><width>{img_w}</width><height>{img_h}</height><depth>3</depth></size>")
    for cn, x1, y1, x2, y2 in objects:
        L.append(f"  <object>{TAG}{cn}{CTAG}<bndbox><xmin>{x1}</xmin><ymin>{y1}</ymin><xmax>{x2}</xmax><ymax>{y2}</ymax></bndbox></object>")
    L.append("</annotation>")
    with open(xml_path, "w") as f:
        f.write(chr(10).join(L))
    return len(objects)

def main():
    print("VRBOT Fix Labels v2")
    model = YOLO(MODEL_PATH)
    cn = model.names
    print(f"Classes: {len(cn)}")
    os.makedirs(XML_DIR, exist_ok=True)
    labels = sorted([f for f in glob.glob(os.path.join(LABELS_DIR, "*.txt")) if "_classes" not in f])
    print(f"Labels: {len(labels)}")
    c = 0
    for lbl in labels:
        b = os.path.splitext(os.path.basename(lbl))[0]
        ip = os.path.join(IMAGES_DIR, f"{b}.png")
        xp = os.path.join(XML_DIR, f"{b}.xml")
        if not os.path.exists(ip): continue
        yolo_to_voc_xml(ip, lbl, cn, xp)
        c += 1
    print(f"Converted: {c}")
    print("Uploading to Roboflow...")
    rf = Roboflow(api_key=API_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)
    xmls = sorted(glob.glob(os.path.join(XML_DIR, "*.xml")))
    ok = fail = 0
    for xp in xmls:
        b = os.path.splitext(os.path.basename(xp))[0]
        ip = os.path.join(IMAGES_DIR, f"{b}.png")
        if not os.path.exists(ip): continue
        try:
            project.upload(image_path=ip, annotation_path=xp, split="train", overwrite=True)
            ok += 1
            print(f"  [{ok}] OK {b}")
        except Exception as e:
            fail += 1
            print(f"  FAIL {b}: {e}")
    print(f"Done! OK: {ok} | FAIL: {fail}")

if __name__ == "__main__":
    main()
