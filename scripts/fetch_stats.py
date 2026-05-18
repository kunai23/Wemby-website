"""
fetch_stats.py — Met à jour data/wemby_stats.json
avec les derniers matchs NBA de Victor Wembanyama.

Sources :
  1. API BallDontLie v1 (BALLDONTLIE_API_KEY requis)
  2. Fallback : NBA Stats API (accès direct serveur)
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
DATA_PATH   = ROOT / "data" / "wemby_stats.json"
WEMBY_ID_NBA = 1641705          # NBA Stats Player ID
CURRENT_SEASONS = ["2023-24", "2024-25"]

# ── Helpers ──────────────────────────────────────────────

def save(data: dict):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[✓] Sauvegardé → {DATA_PATH}")


def load() -> dict:
    return json.loads(DATA_PATH.read_text())


def fmt_date(raw: str) -> str:
    """'OCT 25, 2023'  →  '2023-10-25'"""
    try:
        return datetime.strptime(raw, "%b %d, %Y").strftime("%Y-%m-%d")
    except Exception:
        return raw


# ── NBA Stats API (serveur uniquement) ───────────────────

NBA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept":              "application/json, text/plain, */*",
    "Accept-Language":     "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer":             "https://www.nba.com/",
    "x-nba-stats-origin":  "stats",
    "x-nba-stats-token":   "true",
    "Connection":          "keep-alive",
}

def fetch_nba_gamelog(season: str) -> list[dict]:
    """Fetches game log from stats.nba.com — works server-side with proper headers."""
    url = (
        "https://stats.nba.com/stats/playergamelog"
        f"?PlayerID={WEMBY_ID_NBA}&Season={season}&SeasonType=Regular+Season"
    )
    try:
        r = requests.get(url, headers=NBA_HEADERS, timeout=20)
        r.raise_for_status()
        rs = r.json()["resultSets"][0]
        headers = rs["headers"]
        rows    = rs["rowSet"]
        idx = {h: i for i, h in enumerate(headers)}
        games = []
        for row in rows:
            fg  = row[idx["FGM"]];  fga  = row[idx["FGA"]]
            fg3 = row[idx["FG3M"]]; fg3a = row[idx["FG3A"]]
            ft  = row[idx["FTM"]];  fta  = row[idx["FTA"]]
            matchup: str = row[idx["MATCHUP"]]    # e.g. "SAS vs. MEM" or "SAS @ DAL"
            at_away = "@" in matchup
            parts = matchup.replace("vs.", "vs").replace("@", "vs").split("vs")
            opponent = parts[1].strip() if len(parts) > 1 else matchup.split()[-1]
            wl        = row[idx["WL"]]
            pts       = row[idx["PTS"]]
            reb       = row[idx["REB"]]
            ast       = row[idx["AST"]]
            blk       = row[idx["BLK"]]
            stl       = row[idx["STL"]]
            pm        = row[idx["PLUS_MINUS"]]
            # We don't have team/opp score in gamelog — use MIN as proxy flag
            games.append({
                "date":       fmt_date(row[idx["GAME_DATE"]]),
                "opponent":   opponent,
                "home":       not at_away,
                "wl":         wl,
                "pts":        pts,
                "reb":        reb,
                "ast":        ast,
                "blk":        blk,
                "stl":        stl,
                "fg":         fg,
                "fga":        fga,
                "fg3":        fg3,
                "fg3a":       fg3a,
                "ft":         ft,
                "fta":        fta,
                "plus_minus": pm,
                "score_team": 0,
                "score_opp":  0,
            })
        print(f"[NBA API] {season}: {len(games)} matchs récupérés")
        return games
    except Exception as e:
        print(f"[NBA API] Erreur pour {season}: {e}", file=sys.stderr)
        return []


# ── BallDontLie v1 API ────────────────────────────────────

BDLAPI = "https://api.balldontlie.io/v1"

def find_wemby_bdl(api_key: str) -> int | None:
    """Returns Wembanyama's BallDontLie player ID."""
    r = requests.get(
        f"{BDLAPI}/players",
        params={"search": "wembanyama", "per_page": 5},
        headers={"Authorization": api_key},
        timeout=15,
    )
    r.raise_for_status()
    players = r.json().get("data", [])
    for p in players:
        if "wembanyama" in p.get("last_name", "").lower():
            return p["id"]
    return None


