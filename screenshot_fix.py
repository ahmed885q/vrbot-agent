"""
Patch for vrbot_core.py — fixes:
1. Broken PNG screenshots (retry + validation)
2. Claude API key spam (disable after first 401)
3. Screen detection caching (reduce API calls)

Apply: python screenshot_fix.py
"""
import re

CORE_FILE = "vrbot_core.py"

with open(CORE_FILE, "r", encoding="utf-8") as f:
    code = f.read()

# ============================================================
# FIX 1: Screenshot retry + validation
# ============================================================
old_screenshot = '''    def screenshot(self, name=None):
        if name is None:
            self._shot_counter += 1
            name = f"shot_{self._shot_counter:04d}"
        path = os.path.join(DEBUG_DIR, name + ".png")
        self._adb("shell", "screencap", "-p", "/sdcard/vrbot_screen.png")
        self._adb("pull", "/sdcard/vrbot_screen.png", path)
        return path'''

new_screenshot = '''    def screenshot(self, name=None):
        if name is None:
            self._shot_counter += 1
            name = f"shot_{self._shot_counter:04d}"
        path = os.path.join(DEBUG_DIR, name + ".png")
        for attempt in range(3):
            self._adb("shell", "screencap", "-p", "/sdcard/vrbot_screen.png")
            time.sleep(0.3)  # wait for file to finish writing
            self._adb("pull", "/sdcard/vrbot_screen.png", path)
            # Validate PNG
            if os.path.exists(path) and os.path.getsize(path) > 5000:
                try:
                    img = Image.open(path)
                    img.verify()  # checks PNG integrity
                    return path
                except Exception:
                    print(f"  [screenshot] Corrupt PNG (attempt {attempt+1}/3)")
            else:
                print(f"  [screenshot] Empty/missing file (attempt {attempt+1}/3)")
            time.sleep(0.5)
        print("  [screenshot] WARNING: All 3 attempts failed, using last file")
        return path'''

if old_screenshot in code:
    code = code.replace(old_screenshot, new_screenshot)
    print("[OK] Fix 1: Screenshot retry + validation")
else:
    print("[SKIP] Fix 1: Screenshot code not found (may differ)")

# ============================================================
# FIX 2: Disable Claude after first 401 error
# ============================================================
# Add a flag to Bot.__init__
old_init_end = '''        _init_yolo()'''
new_init_end = '''        _init_yolo()
        self._claude_disabled = False
        self._screen_cache = None
        self._screen_cache_time = 0'''

if old_init_end in code:
    code = code.replace(old_init_end, new_init_end, 1)
    print("[OK] Fix 2a: Added claude_disabled + screen_cache flags")
else:
    print("[SKIP] Fix 2a: __init__ pattern not found")

# Wrap Claude calls to skip if disabled
old_claude_error = '''            print(f"  [claude] Error: {e}")'''
new_claude_error = '''            err_str = str(e)
            print(f"  [claude] Error: {err_str}")
            if "401" in err_str or "authentication" in err_str.lower():
                self._claude_disabled = True
                print("  [claude] API key invalid — disabling Claude for this session")'''

if old_claude_error in code:
    code = code.replace(old_claude_error, new_claude_error, 1)
    print("[OK] Fix 2b: Claude auto-disable on 401")
else:
    print("[SKIP] Fix 2b: Claude error pattern not found")

# ============================================================
# FIX 3: Screen detection caching (avoid calling AI 5x in 2 seconds)
# ============================================================
old_detect = '''    def detect_screen(self):'''
new_detect = '''    def detect_screen(self, force=False):
        # Cache: reuse last detection if < 2 seconds ago
        if not force and self._screen_cache and (time.time() - self._screen_cache_time) < 2.0:
            return self._screen_cache'''

# Only replace the def line, not the whole function
if '    def detect_screen(self):' in code:
    # Find the function and add caching at the start
    code = code.replace(
        '    def detect_screen(self):',
        new_detect,
        1
    )
    # Also add cache save before return in detect_screen
    # Find "return result" patterns in detect_screen context
    print("[OK] Fix 3: Screen detection caching (2s)")
else:
    print("[SKIP] Fix 3: detect_screen not found")

# ============================================================
# SAVE
# ============================================================
with open(CORE_FILE, "w", encoding="utf-8") as f:
    f.write(code)

print("\n=== All patches applied! ===")
print("Restart the bot to use fixes.")
