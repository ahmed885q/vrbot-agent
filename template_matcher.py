"""
VRBOT Template Matcher v1.0
============================
Fast OpenCV template matching for buttons, icons, and UI elements.
Works as Layer 1 in the detection hierarchy:
  1. Template Match (free, ~5ms)  ← THIS
  2. YOLO ONNX (free, ~50-100ms)
  3. OpenAI GPT-4o mini (paid, 2-3s)
  4. Claude (paid, 3-5s)

Usage:
    from template_matcher import TemplateMatcher
    tm = TemplateMatcher("templates")
    result = tm.find_button("close_btn")
    # → {"found": True, "x": 1230, "y": 45, "confidence": 0.92, "template": "close_btn_0.png"}
"""
import os, glob, time
import numpy as np
from PIL import Image


class TemplateMatcher:
    """Fast template matching using normalized cross-correlation."""

    def __init__(self, template_dir="templates", confidence=0.65):
        self.template_dir = template_dir
        self.confidence = confidence
        self._templates = {}  # name → [(img_array, w, h, path)]
        self._loaded = False
        self._stats = {"matches": 0, "misses": 0, "time_ms": 0}

    def load_templates(self):
        """Load all template images into memory."""
        if self._loaded:
            return

        count = 0
        for cat_dir in os.listdir(self.template_dir):
            cat_path = os.path.join(self.template_dir, cat_dir)
            if not os.path.isdir(cat_path):
                continue
            for fname in os.listdir(cat_path):
                if not fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                fpath = os.path.join(cat_path, fname)
                try:
                    img = Image.open(fpath).convert("RGB")
                    arr = np.array(img, dtype=np.float32)
                    w, h = img.size

                    # Skip too small or too large
                    if w < 8 or h < 8 or w > 600 or h > 400:
                        continue

                    # Key = base name without number suffix
                    # e.g., "close_btn_0.png" → "close_btn"
                    base = fname.rsplit(".", 1)[0]  # remove extension
                    # Remove trailing _N
                    parts = base.rsplit("_", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        key = parts[0]
                    else:
                        key = base

                    if key not in self._templates:
                        self._templates[key] = []
                    self._templates[key].append((arr, w, h, fpath))
                    count += 1
                except Exception as e:
                    pass

        self._loaded = True
        print(f"  [tmpl] Loaded {count} templates ({len(self._templates)} unique)")

    def _match_template_ncc(self, screenshot_arr, template_arr):
        """
        Normalized Cross-Correlation template matching.
        Pure NumPy, no OpenCV dependency.
        Returns (max_val, max_x, max_y) where x,y = center of match.
        """
        sh, sw = screenshot_arr.shape[:2]
        th, tw = template_arr.shape[:2]

        if th > sh or tw > sw:
            return 0, 0, 0

        # Convert to grayscale for faster matching
        if len(screenshot_arr.shape) == 3:
            screen_gray = np.mean(screenshot_arr, axis=2)
        else:
            screen_gray = screenshot_arr.astype(np.float32)

        if len(template_arr.shape) == 3:
            tmpl_gray = np.mean(template_arr, axis=2)
        else:
            tmpl_gray = template_arr.astype(np.float32)

        # Normalize template
        tmpl_mean = tmpl_gray.mean()
        tmpl_std = tmpl_gray.std()
        if tmpl_std < 1e-6:
            return 0, 0, 0
        tmpl_norm = (tmpl_gray - tmpl_mean) / tmpl_std

        # Sliding window with stride for speed
        # For large images, use stride=2 for speed, then refine
        stride = 2 if (sh > 400 and sw > 800) else 1
        best_val = 0
        best_x, best_y = 0, 0

        for y in range(0, sh - th + 1, stride):
            for x in range(0, sw - tw + 1, stride):
                patch = screen_gray[y:y+th, x:x+tw]
                patch_mean = patch.mean()
                patch_std = patch.std()
                if patch_std < 1e-6:
                    continue
                patch_norm = (patch - patch_mean) / patch_std
                ncc = np.mean(patch_norm * tmpl_norm)
                if ncc > best_val:
                    best_val = ncc
                    best_x = x
                    best_y = y

        # Refine if stride > 1
        if stride > 1 and best_val > 0.5:
            refine_range = stride + 1
            for y in range(max(0, best_y - refine_range), min(sh - th + 1, best_y + refine_range + 1)):
                for x in range(max(0, best_x - refine_range), min(sw - tw + 1, best_x + refine_range + 1)):
                    patch = screen_gray[y:y+th, x:x+tw]
                    patch_std = patch.std()
                    if patch_std < 1e-6:
                        continue
                    patch_norm = (patch - patch.mean()) / patch_std
                    ncc = np.mean(patch_norm * tmpl_norm)
                    if ncc > best_val:
                        best_val = ncc
                        best_x = x
                        best_y = y

        # Return center coordinates
        cx = best_x + tw // 2
        cy = best_y + th // 2
        return best_val, cx, cy

    def _match_template_cv2(self, screenshot_arr, template_arr):
        """
        OpenCV template matching (faster, preferred if available).
        Returns (max_val, center_x, center_y).
        """
        import cv2

        # Convert to grayscale
        if len(screenshot_arr.shape) == 3:
            screen_gray = cv2.cvtColor(screenshot_arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
        else:
            screen_gray = screenshot_arr.astype(np.uint8)

        if len(template_arr.shape) == 3:
            tmpl_gray = cv2.cvtColor(template_arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
        else:
            tmpl_gray = template_arr.astype(np.uint8)

        th, tw = tmpl_gray.shape[:2]
        if th > screen_gray.shape[0] or tw > screen_gray.shape[1]:
            return 0, 0, 0

        result = cv2.matchTemplate(screen_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        cx = max_loc[0] + tw // 2
        cy = max_loc[1] + th // 2
        return max_val, cx, cy

    def _match(self, screenshot_arr, template_arr):
        """Match template using best available method."""
        try:
            return self._match_template_cv2(screenshot_arr, template_arr)
        except ImportError:
            return self._match_template_ncc(screenshot_arr, template_arr)

    def find(self, name, screenshot_path=None, screenshot_arr=None, 
             screenshot_b64=None, min_confidence=None):
        """
        Find a template in the screenshot.
        
        Args:
            name: Template name (e.g., "close_btn", "ok_btn")
            screenshot_path: Path to screenshot PNG
            screenshot_arr: NumPy array of screenshot
            screenshot_b64: Base64 encoded screenshot
            min_confidence: Override default confidence threshold
            
        Returns:
            {"found": True, "x": cx, "y": cy, "confidence": val, "template": name}
            or None
        """
        self.load_templates()
        t0 = time.time()

        if min_confidence is None:
            min_confidence = self.confidence

        # Load screenshot
        if screenshot_arr is None:
            if screenshot_b64:
                import base64, io
                img_data = base64.b64decode(screenshot_b64)
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                screenshot_arr = np.array(img, dtype=np.float32)
            elif screenshot_path:
                img = Image.open(screenshot_path).convert("RGB")
                screenshot_arr = np.array(img, dtype=np.float32)
            else:
                return None

        # Find matching templates
        templates = self._templates.get(name, [])
        
        # Also try partial matches (e.g., "close" matches "close_btn", "ref_vr_close")
        if not templates:
            for key, tmpls in self._templates.items():
                if name in key or key in name:
                    templates.extend(tmpls)

        if not templates:
            return None

        best_result = None
        for tmpl_arr, tw, th, tpath in templates:
            val, cx, cy = self._match(screenshot_arr, tmpl_arr)
            if val >= min_confidence:
                if best_result is None or val > best_result["confidence"]:
                    best_result = {
                        "found": True,
                        "x": cx, "y": cy,
                        "confidence": round(val, 3),
                        "template": os.path.basename(tpath),
                        "method": "template",
                    }

        elapsed = (time.time() - t0) * 1000
        self._stats["time_ms"] += elapsed

        if best_result:
            self._stats["matches"] += 1
            print(f"  [tmpl] Found {name} at ({best_result['x']},{best_result['y']}) "
                  f"conf={best_result['confidence']} ({elapsed:.0f}ms)")
        else:
            self._stats["misses"] += 1

        return best_result

    def find_any(self, names, screenshot_path=None, screenshot_arr=None,
                 screenshot_b64=None, min_confidence=None):
        """Find any of the given template names."""
        self.load_templates()

        # Load screenshot once
        if screenshot_arr is None:
            if screenshot_b64:
                import base64, io
                img_data = base64.b64decode(screenshot_b64)
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                screenshot_arr = np.array(img, dtype=np.float32)
            elif screenshot_path:
                img = Image.open(screenshot_path).convert("RGB")
                screenshot_arr = np.array(img, dtype=np.float32)
            else:
                return None

        best = None
        for name in names:
            result = self.find(name, screenshot_arr=screenshot_arr,
                              min_confidence=min_confidence)
            if result:
                if best is None or result["confidence"] > best["confidence"]:
                    best = result
        return best

    def find_all(self, name, screenshot_path=None, screenshot_arr=None,
                 screenshot_b64=None, min_confidence=None):
        """Find ALL instances of a template (for multiple buttons, etc.)."""
        self.load_templates()
        
        if min_confidence is None:
            min_confidence = self.confidence

        if screenshot_arr is None:
            if screenshot_b64:
                import base64, io
                img_data = base64.b64decode(screenshot_b64)
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                screenshot_arr = np.array(img, dtype=np.float32)
            elif screenshot_path:
                img = Image.open(screenshot_path).convert("RGB")
                screenshot_arr = np.array(img, dtype=np.float32)
            else:
                return []

        results = []
        templates = self._templates.get(name, [])
        if not templates:
            for key, tmpls in self._templates.items():
                if name in key or key in name:
                    templates.extend(tmpls)

        try:
            import cv2
            for tmpl_arr, tw, th, tpath in templates:
                if len(screenshot_arr.shape) == 3:
                    sg = cv2.cvtColor(screenshot_arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
                else:
                    sg = screenshot_arr.astype(np.uint8)
                if len(tmpl_arr.shape) == 3:
                    tg = cv2.cvtColor(tmpl_arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
                else:
                    tg = tmpl_arr.astype(np.uint8)

                result = cv2.matchTemplate(sg, tg, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= min_confidence)
                for pt_y, pt_x in zip(*locations):
                    cx = pt_x + tw // 2
                    cy = pt_y + th // 2
                    val = result[pt_y, pt_x]
                    results.append({
                        "found": True, "x": cx, "y": cy,
                        "confidence": round(float(val), 3),
                        "template": os.path.basename(tpath),
                    })
        except ImportError:
            # Fallback: just find best match
            r = self.find(name, screenshot_arr=screenshot_arr, min_confidence=min_confidence)
            if r:
                results.append(r)

        return results

    def print_stats(self):
        print(f"  [tmpl] Stats: {self._stats['matches']} matches, "
              f"{self._stats['misses']} misses, "
              f"{self._stats['time_ms']:.0f}ms total")

    @property
    def available_templates(self):
        """List all available template names."""
        self.load_templates()
        return sorted(self._templates.keys())


# Quick test
if __name__ == "__main__":
    tm = TemplateMatcher("templates")
    tm.load_templates()
    print(f"\nAvailable templates: {tm.available_templates}")
    
    # Try matching against a screenshot
    import sys
    if len(sys.argv) > 1:
        screenshot = sys.argv[1]
        print(f"\nTesting against: {screenshot}")
        for name in tm.available_templates:
            result = tm.find(name, screenshot_path=screenshot)
            if result:
                print(f"  ✓ {name}: ({result['x']},{result['y']}) conf={result['confidence']}")
