"""
VRBOT Captcha Detection & Handling
===================================
Inspired by ROK Bot's pass verification system and OSROKBOT's captcha detection.
Monitors for game verification/captcha popups and handles them gracefully.

Features:
- Template matching for known captcha/verification UI elements
- YOLO-based detection as backup
- Auto-pause bot when captcha detected
- Email/webhook notification support
- Manual resolution timeout with auto-retry
- Captcha frequency tracking for anti-ban tuning

Integration: Used by state_machine.py and task_scheduler.py
"""

import time
import logging
import threading
import json
from enum import Enum, auto
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("vrbot.captcha")


class CaptchaType(Enum):
    """Types of verification/captcha in Viking Rise."""
    SLIDER = auto()          # Slide puzzle verification
    IMAGE_SELECT = auto()    # Select correct images
    POPUP_VERIFY = auto()    # Simple "verify you're human" popup
    BEHAVIOR_CHECK = auto()  # Game detects bot-like behavior
    UNKNOWN = auto()


class CaptchaAction(Enum):
    """What to do when captcha is detected."""
    PAUSE_AND_NOTIFY = auto()    # Pause bot, send notification
    AUTO_SOLVE = auto()          # Try to solve automatically (2captcha etc)
    SKIP_TASK = auto()           # Skip current task, continue others
    RESTART_GAME = auto()        # Restart game and hope captcha clears


@dataclass
class CaptchaEvent:
    """Record of a captcha occurrence."""
    timestamp: float
    captcha_type: CaptchaType
    task_name: str
    farm_id: str
    resolved: bool = False
    resolution_time: float = 0
    resolution_method: str = ""
    screenshot_path: str = ""


