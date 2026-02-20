"""
VRBOT Core Test — Tests the AI Vision engine
Run this to verify everything works before building tasks.

Usage:
  python test_core.py              # full test
  python test_core.py screen       # screen detection only
  python test_core.py nav          # navigation test
  python test_core.py find         # find_and_tap test
"""
import sys, time
from vrbot_core import Bot


def test_screenshot(bot):
    """Test 1: Can we take a screenshot?"""
    print("\n  [TEST 1] Screenshot...")
    path = bot.screenshot("test_shot")
    import os
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        print(f"    OK — saved: {path} ({os.path.getsize(path)} bytes)")
        return True
    else:
        print(f"    FAIL — file missing or empty")
        return False


def test_detect_screen(bot):
    """Test 2: Can AI detect the current screen?"""
    print("\n  [TEST 2] Screen Detection...")
    img = bot.screenshot_b64("test_detect")
    r = bot.detect_screen(img)
    if r and r.get("screen"):
        print(f"    OK — Screen: {r['screen']}")
        print(f"    Details: {r.get('details', '')[:80]}")
        return True
    else:
        print(f"    FAIL — no result")
        return False


def test_find_and_tap(bot):
    """Test 3: Can AI find something on screen?"""
    print("\n  [TEST 3] Find & Tap...")
    img = bot.screenshot_b64("test_find")
    r = bot.detect_screen(img)
    screen = r.get("screen", "unknown") if r else "unknown"

    if screen == "city":
        print("    Looking for bottom toolbar icons...")
        result = bot.ask_ai(
            "Viking Rise city view (1280x720).\n"
            "Find the BACKPACK/INVENTORY icon in the bottom-right toolbar.\n"
            "JSON ONLY: {\"found\": true/false, \"x\": number, \"y\": number}",
            img
        )
        if result and result.get("found"):
            print(f"    OK — found at ({result['x']},{result['y']})")
            print(f"    (not tapping — just testing detection)")
            return True
        else:
            print(f"    Could not find inventory icon — trying another...")
            # Try finding any icon
            result2 = bot.ask_ai(
                "Viking Rise city view (1280x720).\n"
                "Find ANY clickable icon or button visible on screen.\n"
                "JSON ONLY: {\"found\": true/false, \"description\": \"what it is\", \"x\": number, \"y\": number}",
                img
            )
            if result2 and result2.get("found"):
                print(f"    OK — found: {result2.get('description')} at ({result2['x']},{result2['y']})")
                return True
    else:
        print(f"    Screen is '{screen}', testing find on this screen...")
        result = bot.ask_ai(
            f"Viking Rise screenshot (1280x720), screen type: {screen}.\n"
            "Find ANY clickable button or icon.\n"
            "JSON ONLY: {\"found\": true/false, \"description\": \"what it is\", \"x\": number, \"y\": number}",
            img
        )
        if result and result.get("found"):
            print(f"    OK — found: {result.get('description')} at ({result['x']},{result['y']})")
            return True

    print(f"    FAIL — nothing found")
    return False


def test_close_popup(bot):
    """Test 4: Can AI find close buttons?"""
    print("\n  [TEST 4] Close Button Detection...")
    img = bot.screenshot_b64("test_close")
    r = bot.detect_screen(img)
    screen = r.get("screen", "unknown") if r else "unknown"

    if screen == "city":
        print(f"    Screen is city — no popup to close (OK)")
        return True

    result = bot.find_close_button(img)
    if result and result.get("found"):
        print(f"    OK — close button at ({result['x']},{result['y']})")
        return True
    else:
        print(f"    No close button found on '{screen}' screen")
        return screen == "city"  # OK if we're on city


def test_navigation(bot):
    """Test 5: Can we navigate to city?"""
    print("\n  [TEST 5] Navigation to City...")
    success = bot.go_to_city()
    if success:
        print(f"    OK — now on city screen")
    else:
        print(f"    FAIL — could not reach city")
    return success


def run_full_test():
    print("=" * 55)
    print("  VRBOT Core Engine Test")
    print("=" * 55)

    bot = Bot()
    results = {}

    # Test 1: Screenshot
    results["screenshot"] = test_screenshot(bot)

    if not results["screenshot"]:
        print("\n  STOP: Screenshot failed — check ADB connection")
        print("  Make sure LDPlayer is running and ADB is connected:")
        print(f"    {bot._adb.__doc__}")
        return

    # Test 2: Screen Detection
    results["detect"] = test_detect_screen(bot)

    if not results["detect"]:
        print("\n  STOP: AI detection failed — check API key")
        print("  $env:ANTHROPIC_API_KEY='sk-ant-...'")
        return

    # Test 3: Find & Tap
    results["find"] = test_find_and_tap(bot)

    # Test 4: Close Button
    results["close"] = test_close_popup(bot)

    # Test 5: Navigation
    results["nav"] = test_navigation(bot)

    # Summary
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n{'=' * 55}")
    print(f"  RESULTS: {passed}/{total} passed")
    print(f"{'=' * 55}")
    for name, ok in results.items():
        status = "OK" if ok else "FAIL"
        print(f"    {name:<15} {status}")

    if passed == total:
        print(f"\n  ALL PASSED — Core engine is ready!")
        print(f"  Next: start building task modules")
    else:
        print(f"\n  Some tests failed — fix before proceeding")


def run_screen_test():
    print("  Screen Detection Test")
    bot = Bot()
    test_detect_screen(bot)


def run_nav_test():
    print("  Navigation Test")
    bot = Bot()
    test_navigation(bot)


def run_find_test():
    print("  Find & Tap Test")
    bot = Bot()
    test_find_and_tap(bot)


def main():
    if len(sys.argv) < 2:
        run_full_test()
    elif sys.argv[1] == "screen":
        run_screen_test()
    elif sys.argv[1] == "nav":
        run_nav_test()
    elif sys.argv[1] == "find":
        run_find_test()
    else:
        print("Usage: python test_core.py [screen|nav|find]")


if __name__ == "__main__":
    main()
