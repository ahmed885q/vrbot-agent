"""Task: Transfer Resources — نقل الموارد (Supply Resources)
================================================================
الـ Flow الحقيقي المبني على الـ UI الفعلي للعبة:

  1. go_to_world_map()
  2. tap على قلعة الـ target (ally)
  3. tap زر "Supply Resources" في الـ popup
  4. شاشة واحدة: اسحب الـ 4 sliders لـ MAX
  5. tap زر "Supply" → يرسل كل شيء في march واحد
  6. انتهى

ملاحظات مهمة من الـ UI الحقيقي:
  - Tax Rate: 25%
  - Supply Capacity: 4,000,000 per march
  - الـ sliders الـ 4 في شاشة واحدة — مش tabs منفصلة
  - زر Supply واحد يرسل كل الموارد المحددة
  - الـ target يجب يكون في نفس الـ Tribe

Config:
  transfer_target_name:   str  — اسم القلعة الهدف
  transfer_resources:     list — ["food", "wood", "stone", "gold"] أو أي منها
  transfer_amount:        str  — "max" أو "half"
  transfer_max_marches:   int  — عدد المرات (default: 1)
"""

import random
from tasks.base_task import BaseTask

# ── الكوردينيتس الحقيقية من الـ screenshots (1280x720) ──────────────────────

# زر Supply Resources في popup القلعة (World Map)
SUPPLY_RESOURCES_BTN = (762, 515)

# شاشة Supply Resources — بداية ونهاية كل slider
SLIDERS = {
    "food":  {"start": (560, 252), "end": (940, 252)},
    "wood":  {"start": (560, 325), "end": (940, 325)},
    "stone": {"start": (560, 400), "end": (940, 400)},
    "gold":  {"start": (560, 475), "end": (940, 475)},
}

# نقطة المنتصف لكل slider (للـ half)
SLIDER_HALF = {
    "food":  (750, 252),
    "wood":  (750, 325),
    "stone": (750, 400),
    "gold":  (750, 475),
}

# زر Supply أسفل الشاشة
SUPPLY_BTN = (793, 587)

# زر إغلاق الشاشة
CLOSE_BTN  = (1113, 89)

# الضريبة الحقيقية
SUPPLY_TAX_RATE = 0.25  # 25%


