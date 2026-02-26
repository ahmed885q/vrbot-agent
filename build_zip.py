"""
Build clean VRBOT Agent zip for distribution.
Run: python build_zip.py
"""
import os
import zipfile
from datetime import datetime

ZIP_NAME = f"vrbot-agent-v5-clean.zip"

# Files/folders to INCLUDE
INCLUDE = [
    "vrbot_main.py", "vrbot_gui.py", "vrbot_core.py", "vrbot_config.py",
    "vrbot_installer.bat", "vrbot_license.json",
    "__init__.py", "hub_client.py", "launcher.py", "main.py",
    "run_task.py", "yolo_detector.py",
    "requirements.txt", "README.md", ".gitignore",
    "install.bat", "setup.bat", "start.bat",
]

INCLUDE_DIRS = [
    "tasks",       # all task files
    "config",      # config files
    "models",      # YOLO models
    "templates",   # template images
    "ws",          # websocket
]

# Files/folders to EXCLUDE
EXCLUDE_PATTERNS = [
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".pyc", ".pyo", ".log", ".tmp", ".bak",
    "debug_screenshots", "logs", "screenshots",
    "check_full.py", "verify_v5.py", "fix_config.py",  # utility scripts
    "Thumbs.db", ".DS_Store",
]

def should_exclude(path):
    for pat in EXCLUDE_PATTERNS:
        if pat in path:
            return True
    return False

print(f"Building {ZIP_NAME}...")
print("=" * 50)

count = 0
total_size = 0

with zipfile.ZipFile(ZIP_NAME, 'w', zipfile.ZIP_DEFLATED) as zf:
    # Root files
    for f in INCLUDE:
        if os.path.exists(f):
            size = os.path.getsize(f)
            zf.write(f, f"vrbot-agent/{f}")
            count += 1
            total_size += size
            print(f"  + {f} ({size/1024:.1f}KB)")
        
    # Directories
    for dir_name in INCLUDE_DIRS:
        if not os.path.isdir(dir_name):
            continue
        for root, dirs, files in os.walk(dir_name):
            # Skip excluded dirs
            dirs[:] = [d for d in dirs if not should_exclude(d)]
            for f in sorted(files):
                fpath = os.path.join(root, f)
                if should_exclude(fpath):
                    continue
                size = os.path.getsize(fpath)
                zf.write(fpath, f"vrbot-agent/{fpath}")
                count += 1
                total_size += size

    print(f"\n  Directories:")
    for dir_name in INCLUDE_DIRS:
        if os.path.isdir(dir_name):
            dir_files = sum(1 for r,d,fs in os.walk(dir_name) 
                          for f in fs if not should_exclude(os.path.join(r,f)))
            print(f"    {dir_name}/: {dir_files} files")

# Summary
zip_size = os.path.getsize(ZIP_NAME)
print(f"\n{'=' * 50}")
print(f"  {ZIP_NAME}")
print(f"  Files: {count}")
print(f"  Original: {total_size/1024/1024:.1f} MB")
print(f"  Zip:      {zip_size/1024/1024:.1f} MB")
print(f"{'=' * 50}")
print(f"Done!")
