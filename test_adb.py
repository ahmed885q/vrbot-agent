"""VRBOT Quick ADB Test"""
import subprocess, sys, os

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except: return "Error", 1

print("\n=== VRBOT ADB Connection Test ===\n")

# Find ADB
print("1. Finding ADB...")
out, code = run("adb version")
if code != 0:
    print("   X ADB not found! Add to PATH")
    print("   LDPlayer ADB: C:\\LDPlayer\\LDPlayer9\\adb.exe")
    sys.exit(1)
print(f"   OK: {out.split(chr(10))[0]}")

# Connect
print("\n2. Connecting...")
ports = [5555, 5556, 5557, 5558, 5559]
device = None
for p in ports:
    d = f"127.0.0.1:{p}"
    out, code = run(f"adb connect {d}")
    if "connected" in out.lower():
        out2, c2 = run(f"adb -s {d} shell echo test")
        if c2 == 0:
            device = d
            print(f"   OK: {d}")
            break

if not device:
    out, _ = run("adb devices")
    lines = [l for l in out.split("\n") if "device" in l and "List" not in l]
    if lines: device = lines[0].split("\t")[0]
    else:
        print("   X No device! Start LDPlayer first")
        sys.exit(1)

# Screen
print("\n3. Screen...")
out, _ = run(f"adb -s {device} shell wm size")
print(f"   {out}")

# Screenshot
print("\n4. Screenshot test...")
os.makedirs("screenshots", exist_ok=True)
run(f"adb -s {device} shell screencap -p /sdcard/vrbot_test.png")
run(f"adb -s {device} pull /sdcard/vrbot_test.png screenshots/test.png")
if os.path.exists("screenshots/test.png"):
    sz = os.path.getsize("screenshots/test.png")
    print(f"   OK: {sz//1024} KB")
else: print("   X Failed")

# Tap
print("\n5. Touch test...")
out, code = run(f"adb -s {device} shell input tap 100 100")
print("   OK" if code == 0 else f"   X {out}")

print(f"\n=== READY! Device: {device} ===")
print(f'Update DEVICE in capture_tool.py: DEVICE = "{device}"')
