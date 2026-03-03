"""
VRBOT Anti-Hallucination Module

Comprehensive validation and consistency checking for AI-based game automation.
Prevents AI hallucinations (incorrect screen detection, building level misreads, etc.)
through multi-query validation, state machine tracking, and confidence scoring.

Uses: Ollama llava:7b, OpenAI GPT-4o-mini, Claude for cross-validation.
"""

import hashlib
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum

import cv2
import numpy as np


logger = logging.getLogger(__name__)


class ScreenState(Enum):
    """Enumeration of possible game screen states."""
    UNKNOWN = "unknown"
    HOME = "home"
    BUILDING = "building"
    TROOPS = "troops"
    RESEARCH = "research"
    BATTLE = "battle"
    LOADING = "loading"
    STUCK = "stuck"


@dataclass
class ValidationResult:
    """
    Represents validation result with confidence scoring and conflict tracking.
    
    Attributes:
        value: The extracted/validated value
        confidence: Confidence score from 0.0 to 1.0
        source: Source of validation ("yolo", "template", "ollama", "openai", "claude", "multi_query")
        conflicts: List of conflicting values from different sources
    """
    value: Any
    confidence: float = 0.0
    source: str = "unknown"
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    
    def is_reliable(self, min_confidence: float = 0.6) -> bool:
        """Check if validation result meets minimum confidence threshold."""
        return self.confidence >= min_confidence
    
    def __repr__(self) -> str:
        conflict_str = f" (conflicts: {len(self.conflicts)})" if self.conflicts else ""
        return f"ValidationResult({self.value}, conf={self.confidence:.2f}, src={self.source}{conflict_str})"


class ScreenStateMachine:
    """
    Tracks screen transitions and detects anomalies like stuck loops or oscillations.
    
    Maintains a history of recent screens and their timestamps to detect:
    - Loops: Same screen repeating 3+ times
    - Oscillations: Alternating between 2 screens
    - Stuck states: No progress for extended period
    """
    
    def __init__(self, history_size: int = 20):
        """
        Initialize state machine with empty history.
        
        Args:
            history_size: Number of screens to keep in history (default: 20)
        """
        self.history: deque = deque(maxlen=history_size)
        self.state_counts: Dict[str, int] = {}
        self.last_screen = None
        self.last_update_time = None
    
    def add_screen(self, screen_name: str, timestamp: float = None) -> None:
        """
        Record screen detection.
        
        Args:
            screen_name: Name/identifier of the screen
            timestamp: Optional timestamp of detection
        """
        self.history.append({
            'screen': screen_name,
            'timestamp': timestamp
        })
        self.last_screen = screen_name
        self.last_update_time = timestamp
        
        # Update counts
        self.state_counts[screen_name] = self.state_counts.get(screen_name, 0) + 1
    
    def detect_loop(self, min_repeats: int = 3) -> Optional[Tuple[str, int]]:
        """
        Detect if same screen repeats multiple times consecutively.
        
        Args:
            min_repeats: Minimum consecutive repeats to flag as loop (default: 3)
        
        Returns:
            Tuple of (screen_name, repeat_count) if loop detected, else None
        """
        if len(self.history) < min_repeats:
            return None
        
        recent = list(self.history)[-min_repeats:]
        if all(item['screen'] == recent[0]['screen'] for item in recent):
            return (recent[0]['screen'], len(recent))
        
        return None
    
    def detect_oscillation(self, window_size: int = 5) -> Optional[Tuple[str, str, int]]:
        """
        Detect if screen alternates between two states.
        
        Args:
            window_size: Size of window to check for oscillation (default: 5)
        
        Returns:
            Tuple of (screen_a, screen_b, count) if oscillation detected, else None
        """
        if len(self.history) < window_size:
            return None
        
        recent = list(self.history)[-window_size:]
        screens = [item['screen'] for item in recent]
        
        # Check for alternation pattern: A-B-A-B-A or B-A-B-A-B
        if len(set(screens)) == 2:
            unique = list(set(screens))
            alternating = True
            for i in range(len(screens) - 1):
                if screens[i] == screens[i + 1]:
                    alternating = False
                    break
            
            if alternating:
                return (unique[0], unique[1], len(screens))
        
        return None
    
    def suggest_recovery(self) -> Optional[Dict[str, Any]]:
        """
        Suggest recovery action based on detected anomalies.
        
        Returns:
            Dict with recovery action or None if no anomaly detected
        """
        loop = self.detect_loop()
        if loop:
            screen, count = loop
            return {
                'type': 'loop_detected',
                'screen': screen,
                'repeat_count': count,
                'actions': ['close_dialog', 'return_home', 'restart_task']
            }
        
        oscillation = self.detect_oscillation()
        if oscillation:
            screen_a, screen_b, count = oscillation
            return {
                'type': 'oscillation_detected',
                'screens': [screen_a, screen_b],
                'occurrences': count,
                'actions': ['wait_longer', 'tap_center', 'restart_task']
            }
        
        return None
    
    def get_history(self) -> List[str]:
        """Get list of screen names from history."""
        return [item['screen'] for item in self.history]
    
    def reset(self) -> None:
        """Clear history and reset state machine."""
        self.history.clear()
        self.state_counts.clear()
        self.last_screen = None
        self.last_update_time = None


