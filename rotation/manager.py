"""
VRBOT Agent — Rotation System
Manages multiple game accounts across LDPlayer instances.
Inspired by GnBots' rotation mode.
"""
import json
import os
import time
import random
import logging
from datetime import datetime, timedelta
from enum import Enum

log = logging.getLogger("vrbot.rotation")

ACCOUNTS_FILE = "config/accounts.json"


class AccountStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"


class Account:
    """Represents a single game account."""

    def __init__(self, data):
        self.id = data.get("id", "")
        self.name = data.get("name", "")
        self.instance_index = data.get("instance_index", 0)
        self.game_account = data.get("game_account", "")
        self.enabled = data.get("enabled", True)
        self.status = AccountStatus(data.get("status", "idle"))
        self.last_run = data.get("last_run")
        self.last_error = data.get("last_error")
        self.run_count = data.get("run_count", 0)
        self.error_count = data.get("error_count", 0)
        self.tasks_completed = data.get("tasks_completed", 0)
        self.rules = data.get("rules", {})
        self.notes = data.get("notes", "")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "instance_index": self.instance_index,
            "game_account": self.game_account,
            "enabled": self.enabled,
            "status": self.status.value,
            "last_run": self.last_run,
            "last_error": self.last_error,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "tasks_completed": self.tasks_completed,
            "rules": self.rules,
            "notes": self.notes,
        }

    def should_run_now(self):
        """Check if account should run based on rules."""
        if not self.enabled:
            return False
        if self.status == AccountStatus.DISABLED:
            return False

        rules = self.rules

        # Check day-of-week rules
        if "days" in rules:
            today = datetime.now().strftime("%a").lower()  # mon, tue, etc.
            if today not in [d.lower() for d in rules["days"]]:
                return False

        # Check time window rules
        if "time_start" in rules and "time_end" in rules:
            now_hour = datetime.now().hour
            if not (rules["time_start"] <= now_hour < rules["time_end"]):
                return False

        # Check cooldown
        if self.last_run and "cooldown_minutes" in rules:
            last = datetime.fromisoformat(self.last_run)
            cooldown = timedelta(minutes=rules["cooldown_minutes"])
            if datetime.now() - last < cooldown:
                return False

        # Check max runs per day
        if "max_runs_per_day" in rules:
            if self.run_count >= rules["max_runs_per_day"]:
                return False

        return True


