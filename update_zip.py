"""
update_zip.py — creates a new agent ZIP and uploads to Supabase Storage
Run: python update_zip.py
"""
import os
import sys
import zipfile
import urllib.request
import json

# Detect agent directory (same dir as this script)
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_NAME = "vrbot-agent-v5.zip"
ZIP_PATH = os.path.join(AGENT_DIR, ZIP_NAME)

SUPABASE_URL = "https://xmanyfpojzkjlwatkrcc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhtYW55ZnBvanpramx3YXRrcmNjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NzYxNzQxNywiZXhwIjoyMDgzMTkzNDE3fQ.0SAL8fcFLiGhHy9FgGCM-AS4l2fNBBhOjEWB9d9zrGc"
BUCKET = "downloads"
OBJECT_NAME = "vrbot-agent-v5.zip"

# Ignore patterns
IGNORE_DIRS = {
    "__pycache__", ".git", ".pytest_cache", "node_modules",
    "debug_screenshots", "logs", ".vscode", ".idea",
    "templates_backup_330",
}
IGNORE_EXTENSIONS = {".pyc", ".log", ".tmp", ".bak"}
IGNORE_FILES = {
    ".env", "smart_retry_memory.json", "tasks_log.json",
    "farm_status.json", "debug_shot.png", "update_zip.py",
}


def should_ignore(path, is_dir=False):
    name = os.path.basename(path)
    if is_dir:
        return name in IGNORE_DIRS
    if name in IGNORE_FILES:
        return True
    _, ext = os.path.splitext(name)
    return ext in IGNORE_EXTENSIONS


# Step 1: Create ZIP
print(f"Creating {ZIP_NAME}...")
file_count = 0
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(AGENT_DIR):
        dirs[:] = [d for d in dirs if not should_ignore(d, is_dir=True)]
        for file in files:
            if should_ignore(file):
                continue
            full_path = os.path.join(root, file)
            arcname = os.path.relpath(full_path, AGENT_DIR)
            # Skip the ZIP itself
            if arcname == ZIP_NAME:
                continue
            zf.write(full_path, arcname)
            file_count += 1

zip_size = os.path.getsize(ZIP_PATH)
print(f"  {file_count} files | {zip_size // 1024}KB")

# Step 2: Upload to Supabase
print(f"\nUploading to Supabase ({BUCKET}/{OBJECT_NAME})...")
with open(ZIP_PATH, "rb") as f:
    data = f.read()

req = urllib.request.Request(
    f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{OBJECT_NAME}",
    data=data,
    method="PUT",
    headers={
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/zip",
        "x-upsert": "true",
    },
)

try:
    r = urllib.request.urlopen(req)
    print(f"  Upload OK ({r.status})")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"  Upload FAILED: {e.code} - {body}")
    sys.exit(1)

# Step 3: Verify
download_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{OBJECT_NAME}"
print(f"\nDone!")
print(f"  URL:  {download_url}")
print(f"  Size: {zip_size // 1024}KB")
print(f"  Files: {file_count}")
