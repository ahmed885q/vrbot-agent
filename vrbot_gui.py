"""
VRBOT Desktop Client GUI v5.0 — Enhanced Edition
==================================================
Same license system + dark theme + 16 tasks.
New: Stats tab, continuous/single mode, 4 enhancements.

Run: python vrbot_gui.py
"""
import sys
import os
import json
import time
import hashlib
import uuid
import random
import threading
import subprocess
import traceback
from datetime import datetime

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt5.QtGui import QFont, QColor, QPalette
except ImportError:
    print("Run: pip install PyQt5")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

SERVER_URL = "https://vrbot.me"
CONFIG_FILE = "vrbot_license.json"
VERSION = "5.0.0"

# ═══════════════════════════════════════════════════════════════════
# Helpers (unchanged)
# ═══════════════════════════════════════════════════════════════════

def get_hw_id():
    info = f"{uuid.getnode()}-{os.environ.get('COMPUTERNAME', 'unknown')}"
    return hashlib.md5(info.encode()).hexdigest()[:16]

def load_cfg():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_cfg(d):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(d, f, indent=2)

# ═══════════════════════════════════════════════════════════════════
# Task Definitions (unchanged)
# ═══════════════════════════════════════════════════════════════════

ALL_TASKS = {
    "Quick Collections": [
        ("daily_gifts",          "Daily Gifts"),
        ("rewards",              "Quest Rewards"),
        ("mail_rewards",         "Mail Rewards"),
        ("helps",                "Alliance Helps"),
        ("tribe_gifts",          "Tribe Gifts"),
        ("prosperity",           "Prosperity"),
        ("promo_codes",          "Promo Codes"),
        ("surprise_gift",        "Surprise Gift"),
        ("account_items",        "Account Items"),
        ("intelligence_rewards", "Intelligence Rewards"),
        ("rebate_pack",          "Rebate Pack"),
    ],
    "Buildings": [
        ("construction",         "Upgrade Building"),
        ("upgrade_chief_hall",   "Upgrade Chief Hall"),
        ("research",             "Research"),
        ("hall_of_valor",        "Hall of Valor"),
        ("clear_forest",         "Clear Forest"),
        ("train_troops",         "Train Troops"),
        ("heal_troops",          "Heal Troops"),
        ("troop_upgrade",        "Troop Upgrade"),
        ("wall_repair",          "Wall Repair"),
        ("smithy",               "Smithy"),
        ("chief_hall",           "Chief Hall"),
    ],
    "World Map": [
        ("gather",               "Gather Resources"),
        ("niflung",              "Kill Niflung"),
        ("kill_monster",         "Kill Monster"),
        ("rally_niflung",        "Rally Niflung Leader"),
        ("gather_boost",         "Gather Boost"),
        ("gather_supplies",      "Gather Supplies"),
        ("map_explore",          "Map Explore"),
        ("conquer_island",       "Conquer Island"),
        ("reclaim_midgard",      "Reclaim Midgard"),
        ("expansion",            "Expansion"),
    ],
    "Alliance": [
        ("tribe_tech",           "Tribe Technology"),
        ("tribe_gold_tile",      "Tribe Gold Tile"),
        ("staging_post",         "Staging Post"),
    ],
    "Heroes & Events": [
        ("hero_training",        "Hero Training"),
        ("hero_xp",              "Hero XP"),
        ("leidolf",              "Leidolf"),
        ("divination",           "Divination"),
        ("village_champions",    "Village Champions"),
        ("farmer_appointments",  "Farmer Appointments"),
        ("recruit_farmers",      "Recruit Farmers"),
    ],
    "Events & Activities": [
        ("cinderbone",           "Cinderbone"),
        ("festival_flames",      "Festival Flames"),
        ("city_rush",            "City Rush"),
        ("community_events",     "Community Events"),
        ("chapter",              "Chapter"),
        ("commissions",          "Commissions"),
        ("errands",              "Errands"),
        ("market_trade",         "Market Trade"),
        ("toy_shop",             "Toy Shop"),
        ("shield",               "Shield"),
    ],
}

