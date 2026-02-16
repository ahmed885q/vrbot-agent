"""
VRBOT Auto-Build v1.1
- Fixed: city view no longer detected as construction queue
- Fixed: go_to_city no longer breaks navigation
- Added: builder busy detection (only gems = wait)
- Added: wait_for_builder to poll until construction finishes

Usage:
  python test_auto_build.py              # detect test
  python test_auto_build.py upgrade      # single upgrade
  python test_auto_build.py auto         # full loop (max 10)
  python test_auto_build.py auto 5       # full loop (max 5)
"""
import subprocess, os, sys, time
import numpy as np
from PIL import Image

# ─── Config ───
ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
ADB_DEVICE = "127.0.0.1:5555"
DEBUG_DIR = "debug_screenshots"

# ─── ADB helpers ───
def adb_tap(x, y):
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "input", "tap", str(x), str(y)],
                   capture_output=True, timeout=10)
    print(f"    tap ({x},{y})")

def adb_back():
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=10)
    print(f"    back")

def screenshot(name="screen"):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = f"{DEBUG_DIR}/{name}.png"
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "screencap", "-p",
                    "/sdcard/vrbot_build.png"], capture_output=True, timeout=10)
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "pull", "/sdcard/vrbot_build.png",
                    path], capture_output=True, timeout=10)
    return np.array(Image.open(path))


# ═══════════════════════════════════════════════
# DETECTION FUNCTIONS
# ═══════════════════════════════════════════════

def find_upgrade_bubble(arr):
    """Find green/teal upgrade bubble (⬆️).
    Returns (cx, cy) or None."""
    Y0, Y1, X0, X1 = 250, 530, 300, 1100
    region = arr[Y0:Y1, X0:X1, :3]
    r, g, b = region[:,:,0].astype(int), region[:,:,1].astype(int), region[:,:,2].astype(int)
    mask = (g > 150) & (b > 120) & (r < 80) & ((g - b) > 10) & ((g - r) > 80)
    count = int(np.sum(mask))
    if count > 80:
        coords = np.where(mask)
        top_y = Y0 + int(np.min(coords[0]))
        cy = top_y - 25
        cx = X0 + int(np.median(coords[1]))
        print(f"  [detect] Upgrade bubble: {count}px → ({cx},{cy})")
        return (cx, cy)
    print(f"  [detect] No upgrade bubble ({count}px)")
    return None


def find_upgrade_free(arr):
    """Find blue 'Upgrade' button (FREE). Returns (cx, cy) or None."""
    region = arr[555:610, 1040:1250, :3]
    mask = (region[:,:,2].astype(int) > 110) & (region[:,:,0].astype(int) < 55) & \
           (region[:,:,1].astype(int) > 65) & (region[:,:,1].astype(int) < 130)
    count = int(np.sum(mask))
    if count > 300:
        coords = np.where(mask)
        cy = 555 + int(np.median(coords[0]))
        cx = 1040 + int(np.median(coords[1]))
        print(f"  [detect] 'Upgrade' (free): {count}px at ({cx},{cy}) ✅")
        return (cx, cy)
    return None


def find_upgrade_gems(arr):
    """Find golden 'Upgrade Now' button (GEMS). Returns (cx, cy) or None."""
    region = arr[520:615, 740:1200, :3]
    mask = (region[:,:,0].astype(int) > 140) & (region[:,:,1].astype(int) > 90) & \
           (region[:,:,1].astype(int) < 160) & (region[:,:,2].astype(int) < 70)
    count = int(np.sum(mask))
    if count > 300:
        coords = np.where(mask)
        cy = 520 + int(np.median(coords[0]))
        cx = 740 + int(np.median(coords[1]))
        print(f"  [detect] 'Upgrade Now' (gems): {count}px at ({cx},{cy}) ⚠️")
        return (cx, cy)
    return None


