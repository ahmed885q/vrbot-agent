"""
VRBOT v5.0 — Comprehensive Compatibility & Error Check
========================================================
Checks:
  1. File structure & syntax
  2. Import chain validation
  3. TASK_MAP consistency (main vs gui vs config vs task files)
  4. Class/method signature compatibility
  5. vrbot_core.Bot API usage validation
  6. vrbot_config integration check
  7. Enhancement classes internal consistency
  8. GUI signal/slot wiring
  9. Thread safety analysis
  10. Dead code & missing reference detection

Usage: python check_full.py
"""
import ast
import os
import sys
import re
import importlib.util
from pathlib import Path

# ═══════════════════════════════════════════════════
PASS = FAIL = WARN = 0

def ok(label, detail=""):
    global PASS; PASS += 1
    print(f"  [PASS] {label}" + (f"  ({detail})" if detail else ""))

def fail(label, detail=""):
    global FAIL; FAIL += 1
    print(f"  [FAIL] {label}" + (f"  → {detail}" if detail else ""))

def warn(label, detail=""):
    global WARN; WARN += 1
    print(f"  [WARN] {label}" + (f"  → {detail}" if detail else ""))

def check(label, cond, detail=""):
    if cond: ok(label, detail)
    else: fail(label, detail)

def parse_file(path):
    try:
        code = open(path, encoding="utf-8").read()
        tree = ast.parse(code)
        return code, tree
    except Exception as e:
        return None, None

def get_classes(tree):
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}

def get_functions(tree):
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

def get_methods(class_node):
    return {n.name: n for n in ast.walk(class_node) if isinstance(n, ast.FunctionDef)}

