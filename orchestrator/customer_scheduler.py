"""
Customer-Aware Scheduler
========================
جدولة عادلة لكل زبون — بغض النظر عن عدد مزارعه

المشكلة:
  - زبون عنده 20 مزرعة
  - زبون عنده 100 مزرعة
  - كلهم لازم يحصلوا على مهامهم كاملة ومجدولة

الحل:
  - كل زبون له جدول مستقل
  - النظام يوزع الـ slots بعدالة
  - المزارع تدور بالتناوب ضمن حصة الزبون
"""

import asyncio
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from models import (
    Farm, FarmStatus, TaskType, TaskPriority,
    TaskRequest, SchedulerConfig
)

logger = logging.getLogger("customer_scheduler")


# ══════════════════════════════════════════
#  Customer Profile
# ══════════════════════════════════════════

@dataclass
class CustomerProfile:
    """ملف الزبون — يحتوي جدوله ومزارعه"""
    customer_id: str
    farms: List[str] = field(default_factory=list)  # farm IDs

    # إعدادات الجدولة
    farming_interval_hours: float = 5.5
    daily_tasks_enabled: bool = True
    nifling_enabled: bool = False

    # الحصة من الـ slots (يُحسب تلقائياً)
    allocated_slots: int = 0

    # تتبع الدورات
    current_farming_index: int = 0   # أين وصلنا في دورة الزراعة
    current_daily_index: int = 0     # أين وصلنا في المهام اليومية
    last_full_cycle_at: Optional[datetime] = None

    @property
    def farm_count(self) -> int:
        return len(self.farms)

    @property
    def batches_needed(self) -> int:
        """عدد الدفعات اللازمة لتغطية كل مزارع الزبون"""
        if self.allocated_slots == 0:
            return 0
        return math.ceil(self.farm_count / self.allocated_slots)

    @property
    def cycle_duration_minutes(self) -> float:
        """المدة الكلية لدورة واحدة كاملة بالدقائق"""
        return self.batches_needed * 30  # 30 دقيقة لكل دفعة


