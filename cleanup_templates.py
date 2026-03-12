"""
VRBOT Template Cleanup
======================
- Keep best 1-2 variants per class
- Remove irrelevant event buttons (change frequently, not useful)
- Pre-compute grayscale cache for speed
"""
import os, shutil, collections
from PIL import Image
import numpy as np

TEMPLATE_DIR = "templates"
BACKUP_DIR = "templates_backup_330"

# Templates the bot ACTUALLY needs (buttons it clicks)
ESSENTIAL = {
    # Navigation buttons
    "close_btn", "back_btn", "ok_btn", "confirm_btn", "cancel_btn",
    # Action buttons
    "claim_btn", "claim_all_btn", "upgrade_btn", "train_btn",
    "speed_up_btn", "attack_btn", "gather_btn", "march_btn",
    "donate_btn", "heal_btn", "recruit_btn", "submit_btn",
    # Navigation icons
    "mail_icon", "mail_btn", "alliance_icon", "alliance_btn",
    "hero_icon", "hero_btn", "quests_icon", "quests_btn",
    "quest_icon", "shop_icon", "shop_btn",
    "city_icon", "world_botn", "settings_btn", "chat_btn",
    # Specific game buttons
    "niflungs", "exit_btn", "resources_btn",
    # Reference templates (from other bots - useful for cross-matching)
    "ref_vr_close", "ref_vr_back", "ref_vr_confirm", "ref_vr_cancel",
    "ref_vr_green_btn", "ref_attack_btn", "ref_gather_btn",
    "ref_claim_btn", "ref_confirm_btn", "ref_train_btn",
    "ref_speedup_btn", "ref_donate_btn", "ref_return_btn",
    "ref_open_btn", "ref_daily_claim", "ref_alliance_claim",
    "ref_search_btn", "ref_scout_btn", "ref_explore_btn",
    "ref_recommend_btn",
    "ref_home_btn", "ref_home_btn_0", "ref_map_btn", "ref_map_btn_0",
    "ref_menu_btn", "ref_march_bar",
    "ref_vr_arrow", "ref_heal_icon", "ref_barracks_icon", "ref_archery_icon",
}

# Templates to DELETE (game event buttons that change, not useful)
REMOVE_PREFIXES = [
    "battle_of_the_ruins",  # event button
    "valhalla_drill",       # event button
    "picks_btn",            # event button
    "event_hub_btn",        # event button (changes)
    "mall_btn",             # shop button (16 variants!)
    "sworn_vengeance",      # event button
    "hero_reclamation",     # event button
    "tap_here_go",          # event button
    "event_info",           # event detail
    "unclaimed_rewards",    # event specific
    "great_event",          # event specific
    "chronicles_rewards",   # event specific
    "ultimate_might",       # event specific
    "event_information",    # event specific
    "highlight_event",      # event specific
    "battle_icon",          # event icon
    "valhalla_drill_icon",  # event icon
    "picks_icon",           # event icon
    "resource_bar_gold",    # too specific
    "resource_bar_red",     # too specific
    "resource_icon",        # generic, not useful
    "popup_chat",           # too large
    "tribe_leader_icon",    # not clickable
    "notifications_icon",   # not useful
    "leader_icon",          # not useful
    "group_chat_icon",      # not useful
    "system_tab",           # mail tabs (too specific)
    "personal_tab",
    "tribe_tab",
    "kingdom_tab",
    "sent_tab",
    "favorites_tab",
    "cold_main_btn",        # unknown
    "pick_btn",             # event
]

def get_base_name(filename):
    """Get base name without _N suffix and extension."""
    base = filename.rsplit(".", 1)[0]
    parts = base.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return base

def should_remove(base_name):
    """Check if template should be removed."""
    for prefix in REMOVE_PREFIXES:
        if base_name.startswith(prefix):
            return True
    return False

