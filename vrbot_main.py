"""
VRBOT Main v5.0 — Enhanced Engine
===================================
Drop-in replacement with 4 built-in improvements:
  1. Anti-Ban scheduler  — random task order within priority groups
  2. Human behavior      — random delays 2-8s, pauses, session breaks
  3. Captcha detection   — AI Vision auto-pause + Discord/Telegram webhook
  4. Health monitor      — auto-restart on crash/freeze/ANR

Backward compatible:
  - Same TASK_MAP, same TASK_ORDER (kept for reference)
  - Same vrbot_core.Bot, same vrbot_config.TASKS_ENABLED
  - All 37 task files untouched
  - Existing vrbot_config.py untouched

Usage:
  python vrbot_main.py              # continuous mode (infinite cycles)
  python vrbot_main.py --once       # single pass then exit
  python vrbot_main.py gather       # run single task
  python vrbot_main.py --list       # show all tasks + priorities
  python vrbot_main.py --classic    # original sequential mode (no enhancements)
"""
import sys
import os
import time
import random
import hashlib
import logging
import subprocess
import threading
import traceback
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════
# Logging — auto-creates logs/ directory
# ═══════════════════════════════════════════════════════════════════

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"logs/vrbot_{time.strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("vrbot")

# ═══════════════════════════════════════════════════════════════════
# Core imports (unchanged)
# ═══════════════════════════════════════════════════════════════════

from vrbot_core import Bot
from vrbot_config import TASKS_ENABLED
from smart_retry import SmartRetry
from state_machine import BotState, TaskState

# ═══════════════════════════════════════════════════════════════════
# Task Registry — 37 tasks (unchanged from original)
# ═══════════════════════════════════════════════════════════════════

TASK_MAP = {
    # Quick Collections
    "daily_gifts":         ("tasks.task_daily_gifts",         "TaskDailyGifts"),
    "rewards":             ("tasks.task_rewards",             "TaskRewards"),
    "mail_rewards":        ("tasks.task_mail_rewards",        "TaskMailRewards"),
    "helps":               ("tasks.task_helps",               "TaskHelps"),
    "tribe_gifts":         ("tasks.task_tribe_gifts",         "TaskTribeGifts"),
    "prosperity":          ("tasks.task_prosperity",          "TaskProsperity"),

    # Buildings
    "construction":        ("tasks.task_construction",        "TaskConstruction"),
    "research":            ("tasks.task_research",            "TaskResearch"),
    "train_troops":        ("tasks.task_train_troops",        "TaskTrainTroops"),
    "hall_of_valor":       ("tasks.task_hall_of_valor",       "TaskHallOfValor"),
    "divination":          ("tasks.task_divination",          "TaskDivination"),
    "smithy":              ("tasks.task_smithy",              "TaskSmithy"),
    "upgrade_chief_hall":  ("tasks.task_upgrade_chief_hall",  "TaskUpgradeChiefHall"),
    "chief_hall":          ("tasks.task_chief_hall",          "TaskChiefHall"),
    "expansion":           ("tasks.task_expansion",           "TaskExpansion"),

    # Economy
    "errands":             ("tasks.task_errands",             "TaskErrands"),
    "commissions":         ("tasks.task_commissions",         "TaskCommissions"),
    "farmer_appointments": ("tasks.task_farmer_appointments", "TaskFarmerAppointments"),
    "recruit_farmers":     ("tasks.task_recruit_farmers",     "TaskRecruitFarmers"),
    "village_champions":   ("tasks.task_village_champions",   "TaskVillageChampions"),

    # Heroes
    "hero_xp":             ("tasks.task_hero_xp",             "TaskHeroXp"),
    "hero_training":       ("tasks.task_hero_training",       "TaskHeroTraining"),
    "account_items":       ("tasks.task_account_items",       "TaskAccountItems"),

    # World Map
    "gather":              ("tasks.task_gather",              "TaskGather"),
    "niflung":             ("tasks.task_niflung",             "TaskNiflung"),
    "kill_monster":        ("tasks.task_kill_monster",         "TaskKillMonster"),
    "rally_niflung":       ("tasks.task_rally_niflung",       "TaskRallyNiflung"),
    "clear_forest":        ("tasks.task_clear_forest",        "TaskClearForest"),
    "cinderbone":          ("tasks.task_cinderbone",          "TaskCinderbone"),
    "staging_post":        ("tasks.task_staging_post",        "TaskStagingPost"),
    "reclaim_midgard":     ("tasks.task_reclaim_midgard",     "TaskReclaimMidgard"),

    # Events
    "leidolf":             ("tasks.task_leidolf",             "TaskLeidolf"),
    "festival_flames":     ("tasks.task_festival_flames",     "TaskFestivalFlames"),
    "chapter":             ("tasks.task_chapter",             "TaskChapter"),
    "promo_codes":         ("tasks.task_promo_codes",         "TaskPromoCodes"),

    # Defense
    "shield":              ("tasks.task_shield",              "TaskShield"),

    # Alliance
    "tribe_tech":          ("tasks.task_tribe_tech",          "TaskTribeTech"),
    "tribe_gold_tile":     ("tasks.task_tribe_gold_tile",     "TaskTribeGoldTile"),

    # Economy (extra)
    "market_trade":        ("tasks.task_market_trade",        "TaskMarketTrade"),

    # Events (extra)
    "community_events":    ("tasks.task_community_events",    "TaskCommunityEvents"),
    "conquer_island":      ("tasks.task_conquer_island",      "TaskConquerIsland"),
    "gather_supplies":     ("tasks.task_gather_supplies",     "TaskGatherSupplies"),
    "rebate_pack":         ("tasks.task_rebate_pack",         "TaskRebatePack"),
    "surprise_gift":       ("tasks.task_surprise_gift",       "TaskSurpriseGift"),
    "toy_shop":            ("tasks.task_toy_shop",            "TaskToyShop"),

    # Resource Management
    "transfer_resources":  ("tasks.task_transfer_resources",  "TaskTransferResources"),

    # Meta
    "city_rush":           ("tasks.task_city_rush",           "TaskCityRush"),

    # v5.1 — Competitor-inspired tasks
    "wall_repair":         ("tasks.task_wall_repair",         "TaskWallRepair"),
    "heal_troops":         ("tasks.task_heal_troops",         "TaskHealTroops"),
    "troop_upgrade":       ("tasks.task_troop_upgrade",       "TaskTroopUpgrade"),
    "gather_boost":        ("tasks.task_gather_boost",        "TaskGatherBoost"),
    "map_explore":         ("tasks.task_map_explore",         "TaskMapExplore"),
    "intelligence_rewards":("tasks.task_intelligence_rewards","TaskIntelligenceRewards"),
}

