"""
Viking Rise Daily Tasks: Errands, Prosperity, Task Rewards, Mail, Daily Gifts
"""

from tasks.base import BaseTask


class ErrandsTask(BaseTask):
    id = "errands"
    name = "Errands"
    interval_sec = 300

    async def execute(self):
        await self.report("Running errands...")
        await self.go_home()
        await self.humanizer.medium_delay()

        if await self.tap_template("btn_errands.png"):
            await self.humanizer.medium_delay()

            # Complete available errands
            for _ in range(10):
                if await self.tap_template("errand_available.png", timeout=2):
                    await self.humanizer.short_delay()
                    if await self.tap_template("btn_complete.png", timeout=2):
                        await self.humanizer.short_delay()
                        await self.report("Errand completed")
                else:
                    break

            await self.back()


class ProsperityDailyTask(BaseTask):
    id = "prosperity_daily"
    name = "Prosperity Daily"
    interval_sec = 3600  # every hour

    async def execute(self):
        await self.report("Checking prosperity daily...")
        await self.go_home()

        if await self.tap_template("btn_prosperity.png"):
            await self.humanizer.medium_delay()

            # Collect available rewards
            for _ in range(5):
                if await self.tap_template("prosperity_collect.png", timeout=2):
                    await self.humanizer.short_delay()
                else:
                    break

            await self.back()


class TaskRewardsTask(BaseTask):
    id = "task_rewards"
    name = "Task Rewards (Chapter/Daily/Quest)"
    interval_sec = 600

    async def execute(self):
        await self.report("Collecting task rewards...")
        await self.go_home()

        # Open quests panel
        if await self.tap_template("btn_quests.png"):
            await self.humanizer.medium_delay()

            # Daily tasks tab
            if await self.tap_template("tab_daily.png", timeout=3):
                await self.humanizer.short_delay()
                for _ in range(10):
                    if await self.tap_template("btn_claim_reward.png", timeout=2):
                        await self.humanizer.short_delay()
                        await self.report("Daily reward claimed")
                    else:
                        break

            # Chapter tasks tab
            if await self.tap_template("tab_chapter.png", timeout=3):
                await self.humanizer.short_delay()
                for _ in range(5):
                    if await self.tap_template("btn_claim_reward.png", timeout=2):
                        await self.humanizer.short_delay()
                        await self.report("Chapter reward claimed")
                    else:
                        break

            # Quest tab
            if await self.tap_template("tab_quest.png", timeout=3):
                await self.humanizer.short_delay()
                for _ in range(5):
                    if await self.tap_template("btn_claim_reward.png", timeout=2):
                        await self.humanizer.short_delay()
                        await self.report("Quest reward claimed")
                    else:
                        break

            await self.back()


class MailRewardsTask(BaseTask):
    id = "mail_rewards"
    name = "Mail Rewards"
    interval_sec = 900

    async def execute(self):
        await self.report("Collecting mail rewards...")
        await self.go_home()

        if await self.tap_template("btn_mail.png"):
            await self.humanizer.medium_delay()

            # Collect all button
            if await self.tap_template("btn_collect_all.png"):
                await self.humanizer.short_delay()
                await self.report("Mail rewards collected")

            await self.back()


class OpenDailyGiftsTask(BaseTask):
    id = "daily_gifts"
    name = "Open Daily Task Gifts"
    interval_sec = 3600

    async def execute(self):
        await self.report("Opening daily task gifts...")
        await self.go_home()

        if await self.tap_template("btn_daily_gift.png"):
            await self.humanizer.medium_delay()

            for _ in range(5):
                if await self.tap_template("gift_available.png", timeout=2):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_open.png", timeout=2)
                    await self.humanizer.short_delay()
                else:
                    break

            await self.back()


class OpenAccountBoundItemsTask(BaseTask):
    id = "account_bound_items"
    name = "Open Account Bound Items"
    interval_sec = 3600

    async def execute(self):
        await self.report("Opening account bound items (grim chests etc)...")
        await self.go_home()

        if await self.tap_template("btn_items.png"):
            await self.humanizer.medium_delay()

            # Look for grim chests and other bound items
            items = ["item_grim_chest.png", "item_bound_chest.png", "item_supply_chest.png"]
            for item in items:
                for _ in range(20):  # Open up to 20
                    if await self.tap_template(item, timeout=2):
                        await self.humanizer.short_delay()
                        if await self.tap_template("btn_use.png", timeout=2):
                            await self.humanizer.short_delay()
                            await self.tap_template("btn_confirm.png", timeout=2)
                    else:
                        break

            await self.back()