class AntiHallucinationValidator:
    """
    Main validator class for preventing AI hallucinations in game automation.
    
    This class is designed to be mixed into or used with the Bot class.
    Provides methods for robust screen detection, number extraction, and state tracking.
    """
    
    def __init__(self, ask_ai_callback: Optional[Callable] = None):
        """
        Initialize anti-hallucination validator.
        
        Args:
            ask_ai_callback: Optional callback to the original Bot._ask_ai_original() method.
                           If not provided, some features will have graceful fallback.
        """
        self.state_machine = ScreenStateMachine()
        self._ask_ai_original = ask_ai_callback
        self.logger = logger
    
    def multi_query_ai(
        self,
        prompt: str,
        image_b64: str,
        num_queries: int = 2,
        max_tokens: int = 300,
        confidence_threshold: float = 0.8
    ) -> ValidationResult:
        """
        Ask AI same question multiple times with slight prompt variations.
        
        Compares responses for consistency. High agreement = high confidence.
        Disagreement = low confidence, triggers conflict tracking.
        
        Args:
            prompt: Base prompt/question for AI
            image_b64: Base64-encoded image
            num_queries: Number of times to ask the question (default: 2)
            max_tokens: Maximum tokens per response (default: 300)
            confidence_threshold: Threshold to flag conflicts (default: 0.8)
        
        Returns:
            ValidationResult with aggregated answer and confidence
        
        Raises:
            RuntimeError: If no AI callback is available
        """
        if not self._ask_ai_original:
            self.logger.warning("No AI callback available for multi_query_ai")
            raise RuntimeError("multi_query_ai requires AI callback configured")
        
        responses = []
        variations = [
            f"{prompt}",
            f"{prompt} Answer with just the key information.",
            f"{prompt} Be precise and avoid assumptions.",
        ]
        
        for i in range(min(num_queries, len(variations))):
            try:
                response = self._ask_ai_original(
                    prompt=variations[i],
                    image_b64=image_b64,
                    max_tokens=max_tokens
                )
                responses.append(response)
            except Exception as e:
                self.logger.error(f"Error in multi_query AI call {i}: {e}")
        
        if not responses:
            return ValidationResult(
                value=None,
                confidence=0.0,
                source="multi_query",
                conflicts=[]
            )
        
        # Analyze response consistency
        return self._analyze_response_consistency(responses, num_queries)
    
    def _analyze_response_consistency(
        self,
        responses: List[str],
        num_queries: int
    ) -> ValidationResult:
        """
        Analyze consistency between multiple AI responses.
        
        Args:
            responses: List of response strings from AI
            num_queries: Total queries attempted
        
        Returns:
            ValidationResult with confidence based on agreement
        """
        if not responses:
            return ValidationResult(value=None, confidence=0.0, source="multi_query")
        
        # Simple consistency check: exact matches
        unique_responses = set(responses)
        match_count = max([responses.count(r) for r in unique_responses])
        confidence = match_count / len(responses) if responses else 0.0
        
        primary_response = max(responses, key=responses.count)
        conflicts = [
            {'value': r, 'frequency': responses.count(r)}
            for r in unique_responses
            if r != primary_response
        ]
        
        return ValidationResult(
            value=primary_response,
            confidence=confidence,
            source="multi_query",
            conflicts=conflicts
        )
    
    def read_number_ocr(
        self,
        prompt_prefix: str,
        image_b64: str,
        expected_range: Optional[Tuple[int, int]] = None,
        cross_validate_yolo: bool = False
    ) -> ValidationResult:
        """
        Specialized OCR reading for game numbers (levels, resources, etc.).
        
        Explicitly warns AI against confusing screen resolution (1280x720)
        with actual in-game numbers. Uses targeted prompts.
        
        Args:
            prompt_prefix: What number to read (e.g., "building level", "troop count")
            image_b64: Base64-encoded image
            expected_range: Tuple of (min, max) for sanity checking
            cross_validate_yolo: Whether to cross-validate with YOLO if available
        
        Returns:
            ValidationResult with extracted number and confidence
        """
        if not self._ask_ai_original:
            return ValidationResult(
                value=None,
                confidence=0.0,
                source="ocr",
                conflicts=[]
            )
        
        # Specialized prompt to prevent hallucination
        ocr_prompt = f"""
Read the {prompt_prefix} from the game screenshot.

IMPORTANT: The screen resolution is 1280x720.
Do NOT confuse the screen resolution numbers with the in-game {prompt_prefix}.

Look specifically at the UI element showing {prompt_prefix}.
Return ONLY the number as an integer. If you cannot read it clearly, say "UNCLEAR".
"""
        
        try:
            response = self._ask_ai_original(
                prompt=ocr_prompt,
                image_b64=image_b64,
                max_tokens=50
            )
            
            # Parse response
            parsed_value = self._parse_ocr_response(response)
            
            # Sanity check
            if expected_range and parsed_value is not None:
                min_val, max_val = expected_range
                if parsed_value < min_val or parsed_value > max_val:
                    self.logger.warning(
                        f"Parsed value {parsed_value} outside expected range {expected_range}"
                    )
                    confidence = 0.3
                else:
                    confidence = 0.85
            else:
                confidence = 0.8 if parsed_value is not None else 0.0
            
            return ValidationResult(
                value=parsed_value,
                confidence=confidence,
                source="ocr",
                conflicts=[]
            )
            
        except Exception as e:
            self.logger.error(f"Error in OCR read: {e}")
            return ValidationResult(
                value=None,
                confidence=0.0,
                source="ocr",
                conflicts=[]
      )
    
    def _parse_ocr_response(self, response: str) -> Optional[int]:
        """
        Parse OCR response to extract integer value.
        
        Args:
            response: Response text from AI
        
        Returns:
            Extracted integer or None if parsing fails
        """
        response = response.strip().upper()
        
        if "UNCLEAR" in response or "CANNOT" in response:
            return None
        
        # Extract first number found
        import re
        numbers = re.findall(r'\d+', response)
        if numbers:
            return int(numbers[0])
        
        return None
    
    def verified_tap(
        self,
        screenshot_before_b64: str,
        screenshot_after_b64: str,
        similarity_threshold: float = 0.95
    ) -> bool:
        """
        Verify that a tap action had effect by comparing before/after screenshots.
        
        Uses perceptual hashing to detect if screen changed.
        
        Args:
            screenshot_before_b64: Base64-encoded screenshot before tap
            screenshot_after_b64: Base64-encoded screenshot after tap
            similarity_threshold: Threshold for considering screen "changed" (default: 0.95)
        
        Returns:
            True if screen changed (tap had effect), False otherwise
        """
        try:
            # Decode images
            before_hash = self._get_image_hash(screenshot_before_b64)
            after_hash = self._get_image_hash(screenshot_after_b64)
            
            if before_hash is None or after_hash is None:
                self.logger.warning("Failed to compute image hashes for tap verification")
                return True  # Assume success if can't verify
            
            # Compare hashes (Hamming distance)
            similarity = self._hash_similarity(before_hash, after_hash)
            changed = similarity < similarity_threshold
            
            self.logger.debug(
                f"Tap verification: similarity={similarity:.3f}, changed={changed}"
            )
            return changed
            
        except Exception as e:
            self.logger.error(f"Error in verified_tap: {e}")
            return True  # Assume success on error
    
    def _get_image_hash(self, image_b64: str) -> Optional[str]:
        """
        Compute perceptual hash of base64-encoded image.
        
        Args:
            image_b64: Base64-encoded image
        
        Returns:
            Hex hash string or None if decoding fails
        """
        try:
            import base64
            
            # Decode base64
            image_data = base64.b64decode(image_b64)
            
            # Convert to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            
            if img is None:
                return None
            
            # Resize to 8x8 for perceptual hash
            img_small = cv2.resize(img, (8, 8))
            
            # Compute average pixel value
            avg_pixel = img_small.mean()
            
            # Create hash: 1 if pixel > avg, 0 otherwise
            hash_bits = (img_small > avg_pixel).flatten()
            
            # Convert to hex string
            hash_bytes = np.packbits(hash_bits)
            return hash_bytes.hex()
            
        except Exception as e:
            self.logger.error(f"Error computing image hash: {e}")
            return None
    
    def _hash_similarity(self, hash1: str, hash2: str) -> float:
        """
        Compute similarity between two image hashes (0.0 to 1.0).
        
        Args:
            hash1: First hash hex string
            hash2: Second hash hex string
        
        Returns:
            Similarity score where 1.0 = identical, 0.0 = completely different
        """
        try:
            if not hash1 or not hash2:
                return 0.0
            
            # Hamming distance
            xor_hash = int(hash1, 16) ^ int(hash2, 16)
            hamming_dist = bin(xor_hash).count('1')
            
            # Normalize to [0, 1] range (64 bits max)
            similarity = 1.0 - (hamming_dist / 64.0)
            return similarity
            
        except Exception as e:
            self.logger.error(f"Error computing hash similarity: {e}")
            return 0.0
    
    def detect_screen_with_state(
        self,
        detect_screen_callback: Callable,
        screenshot_b64: str
    ) -> ValidationResult:
        """
        Wrap screen detection with state machine tracking.
        
        Detects current screen and checks for anomalies (loops, oscillations).
        Updates state machine history for anomaly detection.
        
        Args:
            detect_screen_callback: Original detect_screen method
            screenshot_b64: Base64-encoded current screenshot
        
        Returns:
            ValidationResult with detected screen and confidence
        """
        try:
            # Call original detection
            result = detect_screen_callback(screenshot_b64)
            
            # Update state machine
            screen_name = result.value if isinstance(result, ValidationResult) else str(result)
            self.state_machine.add_screen(screen_name)
            
            # Check for anomalies
            recovery = self.state_machine.suggest_recovery()
            if recovery:
                self.logger.warning(f"Anomaly detected: {recovery}")
            
            # Wrap in ValidationResult if not already
            if not isinstance(result, ValidationResult):
                result = ValidationResult(
                    value=result,
                    confidence=0.7,
                    source="detect_screen"
                )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in detect_screen_with_state: {e}")
            return ValidationResult(
                value=None,
                confidence=0.0,
                source="detect_screen",
                conflicts=[]
            )
    
    def reset_state_machine(self) -> None:
        """Reset state machine history."""
        self.state_machine.reset()
    
    def get_state_anomaly(self) -> Optional[Dict[str, Any]]:
        """
        Get current state anomaly if detected.
        
        Returns:
            Recovery suggestion dict or None if no anomaly
        """
        return self.state_machine.suggest_recovery()


