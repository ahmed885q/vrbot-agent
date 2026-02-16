"""
VRBOT Train Troops v2.2 — AI Vision (Full Auto)
Fully automated: finds barracks, opens training, trains troops in rotation.
SAFETY: No adb_back, no OK on popups.

Usage:
  python test_train_troops.py              # detect test
  python test_train_troops.py train        # single train
  python test_train_troops.py auto         # 1 rotation
  python test_train_troops.py auto 3       # 3 rotations
"""
import subprocess, os, sys, time, json, base64, re

# --- Config ---
ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
ADB_DEVICE = "127.0.0.1:5555"
DEBUG_DIR = "debug_screenshots"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
TROOP_ROTATION = ['infantry', 'lancer', 'archer']

# --- Anthropic Client ---
try:
    import anthropic
    client = anthropic.Anthropic()
except ImportError:
    print("ERROR: pip install anthropic"); sys.exit(1)
except Exception as e:
    print("ERROR:", e); sys.exit(1)


# --- ADB Helpers ---
def adb_tap(x, y):
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "input", "tap", str(x), str(y)],
                   capture_output=True, timeout=10)
    print(f"    tap ({x},{y})")

def adb_swipe(x1, y1, x2, y2, duration=500):
    """Swipe/scroll the screen."""
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "input", "swipe",
                    str(x1), str(y1), str(x2), str(y2), str(duration)],
                   capture_output=True, timeout=10)
    print(f"    swipe ({x1},{y1})->({x2},{y2})")

def screenshot(name="screen"):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, name + ".png")
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "screencap", "-p",
                    "/sdcard/vrbot_train.png"], capture_output=True, timeout=10)
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "pull", "/sdcard/vrbot_train.png",
                    path], capture_output=True, timeout=10)
    return path

def screenshot_base64(name="screen"):
    path = screenshot(name)
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


# ===========================================================
# CLAUDE AI — robust JSON extraction
# ===========================================================

def extract_json(text):
    """Extract JSON from Claude response — handles text before/after JSON."""
    # Try direct parse
    try:
        return json.loads(text.strip())
    except:
        pass
    # Try code block
    for pattern in [r'```json\s*(.*?)\s*```', r'```\s*(.*?)\s*```']:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except:
                pass
    # Try finding { ... } in text
    brace_start = text.find('{')
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == '{': depth += 1
            elif text[i] == '}': depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace_start:i+1])
                except:
                    break
    return None


def ask_claude(image_b64, prompt, max_tokens=1024):
    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                    {"type": "text", "text": prompt}
                ],
            }],
        )
        text = resp.content[0].text
        result = extract_json(text)
        if result is None:
            print(f"  [AI] No JSON found: {text[:150]}")
        return result
    except Exception as e:
        print(f"  [AI] Error: {e}")
        return None


# ===========================================================
# AI PROMPTS
# ===========================================================

def ai_detect_screen(image_b64):
    prompt = (
        "Viking Rise game screenshot (1280x720). What screen is this?\n"
        "Respond with JSON ONLY, no other text:\n"
        '{"screen": "TYPE", "details": "brief description"}\n\n'
        "Screen types:\n"
        "city = main city/base view with buildings and bottom toolbar\n"
        "training = troop training screen with soldier model and Train Now button\n"
        "action_menu = circular action icons floating over a building\n"
        "resource_popup = popup asking to use resources (Cancel/Use buttons)\n"
        "exit_popup = exit game confirmation (Cancel/OK)\n"
        "speedup_popup = speedup items popup (Cancel/OK)\n"
        "queue_screen = training or building queue list\n"
        "building_info = building upgrade or info panel\n"
        "profile = player profile/chief info screen\n"
        "unknown = anything else"
    )
    return ask_claude(image_b64, prompt, 200)


def ai_find_close_button(image_b64):
    prompt = (
        "Viking Rise screenshot (1280x720) has a popup or panel open.\n"
        "Find the CANCEL, CLOSE, or X button to dismiss it.\n"
        "NEVER select OK, Confirm, or Use — ONLY Cancel/Close/X.\n"
        "JSON ONLY: {\"found\": true/false, \"x\": number, \"y\": number}"
    )
    return ask_claude(image_b64, prompt, 150)


