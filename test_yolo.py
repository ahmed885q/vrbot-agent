"""
Quick test — Verify YOLO model loads and detects on a screenshot.

Usage:
    python test_yolo.py
    python test_yolo.py path/to/screenshot.png
"""

import sys
import os
import time

# Add parent dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yolo_detector import YOLODetector


def main():
    print("=" * 50)
    print("  VRBOT — YOLOv8 Detection Test")
    print("=" * 50)

    # Load model
    detector = YOLODetector()

    if not detector.is_ready:
        print("❌ Model not loaded! Check models/best.pt exists")
        return

    print(f"\n✅ Model loaded with {len(detector.class_names)} classes:")
    for i, name in enumerate(detector.class_names):
        print(f"   {i}: {name}")

    # Test on screenshot if provided
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
    else:
        # Try to find any screenshot
        screenshot_dirs = [
            "screenshots",
            "dataset/screenshots",
            os.path.expanduser("~/vrbot-agent/screenshots"),
        ]
        img_path = None
        for d in screenshot_dirs:
            if os.path.exists(d):
                files = [f for f in os.listdir(d) if f.endswith(('.png', '.jpg'))]
                if files:
                    img_path = os.path.join(d, files[0])
                    break

    if img_path and os.path.exists(img_path):
        import cv2
        print(f"\n🖼️ Testing on: {img_path}")
        img = cv2.imread(img_path)

        # Run detection
        state = detector.detect(img)

        print(f"\n⏱️ Inference: {state.inference_ms:.1f}ms")
        print(f"📱 Screen: {state.screen_name}")
        print(f"🎯 Detections ({len(state.detections)}):")

        for det in state.detections:
            print(f"   {det.label:30s} conf={det.confidence:.2f}  center=({det.cx},{det.cy})")

        # Save debug image
        debug_path = detector.debug_save(img, state, "test_detection_result.jpg")
        print(f"\n💾 Debug image: {debug_path}")
    else:
        print("\n⚠️ No screenshot found to test.")
        print("  Run: python test_yolo.py path/to/screenshot.png")

    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