def fetch_bdl_gamelog(api_key: str, season_year: int) -> list[dict]:
    """
    Fetches per-game stats from BallDontLie.
    season_year = start year, e.g. 2024 for '2024-25'.
    """
    pid = find_wemby_bdl(api_key)
    if not pid:
        print("[BDL] Joueur introuvable", file=sys.stderr)
        return []

    games = []
    cursor = None
    while True:
        params = {
            "player_ids[]": pid,
            "seasons[]":    season_year,
            "per_page":     100,
        }
        if cursor:
            params["cursor"] = cursor
        r = requests.get(
            f"{BDLAPI}/stats",
            params=params,
            headers={"Authorization": api_key},
            timeout=20,
        )
        r.raise_for_status()
        body = r.json()
        for row in body.get("data", []):
            g = row.get("game", {})
            home_tid = g.get("home_team_id")
            player_tid = row.get("team", {}).get("id")
            is_home = home_tid == player_tid
            home_score = g.get("home_team_score", 0)
            away_score = g.get("visitor_team_score", 0)
            opp_team   = g.get("visitor_team", {}) if is_home else g.get("home_team", {})
            opp_abbr   = opp_team.get("abbreviation", "???")
            fg  = row.get("fgm", 0) or 0
            fga = row.get("fga", 0) or 0
            fg3 = row.get("fg3m", 0) or 0
            fg3a= row.get("fg3a", 0) or 0
            ft  = row.get("ftm", 0) or 0
            fta = row.get("fta", 0) or 0
            pts = row.get("pts", 0) or 0
            reb = row.get("reb", 0) or 0
            ast = row.get("ast", 0) or 0
            blk = row.get("blk", 0) or 0
            stl = row.get("stl", 0) or 0
            team_score = home_score if is_home else away_score
            opp_score  = away_score if is_home else home_score
            wl = "W" if team_score > opp_score else "L"
            games.append({
                "date":       g.get("date", "")[:10],
                "opponent":   opp_abbr,
                "home":       is_home,
                "wl":         wl,
                "pts":        pts,
                "reb":        reb,
                "ast":        ast,
                "blk":        blk,
                "stl":        stl,
                "fg":         fg,
                "fga":        fga,
                "fg3":        fg3,
                "fg3a":       fg3a,
                "ft":         ft,
                "fta":        fta,
                "plus_minus": 0,
                "score_team": team_score,
                "score_opp":  opp_score,
            })
        meta   = body.get("meta", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break
        time.sleep(0.3)

    print(f"[BDL] {season_year}-{season_year+1}: {len(games)} matchs")
    return sorted(games, key=lambda x: x["date"])


# ── Season averages (NBA Stats) ───────────────────────────

def fetch_career_averages() -> list[dict] | None:
    url = (
        "https://stats.nba.com/stats/playercareerstats"
        f"?PlayerID={WEMBY_ID_NBA}&PerMode=PerGame"
    )
    try:
        r = requests.get(url, headers=NBA_HEADERS, timeout=20)
        r.raise_for_status()
        rs = r.json()["resultSets"][0]
        headers = rs["headers"]
        rows    = rs["rowSet"]
        idx = {h: i for i, h in enumerate(headers)}
        seasons = []
        for row in rows:
            seasons.append({
                "season":  row[idx["SEASON_ID"]],
                "team":    "San Antonio Spurs",
                "league":  "NBA",
                "gp":      row[idx["GP"]],
                "mpg":     row[idx["MIN"]],
                "ppg":     row[idx["PTS"]],
                "rpg":     row[idx["REB"]],
                "apg":     row[idx["AST"]],
                "bpg":     row[idx["BLK"]],
                "spg":     row[idx["STL"]],
                "fg_pct":  round((row[idx["FG_PCT"]] or 0) * 100, 1),
                "fg3_pct": round((row[idx["FG3_PCT"]] or 0) * 100, 1),
                "ft_pct":  round((row[idx["FT_PCT"]] or 0) * 100, 1),
            })
        print(f"[NBA API] Averages: {len(seasons)} saisons NBA")
        return seasons
    except Exception as e:
        print(f"[NBA API] Averages error: {e}", file=sys.stderr)
        return None


# ── Merge helpers ─────────────────────────────────────────

def merge_games(existing: list[dict], new_games: list[dict]) -> list[dict]:
    """Add new games without duplicating existing ones (by date+opponent)."""
    existing_keys = {(g["date"], g["opponent"]) for g in existing}
    added = 0
    for g in new_games:
        key = (g["date"], g["opponent"])
        if key not in existing_keys:
            existing.append(g)
            existing_keys.add(key)
            added += 1
    print(f"[merge] {added} nouveaux matchs ajoutés")
    return sorted(existing, key=lambda x: x["date"])


# ── Main ──────────────────────────────────────────────────

def main():
    data = load()
    api_key = os.environ.get("BALLDONTLIE_API_KEY", "")
    updated = False

    for season_str in CURRENT_SEASONS:
        year = int(season_str.split("-")[0])
        existing = data.setdefault("game_logs", {}).setdefault(season_str, [])
        print(f"\n── Saison {season_str} (matchs existants: {len(existing)}) ──")

        new_games = []

        if api_key:
            new_games = fetch_bdl_gamelog(api_key, year)
        else:
            new_games = fetch_nba_gamelog(season_str)

        if new_games:
            data["game_logs"][season_str] = merge_games(existing, new_games)
            updated = True
        else:
            print(f"[!] Aucune donnée récupérée pour {season_str} — données existantes conservées")

    # Try to update career averages (NBA seasons only)
    nba_avgs = fetch_career_averages()
    if nba_avgs:
        non_nba = [s for s in data.get("career_averages", []) if s.get("league") != "NBA"]
        data["career_averages"] = non_nba + nba_avgs
        updated = True

    if updated:
        save(data)
        print("\n[✓] Mise à jour complète !")
    else:
        print("\n[!] Aucune mise à jour effectuée.")
        save(data)  # still update last_updated timestamp


if __name__ == "__main__":
    main()
