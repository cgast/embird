#!/usr/bin/env python3
"""Replace the Germany section with an Energy section on a running EmBird instance.

Steps:
  1. Delete topic 'germany' (with all its news, preference vectors, clusters,
     UMAP data and sources).
  2. Create topic 'energy' (language 'de') if it does not exist.
  3. Add every row of feeds.csv with include=yes as an RSS source.

Dry run by default; pass --apply to make changes. Safe to re-run: existing
topics and sources are skipped.

Usage:
    python3 apply_energy_section.py feeds.csv [--base-url URL] [--apply]

Standard library only; no install needed.
"""

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request

REMOVE_SLUG = "germany"
TOPIC = {
    "name": "Energy",
    "slug": "energy",
    "description": "Energy market, competitors, prices and regulation",
    "language": "de",
}


class Api:
    def __init__(self, base_url):
        self.base = base_url.rstrip("/") + "/api"

    def request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"{method} {path} failed: HTTP {e.code} {e.read().decode(errors='replace')}")
        return json.loads(raw) if raw else None


def load_feeds(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    review = [r["name"] for r in rows if r.get("include") == "review"]
    if review:
        print(f"Warning: {len(review)} rows still marked 'review' will be skipped: {', '.join(review)}")
    return [r for r in rows if r.get("include") == "yes" and r.get("feed_url")]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("feeds_csv")
    parser.add_argument("--base-url", default="https://news.cgast.org")
    parser.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    args = parser.parse_args()

    feeds = load_feeds(args.feeds_csv)
    api = Api(args.base_url)
    topics = {t["slug"]: t for t in api.request("GET", "/topics")}

    existing_urls = set()
    if TOPIC["slug"] in topics:
        existing_urls = {u["url"] for u in api.request("GET", f"/{TOPIC['slug']}/urls")}
    new_feeds = [r for r in feeds if r["feed_url"] not in existing_urls]

    # ---- Plan ----
    print(f"Instance: {args.base_url}")
    if REMOVE_SLUG in topics:
        n = len(api.request("GET", f"/{REMOVE_SLUG}/urls"))
        print(f"- DELETE topic '{REMOVE_SLUG}' and all its data ({n} sources)")
    else:
        print(f"- topic '{REMOVE_SLUG}' not present, nothing to delete")
    if TOPIC["slug"] in topics:
        print(f"- topic '{TOPIC['slug']}' exists; ensure language '{TOPIC['language']}'")
    else:
        print(f"- CREATE topic '{TOPIC['slug']}' ({TOPIC['name']}, language {TOPIC['language']})")
    print(f"- ADD {len(new_feeds)} RSS sources ({len(feeds) - len(new_feeds)} already present)")
    for r in new_feeds:
        print(f"    {r['name']}: {r['feed_url']}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to make these changes.")
        return 0

    if REMOVE_SLUG in topics:
        answer = input(f"\nType '{REMOVE_SLUG}' to confirm permanent deletion: ")
        if answer.strip() != REMOVE_SLUG:
            print("Aborted, nothing changed.")
            return 1

    # ---- Execute ----
    if REMOVE_SLUG in topics:
        api.request("DELETE", f"/topics/{REMOVE_SLUG}")
        print(f"Deleted topic '{REMOVE_SLUG}'")

    if TOPIC["slug"] not in topics:
        api.request("POST", "/topics", TOPIC)
        print(f"Created topic '{TOPIC['slug']}'")
    # POST /topics does not persist language, so set it explicitly.
    api.request("PUT", f"/topics/{TOPIC['slug']}", {"language": TOPIC["language"]})

    for r in new_feeds:
        api.request("POST", f"/{TOPIC['slug']}/urls", {"url": r["feed_url"], "type": "rss"})
        print(f"Added {r['name']}")

    print("\nDone. New sources are picked up on the next crawler run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
