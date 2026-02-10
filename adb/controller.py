"""
VRBOT Agent — ADB Controller
Controls LDPlayer emulator via ADB + ldconsole for multi-instance management.
"""
import subprocess
import time
import random
import logging
import os
import re
from io import BytesIO

log = logging.getLogger("vrbot.adb")


class ADBController:
    """ADB interface for LDPlayer emulator control."""

    def __init__(self, host="127.0.0.1", port=5555, ldplayer_path=None, ldconsole=None):
        self.host = host
        self.port = port
        self.device = f"{host}:{port}"
        self.ldplayer_path = ldplayer_path or r"C:\LDPlayer\LDPlayer9"
        self.ldconsole = ldconsole or os.path.join(self.ldplayer_path, "ldconsole.exe")
        self.connected = False
        self._screen_size = None

    # ─── Connection ───────────────────────────────────────────

    def connect(self, retries=3):
        """Connect to LDPlayer ADB."""
        for attempt in range(retries):
            try:
                result = self._adb(f"connect {self.device}")
                if "connected" in result.lower():
                    self.connected = True
                    self._screen_size = self._get_screen_size()
                    log.info(f"✅ Connected to {self.device} | Screen: {self._screen_size}")
                    return True
                log.warning(f"Attempt {attempt+1}/{retries}: {result.strip()}")
            except Exception as e:
                log.error(f"Connection error: {e}")
            time.sleep(2)
        log.error(f"❌ Failed to connect to {self.device}")
        return False

    def disconnect(self):
        """Disconnect from device."""
        self._adb(f"disconnect {self.device}")
        self.connected = False
        log.info(f"Disconnected from {self.device}")

    def is_alive(self):
        """Check if device is still responding."""
        try:
            result = self._shell("echo ping")
            return "ping" in result
        except Exception:
            return False

    # ─── Touch Actions ────────────────────────────────────────

    def tap(self, x, y, offset=0):
        """Tap at coordinates with optional random offset."""
        if offset > 0:
            x += random.randint(-offset, offset)
            y += random.randint(-offset, offset)
        x = max(0, min(x, self._screen_size[0] if self._screen_size else 1280))
        y = max(0, min(y, self._screen_size[1] if self._screen_size else 720))
        self._shell(f"input tap {x} {y}")
        log.debug(f"Tap: ({x}, {y})")

    def long_press(self, x, y, duration_ms=1500, offset=0):
        """Long press at coordinates."""
        if offset > 0:
            x += random.randint(-offset, offset)
            y += random.randint(-offset, offset)
        self._shell(f"input swipe {x} {y} {x} {y} {duration_ms}")
        log.debug(f"Long press: ({x}, {y}) {duration_ms}ms")

    def swipe(self, x1, y1, x2, y2, duration_ms=500, human=True):
        """Swipe with optional human-like curve."""
        if human:
            self._human_swipe(x1, y1, x2, y2, duration_ms)
        else:
            self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
        log.debug(f"Swipe: ({x1},{y1}) → ({x2},{y2}) {duration_ms}ms")

    def _human_swipe(self, x1, y1, x2, y2, duration_ms):
        """Swipe with slight curve to mimic human finger movement."""
        # Add slight random curve midpoint
        mid_x = (x1 + x2) // 2 + random.randint(-20, 20)
        mid_y = (y1 + y2) // 2 + random.randint(-20, 20)
        # Use sendevent for multi-point swipe (more human-like)
        # Fallback to simple swipe with duration variation
        duration_ms += random.randint(-100, 150)
        duration_ms = max(200, duration_ms)
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def drag(self, x1, y1, x2, y2, duration_ms=1000):
        """Drag from point A to B (for moving items)."""
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
        log.debug(f"Drag: ({x1},{y1}) → ({x2},{y2})")

    def pinch_zoom(self, center_x, center_y, zoom_in=True):
        """Zoom in/out on map."""
        offset = 100 if zoom_in else -100
        # Simulate two-finger pinch via ADB (approximate)
        self.swipe(
            center_x - offset, center_y - offset,
            center_x + offset, center_y + offset,
            duration_ms=500, human=False
        )

    # ─── Screenshot ───────────────────────────────────────────

    def screenshot(self, save_path=None):
        """Capture screenshot as raw bytes or save to file."""
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "exec-out", "screencap", "-p"],
                capture_output=True, timeout=10
            )
            if result.returncode == 0 and len(result.stdout) > 100:
                png_data = result.stdout
                if save_path:
                    with open(save_path, "wb") as f:
                        f.write(png_data)
                    log.debug(f"Screenshot saved: {save_path}")
                return png_data
        except subprocess.TimeoutExpired:
            log.error("Screenshot timeout")
        except Exception as e:
            log.error(f"Screenshot error: {e}")
        return None

    def screenshot_cv(self):
        """Return screenshot as OpenCV numpy array (BGR)."""
        import cv2
        import numpy as np

        png_data = self.screenshot()
        if png_data:
            nparr = np.frombuffer(png_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        return None

    # ─── App Management ───────────────────────────────────────

    def launch_app(self, package="com.igg.android.vikingrise"):
        """Launch game app."""
        self._shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
        log.info(f"Launched: {package}")

    def close_app(self, package="com.igg.android.vikingrise"):
        """Force close app."""
        self._shell(f"am force-stop {package}")
        log.info(f"Closed: {package}")

    def is_app_running(self, package="com.igg.android.vikingrise"):
        """Check if game is running."""
        result = self._shell(f"pidof {package}")
        return bool(result.strip())

    def go_back(self):
        """Press back button."""
        self._shell("input keyevent 4")

    def go_home(self):
        """Press home button."""
        self._shell("input keyevent 3")

    # ─── LDPlayer Multi-Instance (ldconsole) ──────────────────

    def ld_list_instances(self):
        """List all LDPlayer instances."""
        try:
            result = subprocess.run(
                [self.ldconsole, "list2"],
                capture_output=True, text=True, timeout=10
            )
            instances = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 3:
                        instances.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "status": "running" if parts[4] == "1" else "stopped",
                            "pid": parts[2] if len(parts) > 2 else None,
                        })
            return instances
        except Exception as e:
            log.error(f"ldconsole list error: {e}")
            return []

    def ld_launch(self, index=0):
        """Launch LDPlayer instance by index."""
        try:
            subprocess.Popen([self.ldconsole, "launch", "--index", str(index)])
            log.info(f"Launching LDPlayer instance {index}...")
            # Wait for ADB to become available
            for _ in range(30):
                time.sleep(2)
                if self.connect(retries=1):
                    return True
            return False
        except Exception as e:
            log.error(f"Launch error: {e}")
            return False

    def ld_quit(self, index=0):
        """Quit LDPlayer instance."""
        try:
            subprocess.run(
                [self.ldconsole, "quit", "--index", str(index)],
                timeout=15
            )
            log.info(f"Quit LDPlayer instance {index}")
            return True
        except Exception as e:
            log.error(f"Quit error: {e}")
            return False

    def ld_create_instance(self, name):
        """Create new LDPlayer instance (for multi-account)."""
        try:
            subprocess.run(
                [self.ldconsole, "copy", "--name", name, "--from", "0"],
                timeout=60
            )
            log.info(f"Created instance: {name}")
            return True
        except Exception as e:
            log.error(f"Create instance error: {e}")
            return False

    def ld_get_adb_port(self, index=0):
        """Get ADB port for a specific instance."""
        # LDPlayer default: instance 0 = 5555, instance 1 = 5557, etc.
        return 5555 + (index * 2)

    def ld_sort_wnd(self):
        """Arrange all LDPlayer windows neatly."""
        try:
            subprocess.run([self.ldconsole, "sortWnd"], timeout=10)
        except Exception:
            pass

    # ─── Internal Helpers ─────────────────────────────────────

    def _adb(self, cmd):
        """Run raw ADB command."""
        try:
            result = subprocess.run(
                f"adb {cmd}",
                shell=True, capture_output=True, text=True, timeout=15
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return "timeout"
        except Exception as e:
            return str(e)

    def _shell(self, cmd):
        """Run ADB shell command on device."""
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "shell", cmd],
                capture_output=True, text=True, timeout=15
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            log.error(f"Shell error: {e}")
            return ""

    def _get_screen_size(self):
        """Get device screen resolution."""
        result = self._shell("wm size")
        match = re.search(r"(\d+)x(\d+)", result)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (1280, 720)

    @property
    def screen_width(self):
        return self._screen_size[0] if self._screen_size else 1280

    @property
    def screen_height(self):
        return self._screen_size[1] if self._screen_size else 720

