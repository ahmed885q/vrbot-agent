"""
VisionAI — Screenshot analysis for Ultra Agent.

Two-tier detection:
  1. Fast path: byte-level heuristics (< 5ms) — screen type classification
  2. Slow path: YOLO ONNX if available (~ 15ms) — element detection

Never blocks the bot loop. Falls back gracefully.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("ultra.vision")

# Screen type classification based on screenshot byte analysis
SCREEN_TYPES = {
    "city":      "Main city view",
    "world_map": "World map / kingdom view",
    "menu":      "Popup menu or dialog",
    "battle":    "Battle or march screen",
    "loading":   "Loading screen",
    "login":     "Login / splash screen",
    "unknown":   "Unrecognized state",
}


@dataclass
class ScreenAnalysis:
    screen_type: str = "unknown"
    brightness: float = 0.0
    variance: float = 0.0
    has_dialog: bool = False
    has_close_btn: bool = False
    byte_size: int = 0
    screen_hash: str = ""
    elements: list = field(default_factory=list)


class VisionAI:
    """Analyzes screenshots to determine game state."""

    # Brightness/variance thresholds learned from Viking Rise
    DARK_THRESH = 40       # loading/black screen
    BRIGHT_THRESH = 200    # white/splash screen
    DIALOG_VAR_LOW = 800   # low variance in center = dialog overlay
    CITY_VAR_HIGH = 2500   # high variance = rich city scene

    def __init__(self):
        self._yolo = None
        self._load_yolo()

    def _load_yolo(self):
        try:
            import onnxruntime
            # YOLO model path — optional, works without it
            import os
            model_path = os.path.join(os.path.dirname(__file__), "..", "models", "yolo_vr.onnx")
            if os.path.exists(model_path):
                self._yolo = onnxruntime.InferenceSession(model_path)
                log.info("YOLO model loaded: %s", model_path)
        except ImportError:
            pass
        except Exception as e:
            log.debug("YOLO not available: %s", e)

    def analyze(self, screenshot: bytes) -> ScreenAnalysis:
        """Analyze a screenshot and return game state."""
        if not screenshot or len(screenshot) < 1000:
            return ScreenAnalysis(screen_type="unknown", byte_size=len(screenshot or b""))

        result = ScreenAnalysis(byte_size=len(screenshot))
        result.screen_hash = hashlib.md5(screenshot[:4096]).hexdigest()[:12]

        # Fast byte-level analysis
        self._analyze_bytes(screenshot, result)

        # YOLO element detection (if available)
        if self._yolo:
            self._detect_elements(screenshot, result)

        return result

    def _analyze_bytes(self, data: bytes, result: ScreenAnalysis):
        """Fast heuristic analysis from raw bytes."""
        # Sample every 31st byte (prime step for good distribution)
        step = 31
        vals = [data[i] for i in range(min(100, len(data)), len(data), step)]
        if not vals:
            return

        avg = sum(vals) / len(vals)
        var = sum((v - avg) ** 2 for v in vals) / len(vals)
        result.brightness = avg
        result.variance = var

        # Classify screen type
        if avg < self.DARK_THRESH and var < 500:
            result.screen_type = "loading"
        elif avg > self.BRIGHT_THRESH and var < 500:
            result.screen_type = "login"
        elif var > self.CITY_VAR_HIGH:
            result.screen_type = "city"
        elif var < self.DIALOG_VAR_LOW and avg > 60:
            result.screen_type = "menu"
            result.has_dialog = True
        else:
            result.screen_type = "world_map"

        # Check for close button pattern (high contrast in top-right quadrant)
        tr_start = len(data) * 3 // 4
        tr_vals = [data[i] for i in range(tr_start, len(data), step * 2)]
        if tr_vals:
            tr_var = sum((v - sum(tr_vals) / len(tr_vals)) ** 2 for v in tr_vals) / len(tr_vals)
            result.has_close_btn = tr_var > 3000

    def _detect_elements(self, data: bytes, result: ScreenAnalysis):
        """YOLO-based element detection (optional)."""
        try:
            from PIL import Image
            import io
            import numpy as np

            img = Image.open(io.BytesIO(data)).resize((640, 640)).convert("RGB")
            arr = np.array(img, dtype=np.float32) / 255.0
            arr = arr.transpose(2, 0, 1)[np.newaxis, ...]

            outputs = self._yolo.run(None, {"images": arr})
            # Parse YOLO output — simplified
            for det in outputs[0][0]:
                conf = float(det[4])
                if conf > 0.5:
                    cls_id = int(det[5])
                    result.elements.append({
                        "class": cls_id,
                        "confidence": round(conf, 2),
                        "bbox": [float(x) for x in det[:4]],
                    })
        except Exception as e:
            log.debug("YOLO detection skipped: %s", e)
