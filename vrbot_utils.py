"""
VRBOT Utilities — vrbot_utils.py
=================================
ميزات جديدة:
  1. ROI (Region of Interest)       — بحث في منطقة محددة بدل الشاشة كلها
  2. Image Preprocessing             — grayscale + binarization لتحسين دقة التطابق
  3. Unified Retry + Verify Loop    — إعادة محاولة + تأكيد النجاح بعد كل إجراء
  4. Recovery Helper                 — رجوع آمن للشاشة الرئيسية عند أي خطأ

كيفية الاستخدام:
  from vrbot_utils import ROI, find_in_roi, retry_action, verify_state, safe_recover

الشاشة: 1280×720 (LDPlayer/Redroid)
"""

import cv2
import numpy as np
import base64
import time
import random
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Tuple, List
from enum import Enum

logger = logging.getLogger("vrbot_utils")

# ══════════════════════════════════════════════════════════════════════════════
# 1. ROI — مناطق الاهتمام المُعرَّفة مسبقاً
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ROI:
    """
    منطقة اهتمام على الشاشة (1280×720).

    الاستخدام:
        roi = ROI(x=900, y=600, w=380, h=120, name="bottom_right_buttons")
        cropped_b64 = roi.crop_b64(screenshot_b64)
    """
    x: int          # يسار المنطقة
    y: int          # أعلى المنطقة
    w: int          # العرض
    h: int          # الارتفاع
    name: str = ""  # اسم وصفي للـ logging

    def crop(self, img_bgr: np.ndarray) -> np.ndarray:
        """اقطع المنطقة من صورة BGR."""
        return img_bgr[self.y:self.y + self.h, self.x:self.x + self.w]

    def crop_b64(self, screenshot_b64: str) -> str:
        """اقطع المنطقة من base64 وأرجعها base64."""
        img = _b64_to_bgr(screenshot_b64)
        cropped = self.crop(img)
        return _bgr_to_b64(cropped)

    def to_global(self, local_x: int, local_y: int) -> Tuple[int, int]:
        """حوّل إحداثيات محلية (داخل المنطقة) إلى إحداثيات الشاشة الكاملة."""
        return self.x + local_x, self.y + local_y

    def __repr__(self):
        return f"ROI({self.name or 'unnamed'}: x={self.x},y={self.y} {self.w}×{self.h})"


# ── مناطق مُعرَّفة مسبقاً للشاشة 1280×720 ──────────────────────────────────

class ROIS:
    """
    مناطق جاهزة — استخدمها مباشرةً:
        from vrbot_utils import ROIS
        roi = ROIS.POPUP_CENTER
    """
    # أزرار الإغلاق والرجوع (أعلى الشاشة)
    TOP_BAR          = ROI(x=0,   y=0,   w=1280, h=80,  name="top_bar")
    CLOSE_BTN        = ROI(x=1180,y=0,   w=100,  h=100, name="close_btn")
    BACK_BTN         = ROI(x=0,   y=0,   w=100,  h=100, name="back_btn")

    # منطقة الـ popup المركزية
    POPUP_CENTER     = ROI(x=320, y=180, w=640,  h=360, name="popup_center")
    POPUP_BUTTONS    = ROI(x=300, y=450, w=680,  h=160, name="popup_buttons")

    # أزرار أسفل الشاشة
    BOTTOM_BAR       = ROI(x=0,   y=600, w=1280, h=120, name="bottom_bar")
    BOTTOM_RIGHT     = ROI(x=900, y=550, w=380,  h=170, name="bottom_right")
    BOTTOM_LEFT      = ROI(x=0,   y=550, w=380,  h=170, name="bottom_left")
    BOTTOM_CENTER    = ROI(x=440, y=580, w=400,  h=140, name="bottom_center")

    # شريط التنقل (nav bar)
    NAV_BAR          = ROI(x=0,   y=640, w=1280, h=80,  name="nav_bar")

    # منطقة الموارد (أعلى اليسار)
    RESOURCE_BAR     = ROI(x=0,   y=0,   w=640,  h=60,  name="resource_bar")

    # ميدان المعركة / الخريطة العالمية
    WORLD_MAP        = ROI(x=200, y=100, w=880,  h=500, name="world_map")

    # March / Attack زر عادةً أسفل يمين
    MARCH_BTN        = ROI(x=880, y=620, w=400,  h=100, name="march_btn")
    ATTACK_BTN       = ROI(x=880, y=300, w=400,  h=250, name="attack_btn")

    # Gather زر في الوسط أسفل
    GATHER_BTN       = ROI(x=400, y=580, w=480,  h=140, name="gather_btn")

    # Chat / Notification (يمين وسط)
    CHAT_AREA        = ROI(x=0,   y=100, w=300,  h=500, name="chat_area")

    # Niflung: زر البحث والهجوم
    NIFLUNG_SEARCH   = ROI(x=300, y=430, w=200,  h=120, name="niflung_search")
    NIFLUNG_ATTACK   = ROI(x=880, y=400, w=400,  h=120, name="niflung_attack")

    @classmethod
    def get(cls, name: str) -> Optional[ROI]:
        """احصل على ROI باسمه (case-insensitive)."""
        return getattr(cls, name.upper(), None)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Image Preprocessing — معالجة الصور قبل Template Matching
