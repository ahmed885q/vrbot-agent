"""
FastAPI Endpoints - Dashboard Integration
==========================================
واجهة API للـ Dashboard — تربط كل المكونات

الـ Endpoints:
  POST /deploy           → نشر مزارع جديدة (مع تحقق الجدول)
  POST /nifling/request  → طلب nifling من زبون
  GET  /schedule/{id}    → جدول زبون معين
  GET  /status           → حالة النظام الكاملة
  POST /servers/ready    → إبلاغ جاهزية سيرفر (من Cloud-Init)

  GET  /scaler/status         → حالة Auto-Scaler
  PUT  /scaler/config         → تحديث إعدادات Scaler
  POST /scaler/alerts/approve → الموافقة على توسع
  POST /scaler/alerts/reject  → رفض توسع
  GET  /validate/{farms}      → تحقق قبل الإضافة
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import logging

from batch_scheduler import BatchScheduler
from customer_scheduler import CustomerScheduler
from nifling_handler import NiflingHandler
from auto_provisioner import AutoProvisioner, ServerType
from auto_scaler import AutoScaler, ScalerConfig, ScaleMode
from cycle_validator import CycleValidator
from models import SchedulerConfig

logger = logging.getLogger("api")

# ══════════════════════════════════════════
#  App Setup
# ══════════════════════════════════════════

app = FastAPI(
    title="VRBOT Batch Scheduler",
    description="نظام جدولة المزارع بنظام الدفعات الذكي",
    version="1.0.0"
)

# المكونات
config = SchedulerConfig()
batch_scheduler = BatchScheduler(config)
customer_scheduler = CustomerScheduler(config)
nifling_handler = NiflingHandler(config)
provisioner = AutoProvisioner()
scaler = AutoScaler(provisioner, ScalerConfig(), config)
validator = CycleValidator(config)


# ══════════════════════════════════════════
#  Request Models
# ══════════════════════════════════════════

class DeployRequest(BaseModel):
    """طلب نشر مزارع"""
    farm_count: int
    customer_id: str
    server_type: str = "ax42"  # ax41 or ax42
    nifling_enabled: bool = False

class NiflingRequest(BaseModel):
    """طلب nifling"""
    farm_id: str
    customer_id: str

class ServerReadyRequest(BaseModel):
    """إبلاغ جاهزية سيرفر من Cloud-Init"""
    server_id: str
    ip: str
    max_farms: int

class AddFarmsRequest(BaseModel):
    """إضافة مزارع لزبون"""
    customer_id: str
    farm_count: int


# ══════════════════════════════════════════
#  Deployment Endpoints
# ══════════════════════════════════════════

@app.post("/api/deploy")
async def deploy_farms(req: DeployRequest, background: BackgroundTasks):
    """
    🚀 نشر مزارع جديدة — الزر "Deploy" في Dashboard

    يقوم بـ:
    1. حساب السيرفرات المطلوبة
    2. إنشاء السيرفرات عبر Hetzner API
    3. Cloud-Init يثبت كل شيء
    4. إنشاء Redroid containers
    5. تسجيل الزبون في الجدول
    """
    server_type = ServerType.AX42 if req.server_type == "ax42" else ServerType.AX41

    # ─── فحص مسبق: هل نحتاج سيرفر إضافي؟ ───
    existing_farms = sum(
        c.farm_count for c in customer_scheduler.customers.values()
    )
    current_slots = config.max_concurrent_farms
    pre_check = validator.validate_before_adding(
        existing_farms, req.farm_count, current_slots
    )

    # تشغيل النشر في الخلفية
    background.add_task(
        _deploy_and_register,
        req.farm_count,
        req.customer_id,
        server_type,
        req.nifling_enabled
    )

    # ─── الجواب يعتمد على الحالة ───
    if pre_check.valid:
        return {
            "status": "deploying",
            "message": f"Deploying {req.farm_count} farms for {req.customer_id}",
            "needs_scaling": False,
            "estimated_time": "15-20 minutes"
        }
    else:
        return {
            "status": "pending_approval" if scaler.config.mode == ScaleMode.NOTIFY else "deploying",
            "message": f"Deploying {req.farm_count} farms for {req.customer_id}",
            "needs_scaling": True,
            "scaling_mode": scaler.config.mode.value,
            "extra_servers_needed": pre_check.extra_servers_needed,
            "extra_cost": f"${pre_check.extra_servers_needed * (55 if server_type == ServerType.AX42 else 44)}/month",
            "reason": pre_check.fix_details,
            "action": {
                "notify": "Check /api/scaler/status for pending alerts → approve or reject",
                "auto": "Scaling automatically, check /api/status for progress",
                "manual": "Deploy blocked — add servers manually first",
            }.get(scaler.config.mode.value, ""),
            "estimated_time": "20-30 minutes (including new server setup)"
        }


async def _deploy_and_register(count: int, customer_id: str,
                                server_type: ServerType,
                                nifling_enabled: bool):
    """النشر + التسجيل في الجدول"""
    try:
        # ─── التحقق من الجدول قبل النشر ───
        existing_farms = sum(
            c.farm_count for c in customer_scheduler.customers.values()
        )
        current_slots = config.max_concurrent_farms
        check = validator.validate_before_adding(existing_farms, count, current_slots)

        if not check.valid and check.fix_needed:
            logger.warning(f"⚠️ Schedule will break! {check.fix_details}")

            if scaler.config.mode == ScaleMode.NOTIFY:
                # ─── وضع NOTIFY: أخبر المالك وانتظر موافقته ───
                from auto_scaler import ScaleDecision, AlertLevel
                decision = ScaleDecision(
                    should_scale=True,
                    reason=f"نشر {count} مزرعة لـ {customer_id} يحتاج سيرفرات إضافية",
                    alert_level=AlertLevel.WARNING,
                    servers_needed=check.extra_servers_needed,
                    server_type=server_type,
                    estimated_cost=check.extra_servers_needed * (
                        55 if server_type == ServerType.AX42 else 44
                    )
                )
                # تمرير معلومات النشر المعلّق مع الإشعار
                pending_deploy = {
                    "count": count,
                    "customer_id": customer_id,
                    "server_type": server_type,
                    "nifling_enabled": nifling_enabled,
                }
                await scaler._notify_and_wait(decision, pending_deploy)

                logger.info(
                    f"⏳ Deploy paused for {customer_id}: "
                    f"waiting for scale approval "
                    f"(+{check.extra_servers_needed} servers needed)\n"
                    f"   → approve the alert to continue deployment"
                )
                # لا نكمل النشر — ننتظر الموافقة
                # approve_alert سيُنشئ السيرفرات + يكمل النشر + يسجّل الزبون
                return

            elif scaler.config.mode == ScaleMode.AUTO:
                # ─── وضع AUTO: وسّع تلقائياً ثم أكمل ───
                logger.info(f"🤖 Auto-scaling before deploy...")
                if check.extra_servers_needed > 0:
                    from auto_provisioner import SERVER_CAPACITY
                    extra_farms = check.extra_servers_needed * SERVER_CAPACITY[server_type]
                    await provisioner.deploy_farms(
                        count=extra_farms,
                        server_type=server_type
                    )
                    config.max_concurrent_farms += check.extra_slots_needed
                    logger.info(
                        f"✅ Auto-scaled: +{check.extra_servers_needed} servers, "
                        f"slots now: {config.max_concurrent_farms}"
                    )
                    # إشعار بالنتيجة
                    from auto_scaler import ScaleDecision
                    await scaler._send_notification(
                        f"✅ تم التوسع تلقائياً قبل نشر {count} مزرعة لـ {customer_id}\n"
                        f"المُضاف: +{check.extra_servers_needed} سيرفر\n"
                        f"Slots: {config.max_concurrent_farms}",
                        ScaleDecision()
                    )

            else:
                # ─── وضع MANUAL: أوقف النشر وأخبر فقط ───
                logger.warning(
                    f"⛔ Deploy BLOCKED for {customer_id}: "
                    f"need +{check.extra_servers_needed} servers (manual mode)"
                )
                return

        # نشر البنية التحتية
        report = await provisioner.deploy_farms(
            count=count,
            server_type=server_type,
            customer_id=customer_id
        )

        # تسجيل الزبون في الجدول
        farm_ids = [a["farm_id"] for a in report["assignments"]]
        customer_scheduler.register_customer(
            customer_id=customer_id,
            farm_ids=farm_ids,
            nifling_enabled=nifling_enabled
        )

        logger.info(f"✅ Full deployment complete for {customer_id}: {count} farms")

    except Exception as e:
        logger.error(f"❌ Deployment failed for {customer_id}: {e}")


# ══════════════════════════════════════════
#  Nifling Endpoints
# ══════════════════════════════════════════

@app.post("/api/nifling/request")
async def request_nifling(req: NiflingRequest):
    """
    ⚔️ طلب Nifling — الزبون يطلب من Dashboard

    - يدخل طابور الأولوية
    - يُنفَّذ فوراً (3 slots محجوزة)
    - لا يؤثر على جدول الزراعة
    """
    request = nifling_handler.request_nifling(
        farm_id=req.farm_id,
        customer_id=req.customer_id
    )

    return {
        "request_id": request.request_id,
        "status": request.status,
        "position_in_queue": len(nifling_handler.queue),
        "estimated_wait_seconds": len(nifling_handler.queue) * 10,
    }


@app.get("/api/nifling/status")
async def nifling_status():
    """حالة طابور Nifling"""
    return nifling_handler.get_queue_status()


@app.get("/api/nifling/history/{customer_id}")
async def nifling_history(customer_id: str):
    """سجل طلبات Nifling للزبون"""
    return nifling_handler.get_customer_nifling_history(customer_id)


# ══════════════════════════════════════════
#  Schedule Endpoints
# ══════════════════════════════════════════

@app.get("/api/schedule/{customer_id}")
async def get_customer_schedule(customer_id: str):
    """
    📋 جدول الزبون — يُعرض في Dashboard

    يشمل:
    - عدد المزارع والـ slots المخصصة
    - جدول الزراعة (كل 5.5 ساعة)
    - جدول المهام اليومية (كل 24 ساعة)
    - حالة Nifling
    """
    schedule = customer_scheduler.get_customer_schedule(customer_id)
    if "error" in schedule:
        raise HTTPException(status_code=404, detail=schedule["error"])
    return schedule


@app.get("/api/schedule")
async def get_all_schedules():
    """ملخص جداول كل الزبائن"""
    return customer_scheduler.get_all_schedules_summary()


# ══════════════════════════════════════════
#  Batch Scheduler Status
# ══════════════════════════════════════════

@app.get("/api/batch/status")
async def batch_status():
    """
    📦 حالة الـ Batch Scheduler

    يشمل:
    - الدفعة الحالية (رقم + تقدم)
    - الطوابير الثلاثة (farming + daily + nifling)
    - المهام النشطة
    - نسبة الأخطاء + الأنماط المُتعلَّمة
    """
    return batch_scheduler.get_status()


@app.get("/api/batch/farms/{farm_id}")
async def farm_status(farm_id: str):
    """
    حالة مزرعة معينة

    يشمل: آخر farming, آخر daily, عدد الأخطاء المتتالية
    """
    farm = batch_scheduler.farms.get(farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    return {
        "farm_id": farm.id,
        "customer_id": farm.customer_id,
        "status": farm.status.value,
        "last_farming": farm.last_farming_at.isoformat() if farm.last_farming_at else None,
        "last_daily": farm.last_daily_at.isoformat() if farm.last_daily_at else None,
        "last_nifling": farm.last_nifling_at.isoformat() if farm.last_nifling_at else None,
        "needs_farming": farm.needs_farming(config),
        "needs_daily": farm.needs_daily(config),
        "consecutive_failures": farm.consecutive_failures,
        "total_runs": {
            "farming": farm.total_farming_runs,
            "daily": farm.total_daily_runs,
            "nifling": farm.total_nifling_runs,
        }
    }


# ══════════════════════════════════════════
#  System Status
# ══════════════════════════════════════════

@app.get("/api/status")
async def system_status():
    """
    📊 حالة النظام الكاملة

    يشمل:
    - البنية التحتية (سيرفرات + مزارع)
    - الجدولة (دفعات + طوابير)
    - التعلم الذاتي (أنماط + أخطاء)
    """
    return {
        "infrastructure": provisioner.get_infrastructure_status(),
        "scheduler": batch_scheduler.get_status(),
        "schedules": customer_scheduler.get_all_schedules_summary(),
        "nifling": nifling_handler.get_queue_status(),
    }


@app.get("/api/health")
async def health():
    """فحص سلامة النظام"""
    return {"status": "ok", "version": "1.0.0"}


# ══════════════════════════════════════════
#  Server Callbacks (من Cloud-Init)
# ══════════════════════════════════════════

@app.post("/api/servers/ready")
async def server_ready(req: ServerReadyRequest):
    """
    إبلاغ جاهزية سيرفر — يُستدعى من Cloud-Init

    بعد ما السيرفر يكمل تثبيت كل شيء،
    يرسل هذا الطلب للـ Orchestrator
    """
    server = provisioner.servers.get(req.server_id)

    if server:
        from auto_provisioner import ServerStatus
        server.status = ServerStatus.READY
        server.ip = req.ip
        from datetime import datetime
        server.ready_at = datetime.utcnow()

        logger.info(f"🖥️ Server {req.server_id} is READY at {req.ip}")

        return {"status": "registered", "server_id": req.server_id}
    else:
        raise HTTPException(status_code=404, detail="Server not found")


# ══════════════════════════════════════════
#  Auto-Scaler Endpoints
# ══════════════════════════════════════════

@app.get("/api/scaler/status")
async def scaler_status():
    """حالة Auto-Scaler"""
    return scaler.get_scaler_status()


class ScalerConfigUpdate(BaseModel):
    mode: Optional[str] = None              # auto / notify / manual
    max_monthly_budget: Optional[float] = None
    utilization_threshold: Optional[float] = None
    min_free_slots: Optional[int] = None

@app.put("/api/scaler/config")
async def update_scaler_config(req: ScalerConfigUpdate):
    """
    ⚙️ تحديث إعدادات Auto-Scaler من Dashboard

    مثال: تحويل من notify → auto
    """
    updates = {k: v for k, v in req.dict().items() if v is not None}
    return scaler.update_config(**updates)


class AlertAction(BaseModel):
    alert_id: str

@app.post("/api/scaler/alerts/approve")
async def approve_scale_alert(req: AlertAction):
    """
    ✅ الموافقة على طلب توسع

    يُستدعى من Dashboard عندما تضغط "موافق"
    """
    return await scaler.approve_alert(req.alert_id)


@app.post("/api/scaler/alerts/reject")
async def reject_scale_alert(req: AlertAction):
    """❌ رفض طلب التوسع"""
    return await scaler.reject_alert(req.alert_id)


# ══════════════════════════════════════════
#  Validation Endpoints
# ══════════════════════════════════════════

@app.get("/api/validate/capacity/{farm_count}")
async def validate_capacity(farm_count: int):
    """
    🔍 تحقق: هل النظام يتحمل هذا العدد من المزارع؟

    يُستدعى من Dashboard قبل ما الزبون يطلب مزارع

    مثال: GET /api/validate/capacity/100
    الجواب: ✅ يكفي / ❌ نحتاج سيرفر إضافي
    """
    existing = sum(
        c.farm_count for c in customer_scheduler.customers.values()
    )
    current_slots = config.max_concurrent_farms

    result = validator.validate_before_adding(existing, farm_count, current_slots)

    return {
        "can_add": result.valid,
        "existing_farms": existing,
        "after_adding": existing + farm_count,
        "current_slots": current_slots,
        "cycle_after": f"{result.cycle_duration_hours:.1f}h",
        "farming_interval": f"{result.farming_interval_hours}h",
        "margin": f"{result.farming_margin_hours:.1f}h",
        "fix_needed": result.fix_needed,
        "fix": result.fix_details if result.fix_needed else None,
        "extra_servers": result.extra_servers_needed if result.fix_needed else 0,
    }


@app.get("/api/validate/optimal/{farm_count}")
async def optimal_slots(farm_count: int):
    """
    📊 حساب العدد الأمثل للـ slots لتشغيل X مزرعة

    مثال: GET /api/validate/optimal/1000
    """
    return validator.find_optimal_slots(farm_count)


@app.get("/api/validate/current")
async def validate_current():
    """
    📊 تحقق الوضع الحالي — هل الجدول صحيح الآن؟

    يفحص:
    - هل دورة الـ farming تكفي ضمن 5.5 ساعة؟
    - هل المهام اليومية تكفي ضمن 24 ساعة؟
    - كم هامش الأمان المتبقي؟
    """
    total_farms = sum(
        c.farm_count for c in customer_scheduler.customers.values()
    )
    current_slots = config.max_concurrent_farms

    result = validator.validate(total_farms, current_slots)

    return {
        "valid": result.valid,
        "total_farms": total_farms,
        "concurrent_slots": current_slots,
        "farming": {
            "ok": result.farming_ok,
            "batches": result.batches_needed,
            "cycle_duration": f"{result.cycle_duration_hours:.1f}h",
            "interval": f"{result.farming_interval_hours}h",
            "margin": f"{result.farming_margin_hours:.1f}h",
        },
        "daily": {
            "ok": result.daily_ok,
            "cycle_duration": f"{result.daily_cycle_hours:.1f}h",
            "interval": f"{result.daily_interval_hours}h",
        },
        "fix_needed": result.fix_needed,
        "fix": result.fix_details if result.fix_needed else "All good ✅",
    }


# ══════════════════════════════════════════
#  Startup
# ══════════════════════════════════════════

@app.on_event("startup")
async def startup():
    """تشغيل المكونات عند بدء الـ API"""
    import asyncio

    logger.info("🚀 VRBOT Batch Scheduler API starting...")

    # تشغيل Batch Scheduler (3 طوابير: farming + daily + nifling loops)
    asyncio.create_task(batch_scheduler.start())

    # تشغيل Nifling handler (طابور منفصل للطلبات الفورية)
    asyncio.create_task(nifling_handler.start())

    # تشغيل Auto-Scaler (مراقبة الحمل + توسع تلقائي/إشعار)
    asyncio.create_task(scaler.start())

    logger.info("✅ All components started: BatchScheduler + NiflingHandler + AutoScaler")


@app.on_event("shutdown")
async def shutdown():
    """إيقاف المكونات"""
    await batch_scheduler.stop()
    await nifling_handler.stop()
    await scaler.stop()
    logger.info("🛑 Scheduler stopped")


# ══════════════════════════════════════════
#  Run
# ══════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8080)
