# TFG-Alloy — Alloy calculator

This small tool searches your inventory to find combinations of items (up to a configurable number of distinct item types) that produce a target mass of an alloy while meeting element composition constraints.

The workspace contains:
- `alloy_calc.py` — CLI solver that loads items/recipes and searches integer item counts.
- `items.json` — inventory file (editable). Each entry includes name, mass, availability and per-item element composition.
- `recipes.json` — optional named recipes (element bounds) which can be referenced by name.

## Quick start (PowerShell)

Run with the provided inventory & recipe (defaults):

```powershell
python .\alloy_calc.py
```

Run using a named recipe and strongly preferring overshoot (this is the default behavior):

```powershell
python .\alloy_calc.py --target-recipe bismuth_bronze --prefer-overshoot
```

Show top 5 matches and a different target mass:

```powershell
python .\alloy_calc.py -t 1500 --top 5
```

Disable the overshoot preference:

```powershell
python .\alloy_calc.py --no-prefer-overshoot
```

## Command-line options (high level)

- `--items-file PATH` — path to items JSON (default: `items.json`).
- `--recipes-file PATH` — path to recipes JSON (default: `recipes.json`).
- `-t, --target, --target-mb` — target mass in mb.
- `--allowance` — allowed ± mass tolerance (default: `144`).
- `--max-types` — maximum distinct item types to use (default: `4`).
- `--top` — how many top solutions to print (default: `1`).
- `--prefer-overshoot` / `--no-prefer-overshoot` — prefer overshooting (default: enabled).
- `--add-item 'Name,mass,available,Element'` — add a single-element item inline (can repeat).
- `--recipe 'Cu:0.50-0.65;Zn:0.20-0.30;Bi:0.10-0.20'` — inline recipe bounds.
- `--target-recipe NAME` — use a named recipe from the recipes file.

## `items.json` format

The file is an array of item objects. Each item should contain:

- `name` (string)
- `mass_mb` (number) — mass per item in mb
- `available` (integer) — how many units you have available
- `composition` (object) — element -> fraction (fractions will be normalized if they don't sum to 1)

Example:

```json
[
  {"name":"Purified Copper Ore","mass_mb":100,"available":27,"composition":{"Cu":1.0}},
  {"name":"Small Pile of Bismuth Dust","mass_mb":36,"available":31,"composition":{"Bi":1.0}}
]
```

This supports "non-alloy recipe" items such as a 144mb Copper bar. Example `--add-item` equivalent:

```powershell
python .\alloy_calc.py --add-item "Copper Bar,144,5,Cu"
```

Or add it directly to `items.json`:

```json
{"name":"Copper Bar","mass_mb":144,"available":5,"composition":{"Cu":1.0}}
```

## `recipes.json` format

A mapping of recipe-name -> element bounds. Each element bound is a two-element array `[min, max]` representing fractional composition.

Example (`recipes.json`):

```json
{
  "bismuth_bronze": {
    "Cu": [0.50, 0.65],
    "Zn": [0.20, 0.30],
    "Bi": [0.10, 0.20]
  }
}
```

You can then run:

```powershell
python .\alloy_calc.py --target-recipe bismuth_bronze
```

or supply inline recipe bounds:

```powershell
python .\alloy_calc.py --recipe "Cu:0.50-0.65;Zn:0.20-0.30;Bi:0.10-0.20"
```

## Behavior notes

- By default the solver will heavily prefer overshooting the target mass rather than undershooting it; use `--no-prefer-overshoot` to disable this preference.
- The solver enumerates combinations of up to `--max-types` distinct item types and does integer DFS on counts per type. It's fast for the current inventory size; if you add many more item types or very large availabilities you may want to switch to an ILP solver (I can add an option using `pulp`).
- The scarcity score is used as a tie-breaker: it sums `count / available` across used items (lower is better — i.e., uses more abundant items).

## Examples

Find solutions for the default bismuth bronze target and print the top 2 (defaults):

```powershell
python .\alloy_calc.py
```

Add a 144mb copper bar at runtime and search:

```powershell
python .\alloy_calc.py --add-item "Copper Bar,144,10,Cu"
```

Search with a tighter tolerance:

```powershell
python .\alloy_calc.py -t 2016 --allowance 20 --top 5
```

Save output redirection for review:

```powershell
python .\alloy_calc.py > results.txt
```

## Troubleshooting

- If Python reports a JSON parse error, check `items.json` / `recipes.json` for trailing commas or invalid syntax.
- If no solutions are found, try widening `--allowance` or relaxing recipe bounds.

## Templates and Git ignore

The repository includes template files you can copy to create your own local `items.json` and `recipes.json` files. These files are intentionally ignored by Git so you can keep per-player counts. Basically, my usage won't leak into yours.

Files provided:
- `items.template.json` — example inventory structure. Copy to `items.json` and edit counts and masses for your setup.
- `recipes.template.json` — example recipes. Copy to `recipes.json` and add or edit named recipes.

To create your local files from the templates (PowerShell):

```powershell
Copy-Item .\items.template.json .\items.json -Force
Copy-Item .\recipes.template.json .\recipes.json -Force
```

`.gitignore` is configured to ignore `items.json` and `recipes.json` so you won't accidentally commit your local inventory.

If you'd like the example `items.json`/`recipes.json` to be tracked in Git instead, don't copy the templates into those filenames — instead edit the templates or commit renamed files.

## Next improvements

- Add CSV export of top candidates.
- Add a `--overshoot-weight` numeric option instead of the fixed multiplier.
- Support multi-element `--add-item` with composition fractions.
- Optionally add an ILP backend for exact optimization over larger inventories.
- Better inventory management/importing
- Support for items without mb values (ex: Charcoal in Wrought Iron)