# ══════════════════════════════════════════════════════════════════════════════

class PreprocessMode(Enum):
    NONE        = "none"       # بدون معالجة
    GRAY        = "gray"       # تدرج رمادي فقط
    BINARY      = "binary"     # ثنائي (أسود/أبيض)
    BINARY_INV  = "binary_inv" # ثنائي معكوس
    CANNY       = "canny"      # كشف الحواف


def preprocess(img: np.ndarray, mode: PreprocessMode = PreprocessMode.GRAY,
               binary_thresh: int = 127, scale: float = 1.0) -> np.ndarray:
    """
    معالج الصور — يحوّل الصورة للمطابقة الأفضل.

    المعاملات:
        img           : صورة BGR (numpy array)
        mode          : نوع المعالجة
        binary_thresh : عتبة الـ binarization (0-255)
        scale         : تكبير/تصغير (1.0 = بدون تغيير)

    الاستخدام:
        processed = preprocess(screen, mode=PreprocessMode.BINARY, binary_thresh=160)
    """
    if scale != 1.0:
        h, w = img.shape[:2]
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_CUBIC)

    if mode == PreprocessMode.NONE:
        return img

    # تحويل لرمادي أولاً (مطلوب لباقي الأوضاع)
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    if mode == PreprocessMode.GRAY:
        return gray

    if mode == PreprocessMode.BINARY:
        _, binary = cv2.threshold(gray, binary_thresh, 255, cv2.THRESH_BINARY)
        return binary

    if mode == PreprocessMode.BINARY_INV:
        _, binary = cv2.threshold(gray, binary_thresh, 255, cv2.THRESH_BINARY_INV)
        return binary

    if mode == PreprocessMode.CANNY:
        return cv2.Canny(gray, 50, 150)

    return gray


def preprocess_for_ocr(img: np.ndarray, scale: float = 3.0,
                       binary_thresh: int = 160) -> np.ndarray:
    """
    معالجة خاصة لتحسين دقة OCR (Tesseract).

    الخطوات: resize كبير → رمادي → ثنائي → إزالة ضوضاء

    الاستخدام:
        processed = preprocess_for_ocr(roi_crop)
        text = pytesseract.image_to_string(processed, config='--psm 7')
    """
    # 1. تكبير 3× لتوضيح النص الصغير
    h, w = img.shape[:2]
    big = cv2.resize(img, (int(w * scale), int(h * scale)),
                     interpolation=cv2.INTER_CUBIC)

    # 2. رمادي
    if len(big.shape) == 3:
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    else:
        gray = big

    # 3. تحسين التباين
    gray = cv2.equalizeHist(gray)

    # 4. ثنائي
    _, binary = cv2.threshold(gray, binary_thresh, 255, cv2.THRESH_BINARY)

    # 5. إزالة ضوضاء
    denoised = cv2.medianBlur(binary, 3)

    return denoised


