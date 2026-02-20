"""
VRBOT SaaS Master Setup
========================
Run this ONE script and it creates EVERYTHING:
- vrbot_server/server.py (License Server)
- vrbot_gui.py (Desktop Client GUI)
- patch_license_check.py (License integration)
- vrbot_installer.bat (Client installer)

Usage: python setup_saas.py
"""
import os

print("=" * 60)
print("  VRBOT SaaS — Creating all files...")
print("=" * 60)

# ============================================================
# 1. LICENSE SERVER
# ============================================================
os.makedirs("vrbot_server", exist_ok=True)

with open("vrbot_server/server.py", "w", encoding="utf-8") as f:
    f.write('''\
"""
VRBOT License Server
Run: uvicorn server:app --host 0.0.0.0 --port 8000
Or:  python server.py
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3, hashlib, secrets

app = FastAPI(title="VRBOT License Server", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

DB_PATH = "vrbot_licenses.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            license_key TEXT UNIQUE NOT NULL,
            max_farms INTEGER DEFAULT 5,
            plan TEXT DEFAULT 'basic',
            status TEXT DEFAULT 'active',
            hardware_id TEXT,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_heartbeat TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            plan TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()

init_db()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def gen_key():
    p = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"VRBOT-{p[0]}-{p[1]}-{p[2]}"

PLANS = {
    "starter": {"farms": 5, "price": 15},
    "basic": {"farms": 20, "price": 40},
    "advanced": {"farms": 50, "price": 80},
    "pro": {"farms": 100, "price": 140},
    "enterprise": {"farms": 500, "price": 250},
}

class RegisterReq(BaseModel):
    email: str
    password: str
    name: str = ""

class LoginReq(BaseModel):
    email: str
    password: str

class PurchaseReq(BaseModel):
    user_id: int
    plan: str

class ActivateReq(BaseModel):
    license_key: str
    hardware_id: str = ""

class HeartbeatReq(BaseModel):
    license_key: str
    hardware_id: str
    active_farms: int = 0

@app.post("/api/register")
def register(req: RegisterReq):
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (email, password_hash, name) VALUES (?,?,?)",
                      (req.email, hash_pw(req.password), req.name))
        conn.commit()
        uid = conn.execute("SELECT id FROM users WHERE email=?", (req.email,)).fetchone()["id"]
        return {"success": True, "user_id": uid}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Email already registered")
    finally:
        conn.close()

@app.post("/api/login")
def login(req: LoginReq):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE email=? AND password_hash=?",
                      (req.email, hash_pw(req.password))).fetchone()
    conn.close()
    if not u: raise HTTPException(401, "Invalid credentials")
    return {"success": True, "user_id": u["id"], "name": u["name"], "email": u["email"]}

@app.post("/api/purchase")
def purchase(req: PurchaseReq):
    if req.plan not in PLANS: raise HTTPException(400, "Invalid plan")
    info = PLANS[req.plan]
    key = gen_key()
    exp = datetime.now() + timedelta(days=30)
    conn = get_db()
    conn.execute("INSERT INTO licenses (user_id,license_key,max_farms,plan,expires_at) VALUES (?,?,?,?,?)",
                  (req.user_id, key, info["farms"], req.plan, exp.isoformat()))
    conn.execute("INSERT INTO payments (user_id,amount,plan,status) VALUES (?,?,?,'completed')",
                  (req.user_id, info["price"], req.plan))
    conn.commit()
    conn.close()
    return {"success": True, "license_key": key, "plan": req.plan,
            "max_farms": info["farms"], "price": info["price"], "expires_at": exp.isoformat()}

@app.post("/api/activate")
def activate(req: ActivateReq):
    conn = get_db()
    lic = conn.execute("SELECT * FROM licenses WHERE license_key=?", (req.license_key,)).fetchone()
    if not lic: conn.close(); raise HTTPException(404, "Invalid license key")
    if lic["status"] != "active": conn.close(); raise HTTPException(403, "License not active")
    if lic["expires_at"] and datetime.fromisoformat(lic["expires_at"]) < datetime.now():
        conn.execute("UPDATE licenses SET status='expired' WHERE id=?", (lic["id"],))
        conn.commit(); conn.close(); raise HTTPException(403, "License expired")
    if lic["hardware_id"] and lic["hardware_id"] != req.hardware_id:
        conn.close(); raise HTTPException(403, "License bound to another device")
    conn.execute("UPDATE licenses SET hardware_id=?, last_heartbeat=? WHERE id=?",
                  (req.hardware_id, datetime.now().isoformat(), lic["id"]))
    conn.commit(); conn.close()
    return {"success": True, "plan": lic["plan"], "max_farms": lic["max_farms"], "expires_at": lic["expires_at"]}

@app.post("/api/heartbeat")
def heartbeat(req: HeartbeatReq):
    conn = get_db()
    lic = conn.execute("SELECT * FROM licenses WHERE license_key=? AND hardware_id=?",
                        (req.license_key, req.hardware_id)).fetchone()
    if not lic: conn.close(); raise HTTPException(403, "Invalid license")
    if lic["status"] != "active": conn.close(); raise HTTPException(403, f"Status: {lic['status']}")
    if lic["expires_at"] and datetime.fromisoformat(lic["expires_at"]) < datetime.now():
        conn.execute("UPDATE licenses SET status='expired' WHERE id=?", (lic["id"],))
        conn.commit(); conn.close(); raise HTTPException(403, "License expired")
    if req.active_farms > lic["max_farms"]:
        conn.close(); raise HTTPException(403, f"Max farms: {lic['max_farms']}")
    conn.execute("UPDATE licenses SET last_heartbeat=? WHERE id=?",
                  (datetime.now().isoformat(), lic["id"]))
    conn.commit(); conn.close()
    return {"success": True, "max_farms": lic["max_farms"], "status": "active"}

@app.get("/api/admin/stats")
def stats():
    conn = get_db()
    users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    lics = conn.execute("SELECT COUNT(*) as c FROM licenses WHERE status='active'").fetchone()["c"]
    rev = conn.execute("SELECT COALESCE(SUM(amount),0) as t FROM payments WHERE status='completed'").fetchone()["t"]
    conn.close()
    return {"users": users, "active_licenses": lics, "total_revenue": rev}

@app.get("/api/admin/users")
def admin_users():
    conn = get_db()
    rows = conn.execute("SELECT u.*, COUNT(l.id) as lics FROM users u LEFT JOIN licenses l ON u.id=l.user_id GROUP BY u.id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/admin/licenses")
def admin_lics():
    conn = get_db()
    rows = conn.execute("SELECT l.*,u.email FROM licenses l JOIN users u ON l.user_id=u.id ORDER BY l.created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/generate-test")
def gen_test():
    conn = get_db()
    u = conn.execute("SELECT id FROM users WHERE email='admin@vrbot.com'").fetchone()
    if not u:
        conn.execute("INSERT INTO users (email,password_hash,name) VALUES (?,?,?)",
                      ("admin@vrbot.com", hash_pw("admin123"), "Admin"))
        conn.commit()
        u = conn.execute("SELECT id FROM users WHERE email='admin@vrbot.com'").fetchone()
    key = gen_key()
    exp = datetime.now() + timedelta(days=365)
    conn.execute("INSERT INTO licenses (user_id,license_key,max_farms,plan,expires_at) VALUES (?,?,?,?,?)",
                  (u["id"], key, 999, "enterprise", exp.isoformat()))
    conn.commit(); conn.close()
    return {"license_key": key, "plan": "enterprise", "farms": 999, "expires": "1 year"}

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  VRBOT License Server — http://localhost:8000")
    print("  API Docs: http://localhost:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
''')
print("  [1/4] vrbot_server/server.py")

