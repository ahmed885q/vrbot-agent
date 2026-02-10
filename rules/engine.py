"""
VRBOT Agent — Rules Engine
Defines per-account rules for task execution.
Inspired by GnBots' account rules system.
"""
import json
import os
import logging
from datetime import datetime

log = logging.getLogger("vrbot.rules")

RULES_FILE = "config/rules.json"


class Rule:
    """Single rule for an account/task combination."""

    def __init__(self, data):
        self.account_id = data.get("account_id", "*")  # * = all accounts
        self.task_id = data.get("task_id", "*")         # * = all tasks
        self.enabled = data.get("enabled", True)
        self.conditions = data.get("conditions", {})
        self.overrides = data.get("overrides", {})

    def applies_to(self, account_id, task_id):
        """Check if this rule applies to given account/task."""
        acc_match = self.account_id in ("*", account_id)
        task_match = self.task_id in ("*", task_id)
        return acc_match and task_match

    def evaluate(self):
        """Evaluate if rule conditions are met."""
        if not self.enabled:
            return False

        now = datetime.now()

        # Day of week check
        if "days" in self.conditions:
            day = now.strftime("%a").lower()
            if day not in [d.lower() for d in self.conditions["days"]]:
                return False

        # Time window check
        if "time_start" in self.conditions:
            if now.hour < self.conditions["time_start"]:
                return False
        if "time_end" in self.conditions:
            if now.hour >= self.conditions["time_end"]:
                return False

        # Frequency check (run every N hours)
        if "frequency_hours" in self.conditions:
            # This needs last_run tracking from task runner
            pass

        return True

    def to_dict(self):
        return {
            "account_id": self.account_id,
            "task_id": self.task_id,
            "enabled": self.enabled,
            "conditions": self.conditions,
            "overrides": self.overrides,
        }


class RulesEngine:
    """
    Manages rules that control which tasks run, when, and how.

    Rule types:
    - Skip: Don't run task X on account Y
    - Schedule: Run task only on specific days/times
    - Override: Change task parameters per account
    - Frequency: Run task every N hours
    """

    def __init__(self):
        self.rules = []
        self.load()

    def load(self):
        """Load rules from file."""
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, "r") as f:
                data = json.load(f)
            self.rules = [Rule(r) for r in data.get("rules", [])]
            log.info(f"Loaded {len(self.rules)} rules")
        else:
            self.rules = []
            self.save()

    def save(self):
        """Save rules to file."""
        os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
        data = {"rules": [r.to_dict() for r in self.rules]}
        with open(RULES_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def add_rule(self, account_id="*", task_id="*", enabled=True, conditions=None, overrides=None):
        """Add a new rule."""
        rule = Rule({
            "account_id": account_id,
            "task_id": task_id,
            "enabled": enabled,
            "conditions": conditions or {},
            "overrides": overrides or {},
        })
        self.rules.append(rule)
        self.save()
        return rule

    def should_run_task(self, account_id, task_id):
        """Check if a task should run for an account."""
        for rule in self.rules:
            if rule.applies_to(account_id, task_id):
                if not rule.enabled:
                    log.debug(f"Rule disabled task '{task_id}' for account '{account_id}'")
                    return False
                if not rule.evaluate():
                    log.debug(f"Rule conditions not met for '{task_id}' on '{account_id}'")
                    return False
        return True

    def get_task_overrides(self, account_id, task_id):
        """Get parameter overrides for a task/account combo."""
        overrides = {}
        for rule in self.rules:
            if rule.applies_to(account_id, task_id) and rule.overrides:
                overrides.update(rule.overrides)
        return overrides

    def get_rules_for_account(self, account_id):
        """Get all rules applicable to an account."""
        return [r for r in self.rules if r.applies_to(account_id, "*")]

    def remove_rule(self, index):
        """Remove rule by index."""
        if 0 <= index < len(self.rules):
            self.rules.pop(index)
            self.save()

    # ─── Preset Rules ─────────────────────────────────────────

    def add_skip_task(self, account_id, task_id):
        """Skip a specific task for an account."""
        return self.add_rule(account_id, task_id, enabled=False)

    def add_schedule(self, account_id, task_id, days=None, time_start=None, time_end=None):
        """Schedule task to run only at specific times."""
        conditions = {}
        if days:
            conditions["days"] = days
        if time_start is not None:
            conditions["time_start"] = time_start
        if time_end is not None:
            conditions["time_end"] = time_end
        return self.add_rule(account_id, task_id, conditions=conditions)

    def add_weekend_only(self, account_id, task_id="*"):
        """Run task only on weekends."""
        return self.add_schedule(account_id, task_id, days=["sat", "sun"])