def ai_find_barracks(image_b64):
    prompt = (
        "Viking Rise city view screenshot (1280x720).\n\n"
        "I need to find a COMBAT BARRACKS building to tap on it.\n"
        "Combat barracks types: Infantry Barracks, Archer Barracks, Pikemen/Lancer Barracks.\n\n"
        "How to identify them:\n"
        "- They have small floating icons above them (sword, bow, spear/helmet icons)\n"
        "- They are wooden/stone military buildings with soldiers nearby\n"
        "- They may show a name label like 'Infantry Barracks' when visible\n\n"
        "DO NOT select these (they are NOT combat barracks):\n"
        "- Infirmary (medical cross icon)\n"
        "- Porter Barracks (cart/bag icon)\n"
        "- Academy, Wall, Tower, Storehouse\n\n"
        "Give the coordinates of the building STRUCTURE (roof/center), not floating icons.\n"
        "If you see multiple barracks, pick ANY one.\n\n"
        "JSON ONLY: {\"found\": true/false, \"building\": \"name\", \"x\": number, \"y\": number}"
    )
    return ask_claude(image_b64, prompt, 200)


def ai_find_train_icon(image_b64):
    prompt = (
        "Viking Rise screenshot (1280x720) showing action menu icons over a building.\n\n"
        "FIRST: Read the building name above the icons.\n"
        "Is it a combat barracks? (Infantry Barracks, Archer Barracks, Pikemen Barracks)\n"
        "If NOT combat barracks, set found=false.\n\n"
        "If YES, find the TRAIN icon in the circular menu (sword/troops icon, NOT info or upgrade).\n\n"
        "JSON ONLY: {\"found\": true/false, \"building_name\": \"name\", "
        "\"is_combat_barracks\": true/false, \"x\": number, \"y\": number}"
    )
    return ask_claude(image_b64, prompt, 200)


def ai_analyze_training(image_b64, target_type=None):
    type_hint = ""
    if target_type:
        type_hint = (
            "TARGET: " + target_type.upper() + " "
            "(infantry=sword/axe, lancer=spear, archer=bow). "
            "If wrong type is selected, give sidebar icon coordinates to switch.\n"
        )
    prompt = (
        "Viking Rise TRAINING screen (1280x720).\n"
        + type_hint +
        "The left sidebar has troop type icons. Active one has yellow/gold glow.\n"
        "Bottom-right has Train Now button (green=free, gold=gems).\n\n"
        "JSON ONLY: {\"current_type\": \"infantry\"|\"lancer\"|\"archer\"|\"unknown\", "
        "\"troop_name\": \"name\", \"needs_switch\": true/false, "
        "\"switch_tap\": {\"x\": N, \"y\": N} or null, "
        "\"train_button\": {\"x\": N, \"y\": N, \"type\": \"free\"|\"gems\"|\"none\"}, "
        "\"is_queue_active\": true/false}"
    )
    return ask_claude(image_b64, prompt, 300)


def ai_check_after_train(image_b64):
    prompt = (
        "Viking Rise screenshot (1280x720) after tapping Train Now button.\n"
        "What happened? Is there a resource popup? Did training start?\n"
        "JSON ONLY: {\"screen\": \"training\"|\"resource_popup\"|\"other\", "
        "\"training_started\": true/false, \"resource_popup\": true/false, "
        "\"cancel_button\": {\"x\": N, \"y\": N} or null}"
    )
    return ask_claude(image_b64, prompt, 200)


# ===========================================================
# NAVIGATION
# ===========================================================

def go_to_city():
    """Return to city view safely — no adb_back."""
    for _ in range(8):
        img = screenshot_base64("nav")
        r = ai_detect_screen(img)
        if not r:
            adb_tap(50, 50)
            time.sleep(2)
            continue

        s = r.get("screen", "unknown")
        print(f"  [nav] {s} -- {r.get('details','')[:70]}")

        if s == "city":
            return True

        if s in ("exit_popup", "speedup_popup", "resource_popup"):
            close = ai_find_close_button(img)
            if close and close.get("found"):
                adb_tap(close["x"], close["y"])
            else:
                adb_tap(350, 480)
            time.sleep(2)
        elif s == "profile":
            # Close profile — X button or tap outside
            close = ai_find_close_button(img)
            if close and close.get("found"):
                adb_tap(close["x"], close["y"])
            else:
                adb_tap(1250, 30)  # X at top-right
            time.sleep(2)
        elif s == "action_menu":
            adb_tap(50, 50)  # tap corner to dismiss
            time.sleep(1.5)
        elif s in ("training", "building_info", "queue_screen"):
            close = ai_find_close_button(img)
            if close and close.get("found"):
                adb_tap(close["x"], close["y"])
            else:
                adb_tap(1250, 30)
            time.sleep(2)
        else:
            # Unknown — try corners (safer than center!)
            adb_tap(50, 50)
            time.sleep(2)

    return False


# ===========================================================
# SCROLL PATTERNS for finding barracks
# ===========================================================

