"""
VRBOT Agent — Event Tasks
Seasonal events, promotions, and special activities.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.events")


class CinderboneSoulburnTask(BaseTask):
    task_id = "cinderbone_soulburn"
    task_name = "Cinderbone Soulburn"
    priority = 3
    category = "events"
    estimated_time = 40

    def run(self, overrides):
        """Complete Cinderbone Soulburn event activities."""
        max_attempts = overrides.get("max_attempts", 5)

        # Find event icon or open events panel
        if not self.vision.tap_on("icon_cinderbone_event", wait=False, timeout=3):
            if self._safe_tap("btn_events", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("btn_cinderbone_event", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    log.info("Cinderbone event not active")
                    return True
            else:
                return True

        self.human.delay("normal")

        completed = 0
        for _ in range(max_attempts):
            # Find soulburn target
            if self._safe_tap("btn_cinderbone_attack", timeout=5):
                self.human.delay("normal")

                # Select troops
                if self._safe_tap("btn_march_confirm", timeout=5):
                    self.human.delay("slow")

                    # Wait for battle
                    self.vision.wait_for("btn_battle_result", timeout=90)
                    self.human.delay("normal")

                    # Collect reward
                    self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                    self.human.delay("normal")
                    completed += 1
            else:
                break

        # Collect event milestones
        for _ in range(5):
            if not self.vision.tap_on("btn_event_milestone_claim", wait=False, timeout=1):
                break
            self.human.delay("fast")

        log.info(f"Cinderbone Soulburn: {completed} battles")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class FestivalOfFlamesTask(BaseTask):
    task_id = "festival_of_flames"
    task_name = "Festival of Flames"
    priority = 3
    category = "events"
    estimated_time = 30

    def run(self, overrides):
        """Complete Festival of Flames event tasks and collect rewards."""
        # Open event
        if not self.vision.tap_on("icon_festival_flames", wait=False, timeout=3):
            if self._safe_tap("btn_events", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("btn_festival_flames", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    log.info("Festival of Flames not active")
                    return True
            else:
                return True

        self.human.delay("normal")

        # Collect all available rewards
        collected = 0
        for _ in range(15):
            if self.vision.tap_on("btn_festival_claim", wait=False, timeout=1):
                self.human.delay("fast")
                collected += 1
            else:
                break

        # Complete festival tasks
        tasks_done = 0
        for _ in range(5):
            if self.vision.tap_on("btn_festival_task_go", wait=False, timeout=2):
                self.human.delay("normal")
                tasks_done += 1

        log.info(f"Festival of Flames: {collected} rewards, {tasks_done} tasks")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class RebatePackEventTask(BaseTask):
    task_id = "rebate_pack_event"
    task_name = "Rebate Pack Event (New Account)"
    priority = 2
    category = "events"
    estimated_time = 15

    def run(self, overrides):
        """Claim rebate pack event rewards for new accounts."""
        # Open event
        if not self.vision.tap_on("icon_rebate_pack", wait=False, timeout=3):
            if self._safe_tap("btn_events", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("btn_rebate_pack", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    log.info("Rebate pack event not available")
                    return True
            else:
                return True

        self.human.delay("normal")

        # Claim all available rewards
        claimed = 0
        for _ in range(10):
            if self.vision.tap_on("btn_rebate_claim", wait=False, timeout=1):
                self.human.delay("fast")
                claimed += 1
            else:
                break

        log.info(f"Rebate pack: {claimed} rewards claimed")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class ConquerIslandTask(BaseTask):
    task_id = "conquer_island"
    task_name = "Conquer the Island (New Account)"
    priority = 2
    category = "events"
    estimated_time = 60

    def run(self, overrides):
        """Complete Conquer the Island tutorial/event for new accounts."""
        max_stages = overrides.get("max_stages", 5)

        # Open event
        if not self.vision.tap_on("icon_conquer_island", wait=False, timeout=3):
            if self._safe_tap("btn_events", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("btn_conquer_island", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    log.info("Conquer Island not available")
                    return True
            else:
                return True

        self.human.delay("normal")

        stages_done = 0
        for _ in range(max_stages):
            # Find next stage
            if self._safe_tap("btn_island_next_stage", timeout=5):
                self.human.delay("normal")

                # Battle or complete task
                if self.vision.exists("btn_island_battle"):
                    if self._safe_tap("btn_island_battle", timeout=5):
                        self.human.delay("slow")
                        self.vision.tap_on("btn_auto_battle", wait=False, timeout=3)
                        self.vision.wait_for("btn_battle_result", timeout=90)
                        self.human.delay("normal")
                        self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                        self.human.delay("normal")

                elif self.vision.exists("btn_island_claim"):
                    self._safe_tap("btn_island_claim", timeout=3)
                    self.human.delay("normal")

                stages_done += 1
            else:
                break

        log.info(f"Conquer Island: {stages_done} stages")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class DivinationTask(BaseTask):
    task_id = "divination"
    task_name = "Divination (Speed Ups Only)"
    priority = 5
    category = "events"
    estimated_time = 20

    def run(self, overrides):
        """
        Use divination system — ONLY claim speed up rewards.
        Skip other reward types to save resources.
        """
        max_divinations = overrides.get("max_divinations", 5)
        only_speedups = overrides.get("only_speedups", True)

        # Open divination
        if not self._safe_tap("btn_divination", timeout=5):
            if self._safe_tap("building_oracle", timeout=5):
                self.human.delay("fast")
            else:
                return True

        self.human.delay("normal")

        used = 0
        for _ in range(max_divinations):
            # Check if free divination available
            if not self.vision.exists("btn_free_divination") and not self.vision.exists("btn_divination_use"):
                break

            # Use divination
            if self.vision.tap_on("btn_free_divination", wait=False, timeout=2):
                self.human.delay("reading")
                time.sleep(2)  # Animation
            elif self.vision.tap_on("btn_divination_use", wait=False, timeout=2):
                self.human.delay("reading")
                time.sleep(2)
            else:
                break

            # Check result — only accept speedups
            if only_speedups:
                if self.vision.exists("icon_speedup_reward"):
                    if self._safe_tap("btn_accept_divination", timeout=3):
                        self.human.delay("normal")
                        used += 1
                        log.info("Divination: speed up reward accepted")
                else:
                    # Skip non-speedup result
                    if self._safe_tap("btn_skip_divination", timeout=3):
                        self.human.delay("fast")
                        log.debug("Divination: non-speedup skipped")
            else:
                if self._safe_tap("btn_accept_divination", timeout=3):
                    self.human.delay("normal")
                    used += 1

        log.info(f"Divination: {used} speed ups claimed")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class RedeemPromoCodesTask(BaseTask):
    task_id = "redeem_promo_codes"
    task_name = "Redeem Promotional Codes"
    priority = 6
    category = "events"
    estimated_time = 20

    def run(self, overrides):
        """Redeem promotional/gift codes."""
        codes = overrides.get("codes", [])
        if not codes:
            log.info("No promo codes configured")
            return True

        # Open settings or redemption menu
        if not self._safe_tap("btn_settings", timeout=5):
            return True

        self.human.delay("normal")

        if not self._safe_tap("btn_redeem_code", timeout=3):
            self._safe_tap("btn_close_x", timeout=3)
            return True

        self.human.delay("normal")

        redeemed = 0
        for code in codes:
            # Clear input field
            if self._safe_tap("input_code_field", timeout=3):
                self.human.delay("fast")

                # Type code via ADB
                self.adb._shell(f'input text "{code}"')
                self.human.delay("fast")

                # Submit
                if self._safe_tap("btn_redeem_submit", timeout=3):
                    self.human.delay("normal")

                    # Check result
                    if self.vision.exists("icon_redeem_success"):
                        redeemed += 1
                        log.info(f"Redeemed code: {code[:4]}***")
                    elif self.vision.exists("icon_redeem_used"):
                        log.info(f"Code already used: {code[:4]}***")

                    # Dismiss result dialog
                    self.vision.tap_on("btn_confirm", wait=False, timeout=3)
                    self.human.delay("fast")

        log.info(f"Promo codes redeemed: {redeemed}/{len(codes)}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Export ───────────────────────────────────────────────────

EVENT_TASKS = [
    CinderboneSoulburnTask,
    FestivalOfFlamesTask,
    RebatePackEventTask,
    ConquerIslandTask,
    DivinationTask,
    RedeemPromoCodesTask,
]

