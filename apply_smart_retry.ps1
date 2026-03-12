$agent = "C:\Users\manso\vrbot-agent"
$main = "$agent\vrbot_main.py"

Write-Host "VRBOT Smart Retry - Auto Patch"
Write-Host "================================"

# 1. نسخة احتياطية
Copy-Item $main "$main.bak" -Force
Write-Host "[1] OK - backup created: vrbot_main.py.bak"

# 2. تحقق من smart_retry.py
if (-not (Test-Path "$agent\smart_retry.py")) {
    Write-Host "[!] ERROR - smart_retry.py not found in $agent"
    exit 1
}
Write-Host "[2] OK - smart_retry.py found"

# 3. اقرأ الملف
$content = Get-Content $main -Raw -Encoding UTF8

# 4. اضف import
if ($content -notmatch "from smart_retry import") {
    $content = $content -replace "(from vrbot_config import[^\n]+)", "`$1`nfrom smart_retry import SmartRetry"
    Write-Host "[3] OK - added import SmartRetry"
} else {
    Write-Host "[3] OK - import already exists"
}

# 5. اضف init في TaskRunner
if ($content -notmatch "self\.smart_retry\s*=\s*SmartRetry") {
    $content = $content -replace "(self\.bot\s*=\s*bot)", "`$1`n        self.smart_retry = SmartRetry(bot=self.bot)"
    Write-Host "[4] OK - added SmartRetry init"
} else {
    Write-Host "[4] OK - SmartRetry init already exists"
}

# 6. اضف retry بعد task.run()
if ($content -notmatch "smart_retry\.handle") {
    $old = "success = task_obj.run()"
    $new = "success = task_obj.run()`n            if not success:`n                self.log.warning(f'[{task_name}] failed - SmartRetry...')`n                success = self.smart_retry.handle(task_name, self.bot)`n                if success:`n                    self.log.info(f'[{task_name}] SmartRetry saved it!')"
    $content = $content.Replace($old, $new)
    Write-Host "[5] OK - added retry after task.run()"
} else {
    Write-Host "[5] OK - retry already exists"
}

# 7. احفظ
$content | Set-Content $main -Encoding UTF8
Write-Host "[6] OK - saved vrbot_main.py"

# 8. syntax check
$py = "$env:USERPROFILE\miniconda3\envs\vrbot\python.exe"
$check = & $py -c "import ast; ast.parse(open('$main', encoding='utf-8').read()); print('SYNTAX_OK')" 2>&1
if ($check -match "SYNTAX_OK") {
    Write-Host "[7] OK - syntax check passed"
    Write-Host ""
    Write-Host "SUCCESS! Smart Retry is now active"
    Write-Host "Every failed task will trigger SmartRetry automatically"
} else {
    Write-Host "[7] ERROR - syntax error, restoring backup..."
    Copy-Item "$main.bak" $main -Force
    Write-Host "Restored original file. Apply manually using vrbot_main_patch.py"
    Write-Host $check
    exit 1
}
