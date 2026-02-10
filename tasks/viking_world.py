"""
VRBOT Agent — Viking World Tasks
Open world activities: Reclaim Midgard, Niflung, Monster Caves, City Cleanup.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.world")


class ClearCityForestTask(BaseTask):
    task_id = "clear_city_forest"
    task_name = "Clear City Forest & Monster Caves"
    priority = 4
    category = "world"
    estimated_time = 60

    def run(self, overrides):
        """Clear forest obstacles around city and complete monster caves."""
        max_clears = overrides.get("max_clears", 5)
        cleared = 0

        # --- Part 1: Clear forest obstacles ---
        for _ in range(max_clears):
            # Find clearable obstacles (trees, rocks, ruins)
            obstacle = self.vision.find("icon_obstacle_clearable", threshold=0.75)
            if not obstacle:
                break

            x, y, conf = obstacle
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("normal")

            # Tap clear/remove
            if self.vision.tap_on("btn_clear_obstacle", wait=False, timeout=3):
                self.human.delay("fast")

                # Confirm if needed
                self.vision.tap_on("btn_confirm", wait=False, timeout=2)
                self.human.delay("normal")
                cleared += 1

        log.info(f"Cleared {cleared} forest obstacles")

        # --- Part 2: Monster caves ---
        cave_attempts = overrides.get("cave_attempts", 3)
        caves_done = 0

        for _ in range(cave_attempts):
            cave = self.vision.find("icon_monster_cave", threshold=0.75)
            if not cave:
                break

            x, y, conf = cave
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("normal")

            # Enter cave
            if self._safe_tap("btn_enter_cave", timeout=5):
                self.human.delay("slow")

                # Auto battle through cave
                if self.vision.tap_on("btn_auto_battle", wait=False, timeout=3):
                    pass

                # Wait for completion
                result = self.vision.wait_for("btn_cave_complete", timeout=90)
                if result:
                    self.human.delay("normal")
                    self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                    self.human.delay("normal")
                    caves_done += 1

        log.info(f"Monster caves completed: {caves_done}")
        return True


class ReclaimMidgardTask(BaseTask):
    task_id = "reclaim_midgard"
    task_name = "Reclaim Midgard"
    priority = 3
    category = "world"
    estimated_time = 120

    def run(self, overrides):
        """
        Full Midgard reclaim cycle:
        1. Battle monsters
        2. Unlock sentry towers
        3. Unlock sacrificial stones
        4. Unlock villages
        5. Unlock Odin statue
        """
        max_monster_battles = overrides.get("max_monster_battles", 5)
        auto_unlock = overrides.get("auto_unlock", True)

        # Open world map
        if not self._safe_tap("btn_world_map", timeout=5):
            return True
        self.human.delay("normal")

        # --- Step 1: Battle fog monsters ---
        monsters_killed = self._battle_midgard_monsters(max_monster_battles)
        log.info(f"Midgard monsters killed: {monsters_killed}")

        if not auto_unlock:
            self._safe_tap("btn_main_city", timeout=5)
            return True

        # --- Step 2: Unlock sentry towers ---
        towers = self._unlock_structures("icon_sentry_tower_locked", "btn_unlock_tower")
        log.info(f"Sentry towers unlocked: {towers}")

        # --- Step 3: Unlock sacrificial stones ---
        stones = self._unlock_structures("icon_sacrificial_stone_locked", "btn_unlock_stone")
        log.info(f"Sacrificial stones unlocked: {stones}")

        # --- Step 4: Unlock villages ---
        villages = self._unlock_structures("icon_village_locked", "btn_unlock_village")
        log.info(f"Villages unlocked: {villages}")

        # --- Step 5: Unlock Odin statue ---
        if self.vision.exists("icon_odin_statue_locked"):
            if self._safe_tap("icon_odin_statue_locked", timeout=5):
                self.human.delay("normal")
                if self._safe_tap("btn_unlock_odin", timeout=5):
                    self.human.delay("slow")
                    log.info("Odin statue unlocked!")

        # Return to city
        self._safe_tap("btn_main_city", timeout=5)
        return True

    def _battle_midgard_monsters(self, max_battles):
        """Battle monsters in fog areas."""
        killed = 0
        for _ in range(max_battles):
            monster = self.vision.find("icon_midgard_monster", threshold=0.70)
            if not monster:
                break

            x, y, conf = monster
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("normal")

            # Attack
            if self._safe_tap("btn_attack_monster", timeout=5):
                self.human.delay("slow")

                # Select troops
                if self._safe_tap("btn_march_confirm", timeout=5):
                    self.human.delay("normal")

                    # Wait for battle result
                    self.vision.wait_for("btn_battle_result", timeout=60)
                    self.human.delay("normal")
                    self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                    self.human.delay("normal")
                    killed += 1

        return killed

    def _unlock_structures(self, locked_icon, unlock_btn):
        """Unlock structures (towers, stones, villages)."""
        unlocked = 0
        for _ in range(10):
            structure = self.vision.find(locked_icon, threshold=0.75)
            if not structure:
                break

            x, y, conf = structure
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("normal")

            if self.vision.tap_on(unlock_btn, wait=False, timeout=5):
                self.human.delay("fast")
                self.vision.tap_on("btn_confirm", wait=False, timeout=3)
                self.human.delay("normal")
                unlocked += 1

        return unlocked


class NiflungHuntingTask(BaseTask):
    task_id = "niflung_hunting"
    task_name = "Niflung Hunting"
    priority = 3
    category = "world"
    estimated_time = 45

    def run(self, overrides):
        """Hunt Niflung enemies on the world map."""
        max_hunts = overrides.get("max_hunts", 5)
        target_level = overrides.get("target_level", None)

        # Open world map
        if not self._safe_tap("btn_world_map", timeout=5):
            return True
        self.human.delay("normal")

        # Search for Niflung
        if self._safe_tap("btn_search", timeout=5):
            self.human.delay("fast")

            if self._safe_tap("btn_search_niflung", timeout=3):
                self.human.delay("fast")

                # Select level if specified
                if target_level:
                    if self._safe_tap(f"btn_niflung_level_{target_level}", timeout=3):
                        self.human.delay("fast")

                # Search
                if self._safe_tap("btn_search_confirm", timeout=3):
                    self.human.delay("normal")

        hunts = 0
        for _ in range(max_hunts):
            # Tap on found Niflung
            if self._safe_tap("btn_attack_niflung", timeout=5):
                self.human.delay("normal")

                # Confirm march
                if self._safe_tap("btn_march_confirm", timeout=5):
                    self.human.delay("slow")

                    # Wait for battle
                    self.vision.wait_for("btn_battle_result", timeout=60)
                    self.human.delay("normal")
                    self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                    self.human.delay("normal")
                    hunts += 1

                    # Search next
                    if hunts < max_hunts:
                        self._safe_tap("btn_search_next", timeout=3)
                        self.human.delay("normal")

        log.info(f"Niflung hunts completed: {hunts}")
        self._safe_tap("btn_main_city", timeout=5)
        return True


class LeidolfInHidingTask(BaseTask):
    task_id = "leidolf_in_hiding"
    task_name = "Leidolf in Hiding Event"
    priority = 4
    category = "world"
    estimated_time = 30

    def run(self, overrides):
        """Find and battle Leidolf in Hiding event targets."""
        max_attempts = overrides.get("max_attempts", 3)

        # Open events or find Leidolf icon
        if self.vision.tap_on("icon_leidolf_event", wait=False, timeout=3):
            self.human.delay("normal")
        elif self._safe_tap("btn_events", timeout=5):
            self.human.delay("fast")
            if not self._safe_tap("btn_leidolf_event", timeout=3):
                self._safe_tap("btn_close_x", timeout=3)
                log.info("Leidolf event not active")
                return True
            self.human.delay("normal")

        found = 0
        for _ in range(max_attempts):
            # Search for Leidolf
            if self._safe_tap("btn_search_leidolf", timeout=5):
                self.human.delay("normal")

                # Attack
                if self._safe_tap("btn_attack", timeout=5):
                    self.human.delay("normal")

                    if self._safe_tap("btn_march_confirm", timeout=5):
                        self.human.delay("slow")

                        self.vision.wait_for("btn_battle_result", timeout=60)
                        self.human.delay("normal")
                        self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                        self.human.delay("normal")
                        found += 1

        log.info(f"Leidolf battles: {found}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Export ───────────────────────────────────────────────────

WORLD_TASKS = [
    ClearCityForestTask,
    ReclaimMidgardTask,
    NiflungHuntingTask,
    LeidolfInHidingTask,
]

