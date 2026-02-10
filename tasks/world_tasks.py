"""
Viking Rise World Tasks: Clear City/Forest, Monster Caves, Reclaim Midgard,
Niflung Hunting, Leidolf in Hiding, Cinderbone Soulburn, Festival of Flames
"""

from tasks.base import BaseTask


class ClearCityForestTask(BaseTask):
    id = "clear_city_forest"
    name = "Clear City Forest & Monster Caves"
    interval_sec = 600

    async def execute(self):
        await self.report("Clearing city forest and monster caves...")
        await self.go_home()
        await self.humanizer.medium_delay()

        # Find clearable objects around city
        targets = ["forest_clear.png", "rock_clear.png", "monster_cave.png"]
        for target in targets:
            matches = self.vision.find_all_templates(target, threshold=0.8, max_results=5)
            for match in matches:
                await self.tap_match(match)
                await self.humanizer.medium_delay()

                if await self.tap_template("btn_clear.png", timeout=3):
                    await self.humanizer.short_delay()
                    if await self.tap_template("btn_march.png", timeout=3):
                        await self.report(f"Clearing {target}")
                        await self.humanizer.medium_delay()
                    else:
                        await self.back()
                else:
                    await self.back()

        await self.go_home()


class ReclaimMidgardTask(BaseTask):
    id = "reclaim_midgard"
    name = "Reclaim Midgard"
    interval_sec = 900

    async def execute(self):
        await self.report("Reclaiming Midgard...")
        await self.go_home()

        if await self.tap_template("btn_reclaim_midgard.png"):
            await self.humanizer.medium_delay()

            # Battle monsters
            if self.on_screen("midgard_monster.png"):
                if await self.tap_template("midgard_monster.png"):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_attack.png")
                    await self.humanizer.medium_delay()
                    await self.tap_template("btn_march.png")
                    await self.report("Attacking Midgard monster")

            # Unlock sentry towers
            if await self.tap_template("sentry_tower_locked.png", timeout=3):
                await self.humanizer.short_delay()
                await self.tap_template("btn_unlock.png")
                await self.report("Unlocking sentry tower")

            # Unlock sacrificial stones
            if await self.tap_template("sacrificial_stone_locked.png", timeout=3):
                await self.humanizer.short_delay()
                await self.tap_template("btn_unlock.png")
                await self.report("Unlocking sacrificial stone")

            # Unlock villages
            if await self.tap_template("village_locked.png", timeout=3):
                await self.humanizer.short_delay()
                await self.tap_template("btn_unlock.png")
                await self.report("Unlocking village")

            # Unlock Odin statue
            if await self.tap_template("odin_statue_locked.png", timeout=3):
                await self.humanizer.short_delay()
                await self.tap_template("btn_unlock.png")
                await self.report("Unlocking Odin statue")

            await self.back()


class NiflungHuntingTask(BaseTask):
    id = "niflung_hunting"
    name = "Niflung Hunting"
    interval_sec = 1800  # every 30 min

    async def execute(self):
        await self.report("Niflung hunting...")
        await self.go_home()

        if await self.tap_template("btn_niflung.png"):
            await self.humanizer.medium_delay()

            # Find and attack Niflungs
            for _ in range(5):
                if await self.tap_template("niflung_target.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_attack.png")
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_march.png")
                    await self.report("Attacking Niflung")
                    await self.humanizer.long_delay()
                else:
                    break

            await self.back()


class LeidolfInHidingTask(BaseTask):
    id = "leidolf_hiding"
    name = "Leidolf in Hiding Event"
    interval_sec = 3600

    async def execute(self):
        await self.report("Checking Leidolf in Hiding event...")
        await self.go_home()

        if await self.tap_template("event_leidolf.png"):
            await self.humanizer.medium_delay()

            # Search for Leidolf
            if await self.tap_template("btn_search_leidolf.png", timeout=5):
                await self.humanizer.medium_delay()
                await self.tap_template("btn_confirm.png")
                await self.report("Searching for Leidolf")

            await self.back()
        else:
            await self.report("Leidolf event not active")


class CinderboneSoulburnTask(BaseTask):
    id = "cinderbone_soulburn"
    name = "Cinderbone Soulburn"
    interval_sec = 3600

    async def execute(self):
        await self.report("Checking Cinderbone Soulburn...")
        await self.go_home()

        if await self.tap_template("event_cinderbone.png"):
            await self.humanizer.medium_delay()

            for _ in range(5):
                if await self.tap_template("btn_soulburn.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_confirm.png")
                    await self.report("Cinderbone Soulburn performed")
                    await self.humanizer.medium_delay()
                else:
                    break

            await self.back()
        else:
            await self.report("Cinderbone event not active")


class FestivalOfFlamesTask(BaseTask):
    id = "festival_of_flames"
    name = "Festival of Flames"
    interval_sec = 3600

    async def execute(self):
        await self.report("Checking Festival of Flames...")
        await self.go_home()

        if await self.tap_template("event_festival_flames.png"):
            await self.humanizer.medium_delay()

            # Collect flames rewards
            for _ in range(5):
                if await self.tap_template("flames_collect.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.report("Flames reward collected")
                else:
                    break

            await self.back()
        else:
            await self.report("Festival of Flames not active")
