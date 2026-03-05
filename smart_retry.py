"""
VRBOT Smart Retry System v1.0
==============================
ضعه في: C:\\Users\\manso\\vrbot-agent\\smart_retry.py

يعمل تلقائياً عند فشل أي task — بدون تعديل ملفات الـ tasks نفسها.
الطريقة الوحيدة للربط: تعديل سطرين في vrbot_main.py فقط.
"""

import json
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger("SmartRetry")

# ═══════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════

@dataclass
class Solution:
    task_name:    str
    screen_hash:  str
    action_name:  str
    action_params: dict
    success_count: int  = 1
    fail_count:    int  = 0
    source:        str  = "local"
    last_used:     str  = field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════
# LOCAL MEMORY — يحفظ الحلول في ملف JSON محلي
# ═══════════════════════════════════════════════════════════

class LocalMemory:
    def __init__(self, path="smart_retry_memory.json"):
        self.path = Path(path)
        self.data: dict = self._load()
        log.info(f"[Memory] {len(self.data)} حل محفوظ")

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def get(self, key: str) -> Optional[Solution]:
        if key in self.data:
            return Solution(**self.data[key])
        return None

    def set(self, key: str, sol: Solution):
        self.data[key] = {
            "task_name": sol.task_name, "screen_hash": sol.screen_hash,
            "action_name": sol.action_name, "action_params": sol.action_params,
            "success_count": sol.success_count, "fail_count": sol.fail_count,
            "source": sol.source, "last_used": sol.last_used,
        }
        self._save()
        log.info(f"[Memory] ✅ حُفظ: {sol.task_name} → {sol.action_name}")

    def increment(self, key: str):
        if key in self.data:
            self.data[key]["success_count"] += 1
            self.data[key]["last_used"] = datetime.now().isoformat()
            self._save()

    def increment_fail(self, key: str):
        if key in self.data:
            self.data[key]["fail_count"] = self.data[key].get("fail_count", 0) + 1
            self._save()


# ═══════════════════════════════════════════════════════════
# CLOUD MEMORY — يشارك الحلول عبر Supabase
# ═══════════════════════════════════════════════════════════

class CloudMemory:
    """
    SQL لإنشاء الجدول في Supabase:
    ─────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS learned_solutions (
        id            BIGSERIAL PRIMARY KEY,
        task_name     TEXT NOT NULL,
        screen_hash   TEXT NOT NULL,
        action_name   TEXT NOT NULL,
        action_params JSONB    DEFAULT '{}',
        success_count INT      DEFAULT 1,
        fail_count    INT      DEFAULT 0,
        source        TEXT     DEFAULT 'local',
        last_used     TIMESTAMPTZ DEFAULT NOW(),
        created_at    TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(task_name, screen_hash)
    );
    CREATE INDEX ON learned_solutions(task_name, screen_hash);
    ─────────────────────────────────────────────────────
    """
    def __init__(self, supabase=None):
        self.sb = supabase
        self.ok = supabase is not None

    def fetch(self, task_name: str, screen_hash: str) -> Optional[Solution]:
        if not self.ok:
            return None
        try:
            res = (self.sb.table("learned_solutions")
                   .select("*")
                   .eq("task_name", task_name)
                   .eq("screen_hash", screen_hash)
                   .order("success_count", desc=True)
                   .limit(1).execute())
            if res.data:
                d = res.data[0]
                return Solution(
                    task_name=d["task_name"], screen_hash=d["screen_hash"],
                    action_name=d["action_name"],
                    action_params=d.get("action_params", {}),
                    success_count=d.get("success_count", 1),
                    fail_count=d.get("fail_count", 0),
                    source="cloud",
                )
        except Exception as e:
            log.warning(f"[Cloud] fetch error: {e}")
        return None

    def upload(self, sol: Solution):
        if not self.ok:
            return
        try:
            self.sb.table("learned_solutions").upsert({
                "task_name":    sol.task_name,
                "screen_hash":  sol.screen_hash,
                "action_name":  sol.action_name,
                "action_params":sol.action_params,
                "success_count":sol.success_count,
                "source":       sol.source,
                "last_used":    datetime.now().isoformat(),
            }, on_conflict="task_name,screen_hash").execute()
            log.info(f"[Cloud] ☁️ رُفع: {sol.task_name}")
        except Exception as e:
            log.warning(f"[Cloud] upload error: {e}")


# ═══════════════════════════════════════════════════════════
# SCREEN HASH — بصمة الشاشة
# ═══════════════════════════════════════════════════════════