# ══════════════════════════════════════════════════════════════════════════════
# 3. find_in_roi — البحث عن عنصر داخل ROI فقط
# ══════════════════════════════════════════════════════════════════════════════

def find_in_roi(
    bot,
    button_name: str,
    roi: ROI,
    preprocess_mode: PreprocessMode = PreprocessMode.GRAY,
    confidence: float = 0.80,
    screenshot_b64: Optional[str] = None,
    skip_ai: bool = True,
) -> Optional[dict]:
    """
    ابحث عن زر داخل منطقة ROI فقط (أسرع وأدق من البحث في الشاشة كلها).

    يُرجع dict يحتوي على إحداثيات الشاشة الكاملة (بعد التحويل).

    الاستخدام:
        result = find_in_roi(bot, "close", ROIS.CLOSE_BTN)
        if result:
            bot.tap(result["x"], result["y"])
    """
    if screenshot_b64 is None:
        screenshot_b64 = bot.screenshot_b64()

    # اقطع الـ ROI
    roi_b64 = roi.crop_b64(screenshot_b64)

    if skip_ai:
        # عطّل ask_ai مؤقتاً عبر monkey-patch
        original_ask_ai = bot.ask_ai
        bot.ask_ai = lambda *a, **kw: None
        try:
            result = bot.hybrid_find_button(button_name, image_b64=roi_b64)
        finally:
            bot.ask_ai = original_ask_ai
    else:
        result = bot.hybrid_find_button(button_name, image_b64=roi_b64)


    if result and result.get("found"):
        # حوّل إحداثيات ROI → إحداثيات الشاشة الكاملة
        local_x = result.get("x", 0)
        local_y = result.get("y", 0)
        global_x, global_y = roi.to_global(local_x, local_y)

        logger.debug(f"[roi] Found '{button_name}' in {roi.name}: "
                     f"local=({local_x},{local_y}) → global=({global_x},{global_y})")

        return {
            **result,
            "x": global_x,
            "y": global_y,
            "roi": roi.name,
            "local_x": local_x,
            "local_y": local_y,
        }

    return None


# ══════════════════════════════════════════════════════════════════════════════
# 4. retry_action — حلقة إعادة المحاولة الموحّدة
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RetryConfig:
    """إعدادات حلقة Retry."""
    max_attempts:   int   = 3          # أقصى عدد محاولات
    delay_min:      float = 0.8        # تأخير أدنى بين المحاولات (ثانية)
    delay_max:      float = 2.0        # تأخير أقصى بين المحاولات (ثانية)
    verify_delay:   float = 0.5        # انتظار قبل التحقق من النجاح (ثانية)
    log_prefix:     str   = ""         # بادئة لرسائل الـ log


def retry_action(
    action_fn:   Callable[[], Any],
    verify_fn:   Optional[Callable[[], bool]] = None,
    config:      RetryConfig = None,
    label:       str = "action",
) -> Tuple[bool, Any]:
    """
    نفّذ إجراء مع إعادة المحاولة والتحقق من النجاح.

    المعاملات:
        action_fn  : دالة تُنفّذ الإجراء (مثلاً: lambda: bot.tap(x, y))
        verify_fn  : دالة تتحقق من نجاح الإجراء — تُرجع True/False
                     إذا لم تُمرَّر، يُعتبر الإجراء ناجحاً إذا لم يرمِ استثناء
        config     : إعدادات الـ retry (اختياري — يستخدم الافتراضي إذا لم يُمرَّر)
        label      : اسم الإجراء للـ logging

    يُرجع: (success: bool, result: Any)

    الاستخدام:
        # مثال بسيط
        success, _ = retry_action(
            action_fn=lambda: bot.tap(933, 173),
            verify_fn=lambda: bot.is_on_screen("create_march"),
            label="tap_create_btn"
        )

        # مع إعدادات مخصصة
        cfg = RetryConfig(max_attempts=5, delay_min=1.0, delay_max=3.0)
        success, result = retry_action(
            action_fn=lambda: bot.hybrid_find_button("close"),
            verify_fn=lambda: not bot.is_on_screen("popup"),
            config=cfg,
            label="close_popup"
        )
    """
    if config is None:
        config = RetryConfig()

    prefix = f"[retry:{label}]"
    last_result = None
    last_error = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            logger.info(f"{prefix} Attempt {attempt}/{config.max_attempts}")

            # نفّذ الإجراء
            last_result = action_fn()

            # انتظر قليلاً قبل التحقق
            if config.verify_delay > 0:
                time.sleep(config.verify_delay)

            # تحقق من النجاح
            if verify_fn is None:
                # لا يوجد verify → نعتبره ناجحاً
                logger.info(f"{prefix} ✅ Succeeded (no verify) on attempt {attempt}")
                return True, last_result

            if verify_fn():
                logger.info(f"{prefix} ✅ Verified success on attempt {attempt}")
                return True, last_result
            else:
                logger.warning(f"{prefix} ⚠️ Verify failed on attempt {attempt}")

        except Exception as e:
            last_error = e
            logger.error(f"{prefix} ❌ Exception on attempt {attempt}: {e}")

        # تأخير عشوائي قبل المحاولة التالية
        if attempt < config.max_attempts:
            delay = random.uniform(config.delay_min, config.delay_max)
            logger.debug(f"{prefix} Waiting {delay:.1f}s before next attempt...")
            time.sleep(delay)

    logger.error(f"{prefix} 💀 All {config.max_attempts} attempts failed. "
                 f"Last error: {last_error}")
    return False, last_result


