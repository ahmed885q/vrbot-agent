"""
VRBOT Navigation Test — go_to_city
===================================
يختبر الرجوع للمدينة من أي شاشة.
شغّله وأنت في world_map أو أي شاشة ثانية.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vrbot_core import Bot

def main():
    print("=" * 50)
    print("  VRBOT Navigation Test — go_to_city")
    print("=" * 50)
    
    bot = Bot()
    
    # 1. Screenshot + detect current screen
    print("\n[1] Detecting current screen...")
    img = bot.screenshot_b64()
    screen = bot.detect_screen(img, force=True)
    if screen:
        print(f"    Current screen: {screen.get('screen', 'unknown')}")
    else:
        print("    Could not detect screen!")
    
    # 2. Test go_to_city
    print("\n[2] Running go_to_city()...")
    result = bot.go_to_city(max_attempts=10)
    
    if result:
        print("\n✅ SUCCESS — Returned to city!")
    else:
        print("\n❌ FAILED — Could not return to city")
    
    # 3. Stats
    print(f"\n[Stats] YOLO hits: {bot._yolo_hits} | AI calls: {bot._ai_calls} | Template hits: {bot._tmpl_hits}")

if __name__ == "__main__":
    main()