def hash_screenshot(data: bytes) -> str:
    try:
        from PIL import Image
        import io, numpy as np
        img = Image.open(io.BytesIO(data)).resize((64, 64)).convert("L")
        arr = np.array(img)
        bits = (arr > arr.mean()).flatten()
        return hex(int("".join("1" if b else "0" for b in bits), 2))[:16]
    except Exception:
        return hashlib.md5(data[:2048]).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════
# SMART RETRY ENGINE
# ═══════════════════════════════════════════════════════════

# خريطة كاملة: اسم task → استراتيجيات الإنقاذ المخصصة
TASK_STRATEGIES = {
    "niflung": [
        ("niflung_restart",  1, "أعد Niflung من البداية"),
        ("go_city_retry",    2, "اذهب للمدينة وعد"),
    ],
    "gather": [
        ("gather_scroll",    1, "Scroll للبحث عن موارد"),
        ("go_city_retry",    2, "اذهب للمدينة وعد"),
    ],
    "kill_monster": [
        ("monster_recat",    1, "أعد اختيار الفئة"),
        ("close_tap",        2, "أغلق النافذة"),
    ],
    "hall_of_valor": [
        ("valor_zoomout",    1, "Zoom Out"),
        ("valor_scroll",     2, "Scroll للزر"),
    ],
    "rally_niflung": [
        ("back_retry",       1, "Back ثم حاول"),
        ("go_city_retry",    2, "اذهب للمدينة"),
    ],
    "construction": [
        ("close_tap",        1, "أغلق النافذة"),
        ("back_retry",       2, "Back"),
    ],
    "research": [
        ("close_tap",        1, "أغلق النافذة"),
        ("back_retry",       2, "Back"),
    ],
    "prosperity": [
        ("close_tap",        1, "أغلق"),
        ("wait_retry",       2, "انتظر"),
    ],
    "mail_rewards": [
        ("close_tap",        1, "أغلق"),
        ("back_retry",       2, "Back"),
    ],
    "helps": [
        ("close_tap",        1, "أغلق"),
        ("back_retry",       2, "Back"),
    ],
    "tribe_tech": [
        ("swipe_left",       1, "Swipe Left"),
        ("close_tap",        2, "أغلق"),
    ],
    "tribe_gifts": [
        ("close_tap",        1, "أغلق"),
        ("back_retry",       2, "Back"),
    ],
    # Tasks الأخرى → تستخدم الاستراتيجيات العامة فقط
}

# استراتيجيات عامة لكل task
COMMON_STRATEGIES = [
    ("wait_retry",    8, "انتظر 3 ثوانٍ"),
    ("back_retry",    9, "اضغط Back"),
    ("close_tap",    10, "ابحث عن زر Close"),
    ("go_city_retry",11, "اذهب للمدينة"),
]


