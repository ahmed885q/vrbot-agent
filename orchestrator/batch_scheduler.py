"""
Batch Scheduler - Core Rotation Engine
=======================================
محرك الجدولة الرئيسي - يدير دوران المزارع بنظام الدفعات

النظام:
  - 200 مزرعة → 20 شغّالة بنفس الوقت
  - Farming: كل 5.5 ساعات
  - Daily: كل 24 ساعة
  - Nifling: حسب طلب الزبون (أولوية عالية)
  - Self-learning: يتعلم من الأخطاء ويحسّن نفسه
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from models import (
    Farm, FarmStatus, TaskType, TaskStatus, TaskPriority,
    TaskRequest, BatchInfo, SchedulerConfig
)

logger = logging.getLogger("batch_scheduler")


class BatchScheduler:
    """
    محرك الجدولة الرئيسي

    يدير 3 طوابير:
      1. Farming Queue  - كل 5.5 ساعات
      2. Daily Queue     - كل 24 ساعة
      3. Nifling Queue   - فوري حسب الطلب
    """

    def __init__(self, config: SchedulerConfig = None):
        self.config = config or SchedulerConfig()

        # جميع المزارع
        self.farms: Dict[str, Farm] = {}

        # الطوابير الثلاثة
        self.farming_queue: List[TaskRequest] = []
        self.daily_queue: List[TaskRequest] = []
        self.nifling_queue: List[TaskRequest] = []

        # المهام الشغّالة حالياً
        self.active_tasks: Dict[str, TaskRequest] = {}  # farm_id -> task

        # الدفعة الحالية
        self.current_batch: Optional[BatchInfo] = None
        self.batch_counter: int = 0

        # Self-Learning: تتبع الأخطاء والأنماط
        self.error_tracker = ErrorTracker()

        # حالة التشغيل
        self._running = False
        self._scheduler_task = None

    # ══════════════════════════════════════
    #  التشغيل الرئيسي
    # ══════════════════════════════════════

    async def start(self):
        """تشغيل الـ Scheduler"""
        logger.info("🚀 Batch Scheduler starting...")
        logger.info(f"   Config: {self.config.max_concurrent_farms} concurrent, "
                     f"{self.config.batch_duration_minutes}min/batch")

        self._running = True

        # تشغيل 3 loops متوازية
        await asyncio.gather(
            self._farming_loop(),
            self._daily_loop(),
            self._nifling_loop(),
            self._health_monitor()
        )

    async def stop(self):
        """إيقاف الـ Scheduler بأمان"""
        logger.info("🛑 Scheduler stopping gracefully...")
        self._running = False

        # انتظار المهام الشغّالة
        if self.active_tasks:
            logger.info(f"   Waiting for {len(self.active_tasks)} active tasks...")
            await asyncio.sleep(10)

    # ══════════════════════════════════════
    #  Loop 1: Farming (كل 5.5 ساعات)
    # ══════════════════════════════════════

    async def _farming_loop(self):
        """حلقة الزراعة - تدور كل 5.5 ساعات"""
        while self._running:
            try:
                # جمع المزارع التي تحتاج farming
                pending = self._get_farms_needing(TaskType.FARMING)

                if pending:
                    logger.info(f"🌾 Farming cycle: {len(pending)} farms need farming")
                    await self._execute_in_batches(pending, TaskType.FARMING)
                    logger.info("🌾 Farming cycle complete ✅")
                else:
                    logger.info("🌾 No farms need farming yet")

                # حساب الوقت للدورة القادمة
                next_cycle = self._calculate_next_cycle(TaskType.FARMING)
                logger.info(f"🌾 Next farming cycle in {next_cycle} minutes")

                await asyncio.sleep(next_cycle * 60)

            except Exception as e:
                logger.error(f"❌ Farming loop error: {e}")
                self.error_tracker.record_error("farming_loop", str(e))
                await asyncio.sleep(60)  # انتظر دقيقة ثم حاول مرة أخرى

    # ══════════════════════════════════════
    #  Loop 2: Daily Tasks (كل 24 ساعة)
    # ══════════════════════════════════════

    async def _daily_loop(self):
        """حلقة المهام اليومية - مرة كل 24 ساعة"""
        while self._running:
            try:
                pending = self._get_farms_needing(TaskType.DAILY)

                if pending:
                    logger.info(f"📋 Daily cycle: {len(pending)} farms need daily tasks")
                    await self._execute_in_batches(pending, TaskType.DAILY)
                    logger.info("📋 Daily cycle complete ✅")

                # انتظر حتى الدورة القادمة
                next_cycle = self._calculate_next_cycle(TaskType.DAILY)
                await asyncio.sleep(next_cycle * 60)

            except Exception as e:
                logger.error(f"❌ Daily loop error: {e}")
                self.error_tracker.record_error("daily_loop", str(e))
                await asyncio.sleep(300)

    # ══════════════════════════════════════
    #  Loop 3: Nifling (فوري - حسب الطلب)
    # ══════════════════════════════════════

    async def _nifling_loop(self):
        """حلقة Nifling - تراقب الطلبات الجديدة وتنفذها فوراً"""
        while self._running:
            try:
                if self.nifling_queue:
                    # أخذ الطلبات حسب الأولوية
                    task = self.nifling_queue.pop(0)
                    farm = self.farms.get(task.farm_id)

                    if farm:
                        # التحقق من وجود slot متاح
                        nifling_active = sum(
                            1 for t in self.active_tasks.values()
                            if t.task_type == TaskType.NIFLING
                        )

                        if nifling_active < self.config.nifling_reserved_slots:
                            logger.info(f"⚔️ Nifling: Starting for farm {farm.id} "
                                       f"(requested by {task.requested_by})")
                            await self._execute_single_task(farm, task)
                        else:
                            # الطابور ممتلئ — أرجعه للانتظار
                            self.nifling_queue.insert(0, task)
                            await asyncio.sleep(10)
                    else:
                        logger.warning(f"⚠️ Farm {task.farm_id} not found for nifling")
                else:
                    await asyncio.sleep(5)  # تحقق كل 5 ثوانٍ

            except Exception as e:
                logger.error(f"❌ Nifling loop error: {e}")
                self.error_tracker.record_error("nifling_loop", str(e))
                await asyncio.sleep(10)

    # ══════════════════════════════════════
    #  تنفيذ الدفعات
    # ══════════════════════════════════════

    async def _execute_in_batches(self, farms: List[Farm], task_type: TaskType):
        """تنفيذ قائمة مزارع على شكل دفعات"""

        batch_size = self.config.farming_slots  # 17 (20 - 3 محجوزة لـ nifling)
        batches = [farms[i:i+batch_size] for i in range(0, len(farms), batch_size)]

        for i, batch_farms in enumerate(batches):
            if not self._running:
                break

            self.batch_counter += 1
            self.current_batch = BatchInfo(
                batch_number=self.batch_counter,
                farms=[f.id for f in batch_farms],
                task_type=task_type
            )

            logger.info(f"📦 Batch {self.batch_counter}: "
                       f"{len(batch_farms)} farms ({task_type.value}) "
                       f"[{i+1}/{len(batches)}]")

            # تشغيل المزارع بالتوازي مع تأخير بسيط
            tasks = []
            for j, farm in enumerate(batch_farms):
                # تأخير تدريجي لتجنب الضغط
                delay = j * self.config.container_startup_delay_seconds
                task_req = TaskRequest(
                    farm_id=farm.id,
                    task_type=task_type,
                    priority=TaskPriority.NORMAL
                )
                tasks.append(self._delayed_execute(farm, task_req, delay))

            # انتظار اكتمال كل المزارع في الدفعة
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # تحديث إحصائيات الدفعة
            for result in results:
                if isinstance(result, Exception):
                    self.current_batch.failed_farms += 1
                else:
                    self.current_batch.completed_farms += 1

            logger.info(f"📦 Batch {self.batch_counter} complete: "
                       f"{self.current_batch.completed_farms}✅ "
                       f"{self.current_batch.failed_farms}❌")

            # استراحة بين الدفعات
            if i < len(batches) - 1:
                wait_time = self._smart_wait_time(task_type)
                logger.info(f"⏳ Waiting {wait_time}s before next batch...")
                await asyncio.sleep(wait_time)

    async def _delayed_execute(self, farm: Farm, task: TaskRequest, delay: int):
        """تنفيذ مع تأخير"""
        if delay > 0:
            await asyncio.sleep(delay)
        return await self._execute_single_task(farm, task)

    async def _execute_single_task(self, farm: Farm, task: TaskRequest):
        """تنفيذ مهمة واحدة على مزرعة واحدة"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        self.active_tasks[farm.id] = task
        farm.status = FarmStatus.RUNNING

        try:
            # ─── تشغيل الـ Container ───
            await self._start_container(farm)

            # ─── تنفيذ المهمة ───
            timeout = self._get_timeout(task.task_type)
            await asyncio.wait_for(
                self._run_task_on_farm(farm, task),
                timeout=timeout * 60
            )

            # ─── نجاح ───
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            farm.consecutive_failures = 0
            self._update_farm_timestamps(farm, task.task_type)

            # Self-Learning: تسجيل النجاح
            self.error_tracker.record_success(farm.id, task.task_type)

            logger.info(f"  ✅ Farm {farm.id} - {task.task_type.value} "
                       f"({task.duration.total_seconds():.0f}s)")

        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error_message = "timeout"
            farm.consecutive_failures += 1
            self.error_tracker.record_error(
                f"farm_{farm.id}",
                f"timeout_{task.task_type.value}",
                farm_id=farm.id
            )
            logger.warning(f"  ⏰ Farm {farm.id} - TIMEOUT")

            # إعادة المحاولة إذا لم نتجاوز الحد
            if task.retry_count < self.config.max_retries:
                await self._retry_task(farm, task)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            farm.consecutive_failures += 1
            self.error_tracker.record_error(
                f"farm_{farm.id}",
                str(e),
                farm_id=farm.id
            )
            logger.error(f"  ❌ Farm {farm.id} - ERROR: {e}")

        finally:
            # ─── إيقاف الـ Container ───
            await self._stop_container(farm)
            farm.status = FarmStatus.IDLE
            self.active_tasks.pop(farm.id, None)

    # ══════════════════════════════════════
    #  Container Management
    # ══════════════════════════════════════

    async def _start_container(self, farm: Farm):
        """تشغيل Redroid container للمزرعة"""
        # سيتم الاتصال بالسيرفر عبر SSH وتشغيل docker run
        logger.debug(f"  🐳 Starting container for farm {farm.id}")

        # TODO: ربط مع node agent
        # cmd = f"docker start farm_{farm.id}"
        # async with asyncssh.connect(farm.server_ip) as conn:
        #     await conn.run(cmd)

        await asyncio.sleep(2)  # محاكاة وقت التشغيل
        farm.status = FarmStatus.RUNNING

    async def _stop_container(self, farm: Farm):
        """إيقاف الـ container بعد انتهاء المهمة"""
        logger.debug(f"  🐳 Stopping container for farm {farm.id}")

        # TODO: ربط مع node agent
        # cmd = f"docker stop farm_{farm.id}"
        # async with asyncssh.connect(farm.server_ip) as conn:
        #     await conn.run(cmd)

        await asyncio.sleep(1)
        farm.status = FarmStatus.IDLE

    async def _run_task_on_farm(self, farm: Farm, task: TaskRequest):
        """تنفيذ المهمة الفعلية على المزرعة عبر ADB"""

        # TODO: ربط مع bot engine
        # هنا يتم إرسال الأوامر للمزرعة عبر ADB
        # مثال:
        # await adb_connect(farm.server_ip, farm.adb_port)
        # if task.task_type == TaskType.FARMING:
        #     await bot.execute_farming(farm.id)
        # elif task.task_type == TaskType.DAILY:
        #     await bot.execute_daily_tasks(farm.id)
        # elif task.task_type == TaskType.NIFLING:
        #     await bot.execute_nifling(farm.id)

        # Self-Learning: تعديل المدة حسب التجربة السابقة
        estimated_time = self.error_tracker.get_estimated_duration(
            farm.id, task.task_type
        )
        logger.debug(f"  ⏱️ Estimated duration: {estimated_time}s "
                    f"(learned from history)")

        # محاكاة
        await asyncio.sleep(5)

    # ══════════════════════════════════════
    #  Helper Methods
    # ══════════════════════════════════════

    def _get_farms_needing(self, task_type: TaskType) -> List[Farm]:
        """جمع المزارع التي تحتاج تنفيذ مهمة معينة"""
        pending = []

        for farm in self.farms.values():
            if farm.status == FarmStatus.MAINTENANCE:
                continue
            if farm.consecutive_failures >= self.config.max_retries:
                # Self-Learning: تخطي المزارع المعطّلة مؤقتاً
                cooldown = self.error_tracker.get_cooldown(farm.id)
                if cooldown and datetime.utcnow() < cooldown:
                    continue

            if task_type == TaskType.FARMING and farm.needs_farming(self.config):
                pending.append(farm)
            elif task_type == TaskType.DAILY and farm.needs_daily(self.config):
                pending.append(farm)

        # Self-Learning: ترتيب ذكي
        pending.sort(key=lambda f: self._smart_priority(f, task_type))

        return pending

    def _smart_priority(self, farm: Farm, task_type: TaskType) -> float:
        """
        Self-Learning: ترتيب ذكي للمزارع
        - المزارع الأكثر تأخراً أولاً
        - المزارع الأقل أخطاءً أولاً
        """
        score = 0.0

        # الأكثر تأخراً = أولوية أعلى
        if task_type == TaskType.FARMING:
            wait_time = farm.time_until_next_farming(self.config)
            score -= wait_time.total_seconds()  # سالب = أولوية أعلى

        # الأقل أخطاءً = أولوية أعلى
        failure_rate = self.error_tracker.get_failure_rate(farm.id)
        score += failure_rate * 1000  # المزارع المشكلجية تتأخر

        return score

    def _calculate_next_cycle(self, task_type: TaskType) -> float:
        """حساب دقائق الانتظار للدورة القادمة"""
        farms = list(self.farms.values())
        if not farms:
            return 60  # default

        if task_type == TaskType.FARMING:
            # أقرب مزرعة تحتاج farming
            min_wait = min(
                f.time_until_next_farming(self.config).total_seconds()
                for f in farms
            )
            return max(min_wait / 60, 1)  # على الأقل دقيقة واحدة

        elif task_type == TaskType.DAILY:
            return self.config.daily_interval_hours * 60

        return 60

    def _smart_wait_time(self, task_type: TaskType) -> int:
        """Self-Learning: وقت انتظار ذكي بين الدفعات"""
        # حسب نسبة الأخطاء الأخيرة
        recent_error_rate = self.error_tracker.recent_error_rate()

        base_wait = 30  # 30 ثانية أساسية

        if recent_error_rate > 0.3:
            # أخطاء كثيرة → انتظر أكثر (السيرفر مضغوط)
            return base_wait * 3
        elif recent_error_rate > 0.1:
            return base_wait * 2
        else:
            return base_wait

    def _get_timeout(self, task_type: TaskType) -> int:
        """timeout بالدقائق حسب نوع المهمة"""
        timeouts = {
            TaskType.FARMING: self.config.farming_timeout_minutes,
            TaskType.DAILY: self.config.daily_timeout_minutes,
            TaskType.NIFLING: self.config.nifling_timeout_minutes,
        }
        return timeouts.get(task_type, 30)

    def _update_farm_timestamps(self, farm: Farm, task_type: TaskType):
        """تحديث وقت آخر تنفيذ"""
        now = datetime.utcnow()
        if task_type == TaskType.FARMING:
            farm.last_farming_at = now
            farm.total_farming_runs += 1
        elif task_type == TaskType.DAILY:
            farm.last_daily_at = now
            farm.total_daily_runs += 1
        elif task_type == TaskType.NIFLING:
            farm.last_nifling_at = now
            farm.total_nifling_runs += 1

    async def _retry_task(self, farm: Farm, task: TaskRequest):
        """إعادة محاولة مهمة فاشلة"""
        task.retry_count += 1
        task.status = TaskStatus.QUEUED

        # Self-Learning: تأخير تصاعدي
        delay = self.error_tracker.get_retry_delay(farm.id, task.retry_count)
        logger.info(f"  🔄 Retry {task.retry_count}/{self.config.max_retries} "
                   f"for farm {farm.id} in {delay}s")

        await asyncio.sleep(delay)
        await self._execute_single_task(farm, task)

    # ══════════════════════════════════════
    #  Health Monitor
    # ══════════════════════════════════════

    async def _health_monitor(self):
        """مراقبة صحة النظام"""
        while self._running:
            await asyncio.sleep(300)  # كل 5 دقائق

            active = len(self.active_tasks)
            total = len(self.farms)
            error_rate = self.error_tracker.recent_error_rate()

            logger.info(
                f"📊 Health: {active}/{self.config.max_concurrent_farms} active | "
                f"{total} total farms | "
                f"Error rate: {error_rate:.1%} | "
                f"Learned patterns: {self.error_tracker.learned_patterns_count}"
            )

            # Self-Learning: تعديل الإعدادات تلقائياً
            if error_rate > 0.5:
                logger.warning("⚠️ High error rate! Reducing batch size...")
                self.config.max_concurrent_farms = max(
                    10, self.config.max_concurrent_farms - 5
                )
            elif error_rate < 0.05 and self.config.max_concurrent_farms < 20:
                logger.info("📈 Low error rate, increasing batch size...")
                self.config.max_concurrent_farms = min(
                    20, self.config.max_concurrent_farms + 2
                )

    # ══════════════════════════════════════
    #  Public API
    # ══════════════════════════════════════

    def request_nifling(self, farm_id: str, customer_id: str) -> TaskRequest:
        """
        طلب nifling من زبون
        يدخل طابور الأولوية ويُنفَّذ فوراً
        """
        task = TaskRequest(
            farm_id=farm_id,
            task_type=TaskType.NIFLING,
            priority=TaskPriority.HIGH,
            requested_by=customer_id
        )

        # إدخال حسب الأولوية
        self.nifling_queue.append(task)
        self.nifling_queue.sort(key=lambda t: -t.priority.value)

        logger.info(f"⚔️ Nifling requested: farm={farm_id} by={customer_id} "
                   f"(queue position: {self.nifling_queue.index(task)+1})")

        return task

    def add_farm(self, farm: Farm):
        """إضافة مزرعة جديدة"""
        self.farms[farm.id] = farm
        logger.info(f"➕ Farm {farm.id} added (total: {len(self.farms)})")

    def remove_farm(self, farm_id: str):
        """إزالة مزرعة"""
        if farm_id in self.farms:
            del self.farms[farm_id]
            logger.info(f"➖ Farm {farm_id} removed (total: {len(self.farms)})")

    def get_status(self) -> dict:
        """حالة النظام الحالية"""
        return {
            "total_farms": len(self.farms),
            "active_tasks": len(self.active_tasks),
            "farming_queue": len(self.farming_queue),
            "daily_queue": len(self.daily_queue),
            "nifling_queue": len(self.nifling_queue),
            "current_batch": {
                "number": self.current_batch.batch_number if self.current_batch else None,
                "progress": f"{self.current_batch.progress_percent:.0f}%" if self.current_batch else None,
            },
            "error_rate": f"{self.error_tracker.recent_error_rate():.1%}",
            "learned_patterns": self.error_tracker.learned_patterns_count,
            "config": {
                "max_concurrent": self.config.max_concurrent_farms,
                "batch_duration": self.config.batch_duration_minutes,
                "farming_interval": f"{self.config.farming_interval_hours}h",
                "nifling_slots": self.config.nifling_reserved_slots,
            }
        }


