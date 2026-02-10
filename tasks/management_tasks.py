"""
Viking Rise Management Tasks: Farmers, Village Champions, Hall of Valor,
Hero XP/Training, Recruit Farmers, Tribe Tech/Gifts
"""

from tasks.base import BaseTask


class FarmerAppointmentsTask(BaseTask):
    id = "farmer_appointments"
    name = "Farmer Appointments (Optimized)"
    interval_sec = 1800

    async def execute(self):
        await self.report("Managing farmer appointments (optimized)...")
        await self.go_home()

        if await self.tap_template("btn_farm.png"):
            await self.humanizer.medium_delay()

            # Prioritized farmer placement (not random)
            # Priority: Food > Wood > Stone > Gold based on need
            farm_slots = ["farm_slot_food.png", "farm_slot_wood.png",
                         "farm_slot_stone.png", "farm_slot_gold.png"]

            for slot in farm_slots:
                if await self.tap_template(slot, timeout=3):
                    await self.humanizer.short_delay()
                    if await self.tap_template("btn_appoint.png", timeout=3):
                        await self.humanizer.short_delay()
                        # Select best farmer available
                        if await self.tap_template("farmer_best.png", timeout=3):
                            await self.tap_template("btn_confirm.png")
                            await self.report(f"Farmer appointed to {slot}")
                        await self.humanizer.short_delay()

            await self.back()


class VillageChampionsTask(BaseTask):
    id = "village_champions"
    name = "Village Champions (Optimized - Mining S-tier)"
    interval_sec = 1800

    async def execute(self):
        await self.report("Optimizing village champions (mining + S-tier priority)...")
        await self.go_home()

        if await self.tap_template("btn_villages.png"):
            await self.humanizer.medium_delay()

            # Priority: Mining villages first, then S-tier champions
            village_types = ["village_mining.png", "village_farm.png", "village_wood.png"]

            for vtype in village_types:
                matches = self.vision.find_all_templates(vtype, threshold=0.8, max_results=5)
                for match in matches:
                    await self.tap_match(match)
                    await self.humanizer.medium_delay()

                    if await self.tap_template("btn_assign_champion.png", timeout=3):
                        await self.humanizer.short_delay()
                        # Sort by S-tier first
                        if await self.tap_template("champion_s_tier.png", timeout=3):
                            await self.tap_template("btn_confirm.png")
                            await self.report("S-tier champion assigned to mining village")
                        elif await self.tap_template("champion_a_tier.png", timeout=3):
                            await self.tap_template("btn_confirm.png")
                            await self.report("A-tier champion assigned")
                        await self.humanizer.short_delay()
                    await self.back()

            await self.back()


class HallOfValorTask(BaseTask):
    id = "hall_of_valor"
    name = "Hall of Valor Summons"
    interval_sec = 7200  # every 2 hours

    async def execute(self):
        await self.report("Hall of Valor summons...")
        await self.go_home()

        if await self.tap_template("building_hall_valor.png"):
            await self.humanizer.medium_delay()

            # 1. Free hero summon
            if await self.tap_template("btn_free_summon.png", timeout=3):
                await self.humanizer.medium_delay()
                await self.close_popups()
                await self.report("Free hero summon done")

            # 2. Free card summon
            if await self.tap_template("btn_free_card.png", timeout=3):
                await self.humanizer.medium_delay()
                await self.close_popups()
                await self.report("Free card summon done")

            # 3. Use summon stones if available
            if await self.tap_template("btn_stone_summon.png", timeout=3):
                await self.humanizer.short_delay()
                # Check stone balance before summoning
                if self.on_screen("summon_stones_available.png"):
                    await self.tap_template("btn_summon.png")
                    await self.humanizer.medium_delay()
                    await self.close_popups()
                    await self.report("Summon stone used")

            # 4. Use guarantee when charged
            if self.on_screen("guarantee_charged.png"):
                await self.tap_template("btn_guarantee_summon.png", timeout=3)
                await self.humanizer.medium_delay()
                await self.close_popups()
                await self.report("Guarantee summon used!")

            await self.back()


