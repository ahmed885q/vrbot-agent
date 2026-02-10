"""
VRBOT Agent — Resource Tasks
Advanced resource management tasks for Viking Rise.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.resources")


class ResourceSwapTask(BaseTask):
    task_id = "resource_swap"
    task_name = "Resource Swap"
    priority = 5
    category = "resources"
    estimated_time = 20

    def run(self, overrides):
        """Swap excess resources at the marketplace."""
        from_res = overrides.get("from_resource", "food")
        to_res = overrides.get("to_resource", "stone")

        # Open marketplace
        if not self._safe_tap("building_marketplace", timeout=5):
            log.info("Marketplace not found")
            return True

        self.human.delay("normal")

        # Select exchange tab
        if self._safe_tap("tab_exchange", timeout=3):
            self.human.delay("fast")

            # Select from resource
            if self._safe_tap(f"res_select_{from_res}", timeout=3):
                self.human.delay("fast")

            # Select to resource
            if self._safe_tap(f"res_select_{to_res}", timeout=3):
                self.human.delay("fast")

            # Set amount to max
            if self._safe_tap("btn_max_amount", timeout=3):
                self.human.delay("fast")

            # Confirm exchange
            if self._safe_tap("btn_exchange_confirm", timeout=5):
                self.human.delay("normal")
                log.info(f"Exchanged {from_res} → {to_res}")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class OpenResourcePacksTask(BaseTask):
    task_id = "open_resource_packs"
    task_name = "Open Resource Packs"
    priority = 6
    category = "resources"
    estimated_time = 30

    def run(self, overrides):
        """Open resource packs from inventory."""
        pack_types = overrides.get("pack_types", ["food", "wood", "stone", "iron"])

        # Open items/inventory
        if not self._safe_tap("btn_items", timeout=5):
            return True

        self.human.delay("normal")

        # Switch to resources tab
        if self._safe_tap("tab_resources", timeout=3):
            self.human.delay("fast")

        opened = 0
        for pack_type in pack_types:
            # Find resource pack
            if self.vision.tap_on(f"item_pack_{pack_type}", wait=False):
                self.human.delay("fast")

                # Use all
                if self._safe_tap("btn_use_all", timeout=3):
                    self.human.delay("fast")

                    # Confirm
                    if self._safe_tap("btn_confirm", timeout=3):
                        self.human.delay("normal")
                        opened += 1
                        log.info(f"Opened {pack_type} packs")

        log.info(f"Opened {opened} pack types")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class GemMiningTask(BaseTask):
    task_id = "gem_mining"
    task_name = "Gem Mining"
    priority = 4
    category = "resources"
    estimated_time = 25

    def run(self, overrides):
        """Collect gems from gem mine and send new gathering."""
        # Find gem mine building
        if not self._safe_tap("building_gem_mine", timeout=5):
            log.info("Gem mine not found")
            return True

        self.human.delay("normal")

        # Collect available gems
        if self.vision.tap_on("btn_collect_gems", wait=False, timeout=3):
            self.human.delay("normal")
            log.info("Collected gems from mine")

        # Check if we can start new mining
        if self.vision.tap_on("btn_start_mining", wait=False, timeout=3):
            self.human.delay("normal")
            log.info("Started new gem mining")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class ResourceBoostTask(BaseTask):
    task_id = "resource_boost"
    task_name = "Activate Resource Boost"
    priority = 5
    category = "resources"
    estimated_time = 20

    def run(self, overrides):
        """Activate resource production boost items."""
        boost_types = overrides.get("boost_types", ["food", "wood"])

        # Open items
        if not self._safe_tap("btn_items", timeout=5):
            return True

        self.human.delay("normal")

        # Switch to boosts tab
        if self._safe_tap("tab_boosts", timeout=3):
            self.human.delay("fast")

        activated = 0
        for boost in boost_types:
            if self.vision.tap_on(f"item_boost_{boost}", wait=False):
                self.human.delay("fast")

                if self._safe_tap("btn_use", timeout=3):
                    self.human.delay("normal")
                    activated += 1
                    log.info(f"Activated {boost} production boost")

        self._safe_tap("btn_close_x", timeout=3)
        log.info(f"Activated {activated} boosts")
        return True


class FarmPlotHarvestTask(BaseTask):
    task_id = "farm_plot_harvest"
    task_name = "Harvest Farm Plots"
    priority = 2
    category = "resources"
    estimated_time = 25

    def run(self, overrides):
        """Harvest and replant all farm plots around the city."""
        harvested = 0

        # Find all harvestable plots (green checkmark icons)
        plots = self.vision.find_all("icon_harvest_ready", threshold=0.75, max_results=15)
        for x, y, conf in plots:
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("fast")

            # Tap harvest
            if self.vision.tap_on("btn_harvest", wait=False, timeout=3):
                self.human.delay("fast")
                harvested += 1

            # Auto replant
            if self.vision.tap_on("btn_plant", wait=False, timeout=2):
                self.human.delay("fast")

        log.info(f"Harvested {harvested} farm plots")
        return True


class FishingTask(BaseTask):
    task_id = "fishing"
    task_name = "Fishing"
    priority = 7
    category = "resources"
    estimated_time = 40

    def run(self, overrides):
        """Go fishing for extra resources and items."""
        attempts = overrides.get("fishing_attempts", 3)

        # Find fishing spot
        if not self._safe_tap("btn_fishing", timeout=5):
            log.info("Fishing not available")
            return True

        self.human.delay("normal")

        caught = 0
        for i in range(attempts):
            # Cast line
            if self._safe_tap("btn_cast", timeout=5):
                self.human.delay("reading")

                # Wait for fish bite (watch for indicator)
                bite = self.vision.wait_for("icon_fish_bite", timeout=15, interval=0.5)
                if bite:
                    # Reel in quickly
                    self.human.delay("fast")
                    if self._safe_tap("btn_reel", timeout=3):
                        self.human.delay("normal")
                        caught += 1
                        log.info(f"Caught fish #{caught}")

                # Wait between casts
                self.human.delay("slow")

        log.info(f"Fishing complete: caught {caught}/{attempts}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class ResourceProtectionTask(BaseTask):
    task_id = "resource_protection"
    task_name = "Protect Resources"
    priority = 2
    category = "resources"
    estimated_time = 15

    def run(self, overrides):
        """Store excess resources in warehouse/storehouse for protection."""
        # Open storehouse
        if not self._safe_tap("building_storehouse", timeout=5):
            log.info("Storehouse not found")
            return True

        self.human.delay("normal")

        # Check if resources exceed protection limit
        if self.vision.exists("icon_over_limit"):
            log.warning("Resources over protection limit!")

            # Try to store excess
            if self._safe_tap("btn_store_all", timeout=3):
                self.human.delay("normal")
                log.info("Stored excess resources")

        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Export ───────────────────────────────────────────────────

RESOURCE_TASKS = [
    ResourceSwapTask,
    OpenResourcePacksTask,
    GemMiningTask,
    ResourceBoostTask,
    FarmPlotHarvestTask,
    FishingTask,
    ResourceProtectionTask,
]