# Original sequential order (kept for --classic mode)
TASK_ORDER = [
    # Phase 1: Quick Collections (low API cost)
    "daily_gifts", "rewards", "mail_rewards", "helps", "tribe_gifts",

    # Phase 2: Production (building tasks)
    "construction", "research", "train_troops", "prosperity",

    # Phase 3: Economy
    "errands", "commissions", "farmer_appointments", "recruit_farmers", "village_champions",

    # Phase 4: Heroes
    "hall_of_valor", "hero_xp", "hero_training", "account_items", "divination", "smithy",

    # Phase 5: World Map (combat)
    "gather", "niflung", "kill_monster", "staging_post",
    "clear_forest", "reclaim_midgard",

    # Phase 6: Events
    "leidolf", "festival_flames", "promo_codes", "chapter",
    "community_events", "conquer_island", "gather_supplies",
    "rebate_pack", "surprise_gift", "toy_shop", "cinderbone",

    # Phase 7: Strategy (upgrades)
    "chief_hall", "upgrade_chief_hall", "expansion", "tribe_tech",

    # Phase 8: Economy (extra)
    "market_trade", "tribe_gold_tile",

    # Phase 9: Rally (alliance)
    "rally_niflung",

    # Phase 10: Maintenance (v5.1)
    "wall_repair", "heal_troops", "troop_upgrade",
    "gather_boost", "map_explore", "intelligence_rewards",

    # Phase 11: Meta
    "city_rush",

    # Last: Defense
    "shield",
]

# ═══════════════════════════════════════════════════════════════════
# [NEW] Priority System — groups tasks by importance
# ═══════════════════════════════════════════════════════════════════

PRI_CRITICAL = 1   # always first (shield — keep alive)
PRI_HIGH     = 2   # income/combat (gather, niflung, kill)
PRI_NORMAL   = 3   # production & economy
PRI_LOW      = 4   # collections, events, heroes

TASK_PRIORITY = {
    # CRITICAL — survival
    "shield":              PRI_CRITICAL,

    # HIGH — main income/combat
    "gather":              PRI_HIGH,
    "niflung":             PRI_HIGH,
    "kill_monster":        PRI_HIGH,
    "rally_niflung":       PRI_HIGH,
    "tribe_gold_tile":     PRI_HIGH,

    # NORMAL — production & economy
    "construction":        PRI_NORMAL,
    "research":            PRI_NORMAL,
    "train_troops":        PRI_NORMAL,
    "helps":               PRI_NORMAL,
    "errands":             PRI_NORMAL,
    "commissions":         PRI_NORMAL,
    "farmer_appointments": PRI_NORMAL,
    "recruit_farmers":     PRI_NORMAL,
    "village_champions":   PRI_NORMAL,
    "hall_of_valor":       PRI_NORMAL,
    "staging_post":        PRI_NORMAL,
    "clear_forest":        PRI_NORMAL,
    "cinderbone":          PRI_NORMAL,
    "reclaim_midgard":     PRI_NORMAL,
    "chief_hall":          PRI_NORMAL,
    "upgrade_chief_hall":  PRI_NORMAL,
    "expansion":           PRI_NORMAL,
    "tribe_tech":          PRI_NORMAL,
    "prosperity":          PRI_NORMAL,
    "market_trade":        PRI_NORMAL,
    "city_rush":           PRI_NORMAL,

    # LOW — quick collections & events
    "daily_gifts":         PRI_LOW,
    "rewards":             PRI_LOW,
    "mail_rewards":        PRI_LOW,
    "tribe_gifts":         PRI_LOW,
    "hero_xp":             PRI_LOW,
    "hero_training":       PRI_LOW,
    "account_items":       PRI_LOW,
    "divination":          PRI_LOW,
    "smithy":              PRI_LOW,
    "leidolf":             PRI_LOW,
    "festival_flames":     PRI_LOW,
    "chapter":             PRI_LOW,
    "promo_codes":         PRI_LOW,
    "community_events":    PRI_LOW,
    "conquer_island":      PRI_LOW,
    "gather_supplies":     PRI_LOW,
    "rebate_pack":         PRI_LOW,
    "surprise_gift":       PRI_LOW,
    "toy_shop":            PRI_LOW,

    # v5.1 — Competitor-inspired tasks
    "wall_repair":         PRI_NORMAL,
    "heal_troops":         PRI_HIGH,
    "troop_upgrade":       PRI_NORMAL,
    "gather_boost":        PRI_NORMAL,
    "map_explore":         PRI_LOW,
    "intelligence_rewards":PRI_LOW,
}