def find_go_button(arr):
    """Find blue 'Go' button (prerequisite). 
    Can be at center-bottom OR right-bottom depending on layout.
    Returns (cx, cy) or None."""
    
    # Scan wider area: x=850-1270, y=580-640
    region = arr[580:640, 850:1270, :3]
    mask = (region[:,:,2].astype(int) > 110) & (region[:,:,0].astype(int) < 60) & \
           (region[:,:,1].astype(int) > 70) & (region[:,:,1].astype(int) < 130)
    count = int(np.sum(mask))
    if count > 200:
        coords = np.where(mask)
        cy = 580 + int(np.median(coords[0]))
        cx = 850 + int(np.median(coords[1]))
        print(f"  [detect] 'Go' button: {count}px at ({cx},{cy})")
        return (cx, cy)
    return None


def is_building_info_screen(arr):
    """Building info screen: dark header bar + gray content area.
    OR: large gray area covering right side (alternate layout)."""
    # Method 1: Dark header + gray content
    h = arr[60:90, 200:800, :3]
    dark = np.sum((h[:,:,0] < 80) & (h[:,:,1] < 80) & (h[:,:,2] < 80)) / h[:,:,0].size * 100
    c = arr[200:400, 700:1200, :3]
    gray = np.sum((c[:,:,0] > 170) & (c[:,:,1] > 170) & (c[:,:,2] > 170)) / c[:,:,0].size * 100
    if dark > 60 and gray > 30:
        return True
    
    # Method 2: Large gray area on right side (covers different zoom levels)
    c2 = arr[100:500, 600:1250, :3]
    gray2 = np.sum((c2[:,:,0] > 170) & (c2[:,:,1] > 170) & (c2[:,:,2] > 170)) / c2[:,:,0].size * 100
    if gray2 > 15:
        # Also verify: must have golden OR blue buttons at bottom
        btn_area = arr[520:620, 700:1260, :3]
        gold = np.sum((btn_area[:,:,0] > 140) & (btn_area[:,:,1] > 90) & (btn_area[:,:,2] < 70)) / btn_area[:,:,0].size * 100
        blue = np.sum((btn_area[:,:,2] > 110) & (btn_area[:,:,0] < 60)) / btn_area[:,:,0].size * 100
        if gold > 2 or blue > 2:
            return True
    
    return False


def is_construction_queue(arr):
    """Construction queue screen: has BOTH dark header AND light gray background.
    City view has dark sky but NO gray background."""
    # Dark header
    h = arr[0:30, 200:600, :3]
    dark = np.sum((h[:,:,0] < 80) & (h[:,:,1] < 80) & (h[:,:,2] < 80)) / h[:,:,0].size * 100
    # Light/gray content area (queue has gray boxes)
    c = arr[100:200, 300:800, :3]
    light = np.sum((c[:,:,0] > 180) & (c[:,:,1] > 180) & (c[:,:,2] > 180)) / c[:,:,0].size * 100
    return dark > 40 and light > 20


def is_city_view(arr):
    """Check if in city view — toolbar icons at bottom-right."""
    # Bottom-right has 5 toolbar icons (dark circles)
    region = arr[630:680, 980:1260, :3]
    dark = np.sum((region[:,:,0] < 80) & (region[:,:,1] < 80) & (region[:,:,2] < 80)) / region[:,:,0].size * 100
    return dark > 20


def detect_screen(arr):
    """Detect current screen type."""
    if is_building_info_screen(arr):
        return "info"
    if is_construction_queue(arr):
        return "queue"
    return "city"


# ═══════════════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════════════

def go_to_city():
    """Close any open screen and return to city view."""
    for _ in range(3):
        arr = screenshot("nav")
        screen = detect_screen(arr)
        if screen == "city":
            return True
        elif screen == "info":
            print("  [nav] Closing info screen...")
            adb_tap(1230, 75)  # X button
            time.sleep(1.5)
        elif screen == "queue":
            print("  [nav] Closing queue...")
            adb_back()
            time.sleep(1.5)
    return True


def tap_empty():
    """Tap empty area to dismiss popups / deselect."""
    adb_tap(200, 200)
    time.sleep(1)


# ═══════════════════════════════════════════════
# CORE: OPEN INFO + UPGRADE
# ═══════════════════════════════════════════════

