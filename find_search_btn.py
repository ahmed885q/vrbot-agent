"""Find the exact Monster Search button coordinate.
Usage: python find_search_btn.py
"""
import subprocess, time, sys, os
from PIL import Image
import io

ADB = "adb"
DEVICE = "127.0.0.1:5555"  # LDPlayer game device

def run_adb(args, timeout=15):
    cmd = [ADB, "-s", DEVICE] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout)

def tap(x, y):
    run_adb(["shell", f"input tap {x} {y}"])

def take_screenshot(filename):
    r = run_adb(["exec-out", "screencap", "-p"])
    if len(r.stdout) < 1000:
        return None
    img = Image.open(io.BytesIO(r.stdout))
    img.save(filename)
    return img

def find_blue_button(img):
    w, h = img.size
    pixels = img.load()
    blue_pixels = []
    for y in range(300, 500):
        for x in range(50, 500):
            r, g, b = pixels[x, y][:3]
            if b > 150 and r < 100 and g < 130 and (b - r) > 80:
                blue_pixels.append((x, y))
    if not blue_pixels:
        return None, None
    xs = [p[0] for p in blue_pixels]
    ys = [p[1] for p in blue_pixels]
    return (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2

print("=" * 50)
print("MONSTER SEARCH BUTTON FINDER")
print("=" * 50)

# Test connection
print(f"\nUsing device: {DEVICE}")
img_test = take_screenshot("test.png")
if img_test is None:
    print("Screenshot failed!")
    sys.exit(1)
print(f"Screenshot OK: {img_test.size[0]}x{img_test.size[1]}")

# Navigate
print("\n[1] Going to city...")
tap(47, 643)
time.sleep(3)

print("[2] Going to world map...")
tap(47, 643)
time.sleep(3)

img0 = take_screenshot("step0_worldmap.png")
print(f"    Saved step0_worldmap.png")

# Open search panel
print("\n[3] Tapping magnify (155, 525)...")
tap(155, 525)
time.sleep(3)

# Select Monster
print("[4] Tapping Monster category (200, 640)...")
tap(200, 640)
time.sleep(2)

# Screenshot with panel open
img1 = take_screenshot("step1_search_panel.png")
if img1 is None:
    print("ERROR: Screenshot failed!")
    sys.exit(1)
print(f"    Saved step1_search_panel.png ({img1.size[0]}x{img1.size[1]})")

# Detect blue button
print("\n[5] Detecting blue Search button...")
cx, cy = find_blue_button(img1)

if cx and cy:
    print(f"\n{'=' * 50}")
    print(f"  SEARCH BUTTON FOUND AT: ({cx}, {cy})")
    print(f"{'=' * 50}")
    print(f"\n  MONSTER_SEARCH = ({cx}, {cy})")
else:
    print("\n[!] Could not auto-detect.")
    print("    Upload step1_search_panel.png to Claude.")

# Scan boundaries
print("\n[6] Scanning button area...")
pixels = img1.load()
for test_y in range(380, 450, 5):
    row = ""
    for test_x in range(100, 450, 10):
        r, g, b = pixels[test_x, test_y][:3]
        if b > 150 and r < 100 and (b - r) > 80:
            row += "B"
        else:
            row += "."
    print(f"  y={test_y}: {row}")

print(f"\nDone! Files in: {os.getcwd()}")