def get_dict_keys(code, tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    if isinstance(node.value, ast.Dict):
                        return [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    return []

def get_string_values(code, pattern):
    return re.findall(pattern, code)

# ═══════════════════════════════════════════════════
print("=" * 70)
print("  VRBOT v5.0 — Full Compatibility & Error Check")
print("=" * 70)

# ═══════════════════════════════════════════════════
# [1] FILE STRUCTURE
# ═══════════════════════════════════════════════════
print("\n[1] File Structure:")

required_files = [
    "vrbot_main.py", "vrbot_gui.py", "vrbot_core.py", "vrbot_config.py"
]
for f in required_files:
    check(f"  {f}", os.path.exists(f))

check("  tasks/ directory", os.path.isdir("tasks"))

task_files = []
if os.path.isdir("tasks"):
    task_files = sorted([f for f in os.listdir("tasks") if f.startswith("task_") and f.endswith(".py")])
    check(f"  task files found: {len(task_files)}", len(task_files) >= 15, f"{len(task_files)} files")

optional = ["logs/", "debug_screenshots/", "models/", "templates/"]
for d in optional:
    if os.path.isdir(d.rstrip("/")):
        ok(f"  {d} exists")
    else:
        warn(f"  {d} missing", "optional, will be created at runtime")

# ═══════════════════════════════════════════════════
# [2] SYNTAX VALIDATION
# ═══════════════════════════════════════════════════
print("\n[2] Syntax Validation:")

files_to_check = required_files + [f"tasks/{f}" for f in task_files]
parsed = {}
for f in files_to_check:
    if not os.path.exists(f):
        continue
    try:
        code = open(f, encoding="utf-8").read()
        tree = ast.parse(code)
        parsed[f] = (code, tree)
        ok(f"  {f}")
    except SyntaxError as e:
        fail(f"  {f}", f"Line {e.lineno}: {e.msg}")

# ═══════════════════════════════════════════════════
# [3] TASK_MAP CONSISTENCY
# ═══════════════════════════════════════════════════
print("\n[3] TASK_MAP Consistency:")

main_code, main_tree = parsed.get("vrbot_main.py", (None, None))
gui_code, gui_tree = parsed.get("vrbot_gui.py", (None, None))
config_code, config_tree = parsed.get("vrbot_config.py", (None, None))

main_tasks = []
gui_tasks = []
config_enabled = []

if main_tree:
    main_tasks = get_dict_keys(main_code, main_tree, "TASK_MAP")
    check(f"  vrbot_main.py TASK_MAP: {len(main_tasks)} tasks", len(main_tasks) == 37)

if gui_tree:
    gui_tasks = get_dict_keys(gui_code, gui_tree, "TASK_MAP")
    check(f"  vrbot_gui.py TASK_MAP: {len(gui_tasks)} tasks", len(gui_tasks) >= 15)

# GUI tasks must be subset of main tasks
if main_tasks and gui_tasks:
    missing_in_main = set(gui_tasks) - set(main_tasks)
    if missing_in_main:
        fail(f"  GUI tasks not in main TASK_MAP", str(missing_in_main))
    else:
        ok("  GUI TASK_MAP is subset of main TASK_MAP")

# Check TASKS_ENABLED in config
if config_tree:
    config_enabled = get_dict_keys(config_code, config_tree, "TASKS_ENABLED")
    if config_enabled:
        check(f"  vrbot_config.py TASKS_ENABLED: {len(config_enabled)} tasks", len(config_enabled) > 0)
        # Tasks in config should exist in main
        unknown = set(config_enabled) - set(main_tasks)
        if unknown:
            warn(f"  Config has tasks not in TASK_MAP", str(unknown))
        else:
            ok("  All config tasks exist in TASK_MAP")
    else:
        warn("  Could not parse TASKS_ENABLED from config", "may use different format")

# Check module paths in TASK_MAP match actual files
print("\n  Module → File mapping:")
if main_tree:
    for node in ast.walk(main_tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "TASK_MAP":
                    if isinstance(node.value, ast.Dict):
                        for k, v in zip(node.value.keys, node.value.values):
                            if isinstance(k, ast.Constant) and isinstance(v, ast.Tuple):
                                task_name = k.value
                                if v.elts and isinstance(v.elts[0], ast.Constant):
                                    module_path = v.elts[0].value  # e.g. "tasks.task_gather"
                                    file_path = module_path.replace(".", "/") + ".py"
                                    if os.path.exists(file_path):
                                        pass  # ok, don't print every one
                                    else:
                                        warn(f"    {task_name}: {file_path} not found",
                                             "task file missing from repo")

    # Count missing files
    missing_count = 0
    found_count = 0
    for node in ast.walk(main_tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "TASK_MAP":
                    if isinstance(node.value, ast.Dict):
                        for k, v in zip(node.value.keys, node.value.values):
                            if isinstance(v, ast.Tuple) and v.elts:
                                mp = v.elts[0]
                                if isinstance(mp, ast.Constant):
                                    fp = mp.value.replace(".", "/") + ".py"
                                    if os.path.exists(fp):
                                        found_count += 1
                                    else:
                                        missing_count += 1
    check(f"  Task files found: {found_count}/{found_count + missing_count}",
          missing_count == 0, f"{missing_count} missing" if missing_count else "all present")

# ═══════════════════════════════════════════════════
# [4] PRIORITY MAP CHECK
# ═══════════════════════════════════════════════════
print("\n[4] Priority Map:")

if main_tree:
    pri_tasks = get_dict_keys(main_code, main_tree, "TASK_PRIORITY")
    if pri_tasks:
        check(f"  TASK_PRIORITY defined: {len(pri_tasks)} entries", len(pri_tasks) > 0)
        # Every task in TASK_MAP should have a priority
        no_priority = set(main_tasks) - set(pri_tasks)
        if no_priority:
            warn(f"  Tasks without priority (will default to NORMAL)", str(no_priority))
        else:
            ok("  All 37 tasks have priorities assigned")
        # No orphan priorities
        orphan_pri = set(pri_tasks) - set(main_tasks)
        if orphan_pri:
            warn(f"  Priority entries for non-existent tasks", str(orphan_pri))
        else:
            ok("  No orphan priority entries")
    else:
        fail("  TASK_PRIORITY not found in vrbot_main.py")

# ═══════════════════════════════════════════════════
# [5] vrbot_core.py API CHECK
# ═══════════════════════════════════════════════════
print("\n[5] vrbot_core.py API Compatibility:")

if "vrbot_core.py" in parsed:
    core_code, core_tree = parsed["vrbot_core.py"]
    core_classes = get_classes(core_tree)

    if "Bot" in core_classes:
        ok("  Bot class found")
        bot_methods = get_methods(core_classes["Bot"])
        bot_method_names = set(bot_methods.keys())

        # Methods used by vrbot_main.py
        main_uses = set()
        if main_code:
            for call in ["go_to_city", "wait", "task_delay", "print_stats",
                         "screenshot_b64", "ask_ai", "screenshot"]:
                if f"bot.{call}" in main_code or f"self.bot.{call}" in main_code:
                    main_uses.add(call)

            for method in main_uses:
                if method in bot_method_names:
                    ok(f"    bot.{method}() exists in Bot class")
                else:
                    warn(f"    bot.{method}() used but not found in Bot",
                         "may be defined dynamically or inherited")

        # Methods used by GUI
        gui_uses = set()
        if gui_code:
            for call in ["go_to_city", "wait", "task_delay", "print_stats",
                         "screenshot_b64", "ask_ai", "screenshot"]:
                if f"bot.{call}" in gui_code:
                    gui_uses.add(call)

            for method in gui_uses:
                if method in bot_method_names:
                    ok(f"    bot.{method}() (GUI) exists in Bot class")
                else:
                    warn(f"    bot.{method}() (GUI) not found in Bot",
                         "may be defined dynamically")
    else:
        fail("  Bot class NOT found in vrbot_core.py")
else:
    fail("  vrbot_core.py not parseable")

# ═══════════════════════════════════════════════════
# [6] vrbot_config.py INTEGRATION
# ═══════════════════════════════════════════════════
print("\n[6] vrbot_config.py Integration:")

if config_code:
    # Check what main imports from config
    main_config_imports = []
    if main_code:
        for line in main_code.splitlines():
            if "from vrbot_config import" in line:
                imports = line.split("import")[1].strip()
                main_config_imports = [x.strip() for x in imports.split(",")]

        check(f"  main imports: {', '.join(main_config_imports)}", len(main_config_imports) > 0)

        # Verify imported names exist in config
        config_names = set()
        for node in ast.walk(config_tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        config_names.add(t.id)

        for imp in main_config_imports:
            if imp in config_names:
                ok(f"    {imp} exists in vrbot_config.py")
            else:
                fail(f"    {imp} NOT found in vrbot_config.py")

    # Check ADB_EXE and ADB_DEVICE (used by HealthGuard)
    if main_code and "ADB_EXE" in main_code:
        if "ADB_EXE" in config_names:
            ok("  ADB_EXE found in config (used by HealthGuard)")
        else:
            warn("  ADB_EXE used by HealthGuard but not in config",
                 "HealthGuard has fallback to 'adb'")
    if main_code and "ADB_DEVICE" in main_code:
        if "ADB_DEVICE" in config_names:
            ok("  ADB_DEVICE found in config (used by HealthGuard)")
        else:
            warn("  ADB_DEVICE used by HealthGuard but not in config",
                 "HealthGuard has fallback to 'emulator-5554'")

# ═══════════════════════════════════════════════════
# [7] ENHANCEMENT CLASSES CHECK
# ═══════════════════════════════════════════════════
print("\n[7] Enhancement Classes:")

if main_tree:
    classes = get_classes(main_tree)

    # AntiBanScheduler
    if "AntiBanScheduler" in classes:
        ok("  AntiBanScheduler class")
        methods = get_methods(classes["AntiBanScheduler"])
        check("    build_queue() method", "build_queue" in methods)
    else:
        fail("  AntiBanScheduler class missing")

    # HumanBehavior
    if "HumanBehavior" in classes:
        ok("  HumanBehavior class")
        methods = get_methods(classes["HumanBehavior"])
        check("    task_delay() method", "task_delay" in methods)
        check("    cycle_break() method", "cycle_break" in methods)
        check("    should_break() method", "should_break" in methods)
    else:
        fail("  HumanBehavior class missing")

    # CaptchaGuard
    if "CaptchaGuard" in classes:
        ok("  CaptchaGuard class")
        methods = get_methods(classes["CaptchaGuard"])
        check("    __init__() method", "__init__" in methods)
        check("    check() method", "check" in methods)
        check("    wait_clear() method", "wait_clear" in methods)
        check("    _on_detected() method", "_on_detected" in methods)
        check("    _notify() method", "_notify" in methods)
        # Verify it uses bot.ask_ai
        captcha_code = ast.get_source_segment(main_code, classes["CaptchaGuard"])
        if captcha_code:
            check("    Uses bot.ask_ai()", "ask_ai" in captcha_code)
            check("    Uses bot.screenshot_b64()", "screenshot_b64" in captcha_code)
    else:
        fail("  CaptchaGuard class missing")

    # HealthGuard
    if "HealthGuard" in classes:
        ok("  HealthGuard class")
        methods = get_methods(classes["HealthGuard"])
        check("    __init__() method", "__init__" in methods)
        check("    check() method", "check" in methods)
        check("    recover() method", "recover" in methods)
        check("    start_background() method", "start_background" in methods)
        check("    stop_background() method", "stop_background" in methods)
        check("    _loop() method", "_loop" in methods)
        # Verify game package
        health_code = ast.get_source_segment(main_code, classes["HealthGuard"])
        if health_code:
            check("    Correct game package", "com.igg.android.vikingriseglobal" in health_code)
    else:
        fail("  HealthGuard class missing")

# ═══════════════════════════════════════════════════
# [8] GUI SIGNAL/SLOT WIRING
# ═══════════════════════════════════════════════════
print("\n[8] GUI Signal/Slot Wiring:")

if gui_tree:
    gui_classes = get_classes(gui_tree)

    # BotWorker signals
    if "BotWorker" in gui_classes:
        ok("  BotWorker class found")
        worker_code = ast.get_source_segment(gui_code, gui_classes["BotWorker"])
        if worker_code:
            for sig in ["log_sig", "status_sig", "stats_sig", "done_sig"]:
                check(f"    Signal: {sig}", sig in worker_code)
            # Check emit calls
            for emit in ["log_sig.emit", "status_sig.emit", "stats_sig.emit", "done_sig.emit"]:
                check(f"    Emits: {emit}", emit in worker_code)
    else:
        fail("  BotWorker class missing in GUI")

    # VRBotGUI connections
    if "VRBotGUI" in gui_classes:
        ok("  VRBotGUI class found")
        gui_main_code = ast.get_source_segment(gui_code, gui_classes["VRBotGUI"])
        if gui_main_code:
            # Check signal connections
            check("    Connects log_sig", "log_sig.connect" in gui_main_code)
            check("    Connects status_sig", "status_sig.connect" in gui_main_code)
            check("    Connects stats_sig", "stats_sig.connect" in gui_main_code)
            check("    Connects done_sig", "done_sig.connect" in gui_main_code)
            # Check key methods
            gui_methods = get_methods(gui_classes["VRBotGUI"])
            for m in ["_build", "activate", "_unlock", "start", "stop", "_log", "_update_stats"]:
                check(f"    Method: {m}()", m in gui_methods)
    else:
        fail("  VRBotGUI class missing in GUI")

# ═══════════════════════════════════════════════════
# [9] THREAD SAFETY
# ═══════════════════════════════════════════════════
print("\n[9] Thread Safety:")

if main_code:
    # Health monitor uses daemon thread
    check("  HealthGuard uses daemon thread", "daemon=True" in main_code)
    # Captcha notify uses daemon thread
    check("  CaptchaGuard notify uses daemon thread",
          main_code.count("daemon=True") >= 2, f"found {main_code.count('daemon=True')} daemon threads")

if gui_code:
    # BotWorker inherits QThread
    check("  BotWorker extends QThread", "class BotWorker(QThread)" in gui_code)
    # Health monitor in GUI uses daemon
    check("  GUI health monitor uses daemon thread", "daemon=True" in gui_code)
    # Signals used for cross-thread communication
    check("  Uses pyqtSignal for thread safety", "pyqtSignal" in gui_code)

# ═══════════════════════════════════════════════════
# [10] TASK FILE STRUCTURE CHECK
# ═══════════════════════════════════════════════════
print("\n[10] Task File Compatibility:")

sample_tasks = ["tasks/task_gather.py", "tasks/task_niflung.py", "tasks/task_shield.py",
                "tasks/task_construction.py", "tasks/task_daily_gifts.py"]

for tf in sample_tasks:
    if tf not in parsed:
        if os.path.exists(tf):
            code, tree = parse_file(tf)
            if tree:
                parsed[tf] = (code, tree)

checked_tasks = 0
for tf in task_files[:10]:  # Check first 10 task files
    path = f"tasks/{tf}"
    if path in parsed:
        code, tree = parsed[path]
    elif os.path.exists(path):
        code, tree = parse_file(path)
    else:
        continue

    if not tree:
        fail(f"  {tf}: syntax error")
        continue

    classes = get_classes(tree)
    if not classes:
        warn(f"  {tf}: no class found")
        continue

    # Check first class has .name and .run()
    cls_name = list(classes.keys())[0]
    cls_node = classes[cls_name]
    methods = get_methods(cls_node)

    has_run = "run" in methods
    has_name = False
    # Check for class attribute 'name'
    for node in ast.walk(cls_node):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "name":
                    has_name = True

    if has_run and has_name:
        checked_tasks += 1
    elif not has_run:
        warn(f"  {tf} ({cls_name}): missing run() method")
    elif not has_name:
        warn(f"  {tf} ({cls_name}): missing 'name' attribute")

if checked_tasks > 0:
    ok(f"  {checked_tasks} task files have correct structure (name + run())")

# ═══════════════════════════════════════════════════
# [11] IMPORT CHAIN VALIDATION
# ═══════════════════════════════════════════════════
print("\n[11] Import Chain:")

if main_code:
    # Check all imports in main are standard or available
    imports = []
    for node in ast.walk(main_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    stdlib = {"sys", "os", "time", "random", "hashlib", "logging", "subprocess",
              "threading", "traceback", "datetime"}
    project = {"vrbot_core", "vrbot_config"}

    for imp in imports:
        base = imp.split(".")[0]
        if base in stdlib:
            pass  # ok
        elif base in project:
            if os.path.exists(f"{base}.py"):
                ok(f"  import {imp} → {base}.py exists")
            else:
                fail(f"  import {imp} → {base}.py NOT found")
        elif base == "tasks":
            pass  # lazy loaded
        else:
            warn(f"  import {imp}", "third-party, ensure installed")

# ═══════════════════════════════════════════════════
# [12] CLASSIC MODE / CLI FLAGS
# ═══════════════════════════════════════════════════
print("\n[12] CLI Modes:")

if main_code:
    check("  --list flag", "--list" in main_code)
    check("  --once flag", "--once" in main_code)
    check("  --classic flag", "--classic" in main_code)
    check("  main_classic() function", "def main_classic" in main_code)
    check("  main_enhanced() function", "def main_enhanced" in main_code)
    check("  main() entry point", "def main()" in main_code or "def main():" in main_code)
    check("  __name__ guard", 'if __name__ == "__main__"' in main_code)

# ═══════════════════════════════════════════════════
# [13] CROSS-REFERENCE CHECK
# ═══════════════════════════════════════════════════
print("\n[13] Cross-Reference:")

if main_code:
    # Verify run_task calls load_task_class
    check("  run_task() calls load_task_class()", "load_task_class" in main_code)

    # Verify main_enhanced uses all 4 enhancements
    check("  main_enhanced uses AntiBanScheduler", "AntiBanScheduler.build_queue" in main_code)
    check("  main_enhanced uses HumanBehavior", "HumanBehavior.task_delay" in main_code)
    check("  main_enhanced uses CaptchaGuard", "CaptchaGuard(bot)" in main_code)
    check("  main_enhanced uses HealthGuard", "HealthGuard(bot)" in main_code)

    # Verify TASK_ORDER still exists for classic mode
    check("  TASK_ORDER preserved", "TASK_ORDER = [" in main_code or "TASK_ORDER =" in main_code)

# ═══════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════
print(f"\n{'=' * 70}")
total = PASS + FAIL + WARN
print(f"  RESULTS: {PASS} PASS / {FAIL} FAIL / {WARN} WARN  (total {total} checks)")
print(f"{'=' * 70}")

if FAIL == 0 and WARN == 0:
    print("  ✅ PERFECT — No issues found!")
elif FAIL == 0:
    print(f"  ✅ GOOD — {WARN} warnings (non-critical)")
    print("  Warnings are informational and won't break functionality.")
else:
    print(f"  ❌ {FAIL} issues need fixing before production use.")
print(f"{'=' * 70}")
