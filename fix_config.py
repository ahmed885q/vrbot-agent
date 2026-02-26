"""Add 9 missing tasks to vrbot_config.py"""
code = open('vrbot_config.py', encoding='utf-8').read()
new_tasks = ['city_rush','community_events','conquer_island','gather_supplies','market_trade','rebate_pack','surprise_gift','toy_shop','tribe_gold_tile']
added = 0
for t in new_tasks:
    if f'"{t}"' not in code:
        code = code.rstrip()
        # Find last } in TASKS_ENABLED
        idx = code.rfind('}')
        if idx > 0:
            code = code[:idx] + f'    "{t}": False,\n' + code[idx:]
            added += 1
            print(f'  Added: {t}')
    else:
        print(f'  Already exists: {t}')
open('vrbot_config.py', 'w', encoding='utf-8').write(code)
print(f'Done! Added {added} tasks.')
