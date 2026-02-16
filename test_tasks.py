"""
VRBOT Agent — Test Suite
Tests all core systems: ADB, Vision, Navigation, Tasks.

Usage:
  python test_tasks.py                # Run all tests
  python test_tasks.py screen         # Test screen detection only
  python test_tasks.py templates      # Test template matching only
  python test_tasks.py nav            # Test navigation only
  python test_tasks.py daily          # Test daily quests task
  python test_tasks.py mail           # Test mail collection
  python test_tasks.py tribe          # Test tribe assist/donate
  python test_tasks.py gather         # Test gather resources (farm x1)
  python test_tasks.py gather:sawmill # Gather specific resource
  python test_tasks.py gather:quarry  # Options: farm/sawmill/quarry/goldmine
  python test_tasks.py gatherx5       # Send 5 farm marches
  python test_tasks.py gatherx5:sawmill  # Send 5 sawmill marches
  python test_tasks.py gatherall   # 1 farm + 1 sawmill + 1 quarry + 2 goldmine
"""
import sys
import os
import time
import logging
import subprocess
import traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("vrbot.test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
ADB_DEVICE = "127.0.0.1:5555"


def adb_tap(x, y, offset=2):
    """Direct ADB tap with device specified (avoids 'more than one device' error)."""
    import random
    rx = x + random.randint(-offset, offset)
    ry = y + random.randint(-offset, offset)
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "input", "tap", str(rx), str(ry)],
                   capture_output=True, timeout=5)


def adb_tap_long(x, y, duration_ms=150, offset=2):
    """Longer press via ADB swipe (same start/end point).
    Some game buttons don't register instant taps — this simulates a ~150ms press."""
    import random
    rx = x + random.randint(-offset, offset)
    ry = y + random.randint(-offset, offset)
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "input", "swipe",
                    str(rx), str(ry), str(rx), str(ry), str(duration_ms)],
                   capture_output=True, timeout=5)


def adb_back():
    """Send back key via ADB."""
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=5)


def adb_screenshot_save(path):
    """Save current screen as PNG for debugging."""
    try:
        result = subprocess.run(
            [ADB_EXE, "-s", ADB_DEVICE, "shell", "screencap", "-p"],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            # Fix line endings (ADB on Windows adds \r\n)
            data = result.stdout.replace(b'\r\n', b'\n')
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            with open(path, 'wb') as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"  ⚠️  Screenshot save failed: {e}")
    return False


def has_red_attack_button():
    """Check if a red Attack button is visible in the right-side panel.
    Uses ADB pull method to avoid binary corruption on Windows.
    Returns (cx, cy) center of red button, or None."""
    try:
        from PIL import Image
        import numpy as np
        os.makedirs("debug_screenshots", exist_ok=True)
        # Pull screenshot via file (avoids \r\n corruption)
        subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "screencap", "-p",
                        "/sdcard/vrbot_check.png"], capture_output=True, timeout=10)
        result = subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "pull", "/sdcard/vrbot_check.png",
                        "debug_screenshots/_check.png"], capture_output=True, timeout=10)
        if not os.path.exists("debug_screenshots/_check.png"):
            print("    [pixel] Screenshot pull failed!")
            return None
        img = Image.open("debug_screenshots/_check.png")
        arr = np.array(img)
        print(f"    [pixel] Screenshot: {arr.shape}")
        # Scan for red Attack button — CORRECTED region from debug analysis
        # Actual button center: (949, 467) measured from 05_popup_state screenshot
        # Button colors: R=110-144, G=27-38, B=36-44 (dark red/maroon)
        # Scan wide area to catch button regardless of panel position
        Y1, Y2, X1, X2 = 420, 510, 830, 1080
        region = arr[Y1:Y2, X1:X2, :3]
        # Dark red/maroon Attack button: R > 100, G < 50, B < 55
        red_mask = (region[:, :, 0].astype(int) > 100) & \
                   (region[:, :, 1].astype(int) < 50) & \
                   (region[:, :, 2].astype(int) < 55)
        count = int(np.sum(red_mask))
        print(f"    [pixel] Red pixels found: {count} (region {X1}-{X2}, {Y1}-{Y2})")
        if count > 150:  # Substantial red cluster = Attack button visible
            coords = np.where(red_mask)
            cy = int(np.median(coords[0])) + Y1
            cx = int(np.median(coords[1])) + X1
            print(f"    [pixel] Attack button center: ({cx}, {cy})")
            return (cx, cy)
        # Below 150 = noise/residual, not a real button
    except Exception as e:
        print(f"    [pixel] Error: {e}")
    return None