def open_building_info(max_retries=3):
    """Find upgrade bubble → tap → open building info screen.
    Returns True if info screen opened."""
    
    for attempt in range(1, max_retries + 1):
        arr = screenshot(f"bubble_{attempt}")
        screen = detect_screen(arr)
        
        # If already on info screen, we're good
        if screen == "info":
            return True
        
        # If on queue, close it first
        if screen == "queue":
            adb_back()
            time.sleep(2)
            arr = screenshot(f"bubble_{attempt}b")
        
        bubble = find_upgrade_bubble(arr)
        
        if not bubble and attempt == 1:
            # Try tapping Chief's Hall area
            print("  [build] No bubble — tapping city center...")
            adb_tap(640, 350)
            time.sleep(2)
            arr = screenshot(f"bubble_{attempt}c")
            bubble = find_upgrade_bubble(arr)
        
        if bubble:
            adb_tap(bubble[0], bubble[1])
            time.sleep(3)
            arr2 = screenshot(f"after_bubble_{attempt}")
            if is_building_info_screen(arr2):
                return True
            # Wrong screen — try again
            screen2 = detect_screen(arr2)
            if screen2 == "queue":
                adb_back()
                time.sleep(2)
    
    return False


def try_upgrade():
    """On building info screen, try to upgrade.
    Returns: 'upgraded' | 'go' | 'builder_busy' | 'no_resources' | 'failed'"""
    
    arr = screenshot("upgrade")
    if not is_building_info_screen(arr):
        return 'failed'
    
    # 1. Free Upgrade (blue, right side)
    btn = find_upgrade_free(arr)
    if btn:
        adb_tap(btn[0], btn[1])
        time.sleep(3)
        arr2 = screenshot("after_upgrade")
        if not is_building_info_screen(arr2):
            return 'upgraded'
        return 'failed'
    
    # 2. Go button (prerequisite needed)
    btn = find_go_button(arr)
    if btn:
        print("  → Prerequisite needed, tapping Go...")
        adb_tap(btn[0], btn[1])
        time.sleep(3)
        return 'go'
    
    # 3. Only gems button = builder is busy
    btn = find_upgrade_gems(arr)
    if btn:
        # Check if there's NO free button — means builder busy
        print("  → Only gem upgrade available → builder is busy!")
        return 'builder_busy'
    
    return 'failed'


def wait_for_builder(max_wait=600, check_interval=30):
    """Wait until builder finishes current construction.
    Polls every check_interval seconds, max max_wait total."""
    
    print(f"\n  ⏳ Waiting for builder (check every {check_interval}s, max {max_wait}s)...")
    
    start = time.time()
    while time.time() - start < max_wait:
        elapsed = int(time.time() - start)
        print(f"  ... {elapsed}s elapsed")
        time.sleep(check_interval)
        
        # Go to city, tap building, check if Upgrade (free) is now available
        go_to_city()
        time.sleep(1)
        
        if open_building_info():
            arr = screenshot("wait_check")
            btn = find_upgrade_free(arr)
            if btn:
                print("  ✅ Builder is free!")
                return True
            # Still busy — close and wait more
            adb_tap(1230, 75)
            time.sleep(1)
    
    print(f"  ⏰ Timeout after {max_wait}s")
    return False


# ═══════════════════════════════════════════════
# FULL AUTO-BUILD LOOP
# ═══════════════════════════════════════════════