# ============================================================
# 2. DESKTOP GUI
# ============================================================
with open("vrbot_gui.py", "w", encoding="utf-8") as f:
    f.write('''\
"""
VRBOT Desktop Client GUI
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
VERSION = "1.0.0"

def get_hw_id():
    info = f"{uuid.getnode()}-{os.environ.get('COMPUTERNAME','unknown')}"
    return hashlib.md5(info.encode()).hexdigest()[:16]

def load_cfg():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f: return json.load(f)
    return {}

def save_cfg(d):
    with open(CONFIG_FILE, 'w') as f: json.dump(d, f, indent=2)

ALL_TASKS = {
    "Quick Collections": [
        ("daily_gifts","Daily Gifts"),("rewards","Quest Rewards"),
        ("mail_rewards","Mail Rewards"),("helps","Alliance Helps"),
        ("tribe_gifts","Tribe Gifts"),("prosperity","Prosperity"),
    ],
    "Production": [
        ("construction","Construction"),("research","Research"),
        ("train_troops","Train Troops"),("shield","Shield"),
    ],
    "Economy": [
        ("gather","Gather"),("errands","Errands"),
        ("commissions","Commissions"),("farmer_appointments","Farmer Appts"),
        ("recruit_farmers","Recruit Farmers"),("village_champions","Village Champs"),
    ],
    "Heroes & Items": [
        ("hall_of_valor","Hall of Valor"),("hero_xp","Hero XP"),
        ("hero_training","Hero Training"),("account_items","Account Items"),
        ("divination","Divination"),("smithy","Smithy"),
    ],
    "Combat": [
        ("niflung","Niflung"),("staging_post","Staging Post"),
        ("clear_forest","Clear Forest"),("cinderbone","Cinderbone"),
        ("reclaim_midgard","Reclaim Midgard"),
    ],
    "Events & Strategy": [
        ("leidolf","Leidolf"),("festival_flames","Festival Flames"),
        ("promo_codes","Promo Codes"),("chief_hall","Chief Hall"),
        ("upgrade_chief_hall","Upgrade CH"),("expansion","Expansion"),
        ("tribe_tech","Tribe Tech"),("chapter","Chapter"),
    ],
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
            TASK_MAP = {
                "helps":("tasks.task_helps","TaskHelps"),
                "tribe_gifts":("tasks.task_tribe_gifts","TaskTribeGifts"),
                "mail_rewards":("tasks.task_mail_rewards","TaskMailRewards"),
                "daily_gifts":("tasks.task_daily_gifts","TaskDailyGifts"),
                "rewards":("tasks.task_rewards","TaskRewards"),
                "shield":("tasks.task_shield","TaskShield"),
                "construction":("tasks.task_construction","TaskConstruction"),
                "research":("tasks.task_research","TaskResearch"),
                "train_troops":("tasks.task_train_troops","TaskTrainTroops"),
                "prosperity":("tasks.task_prosperity","TaskProsperity"),
                "errands":("tasks.task_errands","TaskErrands"),
                "commissions":("tasks.task_commissions","TaskCommissions"),
                "farmer_appointments":("tasks.task_farmer_appointments","TaskFarmerAppointments"),
                "recruit_farmers":("tasks.task_recruit_farmers","TaskRecruitFarmers"),
                "village_champions":("tasks.task_village_champions","TaskVillageChampions"),
                "hall_of_valor":("tasks.task_hall_of_valor","TaskHallOfValor"),
                "hero_xp":("tasks.task_hero_xp","TaskHeroXp"),
                "hero_training":("tasks.task_hero_training","TaskHeroTraining"),
                "account_items":("tasks.task_account_items","TaskAccountItems"),
                "divination":("tasks.task_divination","TaskDivination"),
                "smithy":("tasks.task_smithy","TaskSmithy"),
                "gather":("tasks.task_gather","TaskGather"),
                "niflung":("tasks.task_niflung","TaskNiflung"),
                "staging_post":("tasks.task_staging_post","TaskStagingPost"),
                "clear_forest":("tasks.task_clear_forest","TaskClearForest"),
                "cinderbone":("tasks.task_cinderbone","TaskCinderbone"),
                "reclaim_midgard":("tasks.task_reclaim_midgard","TaskReclaimMidgard"),
                "leidolf":("tasks.task_leidolf","TaskLeidolf"),
                "festival_flames":("tasks.task_festival_flames","TaskFestivalFlames"),
                "promo_codes":("tasks.task_promo_codes","TaskPromoCodes"),
                "chief_hall":("tasks.task_chief_hall","TaskChiefHall"),
                "upgrade_chief_hall":("tasks.task_upgrade_chief_hall","TaskUpgradeChiefHall"),
                "expansion":("tasks.task_expansion","TaskExpansion"),
                "tribe_tech":("tasks.task_tribe_tech","TaskTribeTech"),
                "chapter":("tasks.task_chapter","TaskChapter"),
            }
            bot = Bot()
            bot.go_to_city()
            ok = fail = 0
            for tn in self.tasks:
                if not self.running: break
                if tn not in TASK_MAP: continue
                mn, cn = TASK_MAP[tn]
                try:
                    mod = __import__(mn, fromlist=[cn])
                    cls = getattr(mod, cn)
                except Exception as e:
                    self.log_sig.emit(f"[ERR] {tn}: {e}")
                    fail += 1; continue
                self.log_sig.emit(f"[TASK] {cls.name}...")
                self.status_sig.emit(f"Running: {cls.name}")
                bot.go_to_city(); bot.wait(1)
                try:
                    if cls(bot).run():
                        ok += 1; self.log_sig.emit(f"[OK] {cls.name}")
                    else:
                        fail += 1; self.log_sig.emit(f"[FAIL] {cls.name}")
                except Exception as e:
                    fail += 1; self.log_sig.emit(f"[ERR] {cls.name}: {e}")
                bot.task_delay()
            self.log_sig.emit(f"\\n[DONE] {ok} OK / {fail} FAIL")
            bot.print_stats()
        except Exception as e:
            self.log_sig.emit(f"[FATAL] {e}")
        self.running = False
        self.status_sig.emit("Stopped")
        self.done_sig.emit()

    def stop(self): self.running = False

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
        h.setFont(QFont("Segoe UI",16,QFont.Bold)); h.setAlignment(Qt.AlignCenter)
        h.setStyleSheet("color:#bb86fc;padding:8px"); L.addWidget(h)

        g = QGroupBox("License"); gl = QHBoxLayout(g)
        self.lic_input = QLineEdit(); self.lic_input.setPlaceholderText("VRBOT-XXXX-XXXX-XXXX")
        self.lic_input.setMaxLength(19); gl.addWidget(self.lic_input)
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
            tl.addWidget(gb, col//3, col%3); col += 1
        tabs.addTab(sa, "Tasks")

        self.log = QTextEdit(); self.log.setReadOnly(True)
        tabs.addTab(self.log, "Log")

        cl = QHBoxLayout()
        sa_btn = QPushButton("Select All"); sa_btn.clicked.connect(lambda: [c.setChecked(True) for c in self.checks.values()])
        sa_btn.setEnabled(False); self.sa_btn = sa_btn; cl.addWidget(sa_btn)
        da_btn = QPushButton("Deselect All"); da_btn.clicked.connect(lambda: [c.setChecked(False) for c in self.checks.values()])
        da_btn.setEnabled(False); self.da_btn = da_btn; cl.addWidget(da_btn)
        cl.addStretch()
        self.start_btn = QPushButton("START"); self.start_btn.setFont(QFont("Segoe UI",12,QFont.Bold))
        self.start_btn.setMinimumHeight(40); self.start_btn.clicked.connect(self.start)
        self.start_btn.setEnabled(False); cl.addWidget(self.start_btn)
        self.stop_btn = QPushButton("STOP"); self.stop_btn.setObjectName("stop")
        self.stop_btn.setFont(QFont("Segoe UI",12,QFont.Bold)); self.stop_btn.setMinimumHeight(40)
        self.stop_btn.clicked.connect(self.stop); self.stop_btn.setEnabled(False); cl.addWidget(self.stop_btn)
        L.addLayout(cl)

        self.status = QLabel("Enter license key"); self.status.setStyleSheet("color:#888;padding:4px")
        L.addWidget(self.status)

    def activate(self):
        key = self.lic_input.text().strip()
        if not key: return
        hw = get_hw_id()
        try:
            r = requests.post(f"{SERVER_URL}/api/activate", json={"license_key":key,"hardware_id":hw}, timeout=10)
            if r.status_code == 200:
                d = r.json()
                self.cfg.update({"license_key":key,"plan":d["plan"],"max_farms":d["max_farms"],"expires_at":d["expires_at"]})
                save_cfg(self.cfg)
                self.lic_lbl.setText(f"Active - {d['plan']} ({d['max_farms']} farms)")
                self.lic_lbl.setStyleSheet("color:#00ff88;font-weight:bold")
                self._unlock()
                self._log(f"[LICENSE] {d['plan']} plan, {d['max_farms']} farms, expires {d['expires_at']}")
            else:
                err = r.json().get("detail","Failed")
                self.lic_lbl.setText(err); self.lic_lbl.setStyleSheet("color:#cf6679;font-weight:bold")
        except requests.ConnectionError:
            if self.cfg.get("license_key") == key and self.cfg.get("plan"):
                self.lic_lbl.setText(f"Offline - {self.cfg['plan']}")
                self.lic_lbl.setStyleSheet("color:#ff9800;font-weight:bold")
                self._unlock(); self._log("[LICENSE] Offline mode")
            else:
                self.lic_lbl.setText("Server offline"); self.lic_lbl.setStyleSheet("color:#cf6679;font-weight:bold")

    def _unlock(self):
        for cb in self.checks.values(): cb.setEnabled(True)
        self.start_btn.setEnabled(True); self.sa_btn.setEnabled(True); self.da_btn.setEnabled(True)

    def start(self):
        en = [k for k,cb in self.checks.items() if cb.isChecked()]
        if not en: QMessageBox.warning(self,"Error","Select tasks!"); return
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self._log(f"\\nStarting {len(en)} tasks...")
        self.worker = BotWorker(en)
        self.worker.log_sig.connect(self._log)
        self.worker.status_sig.connect(lambda t: self.status.setText(t))
        self.worker.done_sig.connect(lambda: (self.start_btn.setEnabled(True), self.stop_btn.setEnabled(False)))
        self.worker.start()

    def stop(self):
        if self.worker: self.worker.stop(); self._log("[STOP]")

    def _log(self, msg):
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window, QColor(26,26,46))
    p.setColor(QPalette.WindowText, QColor(224,224,224))
    p.setColor(QPalette.Base, QColor(15,15,35))
    p.setColor(QPalette.Text, QColor(224,224,224))
    app.setPalette(p)
    w = VRBotGUI(); w.show(); sys.exit(app.exec_())
''')
print("  [2/4] vrbot_gui.py")

