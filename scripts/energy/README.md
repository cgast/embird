# Energy section migration

Replaces the `germany` topic with an `energy` topic whose sources come from
`sources.csv`. Only real RSS/Atom feeds are added; sites without a feed are skipped.

Requires Python 3 (standard library only).

```bash
cd scripts/energy

# 1. Find feeds for each active row in sources.csv -> feeds.csv
python3 find_feeds.py sources.csv feeds.csv

# 2. Review feeds.csv: set the `include` column to yes/no.
#    Rows marked `review` are section pages whose feed looks site-wide
#    (e.g. a general news feed) and are skipped unless changed to `yes`.

# 3. Dry run (shows what would change)
python3 apply_energy_section.py feeds.csv --base-url https://news.cgast.org

# 4. Apply (asks you to type `germany` before deleting)
python3 apply_energy_section.py feeds.csv --base-url https://news.cgast.org --apply
```

Deleting `germany` permanently removes its news items, preference vectors,
clusters, UMAP data and sources. `apply_energy_section.py` is safe to re-run.
