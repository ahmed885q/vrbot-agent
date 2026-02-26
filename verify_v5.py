"""
VRBOT v5.0 — Verification Script
Run after copying the new files to confirm everything is correct.

Usage: python verify_v5.py
"""
import ast
import os
import sys
import hashlib

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}  {detail}")

print("=" * 60)
print("  VRBOT v5.0 — Verification")
print("=" * 60)

# ── 1. Files exist ──
print("\n[1] File Check:")
for f in ["vrbot_main.py", "vrbot_gui.py", "vrbot_core.py", "vrbot_config.py"]:
    check(f"  {f} exists", os.path.exists(f))

check("  tasks/ folder exists", os.path.isdir("tasks"))

# ── 2. Syntax valid ──
print("\n[2] Syntax Check:")
for f in ["vrbot_main.py", "vrbot_gui.py"]:
    if os.path.exists(f):
        try:
            code = open(f, encoding="utf-8").read()
            ast.parse(code)
            check(f"  {f} syntax OK", True)
        except SyntaxError as e:
            check(f"  {f} syntax", False, str(e))

# ── 3. vrbot_main.py checks ──
print("\n[3] vrbot_main.py Content:")
if os.path.exists("vrbot_main.py"):
    code = open("vrbot_main.py", encoding="utf-8").read()
    
    # Version
    check("  Version 5.0", "v5.0" in code or "5.0" in code)
    
    # All 37 tasks in TASK_MAP
    tree = ast.parse(code)
    task_map_keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "TASK_MAP":
                    if isinstance(node.value, ast.Dict):
                        task_map_keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    check(f"  TASK_MAP has 37 tasks (found {len(task_map_keys)})", len(task_map_keys) == 37)
    
    # Key tasks present
    for t in ["gather", "niflung", "shield", "construction", "daily_gifts"]:
        check(f"    task '{t}' in TASK_MAP", t in task_map_keys)
    
    # Enhancements
    check("  AntiBanScheduler class", "class AntiBanScheduler" in code)
    check("  HumanBehavior class", "class HumanBehavior" in code)
    check("  CaptchaGuard class", "class CaptchaGuard" in code)
    check("  HealthGuard class", "class HealthGuard" in code)
    
    # Original TASK_ORDER preserved
    check("  TASK_ORDER preserved", "TASK_ORDER" in code)
    
    # Classic mode
    check("  --classic mode available", "main_classic" in code)
    
    # Imports
    check("  imports vrbot_core.Bot", "from vrbot_core import Bot" in code)
    check("  imports vrbot_config.TASKS_ENABLED", "from vrbot_config import TASKS_ENABLED" in code)

# ── 4. vrbot_gui.py checks ──
print("\n[4] vrbot_gui.py Content:")
if os.path.exists("vrbot_gui.py"):
    code = open("vrbot_gui.py", encoding="utf-8").read()
    
    check("  Version 5.0.0", '5.0.0' in code)
    
    # GUI TASK_MAP (15 tasks)
    tree = ast.parse(code)
    gui_keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "TASK_MAP":
                    if isinstance(node.value, ast.Dict):
                        gui_keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    check(f"  GUI TASK_MAP has 15 tasks (found {len(gui_keys)})", len(gui_keys) == 15)
    
    # License system
    check("  License activation", "def activate" in code)
    check("  SERVER_URL", "SERVER_URL" in code)
    check("  CONFIG_FILE", "vrbot_license.json" in code)
    
    # Enhancements in GUI
    check("  Stats tab", "stat_labels" in code or "stat_lbl" in code)
    check("  Mode selector (Continuous/Single)", "Continuous" in code and "Single Pass" in code)
    check("  Captcha detection", "captcha" in code.lower())
    check("  Health monitor", "health" in code.lower() and "pidof" in code)
    check("  Random queue", "_build_queue" in code or "shuffle" in code)
    check("  Human delay", "_human_delay" in code)

# ── 5. Core files untouched ──
print("\n[5] Core Files (should be unchanged):")
if os.path.exists("vrbot_core.py"):
    check("  vrbot_core.py present", True)
if os.path.exists("vrbot_config.py"):
    check("  vrbot_config.py present", True)

# ── 6. Task files ──
print("\n[6] Task Files:")
if os.path.isdir("tasks"):
    task_files = [f for f in os.listdir("tasks") if f.startswith("task_") and f.endswith(".py")]
    check(f"  Task files found: {len(task_files)}", len(task_files) >= 15)
    for key_task in ["task_gather.py", "task_niflung.py", "task_shield.py"]:
        check(f"    {key_task}", key_task in task_files)

# ── 7. Import test ──
print("\n[7] Import Test:")
try:
    # Test that vrbot_main can be parsed and key classes found
    spec = ast.parse(open("vrbot_main.py", encoding="utf-8").read())
    classes = [n.name for n in ast.walk(spec) if isinstance(n, ast.ClassDef)]
    check(f"  Classes in vrbot_main: {', '.join(classes)}", len(classes) >= 4)
except Exception as e:
    check("  Parse vrbot_main", False, str(e))

try:
    spec = ast.parse(open("vrbot_gui.py", encoding="utf-8").read())
    classes = [n.name for n in ast.walk(spec) if isinstance(n, ast.ClassDef)]
    check(f"  Classes in vrbot_gui: {', '.join(classes)}", len(classes) >= 2)
except Exception as e:
    check("  Parse vrbot_gui", False, str(e))

# ── Summary ──
print(f"\n{'=' * 60}")
if FAIL == 0:
    print(f"  ALL PASSED! ({PASS}/{PASS} checks)")
    print(f"  VRBOT v5.0 integrated correctly.")
else:
    print(f"  {PASS} PASSED / {FAIL} FAILED")
    print(f"  Fix the failures above before running.")
print(f"{'=' * 60}")
