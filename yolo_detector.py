"""
VRBOT — YOLOv8 Object Detector
Replaces slow template matching (~970ms) with fast YOLO detection (~15ms).
Falls back to template matching when YOLO confidence is low.

Usage:
    from yolo_detector import YOLODetector
    
    detector = YOLODetector()
    
    # Detect all elements on screen
    results = detector.detect(screenshot)
    
    # Find specific element
    btn = detector.find("march_btn", screenshot)
    if btn:
        adb.tap(btn.cx, btn.cy)
    
    # Check which screen we're on
    screen = detector.identify_screen(screenshot)
"""

import os
import time
import logging
import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

try:
    import cv2
except ImportError:
    cv2 = None

log = logging.getLogger("vrbot.yolo")

# Default model path
DEFAULT_MODEL = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "best.pt"
)


# ─── Data Classes ─────────────────────────────────────────

@dataclass
class Detection:
    """Single detected element."""
    label: str          # Class name (e.g., "march_btn", "resource_bar")
    confidence: float   # 0.0 to 1.0
    x1: int            # Bounding box top-left x
    y1: int            # Bounding box top-left y
    x2: int            # Bounding box bottom-right x
    y2: int            # Bounding box bottom-right y
    cx: int = 0        # Center x (tap target)
    cy: int = 0        # Center y (tap target)
    width: int = 0
    height: int = 0

    def __post_init__(self):
        self.cx = (self.x1 + self.x2) // 2
        self.cy = (self.y1 + self.y2) // 2
        self.width = self.x2 - self.x1
        self.height = self.y2 - self.y1

    def __repr__(self):
        return f"Detection({self.label}, conf={self.confidence:.2f}, center=({self.cx},{self.cy}))"


@dataclass 
class ScreenState:
    """Current screen identification."""
    screen_name: str           # e.g., "create_squad", "technology", "mail"
    detections: List[Detection] = field(default_factory=list)
    timestamp: float = 0.0
    inference_ms: float = 0.0

    def has(self, label: str, min_conf: float = 0.3) -> bool:
        """Check if a specific element exists on screen."""
        return any(d.label == label and d.confidence >= min_conf for d in self.detections)

    def get(self, label: str, min_conf: float = 0.3) -> Optional[Detection]:
        """Get best detection of a specific element."""
        matches = [d for d in self.detections if d.label == label and d.confidence >= min_conf]
        if not matches:
            return None
        return max(matches, key=lambda d: d.confidence)

    def get_all(self, label: str, min_conf: float = 0.3) -> List[Detection]:
        """Get all detections of a specific element."""
        return [d for d in self.detections if d.label == label and d.confidence >= min_conf]


# ─── Screen Identification Rules ──────────────────────────

# Map popup labels to screen names
SCREEN_RULES: Dict[str, List[str]] = {
    "create_squad":       ["create_squad_popup", "march_btn", "main_commander"],
    "technology":         ["technology_popup", "tech_tab", "tech_node"],
    "barracks":           ["barracks_popup", "train_btn"],
    "mail":               ["mail_popup", "mail_tab"],
    "tribe":              ["tribe_popup", "tribe_members_btn"],
    "daily_quests":       ["daily_quests_popup", "daily_quests_tab"],
    "exploration":        ["exploration_map_popup", "exploration_squad"],
    "search_targets":     ["search_popup", "monster_icon", "farm_icon"],
    "niflung_info":       ["niflung_popup", "attack_btn"],
    "resource_popup":     ["resource_popup", "gather_btn"],
    "gathering_active":   ["resource_popup", "recall_btn", "gathering_progress"],
    "building_upgrade":   ["building_upgrade_popup", "upgrade_btn"],
    "upgrade_power":      ["upgrade_popup", "go_btn"],
    "worker_info":        ["worker_info_popup", "worker_tab"],
    "mercenary_guild":    ["mercenary_guild_popup", "hire_btn"],
    "hero_summon":        ["hero_summon_popup", "free_summon_btn"],
    "staging_post":       ["staging_post_popup", "quest_icon"],
    "divination":         ["divination_shack_popup", "one_divination_btn"],
    "divination_result":  ["divination_result_popup", "ok_btn"],
    "commission":         ["commission_popup", "go_btn"],
    "clan_camp":          ["clan_camp_popup"],
    "world_map":          ["resource_bar", "hero_avatar", "compass_icon"],
}


# ─── YOLO Detector ────────────────────────────────────────