class RotationManager:
    """
    Manages account rotation — the core multi-account system.

    Modes:
    1. Rotation Mode: Run accounts one at a time, cycling through them
    2. Multi-Instance: Run N accounts simultaneously on separate emulator instances
    """

    def __init__(self, adb_controller, config=None):
        self.adb = adb_controller
        self.config = config or {}
        self.accounts = []
        self.current_index = 0
        self.accounts_at_once = self.config.get("accounts_at_once", 1)
        self.rotation_delay = self.config.get("rotation_delay", 10)
        self.skip_failed = self.config.get("skip_failed_accounts", True)
        self.cooldown = self.config.get("cooldown_between_rotations", 60)
        self._rotation_count = 0

        self.load_accounts()

    # ─── Account Management ───────────────────────────────────

    def load_accounts(self):
        """Load accounts from config file."""
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "r") as f:
                data = json.load(f)
            self.accounts = [Account(a) for a in data.get("accounts", [])]
            log.info(f"Loaded {len(self.accounts)} accounts")
        else:
            self.accounts = []
            self.save_accounts()

    def save_accounts(self):
        """Save accounts to config file."""
        os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
        data = {"accounts": [a.to_dict() for a in self.accounts]}
        with open(ACCOUNTS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def add_account(self, name, instance_index, game_account="", rules=None):
        """Add new account to rotation."""
        acc = Account({
            "id": f"acc_{len(self.accounts)+1}_{int(time.time())}",
            "name": name,
            "instance_index": instance_index,
            "game_account": game_account,
            "rules": rules or {},
        })
        self.accounts.append(acc)
        self.save_accounts()
        log.info(f"Added account: {name} (instance {instance_index})")
        return acc

    def remove_account(self, account_id):
        """Remove account from rotation."""
        self.accounts = [a for a in self.accounts if a.id != account_id]
        self.save_accounts()

    # ─── Rotation Logic ───────────────────────────────────────

    def get_next_accounts(self):
        """Get next account(s) to run based on rotation mode."""
        eligible = [a for a in self.accounts if a.should_run_now()]

        if not eligible:
            log.info("No eligible accounts to run")
            return []

        if self.accounts_at_once == 1:
            # Single rotation mode
            return [self._get_next_single(eligible)]
        else:
            # Multi-instance mode
            return self._get_next_multi(eligible)

    def _get_next_single(self, eligible):
        """Get next single account in rotation."""
        # Round-robin through eligible accounts
        if self.current_index >= len(eligible):
            self.current_index = 0
            self._rotation_count += 1

        account = eligible[self.current_index]
        self.current_index += 1
        return account

    def _get_next_multi(self, eligible):
        """Get next batch of accounts for multi-instance."""
        count = min(self.accounts_at_once, len(eligible))
        batch = eligible[:count]
        # Move processed accounts to end
        for acc in batch:
            idx = self.accounts.index(acc)
            self.accounts.append(self.accounts.pop(idx))
        return batch

    # ─── Instance Switching ───────────────────────────────────

    def switch_to_account(self, account):
        """Switch LDPlayer to run specific account."""
        log.info(f"🔄 Switching to account: {account.name} (instance {account.instance_index})")
        account.status = AccountStatus.RUNNING

        # Get ADB port for this instance
        port = self.adb.ld_get_adb_port(account.instance_index)

        # If different instance, need to launch it
        current_instances = self.adb.ld_list_instances()
        target = None
        for inst in current_instances:
            if inst["index"] == account.instance_index:
                target = inst
                break

        if target and target["status"] != "running":
            log.info(f"Launching instance {account.instance_index}...")
            self.adb.ld_launch(account.instance_index)
            time.sleep(5)

        # Reconnect ADB to new port
        self.adb.port = port
        self.adb.device = f"{self.adb.host}:{port}"
        if not self.adb.connect(retries=5):
            account.status = AccountStatus.FAILED
            account.last_error = "ADB connection failed"
            self.save_accounts()
            return False

        account.last_run = datetime.now().isoformat()
        account.run_count += 1
        self.save_accounts()
        return True

    def mark_completed(self, account, tasks_done=0):
        """Mark account rotation as completed."""
        account.status = AccountStatus.COMPLETED
        account.tasks_completed += tasks_done
        account.error_count = 0
        self.save_accounts()
        log.info(f"✅ Account '{account.name}' completed ({tasks_done} tasks)")

    def mark_failed(self, account, error=""):
        """Mark account as failed."""
        account.status = AccountStatus.FAILED
        account.error_count += 1
        account.last_error = error
        self.save_accounts()
        log.error(f"❌ Account '{account.name}' failed: {error}")

    # ─── Stats ────────────────────────────────────────────────

    @property
    def stats(self):
        return {
            "total_accounts": len(self.accounts),
            "enabled": sum(1 for a in self.accounts if a.enabled),
            "running": sum(1 for a in self.accounts if a.status == AccountStatus.RUNNING),
            "completed": sum(1 for a in self.accounts if a.status == AccountStatus.COMPLETED),
            "failed": sum(1 for a in self.accounts if a.status == AccountStatus.FAILED),
            "rotation_count": self._rotation_count,
            "accounts_at_once": self.accounts_at_once,
        }

    def reset_daily_counts(self):
        """Reset daily run counts for all accounts."""
        for acc in self.accounts:
            acc.run_count = 0
            if acc.status in (AccountStatus.COMPLETED, AccountStatus.FAILED):
                acc.status = AccountStatus.IDLE
        self.save_accounts()
        log.info("Daily counts reset for all accounts")