def find_create_tab():
    """Detect the Create button/tab after Attack.
    
    The game shows one of two UIs after Attack:
    A) POPUP: "Create a Troop..." with blue "Create" button at ~(933, 174)
       → Clickable by ADB (y=174 is within ADB range)
    B) TAB: Small blue "Create" tab at top-right (y=35)
       → Needs pyautogui (y<60 = ADB dead zone in LDPlayer)
    
    Returns (cx, cy, method) where method is 'adb' or 'pyautogui', or None."""
    try:
        from PIL import Image
        import numpy as np
        os.makedirs("debug_screenshots", exist_ok=True)
        subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "screencap", "-p",
                        "/sdcard/vrbot_create.png"], capture_output=True, timeout=10)
        subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "pull", "/sdcard/vrbot_create.png",
                        "debug_screenshots/_create_find.png"], capture_output=True, timeout=10)
        if not os.path.exists("debug_screenshots/_create_find.png"):
            return None
        img = Image.open("debug_screenshots/_create_find.png")
        arr = np.array(img)
        
        # === CHECK A: Popup Create button (y=150-200, x=830-1050) ===
        popup_region = arr[150:200, 830:1050, :3]
        popup_mask = (
            (popup_region[:, :, 2].astype(int) > 120) &
            (popup_region[:, :, 0].astype(int) < 40) &
            (popup_region[:, :, 1].astype(int) > 80) &
            (popup_region[:, :, 1].astype(int) < 120)
        )
        popup_ct = int(np.sum(popup_mask))
        if popup_ct > 2000:
            coords = np.where(popup_mask)
            cy = 150 + int(np.median(coords[0]))
            cx = 830 + int(np.median(coords[1]))
            print(f"    [create] POPUP button found: {popup_ct}px center=({cx},{cy}) → ADB")
            return (cx, cy, 'adb')
        
        # === CHECK B: Top-right tab (y=10-55, x=1000-1280) ===
        tab_region = arr[10:55, 1000:1280, :3]
        total_pixels = tab_region.shape[0] * tab_region.shape[1]
        tab_mask = (
            (tab_region[:, :, 2].astype(int) > 110) &
            (tab_region[:, :, 0].astype(int) < 35) &
            (tab_region[:, :, 1].astype(int) > 70) &
            (tab_region[:, :, 1].astype(int) < 115)
        )
        tab_ct = int(np.sum(tab_mask))
        tab_pct = tab_ct / total_pixels * 100
        if tab_pct > 40:
            coords = np.where(tab_mask)
            cy = 10 + int(np.median(coords[0]))
            cx = 1000 + int(np.median(coords[1]))
            print(f"    [create] TAB found: {tab_pct:.1f}% center=({cx},{cy}) → pyautogui")
            return (cx, cy, 'pyautogui')
        
        # === CHECK C: Broader blue button scan (fallback) ===
        # Scan wider area for any blue button
        for y1, y2, x1, x2 in [(100, 250, 700, 1150), (0, 70, 900, 1280)]:
            scan = arr[y1:y2, x1:x2, :3]
            scan_mask = (
                (scan[:, :, 2].astype(int) > 110) &
                (scan[:, :, 0].astype(int) < 50) &
                (scan[:, :, 1].astype(int) > 70) &
                (scan[:, :, 1].astype(int) < 120)
            )
            scan_ct = int(np.sum(scan_mask))
            if scan_ct > 1500:
                coords = np.where(scan_mask)
                cy = y1 + int(np.median(coords[0]))
                cx = x1 + int(np.median(coords[1]))
                method = 'adb' if cy > 60 else 'pyautogui'
                print(f"    [create] FALLBACK found: {scan_ct}px center=({cx},{cy}) → {method}")
                return (cx, cy, method)
        
        print(f"    [create] Not found (popup={popup_ct}px, tab={tab_pct:.1f}%)")
        return None
    except Exception as e:
        print(f"    [create] Detection error: {e}")
        return None


def pyautogui_tap(game_x, game_y, clicks=1, duration_ms=100):
    """Tap using real mouse click on LDPlayer window.
    ADB taps don't register near screen edges (y<60) in LDPlayer,
    so we use pyautogui to send real Windows mouse clicks instead.
    
    Args:
        game_x, game_y: Game coordinates (1280x720 space)
        clicks: Number of clicks
        duration_ms: Hold duration in ms (not used for click, kept for API compat)
    Returns:
        True if click was sent, False on error
    """
    try:
        import pyautogui
        import ctypes
        import ctypes.wintypes
        import pygetwindow as gw
        
        pyautogui.FAILSAFE = False  # Don't abort if mouse is at corner
        
        wins = gw.getWindowsWithTitle('LDPlayer')
        if not wins:
            print("    [pyautogui] LDPlayer window not found!")
            return False
        
        win = wins[0]
        hwnd = win._hWnd
        
        # Get client area origin (screen coords) and size
        pt = ctypes.wintypes.POINT(0, 0)
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
        rc = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rc))
        
        client_w = rc.right
        client_h = rc.bottom
        
        # Map game coords → screen coords (toolbar_offset=0 confirmed)
        screen_x = pt.x + int(game_x * client_w / 1280)
        screen_y = pt.y + int(game_y * client_h / 720)
        
        print(f"    [pyautogui] game({game_x},{game_y}) → screen({screen_x},{screen_y}) client={client_w}x{client_h}")
        
        # Ensure LDPlayer is focused
        try:
            win.activate()
        except Exception:
            pass  # Sometimes raises if already focused
        import time
        time.sleep(0.5)
        
        pyautogui.click(screen_x, screen_y, clicks=clicks)
        return True
        
    except Exception as e:
        print(f"    [pyautogui] Error: {e}")
        return False