class SmartRetry:
    """
    الاستخدام في vrbot_main.py:
    ─────────────────────────────────────────────────
    from smart_retry import SmartRetry
    retry = SmartRetry(bot=bot, supabase_client=supabase)

    # في run_task():
    result = task_instance.run()
    if not result:
        result = retry.handle(task_name, bot)
    ─────────────────────────────────────────────────
    """

    def __init__(self, bot=None, supabase_client=None, max_attempts=5, delay=1.5):
        self.bot        = bot
        self.local      = LocalMemory()
        self.cloud      = CloudMemory(supabase_client)
        self.max        = max_attempts
        self.delay      = delay

    def handle(self, task_name: str, bot=None) -> bool:
        """
        نقطة الدخول الرئيسية — يُستدعى عند فشل task
        """
        b = bot or self.bot
        if b is None:
            log.warning("[SmartRetry] لا يوجد bot instance")
            return False

        # التقط الشاشة الحالية
        try:
            screenshot = b.adb.screenshot() if hasattr(b, 'adb') else b.screenshot()
        except Exception:
            screenshot = b""

        screen_hash = hash_screenshot(screenshot) if screenshot else "no_screenshot"
        mem_key     = f"{task_name}:{screen_hash}"

        log.info(f"🔄 SmartRetry [{task_name}] hash={screen_hash[:8]}")

        # ── 1. ذاكرة محلية ──────────────────────────────
        cached = self.local.get(mem_key)
        if cached:
            log.info(f"💾 حل محلي: {cached.action_name}")
            ok = self._exec(cached.action_name, b, {})
            if ok and self._verify(task_name, b):
                self.local.increment(mem_key)
                return True
            self.local.increment_fail(mem_key)

        # ── 2. ذاكرة سحابية ─────────────────────────────
        cloud_sol = self.cloud.fetch(task_name, screen_hash)
        if cloud_sol:
            log.info(f"☁️ حل سحابي: {cloud_sol.action_name}")
            ok = self._exec(cloud_sol.action_name, b, cloud_sol.action_params)
            if ok and self._verify(task_name, b):
                self.local.set(mem_key, cloud_sol)
                return True

        # ── 3. تجربة ذكية ───────────────────────────────
        return self._explore(task_name, screen_hash, mem_key, b)

    def _explore(self, task_name: str, screen_hash: str, mem_key: str, b) -> bool:
        """يجرب استراتيجيات مرتبة حسب الأولوية"""
        specific = TASK_STRATEGIES.get(task_name, [])
        all_strats = sorted(specific + COMMON_STRATEGIES, key=lambda x: x[1])

        for name, priority, desc in all_strats[:self.max]:
            log.info(f"  🧪 [{priority}] {desc}")
            try:
                self._exec(name, b, {})
                time.sleep(self.delay)
                if self._verify(task_name, b):
                    log.info(f"  ✅ نجح: {name}")
                    sol = Solution(task_name, screen_hash, name, {}, source="discovered")
                    self.local.set(mem_key, sol)
                    self.cloud.upload(sol)
                    return True
                log.info(f"  ❌ فشل: {name}")
            except Exception as e:
                log.warning(f"  ⚠️ {name}: {e}")
            time.sleep(0.5)

        log.error(f"💀 SmartRetry فشل كلياً [{task_name}]")
        return False

    def _exec(self, action: str, b, params: dict) -> bool:
        """ينفذ إجراء واحد"""
        adb = b.adb if hasattr(b, 'adb') else b
        try:
            if action == "wait_retry":
                time.sleep(3); return True
            elif action == "back_retry":
                adb.adb_back(); return True
            elif action == "close_tap":
                return self._tap_close(b)
            elif action == "go_city_retry":
                b.go_to_city(); time.sleep(1.5); return True
            elif action == "niflung_restart":
                return self._niflung_restart(b)
            elif action == "gather_scroll":
                adb.swipe(640, 400, 640, 200); return True
            elif action == "monster_recat":
                adb.adb_back(); time.sleep(0.5); adb.tap(380, 655); return True
            elif action == "valor_zoomout":
                if hasattr(adb, 'pinch_zoom_out'): adb.pinch_zoom_out()
                return True
            elif action == "valor_scroll":
                adb.swipe(640, 500, 640, 300); return True
            elif action == "swipe_left":
                adb.swipe(800, 400, 400, 400); return True
            else:
                log.warning(f"إجراء غير معروف: {action}")
                return False
        except Exception as e:
            log.warning(f"_exec({action}): {e}")
            return False

    def _tap_close(self, b) -> bool:
        """يبحث عن زر إغلاق بـ YOLO أو يضغط في الموضع الشائع"""
        adb = b.adb if hasattr(b, 'adb') else b
        try:
            # محاولة YOLO أولاً
            if hasattr(b, 'yolo') and b.yolo:
                pos = b.yolo.find("close_button")
                if pos:
                    adb.tap(*pos)
                    return True
        except Exception:
            pass
        # fallback: موضع زر الإغلاق الشائع في Viking Rise
        adb.tap(1220, 50)
        return True

    def _niflung_restart(self, b) -> bool:
        """يعيد بدء مهمة Niflung من الصفر"""
        adb = b.adb if hasattr(b, 'adb') else b
        for _ in range(3):
            adb.adb_back()
            time.sleep(0.4)
        b.go_to_city()
        time.sleep(1)
        adb.tap(380, 655)  # Category
        time.sleep(0.8)
        adb.tap(380, 490)  # Search
        time.sleep(1.5)
        return True

    def _verify(self, task_name: str, b) -> bool:
        """
        يتحقق إذا نجحت المهمة — يمكن توسيعه لكل task
        حالياً يتحقق إذا اختفت نوافذ الخطأ الشائعة
        """
        try:
            time.sleep(1)
            screenshot = b.adb.screenshot() if hasattr(b, 'adb') else b.screenshot()
            if not screenshot:
                return True  # إذا ما قدر يلتقط — افترض نجاح
            if hasattr(b, 'yolo') and b.yolo:
                # إذا ما في error dialog → اعتبر نجاح
                has_error = b.yolo.find("error_dialog") or b.yolo.find("retry_button")
                return not has_error
            return True
        except Exception:
            return True
