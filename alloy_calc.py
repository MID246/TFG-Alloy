"""
Alloy material calculator.

Features added:
- Loads items from a JSON file (`items.json`). Items can contain per-element composition.
- Loads named recipes from a JSON file (`recipes.json`) and/or accept inline CLI recipe definitions.
- CLI options to add single-element items at runtime.
- Heavily prefer overshooting (can be toggled with --prefer-overshoot).

Run examples:
  python alloy_calc.py --items-file items.json --recipes-file recipes.json --target-recipe bismuth_bronze --prefer-overshoot

Item JSON format (array of objects):
  [
    {"name":"Purified Copper Ore","mass_mb":100,"available":27,"composition":{"Cu":1.0}},
    ...
  ]

Recipe JSON format (object):
  {"bismuth_bronze": {"Cu": [0.50,0.65], "Zn": [0.20,0.30], "Bi": [0.10,0.20]}}

"""

import argparse
import json
import os
from itertools import combinations


def load_items(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    items = []
    for it in data:
        name = it.get('name')
        mass = float(it.get('mass_mb'))
        available = int(it.get('available', 0))
        comp = it.get('composition', {})
        # normalize composition to sum to 1 if numeric
        total_frac = sum(comp.values()) if comp else 0
        if total_frac > 0:
            comp = {k: float(v) / total_frac for k, v in comp.items()}
        items.append({'name': name, 'mass': mass, 'available': available, 'comp': comp})
    return items


def load_recipes(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_recipe_string(s):
    # Format: Cu:0.50-0.65;Zn:0.20-0.30;Bi:0.10-0.20
    bounds = {}
    if not s:
        return bounds
    parts = s.split(';')
    for p in parts:
        if not p.strip():
            continue
        k, rng = p.split(':')
        lo, hi = rng.split('-')
        bounds[k.strip()] = (float(lo), float(hi))
    return bounds


def compute_percentages(mass_by_element, total_mass, elements):
    return {el: (mass_by_element.get(el, 0.0) / total_mass) for el in elements}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--items-file', default='items.json', help='Path to items JSON (default: items.json)')
    parser.add_argument('--recipes-file', default='recipes.json', help='Path to recipes JSON (default: recipes.json)')
    parser.add_argument('-t', '--target', '--target-mb', dest='target', type=float, help='Target mass in mb')
    parser.add_argument('--allowance', type=float, default=144.0, help='Allowed +/- mass tolerance (default: 144)')
    parser.add_argument('--max-types', type=int, default=4, help='Max distinct item types to use (default: 4)')
    parser.add_argument('--top', type=int, default=1, help='How many top solutions to print (default: 1)')
    # prefer_overshoot default True; provide --no-prefer-overshoot to disable
    parser.add_argument('--prefer-overshoot', dest='prefer_overshoot', action='store_true', help='Prefer overshooting the target (default: enabled)')
    parser.add_argument('--no-prefer-overshoot', dest='prefer_overshoot', action='store_false', help='Do not prefer overshoot')
    parser.set_defaults(prefer_overshoot=True)
    parser.add_argument('--add-item', action='append', help="Add single-element item: 'Name,mass,available,Element' (can be repeated)")
    parser.add_argument('--recipe', help="Inline recipe bounds: Cu:0.50-0.65;Zn:0.20-0.30;Bi:0.10-0.20")
    parser.add_argument('--target-recipe', help='Name of recipe in recipes file to use')
    args = parser.parse_args()

    items = load_items(args.items_file)
    recipes = load_recipes(args.recipes_file)

    # process add-item CLI
    if args.add_item:
        for s in args.add_item:
            parts = [p.strip() for p in s.split(',')]
            if len(parts) >= 4:
                name = parts[0]
                mass = float(parts[1])
                available = int(parts[2])
                elem = parts[3]
                items.append({'name': name, 'mass': mass, 'available': available, 'comp': {elem: 1.0}})
            else:
                print(f"Ignored malformed --add-item entry: {s}")

    TARGET_MB = args.target
    ALLOWANCE_MB = args.allowance
    MIN_TOTAL = TARGET_MB - ALLOWANCE_MB
    MAX_TOTAL = TARGET_MB + ALLOWANCE_MB

    # Choose composition bounds
    if args.target_recipe:
        if args.target_recipe in recipes:
            COMPOSITION_BOUNDS = {k: tuple(v) for k, v in recipes[args.target_recipe].items()}
        else:
            print(f"Recipe '{args.target_recipe}' not found in {args.recipes_file}. Exiting.")
            return
    elif args.recipe:
        COMPOSITION_BOUNDS = parse_recipe_string(args.recipe)
    else:
        # default bismuth bronze
        COMPOSITION_BOUNDS = {'Cu': (0.50, 0.65), 'Zn': (0.20, 0.30), 'Bi': (0.10, 0.20)}

    elements = sorted(list({e for e in COMPOSITION_BOUNDS.keys()}))

    # Filter items to only those that contain at least one element in the recipe
    filtered_items = [it for it in items if any(k in it.get('comp', {}) for k in COMPOSITION_BOUNDS.keys())]
    if not filtered_items:
        # If no items match the recipe elements, fall back to full list
        filtered_items = items
    ITEMS = filtered_items
    item_index = list(range(len(ITEMS)))

    best_solutions = []

    # DFS search over combinations of up to max types
    for r in range(1, args.max_types + 1):
        for combo in combinations(item_index, r):
            # order by mass desc for pruning
            combo_sorted = sorted(combo, key=lambda i: -ITEMS[i]['mass'])

            # Precompute remaining mass and per-element max-available mass from each position
            n = len(combo_sorted)
            rem_mass_from = [0.0] * (n + 1)
            rem_elem_from = [dict() for _ in range(n + 1)]
            for i in range(n - 1, -1, -1):
                idx_i = combo_sorted[i]
                it = ITEMS[idx_i]
                m_total = it['mass'] * it['available']
                rem_mass_from[i] = rem_mass_from[i + 1] + m_total
                # copy next dict then add this item's contributions
                d = rem_elem_from[i + 1].copy()
                for el, frac in it.get('comp', {}).items():
                    d[el] = d.get(el, 0.0) + it['mass'] * it['available'] * frac
                rem_elem_from[i] = d

            def dfs(pos, curr_counts, curr_mass, mass_by_element):
                # prune large overshoot
                if curr_mass > MAX_TOTAL:
                    return

                # Prune if even using all remaining items we can't reach the minimum total mass
                if curr_mass + rem_mass_from[pos] < MIN_TOTAL:
                    return

                # Prune by checking per-element achievable fractions using remaining max contributions.
                # If even the maximum achievable fraction for an element is below its lower bound,
                # or the minimum achievable fraction (if no further contributions) is above its upper bound,
                # then it's impossible to satisfy composition bounds from this state.
                max_possible_total = curr_mass + rem_mass_from[pos]
                if max_possible_total <= 0.0:
                    return
                for el, (lo, hi) in COMPOSITION_BOUNDS.items():
                    curr_elem = mass_by_element.get(el, 0.0)
                    rem_elem_max = rem_elem_from[pos].get(el, 0.0)
                    # maximum fraction achievable if all remaining contributing mass for this element is used
                    max_fraction = (curr_elem + rem_elem_max) / max_possible_total
                    # minimum fraction achievable (assume remaining contributes none for this element)
                    min_fraction = curr_elem / max_possible_total
                    if max_fraction + 1e-12 < lo or min_fraction - 1e-12 > hi:
                        return
                if pos == len(combo_sorted):
                    if curr_mass < MIN_TOTAL or curr_mass > MAX_TOTAL:
                        return
                    # avoid division by zero for empty selections
                    if curr_mass <= 0.0:
                        return
                    perc = compute_percentages(mass_by_element, curr_mass, elements)
                    ok = True
                    for el, (lo, hi) in COMPOSITION_BOUNDS.items():
                        v = perc.get(el, 0.0)
                        if v < lo - 1e-9 or v > hi + 1e-9:
                            ok = False
                            break
                    if not ok:
                        return
                    # scarcity score: sum(cnt/available)
                    scarcity = 0.0
                    for idx, cnt in zip(combo_sorted, curr_counts):
                        available = ITEMS[idx]['available']
                        scarcity += (cnt / available) if available > 0 else float('inf')
                    diff = abs(curr_mass - TARGET_MB)
                    # heavily prefer overshoot if enabled
                    if args.prefer_overshoot:
                        if curr_mass >= TARGET_MB:
                            score = diff * 0.5
                        else:
                            score = diff * 2.0
                    else:
                        score = diff
                    best_solutions.append({
                        'combo': combo_sorted.copy(),
                        'counts': curr_counts.copy(),
                        'total_mass': curr_mass,
                        'percentages': perc,
                        'diff': diff,
                        'scarcity': scarcity,
                        'score': score,
                    })
                    return

                idx = combo_sorted[pos]
                item = ITEMS[idx]
                mass_per_item = item['mass']
                available = item['available']
                # max count by mass remaining
                max_possible_by_mass = int((MAX_TOTAL - curr_mass) // mass_per_item) if mass_per_item > 0 else available
                max_count = min(available, max_possible_by_mass)

                # iterate counts (try larger first to encourage overshoot combination)
                for cnt in range(max_count, -1, -1):
                    new_mass = curr_mass + cnt * mass_per_item
                    # update mass_by_element with composition fractions
                    if cnt > 0 and item['comp']:
                        for el, frac in item['comp'].items():
                            mass_by_element[el] = mass_by_element.get(el, 0.0) + cnt * mass_per_item * frac
                    curr_counts.append(cnt)
                    dfs(pos + 1, curr_counts, new_mass, mass_by_element)
                    curr_counts.pop()
                    if cnt > 0 and item['comp']:
                        for el, frac in item['comp'].items():
                            mass_by_element[el] -= cnt * mass_per_item * frac

            dfs(0, [], 0.0, {})

    # sort by (score, scarcity)
    best_solutions_sorted = sorted(best_solutions, key=lambda s: (s['score'], s['scarcity']))

    if not best_solutions_sorted:
        print(f"No solutions found within +/-{ALLOWANCE_MB} mb that satisfy composition bounds.")
        return

    print(f"Found {len(best_solutions_sorted)} candidate(s). Showing top {min(args.top, len(best_solutions_sorted))}:\n")
    for i, sol in enumerate(best_solutions_sorted[:args.top], 1):
        print(f"Solution #{i}: total_mass = {sol['total_mass']:.1f} mb (diff {sol['diff']:.1f})  score={sol['score']:.3f}")
        print(f"  scarcity score: {sol['scarcity']:.4f}")
        print("  Breakdown:")
        for idx, cnt in zip(sol['combo'], sol['counts']):
            if cnt == 0:
                continue
            item = ITEMS[idx]
            comp_str = ", ".join([f"{k}:{v:.2f}" for k, v in item['comp'].items()]) if item['comp'] else '[]'
            print(f"    - {item['name']}: {cnt} x {item['mass']} mb = {cnt*item['mass']} mb  (comp: {comp_str}; available {item['available']})")
        perc = sol['percentages']
        perc_str = ", ".join([f"{el}: {perc.get(el,0.0)*100:.2f}%" for el in elements])
        print(f"  Percentages: {perc_str}\n")


if __name__ == '__main__':
    main()