PRI_NAMES = {1: "CRITICAL", 2: "HIGH", 3: "NORMAL", 4: "LOW"}


# ═══════════════════════════════════════════════════════════════════
# [ENHANCEMENT 1] Anti-Ban Scheduler
# ═══════════════════════════════════════════════════════════════════

class AntiBanScheduler:
    """Builds randomized task queue grouped by priority."""

    SWAP_CHANCE = 0.3   # 30% chance to swap adjacent same-priority tasks

    @staticmethod
    def build_queue(enabled_tasks):
        """Group by priority → shuffle within group → random swaps."""
        groups = {}
        for name in enabled_tasks:
            pri = TASK_PRIORITY.get(name, PRI_NORMAL)
            groups.setdefault(pri, []).append(name)

        queue = []
        for pri in sorted(groups.keys()):
            g = groups[pri][:]
            random.shuffle(g)
            queue.extend(g)

        # Adjacent swaps for extra naturalness
        for i in range(len(queue) - 1):
            if random.random() < AntiBanScheduler.SWAP_CHANCE:
                a = TASK_PRIORITY.get(queue[i], PRI_NORMAL)
                b = TASK_PRIORITY.get(queue[i + 1], PRI_NORMAL)
                if a == b:
                    queue[i], queue[i + 1] = queue[i + 1], queue[i]

        return queue


# ═══════════════════════════════════════════════════════════════════
# [ENHANCEMENT 2] Human Behavior Simulator
# ═══════════════════════════════════════════════════════════════════

class HumanBehavior:
    """Anti-ban: random delays, long pauses, session breaks, idle browsing."""

    DELAY_MIN        = 2.0    # sec between tasks
    DELAY_MAX        = 8.0
    LONG_PAUSE_PROB  = 0.05   # 5% chance per task
    LONG_PAUSE_MIN   = 15.0
    LONG_PAUSE_MAX   = 45.0
    BREAK_EVERY      = 8      # cycles between breaks
    BREAK_MIN        = 60.0   # 1 min
    BREAK_MAX        = 180.0  # 3 min
    IDLE_BROWSE_PROB = 0.08   # 8% chance to do idle browsing between tasks
    IDLE_BROWSE_MIN  = 5.0    # min idle browse duration
    IDLE_BROWSE_MAX  = 20.0   # max idle browse duration

    @staticmethod
    def task_delay():
        """Delay between tasks — occasionally pauses longer or does idle browsing."""
        if random.random() < HumanBehavior.LONG_PAUSE_PROB:
            d = random.uniform(HumanBehavior.LONG_PAUSE_MIN, HumanBehavior.LONG_PAUSE_MAX)
            print(f"  [anti-ban] Human pause: {d:.0f}s")
            time.sleep(d)
        else:
            time.sleep(random.uniform(HumanBehavior.DELAY_MIN, HumanBehavior.DELAY_MAX))

    @staticmethod
    def cycle_break():
        """Long break between cycles."""
        d = random.uniform(HumanBehavior.BREAK_MIN, HumanBehavior.BREAK_MAX)
        print(f"  [anti-ban] Cycle break: {d:.0f}s")
        time.sleep(d)

    @staticmethod
    def should_break(cycle_num):
        """Returns True if it's time for a break."""
        return (
            cycle_num > 1
            and HumanBehavior.BREAK_EVERY > 0
            and (cycle_num - 1) % HumanBehavior.BREAK_EVERY == 0
        )

    @staticmethod
    def maybe_idle_browse(bot):
        """Randomly browse screens to simulate human curiosity. ~8% chance."""
        if random.random() >= HumanBehavior.IDLE_BROWSE_PROB:
            return  # No idle browse this time

        duration = random.uniform(HumanBehavior.IDLE_BROWSE_MIN,
                                  HumanBehavior.IDLE_BROWSE_MAX)
        print(f"  [anti-ban] Idle browsing ({duration:.0f}s)...")
        log.debug(f"Idle browse: {duration:.0f}s")

        actions = [
            # Random swipes on city view (like looking around)
            lambda: bot.swipe(
                640 + random.randint(-200, 200), 360 + random.randint(-100, 100),
                640 + random.randint(-200, 200), 360 + random.randint(-100, 100),
                duration=random.randint(400, 900)),
            # Zoom gesture (pinch simulation via fast swipe)
            lambda: bot.swipe(640, 200, 640, 500, duration=random.randint(200, 500)),
            # Small idle tap near center (like absent-mindedly tapping)
            lambda: bot.tap(640 + random.randint(-50, 50),
                            360 + random.randint(-50, 50), jitter=True),
            # Just wait (staring at screen)
            lambda: time.sleep(random.uniform(2, 6)),
        ]

        end_time = time.time() + duration
        while time.time() < end_time:
            action = random.choice(actions)
            try:
                action()
            except Exception:
                pass
            time.sleep(random.uniform(1.5, 4.0))

        # Return to city in case we navigated somewhere
        try:
            bot.go_to_city(max_attempts=5)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# [ENHANCEMENT 3] Captcha Detection (AI Vision)