def auto_build(max_upgrades=10):
    """Full auto-build loop."""
    
    print("\n" + "=" * 55)
    print(f"  VRBOT Auto-Build v1.1 — max {max_upgrades} upgrades")
    print("=" * 55)
    
    upgrades = 0
    fails = 0
    
    for cycle in range(1, max_upgrades + 1):
        print(f"\n{'─' * 55}")
        print(f"  CYCLE {cycle}/{max_upgrades}  (done: {upgrades})")
        print(f"{'─' * 55}")
        
        # Step 0: Ensure city view
        go_to_city()
        time.sleep(1)
        
        # Step 1: Open building info
        print("\n  [1] Opening building info...")
        if not open_building_info():
            print("  ❌ Cannot open building info")
            fails += 1
            if fails >= 3:
                print("  ⛔ 3 fails — stopping")
                break
            tap_empty()
            time.sleep(2)
            continue
        
        fails = 0
        
        # Step 2: Try upgrade
        print("\n  [2] Trying upgrade...")
        result = try_upgrade()
        
        if result == 'upgraded':
            upgrades += 1
            print(f"\n  🎉 Upgrade #{upgrades} complete!")
            time.sleep(3)
            tap_empty()
            time.sleep(2)
            continue
        
        elif result == 'go':
            # Follow prerequisite chain
            print("\n  [3] Following prerequisite...")
            
            for depth in range(3):
                time.sleep(2)
                arr = screenshot(f"prereq_{depth}")
                
                bubble = find_upgrade_bubble(arr)
                if not bubble:
                    adb_tap(640, 400)
                    time.sleep(2)
                    arr = screenshot(f"prereq_{depth}b")
                    bubble = find_upgrade_bubble(arr)
                
                if not bubble:
                    print(f"  → No bubble at depth {depth}")
                    break
                
                adb_tap(bubble[0], bubble[1])
                time.sleep(3)
                
                arr2 = screenshot(f"prereq_info_{depth}")
                if not is_building_info_screen(arr2):
                    if is_construction_queue(arr2):
                        adb_back()
                        time.sleep(2)
                    break
                
                r2 = try_upgrade()
                
                if r2 == 'upgraded':
                    upgrades += 1
                    print(f"\n  🎉 Prerequisite #{upgrades} upgraded! (depth {depth})")
                    time.sleep(3)
                    tap_empty()
                    time.sleep(2)
                    break
                elif r2 == 'go':
                    print(f"  → Deeper prerequisite (depth {depth+1})...")
                    continue
                elif r2 == 'builder_busy':
                    print("  → Builder busy on prerequisite")
                    adb_tap(1230, 75)  # close info
                    time.sleep(1)
                    
                    # Wait for builder then retry
                    if wait_for_builder(max_wait=300):
                        continue  # retry this depth
                    break
                else:
                    print(f"  → Failed: {r2}")
                    adb_tap(1230, 75)
                    time.sleep(1)
                    break
            continue
        
        elif result == 'builder_busy':
            print("\n  ⏳ Builder is busy — waiting...")
            adb_tap(1230, 75)  # close info
            time.sleep(1)
            
            if wait_for_builder(max_wait=300):
                # Builder free — retry this cycle
                continue
            else:
                print("  → Timeout waiting for builder")
                break
        
        elif result == 'no_resources':
            print("\n  💰 Not enough resources — stopping")
            adb_tap(1230, 75)
            break
        
        else:
            print(f"\n  ⚠️ Failed: {result}")
            adb_tap(1230, 75)
            time.sleep(1)
            fails += 1
            if fails >= 3:
                print("  ⛔ 3 fails — stopping")
                break
            continue
    
    print(f"\n{'=' * 55}")
    print(f"  AUTO-BUILD COMPLETE — {upgrades} upgrades")
    print(f"{'=' * 55}")
    return upgrades


# ═══════════════════════════════════════════════
# SINGLE UPGRADE + DETECT
# ═══════════════════════════════════════════════

def test_upgrade():
    """Single upgrade test."""
    print("\n" + "=" * 50)
    print("  Auto-Build — Single Upgrade")
    print("=" * 50)
    
    if not open_building_info():
        print("  ❌ Cannot open building info")
        return False
    
    result = try_upgrade()
    print(f"  Result: {result}")
    return result == 'upgraded'


def test_detect():
    """Detection test."""
    print("\n" + "=" * 50)
    print("  Auto-Build Detection Test")
    print("=" * 50)
    
    arr = screenshot("detect")
    print(f"  Size: {arr.shape[1]}x{arr.shape[0]}")
    
    screen = detect_screen(arr)
    print(f"\n  Screen: {screen}")
    
    print("\n  Elements:")
    find_upgrade_bubble(arr)
    find_upgrade_free(arr)
    find_upgrade_gems(arr)
    find_go_button(arr)


def main():
    os.makedirs(DEBUG_DIR, exist_ok=True)
    
    if len(sys.argv) < 2:
        test_detect()
    elif sys.argv[1] == "upgrade":
        test_upgrade()
    elif sys.argv[1] == "auto":
        max_up = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        auto_build(max_up)
    else:
        print("Usage: python test_auto_build.py [upgrade|auto [N]]")


if __name__ == "__main__":
    main()