SCROLL_PATTERNS = [
    # (direction, swipe params) — scroll city to reveal different areas
    ("right", (800, 360, 400, 360)),
    ("down",  (640, 250, 640, 450)),
    ("left",  (400, 360, 800, 360)),
    ("up",    (640, 450, 640, 250)),
    ("center-reset", None),  # just try current view again
]


# ===========================================================
# OPEN TRAINING SCREEN
# ===========================================================

def open_training_screen():
    """Find barracks in city, tap it, find train icon, open training screen."""

    for attempt in range(8):
        print(f"\n  [open] Attempt {attempt+1}/8")

        img = screenshot_base64(f"open_{attempt}")
        r = ai_detect_screen(img)

        if r and r.get("screen") == "training":
            print("  [open] Already on training screen!")
            return True

        # Handle action menu
        if r and r.get("screen") == "action_menu":
            icon = ai_find_train_icon(img)
            if icon and icon.get("found") and icon.get("is_combat_barracks"):
                print(f"  [open] {icon.get('building_name')} -- train at ({icon['x']},{icon['y']})")
                adb_tap(icon["x"], icon["y"])
                time.sleep(3)
                img2 = screenshot_base64(f"after_icon_{attempt}")
                r2 = ai_detect_screen(img2)
                if r2 and r2.get("screen") == "training":
                    return True
            else:
                bname = icon.get("building_name", "?") if icon else "?"
                print(f"  [open] Not combat: {bname} -- dismissing")
            adb_tap(50, 50)
            time.sleep(2)
            continue

        # Not city? Navigate back
        if r and r.get("screen") not in ("city", "unknown"):
            go_to_city()
            time.sleep(1)
            img = screenshot_base64(f"open_{attempt}b")

        # Find barracks in city
        print("  [open] Looking for barracks...")
        barracks = ai_find_barracks(img)

        if not barracks or not barracks.get("found"):
            print("  [open] No barracks found -- scrolling...")
            # Scroll to reveal different area
            pattern = SCROLL_PATTERNS[attempt % len(SCROLL_PATTERNS)]
            if pattern[1]:
                adb_swipe(*pattern[1])
                print(f"  [open] Scrolled {pattern[0]}")
            time.sleep(2)
            continue

        bx, by = barracks["x"], barracks["y"]
        print(f"  [open] Found: {barracks.get('building')} at ({bx},{by})")

        # Tap barracks
        adb_tap(bx, by)
        time.sleep(3)

        # Check what appeared
        img2 = screenshot_base64(f"after_tap_{attempt}")
        r2 = ai_detect_screen(img2)

        if not r2:
            continue

        s2 = r2.get("screen", "unknown")

        if s2 == "training":
            print("  [open] Training screen opened!")
            return True

        if s2 == "action_menu":
            icon = ai_find_train_icon(img2)
            if icon and icon.get("found") and icon.get("is_combat_barracks"):
                print(f"  [open] Train at ({icon['x']},{icon['y']})")
                adb_tap(icon["x"], icon["y"])
                time.sleep(3)
                img3 = screenshot_base64(f"after_icon_{attempt}")
                r3 = ai_detect_screen(img3)
                if r3 and r3.get("screen") == "training":
                    return True
            else:
                bname = icon.get("building_name", "?") if icon else "?"
                print(f"  [open] Wrong building: {bname}")
                adb_tap(50, 50)
                time.sleep(2)
                continue

        if s2 == "building_info":
            # Tapped a building but got info panel — close it
            print(f"  [open] Got building_info -- closing...")
            go_to_city()
            time.sleep(1)
            continue

        if s2 == "profile":
            print("  [open] Opened profile -- closing...")
            go_to_city()
            time.sleep(1)
            continue

        # Screen didn't change — try again with scroll
        print(f"  [open] Screen after tap: {s2} -- scrolling...")
        pattern = SCROLL_PATTERNS[attempt % len(SCROLL_PATTERNS)]
        if pattern[1]:
            adb_swipe(*pattern[1])
        time.sleep(2)

    return False


# ===========================================================
# SELECT TYPE + TRAIN
# ===========================================================