# ============================================================
# 3. LICENSE PATCH
# ============================================================
with open("patch_license_check.py", "w", encoding="utf-8") as f:
    f.write('''\
"""
Adds license check to vrbot_core.py
Run ONCE: python patch_license_check.py
"""
import os

LICENSE_METHOD = """
    def check_license(self):
        import hashlib, uuid, json
        try:
            if not os.path.exists("vrbot_license.json"):
                print("  [LICENSE] No license. Run vrbot_gui.py first.")
                return False
            with open("vrbot_license.json") as f:
                cfg = json.load(f)
            key = cfg.get("license_key", "")
            if not key:
                print("  [LICENSE] No key found.")
                return False
            info = f"{uuid.getnode()}-{os.environ.get('COMPUTERNAME','unknown')}"
            hw = hashlib.md5(info.encode()).hexdigest()[:16]
            try:
                import requests
                r = requests.post(
                    f"{cfg.get('server_url','http://localhost:8000')}/api/heartbeat",
                    json={"license_key": key, "hardware_id": hw}, timeout=5)
                if r.status_code == 200:
                    print(f"  [LICENSE] Valid - {cfg.get('plan','')} plan")
                    return True
                print(f"  [LICENSE] Rejected: {r.json().get('detail','')}")
                return False
            except:
                if cfg.get("plan"):
                    print(f"  [LICENSE] Offline - {cfg.get('plan','')} plan")
                    return True
                return False
        except Exception as e:
            print(f"  [LICENSE] Error: {e}")
            return False
"""

if not os.path.exists("vrbot_core.py"):
    print("vrbot_core.py not found! Run from vrbot-agent folder.")
else:
    with open("vrbot_core.py", "r", encoding="utf-8") as f:
        code = f.read()
    if "check_license" in code:
        print("License check already exists!")
    else:
        marker = "        _init_yolo()"
        if marker in code:
            code = code.replace(marker, marker + "\\n" + LICENSE_METHOD)
            with open("vrbot_core.py", "w", encoding="utf-8") as f:
                f.write(code)
            print("  License check added to vrbot_core.py!")
        else:
            print("  Could not find insertion point - add manually")
''')
print("  [3/4] patch_license_check.py")

# ============================================================
# 4. INSTALLER BAT
# ============================================================
with open("vrbot_installer.bat", "w", encoding="utf-8") as f:
    f.write('''\
@echo off
echo ============================================
echo   VRBOT Installer
echo ============================================
pip install PyQt5 requests openai ultralytics --quiet
if not exist "models" mkdir models
if not exist "debug_screenshots" mkdir debug_screenshots
echo.
echo   Done! Run: python vrbot_gui.py
pause
''')
print("  [4/4] vrbot_installer.bat")

# ============================================================
# DONE
# ============================================================
print()
print("=" * 60)
print("  ALL FILES CREATED!")
print("=" * 60)
print()
print("  NEXT STEPS:")
print("  1. Open NEW PowerShell:")
print("     cd vrbot_server")
print("     python server.py")
print()
print("  2. Open ANOTHER PowerShell:")
print("     curl -X POST http://localhost:8000/api/admin/generate-test")
print("     (copy the license key)")
print()
print("  3. python vrbot_gui.py")
print("     (paste the key and click Activate)")
print()
print("=" * 60)