def find_and_tap_retry(
    bot,
    button_name: str,
    roi: Optional[ROI] = None,
    verify_fn: Optional[Callable[[], bool]] = None,
    config: RetryConfig = None,
) -> bool:
    """
    ابحث عن زر، انقر عليه، وتحقق من النجاح — مع إعادة المحاولة.

    الاستخدام:
        success = find_and_tap_retry(
            bot,
            button_name="claim",
            roi=ROIS.POPUP_BUTTONS,
            verify_fn=lambda: not bot.is_on_screen("claim_popup"),
        )
    """
    if config is None:
        config = RetryConfig()

    def _action():
        if roi:
            result = find_in_roi(bot, button_name, roi)
        else:
            result = bot.hybrid_find_button(button_name)

        if result and result.get("found"):
            x, y = result["x"], result["y"]
            # إضافة تشويش صغير للنقر (أكثر طبيعية)
            jitter_x = x + random.randint(-3, 3)
            jitter_y = y + random.randint(-3, 3)
            bot.tap(jitter_x, jitter_y)
            logger.debug(f"[tap] {button_name} at ({jitter_x},{jitter_y}) "
                         f"via {result.get('method','?')}")
            return True
        else:
            logger.warning(f"[find] '{button_name}' not found on screen")
            return False

    def _combined_verify():
        if verify_fn:
            return verify_fn()
        return True  # لو ما في verify، نعتبر النقر نجح

    # نعيد المحاولة فقط إذا action نجح (وجد الزر)
    # لكن verify فشل
    success, result = retry_action(
        action_fn=_action,
        verify_fn=_combined_verify,
        config=config,
        label=f"find_tap_{button_name}"
    )
    return success


# ══════════════════════════════════════════════════════════════════════════════
# 5. verify_state — التحقق من حالة الشاشة
# ══════════════════════════════════════════════════════════════════════════════

