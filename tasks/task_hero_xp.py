"""Task: Hero XP — Open hero list → level up heroes
Cooldown: 12 hours
"""
from tasks.base_task import BaseTask

HERO_BTN = (1060, 665)


class TaskHeroXp(BaseTask):
    name = "Hero XP"
    tag = "hero_xp"
    cooldown_hours = 12

    def run(self):
        if not self._cooldown_ok():
            return True

        self.bot.go_to_city()
        self.bot.wait(2)

        self.log.info("Opening hero list...")
        self._tap_ui(None, fallback_xy=HERO_BTN, ai_prompt="Find the Hero button on the bottom toolbar", wait_after=4)

        # Find a hero with available XP/level up
        leveled = 0
        for i in range(3):
            self.log.info(f"Looking for hero to level up ({i + 1})...")
            found = self._find_and_tap(
                "You are on a hero list or hero details screen. "
                "Find a hero with a Level Up button, green arrow, "
                "or 'Add XP' option. Look for any highlighted hero.",
                wait_after=3,
            )
            if found:
                # Try to level up
                lv = self._find_and_tap(
                    "Find a Level Up, Add XP, or Enhance button.",
                    wait_after=2,
                )
                if lv:
                    leveled += 1
                    self._dismiss_popup()  # dismiss
                    bot.wait(2)
                bot.adb_back()
                bot.wait(2)
            else:
                break

        if leveled:
            self.log.info(f"✔ Leveled {leveled} hero(s)!")
        else:
            self.log.info("No heroes to level up.")

        self._safe_close()
        self._save_cooldown()
        return True
