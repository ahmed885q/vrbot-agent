"""
VRBOT Agent — Progression Tasks
Chapter completion, Prosperity, Chief Hall upgrades, Expansion, Speedups.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.progression")


class ProsperityDailyTask(BaseTask):
    task_id = "prosperity_daily"
    task_name = "Prosperity Daily Tasks"
    priority = 2
    category = "progression"
    estimated_time = 25

    def run(self, overrides):
        """Complete daily prosperity tasks and collect rewards."""
        # Open prosperity panel
        if not self._safe_tap("btn_prosperity", timeout=5):
            if self._safe_tap("building_city_hall", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("tab_prosperity", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    return True
            else:
                return True

        self.human.delay("normal")

        # Collect completed tasks
        collected = 0
        for _ in range(10):
            if self.vision.tap_on("btn_prosperity_claim", wait=False, timeout=1):
                self.human.delay("fast")
                collected += 1
            else:
                break

        # Collect milestone chests
        for chest in ["prosperity_chest_1", "prosperity_chest_2", "prosperity_chest_3"]:
            if self.vision.tap_on(f"btn_{chest}", wait=False, timeout=1):
                self.human.delay("fast")
                collected += 1

        # Check prosperity level reward
        if self.vision.tap_on("btn_prosperity_level_reward", wait=False, timeout=2):
            self.human.delay("normal")
            collected += 1

        log.info(f"Prosperity: {collected} rewards collected")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class ChapterCompletionTask(BaseTask):
    task_id = "chapter_completion"
    task_name = "Chapter Completion (Through 17)"
    priority = 3
    category = "progression"
    estimated_time = 90

    def run(self, overrides):
        """Progress through chapter quests up to chapter 17."""
        max_chapter = overrides.get("max_chapter", 17)
        max_steps_per_cycle = overrides.get("max_steps", 5)

        # Open chapter/quest panel
        if not self._safe_tap("btn_chapter_quests", timeout=5):
            if self._safe_tap("btn_quests", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("tab_chapter", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    return True
            else:
                return True

        self.human.delay("normal")

        steps_done = 0
        for _ in range(max_steps_per_cycle):
            # Check current chapter (OCR)
            chapter_region = overrides.get("chapter_region", None)
            if chapter_region:
                current = self.vision.read_number(region=chapter_region)
                if current > max_chapter:
                    log.info(f"Already at chapter {current}, max is {max_chapter}")
                    break

            # Find "Go" button for current chapter task
            if self.vision.tap_on("btn_chapter_go", wait=False, timeout=3):
                self.human.delay("normal")

                # Handle different task types
                # Build task
                if self.vision.exists("btn_upgrade_confirm"):
                    if self._safe_tap("btn_upgrade_confirm", timeout=3):
                        self.human.delay("normal")
                        steps_done += 1

                # Battle task
                elif self.vision.exists("btn_chapter_battle"):
                    if self._safe_tap("btn_chapter_battle", timeout=5):
                        self.human.delay("slow")
                        self.vision.tap_on("btn_auto_battle", wait=False, timeout=3)
                        self.vision.wait_for("btn_battle_result", timeout=90)
                        self.human.delay("normal")
                        self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                        self.human.delay("normal")
                        steps_done += 1

                # Research task
                elif self.vision.exists("btn_research_start"):
                    if self._safe_tap("btn_research_start", timeout=3):
                        self.human.delay("normal")
                        steps_done += 1

                # Collect/claim task
                elif self.vision.tap_on("btn_chapter_claim", wait=False, timeout=3):
                    self.human.delay("normal")
                    steps_done += 1

            # Collect chapter completion rewards
            if self.vision.tap_on("btn_chapter_reward", wait=False, timeout=2):
                self.human.delay("normal")
                log.info("Chapter completion reward claimed!")

        log.info(f"Chapter progression: {steps_done} steps completed")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class UpgradeChiefHallTask(BaseTask):
    task_id = "upgrade_chief_hall"
    task_name = "Fast Chief Hall (Priority to 17)"
    priority = 1
    category = "progression"
    estimated_time = 30

    def run(self, overrides):
        """
        Priority Chief Hall upgrade strategy:
        - Only build what is needed for next CH level
        - Target CH17
        - Elite features cost extra (configurable)
        """
        target_ch = overrides.get("target_ch", 17)
        allow_elite = overrides.get("allow_elite", False)
        use_speedups = overrides.get("use_speedups", True)

        # Check current CH level
        if self._safe_tap("building_chief_hall", timeout=5):
            self.human.delay("normal")
        else:
            return True

        # Check if upgrade is available
        if self.vision.exists("btn_ch_upgrade_available"):
            if self._safe_tap("btn_ch_upgrade_available", timeout=3):
                self.human.delay("slow")

                # Check requirements
                if self.vision.exists("icon_requirements_met"):
                    # Confirm upgrade
                    if self._safe_tap("btn_upgrade_confirm", timeout=3):
                        self.human.delay("normal")
                        log.info("Chief Hall upgrade started!")

                        # Use speedups if enabled
                        if use_speedups:
                            self._use_construction_speedups()
                else:
                    # Requirements not met — check what's needed
                    log.info("CH upgrade requirements not met")

                    # Check if it needs elite building (costs extra)
                    if self.vision.exists("icon_elite_required") and not allow_elite:
                        log.info("Elite building required — skipping (allow_elite=False)")
                    else:
                        # Try to identify and build prerequisites
                        if self._safe_tap("btn_requirements_go", timeout=3):
                            self.human.delay("normal")
                            log.info("Navigated to prerequisite building")

        elif self.vision.exists("construction_in_progress"):
            log.info("Chief Hall already upgrading")
            if use_speedups:
                self._use_construction_speedups()

        self._safe_tap("btn_close_x", timeout=3)
        return True

    def _use_construction_speedups(self):
        """Apply speedups to current construction."""
        if self.vision.tap_on("btn_speedup_construction", wait=False, timeout=3):
            self.human.delay("fast")

            # Use free speedup first
            if self.vision.tap_on("btn_speedup_free", wait=False, timeout=2):
                self.human.delay("fast")
                log.info("Free construction speedup used")

            # Use regular speedups
            if self.vision.tap_on("btn_use_speedup_item", wait=False, timeout=2):
                self.human.delay("fast")
                if self._safe_tap("btn_confirm", timeout=3):
                    self.human.delay("normal")
                    log.info("Construction speedup item used")


class ExpansionBuildTask(BaseTask):
    task_id = "expansion_build"
    task_name = "Expansion Build (5 until Prosperity 4)"
    priority = 3
    category = "progression"
    estimated_time = 30

    def run(self, overrides):
        """
        Build expansion areas:
        - Build to level 5 per area
        - Continue until Prosperity level 4 reached
        """
        target_level = overrides.get("build_to_level", 5)
        target_prosperity = overrides.get("target_prosperity", 4)

        # Check current prosperity level
        prosperity_region = overrides.get("prosperity_region", None)
        if prosperity_region:
            current_prosperity = self.vision.read_number(region=prosperity_region)
            if current_prosperity >= target_prosperity:
                log.info(f"Prosperity {current_prosperity} >= target {target_prosperity}")
                return True

        # Find expansion areas
        expansions = self.vision.find_all("icon_expansion_available", threshold=0.70, max_results=5)

        built = 0
        for ex, ey, econf in expansions:
            self.adb.tap(ex, ey, offset=self.human.pixel_offset)
            self.human.delay("normal")

            # Check current level
            level_region = overrides.get("expansion_level_region", None)
            current_level = 0
            if level_region:
                current_level = self.vision.read_number(region=level_region)

            if current_level >= target_level:
                self._safe_tap("btn_close_x", timeout=2)
                continue

            # Build/Upgrade
            if self._safe_tap("btn_expand_build", timeout=3):
                self.human.delay("fast")

                if self._safe_tap("btn_confirm", timeout=3):
                    self.human.delay("normal")
                    built += 1
                    log.info(f"Expansion built (level {current_level + 1})")

        log.info(f"Expansion builds: {built}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class ConstructionSpeedupTask(BaseTask):
    task_id = "construction_speedups"
    task_name = "Use Construction & Regular Speedups"
    priority = 4
    category = "progression"
    estimated_time = 15

    def run(self, overrides):
        """
        Use speedups for active builds:
        - Construction speedups first (specific)
        - Regular speedups second (universal)
        """
        use_construction_type = overrides.get("use_construction_speedups", True)
        use_regular_type = overrides.get("use_regular_speedups", True)
        max_speedups = overrides.get("max_speedups", 5)

        # Find active construction
        if not self.vision.exists("icon_construction_active"):
            log.info("No active construction to speed up")
            return True

        if self._safe_tap("icon_construction_active", timeout=3):
            self.human.delay("fast")

        # Open speedup panel
        if not self._safe_tap("btn_speedup_panel", timeout=3):
            return True

        self.human.delay("normal")
        used = 0

        # Step 1: Construction-specific speedups
        if use_construction_type:
            for _ in range(max_speedups):
                if self.vision.tap_on("btn_speedup_construction_type", wait=False, timeout=1):
                    self.human.delay("fast")
                    used += 1
                else:
                    break

        # Step 2: Regular/universal speedups
        if use_regular_type and used < max_speedups:
            for _ in range(max_speedups - used):
                if self.vision.tap_on("btn_speedup_regular_type", wait=False, timeout=1):
                    self.human.delay("fast")
                    used += 1
                else:
                    break

        # Confirm
        if used > 0:
            self._safe_tap("btn_confirm", timeout=3)
            self.human.delay("normal")

        log.info(f"Speedups used: {used}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class GatherSuppliesTask(BaseTask):
    task_id = "gather_supplies"
    task_name = "Gather Supplies"
    priority = 3
    category = "progression"
    estimated_time = 20

    def run(self, overrides):
        """Gather supplies from various sources."""
        # Check supply depot
        if self._safe_tap("building_supply_depot", timeout=5):
            self.human.delay("normal")

            # Collect available supplies
            collected = 0
            for _ in range(5):
                if self.vision.tap_on("btn_collect_supply", wait=False, timeout=1):
                    self.human.delay("fast")
                    collected += 1
                else:
                    break

            # Request supplies
            if self.vision.tap_on("btn_request_supply", wait=False, timeout=3):
                self.human.delay("normal")
                log.info("Supply request sent")

            log.info(f"Supplies collected: {collected}")
            self._safe_tap("btn_close_x", timeout=3)

        return True


# ─── Export ───────────────────────────────────────────────────

PROGRESSION_TASKS = [
    ProsperityDailyTask,
    ChapterCompletionTask,
    UpgradeChiefHallTask,
    ExpansionBuildTask,
    ConstructionSpeedupTask,
    GatherSuppliesTask,
]

