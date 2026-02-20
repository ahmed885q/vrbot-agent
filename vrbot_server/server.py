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
