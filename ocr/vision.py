"""
Vision Module — OCR + Template Matching for screen reading
Uses OpenCV for template matching and Tesseract for OCR
"""

import os
import io
import logging
import numpy as np
from typing import Optional, Tuple, List
from dataclasses import dataclass

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

log = logging.getLogger("vrbot.vision")

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


@dataclass
class MatchResult:
    """Result of a template match"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    center_x: int = 0
    center_y: int = 0

    def __post_init__(self):
        self.center_x = self.x + self.width // 2
        self.center_y = self.y + self.height // 2


class Vision:
    def __init__(self, adb):
        self.adb = adb
        self._check_deps()

    def _check_deps(self):
        if cv2 is None:
            log.warning("OpenCV not installed. Run: pip install opencv-python")
        if pytesseract is None:
            log.warning("pytesseract not installed. Run: pip install pytesseract")

    def _screenshot_cv(self) -> Optional[np.ndarray]:
        """Get screenshot as OpenCV image (numpy array)"""
        png_bytes = self.adb.screenshot()
        if not png_bytes:
            return None
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img

    # ─── Template Matching ──────────────────────────

    def find_template(
        self,
        template_name: str,
        threshold: float = 0.85,
        screenshot: Optional[np.ndarray] = None,
    ) -> Optional[MatchResult]:
        """
        Find a template image on screen.
        template_name: filename in templates/ folder (e.g. 'btn_gather.png')
        Returns MatchResult or None
        """
        if cv2 is None:
            log.error("OpenCV required for template matching")
            return None

        # Load template
        template_path = os.path.join(TEMPLATES_DIR, template_name)
        if not os.path.exists(template_path):
            log.warning(f"Template not found: {template_path}")
            return None

        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            log.error(f"Cannot read template: {template_path}")
            return None

        # Get screenshot
        screen = screenshot if screenshot is not None else self._screenshot_cv()
        if screen is None:
            log.error("Cannot take screenshot")
            return None

        # Match
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = template.shape[:2]
            match = MatchResult(
                x=max_loc[0], y=max_loc[1],
                width=w, height=h,
                confidence=max_val,
            )
            log.debug(f"Found '{template_name}' at ({match.center_x},{match.center_y}) conf={max_val:.3f}")
            return match

        log.debug(f"Template '{template_name}' not found (best={max_val:.3f} < {threshold})")
        return None

    def find_all_templates(
        self,
        template_name: str,
        threshold: float = 0.85,
        max_results: int = 20,
    ) -> List[MatchResult]:
        """Find all occurrences of a template on screen"""
        if cv2 is None:
            return []

        template_path = os.path.join(TEMPLATES_DIR, template_name)
        if not os.path.exists(template_path):
            return []

        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        screen = self._screenshot_cv()
        if screen is None or template is None:
            return []

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        h, w = template.shape[:2]

        locations = np.where(result >= threshold)
        matches = []

        for pt in zip(*locations[::-1]):
            # Skip if too close to existing match
            too_close = False
            for m in matches:
                if abs(m.x - pt[0]) < w // 2 and abs(m.y - pt[1]) < h // 2:
                    too_close = True
                    break
            if too_close:
                continue

            matches.append(MatchResult(
                x=pt[0], y=pt[1],
                width=w, height=h,
                confidence=result[pt[1], pt[0]],
            ))
            if len(matches) >= max_results:
                break

        return matches

    def wait_for_template(
        self,
        template_name: str,
        timeout: float = 10.0,
        interval: float = 1.0,
        threshold: float = 0.85,
    ) -> Optional[MatchResult]:
        """Wait for a template to appear on screen"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            match = self.find_template(template_name, threshold)
            if match:
                return match
            time.sleep(interval)
        return None

    def template_exists(self, template_name: str, threshold: float = 0.85) -> bool:
        """Check if template is on screen"""
        return self.find_template(template_name, threshold) is not None

    # ─── OCR ────────────────────────────────────────

    def read_text(
        self,
        region: Optional[Tuple[int, int, int, int]] = None,
        lang: str = "eng",
    ) -> str:
        """
        Read text from screen using OCR.
        region: (x, y, w, h) crop region, or None for full screen
        """
        if pytesseract is None or cv2 is None:
            log.error("pytesseract and OpenCV required for OCR")
            return ""

        screen = self._screenshot_cv()
        if screen is None:
            return ""

        if region:
            x, y, w, h = region
            screen = screen[y:y + h, x:x + w]

        # Preprocess for better OCR
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        text = pytesseract.image_to_string(thresh, lang=lang).strip()
        return text

    def read_number(
        self,
        region: Tuple[int, int, int, int],
        lang: str = "eng",
    ) -> Optional[int]:
        """Read a number from a region"""
        text = self.read_text(region, lang)
        digits = "".join(c for c in text if c.isdigit())
        if digits:
            return int(digits)
        return None

    # ─── Color Detection ────────────────────────────

    def get_pixel_color(self, x: int, y: int) -> Optional[Tuple[int, int, int]]:
        """Get RGB color at pixel"""
        screen = self._screenshot_cv()
        if screen is None:
            return None
        if 0 <= y < screen.shape[0] and 0 <= x < screen.shape[1]:
            b, g, r = screen[y, x]
            return (int(r), int(g), int(b))
        return None

    def color_matches(self, x: int, y: int, expected_rgb: Tuple[int, int, int], tolerance: int = 30) -> bool:
        """Check if pixel color matches expected (with tolerance)"""
        color = self.get_pixel_color(x, y)
        if not color:
            return False
        return all(abs(a - b) <= tolerance for a, b in zip(color, expected_rgb))
