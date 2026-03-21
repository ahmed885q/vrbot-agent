"""
Batch Scheduler - Data Models & Configuration
==============================================
نماذج البيانات وإعدادات النظام لجدولة المزارع بنظام الدفعات
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import uuid
from vrbot_models import FarmCommand, APIResponse, Farm


# ──────────────────────────────────────────
#  Enums
# ──────────────────────────────────────────

class FarmStatus(str, Enum):
    IDLE = "idle"                # خاملة - تنتظر دورها
    STARTING = "starting"        # يتم تشغيل الـ container
    RUNNING = "running"          # شغّالة - تنفذ مهمة
    STOPPING = "stopping"        # يتم إيقافها
    ERROR = "error"              # خطأ
    MAINTENANCE = "maintenance"  # صيانة


class TaskType(str, Enum):
    FARMING = "farming"          # كل 5.5 ساعات
    DAILY = "daily"              # كل 24 ساعة
    NIFLING = "nifling"          # حسب طلب الزبون


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    LOW = 0        # مهام يومية
    NORMAL = 1     # farming عادي
    HIGH = 2       # nifling (طلب زبون)
    URGENT = 3     # إعادة محاولة بعد فشل


# ──────────────────────────────────────────
#  Configuration
# ──────────────────────────────────────────

@dataclass
class SchedulerConfig:
    """إعدادات الـ Batch Scheduler"""

    # عدد المزارع الشغّالة بنفس الوقت
    max_concurrent_farms: int = 20

    # مدة تشغيل كل دفعة بالدقائق
    batch_duration_minutes: int = 30

    # فترات الجدولة
    farming_interval_hours: float = 5.5     # كل 5 ساعات ونص
    daily_interval_hours: float = 24.0      # كل 24 ساعة

    # وقت انتظار بين تشغيل كل container
    container_startup_delay_seconds: int = 5

    # عدد المحاولات عند الفشل
    max_retries: int = 3

    # timeout لكل مهمة بالدقائق
    farming_timeout_minutes: int = 30
    daily_timeout_minutes: int = 20
    nifling_timeout_minutes: int = 45

    # عدد slots محجوزة لـ nifling (من الـ 20)
    nifling_reserved_slots: int = 3

    @property
    def farming_slots(self) -> int:
        """الـ slots المتاحة للمهام العادية"""
        return self.max_concurrent_farms - self.nifling_reserved_slots


# ──────────────────────────────────────────
#  Data Models
# ──────────────────────────────────────────

@dataclass
class Farm:
    """نموذج المزرعة"""
    id: str
    customer_id: str
    server_ip: str

    # الحالة
    status: FarmStatus = FarmStatus.IDLE
    container_name: Optional[str] = None
    adb_port: Optional[int] = None

    # آخر تنفيذ لكل مهمة
    last_farming_at: Optional[datetime] = None
    last_daily_at: Optional[datetime] = None
    last_nifling_at: Optional[datetime] = None

    # إحصائيات
    total_farming_runs: int = 0
    total_daily_runs: int = 0
    total_nifling_runs: int = 0
    consecutive_failures: int = 0

    # إعدادات الزبون
    nifling_enabled: bool = False
    nifling_schedule: Optional[str] = None  # cron expression أو None = يدوي

    def needs_farming(self, config: SchedulerConfig) -> bool:
        """هل المزرعة تحتاج farming؟"""
        if self.last_farming_at is None:
            return True
        elapsed = datetime.utcnow() - self.last_farming_at
        return elapsed >= timedelta(hours=config.farming_interval_hours)

    def needs_daily(self, config: SchedulerConfig) -> bool:
        """هل المزرعة تحتاج مهام يومية؟"""
        if self.last_daily_at is None:
            return True
        elapsed = datetime.utcnow() - self.last_daily_at
        return elapsed >= timedelta(hours=config.daily_interval_hours)

    def time_until_next_farming(self, config: SchedulerConfig) -> timedelta:
        """الوقت المتبقي لـ farming القادم"""
        if self.last_farming_at is None:
            return timedelta(0)
        next_run = self.last_farming_at + timedelta(hours=config.farming_interval_hours)
        remaining = next_run - datetime.utcnow()
        return max(remaining, timedelta(0))


@dataclass
class TaskRequest:
    """طلب تنفيذ مهمة"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    farm_id: str = ""
    task_type: TaskType = TaskType.FARMING
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED

    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    retry_count: int = 0
    error_message: Optional[str] = None

    # للـ nifling
    requested_by: Optional[str] = None  # customer_id

    @property
    def duration(self) -> Optional[timedelta]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class BatchInfo:
    """معلومات الدفعة الحالية"""
    batch_number: int
    farms: list
    task_type: TaskType
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_farms: int = 0
    failed_farms: int = 0

    @property
    def total_farms(self) -> int:
        return len(self.farms)

    @property
    def progress_percent(self) -> float:
        if self.total_farms == 0:
            return 0
        return (self.completed_farms / self.total_farms) * 100

    @property
    def is_complete(self) -> bool:
        return (self.completed_farms + self.failed_farms) >= self.total_farms