def verify_state(
    bot,
    expected_screen: Optional[str] = None,
    expected_element: Optional[str] = None,
    timeout: float = 5.0,
    check_interval: float = 0.5,
) -> bool:
    """
    انتظر حتى تتحقق حالة معينة على الشاشة.

    المعاملات:
        bot              : كائن Bot
        expected_screen  : اسم الشاشة المتوقعة (تُمرَّر لـ bot.detect_screen)
        expected_element : اسم عنصر يجب أن يكون موجوداً (مثل "claim_btn")
        timeout          : أقصى وقت للانتظار (ثانية)
        check_interval   : الفترة بين كل فحص (ثانية)

    الاستخدام:
        # انتظر ظهور شاشة المدينة
        ok = verify_state(bot, expected_screen="city", timeout=8.0)

        # انتظر ظهور زر معين
        ok = verify_state(bot, expected_element="march_btn", timeout=5.0)
    """
    deadline = time.time() + timeout
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        try:
            if expected_screen:
                result = bot.detect_screen()
                if result and result.get("screen") == expected_screen:
                    logger.info(f"[verify] Screen '{expected_screen}' confirmed "
                                f"after {attempt} checks")
                    return True

            if expected_element:
                result = bot.hybrid_find_button(expected_element)
                if result and result.get("found"):
                    logger.info(f"[verify] Element '{expected_element}' found "
                                f"after {attempt} checks")
                    return True

            if not expected_screen and not expected_element:
                logger.warning("[verify] No condition specified — returning True")
                return True

        except Exception as e:
            logger.error(f"[verify] Check {attempt} error: {e}")

        time.sleep(check_interval)

    logger.warning(f"[verify] Timeout after {timeout}s "
                   f"(screen={expected_screen}, element={expected_element})")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# 6. safe_recover — التعافي الآمن عند الخطأ
# ══════════════════════════════════════════════════════════════════════════════

def safe_recover(bot, max_back_presses: int = 5) -> bool:
    """
    حاول الرجوع لحالة آمنة (الشاشة الرئيسية للمدينة).

    الخطوات:
        1. اضغط Back عدة مرات لإغلاق أي popup أو شاشة فرعية
        2. تحقق إذا وصلنا للمدينة
        3. إذا لم يُجدِ، استخدم go_to_city()

    الاستخدام:
        recovered = safe_recover(bot)
        if not recovered:
            logger.error("فشل التعافي! يجب إعادة تشغيل البوت.")
    """
    logger.warning("[recover] Starting safe recovery...")

    # المحاولة 1: أزرار الإغلاق وBack
    for i in range(max_back_presses):
        try:
            screen = bot.detect_screen()
            current = screen.get("screen", "") if screen else ""

            if current in ("city", "city_main", "main"):
                logger.info(f"[recover] ✅ Already on city screen after {i} presses")
                return True

            # جرّب إغلاق أي popup ظاهر
            close_result = find_in_roi(bot, "close", ROIS.CLOSE_BTN)
            if close_result and close_result.get("found"):
                bot.tap(close_result["x"], close_result["y"])
                logger.debug(f"[recover] Pressed close button (step {i+1})")
                time.sleep(random.uniform(0.5, 1.0))
                continue

            # Back button
            bot.adb_back()
            logger.debug(f"[recover] Pressed Back (step {i+1})")
            time.sleep(random.uniform(0.7, 1.2))

        except Exception as e:
            logger.error(f"[recover] Step {i+1} error: {e}")

    # المحاولة 2: go_to_city مباشرةً
    try:
        logger.info("[recover] Trying go_to_city()...")
        bot.go_to_city()
        time.sleep(2.0)

        screen = bot.detect_screen()
        if screen and screen.get("screen") in ("city", "city_main", "main"):
            logger.info("[recover] ✅ Recovery successful via go_to_city()")
            return True

    except Exception as e:
        logger.error(f"[recover] go_to_city() failed: {e}")

    logger.error("[recover] ❌ Recovery failed — bot may need restart")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# 7. task_with_recovery — غلاف شامل لتنفيذ المهام
# ══════════════════════════════════════════════════════════════════════════════

def task_with_recovery(
    bot,
    task_fn: Callable[[], Any],
    task_name: str = "task",
    recover_on_failure: bool = True,
) -> Tuple[bool, Any]:
    """
    نفّذ مهمة كاملة مع التعافي التلقائي عند الفشل.

    الاستخدام:
        def my_task():
            # خطوات المهمة
            bot.tap(380, 655)
            ...
            return True

        success, result = task_with_recovery(bot, my_task, "niflung_hunt")
    """
    logger.info(f"[task:{task_name}] Starting...")
    start_time = time.time()

    try:
        result = task_fn()
        elapsed = time.time() - start_time
        logger.info(f"[task:{task_name}] ✅ Completed in {elapsed:.1f}s")
        return True, result

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[task:{task_name}] ❌ Failed after {elapsed:.1f}s: {e}")

        if recover_on_failure:
            logger.info(f"[task:{task_name}] Attempting recovery...")
            recovered = safe_recover(bot)
            if recovered:
                logger.info(f"[task:{task_name}] Recovery succeeded")
            else:
                logger.error(f"[task:{task_name}] Recovery FAILED")

        return False, None


