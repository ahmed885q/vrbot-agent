"""
VRBOT Agent — Test Gather Resources
Run this on Windows with LDPlayer running Viking Rise.

Usage:
  python test_gather.py              # Default: gather stone
  python test_gather.py food         # Gather food (farm)
  python test_gather.py wood         # Gather wood (sawmill)
  python test_gather.py stone        # Gather stone (quarry)
  python test_gather.py gold         # Gather gold (gold mine)
  python test_gather.py --dry-run    # Show what it would do without tapping
"""
import sys
import os
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("vrbot.test")

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    import cv2

    # Parse args
    resource_type = "stone"
    dry_run = False
    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            dry_run = True
        elif arg in ("food", "wood", "stone", "gold"):
            resource_type = arg

    print("=" * 55)
    print(f"  VRBOT — Gather Test: {resource_type.upper()}")
    print(f"  Dry Run: {dry_run}")
    print("=" * 55)

    # ─── Step 1: Connect ADB ──────────────────────────────
    from adb.controller import ADBController
    from ocr.vision import Vision
    from antiban.humanizer import Humanizer
    from game_nav import GameNavigator, RESOURCE_TILES

    adb = ADBController(host="127.0.0.1", port=5555)
    print("\n[1/7] Connecting to LDPlayer...")

    if not adb.connect():
        print("❌ Cannot connect to LDPlayer! Make sure it's running.")
        return False

    print(f"  ✅ Connected: {adb.device} ({adb.screen_width}x{adb.screen_height})")

    # ─── Step 2: Init Vision ──────────────────────────────
    print("\n[2/7] Loading templates...")
    vision = Vision(adb, config={
        "template_threshold": 0.80,
        "multi_scale": False,  # Same resolution = no need for multi-scale
    })
    count = vision.load_all_templates()
    print(f"  ✅ Loaded {count} templates")

    # ─── Step 3: Init Humanizer + Navigator ───────────────
    human = Humanizer()
    nav = GameNavigator(vision, adb, human)

    # ─── Step 4: Detect Current Screen ────────────────────
    print("\n[3/7] Detecting current screen...")
    screen = nav.detect_screen()
    print(f"  📍 Current screen: {screen}")

    if screen == "unknown":
        print("  ⚠️  Unknown screen — trying to find city/map markers...")
        # Take a debug screenshot
        vision.save_debug_screenshot("unknown_screen")
        # Try detecting what templates match
        vision.capture(fresh=True)
        matches = []
        for name, tpl in vision._template_cache.items():
            result = vision.find(name, threshold=0.75)
            if result:
                matches.append((name, result[2]))
        matches.sort(key=lambda x: -x[1])
        if matches:
            print(f"  Found {len(matches)} templates on screen:")
            for n, c in matches[:10]:
                print(f"    {c:.1%} — {n}")
        else:
            print("  No templates matched! Check if game is open.")
            return False

    # ─── Step 5: Navigate to World Map ────────────────────
    print("\n[4/7] Navigating to world map...")

    if screen == "city":
        print("  On city screen — opening world map...")
        if not dry_run:
            # Tap compass button (bottom-left)
            if vision.tap_on("btn_compass", timeout=5):
                time.sleep(2)
                screen = nav.detect_screen()
                print(f"  📍 Now on: {screen}")
            else:
                print("  ⚠️  Compass button not found")
    elif screen == "world_map":
        print("  ✅ Already on world map")
    else:
        print(f"  Going to city first...")
        if not dry_run:
            nav.go_to_city()
            time.sleep(1)
            if vision.tap_on("btn_compass", timeout=5):
                time.sleep(2)

    # ─── Step 6: Open Search → Select Resource ────────────
    print(f"\n[5/7] Opening search panel → selecting {resource_type}...")

    tile_template = RESOURCE_TILES.get(resource_type)
    if not tile_template:
        print(f"  ❌ Unknown resource: {resource_type}")
        return False

    if not dry_run:
        # Tap the search icon on world map
        if vision.tap_on("btn_worldmap_search", timeout=5):
            time.sleep(1.5)
            print("  ✅ Search panel opened")

            # Check if search panel is visible
            if vision.exists(tile_template, threshold=0.75):
                print(f"  Found {tile_template} tile — tapping...")
                vision.tap_on(tile_template, timeout=3)
                time.sleep(1)

                # Tap the "Search" button
                print("  Tapping Search button...")
                if vision.tap_on("btn_search_blue", timeout=3) or \
                   vision.tap_on("btn_search_conquest", timeout=3):
                    time.sleep(2)
                    print("  ✅ Searching for resource...")
                else:
                    print("  ⚠️  Search button not found")
            else:
                print(f"  ⚠️  Tile {tile_template} not visible")
        else:
            print("  ⚠️  Search icon not found on world map")
    else:
        print(f"  [DRY RUN] Would tap: btn_worldmap_search → {tile_template} → btn_search_blue")

    # ─── Step 7: Find & Tap Gather ────────────────────────
    print(f"\n[6/7] Looking for resource tile to gather...")

    if not dry_run:
        time.sleep(2)
        # After search, we should see a resource tile on the map
        # The game auto-navigates to nearest tile
        # Now tap the resource tile on the map
        vision.capture(fresh=True)

        # Try to find the Gather button (it appears after tapping a tile)
        # First, tap center of screen where resource should appear
        print("  Tapping resource tile on map...")
        adb.tap(640, 400, offset=20)
        time.sleep(1.5)

        # Now look for Gather button in popup
        gather_result = vision.find("btn_gather", threshold=0.75)
        if gather_result:
            x, y, conf = gather_result
            print(f"  ✅ Gather button found at ({x}, {y}) conf={conf:.1%}")
            print("  Tapping Gather...")
            adb.tap(x, y, offset=5)
            time.sleep(1)

            # Check for troop selection / march confirm
            # Usually there's a "March" or confirm button
            print("  Looking for March/Confirm button...")
            time.sleep(1)
            vision.capture(fresh=True)

            # Try tapping march/confirm areas
            march_found = False
            for btn_name in ["btn_ok_green", "btn_claim_green"]:
                if vision.exists(btn_name, threshold=0.70):
                    vision.tap_on(btn_name, wait=False)
                    march_found = True
                    break

            if not march_found:
                # The march button might be at a standard position
                # Usually bottom-right of the troop selection screen
                print("  Looking for any green/blue button...")
                # Check for green button color in bottom area
                green_pos = vision.find_color_region(
                    (120, 200, 50),  # Green button BGR
                    tolerance=40,
                    region=(400, 500, 480, 200)  # Bottom center area
                )
                if green_pos:
                    print(f"  Found green button at {green_pos}")
                    adb.tap(green_pos[0], green_pos[1], offset=5)

            print("  ✅ Gather command sent!")
        else:
            print("  ⚠️  Gather button not found")
            print("  Trying alternate: look for resource popup...")
            # Save debug screenshot
            vision.save_debug_screenshot("no_gather")

            # Try finding the popup
            popup = vision.find("popup_resource_point", threshold=0.70)
            if popup:
                print(f"  Found resource popup at ({popup[0]}, {popup[1]})")
            else:
                print("  No resource popup found either")
    else:
        print("  [DRY RUN] Would tap resource tile → Gather → March")

    # ─── Summary ──────────────────────────────────────────
    print(f"\n[7/7] Final state...")
    if not dry_run:
        time.sleep(2)
        screen = nav.detect_screen()
        print(f"  📍 Screen: {screen}")
        vision.save_debug_screenshot(f"gather_{resource_type}_final")
        print(f"  📸 Debug screenshot saved to screenshots/")

    print("\n" + "=" * 55)
    print("  Gather test complete!")
    print("  Check screenshots/ folder for debug images")
    print("=" * 55)
    return True


if __name__ == "__main__":
    main()