# ═══════════════════════════════════════════════════════════════════

class CaptchaGuard:
    """Detects captcha/verification popups using bot.ask_ai()."""

    PROMPT = (
        "Viking Rise screenshot (1280x720). "
        "Is there a CAPTCHA, verification popup, security check, "
        "slider puzzle, or 'prove you are human' dialog visible? "
        'Respond ONLY with JSON: {"captcha": true/false}'
    )
    CHECK_INTERVAL = 15  # seconds between AI checks
    WAIT_TIMEOUT   = 120 # max seconds to wait for manual resolution

    def __init__(self, bot, webhook_url=None):
        self.bot = bot
        self.smart_retry = SmartRetry(bot=self.bot)
        self.webhook_url = webhook_url  # Discord/Telegram webhook
        self.active = False
        self.total_detected = 0
        self._last_check = 0.0

    def check(self, task_name=""):
        """Check for captcha. Returns True if captcha is active."""
        now = time.time()
        if now - self._last_check < self.CHECK_INTERVAL:
            return self.active
        self._last_check = now
        try:
            img = self.bot.screenshot_b64()
            if not img:
                return False
            result = self.bot.ask_ai(self.PROMPT, img, max_tokens=80)
            if result and isinstance(result, dict) and result.get("captcha"):
                if not self.active:
                    self._on_detected(task_name)
                return True
            elif self.active:
                self.active = False
                print("  [captcha] Cleared!")
                log.info("Captcha cleared")
            return False
        except Exception as e:
            log.debug(f"Captcha check error: {e}")
            return self.active

    def wait_clear(self):
        """Pause execution until captcha is resolved or timeout."""
        print("  [captcha] Paused — waiting for resolution...")
        log.warning("Waiting for captcha resolution")
        start = time.time()
        while self.active and (time.time() - start) < self.WAIT_TIMEOUT:
            time.sleep(5)
            self._last_check = 0  # force re-check
            self.check()
        if self.active:
            print("  [captcha] Timeout — resuming")
            log.warning("Captcha wait timeout")
            self.active = False

    def _on_detected(self, task_name):
        """Called when captcha first detected."""
        self.active = True
        self.total_detected += 1
        msg = f"CAPTCHA detected during: {task_name}"
        print(f"\n  {'!'*50}")
        print(f"  {msg}")
        print(f"  {'!'*50}")
        log.critical(msg)
        # Save screenshot for debugging
        try:
            self.bot.screenshot("captcha_detected")
        except Exception:
            pass
        self._notify(task_name)

    def _notify(self, task_name):
        """Send webhook notification (Discord/Telegram)."""
        if not self.webhook_url:
            return
        try:
            import json as _json
            from urllib.request import Request, urlopen
            payload = _json.dumps({
                "content": (
                    f"🚨 **VRBOT CAPTCHA** | Task: {task_name} | "
                    f"Time: {datetime.now().strftime('%H:%M:%S')} | "
                    f"Total: #{self.total_detected}"
                )
            }).encode()
            req = Request(
                self.webhook_url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            threading.Thread(
                target=lambda: urlopen(req, timeout=10),
                daemon=True,
            ).start()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# [ENHANCEMENT 4] Health Monitor (auto-restart)
# ═══════════════════════════════════════════════════════════════════

class HealthGuard:
    """Monitors game process, detects crashes/freezes, auto-restarts."""

    GAME_PKG = "com.igg.android.vikingrise"
    GAME_ACT = GAME_PKG + "/com.igg.android.vikingrise.MainActivity"
    FREEZE_TIMEOUT = 45     # seconds with identical screenshot = frozen
    CHECK_INTERVAL = 15     # background check interval

    def __init__(self, bot):
        self.bot = bot
        self.smart_retry = SmartRetry(bot=self.bot)
        self.healthy = True
        self.total_restarts = 0
        self._last_hash = None
        self._same_since = time.time()
        self._running = False

        # Load ADB config
        try:
            from vrbot_config import ADB_EXE, ADB_DEVICE
            self._exe = ADB_EXE
            self._dev = ADB_DEVICE
        except Exception:
            self._exe = "adb"
            self._dev = "emulator-5554"

    def _adb(self, *args, timeout=12):
        """Execute ADB command and return stdout."""
        try:
            r = subprocess.run(
                [self._exe, "-s", self._dev] + list(args),
                capture_output=True, text=True, timeout=timeout,
            )
            return r.stdout
        except Exception:
            return ""

    def check(self):
        """Returns True if game is healthy."""
        try:
            # 1. ADB alive?
            if "ok" not in self._adb("shell", "echo", "ok"):
                self.healthy = False
                log.warning("ADB disconnected")
                return False

            # 2. Game process alive?
            pid = self._adb("shell", "pidof", self.GAME_PKG).strip()
            if not pid:
                self.healthy = False
                log.warning("Game process not found (crashed)")
                return False

            # 3. Freeze detection via screenshot hash
            try:
                raw = subprocess.run(
                    [self._exe, "-s", self._dev, "shell", "screencap", "-p"],
                    capture_output=True, timeout=10,
                ).stdout
                h = hashlib.md5(raw[:5000]).hexdigest() if raw else ""
                if h and h == self._last_hash:
                    elapsed = time.time() - self._same_since
                    if elapsed > self.FREEZE_TIMEOUT:
                        self.healthy = False
                        log.warning(f"Game frozen ({elapsed:.0f}s same screen)")
                        return False
                else:
                    self._last_hash = h
                    self._same_since = time.time()
            except Exception:
                pass  # freeze check is optional

            self.healthy = True
            return True

        except Exception as e:
            log.debug(f"Health check error: {e}")
            return True  # don't restart on check errors

    def recover(self):
        """Graduated recovery: back → force-stop → restart."""
        # Step 1: Try pressing back
        print("  [health] Trying back button...")
        self._adb("shell", "input", "keyevent", "4")
        time.sleep(3)
        if self.check():
            print("  [health] Recovered via back button")
            return True

        # Step 2: Force-stop and restart
        self.total_restarts += 1
        print(f"  [health] Restarting game (#{self.total_restarts})...")
        log.warning(f"Game restart #{self.total_restarts}")

        self._adb("shell", "am", "force-stop", self.GAME_PKG)
        time.sleep(5)
        self._adb("shell", "am", "start", "-n", self.GAME_ACT)
        time.sleep(40)  # game loading time

        # Reset freeze detection
        self._last_hash = None
        self._same_since = time.time()

        if self.check():
            print("  [health] Game restarted successfully")
            log.info("Game restarted OK")
            try:
                self.bot.go_to_city()
            except Exception:
                pass
            return True

        print("  [health] Restart FAILED")
        log.error("Game restart failed")
        return False

    def start_background(self):
        """Start background health monitoring thread."""
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True, name="health-monitor")
        t.start()
        log.info("Health monitor started")

    def stop_background(self):
        """Stop background monitoring."""
        self._running = False

    def _loop(self):
        while self._running:
            try:
                if not self.check():
                    self.recover()
            except Exception:
                pass
            time.sleep(self.CHECK_INTERVAL)


