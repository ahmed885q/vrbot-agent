"""
Cycle Validator - Schedule Integrity Checker
=============================================
يتأكد أن الجدول يبقى صحيح مهما زاد العملاء أو المزارع

القواعد الثابتة (ما تتغير أبداً):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🌾 Farming:  مرة كل 5.5 ساعات بالضبط
  📋 Daily:    مرة كل 24 ساعة
  ⚔️ Nifling:  فوري حسب طلب الزبون
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

المشكلة:
  لو عندك 200 مزرعة و 20 slot → دورة = 5 ساعات ✅
  زبون جديد أضاف 100 مزرعة → 300 مزرعة → دورة = 7.5 ساعات ❌
  المزارع ما تلحق تاخذ دورها!

الحل:
  الـ Validator يكتشف المشكلة قبل ما تحصل
  ويطلب سيرفر إضافي لزيادة الـ slots المتزامنة
  أو يزيد حجم الدفعة تلقائياً
"""

import math
import logging
from datetime import timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from models import SchedulerConfig
from auto_provisioner import ServerType, SERVER_CAPACITY

logger = logging.getLogger("cycle_validator")


@dataclass
class ValidationResult:
    """نتيجة التحقق"""
    valid: bool = True
    farming_ok: bool = True
    daily_ok: bool = True

    # تفاصيل Farming
    total_farms: int = 0
    concurrent_slots: int = 0
    batch_duration_min: int = 30
    batches_needed: int = 0
    cycle_duration_hours: float = 0
    farming_interval_hours: float = 5.5
    farming_margin_hours: float = 0  # كم وقت فاضي

    # تفاصيل Daily
    daily_cycle_hours: float = 0
    daily_interval_hours: float = 24

    # الحل المقترح إذا فيه مشكلة
    fix_needed: bool = False
    fix_type: str = ""  # "add_server" or "increase_batch_size"
    fix_details: str = ""
    extra_servers_needed: int = 0
    extra_slots_needed: int = 0


class CycleValidator:
    """
    مُحقق الجداول

    يُستدعى عند:
    1. إضافة زبون جديد
    2. زبون يزيد مزارعه
    3. قبل كل دورة farming
    4. بعد كل تغيير في الإعدادات
    """

    def __init__(self, config: SchedulerConfig = None):
        self.config = config or SchedulerConfig()

    def validate(self, total_farms: int,
                 concurrent_slots: int = None) -> ValidationResult:
        """
        التحقق الرئيسي: هل الجدول يعمل بشكل صحيح؟

        Args:
            total_farms: إجمالي المزارع (كل العملاء)
            concurrent_slots: الـ slots المتزامنة (الافتراضي من الإعدادات)

        Returns:
            ValidationResult مع التفاصيل والحل
        """
        if concurrent_slots is None:
            concurrent_slots = self.config.max_concurrent_farms

        result = ValidationResult(
            total_farms=total_farms,
            concurrent_slots=concurrent_slots,
            batch_duration_min=self.config.batch_duration_minutes,
            farming_interval_hours=self.config.farming_interval_hours,
            daily_interval_hours=self.config.daily_interval_hours,
        )

        # ─── حساب Farming ───
        if concurrent_slots > 0:
            # خصم slots الـ nifling
            farming_slots = concurrent_slots - self.config.nifling_reserved_slots
            farming_slots = max(farming_slots, 1)

            result.batches_needed = math.ceil(total_farms / farming_slots)
            result.cycle_duration_hours = (
                result.batches_needed * self.config.batch_duration_minutes
            ) / 60

            result.farming_margin_hours = (
                self.config.farming_interval_hours - result.cycle_duration_hours
            )
            result.farming_ok = result.farming_margin_hours >= 0

        # ─── حساب Daily ───
        if concurrent_slots > 0:
            daily_slots = concurrent_slots - self.config.nifling_reserved_slots
            daily_slots = max(daily_slots, 1)
            daily_batches = math.ceil(total_farms / daily_slots)
            result.daily_cycle_hours = (
                daily_batches * self.config.batch_duration_minutes
            ) / 60
            result.daily_ok = result.daily_cycle_hours <= self.config.daily_interval_hours

        # ─── النتيجة ───
        result.valid = result.farming_ok and result.daily_ok

        if not result.valid:
            self._calculate_fix(result)

        return result

    def validate_before_adding(self, existing_farms: int,
                                new_farms: int,
                                current_slots: int) -> ValidationResult:
        """
        التحقق قبل إضافة مزارع جديدة

        يُستدعى من:
        - POST /deploy (زبون جديد)
        - إضافة مزارع لزبون موجود

        Returns:
            هل النظام يتحمل المزارع الجديدة؟
            وإذا لا — ماذا نحتاج؟
        """
        total_after = existing_farms + new_farms

        # تحقق بالوضع الحالي
        result = self.validate(total_after, current_slots)

        if not result.valid:
            logger.warning(
                f"⚠️ Adding {new_farms} farms will break the schedule!\n"
                f"   Current: {existing_farms} farms, {current_slots} slots\n"
                f"   After: {total_after} farms\n"
                f"   Cycle would be: {result.cycle_duration_hours:.1f}h "
                f"(limit: {self.config.farming_interval_hours}h)\n"
                f"   Fix: {result.fix_details}"
            )
        else:
            logger.info(
                f"✅ Can add {new_farms} farms safely\n"
                f"   After: {total_after} farms, "
                f"cycle: {result.cycle_duration_hours:.1f}h "
                f"(margin: {result.farming_margin_hours:.1f}h)"
            )

        return result

    def find_optimal_slots(self, total_farms: int) -> dict:
        """
        حساب العدد الأمثل للـ slots المتزامنة

        يُجيب على السؤال:
        "كم slot نحتاج لتشغيل X مزرعة ضمن 5.5 ساعة؟"
        """
        farming_interval = self.config.farming_interval_hours
        batch_duration = self.config.batch_duration_minutes
        nifling_reserved = self.config.nifling_reserved_slots

        # أقل عدد slots يخلي الدورة تكفي
        # cycle = (farms / farming_slots) × batch_duration / 60
        # cycle <= interval
        # farms / farming_slots <= interval × 60 / batch_duration
        # farming_slots >= farms / (interval × 60 / batch_duration)

        max_batches = (farming_interval * 60) / batch_duration
        min_farming_slots = math.ceil(total_farms / max_batches)
        min_total_slots = min_farming_slots + nifling_reserved

        # الأمثل (مع هامش أمان 20%)
        optimal_farming_slots = math.ceil(min_farming_slots * 1.2)
        optimal_total_slots = optimal_farming_slots + nifling_reserved

        # كم سيرفر يحقق هذا؟
        # (بافتراض 20 slot لكل سيرفر)
        slots_per_server = 20  # قابل للتعديل
        min_servers = math.ceil(min_total_slots / slots_per_server)
        optimal_servers = math.ceil(optimal_total_slots / slots_per_server)

        return {
            "total_farms": total_farms,
            "farming_interval": f"{farming_interval}h",
            "batch_duration": f"{batch_duration}min",

            "minimum": {
                "farming_slots": min_farming_slots,
                "total_slots": min_total_slots,
                "servers_needed": min_servers,
                "cycle_duration": f"{(total_farms / min_farming_slots) * batch_duration / 60:.1f}h",
                "margin": "0h (حافة — أي مشكلة تعطل الجدول)",
            },

            "optimal": {
                "farming_slots": optimal_farming_slots,
                "total_slots": optimal_total_slots,
                "servers_needed": optimal_servers,
                "cycle_duration": f"{(total_farms / optimal_farming_slots) * batch_duration / 60:.1f}h",
                "margin": f"{farming_interval - (total_farms / optimal_farming_slots) * batch_duration / 60:.1f}h",
            },
        }

    def _calculate_fix(self, result: ValidationResult):
        """حساب الحل المقترح"""

        if not result.farming_ok:
            # كم slot إضافية نحتاج؟
            max_batches = (
                self.config.farming_interval_hours * 60
            ) / self.config.batch_duration_minutes

            needed_farming_slots = math.ceil(result.total_farms / max_batches)
            current_farming_slots = (
                result.concurrent_slots - self.config.nifling_reserved_slots
            )
            extra_slots = needed_farming_slots - current_farming_slots

            if extra_slots > 0:
                result.fix_needed = True
                result.fix_type = "add_server"
                result.extra_slots_needed = extra_slots

                # كم سيرفر يحقق هذا؟
                capacity = SERVER_CAPACITY.get(ServerType.AX42, 40)
                result.extra_servers_needed = math.ceil(extra_slots / capacity)

                result.fix_details = (
                    f"نحتاج +{extra_slots} slots إضافية "
                    f"(~{result.extra_servers_needed} سيرفر AX42) "
                    f"لتغطية {result.total_farms} مزرعة "
                    f"ضمن {self.config.farming_interval_hours}h"
                )