class TaskTransferResources(BaseTask):
    name = "Transfer Resources"
    tag  = "transfer"
    cooldown_hours = 0

    def __init__(self, bot):
        super().__init__(bot)
        self.marches_sent      = 0
        self.total_transferred = {}

    # ──────────────────────────────────────────────
    #  Utilities
    # ──────────────────────────────────────────────

    def _wait(self, mn: float = 1.5, mx: float = 3.0):
        if hasattr(self, '_human_wait'):
            self._human_wait(mn, mx)
        else:
            self.bot.wait(random.uniform(mn, mx))

    def _get_config(self) -> dict:
        cfg = getattr(self.bot, 'config', {}) or {}
        return {
            "target_name":  cfg.get("transfer_target_name", ""),
            "resources":    cfg.get("transfer_resources", ["food", "wood", "stone", "gold"]),
            "amount":       cfg.get("transfer_amount", "max"),
            "max_marches":  cfg.get("transfer_max_marches", 1),
        }

    # ──────────────────────────────────────────────
    #  Step 1: World Map
    # ──────────────────────────────────────────────

    def _go_to_world_map(self) -> bool:
        bot = self.bot
        bot.go_to_city()
        self._wait(1.5, 2.5)
        if bot.go_to_world_map():
            self._wait(2, 3)
            return True
        bot.go_to_city()
        self._wait(1.5, 2)
        ok = bot.go_to_world_map()
        self._wait(2, 3)
        return ok

    # ──────────────────────────────────────────────
    #  Step 2: إيجاد القلعة والضغط عليها
    # ──────────────────────────────────────────────

    def _find_and_tap_castle(self, target_name: str) -> bool:
        bot = self.bot
        directions = [None, "left", "right", "up", "down"]

        for i, direction in enumerate(directions):
            if direction:
                self._swipe_ui(direction)
                self._wait(1.5, 2)

            self.log.info(f"بحث عن '{target_name}' (محاولة {i+1}/5)...")
            img    = bot.screenshot_b64()
            result = bot.ask_ai(
                f"Viking Rise world map 1280x720. "
                f"Find castle of player '{target_name}'. "
                f"Allied castles have green/blue nameplate with player name above. "
                f'Return {{"found": true, "x": X, "y": Y}} or {{"found": false}}. JSON ONLY.',
                img, 100
            )

            if result and result.get("found"):
                x, y = int(result["x"]), int(result["y"])
                self.log.info(f"القلعة عند ({x},{y}) ✔")
                bot.tap(x, y)
                self._wait(2, 3)
                return True

        self.log.warning(f"قلعة '{target_name}' غير موجودة على الخريطة")
        return False

    # ──────────────────────────────────────────────
    #  Step 3: فتح شاشة Supply Resources
    # ──────────────────────────────────────────────

    def _open_supply_screen(self) -> bool:
        bot = self.bot

        # AI أولاً
        found = self._find_and_tap(
            "In the castle popup menu, find the 'Supply Resources' button. "
            "It's one of two main buttons at the bottom of the popup (left button). "
            "Blue colored button.",
            wait_after=3, retries=2
        )
        if found:
            self.log.info("Supply Resources btn: AI ✔")
        else:
            # Fallback coords
            self.log.info("Fallback: hardcoded Supply Resources coords...")
            bot.tap(*SUPPLY_RESOURCES_BTN)
            self._wait(3, 4)

        # تحقق من فتح الشاشة
        return self._is_on_supply_screen()

    def _is_on_supply_screen(self) -> bool:
        img    = self.bot.screenshot_b64()
        result = self.bot.ask_ai(
            "Viking Rise 1280x720. Am I on the 'SUPPLY RESOURCES' screen? "
            "It shows: player avatar on left side, 4 resource sliders (food/wood/stone/gold) "
            "on right, Tax Rate percentage, blue Supply button with timer at bottom. "
            '{"found": true} or {"found": false}. JSON ONLY.',
            img, 60
        )
        ok = bool(result and result.get("found"))
        if ok:
            self.log.info("شاشة Supply Resources مفتوحة ✔")
        return ok

    # ──────────────────────────────────────────────
    #  Step 4: ضبط الـ Sliders
    # ──────────────────────────────────────────────

    def _set_all_sliders(self, resources: list, amount: str):
        """اسحب sliders الموارد المطلوبة في الشاشة الواحدة."""
        bot = self.bot

        for resource in resources:
            if resource not in SLIDERS:
                self.log.warning(f"resource غير معروف: {resource}")
                continue

            if amount in ("max", "all"):
                sx, sy = SLIDERS[resource]["start"]
                ex, ey = SLIDERS[resource]["end"]
                self.log.info(f"  {resource} → MAX")
                bot.swipe(sx, sy, ex, ey, duration=random.randint(300, 500))

            elif amount == "half":
                sx, sy = SLIDERS[resource]["start"]
                hx, hy = SLIDER_HALF[resource]
                self.log.info(f"  {resource} → HALF")
                bot.swipe(sx, sy, hx, hy, duration=random.randint(300, 500))

            self._wait(0.4, 0.8)

        self._wait(1, 1.5)

    # ──────────────────────────────────────────────
    #  Step 5: إرسال
    # ──────────────────────────────────────────────

    def _tap_supply(self) -> bool:
        bot = self.bot

        # AI أولاً
        found = self._find_and_tap(
            "Find the blue 'Supply' button with hourglass/timer icon at the bottom "
            "of the Supply Resources screen (e.g. shows '00:00:12').",
            wait_after=3, retries=2
        )
        if found:
            self.log.info("Supply btn: AI ✔")
            return True

        # Fallback
        self.log.info("Fallback: hardcoded Supply btn...")
        bot.tap(*SUPPLY_BTN)
        self._wait(3, 4)
        return True

    # ──────────────────────────────────────────────
    #  Step 6: تحقق من نجاح الإرسال
    # ──────────────────────────────────────────────

    def _verify_march_sent(self) -> bool:
        self._wait(2, 4)
        bot = self.bot

        # تحقق عبر الشاشة الحالية
        screen = bot.detect_screen()
        current = (screen.get("screen", "") if screen else "").lower()
        if any(k in current for k in ("world", "city", "map")):
            self.log.info("✔ رجعنا للخريطة — March ناجح")
            return True

        # تحقق عبر AI
        img    = bot.screenshot_b64()
        result = bot.ask_ai(
            "Viking Rise 1280x720. Did the supply march launch successfully? "
            "Success signs: Supply screen closed, back on world map, "
            "march arrow/animation visible, or resource numbers changed. "
            '{"success": true} or {"success": false}. JSON ONLY.',
            img, 60
        )
        if result and result.get("success"):
            self.log.info("✔ March ناجح (AI confirm)")
            return True

        self.log.warning(f"⚠ March: غير متأكد (screen={current})")
        return False

    # ──────────────────────────────────────────────
    #  الـ Flow الكامل لـ march واحد
    # ──────────────────────────────────────────────

    def _do_one_march(self, target_name: str, resources: list, amount: str) -> bool:
        bot = self.bot

        # 1. خريطة
        if not self._go_to_world_map():
            self.log.error("فشل الوصول للخريطة")
            return False

        # 2. إيجاد القلعة
        if not self._find_and_tap_castle(target_name):
            return False

        # 3. فتح Supply Resources
        if not self._open_supply_screen():
            self.log.warning("فشل فتح Supply Resources — محاولة ثانية...")
            # ممكن الـ popup اختفى، نحاول مجدداً
            bot.adb_back()
            self._wait(1, 2)
            if not self._find_and_tap_castle(target_name):
                return False
            if not self._open_supply_screen():
                self.log.error("فشل فتح Supply Resources بعد إعادة المحاولة")
                return False

        # 4. ضبط الـ sliders
        self.log.info(f"ضبط الـ sliders: {resources} → {amount}")
        self._set_all_sliders(resources, amount)

        # 5. إرسال
        self._tap_supply()

        # 6. تحقق
        success = self._verify_march_sent()
        if success:
            self.marches_sent += 1
            for res in resources:
                self.total_transferred[res] = self.total_transferred.get(res, 0) + 1
            self.log.info(f"✔ Marches sent: {self.marches_sent}")

        return success

    # ──────────────────────────────────────────────
    #  Main
    # ──────────────────────────────────────────────

    def run(self):
        cfg         = self._get_config()
        target_name = cfg["target_name"]
        resources   = cfg["resources"]
        amount      = cfg["amount"]
        max_marches = cfg["max_marches"]

        if not target_name:
            self.log.error("transfer_target_name غير محدد في الـ config!")
            return False

        self.log.info("╔══════════════════════════════════════╗")
        self.log.info("║     Supply Resources Task             ║")
        self.log.info(f"║  Target   : {target_name:<26}║")
        self.log.info(f"║  Resources: {', '.join(resources):<26}║")
        self.log.info(f"║  Amount   : {amount:<26}║")
        self.log.info(f"║  Marches  : {max_marches:<26}║")
        self.log.info(f"║  Tax Rate : {SUPPLY_TAX_RATE*100:.0f}%{' '*25}║")
        self.log.info("╚══════════════════════════════════════╝")

        self._set_state("running")
        success_count = 0

        for i in range(max_marches):
            self.log.info(f"\n── March {i+1}/{max_marches} ──")

            ok = self._do_one_march(target_name, resources, amount)

            if ok:
                success_count += 1
            else:
                self.log.warning(f"March {i+1} فشل — متابعة...")

            # انتظار بين الـ marches
            if i < max_marches - 1:
                wait = random.uniform(10, 20)
                self.log.info(f"انتظار {wait:.0f}s...")
                self.bot.wait(wait)

        # رجوع للمدينة
        self.bot.go_to_city()

        # Summary
        self.log.info("\n╔══════════════════════════════════════╗")
        self.log.info("║     Supply Complete                   ║")
        self.log.info(f"║  Sent    : {self.marches_sent}/{max_marches}{' '*24}║")
        for res, count in self.total_transferred.items():
            self.log.info(f"║  {res:<8} : {count} ✔{' '*21}║")
        self.log.info("╚══════════════════════════════════════╝")

        self._set_state("completed")
        return success_count > 0
