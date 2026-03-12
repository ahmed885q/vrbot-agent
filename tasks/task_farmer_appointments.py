"""Task: Farmer Appointments — Optimized appointments (not random)."""

from tasks.base_task import BaseTask


class TaskFarmerAppointments(BaseTask):
    name = "Farmer Appointments"
    tag = "farmer_appointments"
    cooldown_hours = 6

    def run(self):
        if not self._cooldown_ok():
            return True

        bot = self.bot
        bot.go_to_city()
        bot.wait(2)

        # Open farmer/village panel
        self.log.info("Opening farmer appointments...")
        found = self._find_and_tap(
            "Find the Village or Farm management icon — it may show farmers, "
            "houses, or a village map icon on the right side or bottom toolbar.",
            wait_after=4,
        )
        if not found:
            # Try the Village Hall building
            found = self._find_and_tap(
                "Find the Village Hall or Farmstead building in the city.",
                wait_after=4,
            )

        if not found:
            self.log.info("Farmer panel not found.")
            return True

        # Navigate to appointments tab
        self._find_and_tap(
            "Find an 'Appointment', 'Assign', or 'Manage' tab or button.",
            wait_after=3,
        )

        # Appoint farmers strategically
        appointed = 0
        for _ in range(5):
            # Look for available appointment slot
            ok = self._find_and_tap(
                "Find an empty appointment slot or 'Appoint' button. "
                "Choose the best available farmer (highest quality first).",
                wait_after=3,
            )
            if not ok:
                break

            # Confirm appointment
            self._find_and_tap(
                "Find a 'Confirm', 'Appoint', or 'OK' button (green).",
                wait_after=3,
            )
            appointed += 1
            self._dismiss_popup()
            bot.wait(2)

        if appointed:
            self.log.info(f"✔ Appointed {appointed} farmer(s)!")
        else:
            self.log.info("No appointments available.")

        self._safe_close()
        self._save_cooldown()
        return True