TASK_MAP = {
    "daily_gifts":          ("tasks.task_daily_gifts",          "TaskDailyGifts"),
    "rewards":              ("tasks.task_rewards",              "TaskRewards"),
    "mail_rewards":         ("tasks.task_mail_rewards",         "TaskMailRewards"),
    "helps":                ("tasks.task_helps",                "TaskHelps"),
    "tribe_gifts":          ("tasks.task_tribe_gifts",          "TaskTribeGifts"),
    "prosperity":           ("tasks.task_prosperity",           "TaskProsperity"),
    "promo_codes":          ("tasks.task_promo_codes",          "TaskPromoCodes"),
    "surprise_gift":        ("tasks.task_surprise_gift",        "TaskSurpriseGift"),
    "account_items":        ("tasks.task_account_items",        "TaskAccountItems"),
    "intelligence_rewards": ("tasks.task_intelligence_rewards", "TaskIntelligenceRewards"),
    "rebate_pack":          ("tasks.task_rebate_pack",          "TaskRebatePack"),
    "construction":         ("tasks.task_construction",         "TaskConstruction"),
    "upgrade_chief_hall":   ("tasks.task_upgrade_chief_hall",   "TaskUpgradeChiefHall"),
    "research":             ("tasks.task_research",             "TaskResearch"),
    "hall_of_valor":        ("tasks.task_hall_of_valor",        "TaskHallOfValor"),
    "clear_forest":         ("tasks.task_clear_forest",         "TaskClearForest"),
    "train_troops":         ("tasks.task_train_troops",         "TaskTrainTroops"),
    "heal_troops":          ("tasks.task_heal_troops",          "TaskHealTroops"),
    "troop_upgrade":        ("tasks.task_troop_upgrade",        "TaskTroopUpgrade"),
    "wall_repair":          ("tasks.task_wall_repair",          "TaskWallRepair"),
    "smithy":               ("tasks.task_smithy",               "TaskSmithy"),
    "chief_hall":           ("tasks.task_chief_hall",           "TaskChiefHall"),
    "gather":               ("tasks.task_gather",               "TaskGather"),
    "niflung":              ("tasks.task_niflung",              "TaskNiflung"),
    "kill_monster":         ("tasks.task_kill_monster",         "TaskKillMonster"),
    "rally_niflung":        ("tasks.task_rally_niflung",        "TaskRallyNiflung"),
    "gather_boost":         ("tasks.task_gather_boost",         "TaskGatherBoost"),
    "gather_supplies":      ("tasks.task_gather_supplies",      "TaskGatherSupplies"),
    "map_explore":          ("tasks.task_map_explore",          "TaskMapExplore"),
    "conquer_island":       ("tasks.task_conquer_island",       "TaskConquerIsland"),
    "reclaim_midgard":      ("tasks.task_reclaim_midgard",      "TaskReclaimMidgard"),
    "expansion":            ("tasks.task_expansion",            "TaskExpansion"),
    "tribe_tech":           ("tasks.task_tribe_tech",           "TaskTribeTech"),
    "tribe_gold_tile":      ("tasks.task_tribe_gold_tile",      "TaskTribeGoldTile"),
    "staging_post":         ("tasks.task_staging_post",         "TaskStagingPost"),
    "hero_training":        ("tasks.task_hero_training",        "TaskHeroTraining"),
    "hero_xp":              ("tasks.task_hero_xp",              "TaskHeroXp"),
    "leidolf":              ("tasks.task_leidolf",              "TaskLeidolf"),
    "divination":           ("tasks.task_divination",           "TaskDivination"),
    "village_champions":    ("tasks.task_village_champions",    "TaskVillageChampions"),
    "farmer_appointments":  ("tasks.task_farmer_appointments",  "TaskFarmerAppointments"),
    "recruit_farmers":      ("tasks.task_recruit_farmers",      "TaskRecruitFarmers"),
    "cinderbone":           ("tasks.task_cinderbone",           "TaskCinderbone"),
    "festival_flames":      ("tasks.task_festival_flames",      "TaskFestivalFlames"),
    "city_rush":            ("tasks.task_city_rush",            "TaskCityRush"),
    "community_events":     ("tasks.task_community_events",     "TaskCommunityEvents"),
    "chapter":              ("tasks.task_chapter",              "TaskChapter"),
    "commissions":          ("tasks.task_commissions",          "TaskCommissions"),
    "errands":              ("tasks.task_errands",              "TaskErrands"),
    "market_trade":         ("tasks.task_market_trade",         "TaskMarketTrade"),
    "toy_shop":             ("tasks.task_toy_shop",             "TaskToyShop"),
    "shield":               ("tasks.task_shield",               "TaskShield"),
}

