"""
VRBOT Agent — Task System
Base task class and Viking Rise specific tasks.
"""
import time
import logging
from abc import ABC, abstractmethod
from enum import Enum

log = logging.getLogger("vrbot.tasks")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class BaseTask(ABC):
    """Base class for all Viking Rise automation tasks."""

    task_id = "base"
    task_name = "Base Task"
    priority = 5          # 1=highest, 10=lowest
    estimated_time = 30   # seconds
    category = "general"
    requires_main_screen = True

    def __init__(self, vision, adb, humanizer):
        self.vision = vision
        self.adb = adb
        self.human = humanizer
        self.status = TaskStatus.PENDING
        self.error = None
        self.start_time = None
        self.end_time = None

    def execute(self, overrides=None):
        """Run the task with error handling."""
        self.status = TaskStatus.RUNNING
        self.start_time = time.time()
        self.error = None

        try:
            log.info(f"▶ Starting: {self.task_name}")

            if self.requires_main_screen:
                self._ensure_main_screen()

            result = self.run(overrides or {})

            if result:
                self.status = TaskStatus.SUCCESS
                log.info(f"✅ Completed: {self.task_name}")
            else:
                self.status = TaskStatus.FAILED
                log.warning(f"⚠️ Failed: {self.task_name}")

        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error = str(e)
            log.error(f"❌ Error in {self.task_name}: {e}")

        self.end_time = time.time()
        return self.status == TaskStatus.SUCCESS

    @abstractmethod
    def run(self, overrides):
        """Implement task logic. Return True on success."""
        pass

    def _ensure_main_screen(self, max_tries=5):
        """Navigate back to main city screen."""
        for _ in range(max_tries):
            # Check for city screen markers (real templates)
            if (self.vision.exists("btn_compass", threshold=0.80) or
                self.vision.exists("btn_mail", threshold=0.80) or
                self.vision.exists("btn_shield", threshold=0.80)):
                return True
            # Try pressing close buttons
            if self.vision.tap_on("btn_close_x", wait=False):
                self.human.delay("fast")
                continue
            if self.vision.tap_on("btn_popup_close_x", wait=False):
                self.human.delay("fast")
                continue
            if self.vision.tap_on("btn_back", wait=False):
                self.human.delay("fast")
                continue
            self.adb.go_back()
            self.human.delay("fast")
        return False

    def _safe_tap(self, template, delay="normal", timeout=10):
        """Tap template with human delay."""
        result = self.vision.tap_on(template, offset=self.human.pixel_offset, timeout=timeout)
        if result:
            self.human.delay(delay)
        return result

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return round(self.end_time - self.start_time, 1)
        return 0

    @property
    def info(self):
        return {
            "task_id": self.task_id,
            "name": self.task_name,
            "status": self.status.value,
            "priority": self.priority,
            "duration": self.duration,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════
# VIKING RISE TASKS
# ═══════════════════════════════════════════════════════════════


class CollectResourcesTask(BaseTask):
    task_id = "collect_resources"
    task_name = "Collect Resources"
    priority = 1
    category = "resources"
    estimated_time = 15

    def run(self, overrides):
        """Collect all available resources from buildings."""
        collected = 0

        # Find all collectible resource icons on screen
        resources = self.vision.find_all("icon_resource_ready", threshold=0.75)
        for x, y, conf in resources:
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("fast")
            collected += 1

        # Also check for food, wood, stone, iron icons
        for res_type in ["food_ready", "wood_ready", "stone_ready", "iron_ready"]:
            if self.vision.tap_on(res_type, wait=False):
                self.human.delay("fast")
                collected += 1

        log.info(f"Collected {collected} resources")
        return collected > 0 or True  # Success even if nothing to collect


class BuildUpgradeTask(BaseTask):
    task_id = "build_upgrade"
    task_name = "Build / Upgrade"
    priority = 2
    category = "construction"
    estimated_time = 30

    def run(self, overrides):
        """Check and start building upgrades."""
        # Check if builder is free
        if self.vision.exists("builder_busy"):
            log.info("Builder is busy")
            return True

        # Look for upgrade recommendations
        if self.vision.tap_on("btn_upgrade_recommend", wait=False):
            self.human.delay("slow")

            # Confirm upgrade
            if self.vision.tap_on("btn_upgrade_confirm", timeout=5):
                self.human.delay("normal")
                log.info("Started building upgrade")
                return True

        return True


class TrainTroopsTask(BaseTask):
    task_id = "train_troops"
    task_name = "Train Troops"
    priority = 3
    category = "military"
    estimated_time = 45

    def run(self, overrides):
        """Train troops in barracks."""
        troop_type = overrides.get("troop_type", "infantry")
        buildings = {
            "infantry": "barracks",
            "cavalry": "stable",
            "ranged": "archery_range",
        }

        building = buildings.get(troop_type, "barracks")

        # Find and tap the training building
        if not self._safe_tap(f"building_{building}", timeout=5):
            log.info(f"Cannot find {building}")
            return True

        # Tap train button
        if self.vision.tap_on("btn_train", timeout=5):
            self.human.delay("slow")

            # Select max troops
            if self.vision.tap_on("btn_train_max", wait=False):
                self.human.delay("fast")

            # Confirm
            if self.vision.tap_on("btn_train_confirm", timeout=5):
                self.human.delay("normal")
                log.info(f"Started training {troop_type}")
                return True

        return True


class GatherResourcesTask(BaseTask):
    task_id = "gather_resources"
    task_name = "Send Gatherers"
    priority = 3
    category = "resources"
    estimated_time = 60

    TILE_MAP = {
        "food":  "tile_farm",
        "wood":  "tile_sawmill",
        "stone": "tile_quarry",
        "gold":  "tile_gold_mine",
    }

    def run(self, overrides):
        """Send troops to gather resources on the map."""
        resource = overrides.get("resource_type", "food")
        tile_template = self.TILE_MAP.get(resource, "tile_farm")

        # Step 1: Go to world map via compass
        if not self.vision.exists("btn_worldmap_search", threshold=0.75):
            # Not on world map — tap compass from city
            if not self._safe_tap("btn_compass", timeout=5):
                log.warning("Cannot open world map")
                return True
            self.human.delay("normal")

        # Step 2: Open search panel
        if self._safe_tap("btn_worldmap_search", timeout=5):
            self.human.delay("fast")

            # Step 3: Select resource tile type
            if self._safe_tap(tile_template, timeout=5):
                self.human.delay("fast")

                # Step 4: Tap Search button
                if (self._safe_tap("btn_search_blue", timeout=5) or
                    self._safe_tap("btn_search_conquest", timeout=5)):
                    self.human.delay("slow")

                    # Step 5: Tap the resource tile on map
                    self.adb.tap(640, 400, offset=20)
                    self.human.delay("normal")

                    # Step 6: Tap Gather button on popup
                    if self._safe_tap("btn_gather", timeout=10):
                        self.human.delay("normal")

                        # Step 7: Confirm march (tap green/blue confirm button)
                        time.sleep(1)
                        # Try common confirm buttons
                        if (self._safe_tap("btn_ok_green", timeout=5) or
                            self._safe_tap("btn_claim_green", timeout=3)):
                            log.info(f"✅ Sent gatherers for {resource}")
                            self.human.delay("normal")
                            return True
                        else:
                            # Try tapping bottom-right where march button usually is
                            self.adb.tap(1100, 650, offset=10)
                            log.info(f"Sent gatherers for {resource} (alt confirm)")
                            return True

        # Go back to city
        self._ensure_main_screen()
        return True


class CollectMailTask(BaseTask):
    task_id = "collect_mail"
    task_name = "Collect Mail Rewards"
    priority = 4
    category = "daily"
    estimated_time = 20

    def run(self, overrides):
        """Open mail and claim all rewards."""
        if not self._safe_tap("btn_mail", timeout=5):
            return True

        self.human.delay("normal")

        # Try "Read & Claim All" button
        if self.vision.tap_on("btn_read_claim_all", timeout=5):
            self.human.delay("slow")
            log.info("Claimed all mail rewards")
        else:
            # Try individual claim buttons
            if self.vision.tap_on("btn_claim_green", timeout=3):
                self.human.delay("normal")
                log.info("Claimed mail reward")

        # Close mail
        self._safe_tap("btn_close_x", timeout=3)
        return True


class DailyQuestsTask(BaseTask):
    task_id = "daily_quests"
    task_name = "Daily Quests"
    priority = 2
    category = "daily"
    estimated_time = 30

    def run(self, overrides):
        """Collect daily quest rewards."""
        if not self._safe_tap("btn_quests", timeout=5):
            return True

        self.human.delay("normal")

        # Switch to daily tab
        self._safe_tap("tab_daily_quests", timeout=3)
        self.human.delay("fast")

        # Collect available rewards (look for green Claim buttons)
        collected = 0
        for _ in range(10):
            if self.vision.tap_on("btn_quest_claim", wait=False):
                self.human.delay("fast")
                collected += 1
                time.sleep(1)  # Wait for claim animation
            else:
                break

        # Check for chest rewards at top
        for chest in ["icon_chest_20", "icon_chest_40", "icon_chest_60", "icon_chest_80", "icon_chest_100"]:
            if self.vision.tap_on(chest, wait=False, threshold=0.70):
                self.human.delay("fast")
                # Claim chest
                if self.vision.tap_on("btn_claim_green", timeout=3):
                    collected += 1
                    self.human.delay("fast")

        log.info(f"Collected {collected} quest rewards")

        # Close
        self._safe_tap("btn_close_x", timeout=3)
        return True


class AllianceHelpTask(BaseTask):
    task_id = "alliance_help"
    task_name = "Tribe Assist"
    priority = 4
    category = "alliance"
    estimated_time = 10

    def run(self, overrides):
        """Help tribe members (Tribe Assist)."""
        # Open tribe screen
        if not self._safe_tap("btn_alliance", timeout=5):
            return True

        self.human.delay("normal")

        # Tap Assist button
        if self._safe_tap("btn_tribe_assist", timeout=5):
            self.human.delay("normal")
            log.info("Opened Tribe Assist")

            # The assist screen auto-helps when available
            # Just wait and close
            time.sleep(2)
            self._safe_tap("btn_close_x", timeout=3)
        
        self._ensure_main_screen()
        return True


class UseSpeedupTask(BaseTask):
    task_id = "use_speedup"
    task_name = "Use Free Speedups"
    priority = 5
    category = "construction"
    estimated_time = 15

    def run(self, overrides):
        """Use free speedup on construction/research."""
        # Check active constructions
        if self.vision.tap_on("btn_speedup_free", wait=False, timeout=3):
            self.human.delay("normal")
            log.info("Used free speedup")
            return True
        return True


class ShieldTask(BaseTask):
    task_id = "apply_shield"
    task_name = "Apply Shield"
    priority = 1
    category = "defense"
    estimated_time = 15

    def run(self, overrides):
        """Apply peace shield if not active."""
        shield_hours = overrides.get("shield_hours", 8)

        # Check if shield is already active
        if self.vision.exists("shield_active"):
            log.info("Shield already active")
            return True

        # Open items
        if self._safe_tap("btn_items", timeout=5):
            self.human.delay("normal")

            # Find shield item
            if self._safe_tap(f"item_shield_{shield_hours}h", timeout=5):
                self.human.delay("normal")

                if self._safe_tap("btn_use", timeout=3):
                    self.human.delay("normal")
                    log.info(f"Applied {shield_hours}h shield")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class ResearchTask(BaseTask):
    task_id = "research"
    task_name = "Research Technology"
    priority = 3
    category = "technology"
    estimated_time = 30

    def run(self, overrides):
        """Start research if researcher is free."""
        if self.vision.exists("research_busy"):
            log.info("Research already in progress")
            return True

        if self._safe_tap("building_academy", timeout=5):
            self.human.delay("normal")

            if self.vision.tap_on("btn_research_recommend", timeout=5):
                self.human.delay("slow")

                if self.vision.tap_on("btn_research_start", timeout=5):
                    self.human.delay("normal")
                    log.info("Started research")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class HeroExpTask(BaseTask):
    task_id = "hero_exp"
    task_name = "Hero Training"
    priority = 5
    category = "hero"
    estimated_time = 20

    def run(self, overrides):
        """Train heroes for experience."""
        if self._safe_tap("btn_hero_hall", timeout=5):
            self.human.delay("normal")

            if self.vision.tap_on("btn_train_hero", timeout=5):
                self.human.delay("slow")
                log.info("Started hero training")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class TribeGiftsTask(BaseTask):
    task_id = "tribe_gifts"
    task_name = "Claim Tribe Gifts"
    priority = 4
    category = "alliance"
    estimated_time = 15

    def run(self, overrides):
        """Open and claim tribe/alliance gifts."""
        if self._safe_tap("btn_tribe", timeout=5):
            self.human.delay("normal")

            if self._safe_tap("tab_gifts", timeout=3):
                self.human.delay("normal")

                # Claim all gifts
                for _ in range(5):
                    if self.vision.tap_on("btn_claim_gift", wait=False):
                        self.human.delay("fast")
                    else:
                        break

                log.info("Claimed tribe gifts")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class VikingTrialTask(BaseTask):
    task_id = "viking_trial"
    task_name = "Viking Trial"
    priority = 6
    category = "combat"
    estimated_time = 60

    def run(self, overrides):
        """Auto-battle Viking Trial stages."""
        auto_stages = overrides.get("auto_stages", 3)

        if self._safe_tap("btn_viking_trial", timeout=5):
            self.human.delay("normal")

            for stage in range(auto_stages):
                if self.vision.tap_on("btn_challenge", timeout=5):
                    self.human.delay("slow")

                    # Auto battle
                    if self.vision.tap_on("btn_auto_battle", timeout=3):
                        self.human.delay("reading")

                    # Wait for battle to finish
                    self.vision.wait_for("btn_battle_complete", timeout=120)
                    self.human.delay("normal")

                    # Collect rewards
                    self.vision.tap_on("btn_collect_reward", timeout=5)
                    self.human.delay("normal")

            log.info(f"Completed {auto_stages} Viking Trial stages")

        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Import Extended Tasks ────────────────────────────────────

from tasks.resources import RESOURCE_TASKS
from tasks.alliance import ALLIANCE_TASKS
from tasks.daily import DAILY_TASKS
from tasks.viking_world import WORLD_TASKS
from tasks.economy import ECONOMY_TASKS
from tasks.heroes import HERO_TASKS
from tasks.events import EVENT_TASKS
from tasks.progression import PROGRESSION_TASKS
from tasks.inventory import INVENTORY_TASKS

# ─── Task Registry ────────────────────────────────────────────

# Core tasks (13)
CORE_TASKS = [
    CollectResourcesTask,
    BuildUpgradeTask,
    TrainTroopsTask,
    GatherResourcesTask,
    CollectMailTask,
    DailyQuestsTask,
    AllianceHelpTask,
    UseSpeedupTask,
    ShieldTask,
    ResearchTask,
    HeroExpTask,
    TribeGiftsTask,
    VikingTrialTask,
]

# All tasks combined
ALL_TASKS = (
    CORE_TASKS
    + RESOURCE_TASKS      # 7 tasks
    + ALLIANCE_TASKS      # 6 tasks
    + DAILY_TASKS         # 7 tasks
    + WORLD_TASKS         # 4 tasks
    + ECONOMY_TASKS       # 6 tasks
    + HERO_TASKS          # 4 tasks
    + EVENT_TASKS         # 6 tasks
    + PROGRESSION_TASKS   # 6 tasks
    + INVENTORY_TASKS     # 4 tasks
)

TASK_MAP = {t.task_id: t for t in ALL_TASKS}

# Category grouping
TASK_CATEGORIES = {}
for task in ALL_TASKS:
    cat = task.category
    if cat not in TASK_CATEGORIES:
        TASK_CATEGORIES[cat] = []
    TASK_CATEGORIES[cat].append(task)


def get_task_class(task_id):
    """Get task class by ID."""
    return TASK_MAP.get(task_id)


def get_all_task_ids():
    """Get list of all task IDs."""
    return list(TASK_MAP.keys())


def get_tasks_by_category(category):
    """Get all tasks in a category."""
    return TASK_CATEGORIES.get(category, [])


def print_task_summary():
    """Print summary of all registered tasks."""
    print(f"\n📋 VRBOT Task Registry — {len(ALL_TASKS)} Tasks\n")
    for cat, tasks in TASK_CATEGORIES.items():
        if tasks:
            print(f"  [{cat.upper()}] ({len(tasks)} tasks)")
            for t in tasks:
                print(f"    ├─ {t.task_id}: {t.task_name} (priority {t.priority})")
    print()
