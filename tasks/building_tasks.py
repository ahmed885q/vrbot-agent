"""
Viking Rise Building & Event Tasks: Staging Post, Commissions, Smithy,
Chief Hall, Promo Codes, Expansion, Speedups, Divination, Chapters, etc.
"""

from tasks.base import BaseTask


class StagingPostTask(BaseTask):
    id = "staging_post"
    name = "Staging Post (except red battle)"
    interval_sec = 1800

    async def execute(self):
        await self.report("Checking staging post...")
        await self.go_home()

        if await self.tap_template("building_staging_post.png"):
            await self.humanizer.medium_delay()

            # Complete non-battle missions (skip red battle icon)
            for _ in range(10):
                # Check for available missions (NOT red battle)
                if self.on_screen("staging_battle_red.png"):
                    await self.report("Skipping red battle mission")
                    continue

                if await self.tap_template("staging_mission_available.png", timeout=3):
                    await self.humanizer.short_delay()
                    if await self.tap_template("btn_dispatch.png", timeout=3):
                        await self.report("Staging post mission dispatched")
                        await self.humanizer.medium_delay()
                else:
                    break

            # Collect completed missions
            for _ in range(5):
                if await self.tap_template("staging_complete.png", timeout=2):
                    await self.humanizer.short_delay()
                    await self.report("Staging post reward collected")
                else:
                    break

            await self.back()


class CommissionsTask(BaseTask):
    id = "commissions"
    name = "Commissions"
    interval_sec = 1800

    async def execute(self):
        await self.report("Checking commissions...")
        await self.go_home()

        if await self.tap_template("btn_commissions.png"):
            await self.humanizer.medium_delay()

            # Complete available commissions
            for _ in range(10):
                if await self.tap_template("commission_available.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_start.png", timeout=3)
                    await self.report("Commission started")
                    await self.humanizer.short_delay()
                elif await self.tap_template("commission_complete.png", timeout=2):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_claim.png")
                    await self.report("Commission reward claimed")
                else:
                    break

            await self.back()


class SmithyConquestTask(BaseTask):
    id = "smithy_conquest"
    name = "Smithy Conquest"
    interval_sec = 3600

    async def execute(self):
        await self.report("Smithy conquest...")
        await self.go_home()

        if await self.tap_template("building_smithy.png"):
            await self.humanizer.medium_delay()

            if await self.tap_template("tab_conquest.png", timeout=5):
                await self.humanizer.medium_delay()

                # Craft available items
                if await self.tap_template("btn_craft.png", timeout=5):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_confirm.png")
                    await self.report("Smithy conquest item crafted")

            await self.back()


class UpgradeChiefHallTask(BaseTask):
    id = "upgrade_chief_hall"
    name = "Upgrade Chief Hall"
    interval_sec = 600

    async def execute(self):
        await self.report("Checking Chief Hall upgrade...")
        await self.go_home()

        if await self.tap_template("building_chief_hall.png"):
            await self.humanizer.medium_delay()

            if self.on_screen("btn_upgrade_available.png"):
                await self.tap_template("btn_upgrade_available.png")
                await self.humanizer.short_delay()

                # Use speedups if configured for fast build
                if await self.tap_template("btn_confirm.png"):
                    await self.report("Chief Hall upgrade started")
            else:
                await self.report("Chief Hall upgrade not available yet")

            await self.back()


class FastChiefHallTask(BaseTask):
    id = "fast_chief_hall"
    name = "Fast Chief Hall to 22 (Build Only Needed)"
    interval_sec = 300

    async def execute(self):
        await self.report("Fast Chief Hall construction check...")
        await self.go_home()

        # Check current chief hall level
        if await self.tap_template("building_chief_hall.png"):
            await self.humanizer.medium_delay()

            # Check if upgrade requirements are met
            if self.on_screen("requirements_met.png"):
                if await self.tap_template("btn_upgrade.png"):
                    await self.humanizer.short_delay()
                    # Use construction speedups
                    if await self.tap_template("btn_speedup.png", timeout=3):
                        await self.tap_template("btn_use_speedup.png")
                        await self.report("Chief Hall speedup applied")
                    await self.tap_template("btn_confirm.png")
                    await self.report("Chief Hall upgrade initiated")
            elif self.on_screen("requirement_missing.png"):
                await self.report("Missing requirements for Chief Hall upgrade")

            await self.back()