def select_and_train(target_type):
    img = screenshot_base64("train_analyze")
    r = ai_analyze_training(img, target_type)

    if not r:
        return 'failed'

    print(f"  [train] Current: {r.get('current_type')} ({r.get('troop_name')})")
    print(f"  [train] Queue: {r.get('is_queue_active')}")

    # Switch type if needed
    if r.get("needs_switch") and r.get("switch_tap"):
        sx, sy = r["switch_tap"]["x"], r["switch_tap"]["y"]
        print(f"  [train] Switching to {target_type} -- tap ({sx},{sy})")
        adb_tap(sx, sy)
        time.sleep(2)
        img = screenshot_base64("after_switch")
        r = ai_analyze_training(img, target_type)
        if not r:
            return 'failed'
        print(f"  [train] Now: {r.get('current_type')} ({r.get('troop_name')})")

    btn = r.get("train_button", {})
    btn_type = btn.get("type", "none")

    if btn_type == "none":
        return 'failed'
    if btn_type == "gems":
        return 'queue_full'

    # Tap Train Now
    print(f"  [train] Train Now at ({btn['x']},{btn['y']})...")
    adb_tap(btn["x"], btn["y"])
    time.sleep(3)

    # Check result
    img2 = screenshot_base64("after_train")
    r2 = ai_check_after_train(img2)

    if not r2:
        return 'failed'

    if r2.get("resource_popup"):
        print("  [train] No resources!")
        cancel = r2.get("cancel_button")
        if cancel:
            adb_tap(cancel["x"], cancel["y"])
        else:
            close = ai_find_close_button(screenshot_base64("find_cancel"))
            if close and close.get("found"):
                adb_tap(close["x"], close["y"])
            else:
                adb_tap(350, 480)
        time.sleep(1.5)
        return 'no_resources'

    if r2.get("training_started") or r2.get("screen") == "training":
        return 'trained'

    return 'failed'


# ===========================================================
# COMMANDS
# ===========================================================

def train_single():
    print("\n" + "=" * 55)
    print("  Train Troops v2.2 (AI Vision) -- Single Train")
    print("=" * 55)
    if not open_training_screen():
        print("  FAILED: Cannot open training screen")
        return False
    result = select_and_train(TROOP_ROTATION[0])
    print(f"  Result: {result}")
    go_to_city()
    return result == 'trained'


def auto_train(rounds=1):
    print("\n" + "=" * 55)
    print(f"  VRBOT Train Troops v2.2 (AI Vision)")
    print(f"  Rotation: {' -> '.join(TROOP_ROTATION)}")
    print(f"  Rounds: {rounds}")
    print("=" * 55)

    trained = 0
    fails = 0

    for rnd in range(1, rounds + 1):
        print(f"\n--- ROUND {rnd}/{rounds} (trained: {trained}) ---")

        for troop_type in TROOP_ROTATION:
            print(f"\n  >> {troop_type.upper()}")

            if not open_training_screen():
                fails += 1
                if fails >= 3:
                    print("  3 consecutive fails -- stopping")
                    break
                go_to_city()
                time.sleep(2)
                continue

            fails = 0
            result = select_and_train(troop_type)

            if result == 'trained':
                trained += 1
                print(f"  TRAINED {troop_type}! (#{trained})")
            elif result == 'no_resources':
                print(f"  NO RESOURCES -- stopping")
                go_to_city()
                return trained
            elif result == 'queue_full':
                print(f"  Queue full -- skip")
            else:
                print(f"  Failed: {result}")
                fails += 1

            go_to_city()
            time.sleep(1)

        if fails >= 3:
            break

    go_to_city()
    print(f"\n  COMPLETE: {trained} trained")
    return trained


def test_detect():
    print("\n" + "=" * 55)
    print("  Train Troops v2.2 -- Detection Test")
    print("=" * 55)

    img = screenshot_base64("detect")

    print("\n  [1] Screen detection...")
    r = ai_detect_screen(img)
    if r:
        print(f"      Screen: {r.get('screen')}")
        print(f"      Details: {r.get('details')}")

    screen = r.get("screen") if r else "unknown"

    if screen == "city":
        print("\n  [2] Finding barracks...")
        b = ai_find_barracks(img)
        if b and b.get("found"):
            print(f"      Found: {b.get('building')} at ({b.get('x')},{b.get('y')})")
        else:
            print("      No combat barracks found in current view")

    elif screen == "training":
        print("\n  [2] Training analysis...")
        a = ai_analyze_training(img)
        if a:
            print(f"      Type: {a.get('current_type')} ({a.get('troop_name')})")
            print(f"      Queue: {a.get('is_queue_active')}")
            print(f"      Button: {a.get('train_button')}")

    elif screen == "action_menu":
        print("\n  [2] Action menu...")
        icon = ai_find_train_icon(img)
        if icon:
            print(f"      Building: {icon.get('building_name')}")
            print(f"      Combat: {icon.get('is_combat_barracks')}")
            if icon.get("found"):
                print(f"      Train: ({icon.get('x')},{icon.get('y')})")


def main():
    os.makedirs(DEBUG_DIR, exist_ok=True)
    if len(sys.argv) < 2:
        test_detect()
    elif sys.argv[1] == "train":
        train_single()
    elif sys.argv[1] == "auto":
        rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        auto_train(rounds)
    else:
        print("Usage: python test_train_troops.py [train|auto [N]]")


if __name__ == "__main__":
    main()