# ══════════════════════════════════════════════════════════════════════════════
# 8. أدوات مساعدة داخلية
# ══════════════════════════════════════════════════════════════════════════════

def _b64_to_bgr(b64_str: str) -> np.ndarray:
    """حوّل base64 PNG إلى numpy BGR array."""
    # أزل data:image/png;base64, prefix لو موجود
    if "," in b64_str:
        b64_str = b64_str.split(",", 1)[1]
    img_bytes = base64.b64decode(b64_str)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _bgr_to_b64(img: np.ndarray) -> str:
    """حوّل numpy BGR array إلى base64 PNG string."""
    _, buf = cv2.imencode(".png", img)
    return base64.b64encode(buf).decode("utf-8")


def crop_roi_from_b64(screenshot_b64: str, roi: ROI) -> np.ndarray:
    """مختصر: احصل على crop كـ numpy array."""
    img = _b64_to_bgr(screenshot_b64)
    return roi.crop(img)


# ══════════════════════════════════════════════════════════════════════════════
# 9. أمثلة الاستخدام (في نهاية الملف للمرجعية)
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
مثال 1: إيجاد زر Close في ROI محددة
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from vrbot_utils import find_in_roi, ROIS

result = find_in_roi(bot, "close", ROIS.CLOSE_BTN)
if result:
    bot.tap(result["x"], result["y"])

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
مثال 2: نقر على Claim مع retry وverify
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from vrbot_utils import find_and_tap_retry, RetryConfig, ROIS

cfg = RetryConfig(max_attempts=4, delay_min=1.0, delay_max=2.5)

success = find_and_tap_retry(
    bot,
    button_name="claim",
    roi=ROIS.POPUP_BUTTONS,
    verify_fn=lambda: not bot.hybrid_find_button("claim").get("found"),
    config=cfg,
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
مثال 3: retry_action مع verify
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from vrbot_utils import retry_action, RetryConfig

success, _ = retry_action(
    action_fn=lambda: bot.tap(951, 462),          # March
    verify_fn=lambda: bot.is_on_screen("marching"), # تحقق
    config=RetryConfig(max_attempts=3),
    label="march_btn"
)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
مثال 4: مهمة Niflung كاملة مع recovery
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from vrbot_utils import (
    task_with_recovery, find_and_tap_retry, verify_state,
    RetryConfig, ROIS
)

def niflung_task():
    # خطوة 1: Cat
    bot.tap(380, 655)
    time.sleep(1.0)

    # خطوة 2: Search (مع retry)
    ok = find_and_tap_retry(bot, "search", ROIS.NIFLUNG_SEARCH,
                            verify_fn=lambda: bot.is_on_screen("niflung_results"))
    if not ok:
        raise RuntimeError("Search failed")

    # خطوة 3: Attack
    ok = find_and_tap_retry(bot, "attack", ROIS.NIFLUNG_ATTACK,
                            verify_fn=lambda: bot.is_on_screen("create_march"))
    if not ok:
        raise RuntimeError("Attack failed")

    # خطوة 4: March
    bot.tap(985, 640)
    verify_state(bot, expected_screen="marching", timeout=5.0)

success, _ = task_with_recovery(bot, niflung_task, "niflung_hunt")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
مثال 5: OCR لقراءة الموارد
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import pytesseract
from vrbot_utils import ROIS, preprocess_for_ocr, crop_roi_from_b64

screen_b64 = bot.screenshot_b64()
resource_crop = crop_roi_from_b64(screen_b64, ROIS.RESOURCE_BAR)
processed = preprocess_for_ocr(resource_crop, scale=3.0)
text = pytesseract.image_to_string(processed, config="--psm 7 -c tessedit_char_whitelist=0123456789,KMB/")
print("Resources:", text.strip())
"""