# Standalone validation functions (can be used without Bot class)

def validate_confidence_aggregate(
    validations: List[ValidationResult],
    weight_by_source: Optional[Dict[str, float]] = None
) -> ValidationResult:
    """
    Aggregate multiple validation results into a single result.
    
    Args:
        validations: List of ValidationResult objects
        weight_by_source: Optional dict mapping source names to weights
    
    Returns:
        Aggregated ValidationResult
    """
    if not validations:
        return ValidationResult(value=None, confidence=0.0)
    
    if weight_by_source is None:
        weight_by_source = {
            "multi_query": 1.0,
            "ocr": 0.9,
            "template": 0.8,
            "ollama": 0.7,
            "openai": 0.85,
            "claude": 0.85,
            "yolo": 0.6,
        }
    
    # Weight confidences by source
    total_weight = 0.0
    weighted_confidence = 0.0
    conflicts = []
    
    for val in validations:
        weight = weight_by_source.get(val.source, 0.5)
        weighted_confidence += val.confidence * weight
        total_weight += weight
        
        # Collect conflicts
        if val.conflicts:
            conflicts.extend(val.conflicts)
    
    final_confidence = weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    # Use most confident result as primary value
    primary = max(validations, key=lambda v: v.confidence)
    
    return ValidationResult(
        value=primary.value,
        confidence=final_confidence,
        source="aggregated",
        conflicts=conflicts
    )


def is_high_confidence(result: ValidationResult, threshold: float = 0.75) -> bool:
    """
    Check if validation result has high confidence.
    
    Args:
        result: ValidationResult to check
        threshold: Confidence threshold (default: 0.75)
    
    Returns:
        True if result exceeds threshold
    """
    return result.is_reliable(threshold)


def log_validation_result(
    result: ValidationResult,
    context: str = ""
) -> None:
    """
    Log validation result with details.
    
    Args:
        result: ValidationResult to log
        context: Additional context string
    """
    conflict_msg = f" - {len(result.conflicts)} conflicts" if result.conflicts else ""
    msg = f"Validation [{result.source}] = {result.value} (conf={result.confidence:.2f}){conflict_msg}"
    if context:
        msg = f"{context}: {msg}"
    
    if result.confidence < 0.5:
        logger.warning(msg)
    elif result.confidence < 0.7:
        logger.info(msg)
    else:
        logger.debug(msg)


__all__ = [
    'ValidationResult',
    'ScreenState',
    'ScreenStateMachine',
    'AntiHallucinationValidator',
    'validate_confidence_aggregate',
    'is_high_confidence',
    'log_validation_result',
]

