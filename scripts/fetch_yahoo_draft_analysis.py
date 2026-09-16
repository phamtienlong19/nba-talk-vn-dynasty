#!/usr/bin/env python3
"""Fetch Yahoo's public Draft Analysis endpoint and save the raw snapshot.

Standard library only (urllib.request, json). No OAuth: this is Yahoo's
public league endpoint, used only as a player-metadata source (identity,
NBA team, position eligibility, O-Rank, cap dollars) -- never as a source
of this league's actual ownership/roster state.

Usage:
    python3 scripts/fetch_yahoo_draft_analysis.py [config/yahoo_source.json]

Writes local_data/yahoo/draft_analysis_<UTC timestamp>.json (gitignored)
and prints its path on success. Fails loudly (non-zero exit, message on
stderr) on network errors, non-200 responses, unparseable JSON, or a
response shape that no longer contains fantasy_content.league.players.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "yahoo_source.json"
)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "local_data", "yahoo")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_raw(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"unexpected HTTP status: {resp.status}")
            return resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"failed to reach Yahoo endpoint: {e}") from e


def validate_shape(data: dict) -> list:
    """Return the players list, or raise loudly if the shape changed."""
    try:
        league = data["fantasy_content"]["league"]
    except (KeyError, TypeError) as e:
        raise RuntimeError(
            "unexpected response shape: missing fantasy_content.league "
            "(Yahoo may have changed the response format)"
        ) from e

    players = league.get("players")
    if not isinstance(players, list) or not players:
        raise RuntimeError(
            "unexpected response shape: fantasy_content.league.players "
            "is missing or empty"
        )

    return players


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    config = load_config(config_path)
    url = config["draftAnalysisUrl"]

    raw_bytes = fetch_raw(url)

    try:
        data = json.loads(raw_bytes)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"response was not valid JSON: {e}") from e

    players = validate_shape(data)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H%M%SZ"
    )
    out_path = os.path.join(OUTPUT_DIR, f"draft_analysis_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"OK: fetched {len(players)} players", file=sys.stderr)
    print(f"Saved raw snapshot: {out_path}", file=sys.stderr)
    print(out_path)  # sole stdout line, for scripting: path=$(fetch_yahoo_draft_analysis.py)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"YAHOO FETCH ERROR: {e}", file=sys.stderr)
        sys.exit(1)
