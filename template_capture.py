"""
VRBOT Template Capture Tool
============================
Auto-generates template images from game screenshots using YOLO detections.
Also copies useful templates from reference repos.

Usage:
  python template_capture.py auto     # YOLO-based auto capture
  python template_capture.py ref      # Copy from reference repos  
  python template_capture.py manual   # Manual capture with coordinates
  python template_capture.py all      # Do everything
"""
import subprocess, os, sys, time, shutil, glob
from PIL import Image
import numpy as np

# Config
ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
ADB_DEVICE = "emulator-5554"
TEMPLATE_DIR = "templates"
DEBUG_DIR = "debug_screenshots"
REF_VR = r"C:\Users\manso\Desktop\vr-bot-ref"
REF_ROK = r"C:\Users\manso\Desktop\rok-bot-ref"

# Categories for organizing templates
CATEGORIES = {
    "buttons": [
        "claim_btn", "claim_all_botn", "claim_free_btn", "close_btn", "back_btn",
        "confirm_btn", "ok_btn", "cancel_btn", "upgrade_btn", "upgrade_now_btn",
        "attack_btn", "march_btn", "depart_btn", "gather_btn", "train_btn",
        "train_now_btn", "quick_train_btn", "heal_now_btn", "healing_btn",
        "submit_btn", "submit_all_btn", "donate_btn", "donate_gem_btn",
        "recruit_btn", "recruitment_btn", "search_btn", "create_btn",
        "go_btn", "speed_up_btn", "use_btn", "rally_btn", "recall_btn",
        "maximum_btn", "appoint_all_btn", "converge_btn", "assist_btn",
        "complete_all_btn", "explore_btn", "hire_btn",
    ],
    "icons": [
        "city_icon", "city location_icon", "compass_icon", "mail_icon",
        "quest_icon", "event_icon", "hero_icon", "gift_icon", "prosperity_icon",
        "monster_icon", "farm_icon", "quarry_icon", "sawmil_icon",
        "niflung_icon", "boss_icon", "resource-bar_icon",
        "here-avatar_icon", "worker_inf_icon", "chat_ box_icon",
    ],
    "popups": [
        "building_upgrade_popup", "barracks_popup", "mail_popup",
        "tribe_popup", "commission_popup", "divination_shack_popup",
        "infirmary_popup", "note_popup", "success_massage",
        "treasure_obtained_popup",
    ],
    "nav": [
        "warld_btn", "world_botn", "resource_bar", "manage city_icon",
        "daily_quests", "technology_btn",
    ],
}


def adb(*args):
    cmd = [ADB_EXE, "-s", ADB_DEVICE] + list(args)
    return subprocess.run(cmd, capture_output=True, timeout=15)


def take_screenshot(name="capture"):
    """Take screenshot — try exec-out first, fallback to shell+pull."""
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    os.makedirs(DEBUG_DIR, exist_ok=True)

    # Method 1: exec-out (fast, works on real devices)
    try:
        result = subprocess.run(
            [ADB_EXE, "-s", ADB_DEVICE, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=10
        )
        if result.returncode == 0 and len(result.stdout) > 5000:
            with open(path, "wb") as f:
                f.write(result.stdout)
            img = Image.open(path)
            img.verify()
            return path
    except:
        pass

    # Method 2: shell + pull (works on LDPlayer)
    for attempt in range(3):
        try:
            adb("shell", "screencap", "-p", "/sdcard/vrbot_screen.png")
            time.sleep(0.3)
            adb("pull", "/sdcard/vrbot_screen.png", path)
            if os.path.exists(path) and os.path.getsize(path) > 5000:
                img = Image.open(path)
                img.verify()
                return path
        except:
            pass
        time.sleep(0.5)

    print(f"  [ERROR] Could not take screenshot: {path}")
    return path


def run_yolo(image_path):
    """Run YOLO ONNX on image, return detections."""
    import onnxruntime as ort
    import ast

    model_path = "models/best.onnx"
    if not os.path.exists(model_path):
        print(f"[ERROR] YOLO model not found: {model_path}")
        return []

    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    meta = session.get_modelmeta()
    labels = ast.literal_eval(meta.custom_metadata_map["names"])

    img = Image.open(image_path).convert("RGB")
    orig_w, orig_h = img.size

    input_shape = session.get_inputs()[0].shape
    input_size = input_shape[2] if len(input_shape) >= 3 else 720

    scale = min(input_size / orig_w, input_size / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)
    img_resized = img.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (input_size, input_size), (114, 114, 114))
    pad_x = (input_size - new_w) // 2
    pad_y = (input_size - new_h) // 2
    canvas.paste(img_resized, (pad_x, pad_y))

    arr = np.array(canvas, dtype=np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)
    arr = np.expand_dims(arr, 0)

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: arr})
    preds = outputs[0]

    if preds.shape[1] < preds.shape[2]:
        preds = preds[0].T
    else:
        preds = preds[0]

    detections = []
    for pred in preds:
        cx, cy, w, h = pred[:4]
        class_scores = pred[4:]
        cls_id = int(np.argmax(class_scores))
        conf = float(class_scores[cls_id])

        if conf < 0.35:  # lower threshold for capture
            continue

        x1 = int((cx - w / 2 - pad_x) / scale)
        y1 = int((cy - h / 2 - pad_y) / scale)
        x2 = int((cx + w / 2 - pad_x) / scale)
        y2 = int((cy + h / 2 - pad_y) / scale)

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(orig_w, x2), min(orig_h, y2)

        cls_name = labels.get(cls_id, f"class_{cls_id}").lower()
        detections.append({
            "class": cls_name,
            "confidence": round(conf, 3),
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        })

    return detections