class CustomerScheduler:
    """
    المُجدول العادل للزبائن

    كيف يعمل:
    ═══════════════════════════════════════════════
    مجموع السيرفر: 20 slot متزامنة

    مثال: 3 زبائن
    ┌──────────────┬────────┬───────┬────────────┐
    │    الزبون    │ مزارع  │ slots │  الدورة    │
    ├──────────────┼────────┼───────┼────────────┤
    │ زبون A       │  20    │   3   │ 7 دفعات   │
    │ زبون B       │  50    │   7   │ 8 دفعات   │
    │ زبون C       │ 100    │  10   │ 10 دفعات  │
    └──────────────┴────────┴───────┴────────────┘

    الـ 20 slot تتوزع بالتناسب مع عدد المزارع
    كل زبون يحصل على حصته ومزارعه تدور ضمنها
    ═══════════════════════════════════════════════
    """

    def __init__(self, config: SchedulerConfig = None):
        self.config = config or SchedulerConfig()
        self.customers: Dict[str, CustomerProfile] = {}
        self.all_farms: Dict[str, Farm] = {}

        # الحصص
        self._total_slots = self.config.max_concurrent_farms
        self._nifling_reserved = self.config.nifling_reserved_slots
        self._schedulable_slots = self._total_slots - self._nifling_reserved

    # ══════════════════════════════════════
    #  إدارة الزبائن
    # ══════════════════════════════════════

    def register_customer(self, customer_id: str,
                          farm_ids: List[str],
                          nifling_enabled: bool = False) -> CustomerProfile:
        """تسجيل زبون جديد مع مزارعه"""
        profile = CustomerProfile(
            customer_id=customer_id,
            farms=farm_ids,
            nifling_enabled=nifling_enabled
        )
        self.customers[customer_id] = profile

        # إعادة حساب الحصص
        self._recalculate_slots()

        logger.info(
            f"👤 Customer {customer_id} registered: "
            f"{len(farm_ids)} farms, "
            f"{profile.allocated_slots} slots allocated"
        )
        return profile

    def add_farms_to_customer(self, customer_id: str, new_farm_ids: List[str]):
        """إضافة مزارع لزبون موجود"""
        if customer_id not in self.customers:
            raise ValueError(f"Customer {customer_id} not found")

        self.customers[customer_id].farms.extend(new_farm_ids)
        self._recalculate_slots()

        logger.info(
            f"➕ Added {len(new_farm_ids)} farms to {customer_id} "
            f"(total: {self.customers[customer_id].farm_count})"
        )

    def _recalculate_slots(self):
        """
        إعادة حساب حصة كل زبون من الـ slots

        الخوارزمية:
        1. الحصة = (مزارع الزبون / إجمالي المزارع) × الـ slots المتاحة
        2. كل زبون يحصل على slot واحد على الأقل
        3. الباقي يُوزَّع على الأكبر
        """
        total_farms = sum(c.farm_count for c in self.customers.values())
        if total_farms == 0:
            return

        available = self._schedulable_slots

        # حساب الحصة النسبية
        raw_allocations = {}
        for cid, customer in self.customers.items():
            raw = (customer.farm_count / total_farms) * available
            raw_allocations[cid] = raw

        # تحويل لأعداد صحيحة مع ضمان 1 على الأقل
        allocated = {}
        for cid, raw in raw_allocations.items():
            allocated[cid] = max(1, int(raw))

        # توزيع الفائض
        remaining = available - sum(allocated.values())
        if remaining > 0:
            # أعطي الفائض للزبائن الأكبر (بالترتيب)
            sorted_customers = sorted(
                allocated.keys(),
                key=lambda c: self.customers[c].farm_count,
                reverse=True
            )
            for cid in sorted_customers:
                if remaining <= 0:
                    break
                allocated[cid] += 1
                remaining -= 1

        # تحديث الملفات
        for cid, slots in allocated.items():
            self.customers[cid].allocated_slots = slots

        self._log_allocation_table()

    def _log_allocation_table(self):
        """طباعة جدول التوزيع"""
        logger.info("╔══════════════════════════════════════════════╗")
        logger.info("║          Slot Allocation Table               ║")
        logger.info("╠══════════════╦════════╦═══════╦═════════════╣")
        logger.info("║   Customer   ║ Farms  ║ Slots ║ Cycle Time  ║")
        logger.info("╠══════════════╬════════╬═══════╬═════════════╣")

        for c in self.customers.values():
            cycle = f"{c.cycle_duration_minutes:.0f}min"
            logger.info(
                f"║ {c.customer_id[:12]:12s} "
                f"║ {c.farm_count:6d} "
                f"║ {c.allocated_slots:5d} "
                f"║ {cycle:11s} ║"
            )

        total = sum(c.allocated_slots for c in self.customers.values())
        logger.info("╠══════════════╬════════╬═══════╬═════════════╣")
        logger.info(
            f"║ {'TOTAL':12s} "
            f"║ {sum(c.farm_count for c in self.customers.values()):6d} "
            f"║ {total:5d} "
            f"║ {'':11s} ║"
        )
        logger.info("╚══════════════╩════════╩═══════╩═════════════╝")

    # ══════════════════════════════════════
    #  الجدولة الرئيسية
    # ══════════════════════════════════════

    async def run_farming_cycle(self, executor_callback):
        """
        تشغيل دورة farming كاملة لكل الزبائن

        executor_callback: async function(farm_ids, task_type) -> results

        الطريقة:
        ─────────────────────────────────────────
        بدل تشغيل كل زبون لحاله (يطوّل)
        نشغل من كل زبون دفعته الحالية بالتوازي

        Round 1: [A-batch1 + B-batch1 + C-batch1] = 20 slots
        Round 2: [A-batch2 + B-batch2 + C-batch2] = 20 slots
        ...
        حتى ينتهي الكل
        ─────────────────────────────────────────
        """
        logger.info("🌾 ═══ Starting Farming Cycle for ALL customers ═══")

        # تحضير دفعات كل زبون
        customer_batches = {}
        for cid, customer in self.customers.items():
            farms_needing = self._get_customer_farms_needing(cid, TaskType.FARMING)
            if farms_needing:
                batches = self._split_into_batches(
                    farms_needing, customer.allocated_slots
                )
                customer_batches[cid] = batches
                logger.info(
                    f"  👤 {cid}: {len(farms_needing)} farms → "
                    f"{len(batches)} batches × {customer.allocated_slots} slots"
                )

        if not customer_batches:
            logger.info("  No farms need farming")
            return

        # تنفيذ Round-Robin
        max_rounds = max(len(b) for b in customer_batches.values())

        for round_num in range(max_rounds):
            logger.info(f"\n  📦 Round {round_num + 1}/{max_rounds}")

            # جمع الدفعة الحالية من كل زبون
            round_tasks = []
            for cid, batches in customer_batches.items():
                if round_num < len(batches):
                    batch = batches[round_num]
                    for farm_id in batch:
                        round_tasks.append({
                            "farm_id": farm_id,
                            "customer_id": cid,
                            "task_type": TaskType.FARMING
                        })

            if round_tasks:
                logger.info(f"    → {len(round_tasks)} farms across "
                           f"{len(set(t['customer_id'] for t in round_tasks))} customers")

                # تنفيذ
                farm_ids = [t["farm_id"] for t in round_tasks]
                await executor_callback(farm_ids, TaskType.FARMING)

                # تحديث indexes
                for cid, batches in customer_batches.items():
                    if round_num < len(batches):
                        self.customers[cid].current_farming_index += len(
                            batches[round_num]
                        )

            # استراحة بين الراوندات
            if round_num < max_rounds - 1:
                await asyncio.sleep(30)

        # تحديث وقت آخر دورة كاملة
        for cid in customer_batches:
            self.customers[cid].last_full_cycle_at = datetime.utcnow()
            self.customers[cid].current_farming_index = 0  # reset

        logger.info("🌾 ═══ Farming Cycle Complete ═══\n")

    async def run_daily_cycle(self, executor_callback):
        """تشغيل المهام اليومية — نفس المبدأ"""
        logger.info("📋 ═══ Starting Daily Cycle for ALL customers ═══")

        customer_batches = {}
        for cid, customer in self.customers.items():
            if not customer.daily_tasks_enabled:
                continue
            farms_needing = self._get_customer_farms_needing(cid, TaskType.DAILY)
            if farms_needing:
                batches = self._split_into_batches(
                    farms_needing, customer.allocated_slots
                )
                customer_batches[cid] = batches

        if not customer_batches:
            logger.info("  No farms need daily tasks")
            return

        max_rounds = max(len(b) for b in customer_batches.values())

        for round_num in range(max_rounds):
            round_tasks = []
            for cid, batches in customer_batches.items():
                if round_num < len(batches):
                    for farm_id in batches[round_num]:
                        round_tasks.append(farm_id)

            if round_tasks:
                await executor_callback(round_tasks, TaskType.DAILY)

            if round_num < max_rounds - 1:
                await asyncio.sleep(30)

        logger.info("📋 ═══ Daily Cycle Complete ═══\n")

    # ══════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════

    def _get_customer_farms_needing(self, customer_id: str,
                                     task_type: TaskType) -> List[str]:
        """المزارع التي تحتاج تنفيذ من زبون معين"""
        customer = self.customers.get(customer_id)
        if not customer:
            return []

        needing = []
        for farm_id in customer.farms:
            farm = self.all_farms.get(farm_id)
            if not farm:
                continue
            if farm.status == FarmStatus.MAINTENANCE:
                continue

            if task_type == TaskType.FARMING and farm.needs_farming(self.config):
                needing.append(farm_id)
            elif task_type == TaskType.DAILY and farm.needs_daily(self.config):
                needing.append(farm_id)

        return needing

    def _split_into_batches(self, items: list, batch_size: int) -> List[list]:
        """تقسيم قائمة إلى دفعات"""
        if batch_size <= 0:
            batch_size = 1
        return [items[i:i+batch_size] for i in range(0, len(items), batch_size)]

    # ══════════════════════════════════════
    #  Dashboard API
    # ══════════════════════════════════════

    def get_customer_schedule(self, customer_id: str) -> dict:
        """
        جدول الزبون — يُعرض في Dashboard

        مثال للزبون عنده 100 مزرعة:
        {
          "customer_id": "cust_abc",
          "total_farms": 100,
          "allocated_slots": 10,
          "farming": {
            "interval": "5.5h",
            "batches": 10,
            "cycle_duration": "300min (5h)",
            "next_run": "2026-03-07T15:30:00Z"
          },
          "daily": {
            "interval": "24h",
            "next_run": "2026-03-08T00:00:00Z"
          },
          "nifling": "on-demand"
        }
        """
        customer = self.customers.get(customer_id)
        if not customer:
            return {"error": "Customer not found"}

        return {
            "customer_id": customer_id,
            "total_farms": customer.farm_count,
            "allocated_slots": customer.allocated_slots,
            "farming": {
                "interval": f"{customer.farming_interval_hours}h",
                "batches_needed": customer.batches_needed,
                "cycle_duration": f"{customer.cycle_duration_minutes:.0f}min",
                "fits_in_interval": customer.cycle_duration_minutes <= (
                    customer.farming_interval_hours * 60
                ),
                "last_full_cycle": (
                    customer.last_full_cycle_at.isoformat()
                    if customer.last_full_cycle_at else None
                ),
            },
            "daily": {
                "enabled": customer.daily_tasks_enabled,
                "interval": "24h",
            },
            "nifling": {
                "enabled": customer.nifling_enabled,
                "mode": "on-demand",
            }
        }

    def get_all_schedules_summary(self) -> dict:
        """ملخص لكل الزبائن"""
        total_farms = sum(c.farm_count for c in self.customers.values())
        total_slots = sum(c.allocated_slots for c in self.customers.values())

        return {
            "total_customers": len(self.customers),
            "total_farms": total_farms,
            "total_slots_used": f"{total_slots}/{self._schedulable_slots}",
            "nifling_reserved_slots": self._nifling_reserved,
            "customers": {
                cid: {
                    "farms": c.farm_count,
                    "slots": c.allocated_slots,
                    "cycle": f"{c.cycle_duration_minutes:.0f}min",
                    "fits": c.cycle_duration_minutes <= (c.farming_interval_hours * 60)
                }
                for cid, c in self.customers.items()
            }
        }


