# VRBOT Enhanced Modules v1.0.0

## 4 تحسينات متكاملة لمحرك VRBOT

### ✅ 1. State Machine (`state_machine.py`)
نظام حالات متقدم لتنفيذ المهام بشكل أذكى:
- كل مهمة تمر بحالات: `INITIALIZING → NAVIGATING → DETECTING → EXECUTING → VERIFYING → COMPLETED`
- إدارة تلقائية للأخطاء مع timeout و retry
- Recovery تلقائي عند حدوث مشاكل
- سهل التوسع: فقط أضف states و transitions جديدة

### ✅ 2. Captcha Detection (`captcha_detector.py`)  
كشف وإدارة الـ captcha/verification:
- Template matching لأنواع الـ captcha المعروفة
- YOLO detection كبديل للأنواع الجديدة
- Heuristic detection (كشف ذكي للـ popups الغريبة)
- إشعارات عبر Discord/Telegram webhook
- حفظ screenshots عند كشف captcha
- إحصائيات لتحسين الـ anti-ban

### ✅ 3. Auto-Restart (`health_monitor.py`)
مراقبة صحة اللعبة وإعادة تشغيل تلقائي:
- كشف: crash, freeze, ANR, فقدان اتصال ADB
- Recovery متدرج: `tap → back → force_stop → restart → clear_cache → restart_emulator`
- دعم LDPlayer (local) و Redroid/Docker (cloud)
- مراقبة في الخلفية كـ thread مستقل
- إحصائيات uptime

### ✅ 4. Random Task Scheduler (`task_scheduler.py`)
جدولة ذكية مع سلوك بشري لـ anti-ban:
- ترتيب عشوائي للمهام ضمن نفس الأولوية
- تأخيرات عشوائية بين المهام (2-8 ثانية)
- فترات راحة تلقائية (كل 8 دورات)
- نسبة 5% فترات توقف طويلة (15-45 ثانية)
- إزاحة عشوائية للنقرات (±5 pixels)
- أولويات: CRITICAL > HIGH > NORMAL > LOW
- جدولة: EVERY_CYCLE, PERIODIC, DAILY, ON_DEMAND

---

## 🔧 التركيب

```bash
# انسخ الملفات إلى مجلد vrbot-agent/
cp state_machine.py captcha_detector.py health_monitor.py task_scheduler.py vrbot_enhanced.py /path/to/vrbot-agent/
```

## 🚀 الاستخدام

```python
from vrbot_enhanced import VRBotEnhanced

bot = VRBotEnhanced(
    adb_controller=adb,
    device_serial="emulator-5554",
    farm_id="farm_001",
    config={
        'captcha': {'captcha_webhook_url': 'https://discord.webhook/...'},
        'health': {'freeze_threshold': 30},
    }
)

bot.register_tasks({
    'GatherResource': gather_task.run,
    'HuntMonster': hunt_task.run,
    'TrainTroops': train_task.run,
    # ... باقي المهام
})

bot.start()  # يبدأ التشغيل مع كل التحسينات!
```

## 📊 المعمارية

```
VRBotEnhanced
├── TaskScheduler (ترتيب عشوائي، anti-ban)
│   └── VRBotTask → StateMachine (states → transitions)
├── CaptchaDetector (مسح الشاشة للتحقق)
│   └── ScreenGuard (حماية متكاملة)
└── GameHealthMonitor (إعادة تشغيل تلقائي)
    └── Recovery (tap → back → restart → emulator)
```

## 📦 المصادر المُلهمة
- [Dylan-Zheng/Rise-of-Kingdoms-Bot](https://github.com/Dylan-Zheng/Rise-of-Kingdoms-Bot) - Pass verification, random tasks
- [GabrielAgrela/OSROKBOT](https://github.com/GabrielAgrela/OSROKBOT) - State machine, captcha detection
- [mibho/autoclient](https://github.com/mibho/autoclient) - Multi-instance management, auto-restart
