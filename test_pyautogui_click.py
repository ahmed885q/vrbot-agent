"""
Quick test: Create button/tab detection + click (v3.4)
Detects BOTH popup Create button AND old tab.

1. Attack a Niflung manually so Create appears
2. Run: python test_pyautogui_click.py
"""
import subprocess, os, time, numpy as np
from PIL import Image

ADB_EXE = r"C:\LDPlayer\LDPlayer9\adb.exe"
ADB_DEVICE = "127.0.0.1:5555"

def find_create():
    os.makedirs("debug_screenshots", exist_ok=True)
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "screencap", "-p",
                    "/sdcard/vrbot_create.png"], capture_output=True, timeout=10)
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "pull", "/sdcard/vrbot_create.png",
                    "debug_screenshots/_create_test.png"], capture_output=True, timeout=10)
    arr = np.array(Image.open("debug_screenshots/_create_test.png"))
    
    # CHECK A: Popup Create button (y=150-200, x=830-1050)
    popup = arr[150:200, 830:1050, :3]
    pm = ((popup[:,:,2].astype(int) > 120) & (popup[:,:,0].astype(int) < 40) &
          (popup[:,:,1].astype(int) > 80) & (popup[:,:,1].astype(int) < 120))
    pct = int(np.sum(pm))
    if pct > 2000:
        c = np.where(pm)
        cy, cx = 150+int(np.median(c[0])), 830+int(np.median(c[1]))
        print(f"  POPUP Create button: {pct}px center=({cx},{cy}) -> ADB")
        return (cx, cy, 'adb')
    
    # CHECK B: Top-right tab (y=10-55, x=1000-1280)
    tab = arr[10:55, 1000:1280, :3]
    tm = ((tab[:,:,2].astype(int) > 110) & (tab[:,:,0].astype(int) < 35) &
          (tab[:,:,1].astype(int) > 70) & (tab[:,:,1].astype(int) < 115))
    tpct = int(np.sum(tm)) / (tab.shape[0]*tab.shape[1]) * 100
    if tpct > 40:
        c = np.where(tm)
        cy, cx = 10+int(np.median(c[0])), 1000+int(np.median(c[1]))
        print(f"  TAB found: {tpct:.1f}% center=({cx},{cy}) -> pyautogui")
        return (cx, cy, 'pyautogui')
    
    # CHECK C: Broader scan
    for y1,y2,x1,x2 in [(100,250,700,1150), (0,70,900,1280)]:
        s = arr[y1:y2, x1:x2, :3]
        sm = ((s[:,:,2].astype(int)>110)&(s[:,:,0].astype(int)<50)&
              (s[:,:,1].astype(int)>70)&(s[:,:,1].astype(int)<120))
        sc = int(np.sum(sm))
        if sc > 1500:
            c = np.where(sm)
            cy, cx = y1+int(np.median(c[0])), x1+int(np.median(c[1]))
            m = 'adb' if cy > 60 else 'pyautogui'
            print(f"  FALLBACK: {sc}px center=({cx},{cy}) -> {m}")
            return (cx, cy, m)
    
    print(f"  Not found (popup={pct}, tab={tpct:.1f}%)")
    return None

def adb_tap(x, y):
    subprocess.run([ADB_EXE, "-s", ADB_DEVICE, "shell", "input", "tap", str(x), str(y)],
                   capture_output=True, timeout=10)
    print(f"  ADB tapped ({x},{y})")

def pyautogui_tap(gx, gy):
    import pyautogui, ctypes, ctypes.wintypes, pygetwindow as gw
    pyautogui.FAILSAFE = False
    wins = gw.getWindowsWithTitle('LDPlayer')
    if not wins: return False
    win = wins[0]
    pt = ctypes.wintypes.POINT(0,0)
    ctypes.windll.user32.ClientToScreen(win._hWnd, ctypes.byref(pt))
    rc = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetClientRect(win._hWnd, ctypes.byref(rc))
    sx = pt.x + int(gx * rc.right / 1280)
    sy = pt.y + int(gy * rc.bottom / 720)
    try: win.activate()
    except: pass
    time.sleep(0.5)
    pyautogui.click(sx, sy)
    print(f"  pyautogui clicked ({sx},{sy})")
    return True

def main():
    print("=" * 50)
    print("  Create Detection Test v3.4")
    print("=" * 50)
    print("\nMake sure Create button/tab is visible!")
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    result = find_create()
    if not result:
        print("\nCreate not found.")
        return
    
    cx, cy, method = result
    print(f"\nClicking ({cx},{cy}) via {method}...")
    if method == 'adb':
        adb_tap(cx, cy)
    else:
        pyautogui_tap(cx, cy)
    
    time.sleep(3)
    if not find_create():
        print("\nSUCCESS! Create gone - should be in Create Squad now.")
    else:
        print("\nStill visible - trying again...")
        if method == 'adb':
            adb_tap(cx, cy)
        else:
            pyautogui_tap(cx, cy)

if __name__ == "__main__":
    main()