# ══════════════════════════════════════════
#  أمثلة عملية
# ══════════════════════════════════════════

def demo():
    """
    سيناريوهات التحقق:

    1. 200 مزرعة + 20 slot = ✅
    2. 300 مزرعة + 20 slot = ❌ (نحتاج سيرفر)
    3. 1000 مزرعة → كم slot نحتاج؟
    """
    validator = CycleValidator()

    print("=" * 60)
    print("  CYCLE VALIDATOR DEMO")
    print("=" * 60)

    # ─── سيناريو 1: 200 مزرعة ───
    print("\n📋 Scenario 1: 200 farms, 20 slots")
    r = validator.validate(200, 20)
    print(f"   Batches: {r.batches_needed}")
    print(f"   Cycle: {r.cycle_duration_hours:.1f}h")
    print(f"   Farming OK: {'✅' if r.farming_ok else '❌'}")
    print(f"   Margin: {r.farming_margin_hours:.1f}h")

    # ─── سيناريو 2: زبون جديد يضيف 100 ───
    print("\n📋 Scenario 2: Adding 100 farms (200→300)")
    r = validator.validate_before_adding(200, 100, 20)
    print(f"   Valid: {'✅' if r.valid else '❌'}")
    if r.fix_needed:
        print(f"   Fix: {r.fix_details}")

    # ─── سيناريو 3: 1000 مزرعة ───
    print("\n📋 Scenario 3: Optimal slots for 1000 farms")
    optimal = validator.find_optimal_slots(1000)
    print(f"   Minimum: {optimal['minimum']['total_slots']} slots "
          f"({optimal['minimum']['servers_needed']} servers)")
    print(f"   Optimal: {optimal['optimal']['total_slots']} slots "
          f"({optimal['optimal']['servers_needed']} servers)")

    # ─── سيناريو 4: حالات مختلفة ───
    print("\n📋 Quick validation table:")
    print(f"   {'Farms':<8} {'Slots':<8} {'Cycle':<10} {'Status':<8}")
    print(f"   {'─'*8} {'─'*8} {'─'*10} {'─'*8}")

    for farms, slots in [(100, 20), (200, 20), (300, 20),
                          (300, 30), (500, 20), (500, 50),
                          (1000, 20), (1000, 100)]:
        r = validator.validate(farms, slots)
        status = "✅" if r.valid else "❌"
        print(f"   {farms:<8} {slots:<8} {r.cycle_duration_hours:<10.1f}h {status}")


if __name__ == "__main__":
    demo()