class CaptchaDetector:
    """
    Monitors game screen for captcha/verification elements.
    
    Usage:
        detector = CaptchaDetector(adb_controller, vision_engine)
        detector.on_captcha = my_callback
        
        # In your main loop:
        if detector.check(screenshot):
            # Captcha detected! Bot should pause.
            pass
    """

    # Known verification UI indicators in Viking Rise
    # These are relative regions where verification popups typically appear
    VERIFICATION_REGIONS = {
        'center_popup': (0.2, 0.2, 0.8, 0.8),   # Center of screen
        'top_banner': (0.1, 0.0, 0.9, 0.15),     # Top notification area
        'bottom_popup': (0.1, 0.7, 0.9, 1.0),    # Bottom popup area
    }

    # Template names for captcha detection (stored in templates/ folder)
    CAPTCHA_TEMPLATES = [
        'verify_popup.png',
        'slider_track.png',
        'captcha_title.png',
        'human_verify.png',
        'security_check.png',
        'behavior_warning.png',
    ]

    def __init__(self, adb_controller=None, vision_engine=None, config: Dict = None):
        self.adb = adb_controller
        self.vision = vision_engine
        self.config = config or {}
        
        # Detection settings
        self.enabled = True
        self.check_interval = self.config.get('captcha_check_interval', 5)  # seconds
        self.confidence_threshold = self.config.get('captcha_confidence', 0.75)
        self.last_check_time = 0
        
        # State
        self.captcha_active = False
        self.current_captcha: Optional[CaptchaEvent] = None
        self.history: List[CaptchaEvent] = []
        
        # Callbacks
        self.on_captcha: Optional[Callable[[CaptchaEvent], None]] = None
        self.on_resolved: Optional[Callable[[CaptchaEvent], None]] = None
        
        # Notification settings
        self.notify_webhook: Optional[str] = self.config.get('captcha_webhook_url')
        self.notify_email: Optional[str] = self.config.get('captcha_notify_email')
        
        # Anti-ban metrics
        self.detection_count_1h = 0
        self.detection_count_24h = 0
        self._cleanup_thread = None
        
        logger.info("CaptchaDetector initialized")

    def check(self, screenshot=None, task_name: str = "", farm_id: str = "") -> bool:
        """
        Check current screen for captcha. 
        Returns True if captcha detected.
        
        Args:
            screenshot: Current game screenshot (numpy array or PIL Image)
            task_name: Name of currently running task
            farm_id: ID of current farm
        """
        if not self.enabled:
            return False
            
        # Rate limit checks
        now = time.time()
        if now - self.last_check_time < self.check_interval:
            return self.captcha_active  # Return last known state
        self.last_check_time = now
        
        # If no screenshot provided, take one
        if screenshot is None and self.adb:
            try:
                screenshot = self.adb.screenshot()
            except Exception as e:
                logger.error(f"Failed to take screenshot for captcha check: {e}")
                return False
        
        if screenshot is None:
            return False
        
        detected = False
        captcha_type = CaptchaType.UNKNOWN
        confidence = 0.0
        
        # Method 1: Template matching (fast, reliable for known captchas)
        result = self._check_templates(screenshot)
        if result:
            detected = True
            captcha_type = result['type']
            confidence = result['confidence']
        
        # Method 2: YOLO detection (for unknown captcha types)
        if not detected and self.vision:
            result = self._check_yolo(screenshot)
            if result:
                detected = True
                captcha_type = result['type']
                confidence = result['confidence']
        
        # Method 3: Heuristic checks (unusual UI elements)
        if not detected:
            result = self._check_heuristics(screenshot)
            if result:
                detected = True
                captcha_type = result['type']
                confidence = result['confidence']
        
        if detected and not self.captcha_active:
            self._on_captcha_detected(captcha_type, confidence, task_name, farm_id, screenshot)
        
        return detected

    def _check_templates(self, screenshot) -> Optional[Dict]:
        """Check for known captcha templates using OpenCV template matching."""
        try:
            import cv2
            import numpy as np
            
            if not isinstance(screenshot, np.ndarray):
                # Convert PIL to numpy if needed
                screenshot = np.array(screenshot)
            
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY) if len(screenshot.shape) == 3 else screenshot
            
            templates_dir = Path(__file__).parent / 'templates' / 'captcha'
            if not templates_dir.exists():
                return None
            
            for template_name in self.CAPTCHA_TEMPLATES:
                template_path = templates_dir / template_name
                if not template_path.exists():
                    continue
                    
                template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
                if template is None:
                    continue
                
                result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                
                if max_val >= self.confidence_threshold:
                    logger.info(
                        f"Captcha template match: {template_name} "
                        f"(confidence: {max_val:.3f}, location: {max_loc})"
                    )
                    # Determine type from template name
                    if 'slider' in template_name:
                        ctype = CaptchaType.SLIDER
                    elif 'behavior' in template_name:
                        ctype = CaptchaType.BEHAVIOR_CHECK
                    else:
                        ctype = CaptchaType.POPUP_VERIFY
                    
                    return {'type': ctype, 'confidence': max_val, 'location': max_loc}
            
            return None
            
        except ImportError:
            logger.warning("OpenCV not available for template matching")
            return None
        except Exception as e:
            logger.error(f"Template check error: {e}")
            return None

    def _check_yolo(self, screenshot) -> Optional[Dict]:
        """Check for captcha using YOLO model (if available)."""
        try:
            if not self.vision or not hasattr(self.vision, 'detect'):
                return None
            
            detections = self.vision.detect(screenshot)
            
            # Look for captcha-related labels
            captcha_labels = ['captcha', 'verify', 'verification', 'slider', 'puzzle']
            for det in detections:
                label = det.get('label', '').lower()
                conf = det.get('confidence', 0)
                
                if any(cl in label for cl in captcha_labels) and conf >= self.confidence_threshold:
                    return {
                        'type': CaptchaType.UNKNOWN,
                        'confidence': conf,
                        'detection': det
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"YOLO captcha check error: {e}")
            return None

    def _check_heuristics(self, screenshot) -> Optional[Dict]:
        """
        Heuristic checks for unusual UI elements that might indicate captcha.
        Checks for:
        - Unusual darkened overlay (popup background)
        - New UI elements in center of screen
        - Game frozen/unresponsive indicators
        """
        try:
            import cv2
            import numpy as np
            
            if not isinstance(screenshot, np.ndarray):
                screenshot = np.array(screenshot)
            
            h, w = screenshot.shape[:2]
            
            # Check center region for dark overlay (common for popups)
            center = screenshot[h//4:3*h//4, w//4:3*w//4]
            mean_brightness = np.mean(center)
            
            # If center is significantly darker than edges, might be a popup overlay
            edges = np.concatenate([
                screenshot[:h//4, :].flatten(),
                screenshot[3*h//4:, :].flatten()
            ])
            edge_brightness = np.mean(edges)
            
            if mean_brightness < edge_brightness * 0.5 and edge_brightness > 50:
                # Dark overlay detected - possible popup
                # Additional check: look for button-like elements in center
                center_gray = cv2.cvtColor(center, cv2.COLOR_BGR2GRAY) if len(center.shape) == 3 else center
                _, binary = cv2.threshold(center_gray, 200, 255, cv2.THRESH_BINARY)
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Filter for button-sized contours
                button_contours = [
                    c for c in contours 
                    if 1000 < cv2.contourArea(c) < 50000
                    and 1.5 < cv2.boundingRect(c)[2] / max(cv2.boundingRect(c)[3], 1) < 5
                ]
                
                if len(button_contours) >= 1:
                    logger.info(f"Heuristic captcha detection: dark overlay with {len(button_contours)} button(s)")
                    return {
                        'type': CaptchaType.UNKNOWN,
                        'confidence': 0.6,
                        'method': 'heuristic_overlay'
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Heuristic check error: {e}")
            return None

    def _on_captcha_detected(self, captcha_type: CaptchaType, confidence: float,
                               task_name: str, farm_id: str, screenshot=None):
        """Handle captcha detection."""
        self.captcha_active = True
        
        event = CaptchaEvent(
            timestamp=time.time(),
            captcha_type=captcha_type,
            task_name=task_name,
            farm_id=farm_id,
        )
        
        # Save screenshot
        if screenshot is not None:
            try:
                import cv2
                import numpy as np
                screenshots_dir = Path(__file__).parent / 'screenshots' / 'captcha'
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                fname = f"captcha_{int(event.timestamp)}_{farm_id}.png"
                path = screenshots_dir / fname
                if isinstance(screenshot, np.ndarray):
                    cv2.imwrite(str(path), screenshot)
                event.screenshot_path = str(path)
            except Exception as e:
                logger.error(f"Failed to save captcha screenshot: {e}")
        
        self.current_captcha = event
        self.history.append(event)
        self.detection_count_1h += 1
        self.detection_count_24h += 1
        
        logger.critical(
            f"🚨 CAPTCHA DETECTED! Type: {captcha_type.name}, "
            f"Confidence: {confidence:.2f}, Task: {task_name}, Farm: {farm_id}"
        )
        
        # Send notifications
        self._send_notification(event)
        
        # Fire callback
        if self.on_captcha:
            self.on_captcha(event)

    def resolve(self, method: str = "manual"):
        """Mark current captcha as resolved."""
        if self.current_captcha:
            self.current_captcha.resolved = True
            self.current_captcha.resolution_time = time.time() - self.current_captcha.timestamp
            self.current_captcha.resolution_method = method
            
            logger.info(
                f"✅ Captcha resolved ({method}) in "
                f"{self.current_captcha.resolution_time:.1f}s"
            )
            
            if self.on_resolved:
                self.on_resolved(self.current_captcha)
        
        self.captcha_active = False
        self.current_captcha = None

    def _send_notification(self, event: CaptchaEvent):
        """Send captcha notification via webhook or email."""
        # Webhook notification (Discord, Telegram, etc.)
        if self.notify_webhook:
            try:
                import requests
                payload = {
                    "content": (
                        f"🚨 **VRBOT Captcha Alert**\n"
                        f"Farm: {event.farm_id}\n"
                        f"Task: {event.task_name}\n"
                        f"Type: {event.captcha_type.name}\n"
                        f"Time: {time.strftime('%H:%M:%S', time.localtime(event.timestamp))}"
                    )
                }
                threading.Thread(
                    target=lambda: requests.post(self.notify_webhook, json=payload, timeout=10),
                    daemon=True
                ).start()
            except Exception as e:
                logger.error(f"Webhook notification failed: {e}")

    def get_stats(self) -> Dict:
        """Get captcha detection statistics for anti-ban tuning."""
        now = time.time()
        
        # Clean up old events
        recent_1h = [e for e in self.history if now - e.timestamp < 3600]
        recent_24h = [e for e in self.history if now - e.timestamp < 86400]
        
        avg_resolution = 0
        resolved = [e for e in self.history if e.resolved]
        if resolved:
            avg_resolution = sum(e.resolution_time for e in resolved) / len(resolved)
        
        return {
            "total_detections": len(self.history),
            "last_1h": len(recent_1h),
            "last_24h": len(recent_24h),
            "currently_active": self.captcha_active,
            "avg_resolution_time": round(avg_resolution, 1),
            "captcha_types": {
                ct.name: len([e for e in self.history if e.captcha_type == ct])
                for ct in CaptchaType
            }
        }

    def get_risk_level(self) -> str:
        """
        Assess anti-ban risk based on captcha frequency.
        Returns: 'low', 'medium', 'high', 'critical'
        """
        stats = self.get_stats()
        hourly = stats['last_1h']
        daily = stats['last_24h']
        
        if hourly >= 3 or daily >= 10:
            return 'critical'
        elif hourly >= 2 or daily >= 5:
            return 'high'
        elif hourly >= 1 or daily >= 3:
            return 'medium'
        return 'low'


# ─────────────────────────────────────────────
# Captcha-aware screen checker (used in tasks)
# ─────────────────────────────────────────────

class ScreenGuard:
    """
    Lightweight screen checker that integrates into any task.
    Checks for captchas and other unexpected popups.
    
    Usage:
        guard = ScreenGuard(captcha_detector)
        
        # In your task loop:
        if guard.is_safe(screenshot):
            # Proceed with task
            pass
        else:
            # Captcha or unexpected popup - handle it
            guard.handle_interruption()
    """

    def __init__(self, captcha_detector: CaptchaDetector):
        self.detector = captcha_detector
        self.last_known_good_state = None
        self.interruption_count = 0

    def is_safe(self, screenshot=None, task_name: str = "", farm_id: str = "") -> bool:
        """Check if screen is safe to proceed with task."""
        if self.detector.captcha_active:
            return False
        return not self.detector.check(screenshot, task_name, farm_id)

    def handle_interruption(self, adb=None):
        """Try to handle non-captcha interruptions (ads, popups, etc.)."""
        self.interruption_count += 1
        if adb:
            # Try pressing back to dismiss popup
            adb.press_back()
            time.sleep(1)