class ExpansionBuildTask(BaseTask):
    id = "expansion_build"
    name = "Expansion Build at 5 until Prosperity 4"
    interval_sec = 900

    async def execute(self):
        await self.report("Checking expansion builds...")
        await self.go_home()

        # Build expansion structures up to level 5
        if await self.tap_template("btn_expansion.png"):
            await self.humanizer.medium_delay()

            for _ in range(5):
                if await self.tap_template("expansion_buildable.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_build.png")
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_confirm.png")
                    await self.report("Expansion building started")
                    await self.humanizer.medium_delay()
                else:
                    break

            await self.back()


class ConstructionSpeedupTask(BaseTask):
    id = "construction_speedup"
    name = "Construction & Regular Speedups"
    interval_sec = 300

    async def execute(self):
        await self.report("Applying construction speedups...")
        await self.go_home()

        # Find active construction timers
        if self.on_screen("construction_timer.png"):
            await self.tap_template("construction_timer.png")
            await self.humanizer.medium_delay()

            if await self.tap_template("btn_speedup.png"):
                await self.humanizer.short_delay()
                # Use regular speedups (not gems)
                if await self.tap_template("speedup_regular.png", timeout=3):
                    await self.tap_template("btn_use.png")
                    await self.report("Construction speedup applied")
                await self.back()


class RedeemPromoCodesTask(BaseTask):
    id = "redeem_promo_codes"
    name = "Redeem Promotional Codes"
    interval_sec = 86400  # once a day

    async def execute(self):
        await self.report("Checking promo codes...")
        await self.go_home()

        # Open settings → redeem code
        if await self.tap_template("btn_settings.png"):
            await self.humanizer.medium_delay()

            if await self.tap_template("btn_redeem_code.png"):
                await self.humanizer.medium_delay()
                # Promo codes would need to be configured
                await self.report("Promo code screen opened (manual input needed)")

            await self.back()


class DivinationTask(BaseTask):
    id = "divination"
    name = "Divination (Speedups Only)"
    interval_sec = 3600

    async def execute(self):
        await self.report("Checking divination (speedups)...")
        await self.go_home()

        if await self.tap_template("building_divination.png"):
            await self.humanizer.medium_delay()

            # Select speedup category
            if await self.tap_template("divination_speedup.png", timeout=5):
                await self.humanizer.short_delay()
                if await self.tap_template("btn_divine.png"):
                    await self.humanizer.medium_delay()
                    await self.close_popups()
                    await self.report("Divination completed (speedups)")

            await self.back()


class ChapterCompletionTask(BaseTask):
    id = "chapter_completion"
    name = "Chapter Completion through 17"
    interval_sec = 1800

    async def execute(self):
        await self.report("Checking chapter progress...")
        await self.go_home()

        if await self.tap_template("btn_chapters.png"):
            await self.humanizer.medium_delay()

            # Complete available chapter tasks
            for _ in range(10):
                if await self.tap_template("chapter_task_complete.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_claim.png")
                    await self.report("Chapter task claimed")
                elif await self.tap_template("chapter_task_go.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.report("Navigating to chapter task")
                    break
                else:
                    break

            await self.back()


class RebatePackTask(BaseTask):
    id = "rebate_pack"
    name = "Rebate Pack Event (New Account)"
    interval_sec = 3600

    async def execute(self):
        await self.report("Checking rebate pack event...")
        await self.go_home()

        if await self.tap_template("event_rebate_pack.png"):
            await self.humanizer.medium_delay()

            for _ in range(5):
                if await self.tap_template("rebate_claim.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.report("Rebate pack claimed")
                else:
                    break

            await self.back()
        else:
            await self.report("Rebate pack event not active")


class ConquerIslandTask(BaseTask):
    id = "conquer_island"
    name = "Conquer the Island (New Account)"
    interval_sec = 1800

    async def execute(self):
        await self.report("Checking conquer the island...")
        await self.go_home()

        if await self.tap_template("event_conquer_island.png"):
            await self.humanizer.medium_delay()

            for _ in range(5):
                if await self.tap_template("island_task_complete.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_claim.png")
                    await self.report("Island task reward claimed")
                else:
                    break

            await self.back()
        else:
            await self.report("Conquer island event not active")


class GatherSuppliesTask(BaseTask):
    id = "gather_supplies"
    name = "Gather Supplies"
    interval_sec = 600

    async def execute(self):
        await self.report("Gathering supplies...")
        await self.go_home()

        if await self.tap_template("btn_gather_supplies.png"):
            await self.humanizer.medium_delay()

            for _ in range(5):
                if await self.tap_template("supply_collect.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.report("Supply collected")
                else:
                    break

            await self.back()
