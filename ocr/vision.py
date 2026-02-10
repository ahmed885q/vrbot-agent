"""
VRBOT Agent — Vision System
OpenCV Template Matching + Tesseract OCR for game state recognition.
"""
import cv2
import numpy as np
import os
import logging
import time
from functools import lru_cache

log = logging.getLogger("vrbot.vision")


class Vision:
    """Image recognition engine using OpenCV template matching."""

    def __init__(self, adb_controller, config=None):
        self.adb = adb_controller
        self.config = config or {}
        self.threshold = self.config.get("template_threshold", 0.80)
        self.match_method = getattr(cv2, self.config.get("match_method", "TM_CCOEFF_NORMED"))
        self.multi_scale = self.config.get("multi_scale", True)
        self.scales = self.config.get("scales", [0.8, 0.9, 1.0, 1.1, 1.2])
        self.template_dir = "templates"
        self._template_cache = {}
        self._last_screenshot = None
        self._last_screenshot_time = 0

    # ─── Template Loading ─────────────────────────────────────

    def load_template(self, name):
        """Load template image with caching."""
        if name in self._template_cache:
            return self._template_cache[name]

        # Search in templates directory
        for ext in [".png", ".jpg"]:
            path = os.path.join(self.template_dir, name + ext)
            if os.path.exists(path):
                tpl = cv2.imread(path, cv2.IMREAD_COLOR)
                if tpl is not None:
                    self._template_cache[name] = tpl
                    return tpl

        # Also check subdirectories
        for root, dirs, files in os.walk(self.template_dir):
            for f in files:
                if f.startswith(name) and f.endswith((".png", ".jpg")):
                    path = os.path.join(root, f)
                    tpl = cv2.imread(path, cv2.IMREAD_COLOR)
                    if tpl is not None:
                        self._template_cache[name] = tpl
                        return tpl

        log.warning(f"Template not found: {name}")
        return None

    def load_all_templates(self):
        """Pre-load all templates into cache."""
        count = 0
        for root, dirs, files in os.walk(self.template_dir):
            for f in files:
                if f.endswith((".png", ".jpg")):
                    name = os.path.splitext(f)[0]
                    path = os.path.join(root, f)
                    tpl = cv2.imread(path, cv2.IMREAD_COLOR)
                    if tpl is not None:
                        self._template_cache[name] = tpl
                        count += 1
        log.info(f"Loaded {count} templates into cache")
        return count

    # ─── Screenshot ───────────────────────────────────────────

    def capture(self, fresh=False):
        """Get current screen as CV2 image. Uses cache if recent."""
        now = time.time()
        if not fresh and self._last_screenshot is not None and (now - self._last_screenshot_time) < 0.5:
            return self._last_screenshot

        img = self.adb.screenshot_cv()
        if img is not None:
            self._last_screenshot = img
            self._last_screenshot_time = now
        return img

    # ─── Template Matching ────────────────────────────────────

    def find(self, template_name, threshold=None, region=None):
        """
        Find template on screen. Returns (x, y, confidence) or None.
        x, y = center of matched area.
        """
        threshold = threshold or self.threshold
        screen = self.capture()
        if screen is None:
            return None

        template = self.load_template(template_name)
        if template is None:
            return None

        # Crop region if specified (x, y, w, h)
        if region:
            rx, ry, rw, rh = region
            screen = screen[ry:ry+rh, rx:rx+rw]

        if self.multi_scale:
            result = self._multi_scale_match(screen, template, threshold)
        else:
            result = self._single_match(screen, template, threshold)

        if result and region:
            # Adjust coordinates back to full screen
            result = (result[0] + region[0], result[1] + region[1], result[2])

        if result:
            log.debug(f"Found '{template_name}' at ({result[0]}, {result[1]}) conf={result[2]:.2f}")
        return result

    def find_all(self, template_name, threshold=None, region=None, max_results=10):
        """Find all occurrences of template on screen."""
        threshold = threshold or self.threshold
        screen = self.capture()
        if screen is None:
            return []

        template = self.load_template(template_name)
        if template is None:
            return []

        if region:
            rx, ry, rw, rh = region
            screen = screen[ry:ry+rh, rx:rx+rw]

        h, w = template.shape[:2]
        result = cv2.matchTemplate(screen, template, self.match_method)
        locations = np.where(result >= threshold)

        matches = []
        for pt in zip(*locations[::-1]):
            cx = pt[0] + w // 2
            cy = pt[1] + h // 2
            conf = result[pt[1], pt[0]]

            if region:
                cx += region[0]
                cy += region[1]

            # Skip duplicates (within 20px)
            is_dup = False
            for m in matches:
                if abs(m[0] - cx) < 20 and abs(m[1] - cy) < 20:
                    is_dup = True
                    break
            if not is_dup:
                matches.append((cx, cy, float(conf)))

            if len(matches) >= max_results:
                break

        matches.sort(key=lambda m: m[2], reverse=True)
        return matches

    def exists(self, template_name, threshold=None, region=None):
        """Check if template exists on screen (True/False)."""
        return self.find(template_name, threshold, region) is not None

    def wait_for(self, template_name, timeout=15, interval=1.0, threshold=None):
        """Wait until template appears on screen."""
        start = time.time()
        while time.time() - start < timeout:
            result = self.find(template_name, threshold)
            if result:
                return result
            time.sleep(interval)
        log.warning(f"Timeout waiting for '{template_name}' ({timeout}s)")
        return None

    def wait_until_gone(self, template_name, timeout=30, interval=1.0):
        """Wait until template disappears from screen."""
        start = time.time()
        while time.time() - start < timeout:
            if not self.exists(template_name):
                return True
            time.sleep(interval)
        return False

    def tap_on(self, template_name, threshold=None, offset=8, wait=True, timeout=10):
        """Find template and tap on it."""
        if wait:
            result = self.wait_for(template_name, timeout=timeout, threshold=threshold)
        else:
            result = self.find(template_name, threshold)

        if result:
            x, y, conf = result
            self.adb.tap(x, y, offset=offset)
            return True
        return False

    # ─── OCR ──────────────────────────────────────────────────

    def read_text(self, region=None, preprocess="thresh"):
        """Read text from screen region using Tesseract OCR."""
        try:
            import pytesseract
        except ImportError:
            log.error("pytesseract not installed")
            return ""

        screen = self.capture()
        if screen is None:
            return ""

        if region:
            rx, ry, rw, rh = region
            screen = screen[ry:ry+rh, rx:rx+rw]

        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        if preprocess == "thresh":
            gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        elif preprocess == "blur":
            gray = cv2.medianBlur(gray, 3)
        elif preprocess == "adaptive":
            gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 11, 2)

        text = pytesseract.image_to_string(gray, config="--psm 7").strip()
        log.debug(f"OCR result: '{text}'")
        return text

    def read_number(self, region=None):
        """Read number from screen region."""
        text = self.read_text(region, preprocess="thresh")
        # Extract digits
        digits = "".join(c for c in text if c.isdigit())
        if digits:
            return int(digits)
        return 0

    # ─── Color / Pixel Detection ──────────────────────────────

    def get_pixel_color(self, x, y):
        """Get BGR color at pixel (x, y)."""
        screen = self.capture()
        if screen is not None and 0 <= y < screen.shape[0] and 0 <= x < screen.shape[1]:
            return tuple(screen[y, x])
        return None

    def check_pixel_color(self, x, y, expected_bgr, tolerance=30):
        """Check if pixel matches expected color within tolerance."""
        color = self.get_pixel_color(x, y)
        if color is None:
            return False
        return all(abs(int(a) - int(b)) <= tolerance for a, b in zip(color, expected_bgr))

    def find_color_region(self, color_bgr, tolerance=20, region=None):
        """Find center of largest region matching a specific color."""
        screen = self.capture()
        if screen is None:
            return None

        if region:
            rx, ry, rw, rh = region
            screen = screen[ry:ry+rh, rx:rx+rw]

        lower = np.array([max(0, c - tolerance) for c in color_bgr])
        upper = np.array([min(255, c + tolerance) for c in color_bgr])
        mask = cv2.inRange(screen, lower, upper)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            M = cv2.moments(largest)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                if region:
                    cx += region[0]
                    cy += region[1]
                return (cx, cy)
        return None

    # ─── Game State Detection ─────────────────────────────────

    def detect_screen(self, screen_templates):
        """
        Detect which game screen we're on.
        screen_templates: dict of {"screen_name": "template_name"}
        Returns screen name or "unknown"
        """
        for screen_name, template_name in screen_templates.items():
            if self.exists(template_name, threshold=0.85):
                log.debug(f"Detected screen: {screen_name}")
                return screen_name
        return "unknown"

    def is_loading(self):
        """Check if game is in loading state."""
        return self.exists("loading_spinner") or self.exists("loading_bar")

    def wait_loading(self, timeout=60):
        """Wait for loading to finish."""
        time.sleep(1)
        start = time.time()
        while self.is_loading() and (time.time() - start) < timeout:
            time.sleep(1)
        time.sleep(0.5)

    # ─── Internal ─────────────────────────────────────────────

    def _single_match(self, screen, template, threshold):
        """Single-scale template matching."""
        h, w = template.shape[:2]
        if h > screen.shape[0] or w > screen.shape[1]:
            return None

        result = cv2.matchTemplate(screen, template, self.match_method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2
            return (cx, cy, max_val)
        return None

    def _multi_scale_match(self, screen, template, threshold):
        """Multi-scale template matching for resolution differences."""
        best = None
        h_orig, w_orig = template.shape[:2]

        for scale in self.scales:
            w_new = int(w_orig * scale)
            h_new = int(h_orig * scale)
            if w_new < 10 or h_new < 10:
                continue
            if w_new > screen.shape[1] or h_new > screen.shape[0]:
                continue

            scaled = cv2.resize(template, (w_new, h_new))
            result = cv2.matchTemplate(screen, scaled, self.match_method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                if best is None or max_val > best[2]:
                    cx = max_loc[0] + w_new // 2
                    cy = max_loc[1] + h_new // 2
                    best = (cx, cy, max_val)

        return best

    def save_debug_screenshot(self, name="debug"):
        """Save screenshot for debugging."""
        screen = self.capture(fresh=True)
        if screen is not None:
            path = f"screenshots/{name}_{int(time.time())}.png"
            os.makedirs("screenshots", exist_ok=True)
            cv2.imwrite(path, screen)
            log.info(f"Debug screenshot: {path}")
            return path
        return None