# ══════════════════════════════════════════
#  Self-Learning Error Tracker
# ══════════════════════════════════════════

class ErrorTracker:
    """
    نظام التعلم الذاتي من الأخطاء

    يتتبع:
    - أنماط الأخطاء المتكررة
    - المدة الفعلية لكل مهمة
    - أوقات الذروة للأخطاء
    - المزارع المشكلجية

    يتعلم:
    - تعديل timeout تلقائياً
    - تأخير إعادة المحاولة الذكي
    - فترة راحة للمزارع المعطّلة
    - ترتيب الدفعات الأمثل
    """

    def __init__(self):
        # سجل الأخطاء: {source: [(timestamp, error_msg), ...]}
        self.errors: Dict[str, List] = defaultdict(list)

        # سجل النجاحات: {farm_id: {task_type: [durations]}}
        self.successes: Dict[str, Dict] = defaultdict(lambda: defaultdict(list))

        # أنماط مُتعلَّمة
        self.patterns: Dict[str, dict] = {}

        # cooldown للمزارع المعطّلة: {farm_id: datetime}
        self.cooldowns: Dict[str, datetime] = {}

    def record_error(self, source: str, error_msg: str, farm_id: str = None):
        """تسجيل خطأ جديد"""
        now = datetime.utcnow()
        self.errors[source].append((now, error_msg))

        # تحليل النمط
        if farm_id:
            recent_errors = [
                e for e in self.errors.get(f"farm_{farm_id}", [])
                if (now - e[0]).total_seconds() < 3600  # آخر ساعة
            ]

            if len(recent_errors) >= 3:
                # المزرعة مشكلجية → cooldown تصاعدي
                cooldown_minutes = min(len(recent_errors) * 10, 120)  # max 2 ساعة
                self.cooldowns[farm_id] = now + timedelta(minutes=cooldown_minutes)

                # تسجيل النمط المُتعلَّم
                self.patterns[f"cooldown_{farm_id}"] = {
                    "type": "auto_cooldown",
                    "farm_id": farm_id,
                    "reason": f"{len(recent_errors)} errors in 1h",
                    "cooldown_until": self.cooldowns[farm_id].isoformat(),
                    "learned_at": now.isoformat()
                }

        # تنظيف السجلات القديمة (أكثر من 24 ساعة)
        cutoff = now - timedelta(hours=24)
        for key in list(self.errors.keys()):
            self.errors[key] = [
                e for e in self.errors[key] if e[0] > cutoff
            ]

    def record_success(self, farm_id: str, task_type: TaskType):
        """تسجيل نجاح + مدة التنفيذ"""
        self.successes[farm_id][task_type.value].append(datetime.utcnow())

        # إزالة cooldown إذا نجحت
        if farm_id in self.cooldowns:
            del self.cooldowns[farm_id]

    def get_failure_rate(self, farm_id: str) -> float:
        """نسبة فشل المزرعة"""
        errors = len(self.errors.get(f"farm_{farm_id}", []))
        successes = sum(
            len(v) for v in self.successes.get(farm_id, {}).values()
        )
        total = errors + successes
        if total == 0:
            return 0.0
        return errors / total

    def recent_error_rate(self) -> float:
        """نسبة الأخطاء في آخر ساعة"""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=1)

        total_errors = sum(
            len([e for e in errs if e[0] > cutoff])
            for errs in self.errors.values()
        )

        total_successes = sum(
            len([s for s in times if s > cutoff])
            for farm_data in self.successes.values()
            for times in farm_data.values()
        )

        total = total_errors + total_successes
        if total == 0:
            return 0.0
        return total_errors / total

    def get_cooldown(self, farm_id: str) -> Optional[datetime]:
        """وقت انتهاء الـ cooldown للمزرعة"""
        return self.cooldowns.get(farm_id)

    def get_retry_delay(self, farm_id: str, retry_count: int) -> int:
        """تأخير إعادة المحاولة — تصاعدي ذكي"""
        base_delay = 30  # 30 ثانية

        # Exponential backoff
        delay = base_delay * (2 ** (retry_count - 1))

        # Self-Learning: إذا المزرعة مشكلجية → تأخير أكبر
        failure_rate = self.get_failure_rate(farm_id)
        if failure_rate > 0.5:
            delay *= 2

        return min(delay, 600)  # max 10 دقائق

    def get_estimated_duration(self, farm_id: str, task_type: TaskType) -> int:
        """المدة المتوقعة بالثواني — مبنية على التجربة"""
        # TODO: ربط مع قاعدة البيانات لحفظ المدد الفعلية
        defaults = {
            TaskType.FARMING: 25 * 60,   # 25 دقيقة
            TaskType.DAILY: 15 * 60,     # 15 دقيقة
            TaskType.NIFLING: 30 * 60,   # 30 دقيقة
        }
        return defaults.get(task_type, 20 * 60)

    @property
    def learned_patterns_count(self) -> int:
        """عدد الأنماط المُتعلَّمة"""
        return len(self.patterns)
