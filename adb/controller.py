"""
ADB Controller — Communicates with LDPlayer via ADB
Handles: connect, tap, swipe, screenshot, key events
"""

import subprocess
import time
import logging
import io
from typing import Optional, Tuple

log = logging.getLogger("vrbot.adb")


class ADBController:
    def __init__(self, host: str = "127.0.0.1", port: int = 5555, adb_path: str = "adb"):
        self.host = host
        self.port = port
        self.adb_path = adb_path
        self.address = f"{host}:{port}"
        self._connected = False

    def _run(self, *args, timeout: int = 10) -> Tuple[bool, str]:
        """Run ADB command and return (success, output)"""
        cmd = [self.adb_path] + list(args)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                err = result.stderr.strip()
                log.debug(f"ADB error: {err}")
                return False, err
            return True, output
        except subprocess.TimeoutExpired:
            log.warning(f"ADB command timed out: {' '.join(cmd)}")
            return False, "timeout"
        except FileNotFoundError:
            log.error(f"ADB not found at: {self.adb_path}")
            return False, "adb not found"

    def _shell(self, cmd: str, timeout: int = 10) -> Tuple[bool, str]:
        """Run ADB shell command"""
        return self._run("-s", self.address, "shell", cmd, timeout=timeout)

    def _shell_bytes(self, cmd: str, timeout: int = 10) -> Optional[bytes]:
        """Run ADB shell command and return raw bytes"""
        full_cmd = [self.adb_path, "-s", self.address, "shell", cmd]
        try:
            result = subprocess.run(full_cmd, capture_output=True, timeout=timeout)
            if result.returncode != 0:
                return None
            return result.stdout
        except Exception:
            return None

    # ─── Connection ─────────────────────────────────

    def connect(self) -> bool:
        """Connect to LDPlayer ADB"""
        log.info(f"Connecting to {self.address}...")
        ok, out = self._run("connect", self.address, timeout=15)
        if ok and ("connected" in out.lower() or "already" in out.lower()):
            self._connected = True
            log.info(f"Connected to {self.address}")
            return True
        log.error(f"Connection failed: {out}")
        return False

    def disconnect(self):
        """Disconnect ADB"""
        if self._connected:
            self._run("disconnect", self.address)
            self._connected = False
            log.info("Disconnected")

    def is_connected(self) -> bool:
        ok, out = self._shell("echo ok")
        return ok and "ok" in out

    def device_name(self) -> str:
        ok, out = self._shell("getprop ro.product.model")
        return out if ok else "Unknown"

    # ─── Input Actions ─────────────────────────────

    def tap(self, x: int, y: int):
        """Tap at coordinates"""
        self._shell(f"input tap {x} {y}")
        log.debug(f"Tap ({x}, {y})")

    def long_press(self, x: int, y: int, duration_ms: int = 1000):
        """Long press at coordinates"""
        self._shell(f"input swipe {x} {y} {x} {y} {duration_ms}")
        log.debug(f"LongPress ({x}, {y}) {duration_ms}ms")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400):
        """Swipe from (x1,y1) to (x2,y2)"""
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
        log.debug(f"Swipe ({x1},{y1})->({x2},{y2}) {duration_ms}ms")

    def key_event(self, keycode: int):
        """Send key event (e.g. BACK=4, HOME=3, ENTER=66)"""
        self._shell(f"input keyevent {keycode}")
        log.debug(f"Key {keycode}")

    def back(self):
        """Press BACK button"""
        self.key_event(4)

    def home(self):
        """Press HOME button"""
        self.key_event(3)

    def text_input(self, text: str):
        """Type text"""
        # Escape special chars
        safe = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        self._shell(f"input text '{safe}'")

    # ─── Screenshot ─────────────────────────────────

    def screenshot(self) -> Optional[bytes]:
        """Take screenshot and return PNG bytes"""
        raw = self._shell_bytes("screencap -p", timeout=15)
        if raw:
            # Fix line ending issue on some devices
            return raw.replace(b"\r\n", b"\n")
        return None

    def screenshot_to_file(self, path: str) -> bool:
        """Take screenshot and save to local file"""
        data = self.screenshot()
        if data:
            with open(path, "wb") as f:
                f.write(data)
            return True
        return False

    # ─── App Management ────────────────────────────

    def current_app(self) -> str:
        """Get current foreground app package"""
        ok, out = self._shell("dumpsys window | grep mCurrentFocus")
        if ok and "/" in out:
            try:
                return out.split("/")[0].split(" ")[-1]
            except Exception:
                pass
        return ""

    def launch_app(self, package: str, activity: str = ""):
        """Launch an app"""
        if activity:
            self._shell(f"am start -n {package}/{activity}")
        else:
            self._shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
        log.info(f"Launched {package}")

    def is_app_running(self, package: str) -> bool:
        ok, out = self._shell(f"pidof {package}")
        return ok and len(out.strip()) > 0

    # ─── Screen Info ───────────────────────────────

    def screen_size(self) -> Tuple[int, int]:
        """Get screen resolution"""
        ok, out = self._shell("wm size")
        if ok and "x" in out:
            try:
                parts = out.split(":")[-1].strip().split("x")
                return int(parts[0]), int(parts[1])
            except Exception:
                pass
        return 1280, 720  # LDPlayer default

    def screen_on(self) -> bool:
        ok, out = self._shell("dumpsys power | grep 'Display Power'")
        return "ON" in out if ok else True

    def wake_up(self):
        if not self.screen_on():
            self.key_event(26)  # POWER
            time.sleep(0.5)
            self.swipe(640, 600, 640, 200, 300)  # unlock swipe
