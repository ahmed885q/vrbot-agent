"""
VRBOT Agent — Inventory Tasks
Open account bound items, daily task gifts, enhanced task rewards.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.inventory")


class OpenBoundItemsTask(BaseTask):
    task_id = "open_bound_items"
    task_name = "Open Account Bound Items"
    priority = 4
    category = "inventory"
    estimated_time = 30

    def run(self, overrides):
        """
        Open account-bound items:
        - Grim Chests
        - Bound resource packs
        - Token packs
        - Event bound items
        """
        item_types = overrides.get("item_types", [
            "grim_chest", "bound_resource", "token_pack",
            "event_chest", "supply_crate", "hero_fragment_box"
        ])

        # Open inventory/items
        if not self._safe_tap("btn_items", timeout=5):
            return True

        self.human.delay("normal")

        opened = 0

        # Navigate through inventory tabs
        tabs_to_check = ["tab_special", "tab_resources", "tab_other", "tab_chest"]

        for tab in tabs_to_check:
            if self.vision.tap_on(tab, wait=False, timeout=2):
                self.human.delay("fast")

                # Find and open bound items
                for item_type in item_types:
                    items = self.vision.find_all(f"item_{item_type}", threshold=0.70, max_results=5)
                    for ix, iy, iconf in items:
                        self.adb.tap(ix, iy, offset=self.human.pixel_offset)
                        self.human.delay("fast")

                        # Use / Open
                        if self.vision.tap_on("btn_use", wait=False, timeout=2):
                            self.human.delay("fast")
                        elif self.vision.tap_on("btn_open", wait=False, timeout=2):
                            self.human.delay("fast")
                        elif self.vision.tap_on("btn_use_all", wait=False, timeout=2):
                            self.human.delay("fast")

                        # Confirm
                        if self.vision.tap_on("btn_confirm", wait=False, timeout=2):
                            self.human.delay("normal")
                            opened += 1
                            log.info(f"Opened: {item_type}")

                        # Dismiss result
                        self.vision.tap_on("btn_ok", wait=False, timeout=2)
                        self.human.delay("fast")

        log.info(f"Bound items opened: {opened}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class OpenDailyTaskGiftsTask(BaseTask):
    task_id = "open_daily_task_gifts"
    task_name = "Open Daily Task Gifts"
    priority = 2
    category = "inventory"
    estimated_time = 15

    def run(self, overrides):
        """Open daily task gift boxes and activity reward chests."""
        # Open daily tasks/quests
        if not self._safe_tap("btn_quests", timeout=5):
            return True

        self.human.delay("normal")

        # Switch to daily tab
        if self._safe_tap("tab_daily", timeout=3):
            self.human.delay("fast")

        claimed = 0

        # Collect individual task rewards
        for _ in range(15):
            if self.vision.tap_on("btn_quest_claim", wait=False, timeout=1):
                self.human.delay("fast")
                claimed += 1
            else:
                break

        # Collect activity point chests (bottom bar)
        activity_chests = [
            "btn_activity_chest_30",
            "btn_activity_chest_60",
            "btn_activity_chest_100",
            "btn_activity_chest_120",
            "btn_activity_chest_150",
        ]
        for chest in activity_chests:
            if self.vision.tap_on(chest, wait=False, timeout=1):
                self.human.delay("fast")
                claimed += 1

        # Open gift boxes if available
        for _ in range(5):
            if self.vision.tap_on("btn_daily_gift_open", wait=False, timeout=1):
                self.human.delay("fast")
                claimed += 1

        log.info(f"Daily task gifts claimed: {claimed}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class EnhancedTaskRewardsTask(BaseTask):
    task_id = "enhanced_task_rewards"
    task_name = "Task Rewards (Chapter + Daily + Quest)"
    priority = 2
    category = "inventory"
    estimated_time = 30

    def run(self, overrides):
        """
        Comprehensive reward collection across all quest types:
        - Chapter quest rewards
        - Daily quest rewards
        - Side quest rewards
        - Growth quest rewards
        """
        # Open quest panel
        if not self._safe_tap("btn_quests", timeout=5):
            return True

        self.human.delay("normal")
        total_claimed = 0

        # --- Chapter Rewards ---
        if self._safe_tap("tab_chapter", timeout=2):
            self.human.delay("fast")
            for _ in range(10):
                if self.vision.tap_on("btn_chapter_claim", wait=False, timeout=1):
                    self.human.delay("fast")
                    total_claimed += 1
                else:
                    break

        # --- Daily Rewards ---
        if self._safe_tap("tab_daily", timeout=2):
            self.human.delay("fast")
            for _ in range(15):
                if self.vision.tap_on("btn_quest_claim", wait=False, timeout=1):
                    self.human.delay("fast")
                    total_claimed += 1
                else:
                    break

            # Activity chests
            for i in range(5):
                if self.vision.tap_on(f"btn_activity_chest_{i}", wait=False, timeout=1):
                    self.human.delay("fast")
                    total_claimed += 1

        # --- Side Quests ---
        if self._safe_tap("tab_side_quest", timeout=2):
            self.human.delay("fast")
            for _ in range(10):
                if self.vision.tap_on("btn_quest_claim", wait=False, timeout=1):
                    self.human.delay("fast")
                    total_claimed += 1
                else:
                    break

        # --- Growth / Achievement ---
        if self._safe_tap("tab_growth", timeout=2):
            self.human.delay("fast")
            for _ in range(10):
                if self.vision.tap_on("btn_achievement_claim", wait=False, timeout=1):
                    self.human.delay("fast")
                    total_claimed += 1
                else:
                    break

        log.info(f"Task rewards collected: {total_claimed}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class TribeTechR5AcceptTask(BaseTask):
    task_id = "tribe_tech_r5_accept"
    task_name = "Tribe Tech + R5 Accept"
    priority = 3
    category = "alliance"
    estimated_time = 20

    def run(self, overrides):
        """
        Enhanced tribe tech: donate AND accept R5 pending requests.
        """
        max_donations = overrides.get("max_donations", 10)
        accept_r5 = overrides.get("accept_r5_requests", True)

        # Open tribe
        if not self._safe_tap("btn_tribe", timeout=5):
            return True

        self.human.delay("normal")

        # --- Donate Technology ---
        if self._safe_tap("tab_technology", timeout=3):
            self.human.delay("normal")

            donated = 0
            for _ in range(max_donations):
                if self.vision.tap_on("btn_donate", wait=False, timeout=1):
                    self.human.delay("fast")
                    donated += 1
                else:
                    break

            log.info(f"Tribe tech donations: {donated}")

        # --- R5 Accept (Leader/R5 permissions) ---
        if accept_r5:
            if self._safe_tap("tab_management", timeout=3):
                self.human.delay("normal")

                # Check for pending join requests
                if self._safe_tap("btn_join_requests", timeout=3):
                    self.human.delay("fast")

                    accepted = 0
                    # Accept all pending
                    for _ in range(20):
                        if self.vision.tap_on("btn_accept_request", wait=False, timeout=1):
                            self.human.delay("fast")
                            accepted += 1
                        else:
                            break

                    # Or use "Accept All" if available
                    if self.vision.tap_on("btn_accept_all_requests", wait=False, timeout=2):
                        self.human.delay("normal")
                        log.info("Accepted all pending R5 requests")
                    elif accepted > 0:
                        log.info(f"R5 requests accepted: {accepted}")

        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Export ───────────────────────────────────────────────────

INVENTORY_TASKS = [
    OpenBoundItemsTask,
    OpenDailyTaskGiftsTask,
    EnhancedTaskRewardsTask,
    TribeTechR5AcceptTask,
]

