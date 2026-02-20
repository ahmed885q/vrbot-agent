"""
VRBOT Main - Runs all enabled tasks
"""
import time
from vrbot_core import Bot
from vrbot_config import TASKS_ENABLED

TASK_MAP = {
    "helps": ("tasks.task_helps", "TaskHelps"),
    "tribe_gifts": ("tasks.task_tribe_gifts", "TaskTribeGifts"),
    "mail_rewards": ("tasks.task_mail_rewards", "TaskMailRewards"),
    "daily_gifts": ("tasks.task_daily_gifts", "TaskDailyGifts"),
    "rewards": ("tasks.task_rewards", "TaskRewards"),
    "shield": ("tasks.task_shield", "TaskShield"),
    "construction": ("tasks.task_construction", "TaskConstruction"),
    "research": ("tasks.task_research", "TaskResearch"),
    "train_troops": ("tasks.task_train_troops", "TaskTrainTroops"),
    "prosperity": ("tasks.task_prosperity", "TaskProsperity"),
    "errands": ("tasks.task_errands", "TaskErrands"),
    "commissions": ("tasks.task_commissions", "TaskCommissions"),
    "farmer_appointments": ("tasks.task_farmer_appointments", "TaskFarmerAppointments"),
    "recruit_farmers": ("tasks.task_recruit_farmers", "TaskRecruitFarmers"),
    "village_champions": ("tasks.task_village_champions", "TaskVillageChampions"),
    "hall_of_valor": ("tasks.task_hall_of_valor", "TaskHallOfValor"),
    "hero_xp": ("tasks.task_hero_xp", "TaskHeroXp"),
    "hero_training": ("tasks.task_hero_training", "TaskHeroTraining"),
    "account_items": ("tasks.task_account_items", "TaskAccountItems"),
    "divination": ("tasks.task_divination", "TaskDivination"),
    "smithy": ("tasks.task_smithy", "TaskSmithy"),
    "gather": ("tasks.task_gather", "TaskGather"),
    "niflung": ("tasks.task_niflung", "TaskNiflung"),
    "staging_post": ("tasks.task_staging_post", "TaskStagingPost"),
    "clear_forest": ("tasks.task_clear_forest", "TaskClearForest"),
    "cinderbone": ("tasks.task_cinderbone", "TaskCinderbone"),
    "reclaim_midgard": ("tasks.task_reclaim_midgard", "TaskReclaimMidgard"),
    "leidolf": ("tasks.task_leidolf", "TaskLeidolf"),
    "festival_flames": ("tasks.task_festival_flames", "TaskFestivalFlames"),
    "promo_codes": ("tasks.task_promo_codes", "TaskPromoCodes"),
    "chief_hall": ("tasks.task_chief_hall", "TaskChiefHall"),
    "upgrade_chief_hall": ("tasks.task_upgrade_chief_hall", "TaskUpgradeChiefHall"),
    "expansion": ("tasks.task_expansion", "TaskExpansion"),
    "tribe_tech": ("tasks.task_tribe_tech", "TaskTribeTech"),
    "chapter": ("tasks.task_chapter", "TaskChapter"),
}

TASK_ORDER = [
    # Phase 2: Quick
    "daily_gifts", "rewards", "mail_rewards", "helps", "tribe_gifts",
    # Phase 3: Production
    "construction", "research", "train_troops", "prosperity",
    # Phase 4: Economy
    "errands", "commissions", "farmer_appointments", "recruit_farmers", "village_champions",
    # Phase 5: Heroes
    "hall_of_valor", "hero_xp", "hero_training", "account_items", "divination", "smithy",
    # Phase 6: Combat
    "gather", "niflung", "staging_post", "clear_forest", "cinderbone", "reclaim_midgard",
    # Phase 7: Events
    "leidolf", "festival_flames", "promo_codes",
    # Phase 8: Strategy
    "chief_hall", "upgrade_chief_hall", "expansion", "tribe_tech", "chapter",
    # Last
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
    print("  VRBOT — Starting all tasks")
    print("=" * 60)
    print("  [setup] Navigating to city...")
    bot.go_to_city()
    bot.wait(2)

    results = {}
    for task_name in TASK_ORDER:
        if not TASKS_ENABLED.get(task_name, False):
            print(f"  [skip] {task_name} disabled")
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
    for t, s in results.items():
        print(f"    {t:25s} [{'OK' if s else 'FAIL'}]")
    ok = sum(1 for v in results.values() if v)
    print(f"\n  Total: {ok}/{len(results)} tasks succeeded")
    print("=" * 60)

if __name__ == "__main__":
    main()