class YOLODetector:
    """
    YOLOv8-based UI element detector for Viking Rise.
    
    Features:
    - Fast detection (~15ms on GPU, ~50ms on CPU)
    - Screen identification from detected elements
    - Confidence-based filtering
    - Detection caching to avoid redundant inference
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL,
        conf_threshold: float = 0.25,
        device: str = "auto",
        cache_ttl: float = 0.5,  # Cache results for 500ms
    ):
        self.conf_threshold = conf_threshold
        self.cache_ttl = cache_ttl
        self._last_state: Optional[ScreenState] = None
        self._model = None
        self._class_names: Dict[int, str] = {}

        if not HAS_YOLO:
            log.warning("ultralytics not installed! Run: pip install ultralytics")
            log.warning("YOLO detection disabled, will need template matching fallback")
            return

        if not os.path.exists(model_path):
            log.warning(f"Model not found: {model_path}")
            log.warning("YOLO detection disabled, will need template matching fallback")
            return

        # Select device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        log.info(f"Loading YOLOv8 model from {model_path} on {device}...")
        t0 = time.time()
        self._model = YOLO(model_path)
        self._class_names = self._model.names  # {0: 'march_btn', 1: 'resource_bar', ...}
        load_time = (time.time() - t0) * 1000
        log.info(f"✅ Model loaded in {load_time:.0f}ms — {len(self._class_names)} classes")
        log.info(f"   Classes: {list(self._class_names.values())}")

    @property
    def is_ready(self) -> bool:
        """Check if YOLO model is loaded and ready."""
        return self._model is not None

    @property
    def class_names(self) -> List[str]:
        """Get list of all detectable class names."""
        return list(self._class_names.values()) if self._class_names else []

    # ─── Core Detection ───────────────────────────────

    def detect(
        self,
        screenshot: np.ndarray,
        conf: Optional[float] = None,
    ) -> ScreenState:
        """
        Run YOLO detection on a screenshot.
        
        Args:
            screenshot: OpenCV image (BGR numpy array)
            conf: Confidence threshold (default: self.conf_threshold)
            
        Returns:
            ScreenState with all detections and screen identification
        """
        if not self.is_ready:
            return ScreenState(screen_name="unknown", timestamp=time.time())

        conf = conf or self.conf_threshold
        t0 = time.time()

        # Run inference
        results = self._model.predict(
            screenshot,
            conf=conf,
            verbose=False,
            imgsz=640,
        )

        inference_ms = (time.time() - t0) * 1000

        # Parse detections
        detections = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                label = self._class_names.get(cls_id, f"class_{cls_id}")
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                detections.append(Detection(
                    label=label,
                    confidence=confidence,
                    x1=x1, y1=y1, x2=x2, y2=y2,
                ))

        # Identify screen
        screen_name = self._identify_screen(detections)

        state = ScreenState(
            screen_name=screen_name,
            detections=detections,
            timestamp=time.time(),
            inference_ms=inference_ms,
        )

        self._last_state = state
        log.debug(f"Detected {len(detections)} elements in {inference_ms:.1f}ms → {screen_name}")
        return state

    def find(
        self,
        label: str,
        screenshot: np.ndarray,
        conf: Optional[float] = None,
    ) -> Optional[Detection]:
        """
        Find a specific element on screen.
        
        Args:
            label: Element label (e.g., "march_btn")
            screenshot: OpenCV image
            conf: Minimum confidence
            
        Returns:
            Best Detection or None
        """
        state = self.detect(screenshot, conf)
        return state.get(label)

    def find_all(
        self,
        label: str,
        screenshot: np.ndarray,
        conf: Optional[float] = None,
    ) -> List[Detection]:
        """Find all instances of a specific element."""
        state = self.detect(screenshot, conf)
        return state.get_all(label)

    def exists(
        self,
        label: str,
        screenshot: np.ndarray,
        conf: Optional[float] = None,
    ) -> bool:
        """Check if an element exists on screen."""
        return self.find(label, screenshot, conf) is not None

    # ─── Screen Identification ────────────────────────

    def _identify_screen(self, detections: List[Detection]) -> str:
        """Identify current screen from detected elements."""
        if not detections:
            return "unknown"

        detected_labels = {d.label for d in detections}

        best_screen = "unknown"
        best_score = 0

        for screen_name, required_labels in SCREEN_RULES.items():
            # Score = number of matching labels / total required
            matches = sum(1 for lbl in required_labels if lbl in detected_labels)
            score = matches / len(required_labels)

            if score > best_score:
                best_score = score
                best_screen = screen_name

        # Require at least 40% match
        if best_score < 0.4:
            return "unknown"

        return best_screen

    def identify_screen(self, screenshot: np.ndarray) -> str:
        """Get current screen name."""
        state = self.detect(screenshot)
        return state.screen_name

    # ─── Cached Detection ─────────────────────────────

    def get_cached(self) -> Optional[ScreenState]:
        """Get cached detection if still fresh."""
        if self._last_state is None:
            return None
        age = time.time() - self._last_state.timestamp
        if age > self.cache_ttl:
            return None
        return self._last_state

    # ─── Utility ──────────────────────────────────────

    def detect_and_tap(
        self,
        label: str,
        screenshot: np.ndarray,
        adb,
        humanizer=None,
        conf: float = 0.3,
    ) -> bool:
        """
        Detect element and tap it.
        
        Args:
            label: Element to find and tap
            screenshot: Current screen image
            adb: ADB controller instance
            humanizer: Optional humanizer for anti-ban delays
            conf: Minimum confidence
            
        Returns:
            True if element was found and tapped
        """
        detection = self.find(label, screenshot, conf)
        if detection is None:
            log.debug(f"'{label}' not found on screen")
            return False

        # Apply random offset for anti-ban
        offset_x = np.random.randint(-3, 4)
        offset_y = np.random.randint(-3, 4)
        tap_x = detection.cx + offset_x
        tap_y = detection.cy + offset_y

        log.info(f"Tapping '{label}' at ({tap_x},{tap_y}) conf={detection.confidence:.2f}")

        if humanizer:
            humanizer.random_delay()

        adb.tap(tap_x, tap_y)
        return True

    def wait_for(
        self,
        label: str,
        adb,
        timeout: float = 10.0,
        interval: float = 0.5,
        conf: float = 0.3,
    ) -> Optional[Detection]:
        """
        Wait for an element to appear on screen.
        
        Args:
            label: Element to wait for
            adb: ADB controller (for screenshots)
            timeout: Max wait time in seconds
            interval: Check interval in seconds
            conf: Minimum confidence
            
        Returns:
            Detection if found, None if timeout
        """
        start = time.time()
        while (time.time() - start) < timeout:
            screenshot = self._take_screenshot(adb)
            if screenshot is None:
                time.sleep(interval)
                continue

            detection = self.find(label, screenshot, conf)
            if detection:
                return detection

            time.sleep(interval)

        log.warning(f"Timeout waiting for '{label}' ({timeout}s)")
        return None

    def _take_screenshot(self, adb) -> Optional[np.ndarray]:
        """Take screenshot via ADB and convert to OpenCV format."""
        try:
            png_bytes = adb.screenshot()
            if not png_bytes:
                return None
            arr = np.frombuffer(png_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            log.error(f"Screenshot failed: {e}")
            return None

    def debug_save(
        self,
        screenshot: np.ndarray,
        state: Optional[ScreenState] = None,
        save_path: str = "debug_detection.jpg",
    ) -> str:
        """
        Save screenshot with detection boxes drawn (for debugging).
        
        Args:
            screenshot: Original screenshot
            state: ScreenState (if None, runs detection)
            save_path: Output file path
            
        Returns:
            Path to saved image
        """
        if state is None:
            state = self.detect(screenshot)

        img = screenshot.copy()

        for det in state.detections:
            # Color by confidence: green (high) → red (low)
            g = int(det.confidence * 255)
            r = int((1 - det.confidence) * 255)
            color = (0, g, r)

            # Draw box
            cv2.rectangle(img, (det.x1, det.y1), (det.x2, det.y2), color, 2)

            # Draw label
            label_text = f"{det.label} {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img, (det.x1, det.y1 - th - 8), (det.x1 + tw, det.y1), color, -1)
            cv2.putText(img, label_text, (det.x1, det.y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Draw screen name
        cv2.putText(img, f"Screen: {state.screen_name} ({state.inference_ms:.1f}ms)",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imwrite(save_path, img)
        log.info(f"Debug image saved: {save_path}")
        return save_path


# ─── Hybrid Detector (YOLO + Template Fallback) ──────────

class HybridDetector:
    """
    Combines YOLO detection with template matching fallback.
    Uses YOLO first (fast), falls back to templates if element not found.
    """

    def __init__(
        self,
        yolo: YOLODetector,
        vision=None,  # Legacy Vision/template matching module
        yolo_conf: float = 0.3,
        template_threshold: float = 0.80,
    ):
        self.yolo = yolo
        self.vision = vision
        self.yolo_conf = yolo_conf
        self.template_threshold = template_threshold
        self._stats = {"yolo_hits": 0, "template_hits": 0, "misses": 0}

    def find(
        self,
        label: str,
        screenshot: np.ndarray,
        template_name: Optional[str] = None,
    ) -> Optional[Detection]:
        """
        Find element using YOLO first, template matching as fallback.
        
        Args:
            label: YOLO class name
            screenshot: OpenCV image
            template_name: Optional template filename for fallback
        """
        # Try YOLO first
        if self.yolo.is_ready:
            det = self.yolo.find(label, screenshot, self.yolo_conf)
            if det:
                self._stats["yolo_hits"] += 1
                return det

        # Fallback to template matching
        if self.vision and template_name:
            match = self.vision.find_template(template_name, self.template_threshold, screenshot)
            if match:
                self._stats["template_hits"] += 1
                return Detection(
                    label=label,
                    confidence=match.confidence,
                    x1=match.x, y1=match.y,
                    x2=match.x + match.width, y2=match.y + match.height,
                )

        self._stats["misses"] += 1
        return None

    def detect_screen(self, screenshot: np.ndarray) -> ScreenState:
        """Detect screen using YOLO."""
        if self.yolo.is_ready:
            return self.yolo.detect(screenshot)
        return ScreenState(screen_name="unknown", timestamp=time.time())

    @property
    def stats(self) -> Dict:
        """Get detection statistics."""
        total = sum(self._stats.values())
        return {
            **self._stats,
            "total": total,
            "yolo_rate": self._stats["yolo_hits"] / max(total, 1) * 100,
        }
