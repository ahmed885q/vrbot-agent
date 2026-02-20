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
            code = code.replace(marker, marker + "\n" + LICENSE_METHOD)
            with open("vrbot_core.py", "w", encoding="utf-8") as f:
                f.write(code)
            print("  License check added to vrbot_core.py!")
        else:
            print("  Could not find insertion point - add manually")