# ══════════════════════════════════════════
#  مثال عملي
# ══════════════════════════════════════════

async def example():
    """
    مثال: 3 زبائن بأحجام مختلفة

    النتيجة المتوقعة:
    ┌──────────────┬────────┬───────┬──────────┬──────────────┐
    │    الزبون    │ مزارع  │ slots │ دفعات   │ مدة الدورة   │
    ├──────────────┼────────┼───────┼──────────┼──────────────┤
    │ أحمد         │  20    │   2   │  10      │  300min(5h)  │
    │ محمد         │  50    │   5   │  10      │  300min(5h)  │
    │ خالد         │ 100    │  10   │  10      │  300min(5h)  │
    └──────────────┴────────┴───────┴──────────┴──────────────┘

    الكل يخلص في 5 ساعات ✅ (أقل من 5.5 ساعة)
    """
    scheduler = CustomerScheduler()

    # تسجيل الزبائن
    scheduler.register_customer(
        "ahmed",
        [f"ahmed_farm_{i}" for i in range(20)],
        nifling_enabled=True
    )

    scheduler.register_customer(
        "mohammed",
        [f"mohammed_farm_{i}" for i in range(50)]
    )

    scheduler.register_customer(
        "khaled",
        [f"khaled_farm_{i}" for i in range(100)],
        nifling_enabled=True
    )

    # عرض التوزيع
    summary = scheduler.get_all_schedules_summary()
    print("\n📊 Schedule Summary:")
    for cid, info in summary["customers"].items():
        print(f"  {cid}: {info['farms']} farms → "
              f"{info['slots']} slots, "
              f"cycle: {info['cycle']}, "
              f"fits: {'✅' if info['fits'] else '❌'}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example())
