"""
Viking Rise Core Tasks: Gather, Construction, Research, Helps, Shield
"""

from tasks.base import BaseTask


class GatherTask(BaseTask):
    id = "gather"
    name = "Gather Resources"
    interval_sec = 180  # every 3 min check

    async def execute(self):
        await self.report("Checking idle troops for gathering...")
        await self.go_home()
        await self.humanizer.medium_delay()

        # Open world map
        if not await self.tap_template("nav_world.png"):
            await self.report("Cannot open world map")
            return

        await self.humanizer.medium_delay()

        # Check for resource nodes (food, wood, stone, gold)
        resources = ["node_food.png", "node_wood.png", "node_stone.png", "node_gold.png"]
        for res in resources:
            match = self.find(res)
            if match:
                await self.tap_match(match)
                await self.humanizer.medium_delay()

                if await self.tap_template("btn_gather.png"):
                    await self.humanizer.short_delay()
                    if await self.tap_template("btn_march.png"):
                        await self.report(f"Sent troops to gather {res}")
                        await self.humanizer.medium_delay()

        await self.go_home()


class ConstructionTask(BaseTask):
    id = "construction"
    name = "Construction"
    interval_sec = 120  # every 2 min

    async def execute(self):
        await self.report("Checking construction queue...")
        await self.go_home()
        await self.humanizer.medium_delay()

        # Check if builder is free (builder icon)
        if self.on_screen("builder_free.png"):
            await self.report("Builder available, checking upgrade queue")
            # Open construction menu or recommended build
            if await self.tap_template("btn_build.png"):
                await self.humanizer.medium_delay()
                if await self.tap_template("btn_upgrade.png"):
                    await self.humanizer.medium_delay()
                    await self.tap_template("btn_confirm.png")
                    await self.report("Started construction")
        else:
            # Check if speedup available
            if self.on_screen("construction_timer.png"):
                await self.report("Construction in progress")


class ResearchTask(BaseTask):
    id = "research"
    name = "Research"
    interval_sec = 300  # every 5 min

    async def execute(self):
        await self.report("Checking research...")
        await self.go_home()
        await self.humanizer.medium_delay()

        # Open research building (Hall of Knowledge)
        if await self.tap_template("building_research.png"):
            await self.humanizer.medium_delay()

            # Check if research slot is free
            if self.on_screen("research_free.png"):
                await self.report("Research slot available")
                # TODO: Select best research based on priority
                if await self.tap_template("btn_research.png"):
                    await self.humanizer.medium_delay()
                    await self.tap_template("btn_confirm.png")
                    await self.report("Started research")
            else:
                await self.report("Research in progress")

            await self.back()


class HelpsTask(BaseTask):
    id = "helps"
    name = "Alliance Helps"
    interval_sec = 60  # every 1 min

    async def execute(self):
        await self.report("Checking alliance helps...")
        await self.go_home()

        # Tap alliance help button (handshake icon)
        if await self.tap_template("btn_helps.png"):
            await self.humanizer.short_delay()
            await self.report("Helped alliance members")
        elif await self.tap_template("btn_help_all.png"):
            await self.humanizer.short_delay()
            await self.report("Helped all alliance members")


class ShieldTask(BaseTask):
    id = "shield"
    name = "Shield / Peace Shield"
    interval_sec = 600  # every 10 min check

    async def execute(self):
        await self.report("Checking shield status...")
        await self.go_home()

        # Check if shield is active
        if self.on_screen("shield_active.png"):
            await self.report("Shield is active")
            return

        # Shield expired — activate new one
        await self.report("Shield expired! Activating...")
        # Open items
        if await self.tap_template("btn_items.png"):
            await self.humanizer.medium_delay()
            # Find peace shield item
            if await self.tap_template("item_shield.png"):
                await self.humanizer.short_delay()
                await self.tap_template("btn_use.png")
                await self.report("Shield activated")
            else:
                await self.report("No shield items available!")

            await self.back()
