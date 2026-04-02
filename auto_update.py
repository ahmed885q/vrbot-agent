"""
auto_update.py — VRBOT Auto-Update System
"""
import os, sys, json, hashlib, shutil, time
try:
    import requests
except ImportError:
    requests = None

SERVER_URL = "https://vrbot.me"
UPDATE_URL = f"{SERVER_URL}/api/update"
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "_backups")

def _current_version():
    try:
        ver_file = os.path.join(BASE_DIR, "version.txt")
        if os.path.exists(ver_file):
            return open(ver_file).read().strip()
        gui = os.path.join(BASE_DIR, "vrbot_gui.py")
        if os.path.exists(gui):
            for line in open(gui, encoding="utf-8"):
                if line.startswith("VERSION"):
                    return line.split('"')[1]
    except Exception:
        pass
    return "0.0.0"

def _file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def _backup(path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = os.path.basename(path)
    ts   = time.strftime("%Y%m%d_%H%M%S")
    dst  = os.path.join(BACKUP_DIR, f"{name}.{ts}.bak")
    shutil.copy2(path, dst)

def check_and_update(log=None):
    def _log(msg):
        if log: log(msg)
        else:   print(msg)

    if requests is None:
        _log("  [update] requests not installed — skipping")
        return False

    current = _current_version()
    _log(f"  [update] Checking updates (v{current})...")

    try:
        resp = requests.get(f"{UPDATE_URL}/check",
                            params={"version": current}, timeout=8)
        if resp.status_code != 200:
            return False
        data = resp.json()
        if not data.get("update_available"):
            _log(f"  [update] Already up to date (v{current})")
            return False

        latest = data.get("version", "?")
        files  = data.get("files", [])
        notes  = data.get("notes", "")
        _log(f"  [update] New version: v{latest}")
        if notes: _log(f"  [update] Notes: {notes}")

        ALLOWED = {"vrbot_core.py", "vrbot_config.py",
                   "template_matcher.py", "vrbot_utils.py", "vrbot_gui.py"}
        updated = False

        for file_info in files:
            fname    = file_info["name"]
            url      = file_info["url"]
            expected = file_info.get("md5")

            if not (fname in ALLOWED or fname.startswith("tasks/")):
                _log(f"  [update] Skipping: {fname}")
                continue

            dst_path = os.path.join(BASE_DIR, fname.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst_path) if os.path.dirname(dst_path) else BASE_DIR, exist_ok=True)

            if expected and os.path.exists(dst_path):
                if _file_hash(dst_path) == expected:
                    _log(f"  [update] {fname} — unchanged")
                    continue

            try:
                r = requests.get(url, timeout=30)
                if r.status_code != 200: continue
                content = r.content
                if expected and hashlib.md5(content).hexdigest() != expected:
                    _log(f"  [update] Hash mismatch: {fname}")
                    continue
                if os.path.exists(dst_path): _backup(dst_path)
                with open(dst_path, "wb") as f: f.write(content)
                _log(f"  [update] Updated: {fname}")
                updated = True
            except Exception as e:
                _log(f"  [update] Error: {fname}: {e}")

        if updated:
            with open(os.path.join(BASE_DIR, "version.txt"), "w") as f:
                f.write(latest)
            _log(f"  [update] Complete — v{latest} (restart required)")
        return updated
    except Exception as e:
        _log(f"  [update] Error: {e}")
        return False

def check_and_restart_if_updated(log=None):
    updated = check_and_update(log)
    if updated:
        if log: log("  [update] Restarting VRBOT...")
        time.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    return updated