# Priority: 2=HIGH (combat), 3=NORMAL (production), 4=LOW (collections)
TASK_PRI = {
    "gather": 2, "niflung": 2, "kill_monster": 2, "rally_niflung": 2,
    "gather_boost": 2, "gather_supplies": 2, "map_explore": 2,
    "conquer_island": 2, "reclaim_midgard": 2, "expansion": 2,
    "construction": 3, "research": 3, "helps": 3, "tribe_tech": 3,
    "hall_of_valor": 3, "clear_forest": 3, "prosperity": 3,
    "train_troops": 3, "heal_troops": 3, "troop_upgrade": 3,
    "wall_repair": 3, "smithy": 3, "chief_hall": 3,
    "upgrade_chief_hall": 3, "tribe_gold_tile": 3, "staging_post": 3,
    "hero_training": 3, "hero_xp": 3, "leidolf": 3,
    # everything else defaults to 4
}

# ═══════════════════════════════════════════════════════════════════
# Enhanced Bot Worker — all 4 improvements built-in
# ═══════════════════════════════════════════════════════════════════

class BotWorker(QThread):
    log_sig   = pyqtSignal(str)
    status_sig = pyqtSignal(str)
    stats_sig  = pyqtSignal(dict)
    done_sig   = pyqtSignal()

    def __init__(self, tasks, continuous=True):
        super().__init__()
        self.task_names = tasks
        self.continuous = continuous
        self.running = False

        # Stats
        self.cycle    = 0
        self.ok       = 0
        self.fail     = 0
        self.skip     = 0
        self.restarts = 0
        self.captchas = 0

    # ── Main loop ──────────────────────────────────

    def run(self):
        self.running = True
        self.status_sig.emit("Starting...")

        try:
            self.log_sig.emit("[VRBOT v5.0] Enhanced Engine")
            self.log_sig.emit("  [1] Anti-Ban Order  [2] Human Delays")
            self.log_sig.emit("  [3] Captcha Guard   [4] Auto-Restart")

            from vrbot_core import Bot
            bot = Bot()
            bot.go_to_city()

            self._start_health_monitor(bot)

            while self.running:
                self.cycle += 1

                # Break every 8 cycles
                if self.cycle > 1 and (self.cycle - 1) % 8 == 0:
                    d = random.uniform(60, 180)
                    self.log_sig.emit(f"  [break] {d:.0f}s rest")
                    self.status_sig.emit(f"Break ({d:.0f}s)")
                    time.sleep(d)
                    if not self.running:
                        break

                # Build randomized queue
                queue = self._build_queue()
                self.log_sig.emit(f"\n[Cycle {self.cycle}] {', '.join(queue)}")
                self.status_sig.emit(f"Cycle {self.cycle}")

                for tn in queue:
                    if not self.running:
                        break

                    if tn not in TASK_MAP:
                        self.skip += 1
                        continue

                    mn, cn = TASK_MAP[tn]
                    try:
                        mod = __import__(mn, fromlist=[cn])
                        cls = getattr(mod, cn)
                    except Exception as e:
                        self.log_sig.emit(f"[SKIP] {tn}: {e}")
                        self.skip += 1
                        continue

                    # Pre-task captcha check
                    if self._check_captcha(bot, tn):
                        continue  # skip task if captcha timeout

                    self.log_sig.emit(f"[>] {cls.name}")
                    self.status_sig.emit(f"Running: {cls.name}")

                    bot.go_to_city()
                    bot.wait(1)

                    t0 = time.time()
                    try:
                        success = cls(bot).run()
                    except Exception as e:
                        self.log_sig.emit(f"[ERR] {cls.name}: {e}")
                        success = False

                    dur = time.time() - t0
                    if success:
                        self.ok += 1
                        self.log_sig.emit(f"[OK]   {cls.name} ({dur:.1f}s)")
                    else:
                        self.fail += 1
                        self.log_sig.emit(f"[FAIL] {cls.name} ({dur:.1f}s)")
                        bot.go_to_city()

                    # Post-task captcha check
                    self._check_captcha(bot, tn)

                    # Human delay
                    self._human_delay()

                    # Update stats
                    self.stats_sig.emit(self._get_stats())

                self.log_sig.emit(f"[Cycle {self.cycle}] Complete")

                if not self.continuous:
                    break

                # Inter-cycle pause
                p = random.uniform(10, 25)
                time.sleep(p)

            # Done
            self.log_sig.emit(
                f"\n[DONE] {self.cycle} cycles | {self.ok} OK | {self.fail} FAIL | "
                f"restarts: {self.restarts} | captchas: {self.captchas}"
            )
            try:
                bot.print_stats()
            except Exception:
                pass

        except Exception as e:
            self.log_sig.emit(f"[FATAL] {e}")
            traceback.print_exc()

        self.running = False
        self.status_sig.emit("Stopped")
        self.stats_sig.emit(self._get_stats())
        self.done_sig.emit()

    def stop(self):
        self.running = False

    # ── [1] Random queue by priority ──────────────

    def _build_queue(self):
        groups = {}
        for n in self.task_names:
            p = TASK_PRI.get(n, 4)
            groups.setdefault(p, []).append(n)
        q = []
        for p in sorted(groups.keys()):
            g = groups[p][:]
            random.shuffle(g)
            q.extend(g)
        # Adjacent swaps
        for i in range(len(q) - 1):
            if random.random() < 0.3:
                if TASK_PRI.get(q[i], 4) == TASK_PRI.get(q[i + 1], 4):
                    q[i], q[i + 1] = q[i + 1], q[i]
        return q

    # ── [2] Human delay ───────────────────────────

    def _human_delay(self):
        if random.random() < 0.05:
            d = random.uniform(15, 45)
            self.log_sig.emit(f"  [anti-ban] Pause {d:.0f}s")
            time.sleep(d)
        else:
            time.sleep(random.uniform(2, 8))

    # ── [3] Captcha check via AI ──────────────────

    def _check_captcha(self, bot, task_name):
        """Returns True if captcha detected and not cleared (skip task)."""
        try:
            img = bot.screenshot_b64()
            if not img:
                return False
            r = bot.ask_ai(
                "Viking Rise screenshot. Is there a CAPTCHA, verification popup, "
                'or security check visible? JSON: {"captcha": true/false}',
                img, max_tokens=80,
            )
            if r and isinstance(r, dict) and r.get("captcha"):
                self.captchas += 1
                self.log_sig.emit(f"  [CAPTCHA] Detected during {task_name}!")
                self.status_sig.emit("CAPTCHA — Waiting...")
                try:
                    bot.screenshot("captcha_detected")
                except Exception:
                    pass
                # Wait for resolution (max 2 min)
                for _ in range(24):
                    time.sleep(5)
                    if not self.running:
                        return True
                    img2 = bot.screenshot_b64()
                    if not img2:
                        continue
                    r2 = bot.ask_ai(
                        'Is CAPTCHA still visible? JSON: {"captcha": true/false}',
                        img2, max_tokens=80,
                    )
                    if r2 and isinstance(r2, dict) and not r2.get("captcha"):
                        self.log_sig.emit("  [CAPTCHA] Cleared!")
                        return False
                self.log_sig.emit("  [CAPTCHA] Timeout")
                return True
        except Exception:
            pass
        return False

    # ── [4] Health monitor (background) ───────────

    def _start_health_monitor(self, bot):
        def _monitor():
            try:
                from vrbot_config import ADB_EXE, ADB_DEVICE
                exe, dev = ADB_EXE, ADB_DEVICE
            except Exception:
                exe, dev = "adb", "emulator-5554"

            pkg = "com.igg.android.vikingrise"
            act = pkg + "/" + pkg + ".MainActivity"

            while self.running:
                try:
                    r = subprocess.run(
                        [exe, "-s", dev, "shell", "pidof", pkg],
                        capture_output=True, text=True, timeout=10,
                    )
                    if not r.stdout.strip():
                        self.restarts += 1
                        self.log_sig.emit(
                            f"  [health] Game crashed! Restart #{self.restarts}"
                        )
                        subprocess.run(
                            [exe, "-s", dev, "shell", "am", "force-stop", pkg],
                            capture_output=True, timeout=10,
                        )
                        time.sleep(5)
                        subprocess.run(
                            [exe, "-s", dev, "shell", "am", "start", "-n", act],
                            capture_output=True, timeout=10,
                        )
                        time.sleep(40)
                        try:
                            bot.go_to_city()
                        except Exception:
                            pass
                        self.log_sig.emit("  [health] Game restarted")
                        self.stats_sig.emit(self._get_stats())
                except Exception:
                    pass
                time.sleep(15)

        threading.Thread(target=_monitor, daemon=True, name="health").start()

    # ── Stats helper ──────────────────────────────

    def _get_stats(self):
        return {
            "cycle":    self.cycle,
            "ok":       self.ok,
            "fail":     self.fail,
            "skip":     self.skip,
            "restarts": self.restarts,
            "captchas": self.captchas,
        }