class TestRunner:
    """Runs VRBOT tests on live LDPlayer instance."""

    def __init__(self):
        self.adb = None
        self.vision = None
        self.human = None
        self.nav = None
        self.results = []

    def setup(self):
        """Initialize all systems."""
        from adb.controller import ADBController
        from ocr.vision import Vision
        from antiban.humanizer import Humanizer
        from game_nav import GameNavigator

        print("=" * 55)
        print("  VRBOT Agent — Test Suite")
        print("=" * 55)

        # Connect ADB
        print("\n[Setup] Connecting to LDPlayer...")
        self.adb = ADBController(host="127.0.0.1", port=5555)
        if not self.adb.connect():
            print("❌ Failed to connect!")
            return False
        print(f"  ✅ Connected ({self.adb.screen_width}x{self.adb.screen_height})")

        # Init Vision
        print("[Setup] Loading templates...")
        self.vision = Vision(self.adb, config={
            "template_threshold": 0.80,
            "multi_scale": False,
        })
        count = self.vision.load_all_templates()
        print(f"  ✅ {count} templates loaded")

        # Init Humanizer + Nav
        self.human = Humanizer()
        self.nav = GameNavigator(self.vision, self.adb, self.human)
        return True

    def record(self, test_name, passed, detail=""):
        """Record test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name} {detail}")
        self.results.append((test_name, passed, detail))

    # ═══════════════════════════════════════════════════════
    # TEST: Template Matching
    # ═══════════════════════════════════════════════════════

    def test_templates(self):
        """Test how many templates match current screen."""
        print("\n" + "─" * 55)
        print("  TEST: Template Matching")
        print("─" * 55)

        self.vision.capture(fresh=True)
        matched = []
        total = 0

        for name in sorted(self.vision._template_cache.keys()):
            total += 1
            result = self.vision.find(name, threshold=0.70)
            if result:
                matched.append((name, result[2], result[0], result[1]))

        matched.sort(key=lambda x: -x[1])

        print(f"\n  Matched: {len(matched)}/{total} templates (>70%)")
        print(f"  {'Template':<45} {'Conf':>6} {'Position':>15}")
        print(f"  {'─'*45} {'─'*6} {'─'*15}")
        for name, conf, x, y in matched[:25]:
            print(f"  {name:<45} {conf:5.1%}  ({x:4d}, {y:4d})")

        self.record("template_matching", len(matched) >= 5,
                     f"{len(matched)} templates matched")
        return matched

    # ═══════════════════════════════════════════════════════
    # TEST: Screen Detection
    # ═══════════════════════════════════════════════════════

    def test_screen_detection(self):
        """Test screen detection system."""
        print("\n" + "─" * 55)
        print("  TEST: Screen Detection")
        print("─" * 55)

        screen = self.nav.detect_screen()
        print(f"\n  Detected: {screen}")

        self.record("screen_detection", screen != "unknown",
                     f"screen={screen}")

        self.vision.save_debug_screenshot(f"screen_{screen}")
        return screen

    # ═══════════════════════════════════════════════════════
    # TEST: Navigation
    # ═══════════════════════════════════════════════════════

    def test_navigation(self):
        """Test navigating between screens."""
        print("\n" + "─" * 55)
        print("  TEST: Navigation")
        print("─" * 55)

        # Test: Go to city
        print("\n  [Nav] Going to city...")
        city_ok = self.nav.go_to_city(timeout=10)
        self.record("nav_to_city", city_ok)
        time.sleep(1)

        # Test: Open world map
        print("  [Nav] Opening world map...")
        map_ok = self.nav.go_to_world_map(timeout=10)
        self.record("nav_to_world_map", map_ok)
        time.sleep(1)

        # Test: Back to city
        print("  [Nav] Back to city...")
        city_ok2 = self.nav.go_to_city(timeout=10)
        self.record("nav_back_to_city", city_ok2)
        time.sleep(1)

    # ═══════════════════════════════════════════════════════
    # TEST: Daily Quests
    # ═══════════════════════════════════════════════════════

    def test_daily_quests(self):
        """Test claiming daily quest rewards."""
        print("\n" + "─" * 55)
        print("  TEST: Daily Quests")
        print("─" * 55)

        print("\n  [Quest] Opening daily quests...")
        self.nav.go_to_city()
        time.sleep(1)

        self.vision.capture(fresh=True)
        dq_panel = self.vision.find("panel_daily_quests_header", threshold=0.65)
        if dq_panel and dq_panel[0] < 400:
            print(f"  Daily Quests panel already open at ({dq_panel[0]},{dq_panel[1]})")
        else:
            print("  Tapping avatar to open Daily Quests panel...")
            adb_tap(65, 100)
            time.sleep(2)
            self.vision.capture(fresh=True)
            dq_panel = self.vision.find("panel_daily_quests_header", threshold=0.60)
            if not dq_panel or dq_panel[0] > 400:
                adb_tap(60, 85)
                time.sleep(2)
                self.vision.capture(fresh=True)
                dq_panel = self.vision.find("panel_daily_quests_header", threshold=0.55)

        if dq_panel and dq_panel[0] < 400:
            print(f"  ✅ Daily Quests panel confirmed")

            claim_btn = self.vision.find("btn_quest_claim", threshold=0.70)
            if claim_btn and claim_btn[0] < 400:
                x, y, conf = claim_btn
                print(f"  ✅ Found Claim button at ({x}, {y})")
                adb_tap(x, y)
                time.sleep(1.5)
                self.record("daily_quest_claim", True, "Claim button found & tapped")
            else:
                print("  No claimable quests right now")
                self.record("daily_quest_claim", True, "No claims available")
        else:
            print("  ❌ Could not open Daily Quests panel")
            self.record("daily_quest_claim", False, "Could not open DQ panel")

        self.nav.go_to_city()

    # ═══════════════════════════════════════════════════════
    # TEST: Mail Collection
    # ═══════════════════════════════════════════════════════

    def test_mail(self):
        """Test mail reading and claiming.

        FLOW: Open mail → tap System tab → tap Read & Claim All → Back to close
        Mail icon: right side at (1235, 585)
        System tab: sidebar at (85, 200)
        Read & Claim All: bottom at (310, 658)
        """
        print("\n" + "─" * 55)
        print("  TEST: Mail Collection")
        print("─" * 55)

        print("\n  [Mail] Opening mail...")
        self.nav.go_to_city()
        time.sleep(1)

        # ── STEP 1: Open Mail (right side icon) ──
        self.vision.capture(fresh=True)
        mail_found = False
        for tpl in ["btn_open_mail", "btn_open_mail_v2"]:
            r = self.vision.find(tpl, threshold=0.65)
            if r and r[0] > 1100 and r[1] > 500 and r[1] < 640:
                print(f"  Found {tpl} at ({r[0]},{r[1]}) conf={r[2]:.2f}")
                adb_tap(r[0], r[1])
                mail_found = True
                break
        if not mail_found:
            print("  Using hardcoded mail position (1235, 585)")
            adb_tap(1235, 585)

        time.sleep(2.5)

        # ── STEP 2: Verify we're in Mail ──
        self.vision.capture(fresh=True)
        screen = self.nav.detect_screen()
        print(f"  Screen: {screen}")

        if screen == "hero":
            print("  ❌ Wrong screen — tapping back...")
            adb_tap(30, 25)
            time.sleep(1)
            self.record("mail_claim_all", False, "Opened Heroes Hall")
            self.nav.go_to_city()
            return

        print("  ✅ Mail screen opened!")

        # ── STEP 3: Tap System tab (sidebar) ──
        print("  Tapping System tab at (85, 200)...")
        adb_tap(85, 200)
        time.sleep(1.5)

        # ── STEP 4: Tap "Read & Claim All" (bottom of mail) ──
        print("  Tapping 'Read & Claim All' at (310, 658)...")
        adb_tap(310, 658)
        time.sleep(2)

        self.record("mail_claim_all", True, "System → Read & Claim All")

        # ── STEP 5: Close mail by tapping Mail icon (top-left) ──
        print("  Closing mail (tap Mail header at 30, 25)...")
        adb_tap(30, 25)
        time.sleep(1.5)
        self.nav.go_to_city()

    # ═══════════════════════════════════════════════════════
    # TEST: Tribe Actions
    # ═══════════════════════════════════════════════════════

    def test_tribe(self):
        """Test tribe assist and donate."""
        print("\n" + "─" * 55)
        print("  TEST: Tribe Actions")
        print("─" * 55)

        print("\n  [Tribe] Opening tribe...")
        self.nav.go_to_city()
        time.sleep(1)

        if self.vision.tap_on("btn_alliance", timeout=5):
            time.sleep(2)
            screen = self.nav.detect_screen()
            print(f"  Screen: {screen}")

            for btn in ["btn_tribe_assist", "btn_tribe_gifts", "btn_tribe_technology"]:
                exists = self.vision.exists(btn, threshold=0.70)
                print(f"  {btn}: {'✅ Found' if exists else '❌ Not found'}")

            print("\n  [Tribe] Opening Assist...")
            if self.vision.tap_on("btn_tribe_assist", timeout=3):
                time.sleep(1.5)
                assist_screen = self.vision.exists("btn_close_x", threshold=0.70)
                self.record("tribe_assist", assist_screen, "Assist opened")
                self.nav.close_popup()
            else:
                self.record("tribe_assist", False, "Assist button not found")

            self.nav.close_popup()
        else:
            self.record("tribe_assist", False, "Could not open tribe")

        self.nav.go_to_city()

    # ═══════════════════════════════════════════════════════
    # HELPER: Reliable World Map Navigation
    # ═══════════════════════════════════════════════════════

    def _go_to_world_map_reliable(self, max_attempts=3):
        """Navigate to world map with VERIFICATION.

        Problem: go_to_world_map() sometimes returns True while still in city.
        Fix: After tapping compass, verify by checking if compass DISAPPEARS
             (compass is only visible in city, NOT on world map).

        Compass button: (65, 655) — confirmed from diagnostics.
        """
        for attempt in range(1, max_attempts + 1):
            # Check: are we already on world map?
            self.vision.capture(fresh=True)
            compass = self.vision.find("btn_city_compass", threshold=0.85)
            if not compass:
                compass = self.vision.find("btn_compass", threshold=0.85)

            if not compass:
                # No compass found = we're likely on world map already
                print(f"    [Attempt {attempt}] No compass found → likely on world map ✅")
                return True

            # Compass visible = we're in city → tap it
            print(f"    [Attempt {attempt}] Compass at ({compass[0]},{compass[1]}) → tapping...")
            adb_tap(compass[0], compass[1])
            time.sleep(3)

            # VERIFY: compass should disappear after going to world map
            self.vision.capture(fresh=True)
            still_compass = self.vision.find("btn_city_compass", threshold=0.85)
            if not still_compass:
                still_compass = self.vision.find("btn_compass", threshold=0.85)

            if not still_compass:
                print(f"    [Attempt {attempt}] Compass gone → world map confirmed ✅")
                return True
            else:
                print(f"    [Attempt {attempt}] Still in city (compass at {still_compass[0]},{still_compass[1]})")
                # Close any popup that might have opened
                adb_back()
                time.sleep(1.5)

        print("    ❌ Failed to navigate to world map after all attempts")
        return False

    # ═══════════════════════════════════════════════════════
    # TEST: Gather Resources
    # ═══════════════════════════════════════════════════════

    def test_gather(self, resource="farm", count=1):
        """Test gathering resources from world map.

        FLOW (7 steps per march):
          1. Go to world map (with VERIFICATION)
          2. Tap magnify icon (155, 525)
          3. Select resource type from bottom bar
          4. Tap 'Search' button (555, 490) — game auto-navigates + shows popup
          5. Tap 'Gather' button (~1070, 485)
          6. Tap 'Create' button (~940, 145)
          7. Tap 'March' button (~960, 615)

        Resource positions (bottom bar in search panel, y~655):
          Farm:     (555, 655)
          Sawmill:  (725, 655)
          Quarry:   (890, 655)
          Gold Mine:(1060, 655)
        """
        RESOURCE_POS = {
            "farm":     (555, 655),
            "sawmill":  (725, 655),
            "quarry":   (890, 655),
            "goldmine": (1060, 655),
        }

        print("\n" + "─" * 55)
        print(f"  TEST: Gather Resources ({resource}) x{count}")
        print("─" * 55)

        if resource not in RESOURCE_POS:
            print(f"  ❌ Unknown resource: {resource}")
            print(f"     Valid options: {', '.join(RESOURCE_POS.keys())}")
            self.record("gather_resource", False, f"Unknown resource: {resource}")
            return

        success_count = 0

        for i in range(1, count + 1):
            print(f"\n  {'='*40}")
            print(f"  MARCH {i}/{count}")
            print(f"  {'='*40}")

            try:
                # ── STEP 1: Go to world map (with verification) ──
                print(f"\n  [Step 1/7] Going to world map...")

                # First make sure we're in city
                self.nav.go_to_city()
                time.sleep(1)

                if not self._go_to_world_map_reliable():
                    self.record(f"gather_{i}", False, "Could not navigate to world map")
                    continue

                print("  ✅ On world map!")
                time.sleep(1)

                # 📸 Save world map state
                debug_dir = "debug_screenshots"
                os.makedirs(debug_dir, exist_ok=True)
                tag = f"{resource}_{i}"
                adb_screenshot_save(f"{debug_dir}/01_world_map_{tag}.png")

                # ── STEP 2: Tap search/magnify icon ──
                print("  [Step 2/7] Tapping magnify/search icon (155, 525)...")
                adb_tap(155, 525)
                time.sleep(2)

                # 📸 Save search icon state
                adb_screenshot_save(f"{debug_dir}/02_after_magnify_{tag}.png")

                # Verify search panel opened
                self.vision.capture(fresh=True)
                search_found = self.vision.find("btn_search_resource", threshold=0.55)
                if search_found:
                    print(f"  ✅ Search panel opened")
                else:
                    print("  ⚠️  Retrying tap...")
                    adb_tap(155, 525)
                    time.sleep(2)
                    adb_screenshot_save(f"{debug_dir}/02_retry_magnify_{tag}.png")

                # ── STEP 3: Select resource type ──
                rx, ry = RESOURCE_POS[resource]
                print(f"  [Step 3/7] Selecting {resource} at ({rx}, {ry})...")
                adb_tap(rx, ry)
                time.sleep(2)

                # 📸 Save search panel state
                adb_screenshot_save(f"{debug_dir}/03_search_panel_{tag}.png")

                # ── STEP 4: Tap 'Search' blue button ──
                # CRITICAL: Search button centers on the selected tab!
                # Its X position matches the resource tab X position
                search_x = rx  # Same X as the resource tab
                search_y = 490
                print(f"  [Step 4/7] Tapping 'Search' button ({search_x}, {search_y})...")
                adb_tap(search_x, search_y)
                time.sleep(6)  # Wait for map navigation to complete

                # 📸 Save state after search navigation
                adb_screenshot_save(f"{debug_dir}/04_after_search_{tag}.png")
                print(f"  📸 Screenshots saved to {debug_dir}/")

                # ── STEP 5: Tap resource → Open Gather popup ──
                # After Search, resource appears on screen but popup may NOT auto-open
                # Need to tap ON the resource to get Gather popup
                print("  [Step 5/7] Looking for Gather button...")
                gather_found = False

                # First check if popup auto-appeared
                self.vision.capture(fresh=True)
                gather_btn = self.vision.find("btn_gather", threshold=0.85)
                if gather_btn:
                    print(f"  ✅ Found Gather at ({gather_btn[0]},{gather_btn[1]}) conf={gather_btn[2]:.2f}")
                    adb_tap(gather_btn[0], gather_btn[1])
                    gather_found = True
                else:
                    # Popup didn't auto-appear — tap resource node
                    # Resource appears at various positions after search
                    resource_taps = [
                        (640, 350, "center"),
                        (640, 300, "center-up"),
                        (640, 250, "upper"),
                        (500, 300, "left"),
                        (780, 300, "right"),
                    ]
                    for tx, ty, label in resource_taps:
                        print(f"  ⚠️  Tapping {label} ({tx},{ty})...")
                        adb_tap(tx, ty)
                        time.sleep(3)

                        # 📸 Save what we see after tapping
                        adb_screenshot_save(f"{debug_dir}/05_tap_{label}_{tag}.png")

                        self.vision.capture(fresh=True)
                        gather_btn = self.vision.find("btn_gather", threshold=0.85)
                        if gather_btn:
                            print(f"  ✅ Found Gather at ({gather_btn[0]},{gather_btn[1]}) conf={gather_btn[2]:.2f}")
                            adb_tap(gather_btn[0], gather_btn[1])
                            gather_found = True
                            break

                        # Check if we got "Open Field" (wrong tap) — close and try next
                        # Open Field has "Relocation" text — check template
                        open_field = self.vision.find("btn_relocation", threshold=0.70)
                        if open_field:
                            print("  ❌ Open Field popup — closing...")
                            adb_back()
                            time.sleep(1)

                if not gather_found:
                    print("  ❌ Could not find Gather button — SKIPPING")
                    adb_screenshot_save(f"{debug_dir}/05_FAILED_{tag}.png")
                    adb_back()
                    time.sleep(1)
                    continue

                time.sleep(3)

                # 📸 Save state after Gather
                adb_screenshot_save(f"{debug_dir}/06_after_gather_{tag}.png")

                # ── STEP 6: Tap 'Create' button ──
                print("  [Step 6/7] Looking for Create button...")
                self.vision.capture(fresh=True)

                create_btn = self.vision.find("btn_create_troop", threshold=0.70)
                if not create_btn:
                    create_btn = self.vision.find("btn_create", threshold=0.70)

                if create_btn:
                    print(f"  ✅ Found Create at ({create_btn[0]},{create_btn[1]}) conf={create_btn[2]:.2f}")
                    adb_tap(create_btn[0], create_btn[1])
                    time.sleep(3)
                else:
                    # Maybe already on CREATE SQUAD
                    squad = self.vision.find("title_create_squad", threshold=0.70)
                    if squad:
                        print("  ✅ Already on CREATE SQUAD")
                    else:
                        print("  ⚠️  Using fallback (940, 145)...")
                        adb_tap(940, 145)
                        time.sleep(3)

                # 📸 Save CREATE SQUAD state
                adb_screenshot_save(f"{debug_dir}/07_before_march_{tag}.png")

                # ── STEP 7: Tap 'March' button ──
                print("  [Step 7/7] Looking for March button...")
                self.vision.capture(fresh=True)

                march_btn = self.vision.find("btn_march", threshold=0.70)
                if march_btn and march_btn[1] > 500:
                    print(f"  ✅ Found March at ({march_btn[0]},{march_btn[1]}) conf={march_btn[2]:.2f}")
                    adb_tap(march_btn[0], march_btn[1])
                else:
                    if march_btn:
                        print(f"  ⚠️  March at ({march_btn[0]},{march_btn[1]}) — y too low, skipping")
                    print("  ⚠️  Using fallback (960, 615)...")
                    adb_tap(960, 615)
                time.sleep(4)

                # 📸 Save final state
                adb_screenshot_save(f"{debug_dir}/08_after_march_{tag}.png")

                # ── VERIFY ──
                # If we got through all 7 steps (Gather→Create→March), march succeeded.
                # Previous verification using title_create_squad gave false positives.
                print(f"  ✅ March {i}/{count} sent!")
                success_count += 1

            except Exception as e:
                print(f"\n  ❌ ERROR on march {i}: {e}")
                traceback.print_exc()

            # Small delay between marches
            if i < count:
                print(f"\n  Waiting 2s before next march...")
                time.sleep(2)

        # Record overall result
        self.record("gather_resource", success_count > 0,
                     f"{resource} x{success_count}/{count} marches sent")

        # Return to city
        try:
            self.nav.go_to_city()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════
    # TEST: Hunt Monsters (Niflung)
    # ═══════════════════════════════════════════════════════

    def _is_open_field_popup(self):
        """Detect Open Field popup WITHOUT relying on btn_relocation template.
        Uses pixel analysis: Open Field has white background panel with blue buttons."""
        try:
            from PIL import Image
            import numpy as np
            subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "screencap", "-p",
                            "/sdcard/vrbot_check.png"], capture_output=True, timeout=10)
            subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "pull", "/sdcard/vrbot_check.png",
                            "debug_screenshots/_of_check.png"], capture_output=True, timeout=10)
            img = Image.open("debug_screenshots/_of_check.png")
            arr = np.array(img)
            # Open Field popup: white panel in center-right area
            # Check region y=150-350, x=300-900 for white background
            panel_region = arr[250:400, 400:850, :3]
            avg_r = float(np.mean(panel_region[:, :, 0]))
            avg_g = float(np.mean(panel_region[:, :, 1]))
            avg_b = float(np.mean(panel_region[:, :, 2]))
            # White panel: all channels > 180
            if avg_r > 180 and avg_g > 180 and avg_b > 180:
                # Double-check: look for blue buttons (Relocation/March)
                btn_region = arr[390:440, 350:800, :3]
                btn_b = float(np.mean(btn_region[:, :, 2]))
                btn_r = float(np.mean(btn_region[:, :, 0]))
                if btn_b > 100 and btn_b > btn_r:
                    return True
        except Exception:
            pass
        return False

    def _is_shop_screen(self):
        """Detect Shop screen using pixel analysis."""
        try:
            from PIL import Image
            import numpy as np
            # Reuse the screenshot from _is_open_field_popup if recent
            if not os.path.exists("debug_screenshots/_of_check.png"):
                subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "screencap", "-p",
                                "/sdcard/vrbot_check.png"], capture_output=True, timeout=10)
                subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "pull", "/sdcard/vrbot_check.png",
                                "debug_screenshots/_of_check.png"], capture_output=True, timeout=10)
            img = Image.open("debug_screenshots/_of_check.png")
            arr = np.array(img)
            # Shop: dark blue/purple background
            top = arr[0:100, 200:1000, :3]
            avg_b = float(np.mean(top[:, :, 2]))
            avg_r = float(np.mean(top[:, :, 0]))
            if avg_b > 80 and avg_r < 60:
                return True
        except Exception:
            pass
        return False

    def _dismiss_popups(self, debug_dir="debug_screenshots", tag=""):
        """Detect and dismiss Open Field or Shop popups.
        Returns: 'open_field', 'shop', or None."""
        if self._is_open_field_popup():
            print("    ⚠️  Open Field popup → tapping away...")
            adb_screenshot_save(f"{debug_dir}/popup_openfield_{tag}.png")
            adb_tap(100, 200)
            time.sleep(2)
            return "open_field"
        if self._is_shop_screen():
            print("    ⚠️  Shop screen → closing...")
            adb_screenshot_save(f"{debug_dir}/popup_shop_{tag}.png")
            adb_tap(30, 25)
            time.sleep(2)
            return "shop"
        return None

    def test_hunt(self, monster="niflung", count=1):
        """Test hunting monsters from world map.

        v2.9 FIXES (from video35-38 analysis):
          - ROOT CAUSE FOUND: ADB input tap/swipe does NOT register at y<60 in LDPlayer!
          - Confirmed via manual testing: all 5 ADB methods failed, mouse click works.
          - FIX: Use pyautogui (real Windows mouse click) for Create tab ONLY.
          - FIX: Detect Create tab position dynamically (it moves per march direction).
          - All other steps remain ADB (works fine for y>60).
          - Attack: pixel scan at (951, 462) confirmed working 100%.
          - Create tab: pyautogui click at (1170, 35) — real mouse input.
        """
        MONSTER_POS = {
            "monster":  (210, 655),
            "niflung":  (380, 655),
        }

        print("\n" + "─" * 55)
        print(f"  TEST: Hunt {monster} x{count}")
        print("─" * 55)

        if monster not in MONSTER_POS:
            print(f"  ❌ Unknown monster: {monster}")
            self.record("hunt_monster", False, f"Unknown: {monster}")
            return

        success_count = 0

        for i in range(1, count + 1):
            print(f"\n  {'='*40}")
            print(f"  MARCH {i}/{count}")
            print(f"  {'='*40}")

            try:
                # ── STEP 1: Go to world map ──
                print(f"\n  [Step 1/8] Going to world map...")
                self.nav.go_to_city()
                time.sleep(1)

                if not self._go_to_world_map_reliable():
                    self.record(f"hunt_{i}", False, "Could not navigate to world map")
                    continue

                print("  ✅ On world map!")
                time.sleep(1)

                debug_dir = "debug_screenshots"
                os.makedirs(debug_dir, exist_ok=True)
                tag = f"hunt_{monster}_{i}"

                # ── STEP 2: Tap search/magnify icon ──
                print("  [Step 2/8] Tapping magnify/search icon (155, 525)...")
                adb_tap(155, 525)
                time.sleep(3)

                self.vision.capture(fresh=True)
                search_found = self.vision.find("btn_search_resource", threshold=0.55)
                if search_found:
                    print("  ✅ Search panel opened")
                else:
                    print("  ⚠️  Retrying (155, 525)...")
                    adb_tap(155, 525)
                    time.sleep(3)
                    self.vision.capture(fresh=True)
                    search_found = self.vision.find("btn_search_resource", threshold=0.55)
                    if not search_found:
                        print("  ❌ Search panel FAILED — SKIPPING")
                        adb_tap(400, 300)
                        time.sleep(1)
                        continue

                adb_screenshot_save(f"{debug_dir}/02_search_panel_{tag}.png")

                # ── STEP 3: Select monster type ──
                mx, my = MONSTER_POS[monster]
                print(f"  [Step 3/8] Selecting {monster} at ({mx}, {my})...")
                adb_tap(mx, my)
                time.sleep(2)

                # ── STEP 4: Tap 'Search' button ──
                print(f"  [Step 4/8] Tapping 'Search' ({mx}, 490)...")
                adb_tap(mx, 490)

                print("  ⏳ Waiting 14s for popup...")
                time.sleep(14)

                adb_screenshot_save(f"{debug_dir}/05_popup_state_{tag}.png")

                # ── STEP 5: Tap 'Attack' button ──
                # KEY FIX (v2.5): From pixel analysis of 05_popup_state screenshot,
                # Attack button center is at approximately (949, 467).
                # The button is a dark red/maroon color (R=110-144, G=27-38, B=36-44).
                # Old v2.4 was tapping (1240, 400) which is OUTSIDE the panel!                # approximately (1230, 400), NOT (1180, 400).
                # The button is in the center-right panel area: x≈880-1020, y≈445-480
                # Previous versions tapped too far LEFT and missed the button.
                print("  [Step 5/8] Tapping Attack button...")
                attack_success = False

                # ── 5a: Pixel scan for exact position ──
                attack_pos = has_red_attack_button()
                if attack_pos:
                    ax, ay = attack_pos
                    print(f"    → Pixel scan: Attack at ({ax}, {ay})")
                    adb_tap(ax, ay)
                    time.sleep(3)  # v2.6: longer wait for game transition

                    # Verify: Attack button should DISAPPEAR if tap worked
                    attack_gone = has_red_attack_button()
                    if not attack_gone:
                        print("    ✅ Attack button gone → tap worked!")
                        attack_success = True
                    else:
                        # v3.0: If pixels dropped massively (5000→45), Attack worked!
                        # Don't retry — second tap would dismiss the Create popup.
                        print("    → Some red remains — checking if Attack actually worked...")
                        time.sleep(2)
                        attack_gone2 = has_red_attack_button()
                        if not attack_gone2:
                            print("    ✅ Attack gone (residual pixels cleared)!")
                            attack_success = True
                        else:
                            # Only retry if Attack TRULY didn't work
                            print("    → Attack truly still visible, retrying...")
                            adb_tap(ax, ay)
                            time.sleep(3)
                            attack_gone3 = has_red_attack_button()
                            if not attack_gone3:
                                print("    ✅ Attack gone on retry!")
                                attack_success = True

                if not attack_success:
                    # ── 5b: Hardcoded positions — CORRECTED from pixel analysis ──
                    # Actual Attack button center: (949, 467) from debug screenshots
                    print("    → Hardcoded Attack taps (center-right panel)...")
                    attack_positions = [
                        (949, 467),   # Exact center from pixel analysis
                        (940, 462),   # Slightly left/up
                        (960, 470),   # Slightly right/down
                        (935, 455),   # Upper area
                        (955, 475),   # Lower area
                        (945, 460),   # Another center attempt
                    ]
                    for ax, ay in attack_positions:
                        adb_tap(ax, ay)
                        time.sleep(2)

                        # Check if Attack registered after each tap
                        self.vision.capture(fresh=True)
                        march_check = self.vision.find("btn_march", threshold=0.55)
                        if march_check and march_check[1] > 500:
                            print(f"    ✅ Attack registered at ({ax}, {ay})!")
                            attack_success = True
                            break

                        # Check if panel disappeared — BUT this could mean:
                        # a) Attack worked → went to Create Squad (check for march btn)
                        # b) Tap missed → closed popup (BAD — need to re-open)
                        attack_still = has_red_attack_button()
                        if not attack_still:
                            # Check if we got to Create Squad screen
                            self.vision.capture(fresh=True)
                            march_after = self.vision.find("btn_march", threshold=0.55)
                            if march_after and march_after[1] > 500:
                                print(f"    ✅ Attack worked at ({ax}, {ay}) → Create Squad!")
                                attack_success = True
                                break
                            else:
                                # Panel just closed without attacking — need to re-open
                                print(f"    ⚠️  Panel dismissed (not attacked) at ({ax}, {ay}) — re-searching...")
                                # Re-do search: magnify → niflung → search
                                adb_tap(155, 525)  # magnify
                                time.sleep(2)
                                adb_tap(380, 655)  # niflung
                                time.sleep(1)
                                adb_tap(380, 490)  # search
                                time.sleep(14)
                                break  # Will retry in step 5c

                if not attack_success:
                    # ── 5c: Tap the Niflung on map ──
                    # From video: Niflung is at approx (800-850, 220-300)
                    print("    → Tapping Niflung on map to re-open panel...")
                    for nfx, nfy in [(830, 260), (810, 240), (850, 280), (800, 220)]:
                        adb_tap(nfx, nfy)
                        time.sleep(3)

                        # Check for Open Field popup
                        if self._is_open_field_popup():
                            print(f"    ⚠️  Open Field at ({nfx},{nfy}) → dismissing...")
                            adb_tap(100, 200)
                            time.sleep(2)
                            continue

                        # Check for Attack button
                        attack_pos2 = has_red_attack_button()
                        if attack_pos2:
                            print(f"    → Found Attack at ({attack_pos2[0]}, {attack_pos2[1]})")
                            adb_tap(attack_pos2[0], attack_pos2[1])
                            time.sleep(2)
                            attack_success = True
                            break

                if not attack_success:
                    print("  ❌ Could not tap Attack — SKIPPING this march")
                    self._dismiss_popups(debug_dir, tag)
                    adb_tap(100, 200)
                    time.sleep(1)
                    continue

                adb_screenshot_save(f"{debug_dir}/06_after_attack_{tag}.png")

                # ── STEP 6: Tap 'Create' tab ──
                # v2.9 FIX: ADB input tap/swipe does NOT register at y<60 in LDPlayer.
                # Confirmed: mouse click works, ADB does not. All 5 ADB tests failed.
                # Solution: detect tab position dynamically, then pyautogui click.
                # The tab MOVES depending on march direction — cannot use fixed coords.
                print("  [Step 6/8] Tapping Create tab (pyautogui)...")

                time.sleep(4)  # Wait for Create tab animation

                adb_screenshot_save(f"{debug_dir}/06_before_create_{tag}.png")

                create_opened = False

                # Detect → Click loop (up to 5 attempts)
                for attempt in range(1, 6):
                    # Step A: Find where the Create button/tab is
                    result = find_create_tab()
                    if not result:
                        print(f"    [{attempt}/5] Create not visible — waiting 2s...")
                        time.sleep(2)
                        continue
                    
                    cx, cy, method = result
                    
                    # Step B: Click using appropriate method
                    if method == 'adb':
                        print(f"    [{attempt}/5] ADB tap ({cx},{cy})...")
                        adb_tap(cx, cy)
                    else:
                        print(f"    [{attempt}/5] pyautogui click ({cx},{cy})...")
                        if not pyautogui_tap(cx, cy):
                            print(f"    ⚠️  pyautogui failed")
                            continue
                    time.sleep(2.5)

                    # Step C: Verify — did Create Squad panel open?
                    if self._is_shop_screen():
                        print(f"    ⚠️  Shop opened → closing...")
                        adb_back()
                        time.sleep(2)
                        continue

                    self.vision.capture(fresh=True)
                    march_check = self.vision.find("btn_march", threshold=0.55)
                    if march_check and march_check[1] > 500:
                        print(f"    ✅ CREATE SQUAD opened!")
                        create_opened = True
                        break

                    if self._is_open_field_popup():
                        print(f"    ⚠️  Open Field popup → click missed tab")
                        adb_tap(100, 200)
                        time.sleep(2)
                        continue

                    # Tab might need a different spot — try offset
                    for ox, oy in [(0, 10), (30, 0), (-30, 0), (0, -10)]:
                        nx, ny = cx + ox, cy + oy
                        print(f"    [{attempt}/5] retry offset ({nx},{ny})...")
                        if method == 'adb':
                            adb_tap(nx, ny)
                        else:
                            pyautogui_tap(nx, ny)
                        time.sleep(2)
                        self.vision.capture(fresh=True)
                        march_check = self.vision.find("btn_march", threshold=0.55)
                        if march_check and march_check[1] > 500:
                            print(f"    ✅ CREATE SQUAD opened at offset ({ox},{oy})!")
                            create_opened = True
                            break
                    if create_opened:
                        break

                adb_screenshot_save(f"{debug_dir}/07_create_squad_{tag}.png")

                # ── STEP 7: Tap 'March' button ──
                print("  [Step 7/8] Looking for March button...")
                
                if not create_opened:
                    print("  ❌ Create Squad never opened — cannot March")
                    print("     SKIPPING this march (Create tab issue)")
                    adb_back()
                    time.sleep(2)
                    continue
                
                self.vision.capture(fresh=True)

                march_btn = self.vision.find("btn_march", threshold=0.55)
                if march_btn and march_btn[1] > 500:
                    print(f"  ✅ Found March at ({march_btn[0]},{march_btn[1]})")
                    adb_tap(march_btn[0], march_btn[1])
                else:
                    print("  ⚠️  March template not found, trying fallback positions...")
                    for mx, my in [(1160, 590), (1150, 600), (1170, 585)]:
                        adb_tap(mx, my)
                        time.sleep(1)
                time.sleep(3)

                adb_screenshot_save(f"{debug_dir}/08_after_march_{tag}.png")

                # ── STEP 8: Handle 'NOTE' warning popup ──
                print("  [Step 8/8] Checking for NOTE warning popup...")
                time.sleep(1)
                adb_tap_long(985, 440, duration_ms=150)
                time.sleep(2)
                adb_tap(985, 440)
                time.sleep(2)

                adb_screenshot_save(f"{debug_dir}/09_final_state_{tag}.png")

                print(f"  ✅ March {i}/{count} sent!")
                success_count += 1

            except Exception as e:
                print(f"\n  ❌ ERROR on march {i}: {e}")
                traceback.print_exc()
                try:
                    self._dismiss_popups(debug_dir, tag)
                except Exception:
                    pass
                adb_tap(100, 200)
                time.sleep(1)

            if i < count:
                print(f"\n  Waiting 3s before next march...")
                time.sleep(3)
                # Reset: close any popups, then Step 1 handles city→world map
                print("  [Reset] Clearing screen...")
                # Try to close any visible popup
                for _ in range(3):
                    self.vision.capture(fresh=True)
                    close_btn = self.vision.find("close_btn", threshold=0.55)
                    if close_btn:
                        print(f"    → Closing popup at ({close_btn[0]},{close_btn[1]})")
                        adb_tap(close_btn[0], close_btn[1])
                        time.sleep(1)
                    else:
                        break
                # Check for Open Field popup (has "Relocation"/"March" buttons)
                if self._is_open_field_popup():
                    print("    → Dismissing Open Field popup...")
                    adb_tap(50, 700)  # tap far bottom-left corner (outside popup)
                    time.sleep(1)

        self.record("hunt_monster", success_count > 0,
                     f"{monster} x{success_count}/{count} marches sent")

        try:
            self.nav.go_to_city()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════

    def print_summary(self):
        """Print test results summary."""
        print("\n" + "=" * 55)
        print("  TEST RESULTS SUMMARY")
        print("=" * 55)

        passed = sum(1 for _, p, _ in self.results if p)
        total = len(self.results)

        for name, p, detail in self.results:
            status = "✅" if p else "❌"
            print(f"  {status} {name:<30} {detail}")

        print(f"\n  Total: {passed}/{total} passed")
        pct = (passed / total * 100) if total > 0 else 0
        print(f"  Score: {pct:.0f}%")

        if total == 0:
            print("\n  ⚠️  No tests were recorded!")
        elif pct >= 80:
            print("\n  🎉 Bot is ready for automation!")
        elif pct >= 50:
            print("\n  ⚠️  Some issues — check failed tests")
        else:
            print("\n  ❌ Major issues — review template matching")

        print("=" * 55)


def main():
    runner = TestRunner()
    if not runner.setup():
        return

    # Parse which tests to run
    args = sys.argv[1:] if len(sys.argv) > 1 else ["all"]

    # Normalize: extract test names (handle gather:sawmill → gather + resource)
    tests = []
    gather_resource = "farm"  # default
    gather_count = 1  # default: 1 march
    hunt_monster = "niflung"  # default
    hunt_count = 1  # default: 1 march

    for arg in args:
        if arg.startswith("gather:"):
            # gather:sawmill
            tests.append("gather")
            gather_resource = arg.split(":", 1)[1]
        elif arg == "gatherall":
            # 1 farm + 1 sawmill + 1 quarry + 2 goldmine = 5 marches
            tests.append("gatherall")
        elif arg.startswith("gatherx"):
            # gatherx5 = farm x5 | gatherx5:sawmill = sawmill x5
            tests.append("gather")
            parts = arg.replace("gatherx", "")
            if ":" in parts:
                cnt, res = parts.split(":", 1)
                gather_count = int(cnt)
                gather_resource = res
            else:
                gather_count = int(parts)
        elif arg.startswith("hunt"):
            # hunt = niflung x1 | hunt:monster = monster x1
            # huntx3 = niflung x3 | huntx3:monster = monster x3
            tests.append("hunt")
            if arg.startswith("huntx"):
                parts = arg.replace("huntx", "")
                if ":" in parts:
                    cnt, mon = parts.split(":", 1)
                    hunt_count = int(cnt)
                    hunt_monster = mon
                else:
                    hunt_count = int(parts)
            elif ":" in arg:
                hunt_monster = arg.split(":", 1)[1]
        else:
            tests.append(arg)

    # Run tests
    try:
        if "all" in tests or "templates" in tests:
            runner.test_templates()

        if "all" in tests or "screen" in tests:
            runner.test_screen_detection()

        if "all" in tests or "nav" in tests:
            runner.test_navigation()

        if "all" in tests or "daily" in tests:
            runner.test_daily_quests()

        if "all" in tests or "mail" in tests:
            runner.test_mail()

        if "all" in tests or "tribe" in tests:
            runner.test_tribe()

        if "gather" in tests:
            runner.test_gather(gather_resource, gather_count)

        if "gatherall" in tests:
            # 1 farm + 1 sawmill + 1 quarry + 2 goldmine
            march_plan = [
                ("farm", 1),
                ("sawmill", 1),
                ("quarry", 1),
                ("goldmine", 2),
            ]
            print("\n" + "═" * 55)
            print("  GATHER ALL: 1 Farm + 1 Sawmill + 1 Quarry + 2 Gold Mine")
            print("═" * 55)
            for res, cnt in march_plan:
                runner.test_gather(res, cnt)

        if "hunt" in tests:
            runner.test_hunt(hunt_monster, hunt_count)

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        traceback.print_exc()

    runner.print_summary()


if __name__ == "__main__":
    main()
