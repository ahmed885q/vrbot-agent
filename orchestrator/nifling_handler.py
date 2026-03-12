"""
Nifling Handler - On-Demand Priority System
============================================
نظام Nifling المنفرد — حسب طلب الزبون

خصائص:
  - أولوية عالية (يقطع الدور)
  - 3 slots محجوزة دائماً
  - كل طلب مستقل عن الجدول العادي
  - الزبون يطلب والنظام ينفذ فوراً
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field

from models import (
    Farm, TaskType, TaskPriority, TaskRequest, TaskStatus, SchedulerConfig
)

logger = logging.getLogger("nifling_handler")


@dataclass
class NiflingRequest:
    """طلب nifling من زبون"""
    request_id: str
    farm_id: str
    customer_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "queued"  # queued, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def wait_time_seconds(self) -> float:
        """كم انتظر الطلب"""
        if self.started_at:
            return (self.started_at - self.created_at).total_seconds()
        return (datetime.utcnow() - self.created_at).total_seconds()


class NiflingHandler:
    """
    مُعالج طلبات Nifling

    ┌─────────────────────────────────────┐
    │         Nifling Queue               │
    │                                     │
    │  [req_1] → [req_2] → [req_3] → ... │
    │                                     │
    │  Max concurrent: 3 (محجوزة)        │
    │  Priority: FIFO per customer        │
    │  Execution: فوري                    │
    └─────────────────────────────────────┘
    """

    def __init__(self, config: SchedulerConfig = None,
                 executor: Callable = None):
        self.config = config or SchedulerConfig()
        self.executor = executor  # async function(farm_id, task_type)

        # الطابور
        self.queue: List[NiflingRequest] = []

        # الطلبات الشغّالة
        self.active: Dict[str, NiflingRequest] = {}  # farm_id -> request

        # سجل الطلبات
        self.history: List[NiflingRequest] = []

        # Max slots
        self.max_slots = self.config.nifling_reserved_slots

        self._running = False

    async def start(self):
        """تشغيل معالج Nifling"""
        self._running = True
        logger.info(f"⚔️ Nifling Handler started ({self.max_slots} slots reserved)")

        while self._running:
            await self._process_queue()
            await asyncio.sleep(3)

    async def stop(self):
        self._running = False

    async def _process_queue(self):
        """معالجة الطابور"""
        while self.queue and len(self.active) < self.max_slots:
            request = self.queue.pop(0)

            # تأكد المزرعة مش مشغولة
            if request.farm_id in self.active:
                # أرجعها آخر الطابور
                self.queue.append(request)
                continue

            # نفّذ
            asyncio.create_task(self._execute_nifling(request))

    async def _execute_nifling(self, request: NiflingRequest):
        """تنفيذ طلب nifling واحد"""
        request.status = "running"
        request.started_at = datetime.utcnow()
        self.active[request.farm_id] = request

        wait_time = request.wait_time_seconds
        logger.info(
            f"⚔️ Nifling START: farm={request.farm_id} "
            f"customer={request.customer_id} "
            f"(waited {wait_time:.0f}s)"
        )

        try:
            if self.executor:
                await self.executor(request.farm_id, TaskType.NIFLING)

            request.status = "completed"
            request.completed_at = datetime.utcnow()
            duration = (request.completed_at - request.started_at).total_seconds()

            logger.info(
                f"⚔️ Nifling DONE: farm={request.farm_id} "
                f"({duration:.0f}s)"
            )

        except Exception as e:
            request.status = "failed"
            request.error = str(e)
            logger.error(f"⚔️ Nifling FAILED: farm={request.farm_id} - {e}")

        finally:
            self.active.pop(request.farm_id, None)
            self.history.append(request)

    # ══════════════════════════════════════
    #  Public API
    # ══════════════════════════════════════

    def request_nifling(self, farm_id: str, customer_id: str) -> NiflingRequest:
        """
        API: زبون يطلب nifling لمزرعته

        Returns: NiflingRequest مع حالة الطلب
        """
        import uuid

        # تحقق: هل يوجد طلب مُعلَّق لنفس المزرعة؟
        existing = next(
            (r for r in self.queue if r.farm_id == farm_id), None
        )
        if existing:
            logger.info(f"⚔️ Nifling already queued for {farm_id}")
            return existing

        if farm_id in self.active:
            logger.info(f"⚔️ Nifling already running for {farm_id}")
            return self.active[farm_id]

        request = NiflingRequest(
            request_id=uuid.uuid4().hex[:12],
            farm_id=farm_id,
            customer_id=customer_id
        )

        self.queue.append(request)

        position = len(self.queue)
        estimated_wait = position * 10  # تقدير تقريبي

        logger.info(
            f"⚔️ Nifling QUEUED: farm={farm_id} customer={customer_id} "
            f"(position: {position}, est. wait: {estimated_wait}s)"
        )

        return request

    def get_queue_status(self) -> dict:
        """حالة طابور Nifling"""
        return {
            "queue_length": len(self.queue),
            "active_count": len(self.active),
            "max_slots": self.max_slots,
            "available_slots": self.max_slots - len(self.active),
            "queue": [
                {
                    "farm_id": r.farm_id,
                    "customer_id": r.customer_id,
                    "waiting_since": r.wait_time_seconds,
                }
                for r in self.queue
            ],
            "active": [
                {
                    "farm_id": r.farm_id,
                    "customer_id": r.customer_id,
                    "running_since": (
                        datetime.utcnow() - r.started_at
                    ).total_seconds() if r.started_at else 0,
                }
                for r in self.active.values()
            ]
        }

    def get_customer_nifling_history(self, customer_id: str) -> List[dict]:
        """سجل طلبات الزبون"""
        return [
            {
                "request_id": r.request_id,
                "farm_id": r.farm_id,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "duration": (
                    (r.completed_at - r.started_at).total_seconds()
                    if r.completed_at and r.started_at else None
                ),
            }
            for r in self.history
            if r.customer_id == customer_id
        ]