def pick_best(variants):
    """Pick 1-2 best variants from a group.
    Prefer: medium size (40-100px), not too small, not too large.
    """
    # Sort by how close to ideal size (60x50)
    ideal_area = 60 * 50  # 3000px²
    scored = []
    for cat, fname, w, h, area in variants:
        # Penalize too small (< 30px) and too large (> 200px)
        size_score = 1.0
        if w < 30 or h < 25:
            size_score = 0.3
        elif w > 200 or h > 150:
            size_score = 0.5
        
        area_diff = abs(area - ideal_area) / ideal_area
        score = size_score / (1 + area_diff)
        scored.append((score, cat, fname, w, h))
    
    scored.sort(key=lambda x: -x[0])
    
    # Keep best 1, or 2 if they're different sizes (for multi-scale matching)
    keep = [scored[0]]
    if len(scored) > 1:
        best_w, best_h = scored[0][3], scored[0][4]
        for s in scored[1:]:
            sw, sh = s[3], s[4]
            # Keep second if significantly different size
            if abs(sw - best_w) > 20 or abs(sh - best_h) > 20:
                keep.append(s)
                break
    
    return [(cat, fname) for _, cat, fname, _, _ in keep]


def cleanup():
    print("=" * 60)
    print("  TEMPLATE CLEANUP")
    print("=" * 60)
    
    # Backup first
    if not os.path.exists(BACKUP_DIR):
        print(f"\n  📦 Backing up to {BACKUP_DIR}/...")
        shutil.copytree(TEMPLATE_DIR, BACKUP_DIR)
        print(f"  ✅ Backup complete")
    else:
        print(f"\n  📦 Backup already exists: {BACKUP_DIR}/")
    
    # Scan all templates
    groups = collections.defaultdict(list)
    all_files = []
    
    for cat in os.listdir(TEMPLATE_DIR):
        cat_path = os.path.join(TEMPLATE_DIR, cat)
        if not os.path.isdir(cat_path):
            continue
        for f in os.listdir(cat_path):
            if not f.endswith('.png'):
                continue
            path = os.path.join(cat_path, f)
            img = Image.open(path)
            w, h = img.size
            base = get_base_name(f)
            groups[base].append((cat, f, w, h, w * h))
            all_files.append((cat, f, base))
    
    print(f"\n  Before: {len(all_files)} files, {len(groups)} unique names")
    
    # Decide what to keep
    keep_set = set()  # (cat, filename)
    remove_list = []
    
    for base_name, variants in groups.items():
        # Remove irrelevant templates
        if should_remove(base_name):
            for cat, f, w, h, area in variants:
                remove_list.append((cat, f, "irrelevant"))
            continue
        
        # For essential or useful templates, pick best variants
        best = pick_best(variants)
        for cat, f in best:
            keep_set.add((cat, f))
        
        # Mark rest for removal
        for cat, f, w, h, area in variants:
            if (cat, f) not in keep_set:
                remove_list.append((cat, f, "duplicate"))
    
    # Execute removals
    removed = 0
    print(f"\n  🗑️  Removing {len(remove_list)} templates:")
    
    reasons = collections.Counter()
    for cat, f, reason in remove_list:
        path = os.path.join(TEMPLATE_DIR, cat, f)
        if os.path.exists(path):
            os.remove(path)
            removed += 1
            reasons[reason] += 1
    
    for reason, count in reasons.items():
        print(f"    {reason}: {count}")
    
    # Clean empty directories
    for cat in os.listdir(TEMPLATE_DIR):
        cat_path = os.path.join(TEMPLATE_DIR, cat)
        if os.path.isdir(cat_path):
            remaining = [f for f in os.listdir(cat_path) if f.endswith('.png')]
            if not remaining:
                shutil.rmtree(cat_path)
                print(f"    Removed empty dir: {cat}/")
    
    # Print final inventory
    print(f"\n  ✅ Removed {removed} files")
    print(f"\n{'='*60}")
    print("  FINAL INVENTORY")
    print("=" * 60)
    
    total = 0
    for cat in sorted(os.listdir(TEMPLATE_DIR)):
        cat_path = os.path.join(TEMPLATE_DIR, cat)
        if not os.path.isdir(cat_path):
            continue
        files = sorted([f for f in os.listdir(cat_path) if f.endswith('.png')])
        if files:
            print(f"\n  📁 {cat}/ ({len(files)})")
            for f in files:
                img = Image.open(os.path.join(cat_path, f))
                print(f"    {f}: {img.size[0]}x{img.size[1]}")
                total += 1
    
    print(f"\n  TOTAL: {total} templates (was 330)")
    print(f"\n  Backup at: {BACKUP_DIR}/ (restore with: shutil.copytree)")


if __name__ == "__main__":
    cleanup()