def get_category(class_name):
    """Determine which category a class belongs to."""
    for cat, classes in CATEGORIES.items():
        for c in classes:
            if c.lower() in class_name or class_name in c.lower():
                return cat
    if "btn" in class_name or "button" in class_name:
        return "buttons"
    if "icon" in class_name:
        return "icons"
    if "popup" in class_name:
        return "popups"
    return "other"


def auto_capture():
    """Take multiple screenshots, run YOLO, save each detection as template."""
    print("\n" + "=" * 60)
    print("  AUTO CAPTURE: Taking screenshots + YOLO detection")
    print("=" * 60)

    # Create template directories
    for cat in list(CATEGORIES.keys()) + ["other"]:
        os.makedirs(os.path.join(TEMPLATE_DIR, cat), exist_ok=True)

    captured = {}  # class_name -> count
    total_saved = 0

    # Take screenshots with different game states
    screens = [
        ("screen_current", "Current screen"),
    ]

    for screen_name, desc in screens:
        print(f"\n  [{desc}] Taking screenshot...")
        img_path = take_screenshot(screen_name)
        img = Image.open(img_path)

        detections = run_yolo(img_path)
        print(f"  [{desc}] Found {len(detections)} detections")

        for det in detections:
            cls = det["class"]
            conf = det["confidence"]
            x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]

            # Skip tiny or huge detections
            w = x2 - x1
            h = y2 - y1
            if w < 10 or h < 10 or w > 800 or h > 500:
                continue

            # Skip if we already have a better version
            count = captured.get(cls, 0)
            if count >= 3:  # max 3 per class
                continue

            # Crop and save
            cat = get_category(cls)
            crop = img.crop((x1, y1, x2, y2))

            # Clean filename
            safe_name = cls.replace(" ", "_").replace("-", "_")
            filename = f"{safe_name}_{count}.png"
            save_path = os.path.join(TEMPLATE_DIR, cat, filename)
            crop.save(save_path)
            captured[cls] = count + 1
            total_saved += 1
            print(f"    ✓ {cat}/{filename} ({w}x{h}, conf={conf})")

    print(f"\n  Total templates captured: {total_saved}")
    print(f"  Unique classes: {len(captured)}")
    return total_saved


def auto_capture_multi(num_screenshots=5, delay=3):
    """Take multiple screenshots over time to capture different game states."""
    print("\n" + "=" * 60)
    print(f"  MULTI-CAPTURE: {num_screenshots} screenshots, {delay}s apart")
    print("  Interact with the game during capture!")
    print("=" * 60)

    for cat in list(CATEGORIES.keys()) + ["other"]:
        os.makedirs(os.path.join(TEMPLATE_DIR, cat), exist_ok=True)

    captured = {}
    total_saved = 0

    for i in range(num_screenshots):
        print(f"\n  --- Screenshot {i+1}/{num_screenshots} ---")
        img_path = take_screenshot(f"multi_{i:02d}")
        img = Image.open(img_path)

        detections = run_yolo(img_path)
        print(f"  Found {len(detections)} detections")

        for det in detections:
            cls = det["class"]
            conf = det["confidence"]
            x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]

            w = x2 - x1
            h = y2 - y1
            if w < 10 or h < 10 or w > 800 or h > 500:
                continue

            count = captured.get(cls, 0)
            if count >= 3:
                continue

            # Only save high-confidence detections as templates
            if conf < 0.50:
                continue

            cat = get_category(cls)
            crop = img.crop((x1, y1, x2, y2))
            safe_name = cls.replace(" ", "_").replace("-", "_")
            filename = f"{safe_name}_{count}.png"
            save_path = os.path.join(TEMPLATE_DIR, cat, filename)
            crop.save(save_path)
            captured[cls] = count + 1
            total_saved += 1
            print(f"    ✓ {cat}/{filename} ({w}x{h}, conf={conf})")

        if i < num_screenshots - 1:
            print(f"  Waiting {delay}s... (navigate in game)")
            time.sleep(delay)

    print(f"\n  Total templates: {total_saved}")
    print(f"  Classes captured: {len(captured)}")
    return total_saved


