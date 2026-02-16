import subprocess
import time
import os

SAVE_DIR = "dataset/screenshots"
ADB_DEVICE = "emulator-5554"
TOTAL = 300
INTERVAL = 3

os.makedirs(SAVE_DIR, exist_ok=True)

print("=" * 40)
print("Start playing the game manually")
print("Screenshot every 3 seconds")
print("=" * 40)
time.sleep(3)

for i in range(TOTAL):
    filename = f"{SAVE_DIR}/screen_{i:04d}.png"
    result = subprocess.run(
        ["adb", "-s", ADB_DEVICE, "exec-out", "screencap", "-p"],
        stdout=open(filename, "wb"),
        stderr=subprocess.PIPE
    )
    if result.returncode == 0:
        size = os.path.getsize(filename)
        print(f"[{i+1}/{TOTAL}] OK - {filename} ({size//1024} KB)")
    else:
        print(f"[{i+1}/{TOTAL}] FAILED!")
    time.sleep(INTERVAL)

print(f"\nDone! {TOTAL} screenshots saved in {SAVE_DIR}")
