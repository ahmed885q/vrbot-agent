"""
VRBOT Agent — Hero Tasks
Hall of Vallor summons, Hero XP, Squad Base training, Smithy Conquest.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.heroes")


class HallOfVallorTask(BaseTask):
    task_id = "hall_of_vallor"
    task_name = "Hall of Vallor Summons"
    priority = 2
    category = "hero"
    estimated_time = 40

    def run(self, overrides):
        """
        Smart summoning system:
        1. Use free daily summons (hero + card)
        2. Use summon stones when balanced
        3. Use guarantee when fully charged
        """
        use_free = overrides.get("use_free", True)
        use_stones = overrides.get("use_stones", True)
        use_guarantee = overrides.get("use_guarantee", True)
        min_stones_to_use = overrides.get("min_stones_balance", 10)

        # Open Hall of Vallor
        if not self._safe_tap("building_hall_of_vallor", timeout=5):
            if not self._safe_tap("btn_summon", timeout=5):
                return True

        self.human.delay("normal")
        summons = 0

        # --- Step 1: Free hero summon ---
        if use_free:
            if self.vision.exists("btn_free_hero_summon"):
                if self._safe_tap("btn_free_hero_summon", timeout=3):
                    self.human.delay("reading")
                    # Wait for animation
                    time.sleep(3)
                    self.vision.tap_on("btn_summon_continue", wait=False, timeout=5)
                    self.human.delay("normal")
                    summons += 1
                    log.info("Free hero summon used")

            # Free card summon
            if self.vision.exists("btn_free_card_summon"):
                if self._safe_tap("btn_free_card_summon", timeout=3):
                    self.human.delay("reading")
                    time.sleep(3)
                    self.vision.tap_on("btn_summon_continue", wait=False, timeout=5)
                    self.human.delay("normal")
                    summons += 1
                    log.info("Free card summon used")

        # --- Step 2: Use summon stones ---
        if use_stones:
            # Check stone balance via OCR
            stone_region = overrides.get("stone_count_region", None)
            stone_count = 0
            if stone_region:
                stone_count = self.vision.read_number(region=stone_region)

            if stone_count >= min_stones_to_use or not stone_region:
                # Try stone summon (single)
                if self.vision.exists("btn_stone_summon"):
                    if self._safe_tap("btn_stone_summon", timeout=3):
                        self.human.delay("reading")
                        time.sleep(3)
                        self.vision.tap_on("btn_summon_continue", wait=False, timeout=5)
                        self.human.delay("normal")
                        summons += 1
                        log.info("Stone summon used")

                # Try 10x summon if enough stones
                if stone_count >= min_stones_to_use * 10:
                    if self.vision.exists("btn_stone_summon_10x"):
                        if self._safe_tap("btn_stone_summon_10x", timeout=3):
                            self.human.delay("reading")
                            time.sleep(5)
                            self.vision.tap_on("btn_summon_continue", wait=False, timeout=5)
                            self.human.delay("normal")
                            summons += 10
                            log.info("10x stone summon used")

        # --- Step 3: Guarantee summon (when charged) ---
        if use_guarantee:
            if self.vision.exists("icon_guarantee_ready") or self.vision.exists("btn_guarantee_summon_ready"):
                if self._safe_tap("btn_guarantee_summon_ready", timeout=3):
                    self.human.delay("reading")
                    time.sleep(4)
                    self.vision.tap_on("btn_summon_continue", wait=False, timeout=5)
                    self.human.delay("normal")
                    summons += 1
                    log.info("🌟 Guarantee summon used!")

        log.info(f"Hall of Vallor: {summons} total summons")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class HeroXPChipsTask(BaseTask):
    task_id = "hero_xp_chips"
    task_name = "Use Hero XP Chips"
    priority = 5
    category = "hero"
    estimated_time = 25

    def run(self, overrides):
        """Use XP chips to level up heroes."""
        target_hero = overrides.get("target_hero", None)
        max_chips = overrides.get("max_chips", 50)

        # Open hero list
        if not self._safe_tap("btn_hero_list", timeout=5):
            return True

        self.human.delay("normal")

        # Select target hero or first available
        if target_hero:
            if not self._safe_tap(f"hero_{target_hero}", timeout=3):
                # Fallback to first hero
                self._safe_tap("hero_slot_1", timeout=3)
        else:
            self._safe_tap("hero_slot_1", timeout=3)

        self.human.delay("fast")

        # Open level up / XP panel
        if self._safe_tap("btn_hero_level_up", timeout=3):
            self.human.delay("fast")

            # Use XP chips
            chips_used = 0

            # Try "Use All" or set amount
            if self.vision.tap_on("btn_use_all_chips", wait=False, timeout=3):
                self.human.delay("normal")
                if self._safe_tap("btn_confirm", timeout=3):
                    self.human.delay("normal")
                    chips_used = max_chips
                    log.info(f"Used all XP chips on hero")
            else:
                # Manual chip usage
                for _ in range(min(max_chips, 20)):
                    if self.vision.tap_on("btn_use_xp_chip", wait=False, timeout=1):
                        self.human.micro_delay()
                        chips_used += 1
                    else:
                        break

                # Confirm
                if chips_used > 0:
                    self._safe_tap("btn_confirm", timeout=3)
                    self.human.delay("normal")

            log.info(f"XP chips used: {chips_used}")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class HeroSquadTrainingTask(BaseTask):
    task_id = "hero_squad_training"
    task_name = "Hero Training (Squad Base)"
    priority = 4
    category = "hero"
    estimated_time = 25

    def run(self, overrides):
        """Train heroes via Squad Base for XP and skills."""
        max_slots = overrides.get("max_training_slots", 3)

        # Open Squad Base
        if not self._safe_tap("building_squad_base", timeout=5):
            return True

        self.human.delay("normal")

        # Collect completed training
        collected = 0
        for _ in range(max_slots):
            if self.vision.tap_on("btn_training_collect", wait=False, timeout=2):
                self.human.delay("fast")
                collected += 1

        # Start new training in empty slots
        started = 0
        for _ in range(max_slots):
            slot = self.vision.find("slot_training_empty", threshold=0.75)
            if not slot:
                break

            x, y, conf = slot
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("fast")

            # Select hero for training
            if self._safe_tap("btn_select_hero_training", timeout=3):
                self.human.delay("fast")

                # Pick first available hero
                if self._safe_tap("hero_available_1", timeout=3):
                    self.human.delay("fast")

                    # Start training
                    if self._safe_tap("btn_start_training", timeout=3):
                        self.human.delay("normal")
                        started += 1

        log.info(f"Squad training: collected {collected}, started {started}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class SmithyConquestTask(BaseTask):
    task_id = "smithy_conquest"
    task_name = "Smithy Conquest"
    priority = 5
    category = "hero"
    estimated_time = 35

    def run(self, overrides):
        """Complete Smithy Conquest challenges for equipment."""
        max_battles = overrides.get("max_smithy_battles", 3)

        # Open Smithy
        if not self._safe_tap("building_smithy", timeout=5):
            return True

        self.human.delay("normal")

        # Go to conquest tab
        if not self._safe_tap("tab_conquest", timeout=3):
            self._safe_tap("btn_close_x", timeout=3)
            return True

        self.human.delay("normal")

        battles = 0
        for _ in range(max_battles):
            # Find available challenge
            if self._safe_tap("btn_smithy_challenge", timeout=5):
                self.human.delay("slow")

                # Auto battle
                self.vision.tap_on("btn_auto_battle", wait=False, timeout=3)

                # Wait for result
                result = self.vision.wait_for("btn_battle_result", timeout=60)
                if result:
                    self.human.delay("normal")
                    self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                    self.human.delay("normal")
                    battles += 1
            else:
                break

        # Collect any smithy materials
        self.vision.tap_on("btn_collect_materials", wait=False, timeout=3)
        self.human.delay("fast")

        log.info(f"Smithy conquest: {battles} battles")
        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Export ───────────────────────────────────────────────────

HERO_TASKS = [
    HallOfVallorTask,
    HeroXPChipsTask,
    HeroSquadTrainingTask,
    SmithyConquestTask,
]

