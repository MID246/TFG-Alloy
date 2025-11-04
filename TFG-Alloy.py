"""TFG alloy finder.

Usage examples (PowerShell):
  cd "C:\Users\mikei\Desktop\MID-Cursor\TFG-Alloy"
  py -3 TFG-Alloy.py                    # runs with packaged `items.py`, default target and ranges
  py -3 TFG-Alloy.py --target 2016 --ranges "{\"Cu\": [0.5,0.65], \"Zn\": [0.2,0.3], \"Bi\": [0.1,0.2]}"
  py -3 TFG-Alloy.py --items-file other_items.py --target 1000 --ranges ranges.json

The script accepts an items file (defaults to `items.py` in the same folder), a numeric
`--target` (total mb goal), and `--ranges` which can be a JSON string or a path to a
JSON file mapping metal symbols to [min_frac, max_frac].
"""

from itertools import combinations
import argparse
import json
import os
import runpy
import sys


def load_items(path):
    # If path is a module file, run it and grab `items` variable
    if os.path.isfile(path):
        ctx = runpy.run_path(path)
        if 'items' in ctx:
            return ctx['items']
        else:
            raise SystemExit(f"Items file {path!r} does not define `items` variable")
    else:
        raise SystemExit(f"Items file {path!r} not found")


def parse_ranges(ranges_arg):
    # if looks like JSON or a file path
    if os.path.isfile(ranges_arg):
        with open(ranges_arg, 'r', encoding='utf-8') as f:
            return json.load(f)
    try:
        return json.loads(ranges_arg)
    except Exception:
        raise SystemExit("Could not parse --ranges. Provide a JSON string or path to a JSON file")


def find_solutions(items, target, ranges, top_n=10):
    # compute absolute min/max mb required per metal
    min_req = {m: int(ranges[m][0]*target) for m in ranges}
    max_req = {m: int(ranges[m][1]*target) for m in ranges}

    solutions = []

    def search_combo(combo):
        n = len(combo)
        max_counts = [c[3] for c in combo]
        mbs = [c[2] for c in combo]
        metals = [c[1] for c in combo]
        # suffix max for pruning (unused currently but kept for possible optimizations)
        suffix_max = [0]*(n+1)
        for i in range(n-1, -1, -1):
            suffix_max[i] = suffix_max[i+1] + max_counts[i]*mbs[i]
        current = [0]*n

        def backtrack(i, metal_totals, total):
            if i == n:
                # require all metals present in ranges
                if all(min_req[m] <= metal_totals.get(m, 0) <= max_req[m] for m in ranges):
                    diff = abs(total - target)
                    abundance = sum((current[j]/combo[j][3]) for j in range(n))
                    solutions.append({
                        "combo": combo.copy(),
                        "counts": current.copy(),
                        "total": total,
                        "metal_totals": metal_totals.copy(),
                        "pct": {m: (metal_totals.get(m,0)/total if total>0 else 0) for m in ranges},
                        "diff": diff,
                        "abundance": abundance
                    })
                return

            # prune: if any metal cannot reach min even with remaining max, stop
            max_possible_per_metal = {m: metal_totals.get(m, 0) for m in ranges}
            for j in range(i, n):
                max_possible_per_metal[combo[j][1]] = max_possible_per_metal.get(combo[j][1], 0) + max_counts[j]*mbs[j]
            for m in ranges:
                if max_possible_per_metal.get(m, 0) < min_req[m]:
                    return
            for m in ranges:
                if metal_totals.get(m, 0) > max_req[m]:
                    return

            item_metal = metals[i]
            item_mb = mbs[i]
            max_c = max_counts[i]
            upper_by_metal = (max_req.get(item_metal, 0) - metal_totals.get(item_metal, 0)) // item_mb
            upper = min(max_c, upper_by_metal)
            if upper < 0:
                return
            for c in range(0, upper+1):
                current[i] = c
                metal_totals[item_metal] = metal_totals.get(item_metal, 0) + c * item_mb
                backtrack(i+1, metal_totals, total + c*item_mb)
                metal_totals[item_metal] -= c * item_mb
                if metal_totals[item_metal] == 0:
                    metal_totals.pop(item_metal, None)
                current[i] = 0

        backtrack(0, {}, 0)

    # search combos of size 3 and 4 that include the metals in ranges
    idxs = range(len(items))
    required_metals = set(ranges.keys())
    for r in (3,4):
        for combo_idx in combinations(idxs, r):
            combo = [items[i] for i in combo_idx]
            metals_in_combo = set(c[1] for c in combo)
            if not required_metals.issubset(metals_in_combo):
                continue
            search_combo(combo)

    # sort by closeness to target then by abundance preference
    solutions_sorted = sorted(solutions, key=lambda s: (s["diff"], s["abundance"], len(s["combo"]), -s["total"]))
    return solutions_sorted[:top_n], len(solutions)


def main(argv=None):
    p = argparse.ArgumentParser(description="TFG alloy finder: find item combos matching metal % ranges")
    default_items = os.path.join(os.path.dirname(__file__), 'items.py')
    p.add_argument('--items-file', default=default_items, help='path to a .py file that defines `items` variable')
    p.add_argument('--target', type=int, default=2016, help='target total mb (integer)')
    p.add_argument('--ranges', type=str, default='{"Cu": [0.5,0.65], "Zn": [0.2,0.3], "Bi": [0.1,0.2]}',
                   help='JSON string or path to JSON file mapping metal to [min_frac, max_frac]')
    p.add_argument('--show-top', type=int, default=10, help='how many top results to show')
    args = p.parse_args(argv)

    items = load_items(args.items_file)
    ranges = parse_ranges(args.ranges)

    solutions, total_count = find_solutions(items, args.target, ranges, top_n=args.show_top)

    print(f"Found {total_count} valid solutions. Showing top {len(solutions)}:")
    for sol in solutions:
        items_str = ", ".join(f"{sol['combo'][i][0]} x{sol['counts'][i]}" for i in range(len(sol['combo'])))
        # show percentages for requested metals
        pct_parts = " ".join(f"{m} {sol['pct'][m]*100:.2f}%" for m in ranges)
        print(f"{items_str} | Total {sol['total']} mb | {pct_parts} | diff {sol['diff']} | abundance {sol['abundance']:.3f}")


if __name__ == '__main__':
    main()

