"""
VRBOT Smart Template Capture
==============================
Uses AI (one-time cost ~$0.05) to find ALL buttons in screenshots,
then crops and saves them as permanent templates.

Run: python smart_capture.py
Navigate through game screens during capture!
"""
import subprocess, os, time, json, base64
from PIL import Image

ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
ADB_DEVICE = "emulator-5554"
TEMPLATE_DIR = "templates"
DEBUG_DIR = "debug_screenshots"

def adb(*args):
    cmd = [ADB_EXE, "-s", ADB_DEVICE] + list(args)
    return subprocess.run(cmd, capture_output=True, timeout=15)

def screenshot(name):
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    os.makedirs(DEBUG_DIR, exist_ok=True)
    adb("shell", "screencap", "-p", "/sdcard/vrbot_screen.png")
    time.sleep(0.3)
    adb("pull", "/sdcard/vrbot_screen.png", path)
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        return path
    return None

def img_to_b64(path):
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def ask_ai_buttons(image_b64):
    """Ask GPT-4o mini to find ALL buttons and UI elements in screenshot."""
    from openai import OpenAI
    client = OpenAI()
    
    prompt = """Viking Rise game screenshot (1280x720). Find ALL clickable buttons and UI elements.

For EACH element, give me:
- name: descriptive name (e.g. "close_btn", "claim_btn", "ok_btn", "back_btn", "upgrade_btn")
- x1, y1, x2, y2: bounding box coordinates (top-left to bottom-right)
- category: "buttons", "icons", "nav", or "popups"

Look for these types:
- Close/X buttons (usually top-right of popups)
- Back buttons (top-left with arrow)
- OK/Confirm/Yes buttons (center-bottom of popups)
- Cancel buttons
- Claim/Collect buttons (green)
- Upgrade/Build buttons
- Train/Recruit buttons
- Speed Up buttons
- Donate buttons
- Attack/March/Gather buttons
- Navigation icons (mail, quests, alliance, hero, shop)
- Resource bar elements
- Any other clickable buttons

Return JSON array ONLY:
[{"name":"close_btn","x1":1220,"y1":25,"x2":1260,"y2":55,"category":"buttons"},...]

Find as many as possible! JSON ONLY, no other text."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=2000,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "high"}},
            {"type": "text", "text": prompt}
        ]}],
    )
    
    text = resp.choices[0].message.content
    # Parse JSON
    try:
        # Try direct parse
        return json.loads(text.strip())
    except:
        # Find JSON array in text
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except:
                pass
    print(f"  [WARN] Could not parse AI response: {text[:200]}")
    return []


def capture_screen(screen_name, instructions):
    """Capture one screen and extract all buttons."""
    print(f"\n{'='*50}")
    print(f"  📸 Capturing: {screen_name}")
    print(f"  📋 {instructions}")
    print(f"{'='*50}")
    
    input(f"  Press ENTER when ready (game showing {screen_name})...")
    
    # Take screenshot
    path = screenshot(f"smart_{screen_name}")
    if not path or not os.path.exists(path):
        print(f"  [ERROR] Screenshot failed!")
        return 0
    
    img = Image.open(path)
    b64 = img_to_b64(path)
    
    # Ask AI to find all buttons
    print(f"  🤖 Asking AI to find buttons...")
    elements = ask_ai_buttons(b64)
    print(f"  Found {len(elements)} elements")
    
    saved = 0
    for elem in elements:
        name = elem.get("name", "unknown").lower().replace(" ", "_")
        cat = elem.get("category", "buttons")
        x1 = int(elem.get("x1", 0))
        y1 = int(elem.get("y1", 0))
        x2 = int(elem.get("x2", 0))
        y2 = int(elem.get("y2", 0))
        
        # Validate
        if x1 > x2: x1, x2 = x2, x1
        if y1 > y2: y1, y2 = y2, y1
        w, h = x2 - x1, y2 - y1
        if w < 15 or h < 12 or w > 500 or h > 300:
            print(f"  ⚠ Skip {name}: bad size {w}x{h}")
            continue
        if x1 < 0 or y1 < 0 or x2 > 1280 or y2 > 720:
            print(f"  ⚠ Skip {name}: out of bounds")
            continue
        
        # Add padding (4px each side for tolerance)
        pad = 4
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(1280, x2 + pad)
        y2 = min(720, y2 + pad)
        
        # Crop and save
        cat_dir = os.path.join(TEMPLATE_DIR, cat)
        os.makedirs(cat_dir, exist_ok=True)
        
        # Avoid duplicate names
        save_name = f"{name}.png"
        save_path = os.path.join(cat_dir, save_name)
        counter = 0
        while os.path.exists(save_path):
            counter += 1
            save_name = f"{name}_{counter}.png"
            save_path = os.path.join(cat_dir, save_name)
        
        crop = img.crop((x1, y1, x2, y2))
        crop.save(save_path)
        saved += 1
        print(f"  ✅ {cat}/{save_name} ({x2-x1}x{y2-y1})")
    
    return saved


def auto_mode():
    """Automatic mode - take screenshots and ask AI, no user interaction."""
    print("\n" + "=" * 60)
    print("  🤖 AUTO MODE: Taking screenshots + AI analysis")
    print("  Cost: ~$0.01 per screenshot (GPT-4o mini with detail=high)")
    print("=" * 60)
    
    total = 0
    
    # Take current screenshot
    path = screenshot("smart_auto_current")
    if path and os.path.exists(path):
        img = Image.open(path)
        b64 = img_to_b64(path)
        print(f"\n  📸 Analyzing current screen...")
        elements = ask_ai_buttons(b64)
        print(f"  Found {len(elements)} elements")
        
        for elem in elements:
            name = elem.get("name", "unknown").lower().replace(" ", "_")
            cat = elem.get("category", "buttons")
            x1, y1 = int(elem.get("x1", 0)), int(elem.get("y1", 0))
            x2, y2 = int(elem.get("x2", 0)), int(elem.get("y2", 0))
            
            # Fix swapped coordinates from AI
            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1
            w, h = x2 - x1, y2 - y1
            if w < 15 or h < 12 or w > 500 or h > 300:
                continue
            if x1 < 0 or y1 < 0 or x2 > 1280 or y2 > 720:
                continue
            
            pad = 4
            x1, y1 = max(0, x1-pad), max(0, y1-pad)
            x2, y2 = min(1280, x2+pad), min(720, y2+pad)
            
            cat_dir = os.path.join(TEMPLATE_DIR, cat)
            os.makedirs(cat_dir, exist_ok=True)
            save_name = f"{name}.png"
            save_path = os.path.join(cat_dir, save_name)
            counter = 0
            while os.path.exists(save_path):
                counter += 1
                save_name = f"{name}_{counter}.png"
                save_path = os.path.join(cat_dir, save_name)
            
            crop = img.crop((x1, y1, x2, y2))
            crop.save(save_path)
            total += 1
            print(f"  ✅ {cat}/{save_name} ({x2-x1}x{y2-y1})")
    
    # Also analyze existing screenshots
    import glob
    existing = sorted(glob.glob(os.path.join(DEBUG_DIR, "multi_*.png")))
    for spath in existing:
        if not os.path.exists(spath):
            continue
        img = Image.open(spath)
        b64 = img_to_b64(spath)
        print(f"\n  📸 Analyzing {os.path.basename(spath)}...")
        elements = ask_ai_buttons(b64)
        print(f"  Found {len(elements)} elements")
        
        for elem in elements:
            name = elem.get("name", "unknown").lower().replace(" ", "_")
            cat = elem.get("category", "buttons")
            x1, y1 = int(elem.get("x1", 0)), int(elem.get("y1", 0))
            x2, y2 = int(elem.get("x2", 0)), int(elem.get("y2", 0))
            
            # Fix swapped coordinates from AI
            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1
            w, h = x2 - x1, y2 - y1
            if w < 15 or h < 12 or w > 500 or h > 300:
                continue
            
            pad = 4
            x1, y1 = max(0, x1-pad), max(0, y1-pad)
            x2, y2 = min(1280, x2+pad), min(720, y2+pad)
            
            cat_dir = os.path.join(TEMPLATE_DIR, cat)
            os.makedirs(cat_dir, exist_ok=True)
            save_name = f"{name}.png"
            save_path = os.path.join(cat_dir, save_name)
            counter = 0
            while os.path.exists(save_path):
                counter += 1
                save_name = f"{name}_{counter}.png"
                save_path = os.path.join(cat_dir, save_name)
            
            crop = img.crop((x1, y1, x2, y2))
            crop.save(save_path)
            total += 1
            print(f"  ✅ {cat}/{save_name} ({x2-x1}x{y2-y1})")
    
    return total


def interactive_mode():
    """Guide user through different screens to capture templates."""
    SCREENS = [
        ("city_main", "Navigate to your CITY (main base view)"),
        ("city_popup", "Tap any BUILDING to open its popup (with upgrade/close buttons)"),
        ("mail", "Open MAIL inbox"),
        ("alliance", "Open ALLIANCE/TRIBE panel"),
        ("quests", "Open DAILY QUESTS / EVENTS"),
        ("barracks", "Open BARRACKS (troop training)"),
        ("world_map", "Go to WORLD MAP"),
        ("world_action", "Tap a RESOURCE TILE on world map (gather popup)"),
    ]
    
    total = 0
    print("\n" + "=" * 60)
    print("  🎮 INTERACTIVE CAPTURE MODE")
    print("  Navigate to each screen, I'll capture all buttons!")
    print("  Cost: ~$0.08 total (8 screens × $0.01)")
    print("=" * 60)
    
    for screen_name, instructions in SCREENS:
        saved = capture_screen(screen_name, instructions)
        total += saved
        print(f"  📊 Total so far: {total} templates")
    
    return total


def print_inventory():
    """Print all templates."""
    print("\n" + "=" * 60)
    print("  📦 TEMPLATE INVENTORY")
    print("=" * 60)
    total = 0
    for cat in sorted(os.listdir(TEMPLATE_DIR)):
        cat_path = os.path.join(TEMPLATE_DIR, cat)
        if not os.path.isdir(cat_path):
            continue
        files = sorted([f for f in os.listdir(cat_path) if f.endswith(('.png','.jpg'))])
        if files:
            print(f"\n  📁 {cat}/ ({len(files)} templates)")
            for f in files:
                try:
                    img = Image.open(os.path.join(cat_path, f))
                    print(f"    {f}: {img.size[0]}x{img.size[1]}")
                except:
                    print(f"    {f}: (error reading)")
                total += 1
    print(f"\n  TOTAL: {total} templates")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True)
    
    if mode == "auto":
        total = auto_mode()
    elif mode == "interactive":
        total = interactive_mode()
    else:
        print("Usage: python smart_capture.py [auto|interactive]")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"  ✅ Captured {total} new templates!")
    print(f"{'='*60}")
    print_inventory()
