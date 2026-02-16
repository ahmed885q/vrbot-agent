"""
VRBOT Re-Label & Upload as XML
"""
import os, glob
from ultralytics import YOLO
from roboflow import Roboflow

MODEL_PATH = r"C:\Users\manso\vrbot-agent\models\best.pt"
IMAGES_DIR = r"C:\Users\manso\vrbot-agent\dataset\screenshots"
XML_DIR = r"C:\Users\manso\vrbot-agent\dataset\xml_labels_v4"
CONFIDENCE = 0.40
API_KEY = "uwA6un1dJmhKwxbbN1Wg"

def make_xml(img_name, img_w, img_h, boxes):
    LT = chr(60)
    GT = chr(62)
    name_open = LT + "name" + GT
    name_close = LT + "/name" + GT
    lines = []
    lines.append(LT + "annotation" + GT)
    lines.append(f"  {LT}filename{GT}{img_name}{LT}/filename{GT}")
    lines.append(f"  {LT}size{GT}")
    lines.append(f"    {LT}width{GT}{img_w}{LT}/width{GT}")
    lines.append(f"    {LT}height{GT}{img_h}{LT}/height{GT}")
    lines.append(f"    {LT}depth{GT}3{LT}/depth{GT}")
    lines.append(f"  {LT}/size{GT}")
    for cls_name, x1, y1, x2, y2, conf in boxes:
        lines.append(f"  {LT}object{GT}")
        lines.append(f"    {name_open}{cls_name}{name_close}")
        lines.append(f"    {LT}pose{GT}Unspecified{LT}/pose{GT}")
        lines.append(f"    {LT}truncated{GT}0{LT}/truncated{GT}")
        lines.append(f"    {LT}difficult{GT}0{LT}/difficult{GT}")
        lines.append(f"    {LT}bndbox{GT}")
        lines.append(f"      {LT}xmin{GT}{int(x1)}{LT}/xmin{GT}")
        lines.append(f"      {LT}ymin{GT}{int(y1)}{LT}/ymin{GT}")
        lines.append(f"      {LT}xmax{GT}{int(x2)}{LT}/xmax{GT}")
        lines.append(f"      {LT}ymax{GT}{int(y2)}{LT}/ymax{GT}")
        lines.append(f"    {LT}/bndbox{GT}")
        lines.append(f"  {LT}/object{GT}")
    lines.append(LT + "/annotation" + GT)
    return "\n".join(lines)

def main():
    print("=" * 60)
    print("VRBOT Re-Label as XML and Upload")
    print("=" * 60)

    print("\n[1/3] Loading model...")
    model = YOLO(MODEL_PATH)
    names = model.names
    print(f"  Model: {len(names)} classes")

    print(f"\n[2/3] Labeling images (conf={CONFIDENCE})...")
    os.makedirs(XML_DIR, exist_ok=True)

    images = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.png")))
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
        boxes = []
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            cls_name = names.get(cls_id, f"class_{cls_id}")
            boxes.append((cls_name, x1, y1, x2, y2, conf))
        xml_content = make_xml(img_name, img_w, img_h, boxes)
        xml_path = os.path.join(XML_DIR, f"{base}.xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        total_dets += len(boxes)
        labeled += 1
        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(images)}...")

    print(f"  Labeled: {labeled}, Skipped: {skipped}, Detections: {total_dets}")

    print(f"\n[3/3] Uploading to Roboflow...")
    rf = Roboflow(api_key=API_KEY)
    project = rf.workspace("vrbot").project("vrbot-detection")
    ok = 0
    fail = 0
    xml_files = sorted(glob.glob(os.path.join(XML_DIR, "*.xml")))
    for xml_path in xml_files:
        base = os.path.splitext(os.path.basename(xml_path))[0]
        img_path = os.path.join(IMAGES_DIR, f"{base}.png")
        if not os.path.exists(img_path):
            continue
        try:
            project.upload(image_path=img_path, annotation_path=xml_path, split="train", overwrite=True)
            ok += 1
            if ok % 20 == 0:
                print(f"  Uploaded {ok}...")
        except Exception as e:
            fail += 1
            if fail <= 3:
                print(f"  FAIL {base}: {str(e)[:80]}")

    print(f"\nDONE! Labeled: {labeled} | Uploaded: {ok} | Failed: {fail}")
    print(f"Next: Create Version 5 in Roboflow, then train on Colab with version(5)")

if __name__ == "__main__":
    main()