def copy_ref_templates():
    """Copy useful templates from reference repos (ROK + VR bots)."""
    print("\n" + "=" * 60)
    print("  REFERENCE: Copying templates from reference repos")
    print("=" * 60)

    ref_dir = os.path.join(TEMPLATE_DIR, "reference")
    os.makedirs(ref_dir, exist_ok=True)

    copied = 0

    # ROK-bot has nicely named button templates
    rok_mapping = {
        "attack_button.png": "buttons/ref_attack_btn.png",
        "resource_gather_button.png": "buttons/ref_gather_btn.png",
        "resource_search_button.png": "buttons/ref_search_btn.png",
        "quests_claim_button.png": "buttons/ref_claim_btn.png",
        "alliance_gifts_claim_button.png": "buttons/ref_alliance_claim.png",
        "alliance_tech_donate.png": "buttons/ref_donate_btn.png",
        "alliance_tech_recommend.png": "buttons/ref_recommend_btn.png",
        "speed_up_button.png": "buttons/ref_speedup_btn.png",
        "return_button.png": "buttons/ref_return_btn.png",
        "home_button.png": "nav/ref_home_btn.png",
        "home_button_0.png": "nav/ref_home_btn_0.png",
        "map_button.png": "nav/ref_map_btn.png",
        "map_button_0.png": "nav/ref_map_btn_0.png",
        "heal_icon.png": "icons/ref_heal_icon.png",
        "new_troops_button.png": "buttons/ref_train_btn.png",
        "chest_open_button.png": "buttons/ref_open_btn.png",
        "chest_confirm_button.png": "buttons/ref_confirm_btn.png",
        "scout_button.png": "buttons/ref_scout_btn.png",
        "explore_button.png": "buttons/ref_explore_btn.png",
        "menu_button.png": "nav/ref_menu_btn.png",
        "march_bar.png": "nav/ref_march_bar.png",
        "barracks_button.png": "icons/ref_barracks_icon.png",
        "archery_range_button.png": "icons/ref_archery_icon.png",
        "daily_ap_claim.png": "buttons/ref_daily_claim.png",
    }

    for src_name, dst_rel in rok_mapping.items():
        src = os.path.join(REF_ROK, "resource", src_name)
        if os.path.exists(src):
            dst_dir = os.path.join(TEMPLATE_DIR, os.path.dirname(dst_rel))
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(TEMPLATE_DIR, dst_rel)
            shutil.copy2(src, dst)
            copied += 1
            img = Image.open(dst)
            print(f"  ✓ {dst_rel} ({img.size[0]}x{img.size[1]})")

    # VR-bot has some Viking Rise specific templates
    vr_mapping = {
        "imgs/02_cj_back.png": "buttons/ref_vr_back.png",
        "imgs/02_cj_cross.png": "buttons/ref_vr_close.png",
        "imgs/04_cj_cancel.png": "buttons/ref_vr_cancel.png",
        "imgs/04_cj_confirm.png": "buttons/ref_vr_confirm.png",
        "imgs/02_cj_ssj_green.png": "buttons/ref_vr_green_btn.png",
        "imgs/03_cj_44_arrow.png": "icons/ref_vr_arrow.png",
    }

    for src_rel, dst_rel in vr_mapping.items():
        src = os.path.join(REF_VR, src_rel)
        if os.path.exists(src):
            dst_dir = os.path.join(TEMPLATE_DIR, os.path.dirname(dst_rel))
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(TEMPLATE_DIR, dst_rel)
            shutil.copy2(src, dst)
            copied += 1
            img = Image.open(dst)
            print(f"  ✓ {dst_rel} ({img.size[0]}x{img.size[1]})")

    print(f"\n  Reference templates copied: {copied}")
    return copied


def print_summary():
    """Print template inventory."""
    print("\n" + "=" * 60)
    print("  TEMPLATE INVENTORY")
    print("=" * 60)
    total = 0
    for cat in os.listdir(TEMPLATE_DIR):
        cat_path = os.path.join(TEMPLATE_DIR, cat)
        if os.path.isdir(cat_path):
            files = [f for f in os.listdir(cat_path) if f.endswith(('.png', '.jpg'))]
            if files:
                print(f"\n  📁 {cat}/ ({len(files)} templates)")
                for f in sorted(files):
                    img = Image.open(os.path.join(cat_path, f))
                    print(f"    {f}: {img.size[0]}x{img.size[1]}")
                    total += 1
    print(f"\n  TOTAL: {total} templates")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True)

    if mode == "auto":
        auto_capture()
    elif mode == "multi":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        auto_capture_multi(num_screenshots=n)
    elif mode == "ref":
        copy_ref_templates()
    elif mode == "all":
        copy_ref_templates()
        auto_capture()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python template_capture.py [auto|multi|ref|all]")
        sys.exit(1)

    print_summary()
    print("\nDone! Now run: python template_capture.py multi 10")
    print("(Navigate through different game screens during capture)")
