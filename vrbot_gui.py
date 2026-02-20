"""
VRBOT Desktop Client GUI - 16 Tasks Edition
Run: python vrbot_gui.py
"""
import sys, os, json, time, hashlib, uuid, threading, requests
from datetime import datetime

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt5.QtGui import QFont, QColor, QPalette
except ImportError:
    print("Run: pip install PyQt5")
    sys.exit(1)

SERVER_URL = "http://localhost:8000"
CONFIG_FILE = "vrbot_license.json"
VERSION = "1.1.0"

def get_hw_id():
    info = f"{uuid.getnode()}-{os.environ.get('COMPUTERNAME','unknown')}"
    return hashlib.md5(info.encode()).hexdigest()[:16]

def load_cfg():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f: return json.load(f)
    return {}

def save_cfg(d):
    with open(CONFIG_FILE, 'w') as f: json.dump(d, f, indent=2)

# === 16 TASKS ONLY ===
ALL_TASKS = {
    "Quick Collections": [
        ("daily_gifts", "Daily Gifts"),
        ("rewards", "Quest Rewards"),
        ("mail_rewards", "Mail Rewards"),
        ("helps", "Alliance Helps"),
        ("tribe_gifts", "Tribe Gifts"),
        ("prosperity", "Prosperity"),
    ],
    "Buildings": [
        ("construction", "Upgrade Building"),
        ("research", "Research"),
        ("hall_of_valor", "Hall of Valor"),
        ("clear_forest", "Clear Forest"),
    ],
    "World Map": [
        ("gather", "Gather Resources"),
        ("niflung", "Kill Niflung"),
        ("kill_monster", "Kill Monster"),
        ("rally_niflung", "Rally Niflung Leader"),
    ],
    "Alliance": [
        ("tribe_tech", "Tribe Technology"),
    ],
}

# Task module mapping
TASK_MAP = {
    "daily_gifts": ("tasks.task_daily_gifts", "TaskDailyGifts"),
    "rewards": ("tasks.task_rewards", "TaskRewards"),
    "mail_rewards": ("tasks.task_mail_rewards", "TaskMailRewards"),
    "helps": ("tasks.task_helps", "TaskHelps"),
    "tribe_gifts": ("tasks.task_tribe_gifts", "TaskTribeGifts"),
    "prosperity": ("tasks.task_prosperity", "TaskProsperity"),
    "construction": ("tasks.task_construction", "TaskConstruction"),
    "research": ("tasks.task_research", "TaskResearch"),
    "hall_of_valor": ("tasks.task_hall_of_valor", "TaskHallOfValor"),
    "clear_forest": ("tasks.task_clear_forest", "TaskClearForest"),
    "gather": ("tasks.task_gather", "TaskGather"),
    "niflung": ("tasks.task_niflung", "TaskNiflung"),
    "kill_monster": ("tasks.task_kill_monster", "TaskKillMonster"),
    "rally_niflung": ("tasks.task_rally_niflung", "TaskRallyNiflung"),
    "tribe_tech": ("tasks.task_tribe_tech", "TaskTribeTech"),
}


class BotWorker(QThread):
    log_sig = pyqtSignal(str)
    status_sig = pyqtSignal(str)
    done_sig = pyqtSignal()

    def __init__(self, tasks):
        super().__init__()
        self.tasks = tasks
        self.running = False

    def run(self):
        self.running = True
        self.status_sig.emit("Running")
        try:
            self.log_sig.emit("[VRBOT] Starting...")
            from vrbot_core import Bot
            bot = Bot()
            bot.go_to_city()
            ok = fail = skip = 0
            for tn in self.tasks:
                if not self.running:
                    break
                if tn not in TASK_MAP:
                    self.log_sig.emit(f"[SKIP] {tn}: no module yet")
                    skip += 1
                    continue
                mn, cn = TASK_MAP[tn]
                try:
                    mod = __import__(mn, fromlist=[cn])
                    cls = getattr(mod, cn)
                except Exception as e:
                    self.log_sig.emit(f"[SKIP] {tn}: {e}")
                    skip += 1
                    continue
                self.log_sig.emit(f"[TASK] {cls.name}...")
                self.status_sig.emit(f"Running: {cls.name}")
                bot.go_to_city()
                bot.wait(1)
                try:
                    if cls(bot).run():
                        ok += 1
                        self.log_sig.emit(f"[OK] {cls.name}")
                    else:
                        fail += 1
                        self.log_sig.emit(f"[FAIL] {cls.name}")
                except Exception as e:
                    fail += 1
                    self.log_sig.emit(f"[ERR] {cls.name}: {e}")
                bot.task_delay()
            self.log_sig.emit(f"\n[DONE] {ok} OK / {fail} FAIL / {skip} SKIP")
            bot.print_stats()
        except Exception as e:
            self.log_sig.emit(f"[FATAL] {e}")
        self.running = False
        self.status_sig.emit("Stopped")
        self.done_sig.emit()

    def stop(self):
        self.running = False


class VRBotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.worker = None
        self.checks = {}
        self._build()
        if self.cfg.get("license_key"):
            self.lic_input.setText(self.cfg["license_key"])
            QTimer.singleShot(500, self.activate)

    def _build(self):
        self.setWindowTitle(f"VRBOT v{VERSION}")
        self.setMinimumSize(820, 620)
        self.setStyleSheet("""
            QMainWindow{background:#1a1a2e}
            QLabel{color:#e0e0e0}
            QGroupBox{color:#bb86fc;border:1px solid #333;border-radius:8px;margin-top:10px;padding-top:15px;font-weight:bold}
            QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px}
            QCheckBox{color:#e0e0e0;spacing:6px}
            QPushButton{background:#bb86fc;color:#1a1a2e;border:none;border-radius:6px;padding:8px 16px;font-weight:bold}
            QPushButton:hover{background:#d4a3ff}
            QPushButton:disabled{background:#555;color:#999}
            QPushButton#stop{background:#cf6679}
            QLineEdit{background:#16213e;color:#e0e0e0;border:1px solid #333;border-radius:6px;padding:8px;font-size:14px}
            QTextEdit{background:#0f0f23;color:#00ff88;border:1px solid #333;border-radius:6px;font-family:Consolas;font-size:12px}
            QTabWidget::pane{border:1px solid #333;background:#1a1a2e}
            QTabBar::tab{background:#16213e;color:#aaa;padding:8px 16px;border-top-left-radius:6px;border-top-right-radius:6px}
            QTabBar::tab:selected{background:#bb86fc;color:#1a1a2e}
        """)
        c = QWidget(); self.setCentralWidget(c); L = QVBoxLayout(c)

        h = QLabel("VRBOT - Viking Rise Automation")
        h.setFont(QFont("Segoe UI", 16, QFont.Bold)); h.setAlignment(Qt.AlignCenter)
        h.setStyleSheet("color:#bb86fc;padding:8px"); L.addWidget(h)

        g = QGroupBox("License"); gl = QHBoxLayout(g)
        self.lic_input = QLineEdit(); self.lic_input.setPlaceholderText("VRBOT-XXXX-XXXX-XXXX")
        self.lic_input.setMaxLength(20); gl.addWidget(self.lic_input)
        ab = QPushButton("Activate"); ab.clicked.connect(self.activate); gl.addWidget(ab)
        self.lic_lbl = QLabel("Not activated")
        self.lic_lbl.setStyleSheet("color:#ff9800;font-weight:bold"); gl.addWidget(self.lic_lbl)
        L.addWidget(g)

        tabs = QTabWidget(); L.addWidget(tabs)

        tw = QWidget(); sa = QScrollArea(); sa.setWidget(tw); sa.setWidgetResizable(True)
        tl = QGridLayout(tw); col = 0
        for gn, ts in ALL_TASKS.items():
            gb = QGroupBox(gn); gbl = QVBoxLayout(gb)
            for k, n in ts:
                cb = QCheckBox(n); cb.setChecked(True); cb.setEnabled(False)
                self.checks[k] = cb; gbl.addWidget(cb)
            tl.addWidget(gb, col // 2, col % 2); col += 1
        tabs.addTab(sa, "Tasks")

        self.log = QTextEdit(); self.log.setReadOnly(True)
        tabs.addTab(self.log, "Log")

        cl = QHBoxLayout()
        sa_btn = QPushButton("Select All")
        sa_btn.clicked.connect(lambda: [c.setChecked(True) for c in self.checks.values()])
        sa_btn.setEnabled(False); self.sa_btn = sa_btn; cl.addWidget(sa_btn)
        da_btn = QPushButton("Deselect All")
        da_btn.clicked.connect(lambda: [c.setChecked(False) for c in self.checks.values()])
        da_btn.setEnabled(False); self.da_btn = da_btn; cl.addWidget(da_btn)
        cl.addStretch()
        self.start_btn = QPushButton("START")
        self.start_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start)
        self.start_btn.setEnabled(False); cl.addWidget(self.start_btn)
        self.stop_btn = QPushButton("STOP"); self.stop_btn.setObjectName("stop")
        self.stop_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False); cl.addWidget(self.stop_btn)
        L.addLayout(cl)

        self.status = QLabel("Enter license key")
        self.status.setStyleSheet("color:#888;padding:4px")
        L.addWidget(self.status)

    def activate(self):
        key = self.lic_input.text().strip()
        if not key:
            return
        hw = get_hw_id()
        try:
            r = requests.post(f"{SERVER_URL}/api/activate",
                              json={"license_key": key, "hardware_id": hw}, timeout=10)
            if r.status_code == 200:
                d = r.json()
                self.cfg.update({
                    "license_key": key, "plan": d["plan"],
                    "max_farms": d["max_farms"], "expires_at": d["expires_at"]
                })
                save_cfg(self.cfg)
                self.lic_lbl.setText(f"Active - {d['plan']} ({d['max_farms']} farms)")
                self.lic_lbl.setStyleSheet("color:#00ff88;font-weight:bold")
                self._unlock()
                self._log(f"[LICENSE] {d['plan']} plan, {d['max_farms']} farms")
            else:
                err = r.json().get("detail", "Failed")
                self.lic_lbl.setText(err)
                self.lic_lbl.setStyleSheet("color:#cf6679;font-weight:bold")
        except requests.ConnectionError:
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

    def start(self):
        en = [k for k, cb in self.checks.items() if cb.isChecked()]
        if not en:
            QMessageBox.warning(self, "Error", "Select tasks!")
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._log(f"\nStarting {len(en)} tasks...")
        self.worker = BotWorker(en)
        self.worker.log_sig.connect(self._log)
        self.worker.status_sig.connect(lambda t: self.status.setText(t))
        self.worker.done_sig.connect(
            lambda: (self.start_btn.setEnabled(True), self.stop_btn.setEnabled(False))
        )
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.stop()
            self._log("[STOP]")

    def _log(self, msg):
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window, QColor(26, 26, 46))
    p.setColor(QPalette.WindowText, QColor(224, 224, 224))
    p.setColor(QPalette.Base, QColor(15, 15, 35))
    p.setColor(QPalette.Text, QColor(224, 224, 224))
    app.setPalette(p)
    w = VRBotGUI(); w.show(); sys.exit(app.exec_())