# ═══════════════════════════════════════════════════════════════════
# GUI (same structure + Stats tab + mode selector)
# ═══════════════════════════════════════════════════════════════════

STYLESHEET = """
QMainWindow{background:#1a1a2e}
QLabel{color:#e0e0e0}
QGroupBox{color:#bb86fc;border:1px solid #333;border-radius:8px;
          margin-top:10px;padding-top:15px;font-weight:bold}
QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px}
QCheckBox{color:#e0e0e0;spacing:6px}
QPushButton{background:#bb86fc;color:#1a1a2e;border:none;
            border-radius:6px;padding:8px 16px;font-weight:bold}
QPushButton:hover{background:#d4a3ff}
QPushButton:disabled{background:#555;color:#999}
QPushButton#stop{background:#cf6679}
QPushButton#stop:hover{background:#e57373}
QLineEdit{background:#16213e;color:#e0e0e0;border:1px solid #333;
          border-radius:6px;padding:8px;font-size:14px}
QTextEdit{background:#0f0f23;color:#00ff88;border:1px solid #333;
          border-radius:6px;font-family:Consolas;font-size:12px}
QTabWidget::pane{border:1px solid #333;background:#1a1a2e}
QTabBar::tab{background:#16213e;color:#aaa;padding:8px 16px;
             border-top-left-radius:6px;border-top-right-radius:6px}
QTabBar::tab:selected{background:#bb86fc;color:#1a1a2e}
QComboBox{background:#16213e;color:#e0e0e0;border:1px solid #333;
          border-radius:6px;padding:6px 10px;min-width:140px}
QComboBox QAbstractItemView{background:#16213e;color:#e0e0e0;
                            selection-background-color:#bb86fc}
"""


class VRBotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.worker = None
        self.checks = {}
        self.stat_labels = {}
        self._build()
        # Auto-activate if license saved
        if self.cfg.get("license_key"):
            self.lic_input.setText(self.cfg["license_key"])
            QTimer.singleShot(500, self.activate)

    # ── Build UI ──────────────────────────────────

    def _build(self):
        self.setWindowTitle(f"VRBOT v{VERSION}")
        self.setMinimumSize(900, 780)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Header
        title = QLabel("VRBOT v5.0 — Enhanced Edition")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:#bb86fc;padding:6px")
        layout.addWidget(title)

        badges = QLabel(
            "Anti-Ban Order  |  Captcha Guard  |  Auto-Restart  |  Human Behavior"
        )
        badges.setAlignment(Qt.AlignCenter)
        badges.setStyleSheet("color:#00ff88;font-size:11px;padding:2px")
        layout.addWidget(badges)

        # License section
        lic_group = QGroupBox("License")
        lic_layout = QHBoxLayout(lic_group)
        self.lic_input = QLineEdit()
        self.lic_input.setPlaceholderText("Enter your farm token")
        self.lic_input.setMaxLength(40)
        lic_layout.addWidget(self.lic_input)
        act_btn = QPushButton("Activate")
        act_btn.clicked.connect(self.activate)
        lic_layout.addWidget(act_btn)
        self.lic_lbl = QLabel("Not activated")
        self.lic_lbl.setStyleSheet("color:#ff9800;font-weight:bold")
        lic_layout.addWidget(self.lic_lbl)
        layout.addWidget(lic_group)

        # Tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── Tab 1: Tasks ──
        tasks_widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidget(tasks_widget)
        scroll.setWidgetResizable(True)
        grid = QGridLayout(tasks_widget)
        col = 0
        pri_icon = {2: " [HIGH]", 3: "", 4: ""}
        for group_name, task_list in ALL_TASKS.items():
            group = QGroupBox(group_name)
            group_layout = QVBoxLayout(group)
            for key, name in task_list:
                icon = pri_icon.get(TASK_PRI.get(key, 4), "")
                cb = QCheckBox(name + icon)
                cb.setChecked(True)
                cb.setEnabled(False)
                self.checks[key] = cb
                group_layout.addWidget(cb)
            grid.addWidget(group, col // 2, col % 2)
            col += 1
        tabs.addTab(scroll, "Tasks")

        # ── Tab 2: Log ──
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        tabs.addTab(self.log_box, "Log")

        # ── Tab 3: Stats (NEW) ──
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.addSpacing(10)
        for key, label in [
            ("cycle",    "Cycles Completed"),
            ("ok",       "Tasks Successful"),
            ("fail",     "Tasks Failed"),
            ("skip",     "Tasks Skipped"),
            ("restarts", "Game Restarts"),
            ("captchas", "Captchas Detected"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"  {label}:")
            lbl.setStyleSheet("color:#aaa;font-size:14px")
            val = QLabel("0")
            val.setStyleSheet("color:#00ff88;font-size:20px;font-weight:bold")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            stats_layout.addLayout(row)
            self.stat_labels[key] = val
        stats_layout.addStretch()
        tabs.addTab(stats_widget, "Stats")

        # ── Controls bar ──
        ctrl = QHBoxLayout()

        # Mode selector (NEW)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Continuous", "Single Pass"])
        self.mode_combo.setEnabled(False)
        ctrl.addWidget(self.mode_combo)

        self.sa_btn = QPushButton("Select All")
        self.sa_btn.clicked.connect(
            lambda: [cb.setChecked(True) for cb in self.checks.values()]
        )
        self.sa_btn.setEnabled(False)
        ctrl.addWidget(self.sa_btn)

        self.da_btn = QPushButton("Deselect All")
        self.da_btn.clicked.connect(
            lambda: [cb.setChecked(False) for cb in self.checks.values()]
        )
        self.da_btn.setEnabled(False)
        ctrl.addWidget(self.da_btn)

        ctrl.addStretch()

        self.start_btn = QPushButton("START")
        self.start_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start)
        self.start_btn.setEnabled(False)
        ctrl.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False)
        ctrl.addWidget(self.stop_btn)

        layout.addLayout(ctrl)

        # Status bar
        self.status = QLabel("Enter license key")
        self.status.setStyleSheet("color:#888;padding:4px")
        layout.addWidget(self.status)

    # ── License activation (unchanged logic) ──────

    def activate(self):
        key = self.lic_input.text().strip()
        if not key:
            return
        hw = get_hw_id()
        try:
            if requests:
                r = requests.post(
                    f"{SERVER_URL}/api/activate",
                    json={"license_key": key, "hardware_id": hw},
                    timeout=10,
                )
                if r.status_code == 200:
                    d = r.json()
                    self.cfg.update({
                        "license_key": key,
                        "plan": d["plan"],
                        "max_farms": d["max_farms"],
                        "expires_at": d["expires_at"],
                    })
                    save_cfg(self.cfg)
                    self.lic_lbl.setText(
                        f"Active - {d['plan']} ({d['max_farms']} farms)"
                    )
                    self.lic_lbl.setStyleSheet("color:#00ff88;font-weight:bold")
                    self._unlock()
                    self._log(f"[LICENSE] {d['plan']} plan, {d['max_farms']} farms")
                    return
                else:
                    err = r.json().get("detail", "Failed")
                    self.lic_lbl.setText(err)
                    self.lic_lbl.setStyleSheet("color:#cf6679;font-weight:bold")
                    return
        except Exception:
            pass

        # Offline fallback
        if self.cfg.get("license_key") == key and self.cfg.get("plan"):
            self.lic_lbl.setText(f"Offline - {self.cfg['plan']}")
            self.lic_lbl.setStyleSheet("color:#ff9800;font-weight:bold")
            self._unlock()
            self._log("[LICENSE] Offline mode")
        else:
            self.lic_lbl.setText("Server offline")
            self.lic_lbl.setStyleSheet("color:#cf6679;font-weight:bold")

    def _unlock(self):
        for cb in self.checks.values():
            cb.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.sa_btn.setEnabled(True)
        self.da_btn.setEnabled(True)
        self.mode_combo.setEnabled(True)

    # ── Start / Stop ──────────────────────────────

    def start(self):
        enabled = [k for k, cb in self.checks.items() if cb.isChecked()]
        if not enabled:
            QMessageBox.warning(self, "Error", "Select at least one task!")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        continuous = self.mode_combo.currentIndex() == 0
        mode_str = "continuous" if continuous else "single pass"
        self._log(f"\nStarting {len(enabled)} tasks ({mode_str})...")

        self.worker = BotWorker(enabled, continuous=continuous)
        self.worker.log_sig.connect(self._log)
        self.worker.status_sig.connect(lambda t: self.status.setText(t))
        self.worker.stats_sig.connect(self._update_stats)
        self.worker.done_sig.connect(self._on_done)
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.stop()
            self._log("[STOP] Stopping...")

    def _on_done(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # ── Logging ───────────────────────────────────

    def _log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_box.append(f"[{ts}] {msg}")

    # ── Stats update (NEW) ────────────────────────

    def _update_stats(self, stats):
        for key, value in stats.items():
            if key in self.stat_labels:
                self.stat_labels[key].setText(str(value))


# ═══════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(26, 26, 46))
    palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
    palette.setColor(QPalette.Base, QColor(15, 15, 35))
    palette.setColor(QPalette.Text, QColor(224, 224, 224))
    app.setPalette(palette)
    window = VRBotGUI()
    window.show()
    sys.exit(app.exec_())