# ═══════════════════════════════════════════════════════════════════
# Task Loader (unchanged logic)
# ═══════════════════════════════════════════════════════════════════

def load_task_class(task_name):
    """Lazy-load a task class by name."""
    if task_name not in TASK_MAP:
        return None
    module_name, class_name = TASK_MAP[task_name]
    try:
        mod = __import__(module_name, fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception as e:
        log.error(f"Could not load {task_name}: {e}")
        return None


def run_task(bot, task_name, captcha=None, smart_retry=None):
    """Run a single task with Smart Retry + full error recovery on failure."""
    cls = load_task_class(task_name)
    if cls is None:
        return None

    # Pre-task captcha check
    if captcha and captcha.check(task_name):
        captcha.wait_clear()

    log.info(f"Running: {cls.name}")

    t0 = time.time()
    crash_error = None
    try:
        task = cls(bot)
        success = task.run()
    except Exception as e:
        log.error(f"{task_name} crashed: {e}")
        traceback.print_exc()
        success = False
        crash_error = str(e)

    # ── Smart Retry on failure ──
    if not success and smart_retry:
        log.warning(f"[{task_name}] failed — SmartRetry attempting recovery...")
        success = smart_retry.handle(task_name, bot)
        if success:
            log.info(f"[{task_name}] SmartRetry recovered!")
        else:
            log.error(f"[{task_name}] SmartRetry also failed.")

    # ── Final failure: ERROR_STATE recovery ──
    if not success:
        _handle_final_failure(bot, task_name, crash_error)

    duration = time.time() - t0
    status = "OK" if success else "FAIL"
    log.info(f"Result: {task_name} = {status} ({duration:.1f}s)")

    # Post-task captcha check
    if captcha and captcha.check(task_name):
        captcha.wait_clear()

    return success


def _handle_final_failure(bot, task_name, error_msg=None):
    """Handle complete task failure after SmartRetry exhausted.

    Steps:
      1. Set BotState to ERROR_RECOVERY
      2. Try closing popups / pressing back
      3. Attempt go_to_city() recovery
      4. Send alert to Hub WebSocket (if connected)
      5. Update state manager with error details
    """
    global _bot_state

    prev_state = _bot_state.state
    _bot_state.set_state(BotState.ERROR_RECOVERY, f"{task_name} final failure")
    _bot_state.last_error = f"{task_name}: {error_msg}" if error_msg else f"{task_name} failed"

    log.warning(f"[{task_name}] Final failure — entering ERROR_RECOVERY")

    # Step 1: Try closing any stacked popups via YOLO/Template
    for attempt in range(3):
        closed = bot.close_popup()
        if not closed:
            break
        time.sleep(1)

    # Step 2: Press back a few times
    for _ in range(2):
        bot.adb_back()
        time.sleep(1.5)

    # Step 3: Try to get back to city
    recovered = False
    try:
        recovered = bot.go_to_city(max_attempts=8)
    except Exception as e:
        log.error(f"[{task_name}] Recovery go_to_city failed: {e}")

    if recovered:
        log.info(f"[{task_name}] Recovered to city after final failure")
    else:
        log.error(f"[{task_name}] Could NOT recover to city — bot may be stuck")
        _bot_state.consecutive_failures += 1

    # Step 4: Notify via Hub WebSocket (if listener is connected)
    _bot_state._notify("alert", {
        "type": "task_final_failure",
        "task": task_name,
        "error": error_msg or "unknown",
        "recovered": recovered,
    })

    # Step 5: Restore previous state or set FATAL_ERROR if too many consecutive failures
    if recovered:
        _bot_state.consecutive_failures = 0
        _bot_state.set_state(prev_state if prev_state != BotState.ERROR_RECOVERY
                             else BotState.RUNNING, "recovered from error")
    else:
        if _bot_state.consecutive_failures >= 3:
            _bot_state.set_state(BotState.FATAL_ERROR, f"3+ consecutive failures: {task_name}")
            log.critical(f"FATAL_ERROR: {_bot_state.consecutive_failures} consecutive failures")
        else:
            _bot_state.set_state(BotState.ERROR_RECOVERY, "stuck after failure")


# ═══════════════════════════════════════════════════════════════════
# Classic Mode (original behavior, no enhancements)
# ═══════════════════════════════════════════════════════════════════

def main_classic():
    """Original sequential mode — no enhancements."""
    bot = Bot()
    print("=" * 60)
    print(f"  VRBOT — Classic Mode ({sum(1 for v in TASKS_ENABLED.values() if v)} tasks)")
    print("=" * 60)
    bot.go_to_city()
    bot.wait(2)

    results = {}
    for task_name in TASK_ORDER:
        if not TASKS_ENABLED.get(task_name, False):
            continue
        if task_name not in TASK_MAP:
            continue
        bot.go_to_city()
        bot.wait(1)
        success = run_task(bot, task_name)
        results[task_name] = success
        bot.task_delay()

    print("\n" + "=" * 60)
    print("  VRBOT — Session Complete")
    print("=" * 60)
    ok = fail = 0
    for t, s in results.items():
        icon = "OK" if s else "FAIL"
        ok += 1 if s else 0
        fail += 0 if s else 1
        print(f"    {t:25s} [{icon}]")
    print(f"\n  Total: {ok} OK / {fail} FAIL / {len(TASK_ORDER) - len(results)} skipped")
    print("=" * 60)
    bot.print_stats()


# ═══════════════════════════════════════════════════════════════════
# [NEW] Bot State Manager — integrates state_machine.py
# ═══════════════════════════════════════════════════════════════════

class BotStateManager:
    """Top-level bot state tracker. Reports status for Socket.IO/UI."""

    def __init__(self):
        self.state = BotState.STOPPED
        self.current_task: str = ""
        self.task_state: str = ""
        self.cycle: int = 0
        self.total_ok: int = 0
        self.total_fail: int = 0
        self.total_skip: int = 0
        self.start_time: float = 0
        self.last_error: str = ""
        self.game_restarts: int = 0
        self.captchas_detected: int = 0
        self.consecutive_failures: int = 0
        self._listeners = []

    def set_state(self, new_state: BotState, reason: str = ""):
        old = self.state
        self.state = new_state
        if old != new_state:
            log.info(f"BotState: {old.name} → {new_state.name}" +
                     (f" ({reason})" if reason else ""))
            self._notify("state_change", self.get_status())

    def set_task(self, task_name: str, task_state: str = "running"):
        self.current_task = task_name
        self.task_state = task_state
        self._notify("task_update", {
            "task": task_name, "task_state": task_state
        })

    def on_task_result(self, task_name: str, success: bool, duration: float):
        if success:
            self.total_ok += 1
            self.consecutive_failures = 0
        else:
            self.total_fail += 1
        self._notify("task_result", {
            "task": task_name, "success": success, "duration": round(duration, 1)
        })

    def get_status(self) -> dict:
        uptime = time.time() - self.start_time if self.start_time else 0
        return {
            "state": self.state.name,
            "current_task": self.current_task,
            "task_state": self.task_state,
            "cycle": self.cycle,
            "total_ok": self.total_ok,
            "total_fail": self.total_fail,
            "total_skip": self.total_skip,
            "uptime_seconds": round(uptime),
            "game_restarts": self.game_restarts,
            "captchas_detected": self.captchas_detected,
            "last_error": self.last_error,
        }

    def add_listener(self, callback):
        """Register event listener (for Socket.IO integration)."""
        self._listeners.append(callback)

    def _notify(self, event: str, data: dict):
        for cb in self._listeners:
            try:
                cb(event, data)
            except Exception:
                pass


# Global bot state — accessible from Socket.IO client
_bot_state = BotStateManager()

def get_bot_state() -> BotStateManager:
    """Get the global bot state manager."""
    return _bot_state


# ═══════════════════════════════════════════════════════════════════
# Enhanced Mode (default)
# ═══════════════════════════════════════════════════════════════════

def main_enhanced(once=False, single_task=None):
    """Enhanced mode with all 5 improvements (+ Smart Retry + State Machine + Vision GSM)."""
    global _bot_state
    bot = Bot()
    captcha = CaptchaGuard(bot)
    health = HealthGuard(bot)
    retry = SmartRetry(bot=bot)

    # ── Game State Machine (vision-based) ──
    gsm = None
    try:
        from game_state import GameStateMachine, GameScreen
        gsm = GameStateMachine(bot)
        log.info("GameStateMachine initialized — vision-based state tracking enabled")
    except Exception as e:
        log.debug(f"GameStateMachine not available: {e}")

    _bot_state.start_time = time.time()
    _bot_state.set_state(BotState.STARTING, "initializing")

    # ── WebSocket Hub (connects to ws.vrbot.me relay) ──
    hub_client = None
    try:
        from hub_client import integrate_hub
        hub_client = integrate_hub(_bot_state)
        if hub_client:
            log.info("Hub WebSocket connected — dashboard can monitor live")
    except Exception as e:
        log.debug(f"Hub WebSocket not available: {e}")

    # ── Single task ──
    if single_task:
        bot.go_to_city()
        _bot_state.set_state(BotState.RUNNING, f"single task: {single_task}")
        _bot_state.set_task(single_task)
        run_task(bot, single_task, captcha, smart_retry=retry)
        _bot_state.set_state(BotState.STOPPED, "single task done")
        bot.print_stats()
        return

    # ── Full run ──
    enabled = [t for t in TASK_MAP if TASKS_ENABLED.get(t, False)]
    if not enabled:
        print("  No tasks enabled in vrbot_config.py!")
        _bot_state.set_state(BotState.STOPPED, "no tasks enabled")
        return

    print("\n" + "=" * 60)
    print(f"  VRBOT v5.0 — Enhanced Engine + State Machine")
    print(f"  {len(enabled)} tasks enabled | {'single pass' if once else 'continuous'}")
    print(f"  [1] Anti-Ban Scheduler   [2] Human Behavior")
    print(f"  [3] Captcha Detection    [4] Health Monitor")
    print(f"  [5] State Machine        [6] Smart Retry")
    print("=" * 60)

    health.start_background()
    bot.go_to_city()
    bot.wait(2)
    _bot_state.set_state(BotState.RUNNING, "main loop started")

    try:
        while True:
            _bot_state.cycle += 1

            # Break between cycles
            if HumanBehavior.should_break(_bot_state.cycle):
                _bot_state.set_state(BotState.PAUSED, "cycle break")
                HumanBehavior.cycle_break()
                _bot_state.set_state(BotState.RUNNING, "resumed after break")

            # Build RANDOMIZED queue
            queue = AntiBanScheduler.build_queue(enabled)

            print(f"\n{'=' * 60}")
            print(f"  Cycle {_bot_state.cycle} — {len(queue)} tasks")
            print(f"  Order: {', '.join(queue)}")
            print(f"{'=' * 60}")

            cycle_ok = cycle_fail = 0

            for task_name in queue:
                # Fatal error check — attempt full recovery
                if _bot_state.state == BotState.FATAL_ERROR:
                    log.critical("Bot in FATAL_ERROR — attempting emulator restart...")
                    _bot_state._notify("alert", {
                        "type": "fatal_error",
                        "message": f"Bot stuck in FATAL_ERROR after {_bot_state.consecutive_failures} failures",
                    })
                    try:
                        health.recover()  # This can restart emulator
                        _bot_state.consecutive_failures = 0
                        _bot_state.set_state(BotState.RUNNING, "recovered from FATAL_ERROR")
                    except Exception as e:
                        log.critical(f"Recovery from FATAL_ERROR failed: {e}")
                        time.sleep(60)  # Wait before retrying
                        continue

                # Health check
                if not health.healthy:
                    _bot_state.set_state(BotState.ERROR_RECOVERY, "game unhealthy")
                    _bot_state.game_restarts = health.total_restarts
                    print("  [health] Game unhealthy — recovering...")
                    health.recover()
                    _bot_state.game_restarts = health.total_restarts
                    _bot_state.set_state(BotState.RUNNING, "recovered")

                # Captcha check
                if captcha.check(task_name):
                    _bot_state.set_state(BotState.CAPTCHA_WAIT, task_name)
                    _bot_state.captchas_detected = captcha.total_detected
                    captcha.wait_clear()
                    _bot_state.set_state(BotState.RUNNING, "captcha cleared")

                # Navigate home (vision-aware if GSM available)
                if gsm:
                    if not gsm.ensure_ready_for_task(task_name):
                        log.warning(f"[{task_name}] GSM recovery failed, trying go_to_city()")
                        bot.go_to_city()
                        # Double-check with GSM — if still not ready, skip this task
                        if not gsm.verify_state(GameScreen.CITY):
                            log.error(f"[{task_name}] Still not in CITY after recovery — skipping")
                            _bot_state.total_skip += 1
                            _bot_state.set_task(task_name, "skipped")
                            continue
                else:
                    bot.go_to_city()
                bot.wait(1)

                _bot_state.set_task(task_name, "running")
                t0 = time.time()
                result = run_task(bot, task_name, captcha, smart_retry=retry)
                duration = time.time() - t0

                # Post-task state check
                if gsm:
                    post_state = gsm.post_task_check(task_name)
                    log.debug(f"[{task_name}] Post-task state: {post_state.value}")

                if result is None:
                    _bot_state.total_skip += 1
                    _bot_state.set_task(task_name, "skipped")
                elif result:
                    _bot_state.on_task_result(task_name, True, duration)
                    cycle_ok += 1
                else:
                    _bot_state.on_task_result(task_name, False, duration)
                    _bot_state.last_error = f"{task_name} failed"
                    cycle_fail += 1
                    if gsm:
                        gsm.recover_to_city(max_attempts=8)
                    else:
                        bot.go_to_city()  # recover position on fail

                # Human delay + occasional idle browsing
                HumanBehavior.task_delay()
                HumanBehavior.maybe_idle_browse(bot)

            print(f"\n  Cycle {_bot_state.cycle}: {cycle_ok} OK / {cycle_fail} FAIL")

            if once:
                break

            # Inter-cycle pause
            pause = random.uniform(10, 25)
            print(f"  Next cycle in {pause:.0f}s...")
            time.sleep(pause)

    except KeyboardInterrupt:
        print("\n\n  Stopped by user (Ctrl+C)")

    # ── Session Summary ──
    _bot_state.set_state(BotState.SHUTTING_DOWN, "session ending")
    health.stop_background()

    s = _bot_state
    print(f"\n{'=' * 60}")
    print(f"  SESSION COMPLETE")
    print(f"  Cycles: {s.cycle}  |  OK: {s.total_ok}  |  FAIL: {s.total_fail}  |  Skip: {s.total_skip}")
    print(f"  Game Restarts: {health.total_restarts}  |  Captchas: {captcha.total_detected}")
    if gsm:
        gs = gsm.get_stats()
        print(f"  Vision Detections: {gs['detections']}  |  Recoveries: {gs['recovery_attempts']}")
    print(f"{'=' * 60}")
    bot.print_stats()
    _bot_state.set_state(BotState.STOPPED, "session complete")

    # Disconnect Hub WebSocket
    if hub_client:
        hub_client.disconnect()


# ═══════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    # --list: show all tasks
    if "--list" in args:
        print(f"\n  {'Task':<25} {'ON':<6} {'Priority'}")
        print(f"  {'─'*25} {'─'*6} {'─'*10}")
        for name in sorted(TASK_MAP.keys()):
            on = TASKS_ENABLED.get(name, False)
            pri = TASK_PRIORITY.get(name, PRI_NORMAL)
            print(f"  {name:<25} {'✓' if on else ' ':<6} {PRI_NAMES.get(pri, '?')}")
        return

    # --classic: original mode
    if "--classic" in args:
        main_classic()
        return

    # --adb-serial: override ADB device serial (used by orchestrator)
    adb_serial = None
    for i, a in enumerate(args):
        if a == "--adb-serial" and i + 1 < len(args):
            adb_serial = args[i + 1]
            os.environ["ADB_SERIAL"] = adb_serial
            log.info(f"ADB serial override: {adb_serial}")

    # Parse flags
    once = "--once" in args or "--single-run" in args
    single_task = None

    # --task <name>: single task mode (from orchestrator)
    for i, a in enumerate(args):
        if a == "--task" and i + 1 < len(args):
            single_task = args[i + 1]

    # --tasks <name1,name2,...>: multi-task mode (from orchestrator daily)
    task_list = None
    for i, a in enumerate(args):
        if a == "--tasks" and i + 1 < len(args):
            task_list = [t.strip() for t in args[i + 1].split(",") if t.strip()]

    # Legacy: positional task name
    if not single_task and not task_list:
        for a in args:
            if not a.startswith("--") and a in TASK_MAP:
                single_task = a

    # Multi-task mode: run each task once then exit
    if task_list:
        log.info(f"Multi-task mode: {len(task_list)} tasks")
        for task_name in task_list:
            if task_name in TASK_MAP:
                main_enhanced(once=True, single_task=task_name)
            else:
                log.warning(f"Unknown task: {task_name}")
        return

    main_enhanced(once=once, single_task=single_task)


if __name__ == "__main__":
    main()

