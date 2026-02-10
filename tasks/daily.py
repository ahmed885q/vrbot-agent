"""
VRBOT Agent — Daily Tasks
Daily activities, events, and reward collection for Viking Rise.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.daily")


class DailyLoginRewardTask(BaseTask):
    task_id = "daily_login_reward"
    task_name = "Daily Login Reward"
    priority = 1
    category = "daily"
    estimated_time = 10

    def run(self, overrides):
        """Collect daily login rewards and check-in bonuses."""
        # Check if login reward popup is showing
        if self.vision.tap_on("btn_daily_login_claim", wait=False, timeout=3):
            self.human.delay("normal")
            log.info("Claimed daily login reward")
            return True

        # Try opening rewards manually
        if self._safe_tap("btn_benefits", timeout=5):
            self.human.delay("normal")

            # Daily check-in tab
            if self._safe_tap("tab_daily_checkin", timeout=3):
                self.human.delay("fast")

                # Claim today's reward
                if self.vision.tap_on("btn_checkin_claim", wait=False, timeout=3):
                    self.human.delay("normal")
                    log.info("Daily check-in claimed")

            self._safe_tap("btn_close_x", timeout=3)

        return True


class LuckyWheelSpinTask(BaseTask):
    task_id = "lucky_wheel"
    task_name = "Lucky Wheel Spin"
    priority = 3
    category = "daily"
    estimated_time = 20

    def run(self, overrides):
        """Spin the lucky wheel for free rewards."""
        max_spins = overrides.get("max_free_spins", 3)

        # Find and open lucky wheel
        if not self._safe_tap("btn_lucky_wheel", timeout=5):
            # Try through events menu
            if self._safe_tap("btn_events", timeout=3):
                self.human.delay("fast")
                if not self._safe_tap("btn_lucky_wheel_event", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    return True

        self.human.delay("normal")

        spins = 0
        for _ in range(max_spins):
            # Check if free spin available
            if self.vision.exists("btn_free_spin"):
                if self._safe_tap("btn_free_spin", timeout=3):
                    # Wait for wheel animation
                    self.human.delay("reading")
                    time.sleep(3)  # Wheel spinning animation

                    # Collect reward
                    if self.vision.tap_on("btn_collect_reward", wait=False, timeout=5):
                        self.human.delay("normal")
                        spins += 1
                        log.info(f"Lucky wheel spin #{spins}")
            else:
                break

        log.info(f"Lucky wheel: {spins} free spins used")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class ArenaBattleTask(BaseTask):
    task_id = "arena_battle"
    task_name = "Arena Battle"
    priority = 4
    category = "daily"
    estimated_time = 45

    def run(self, overrides):
        """Complete daily arena battles."""
        max_battles = overrides.get("max_arena_battles", 5)

        # Open arena
        if not self._safe_tap("btn_arena", timeout=5):
            return True

        self.human.delay("normal")

        battles = 0
        for _ in range(max_battles):
            # Check remaining attempts
            if self.vision.exists("arena_no_attempts"):
                log.info("No arena attempts remaining")
                break

            # Find opponent and challenge
            if self._safe_tap("btn_arena_challenge", timeout=5):
                self.human.delay("slow")

                # Auto battle
                if self.vision.tap_on("btn_auto_battle", wait=False, timeout=3):
                    pass

                # Wait for battle result
                result = self.vision.wait_for("btn_battle_result", timeout=60)
                if result:
                    self.human.delay("normal")
                    # Collect reward
                    self.vision.tap_on("btn_collect_reward", wait=False, timeout=5)
                    self.human.delay("normal")
                    battles += 1
                    log.info(f"Arena battle #{battles} complete")

        log.info(f"Arena: {battles}/{max_battles} battles done")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class EventRewardsTask(BaseTask):
    task_id = "event_rewards"
    task_name = "Collect Event Rewards"
    priority = 2
    category = "daily"
    estimated_time = 30

    def run(self, overrides):
        """Collect all available event rewards."""
        # Open events panel
        if not self._safe_tap("btn_events", timeout=5):
            return True

        self.human.delay("normal")

        collected = 0

        # Scroll through event tabs and claim rewards
        event_tabs = ["tab_kingdom_event", "tab_daily_event", "tab_growth_event",
                       "tab_limited_event", "tab_alliance_event"]

        for tab in event_tabs:
            if self.vision.tap_on(tab, wait=False, timeout=2):
                self.human.delay("fast")

                # Claim all available rewards in this tab
                for _ in range(10):
                    if self.vision.tap_on("btn_event_claim", wait=False, timeout=1):
                        self.human.delay("fast")
                        collected += 1
                    else:
                        break

        log.info(f"Collected {collected} event rewards")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class FreeShopItemsTask(BaseTask):
    task_id = "free_shop_items"
    task_name = "Claim Free Shop Items"
    priority = 2
    category = "daily"
    estimated_time = 15

    def run(self, overrides):
        """Claim free daily items from the shop."""
        # Open shop
        if not self._safe_tap("btn_shop", timeout=5):
            return True

        self.human.delay("normal")

        claimed = 0

        # Check daily free tab
        if self._safe_tap("tab_daily_deals", timeout=3):
            self.human.delay("fast")

            # Find free items (price = 0 or "FREE" tag)
            free_items = self.vision.find_all("tag_free_item", threshold=0.75, max_results=5)
            for x, y, conf in free_items:
                self.adb.tap(x, y, offset=self.human.pixel_offset)
                self.human.delay("fast")

                # Claim
                if self.vision.tap_on("btn_claim_free", wait=False, timeout=3):
                    self.human.delay("normal")
                    claimed += 1

        # Also check supplies tab
        if self._safe_tap("tab_supplies", timeout=3):
            self.human.delay("fast")

            if self.vision.tap_on("btn_free_supply", wait=False, timeout=3):
                self.human.delay("normal")
                claimed += 1

        log.info(f"Claimed {claimed} free shop items")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class VIPChestTask(BaseTask):
    task_id = "vip_chest"
    task_name = "VIP Daily Chest"
    priority = 2
    category = "daily"
    estimated_time = 10

    def run(self, overrides):
        """Collect daily VIP chest rewards."""
        # Open VIP panel
        if not self._safe_tap("btn_vip", timeout=5):
            return True

        self.human.delay("normal")

        # Claim daily VIP chest
        if self.vision.tap_on("btn_vip_chest_claim", wait=False, timeout=3):
            self.human.delay("normal")
            log.info("Claimed VIP daily chest")

        # Also claim VIP shop freebies
        if self._safe_tap("tab_vip_shop", timeout=3):
            self.human.delay("fast")

            if self.vision.tap_on("btn_vip_free_claim", wait=False, timeout=3):
                self.human.delay("normal")
                log.info("Claimed VIP shop freebie")

        self._safe_tap("btn_close_x", timeout=3)
        return True


class AchievementClaimsTask(BaseTask):
    task_id = "achievement_claims"
    task_name = "Claim Achievements"
    priority = 3
    category = "daily"
    estimated_time = 20

    def run(self, overrides):
        """Collect all available achievement rewards."""
        # Open achievements/quests
        if not self._safe_tap("btn_quests", timeout=5):
            return True

        self.human.delay("normal")

        claimed = 0

        # Check achievement tabs
        tabs = ["tab_achievements", "tab_growth", "tab_chapter"]
        for tab in tabs:
            if self.vision.tap_on(tab, wait=False, timeout=2):
                self.human.delay("fast")

                # Claim all available
                for _ in range(15):
                    if self.vision.tap_on("btn_achievement_claim", wait=False, timeout=1):
                        self.human.delay("fast")
                        claimed += 1
                    elif self.vision.tap_on("btn_quest_claim", wait=False, timeout=1):
                        self.human.delay("fast")
                        claimed += 1
                    else:
                        break

        # Also collect activity chest rewards (daily points)
        for chest in ["chest_50", "chest_100", "chest_150", "chest_200"]:
            if self.vision.tap_on(f"btn_{chest}", wait=False, timeout=1):
                self.human.delay("fast")
                claimed += 1

        log.info(f"Claimed {claimed} achievement/quest rewards")
        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Export ───────────────────────────────────────────────────

DAILY_TASKS = [
    DailyLoginRewardTask,
    LuckyWheelSpinTask,
    ArenaBattleTask,
    EventRewardsTask,
    FreeShopItemsTask,
    VIPChestTask,
    AchievementClaimsTask,
]

