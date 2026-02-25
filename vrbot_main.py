"""
VRBOT Main - Runs all enabled tasks (37 tasks)
"""
import time
from vrbot_core import Bot
from vrbot_config import TASKS_ENABLED

TASK_MAP = {
    # Quick Collections
    "daily_gifts": ("tasks.task_daily_gifts", "TaskDailyGifts"),
    "rewards": ("tasks.task_rewards", "TaskRewards"),
    "mail_rewards": ("tasks.task_mail_rewards", "TaskMailRewards"),
    "helps": ("tasks.task_helps", "TaskHelps"),
    "tribe_gifts": ("tasks.task_tribe_gifts", "TaskTribeGifts"),
    "prosperity": ("tasks.task_prosperity", "TaskProsperity"),

    # Buildings
    "construction": ("tasks.task_construction", "TaskConstruction"),
    "research": ("tasks.task_research", "TaskResearch"),
    "train_troops": ("tasks.task_train_troops", "TaskTrainTroops"),
    "hall_of_valor": ("tasks.task_hall_of_valor", "TaskHallOfValor"),
    "divination": ("tasks.task_divination", "TaskDivination"),
    "smithy": ("tasks.task_smithy", "TaskSmithy"),
    "upgrade_chief_hall": ("tasks.task_upgrade_chief_hall", "TaskUpgradeChiefHall"),
    "chief_hall": ("tasks.task_chief_hall", "TaskChiefHall"),
    "expansion": ("tasks.task_expansion", "TaskExpansion"),

    # Economy
    "errands": ("tasks.task_errands", "TaskErrands"),
    "commissions": ("tasks.task_commissions", "TaskCommissions"),
    "farmer_appointments": ("tasks.task_farmer_appointments", "TaskFarmerAppointments"),
    "recruit_farmers": ("tasks.task_recruit_farmers", "TaskRecruitFarmers"),
    "village_champions": ("tasks.task_village_champions", "TaskVillageChampions"),

    # Heroes
    "hero_xp": ("tasks.task_hero_xp", "TaskHeroXp"),
    "hero_training": ("tasks.task_hero_training", "TaskHeroTraining"),
    "account_items": ("tasks.task_account_items", "TaskAccountItems"),

    # World Map
    "gather": ("tasks.task_gather", "TaskGather"),
    "niflung": ("tasks.task_niflung", "TaskNiflung"),
    "kill_monster": ("tasks.task_kill_monster", "TaskKillMonster"),
    "rally_niflung": ("tasks.task_rally_niflung", "TaskRallyNiflung"),
    "clear_forest": ("tasks.task_clear_forest", "TaskClearForest"),
    "cinderbone": ("tasks.task_cinderbone", "TaskCinderbone"),
    "staging_post": ("tasks.task_staging_post", "TaskStagingPost"),
    "reclaim_midgard": ("tasks.task_reclaim_midgard", "TaskReclaimMidgard"),

    # Events
    "leidolf": ("tasks.task_leidolf", "TaskLeidolf"),
    "festival_flames": ("tasks.task_festival_flames", "TaskFestivalFlames"),
    "chapter": ("tasks.task_chapter", "TaskChapter"),
    "promo_codes": ("tasks.task_promo_codes", "TaskPromoCodes"),

    # Defense
    "shield": ("tasks.task_shield", "TaskShield"),

    # Alliance
    "tribe_tech": ("tasks.task_tribe_tech", "TaskTribeTech"),
}

TASK_ORDER = [
    # Phase 1: Quick Collections (low API cost)
    "daily_gifts", "rewards", "mail_rewards", "helps", "tribe_gifts",

    # Phase 2: Production (building tasks)
    "construction", "research", "train_troops", "prosperity",

    # Phase 3: Economy
    "errands", "commissions", "farmer_appointments", "recruit_farmers", "village_champions",

    # Phase 4: Heroes
    "hall_of_valor", "hero_xp", "hero_training", "account_items", "divination", "smithy",

    # Phase 5: World Map (combat)
    "gather", "niflung", "kill_monster", "staging_post",
    "clear_forest", "cinderbone", "reclaim_midgard",

    # Phase 6: Events
    "leidolf", "festival_flames", "promo_codes", "chapter",

    # Phase 7: Strategy (upgrades)
    "chief_hall", "upgrade_chief_hall", "expansion", "tribe_tech",

    # Phase 8: Rally (alliance)
    "rally_niflung",

    # Last: Defense
    "shield",
]


def run_task(bot, task_name):
    if task_name not in TASK_MAP:
        return None
    module_name, class_name = TASK_MAP[task_name]
    try:
        mod = __import__(module_name, fromlist=[class_name])
        cls = getattr(mod, class_name)
    except Exception as e:
        print(f"  [error] Could not load {task_name}: {e}")
        return False
    print(f"\n  Running: {cls.name}")
    print("=" * 50)
    task = cls(bot)
    try:
        success = task.run()
    except Exception as e:
        print(f"  [error] {task_name} crashed: {e}")
        success = False
    print("=" * 50)
    print(f"  Result: {'OK' if success else 'FAIL'}")
    return success


def main():
    bot = Bot()
    print("=" * 60)
    print(f"  VRBOT — Starting ({sum(1 for v in TASKS_ENABLED.values() if v)} tasks enabled)")
    print("=" * 60)
    print("  [setup] Navigating to city...")
    bot.go_to_city()
    bot.wait(2)

    results = {}
    for task_name in TASK_ORDER:
        if not TASKS_ENABLED.get(task_name, False):
            continue
        if task_name not in TASK_MAP:
            continue
        bot.go_to_city()
        bot.wait(1)
        success = run_task(bot, task_name)
        results[task_name] = success
        bot.task_delay()

    print("\n" + "=" * 60)
    print("  VRBOT — Session Complete")
    print("=" * 60)
    ok = fail = skip = 0
    for t, s in results.items():
        status = "OK" if s else "FAIL"
        if s:
            ok += 1
        else:
            fail += 1
        print(f"    {t:25s} [{status}]")
    print(f"\n  Total: {ok} OK / {fail} FAIL / {len(TASK_ORDER) - len(results)} skipped")
    print("=" * 60)
    bot.print_stats()


if __name__ == "__main__":
    main()
