"""
VRBOT Agent — Alliance Tasks
Alliance/Tribe management tasks for Viking Rise.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.alliance")


class DonateTechnologyTask(BaseTask):
    task_id = "donate_technology"
    task_name = "Donate Alliance Technology"
    priority = 3
    category = "alliance"
    estimated_time = 25

    def run(self, overrides):
        """Donate resources to alliance technology research."""
        donate_type = overrides.get("donate_type", "resources")  # resources or gems
        max_donations = overrides.get("max_donations", 10)

        # Open alliance/tribe menu
        if not self._safe_tap("btn_tribe", timeout=5):
            return True

        self.human.delay("normal")

        # Go to technology tab
        if not self._safe_tap("tab_technology", timeout=3):
            self._safe_tap("btn_close_x", timeout=3)
            return True

        self.human.delay("normal")

        # Select active research
        if self.vision.tap_on("tech_active_research", wait=False, timeout=3):
            self.human.delay("fast")

        donated = 0
        for _ in range(max_donations):
            # Tap donate button (resources or gems)
            btn = "btn_donate_gems" if donate_type == "gems" else "btn_donate"
            if self.vision.tap_on(btn, wait=False, timeout=2):
                self.human.delay("fast")
                donated += 1
            else:
                break

        log.info(f"Donated {donated} times to alliance tech")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class AllianceWarRegisterTask(BaseTask):
    task_id = "alliance_war_register"
    task_name = "Alliance War Register"
    priority = 2
    category = "alliance"
    estimated_time = 20

    def run(self, overrides):
        """Register for alliance war / kingdom vs kingdom events."""
        # Open alliance menu
        if not self._safe_tap("btn_tribe", timeout=5):
            return True

        self.human.delay("normal")

        # Go to war tab
        if not self._safe_tap("tab_war", timeout=3):
            self._safe_tap("btn_close_x", timeout=3)
            return True

        self.human.delay("normal")

        # Check if registration is open
        if self.vision.exists("btn_register_war"):
            if self._safe_tap("btn_register_war", timeout=3):
                self.human.delay("normal")

                # Confirm registration
                if self._safe_tap("btn_confirm", timeout=3):
                    self.human.delay("normal")
                    log.info("Registered for alliance war")
        else:
            log.info("Alliance war registration not available")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class HonorWallTask(BaseTask):
    task_id = "honor_wall"
    task_name = "Honor Wall Contribution"
    priority = 5
    category = "alliance"
    estimated_time = 15

    def run(self, overrides):
        """Contribute to alliance honor wall."""
        # Open alliance
        if not self._safe_tap("btn_tribe", timeout=5):
            return True

        self.human.delay("normal")

        # Go to honor wall
        if not self._safe_tap("tab_honor_wall", timeout=3):
            self._safe_tap("btn_close_x", timeout=3)
            return True

        self.human.delay("normal")

        # Contribute
        if self.vision.tap_on("btn_contribute", wait=False, timeout=3):
            self.human.delay("fast")

            # Max contribution
            if self._safe_tap("btn_max_amount", timeout=2):
                self.human.delay("fast")

            # Confirm
            if self._safe_tap("btn_confirm", timeout=3):
                self.human.delay("normal")
                log.info("Contributed to honor wall")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class AllianceBankTask(BaseTask):
    task_id = "alliance_bank"
    task_name = "Alliance Bank Deposit"
    priority = 5
    category = "alliance"
    estimated_time = 20

    def run(self, overrides):
        """Deposit resources to alliance bank."""
        deposit_amount = overrides.get("deposit_percent", 10)  # % of resources

        # Open alliance
        if not self._safe_tap("btn_tribe", timeout=5):
            return True

        self.human.delay("normal")

        # Open bank
        if not self._safe_tap("tab_bank", timeout=3):
            self._safe_tap("btn_close_x", timeout=3)
            return True

        self.human.delay("normal")

        # Deposit
        if self.vision.tap_on("btn_deposit", wait=False, timeout=3):
            self.human.delay("fast")

            # Set amount
            if self._safe_tap("btn_set_amount", timeout=2):
                self.human.delay("fast")

            # Confirm deposit
            if self._safe_tap("btn_confirm_deposit", timeout=3):
                self.human.delay("normal")
                log.info("Deposited to alliance bank")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class TerritoryBattleTask(BaseTask):
    task_id = "territory_battle"
    task_name = "Territory Battle"
    priority = 3
    category = "alliance"
    estimated_time = 45

    def run(self, overrides):
        """Participate in alliance territory battles."""
        max_marches = overrides.get("max_marches", 2)

        # Open alliance
        if not self._safe_tap("btn_tribe", timeout=5):
            return True

        self.human.delay("normal")

        # Territory tab
        if not self._safe_tap("tab_territory", timeout=3):
            self._safe_tap("btn_close_x", timeout=3)
            return True

        self.human.delay("normal")

        # Check if territory battle is active
        if not self.vision.exists("territory_battle_active"):
            log.info("No active territory battle")
            self._safe_tap("btn_close_x", timeout=3)
            return True

        marches_sent = 0
        for _ in range(max_marches):
            # Find available territory to attack/defend
            if self.vision.tap_on("btn_territory_action", wait=False, timeout=3):
                self.human.delay("normal")

                # Select troops
                if self._safe_tap("btn_select_troops", timeout=3):
                    self.human.delay("fast")

                # March
                if self._safe_tap("btn_march_confirm", timeout=3):
                    self.human.delay("normal")
                    marches_sent += 1
                    log.info(f"Territory march #{marches_sent} sent")

        self._safe_tap("btn_close_x", timeout=3)
        log.info(f"Territory battle: {marches_sent} marches sent")
        return True


class AllianceBossTask(BaseTask):
    task_id = "alliance_boss"
    task_name = "Alliance Boss Battle"
    priority = 4
    category = "alliance"
    estimated_time = 40

    def run(self, overrides):
        """Join alliance boss battle."""
        # Open alliance
        if not self._safe_tap("btn_tribe", timeout=5):
            return True

        self.human.delay("normal")

        # Find boss event
        if not self._safe_tap("btn_alliance_boss", timeout=3):
            log.info("Alliance boss not available")
            self._safe_tap("btn_close_x", timeout=3)
            return True

        self.human.delay("normal")

        # Check if boss is active
        if self.vision.exists("boss_active"):
            # Join battle
            if self._safe_tap("btn_join_battle", timeout=5):
                self.human.delay("slow")

                # Auto battle
                if self.vision.tap_on("btn_auto_battle", wait=False, timeout=3):
                    self.human.delay("reading")

                # Wait for battle to finish
                self.vision.wait_for("btn_battle_result", timeout=120)
                self.human.delay("normal")

                # Collect rewards
                if self.vision.tap_on("btn_collect_reward", wait=False, timeout=5):
                    self.human.delay("normal")
                    log.info("Alliance boss battle completed")

        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Export ───────────────────────────────────────────────────

ALLIANCE_TASKS = [
    DonateTechnologyTask,
    AllianceWarRegisterTask,
    HonorWallTask,
    AllianceBankTask,
    TerritoryBattleTask,
    AllianceBossTask,
]

