"""Quick debug test - verify ADB taps work"""
import subprocess, time

ADB = r"C:\LDPlayer\LDPlayer9\adb.exe"
DEV = "127.0.0.1:5555"

def adb(*args):
    cmd = [ADB, "-s", DEV] + list(args)
    r = subprocess.run(cmd, capture_output=True, timeout=15)
    return r

def save_screen(name):
    adb("shell", "screencap", "-p", "/sdcard/vrbot_debug.png")
    adb("pull", "/sdcard/vrbot_debug.png", f"debug_screenshots/{name}.png")
    print(f"  Saved: {name}.png")

def tap(x, y):
    r = adb("shell", "input", "tap", str(x), str(y))
    print(f"  tap({x},{y}) returncode={r.returncode} stderr={r.stderr.decode().strip()}")

print("=== TEST 1: World Map (47, 643) ===")
save_screen("test_before_worldmap")
print("  Tapping world map...")
tap(47, 643)
time.sleep(3)
save_screen("test_after_worldmap")

print("\n=== TEST 2: Back to city (97, 654) ===")
tap(97, 654)
time.sleep(3)
save_screen("test_after_city")

print("\n=== TEST 3: Mail (1245, 580) ===")
tap(1245, 580)
time.sleep(3)
save_screen("test_after_mail")

print("\n=== Back to city ===")
adb("shell", "input", "keyevent", "4")
time.sleep(2)

print("\n=== TEST 4: Alliance (1100, 685) ===")
tap(1100, 685)
time.sleep(3)
save_screen("test_after_alliance")

print("\n=== DONE - check debug_screenshots/ ===")
