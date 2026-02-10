"""
VRBOT Agent — Economy Tasks
Errands, Farmer management, Village Champions, Staging Post, Commissions.
"""
import time
import logging
from tasks import BaseTask

log = logging.getLogger("vrbot.tasks.economy")


class ErrandsTask(BaseTask):
    task_id = "errands"
    task_name = "Complete Errands"
    priority = 3
    category = "economy"
    estimated_time = 30

    def run(self, overrides):
        """Complete available errands for rewards."""
        # Open errands panel
        if not self._safe_tap("btn_errands", timeout=5):
            # Try finding through city hall or main UI
            if self._safe_tap("building_city_hall", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("tab_errands", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    return True
            else:
                return True

        self.human.delay("normal")

        completed = 0
        max_errands = overrides.get("max_errands", 10)

        for _ in range(max_errands):
            # Find available errand
            errand = self.vision.find("btn_errand_start", threshold=0.75)
            if not errand:
                # Try claim completed errands first
                if self.vision.tap_on("btn_errand_claim", wait=False, timeout=2):
                    self.human.delay("fast")
                    completed += 1
                    continue
                break

            x, y, conf = errand
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("fast")

            # Confirm start
            if self.vision.tap_on("btn_confirm", wait=False, timeout=3):
                self.human.delay("normal")
                completed += 1

        # Claim all completed errands
        for _ in range(5):
            if not self.vision.tap_on("btn_errand_claim", wait=False, timeout=1):
                break
            self.human.delay("fast")
            completed += 1

        log.info(f"Errands completed/claimed: {completed}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class FarmerAppointmentsTask(BaseTask):
    task_id = "farmer_appointments"
    task_name = "Farmer Appointments (Optimized)"
    priority = 2
    category = "economy"
    estimated_time = 35

    def run(self, overrides):
        """
        Manage farmer appointments with optimized scheduling.
        NOT random — prioritizes based on:
        1. Expiring appointments first
        2. Highest yield farmers
        3. Resource need balance
        """
        # Open farmer management
        if not self._safe_tap("btn_farmer_manage", timeout=5):
            if self._safe_tap("building_farm_house", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("tab_appointments", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    return True
            else:
                return True

        self.human.delay("normal")

        # Step 1: Collect completed appointments
        collected = 0
        for _ in range(10):
            if self.vision.tap_on("btn_collect_appointment", wait=False, timeout=1):
                self.human.delay("fast")
                collected += 1
            else:
                break

        log.info(f"Collected {collected} farmer appointments")

        # Step 2: Start new appointments (priority order)
        # Priority: food > wood > stone > iron (based on typical needs)
        appointment_priority = overrides.get("priority_order", ["food", "wood", "stone", "iron"])
        started = 0

        for resource in appointment_priority:
            # Find empty appointment slot
            slot = self.vision.find("slot_appointment_empty", threshold=0.75)
            if not slot:
                break

            x, y, conf = slot
            self.adb.tap(x, y, offset=self.human.pixel_offset)
            self.human.delay("fast")

            # Select farmer with highest yield for this resource
            if self._safe_tap(f"farmer_best_{resource}", timeout=3):
                self.human.delay("fast")

                # Confirm appointment
                if self._safe_tap("btn_appoint", timeout=3):
                    self.human.delay("normal")
                    started += 1
                    log.info(f"Appointed farmer for {resource}")

        log.info(f"Farmer appointments: collected {collected}, started {started}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class RecruitFarmersTask(BaseTask):
    task_id = "recruit_farmers"
    task_name = "Recruit Farmers"
    priority = 4
    category = "economy"
    estimated_time = 20

    def run(self, overrides):
        """Recruit new farmers when slots available."""
        # Open farmer recruitment
        if not self._safe_tap("btn_recruit_farmer", timeout=5):
            if self._safe_tap("building_farm_house", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("tab_recruit", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    return True
            else:
                return True

        self.human.delay("normal")

        # Check for free recruitment
        recruited = 0
        if self.vision.tap_on("btn_free_recruit", wait=False, timeout=3):
            self.human.delay("normal")
            # Confirm
            self.vision.tap_on("btn_confirm", wait=False, timeout=3)
            self.human.delay("normal")
            recruited += 1
            log.info("Free farmer recruited")

        # Check for recruitable using resources
        max_recruits = overrides.get("max_recruits", 2)
        for _ in range(max_recruits):
            if self.vision.tap_on("btn_recruit_resource", wait=False, timeout=2):
                self.human.delay("fast")
                self.vision.tap_on("btn_confirm", wait=False, timeout=3)
                self.human.delay("normal")
                recruited += 1

        log.info(f"Farmers recruited: {recruited}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class VillageChampionsTask(BaseTask):
    task_id = "village_champions"
    task_name = "Village Champions (Optimized)"
    priority = 3
    category = "economy"
    estimated_time = 45

    def run(self, overrides):
        """
        Manage village champions with optimization:
        - Favor mining villages
        - S-tier heroes assigned first
        - Balanced distribution
        """
        # Priority tiers for hero assignment
        hero_priority = overrides.get("hero_tiers", ["S", "A", "B"])
        favor_mining = overrides.get("favor_mining", True)

        # Open village management
        if not self._safe_tap("btn_village_manage", timeout=5):
            if self._safe_tap("btn_world_map", timeout=3):
                self.human.delay("fast")
                if not self._safe_tap("btn_my_villages", timeout=3):
                    self._safe_tap("btn_main_city", timeout=3)
                    return True
            else:
                return True

        self.human.delay("normal")

        assigned = 0

        # Step 1: Collect completed champion rewards
        for _ in range(10):
            if self.vision.tap_on("btn_champion_collect", wait=False, timeout=1):
                self.human.delay("fast")

        # Step 2: Find villages needing champions
        # Mining villages first if favor_mining enabled
        village_types = ["mining", "lumber", "farm", "stone"] if favor_mining else ["farm", "lumber", "mining", "stone"]

        for v_type in village_types:
            villages = self.vision.find_all(f"village_{v_type}_empty", threshold=0.70, max_results=5)

            for vx, vy, vconf in villages:
                self.adb.tap(vx, vy, offset=self.human.pixel_offset)
                self.human.delay("fast")

                # Assign champion tab
                if self._safe_tap("btn_assign_champion", timeout=3):
                    self.human.delay("fast")

                    # Try highest tier hero first
                    hero_assigned = False
                    for tier in hero_priority:
                        if self.vision.tap_on(f"hero_tier_{tier}_available", wait=False, timeout=2):
                            self.human.delay("fast")
                            if self._safe_tap("btn_assign_confirm", timeout=3):
                                self.human.delay("normal")
                                assigned += 1
                                hero_assigned = True
                                log.info(f"Assigned {tier}-tier hero to {v_type} village")
                                break

                    if not hero_assigned:
                        self._safe_tap("btn_close_x", timeout=2)

        log.info(f"Village champions assigned: {assigned}")
        self._safe_tap("btn_close_x", timeout=3)
        self._safe_tap("btn_main_city", timeout=3)
        return True


class StagingPostTask(BaseTask):
    task_id = "staging_post"
    task_name = "Staging Post (Skip Red Battle)"
    priority = 4
    category = "economy"
    estimated_time = 25

    def run(self, overrides):
        """
        Complete staging post tasks EXCEPT red battle icons.
        Collect rewards, send caravans, manage supplies.
        """
        skip_battle = overrides.get("skip_red_battle", True)

        # Open staging post
        if not self._safe_tap("building_staging_post", timeout=5):
            return True

        self.human.delay("normal")

        completed = 0

        # Collect ready rewards first
        for _ in range(5):
            if self.vision.tap_on("btn_staging_collect", wait=False, timeout=1):
                self.human.delay("fast")
                completed += 1

        # Find available tasks
        tasks = self.vision.find_all("btn_staging_task", threshold=0.70, max_results=8)

        for tx, ty, tconf in tasks:
            # Check if this is a red battle icon — skip it
            if skip_battle:
                # Check area around the task for red/battle indicator
                region = (tx - 40, ty - 40, 80, 80)
                if self.vision.exists("icon_staging_battle", region=region):
                    log.debug("Skipping red battle staging task")
                    continue

            self.adb.tap(tx, ty, offset=self.human.pixel_offset)
            self.human.delay("fast")

            # Start task
            if self.vision.tap_on("btn_staging_start", wait=False, timeout=3):
                self.human.delay("normal")
                completed += 1

            # Or send caravan
            if self.vision.tap_on("btn_send_caravan", wait=False, timeout=2):
                self.human.delay("fast")
                if self._safe_tap("btn_confirm", timeout=3):
                    self.human.delay("normal")
                    completed += 1

        log.info(f"Staging post tasks: {completed}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


class CommissionsTask(BaseTask):
    task_id = "commissions"
    task_name = "Commissions"
    priority = 5
    category = "economy"
    estimated_time = 25

    def run(self, overrides):
        """Complete commissions (exploration coming soon)."""
        # Open commissions
        if not self._safe_tap("btn_commissions", timeout=5):
            if self._safe_tap("building_tavern", timeout=5):
                self.human.delay("fast")
                if not self._safe_tap("tab_commissions", timeout=3):
                    self._safe_tap("btn_close_x", timeout=3)
                    return True
            else:
                return True

        self.human.delay("normal")

        completed = 0

        # Collect completed commissions
        for _ in range(5):
            if self.vision.tap_on("btn_commission_collect", wait=False, timeout=1):
                self.human.delay("fast")
                completed += 1

        # Start new available commissions
        for _ in range(5):
            if self.vision.tap_on("btn_commission_start", wait=False, timeout=2):
                self.human.delay("fast")

                # Select heroes for commission
                if self._safe_tap("btn_auto_select_heroes", timeout=3):
                    self.human.delay("fast")

                # Dispatch
                if self._safe_tap("btn_dispatch", timeout=3):
                    self.human.delay("normal")
                    completed += 1

        log.info(f"Commissions: {completed}")
        self._safe_tap("btn_close_x", timeout=3)
        return True


# ─── Export ───────────────────────────────────────────────────

ECONOMY_TASKS = [
    ErrandsTask,
    FarmerAppointmentsTask,
    RecruitFarmersTask,
    VillageChampionsTask,
    StagingPostTask,
    CommissionsTask,
]

