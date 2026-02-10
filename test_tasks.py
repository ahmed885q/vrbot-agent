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
"""
import sys
import os
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("vrbot.test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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

        # Save annotated screenshot
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

        # Navigate to quests
        print("\n  [Quest] Opening daily quests...")
        self.nav.go_to_city()
        time.sleep(1)

        if self.vision.tap_on("btn_quests", timeout=5):
            time.sleep(2)
            screen = self.nav.detect_screen()
            print(f"  Screen: {screen}")

            # Look for claimable quests
            claim_btn = self.vision.find("btn_quest_claim", threshold=0.75)
            if claim_btn:
                x, y, conf = claim_btn
                print(f"  ✅ Found Claim button at ({x}, {y})")
                print("  Claiming reward...")
                self.adb.tap(x, y, offset=5)
                time.sleep(1.5)
                self.record("daily_quest_claim", True, "Claim button found & tapped")
            else:
                print("  No claimable quests right now")
                self.record("daily_quest_claim", True, "No claims available")

            # Check for chest rewards at top
            for chest in ["icon_chest_20", "icon_chest_40", "icon_chest_60"]:
                if self.vision.exists(chest, threshold=0.70):
                    print(f"  Found chest: {chest}")

            self.nav.close_popup()
        else:
            self.record("daily_quest_claim", False, "Could not open quests")

        self.nav.go_to_city()

    # ═══════════════════════════════════════════════════════
    # TEST: Mail Collection
    # ═══════════════════════════════════════════════════════

    def test_mail(self):
        """Test mail reading and claiming."""
        print("\n" + "─" * 55)
        print("  TEST: Mail Collection")
        print("─" * 55)

        print("\n  [Mail] Opening mail...")
        self.nav.go_to_city()
        time.sleep(1)

        if self.vision.tap_on("btn_mail", timeout=5):
            time.sleep(2)
            screen = self.nav.detect_screen()
            print(f"  Screen: {screen}")

            # Check for Read & Claim All
            if self.vision.exists("btn_read_claim_all", threshold=0.75):
                print("  ✅ 'Read & Claim All' button found")
                self.vision.tap_on("btn_read_claim_all", wait=False)
                time.sleep(2)
                self.record("mail_claim_all", True)
            else:
                print("  No 'Read & Claim All' button")
                self.record("mail_claim_all", True, "No claims needed")

            # Check mail tabs
            for tab in ["tab_mail_report", "tab_mail_system", "tab_mail_personal"]:
                exists = self.vision.exists(tab, threshold=0.70)
                print(f"  Tab {tab}: {'✅' if exists else '❌'}")

            self.nav.close_popup()
        else:
            self.record("mail_claim_all", False, "Could not open mail")

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

            # Check for tribe buttons
            for btn in ["btn_tribe_assist", "btn_tribe_gifts", "btn_tribe_technology"]:
                exists = self.vision.exists(btn, threshold=0.70)
                print(f"  {btn}: {'✅ Found' if exists else '❌ Not found'}")

            # Try tapping Assist
            print("\n  [Tribe] Opening Assist...")
            if self.vision.tap_on("btn_tribe_assist", timeout=3):
                time.sleep(1.5)
                # Look for assist content
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

        if pct >= 80:
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
    tests = sys.argv[1:] if len(sys.argv) > 1 else ["all"]

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

    runner.print_summary()


if __name__ == "__main__":
    main()
