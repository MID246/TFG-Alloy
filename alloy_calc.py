import json
from itertools import combinations

def load_items(path="items.json"):
    with open(path, "r") as f:
        return json.load(f)

def get_ranges():
    print("Enter metal composition ranges (fractions or percentages).")
    print("Example: Cu 50-65, Zn 20-30, Bi 10-20")
    ranges = {}
    while True:
        entry = input("Metal range (or blank to finish): ").strip()
        if not entry:
            break
        try:
            metal, rng = entry.split()
            low, high = [float(x.strip("%"))/100 for x in rng.split("-")]
            ranges[metal.capitalize()[:2]] = (low, high)
        except Exception:
            print("Invalid format. Try again (e.g. Cu 50-65).")
    return ranges

def search_alloys(items, target, ranges):
    metals = set(ranges.keys())
    min_req = {m: ranges[m][0]*target for m in metals}
    max_req = {m: ranges[m][1]*target for m in metals}

    solutions = []

    def backtrack(combo, i, current, totals, total_mb):
        if i == len(combo):
            if all(min_req[m] <= totals[m] <= max_req[m] for m in metals):
                # Prefer overshoot: penalize undershoot more heavily
                if total_mb < target:
                    diff = (target - total_mb) * 10  # strong penalty for undershooting
                else:
                    diff = total_mb - target  # smaller penalty for overshoot
                solutions.append((combo.copy(), current.copy(), total_mb, totals.copy(), diff))
            return

        name, metal, mb, count = combo[i]
        if metal not in metals:
            backtrack(combo, i+1, current, totals, total_mb)
            return

        for c in range(count+1):
            new_totals = totals.copy()
            new_totals[metal] += c * mb
            new_total_mb = total_mb + c * mb

            # pruning
            if new_total_mb > target * 1.5:
                break  # prune far overshoots

            if i == len(combo) - 1 and new_total_mb < target:
                continue  # don't keep undershoot results

            if any(new_totals[m] > max_req[m] for m in metals):
                break

            current[i] = c
            backtrack(combo, i+1, current, new_totals, new_total_mb)
            current[i] = 0

    # combos of 3–4 items (can increase upper bound if needed)
    for r in range(1, 5):
        for combo in combinations(items, r):
            if metals.issubset(set(i["metal"] for i in combo)):
                backtrack(combo, 0, [0]*len(combo), {m: 0 for m in metals}, 0)

    return sorted(solutions, key=lambda s: s[4])

def main():
    items = load_items()
    target = float(input("Target total mb: "))
    ranges = get_ranges()

    print("\nSearching for valid combinations...\n")
    sols = search_alloys(items, target, ranges)

    if not sols:
        print("No valid combinations found.")
        return

    print(f"Found {len(sols)} valid combinations. Showing top 10:\n")
    for sol in sols[:10]:
        combo, counts, total, totals, diff = sol
        pct = {m: totals[m]/total for m in totals}
        item_str = ", ".join(f"{combo[i]['name']} x{counts[i]}" for i in range(len(combo)) if counts[i])
        metals_str = " ".join(f"{m}: {pct[m]*100:.1f}%" for m in pct)
        print(f"{item_str}\n → {total:.1f}mb total | {metals_str} | diff {diff:.1f}\n")

if __name__ == "__main__":
    main()