class HeroXPChipsTask(BaseTask):
    id = "hero_xp_chips"
    name = "Hero XP Chips"
    interval_sec = 3600

    async def execute(self):
        await self.report("Using hero XP chips...")
        await self.go_home()

        if await self.tap_template("btn_heroes.png"):
            await self.humanizer.medium_delay()

            # Find heroes that can level up
            if await self.tap_template("hero_level_up.png", timeout=5):
                await self.humanizer.short_delay()
                if await self.tap_template("btn_use_xp.png"):
                    await self.humanizer.short_delay()
                    # Use max XP chips
                    await self.tap_template("btn_max.png")
                    await self.tap_template("btn_confirm.png")
                    await self.report("XP chips applied to hero")

            await self.back()


class RecruitFarmersTask(BaseTask):
    id = "recruit_farmers"
    name = "Recruit Farmers"
    interval_sec = 3600

    async def execute(self):
        await self.report("Recruiting farmers...")
        await self.go_home()

        if await self.tap_template("building_tavern.png"):
            await self.humanizer.medium_delay()

            for _ in range(5):
                if await self.tap_template("btn_recruit.png", timeout=3):
                    await self.humanizer.medium_delay()
                    await self.close_popups()
                    await self.report("Farmer recruited")
                else:
                    break

            await self.back()


class HeroTrainingTask(BaseTask):
    id = "hero_training"
    name = "Hero Training (via Squad Base)"
    interval_sec = 3600

    async def execute(self):
        await self.report("Hero training via squad base...")
        await self.go_home()

        if await self.tap_template("building_squad_base.png"):
            await self.humanizer.medium_delay()

            if await self.tap_template("btn_training.png"):
                await self.humanizer.medium_delay()

                # Assign heroes to training slots
                for _ in range(4):
                    if await self.tap_template("training_slot_empty.png", timeout=3):
                        await self.humanizer.short_delay()
                        await self.tap_template("hero_available.png", timeout=3)
                        await self.tap_template("btn_confirm.png")
                        await self.report("Hero assigned to training")
                    else:
                        break

                # Start training
                if await self.tap_template("btn_start_training.png", timeout=3):
                    await self.report("Training started")

            await self.back()


class TribeGiftsTask(BaseTask):
    id = "tribe_gifts"
    name = "Tribe Gifts"
    interval_sec = 1800

    async def execute(self):
        await self.report("Opening tribe gifts...")
        await self.go_home()

        if await self.tap_template("btn_tribe.png"):
            await self.humanizer.medium_delay()

            if await self.tap_template("tab_gifts.png"):
                await self.humanizer.medium_delay()

                # Open all available gifts
                for _ in range(20):
                    if await self.tap_template("gift_available.png", timeout=2):
                        await self.humanizer.short_delay()
                        await self.tap_template("btn_open.png")
                        await self.humanizer.short_delay()
                        await self.close_popups()
                    else:
                        break

                await self.report("Tribe gifts opened")

            await self.back()


class TribeTechTask(BaseTask):
    id = "tribe_tech"
    name = "Tribe Tech Contribution & R5 Accept"
    interval_sec = 3600

    async def execute(self):
        await self.report("Contributing to tribe tech...")
        await self.go_home()

        if await self.tap_template("btn_tribe.png"):
            await self.humanizer.medium_delay()

            if await self.tap_template("tab_tech.png"):
                await self.humanizer.medium_delay()

                # Contribute to current tech
                if await self.tap_template("btn_contribute.png", timeout=5):
                    await self.humanizer.short_delay()
                    await self.tap_template("btn_confirm.png")
                    await self.report("Tech contribution done")

                # R5 accept (if leader)
                if await self.tap_template("btn_r5_accept.png", timeout=3):
                    await self.humanizer.short_delay()
                    await self.report("R5 accepted")

            await self.back()
