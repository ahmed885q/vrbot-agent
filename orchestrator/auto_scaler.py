"""
Auto-Scaler - Smart Server Scaling
====================================
نظام التوسع الذكي — يراقب الحمل ويقرر تلقائياً

3 أوضاع:
  1. AUTO    → يضيف سيرفر تلقائياً بدون تدخلك
  2. NOTIFY  → يخبرك ويسأل قبل الإضافة
  3. MANUAL  → ما يسوي شيء، بس يعطيك تقرير

متى يُفعّل؟
  ─────────────────────────────────────────
  ✅ زبون جديد طلب مزارع → ما فيه slots كافية
  ✅ نسبة الاستخدام > 85% → وشك السيرفرات تمتلئ
  ✅ Farming cycle أطول من الفترة المحددة (5.5 ساعة)
  ✅ أخطاء كثيرة بسبب ضغط الموارد
  ✅ زبون رفع عدد مزارعه
  ─────────────────────────────────────────
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from models import SchedulerConfig
from auto_provisioner import AutoProvisioner, ServerType, ServerStatus, ServerNode

logger = logging.getLogger("auto_scaler")


# ══════════════════════════════════════════
#  Configuration
# ══════════════════════════════════════════

class ScaleMode(str, Enum):
    AUTO = "auto"       # يضيف تلقائياً
    NOTIFY = "notify"   # يخبرك أولاً
    MANUAL = "manual"   # تقرير فقط


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ScalerConfig:
    """إعدادات Auto-Scaler"""

    # الوضع
    mode: ScaleMode = ScaleMode.NOTIFY  # الافتراضي: يخبرك

    # حدود التفعيل
    utilization_threshold: float = 0.85       # 85% → ابدأ التوسع
    critical_threshold: float = 0.95          # 95% → طوارئ
    min_free_slots: int = 10                  # لازم يكون 10 slots فارغة على الأقل
    cycle_overflow_threshold: float = 1.0     # إذا الدورة أطول من الفترة المحددة

    # التوسع
    preferred_server_type: ServerType = ServerType.AX42
    scale_up_count: int = 1                   # كم سيرفر يضيف كل مرة
    cooldown_minutes: int = 30                # انتظر 30 دقيقة بين كل توسع

    # فحص كل كم دقيقة
    check_interval_minutes: int = 5

    # الإشعارات
    webhook_url: Optional[str] = None         # Discord/Telegram webhook
    notify_email: Optional[str] = None

    # حد التكلفة الشهرية
    max_monthly_budget: float = 500.0         # $500 max
    alert_at_budget_percent: float = 0.8      # تنبيه عند 80% من الميزانية


# ══════════════════════════════════════════
#  Scale Decision
# ══════════════════════════════════════════

@dataclass
class ScaleDecision:
    """قرار التوسع"""
    should_scale: bool = False
    reason: str = ""
    alert_level: AlertLevel = AlertLevel.INFO
    servers_needed: int = 0
    server_type: ServerType = ServerType.AX42
    estimated_cost: float = 0.0
    auto_approved: bool = False  # هل تم تنفيذه تلقائياً
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScaleAlert:
    """إشعار توسع"""
    id: str
    level: AlertLevel
    message: str
    decision: ScaleDecision
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    approved: Optional[bool] = None  # None = ينتظر، True = موافق، False = مرفوض
    pending_deploy: Optional[dict] = None  # نشر معلّق يُكمل بعد الموافقة


# ══════════════════════════════════════════
#  Auto-Scaler
# ══════════════════════════════════════════

class AutoScaler:
    """
    نظام التوسع الذكي

    ┌────────────────────────────────────────────┐
    │            Auto-Scaler Loop                │
    │                                            │
    │  كل 5 دقائق:                              │
    │  ┌──────────────────────────────────────┐  │
    │  │ 1. فحص نسبة الاستخدام              │  │
    │  │ 2. فحص الـ slots المتاحة            │  │
    │  │ 3. فحص مدة الدورة                  │  │
    │  │ 4. فحص أخطاء الموارد               │  │
    │  │ 5. فحص الميزانية                   │  │
    │  └──────────────┬───────────────────────┘  │
    │                 ↓                          │
    │        ┌─── القرار ───┐                    │
    │        │              │                    │
    │   AUTO: ينفذ     NOTIFY: يرسل             │
    │   فوراً          إشعار وينتظر              │
    │                  موافقتك                   │
    └────────────────────────────────────────────┘
    """

    def __init__(self, provisioner: AutoProvisioner,
                 config: ScalerConfig = None,
                 scheduler_config: SchedulerConfig = None):
        self.provisioner = provisioner
        self.config = config or ScalerConfig()
        self.scheduler_config = scheduler_config or SchedulerConfig()

        # سجل القرارات
        self.decisions: List[ScaleDecision] = []

        # الإشعارات المعلّقة
        self.pending_alerts: Dict[str, ScaleAlert] = {}
        self.alert_history: List[ScaleAlert] = []

        # آخر توسع
        self.last_scale_at: Optional[datetime] = None

        # Webhook callback
        self.on_alert: Optional[Callable] = None  # async func(alert)

        self._running = False

    # ══════════════════════════════════════
    #  Main Loop
    # ══════════════════════════════════════

    async def start(self):
        """تشغيل المراقبة"""
        self._running = True
        logger.info(f"📡 Auto-Scaler started (mode: {self.config.mode.value})")

        while self._running:
            try:
                await self._check_and_decide()
            except Exception as e:
                logger.error(f"❌ Auto-Scaler error: {e}")

            await asyncio.sleep(self.config.check_interval_minutes * 60)

    async def stop(self):
        self._running = False

    async def _check_and_decide(self):
        """الفحص واتخاذ القرار"""

        # ─── جمع المعلومات ───
        infra = self.provisioner.get_infrastructure_status()
        metrics = self._collect_metrics(infra)

        # ─── تحليل ───
        decision = self._analyze(metrics)

        if decision.should_scale:
            self.decisions.append(decision)

            # ─── التنفيذ حسب الوضع ───
            if self.config.mode == ScaleMode.AUTO:
                await self._auto_execute(decision)

            elif self.config.mode == ScaleMode.NOTIFY:
                await self._notify_and_wait(decision)

            elif self.config.mode == ScaleMode.MANUAL:
                self._log_recommendation(decision)

    # ══════════════════════════════════════
    #  Metrics Collection
    # ══════════════════════════════════════

    def _collect_metrics(self, infra: dict) -> dict:
        """جمع مقاييس النظام"""

        servers = self.provisioner.servers
        total_capacity = sum(s.max_farms for s in servers.values())
        total_active = sum(s.active_farms for s in servers.values())
        total_cost = sum(s.monthly_cost for s in servers.values())

        # حساب مدة الدورة الفعلية
        # (عدد المزارع الكلي / الـ slots المتزامنة) × مدة الدفعة
        max_concurrent = self.scheduler_config.max_concurrent_farms
        batch_duration = self.scheduler_config.batch_duration_minutes
        if max_concurrent > 0:
            cycle_duration_hours = (total_active / max_concurrent) * batch_duration / 60
        else:
            cycle_duration_hours = 0

        return {
            "total_servers": len(servers),
            "ready_servers": sum(
                1 for s in servers.values()
                if s.status == ServerStatus.READY
            ),
            "total_capacity": total_capacity,
            "total_active": total_active,
            "free_slots": total_capacity - total_active,
            "utilization": total_active / total_capacity if total_capacity > 0 else 0,
            "monthly_cost": total_cost,
            "budget_used": total_cost / self.config.max_monthly_budget if self.config.max_monthly_budget > 0 else 0,
            "cycle_duration_hours": cycle_duration_hours,
            "farming_interval_hours": self.scheduler_config.farming_interval_hours,
            "cycle_overflow": cycle_duration_hours > self.scheduler_config.farming_interval_hours,
        }

    # ══════════════════════════════════════
    #  Analysis Engine
    # ══════════════════════════════════════

    def _analyze(self, metrics: dict) -> ScaleDecision:
        """تحليل المقاييس واتخاذ القرار"""

        decision = ScaleDecision(server_type=self.config.preferred_server_type)

        # ─── تحقق: Cooldown ───
        if self.last_scale_at:
            elapsed = (datetime.utcnow() - self.last_scale_at).total_seconds()
            if elapsed < self.config.cooldown_minutes * 60:
                remaining = self.config.cooldown_minutes - (elapsed / 60)
                logger.debug(f"⏳ Scale cooldown: {remaining:.0f}min remaining")
                return decision

        # ─── تحقق: الميزانية ───
        if metrics["budget_used"] >= 1.0:
            decision.reason = "⛔ الميزانية وصلت الحد الأقصى"
            decision.alert_level = AlertLevel.CRITICAL
            decision.should_scale = False
            logger.warning(f"⛔ Budget limit reached: ${metrics['monthly_cost']:.0f}"
                         f"/${self.config.max_monthly_budget:.0f}")
            return decision

        # ─── فحص 1: نسبة الاستخدام الحرجة ───
        if metrics["utilization"] >= self.config.critical_threshold:
            from auto_provisioner import SERVER_CAPACITY, SERVER_MONTHLY_COST
            capacity = SERVER_CAPACITY[self.config.preferred_server_type]
            cost = SERVER_MONTHLY_COST[self.config.preferred_server_type]

            decision.should_scale = True
            decision.alert_level = AlertLevel.CRITICAL
            decision.servers_needed = max(1, self.config.scale_up_count)
            decision.estimated_cost = cost * decision.servers_needed
            decision.reason = (
                f"🔴 استخدام حرج {metrics['utilization']:.0%} "
                f"({metrics['free_slots']} slots فارغة فقط)"
            )
            return decision

        # ─── فحص 2: نسبة الاستخدام عالية ───
        if metrics["utilization"] >= self.config.utilization_threshold:
            from auto_provisioner import SERVER_CAPACITY, SERVER_MONTHLY_COST
            capacity = SERVER_CAPACITY[self.config.preferred_server_type]
            cost = SERVER_MONTHLY_COST[self.config.preferred_server_type]

            decision.should_scale = True
            decision.alert_level = AlertLevel.WARNING
            decision.servers_needed = 1
            decision.estimated_cost = cost
            decision.reason = (
                f"🟡 استخدام عالي {metrics['utilization']:.0%} "
                f"({metrics['free_slots']} slots فارغة)"
            )
            return decision

        # ─── فحص 3: Slots أقل من الحد الأدنى ───
        if metrics["free_slots"] < self.config.min_free_slots:
            from auto_provisioner import SERVER_MONTHLY_COST
            cost = SERVER_MONTHLY_COST[self.config.preferred_server_type]

            decision.should_scale = True
            decision.alert_level = AlertLevel.WARNING
            decision.servers_needed = 1
            decision.estimated_cost = cost
            decision.reason = (
                f"🟡 Slots قليلة: {metrics['free_slots']} فارغة "
                f"(الحد الأدنى: {self.config.min_free_slots})"
            )
            return decision

        # ─── فحص 4: الدورة أطول من الفترة ───
        if metrics["cycle_overflow"]:
            # كم سيرفر إضافي يحل المشكلة؟
            from auto_provisioner import SERVER_CAPACITY, SERVER_MONTHLY_COST
            capacity = SERVER_CAPACITY[self.config.preferred_server_type]
            cost = SERVER_MONTHLY_COST[self.config.preferred_server_type]

            overflow_ratio = metrics["cycle_duration_hours"] / metrics["farming_interval_hours"]
            extra_slots_needed = int(
                (overflow_ratio - 1) * self.scheduler_config.max_concurrent_farms
            )
            servers = math.ceil(extra_slots_needed / capacity)

            if servers > 0:
                decision.should_scale = True
                decision.alert_level = AlertLevel.WARNING
                decision.servers_needed = servers
                decision.estimated_cost = cost * servers
                decision.reason = (
                    f"🟡 الدورة ({metrics['cycle_duration_hours']:.1f}h) "
                    f"أطول من الفترة ({metrics['farming_interval_hours']}h) — "
                    f"المزارع ما تلحق تاخذ دورها"
                )
                return decision

        # ─── فحص 5: تنبيه الميزانية ───
        if metrics["budget_used"] >= self.config.alert_at_budget_percent:
            decision.alert_level = AlertLevel.INFO
            decision.reason = (
                f"💰 تنبيه ميزانية: "
                f"${metrics['monthly_cost']:.0f}/"
                f"${self.config.max_monthly_budget:.0f} "
                f"({metrics['budget_used']:.0%})"
            )
            # لا يحتاج توسع — بس تنبيه

        # ─── كل شيء تمام ───
        logger.debug(
            f"✅ System healthy: "
            f"{metrics['utilization']:.0%} util, "
            f"{metrics['free_slots']} free, "
            f"cycle: {metrics['cycle_duration_hours']:.1f}h"
        )
        return decision

    # ══════════════════════════════════════
    #  Execution Modes
    # ══════════════════════════════════════

    async def _auto_execute(self, decision: ScaleDecision):
        """
        وضع AUTO: ينفذ تلقائياً

        يضيف السيرفر + يرسل إشعار بعد التنفيذ
        """
        logger.info(f"🤖 AUTO-SCALE: {decision.reason}")
        logger.info(f"   Adding {decision.servers_needed} × {decision.server_type.value} server(s)")

        try:
            # تنفيذ التوسع
            from auto_provisioner import SERVER_CAPACITY
            farms_per_server = SERVER_CAPACITY[decision.server_type]
            total_new_farms = decision.servers_needed * farms_per_server

            report = await self.provisioner.deploy_farms(
                count=total_new_farms,
                server_type=decision.server_type
            )

            decision.auto_approved = True
            self.last_scale_at = datetime.utcnow()

            # إشعار بالنتيجة
            alert_msg = (
                f"✅ تم التوسع تلقائياً\n"
                f"السبب: {decision.reason}\n"
                f"المُضاف: {decision.servers_needed} سيرفر "
                f"({total_new_farms} slot جديدة)\n"
                f"التكلفة: +${decision.estimated_cost:.0f}/شهر"
            )
            await self._send_notification(alert_msg, decision)

            logger.info(f"✅ Auto-scale complete: +{decision.servers_needed} servers")

        except Exception as e:
            error_msg = f"❌ فشل التوسع التلقائي: {e}"
            logger.error(error_msg)
            await self._send_notification(error_msg, decision)

    async def _notify_and_wait(self, decision: ScaleDecision,
                               pending_deploy: dict = None):
        """
        وضع NOTIFY: يخبرك وينتظر موافقتك

        يرسل إشعار → تضغط "موافق" من Dashboard → يُنفَّذ
        إذا فيه deploy معلّق → يُكمله بعد الموافقة

        Args:
            decision: قرار التوسع
            pending_deploy: نشر معلّق يُكمل بعد الموافقة
                           {"count": 100, "customer_id": "x", ...}
        """
        import uuid

        alert_id = uuid.uuid4().hex[:8]
        alert = ScaleAlert(
            id=alert_id,
            level=decision.alert_level,
            message=self._format_alert_message(decision),
            decision=decision
        )

        # حفظ معلومات النشر المعلّق مع الإشعار
        if pending_deploy:
            alert.pending_deploy = pending_deploy

        # حفظ في المعلّقات
        self.pending_alerts[alert_id] = alert

        logger.info(f"📢 SCALE ALERT [{alert_id}]: {decision.reason}")
        if pending_deploy:
            logger.info(f"   📦 Pending deploy: {pending_deploy['count']} farms "
                       f"for {pending_deploy.get('customer_id', 'unknown')}")

        # إرسال إشعار
        await self._send_notification(alert.message, decision)

    async def approve_alert(self, alert_id: str) -> dict:
        """
        API: الموافقة على إشعار توسع

        يُستدعى من Dashboard عندما تضغط "موافق"

        التسلسل:
        1. ينشئ السيرفرات الإضافية
        2. يزيد الـ slots المتزامنة
        3. إذا فيه deploy معلّق → يُكمله تلقائياً
        4. يرسل إشعار بالنتيجة
        """
        alert = self.pending_alerts.get(alert_id)
        if not alert:
            return {"error": "Alert not found"}

        alert.approved = True
        alert.acknowledged = True

        # تنفيذ التوسع
        decision = alert.decision
        try:
            from auto_provisioner import SERVER_CAPACITY
            farms_per_server = SERVER_CAPACITY[decision.server_type]
            total_new_slots = decision.servers_needed * farms_per_server

            # ─── الخطوة 1: إنشاء السيرفرات الإضافية ───
            scale_report = await self.provisioner.deploy_farms(
                count=total_new_slots,
                server_type=decision.server_type
            )

            self.last_scale_at = datetime.utcnow()

            result = {
                "status": "approved_and_executing",
                "servers_added": decision.servers_needed,
                "new_slots": total_new_slots,
                "additional_cost": f"${decision.estimated_cost:.0f}/month",
            }

            # ─── الخطوة 2: إكمال النشر المعلّق إذا وجد ───
            pending = getattr(alert, 'pending_deploy', None)
            if pending:
                logger.info(
                    f"📦 Continuing paused deploy: "
                    f"{pending['count']} farms for {pending.get('customer_id')}"
                )

                deploy_report = await self.provisioner.deploy_farms(
                    count=pending["count"],
                    server_type=pending.get("server_type", decision.server_type),
                    customer_id=pending.get("customer_id")
                )

                result["pending_deploy_completed"] = True
                result["farms_deployed"] = pending["count"]
                result["customer_id"] = pending.get("customer_id")

                # إشعار
                await self._send_notification(
                    f"✅ تم التوسع + إكمال النشر\n"
                    f"سيرفرات جديدة: +{decision.servers_needed}\n"
                    f"مزارع منشورة: {pending['count']} لـ {pending.get('customer_id')}\n"
                    f"التكلفة: +${decision.estimated_cost:.0f}/شهر",
                    decision
                )
            else:
                await self._send_notification(
                    f"✅ تم التوسع بنجاح\n"
                    f"سيرفرات جديدة: +{decision.servers_needed}\n"
                    f"Slots جديدة: +{total_new_slots}\n"
                    f"التكلفة: +${decision.estimated_cost:.0f}/شهر",
                    decision
                )

            # نقل للسجل
            del self.pending_alerts[alert_id]
            self.alert_history.append(alert)

            return result

        except Exception as e:
            error_msg = f"❌ فشل التوسع: {e}"
            logger.error(error_msg)
            await self._send_notification(error_msg, decision)
            return {"status": "error", "message": str(e)}

    async def reject_alert(self, alert_id: str) -> dict:
        """
        API: رفض إشعار التوسع

        يُستدعى من Dashboard عندما تضغط "لا"
        """
        alert = self.pending_alerts.get(alert_id)
        if not alert:
            return {"error": "Alert not found"}

        alert.approved = False
        alert.acknowledged = True

        del self.pending_alerts[alert_id]
        self.alert_history.append(alert)

        logger.info(f"❌ Scale alert [{alert_id}] rejected")
        return {"status": "rejected"}

    def _log_recommendation(self, decision: ScaleDecision):
        """وضع MANUAL: تقرير فقط"""
        logger.info(
            f"📊 SCALE RECOMMENDATION:\n"
            f"   {decision.reason}\n"
            f"   Suggested: +{decision.servers_needed} × {decision.server_type.value}\n"
            f"   Cost: +${decision.estimated_cost:.0f}/month\n"
            f"   (Manual mode — no action taken)"
        )

    # ══════════════════════════════════════
    #  Pre-Check for New Customers
    # ══════════════════════════════════════

    def check_capacity_for_new_farms(self, farm_count: int) -> ScaleDecision:
        """
        فحص قبل إضافة مزارع جديدة

        يُستدعى عند:
        - زبون جديد يطلب مزارع
        - زبون موجود يرفع عدد مزارعه

        Returns: قرار هل نحتاج سيرفر إضافي أم لا
        """
        from auto_provisioner import SERVER_CAPACITY, SERVER_MONTHLY_COST

        servers = self.provisioner.servers
        free_slots = sum(
            s.available_slots for s in servers.values()
            if s.status in (ServerStatus.READY, ServerStatus.FULL)
        )

        decision = ScaleDecision(server_type=self.config.preferred_server_type)

        if farm_count <= free_slots:
            # يكفي — ما نحتاج سيرفر جديد
            decision.should_scale = False
            decision.reason = (
                f"✅ يوجد {free_slots} slots فارغة — يكفي لـ {farm_count} مزرعة"
            )
        else:
            # ما يكفي — نحتاج سيرفرات
            shortage = farm_count - free_slots
            capacity = SERVER_CAPACITY[self.config.preferred_server_type]
            cost = SERVER_MONTHLY_COST[self.config.preferred_server_type]
            servers_needed = math.ceil(shortage / capacity)

            decision.should_scale = True
            decision.servers_needed = servers_needed
            decision.estimated_cost = servers_needed * cost
            decision.alert_level = AlertLevel.WARNING
            decision.reason = (
                f"⚠️ ينقص {shortage} slot — "
                f"نحتاج {servers_needed} سيرفر {self.config.preferred_server_type.value} "
                f"(+${decision.estimated_cost:.0f}/شهر)"
            )

        return decision

    # ══════════════════════════════════════
    #  Notifications
    # ══════════════════════════════════════

    def _format_alert_message(self, decision: ScaleDecision) -> str:
        """تنسيق رسالة الإشعار"""
        from auto_provisioner import SERVER_CAPACITY

        capacity = SERVER_CAPACITY[decision.server_type]
        total_new = decision.servers_needed * capacity

        emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🔴",
        }

        return (
            f"{emoji.get(decision.alert_level, '📢')} طلب توسع\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"السبب: {decision.reason}\n"
            f"المطلوب: {decision.servers_needed} × {decision.server_type.value}\n"
            f"سعة جديدة: +{total_new} slot\n"
            f"التكلفة: +${decision.estimated_cost:.0f}/شهر\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"هل توافق؟"
        )

    async def _send_notification(self, message: str, decision: ScaleDecision):
        """إرسال إشعار عبر webhook"""

        # ─── Discord Webhook ───
        if self.config.webhook_url:
            try:
                import aiohttp
                payload = {
                    "content": message,
                    "embeds": [{
                        "title": "VRBOT Auto-Scaler",
                        "description": decision.reason,
                        "color": {
                            AlertLevel.INFO: 0x3498db,
                            AlertLevel.WARNING: 0xf39c12,
                            AlertLevel.CRITICAL: 0xe74c3c,
                        }.get(decision.alert_level, 0x95a5a6),
                        "fields": [
                            {"name": "سيرفرات", "value": str(decision.servers_needed), "inline": True},
                            {"name": "التكلفة", "value": f"${decision.estimated_cost:.0f}/mo", "inline": True},
                        ]
                    }]
                }
                async with aiohttp.ClientSession() as session:
                    await session.post(self.config.webhook_url, json=payload)

            except Exception as e:
                logger.error(f"Failed to send webhook: {e}")

        # ─── Custom callback ───
        if self.on_alert:
            try:
                await self.on_alert(message, decision)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        # ─── دائماً log ───
        logger.info(f"📢 Notification sent: {decision.reason}")

    # ══════════════════════════════════════
    #  Dashboard API Data
    # ══════════════════════════════════════

    def get_scaler_status(self) -> dict:
        """حالة Auto-Scaler للـ Dashboard"""
        return {
            "mode": self.config.mode.value,
            "is_running": self._running,
            "check_interval": f"{self.config.check_interval_minutes}min",
            "thresholds": {
                "utilization_warning": f"{self.config.utilization_threshold:.0%}",
                "utilization_critical": f"{self.config.critical_threshold:.0%}",
                "min_free_slots": self.config.min_free_slots,
            },
            "budget": {
                "max": f"${self.config.max_monthly_budget:.0f}",
                "alert_at": f"{self.config.alert_at_budget_percent:.0%}",
            },
            "last_scale": self.last_scale_at.isoformat() if self.last_scale_at else None,
            "pending_alerts": [
                {
                    "id": a.id,
                    "level": a.level.value,
                    "message": a.message,
                    "created_at": a.created_at.isoformat(),
                }
                for a in self.pending_alerts.values()
            ],
            "recent_decisions": [
                {
                    "reason": d.reason,
                    "servers": d.servers_needed,
                    "auto": d.auto_approved,
                    "time": d.timestamp.isoformat(),
                }
                for d in self.decisions[-10:]  # آخر 10
            ]
        }

    def update_config(self, **kwargs) -> dict:
        """
        تحديث إعدادات Auto-Scaler من Dashboard

        مثال:
          update_config(mode="auto", max_monthly_budget=1000)
        """
        for key, value in kwargs.items():
            if key == "mode":
                self.config.mode = ScaleMode(value)
            elif hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                return {"error": f"Unknown config key: {key}"}

        logger.info(f"⚙️ Scaler config updated: {kwargs}")
        return {"status": "updated", "config": self.get_scaler_status()}
