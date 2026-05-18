"""
fetch_stats.py — Met à jour data/wemby_stats.json
avec les derniers matchs NBA de Victor Wembanyama.

Ordre de priorité :
  1. BallDontLie v1 (si BALLDONTLIE_API_KEY fourni)
  2. ESPN API           (gratuite, sans clé)
  3. NBA Stats API      (peut être bloquée depuis serveurs)

Le script ne quitte JAMAIS avec exit code 1.
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
DATA_PATH     = ROOT / "data" / "wemby_stats.json"
WEMBY_ID_NBA  = 1641705
WEMBY_ID_ESPN = 4432816   # ESPN athlete ID
CURRENT_SEASONS = ["2023-24", "2024-25"]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
})

# ── Helpers ──────────────────────────────────────────────

def save(data: dict):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[✓] Sauvegardé → {DATA_PATH}")


def load() -> dict:
    return json.loads(DATA_PATH.read_text())


def fmt_date(raw: str) -> str:
    for fmt in ("%b %d, %Y", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:len(fmt)+2], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return raw[:10]


def merge_games(existing: list, new_games: list) -> list:
    keys = {(g["date"], g["opponent"]) for g in existing}
    added = 0
    for g in new_games:
        k = (g["date"], g["opponent"])
        if k not in keys:
            existing.append(g)
            keys.add(k)
            added += 1
    print(f"  → {added} nouveaux matchs ajoutés (total: {len(existing)})")
    return sorted(existing, key=lambda x: x["date"])


# ── ESPN API (gratuit, sans clé) ─────────────────────────

ESPN_BASE = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"

def _espn_season_year(season_str: str) -> int:
    """'2024-25' → 2025"""
    return int(season_str.split("-")[0]) + 1


def fetch_espn_gamelog(season_str: str) -> list:
    year = _espn_season_year(season_str)
    url  = f"{ESPN_BASE}/athletes/{WEMBY_ID_ESPN}/gamelog"
    try:
        r = SESSION.get(url, params={"season": year}, timeout=20)
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        print(f"  [ESPN] Erreur requête {season_str}: {e}", file=sys.stderr)
        return []

    try:
        # ESPN returns categories + events keyed by label
        categories = body.get("categories", [])
        events     = body.get("events", {})
        labels_map = body.get("labelsMap", {})  # not always present

        # Find the stat labels
        stats_labels = []
        for cat in categories:
            if cat.get("type") == "total" or cat.get("name") == "":
                continue
            stats_labels = [l.get("abbreviation", "") for l in cat.get("labels", [])]
            if stats_labels:
                break

        if not stats_labels:
            print("  [ESPN] Format inattendu — labels introuvables", file=sys.stderr)
            return []

        def idx(abbr):
            try:    return stats_labels.index(abbr)
            except: return -1

        games = []
        for event_id, event_data in events.items():
            try:
                game_info  = event_data.get("gameInfo", {})
                competitor = event_data.get("competitors", [{}])[0]
                stats_raw  = event_data.get("stats", [])
                if not stats_raw:
                    continue

                date_raw  = game_info.get("date", "")
                home_away = competitor.get("homeAway", "home")
                is_home   = home_away == "home"
                opp_info  = game_info.get(
                    "awayTeam" if is_home else "homeTeam", {}
                )
                opp_abbr  = opp_info.get("abbreviation", "???")

                def st(abbr, default=0):
                    i = idx(abbr)
                    if i < 0 or i >= len(stats_raw): return default
                    try:    return float(stats_raw[i]) if stats_raw[i] not in ("", "--") else default
                    except: return default

                pts  = int(st("PTS"))
                reb  = int(st("REB"))
                ast  = int(st("AST"))
                blk  = int(st("BLK"))
                stl  = int(st("STL"))
                fg   = int(st("FGM"))
                fga  = int(st("FGA"))
                fg3  = int(st("3PM"))
                fg3a = int(st("3PA"))
                ft   = int(st("FTM"))
                fta  = int(st("FTA"))
                pm   = int(st("+/-"))

                team_score = int(game_info.get(
                    "homeScore" if is_home else "awayScore", 0) or 0)
                opp_score  = int(game_info.get(
                    "awayScore" if is_home else "homeScore", 0) or 0)
                wl = "W" if team_score > opp_score else "L"

                games.append({
                    "date":       fmt_date(date_raw),
                    "opponent":   opp_abbr,
                    "home":       is_home,
                    "wl":         wl,
                    "pts":        pts, "reb": reb, "ast": ast,
                    "blk":        blk, "stl": stl,
                    "fg":         fg,  "fga": fga,
                    "fg3":        fg3, "fg3a": fg3a,
                    "ft":         ft,  "fta":  fta,
                    "plus_minus": pm,
                    "score_team": team_score,
                    "score_opp":  opp_score,
                })
            except Exception as ex:
                print(f"  [ESPN] Ligne ignorée: {ex}", file=sys.stderr)
                continue

        print(f"  [ESPN] {season_str}: {len(games)} matchs")
        return sorted(games, key=lambda x: x["date"])

    except Exception as e:
        print(f"  [ESPN] Erreur parsing {season_str}: {e}", file=sys.stderr)
        return []


def fetch_espn_averages() -> list | None:
    """Fetch season-by-season averages from ESPN."""
    url = f"{ESPN_BASE}/athletes/{WEMBY_ID_ESPN}/stats"
    try:
        r = SESSION.get(url, timeout=20)
        r.raise_for_status()
        body = r.json()
        # ESPN stats structure varies — basic extraction
        splits = body.get("splits", {}).get("categories", [])
        seasons_data = []
        for split in splits:
            label = split.get("displayName", "")
            stats = {s["abbreviation"]: s["value"] for s in split.get("stats", [])}
            if "PTS" in stats:
                seasons_data.append({
                    "season": label,
                    "team":   "San Antonio Spurs",
                    "league": "NBA",
                    "gp":     int(stats.get("GP", 0)),
                    "mpg":    round(float(stats.get("MIN", 0)), 1),
                    "ppg":    round(float(stats.get("PTS", 0)), 1),
                    "rpg":    round(float(stats.get("REB", 0)), 1),
                    "apg":    round(float(stats.get("AST", 0)), 1),
                    "bpg":    round(float(stats.get("BLK", 0)), 1),
                    "spg":    round(float(stats.get("STL", 0)), 1),
                    "fg_pct": round(float(stats.get("FG%", 0)) * 100, 1) if float(stats.get("FG%", 0)) < 1 else round(float(stats.get("FG%", 0)), 1),
                    "fg3_pct":round(float(stats.get("3P%", 0)) * 100, 1) if float(stats.get("3P%", 0)) < 1 else round(float(stats.get("3P%", 0)), 1),
                    "ft_pct": round(float(stats.get("FT%", 0)) * 100, 1) if float(stats.get("FT%", 0)) < 1 else round(float(stats.get("FT%", 0)), 1),
                })
        print(f"  [ESPN] Averages: {len(seasons_data)} saisons")
        return seasons_data if seasons_data else None
    except Exception as e:
        print(f"  [ESPN] Averages error: {e}", file=sys.stderr)
        return None


# ── BallDontLie v1 ────────────────────────────────────────

BDLAPI = "https://api.balldontlie.io/v1"

def find_wemby_bdl(api_key: str) -> int | None:
    try:
        r = SESSION.get(
            f"{BDLAPI}/players",
            params={"search": "wembanyama", "per_page": 5},
            headers={"Authorization": api_key},
            timeout=15,
        )
        r.raise_for_status()
        for p in r.json().get("data", []):
            if "wembanyama" in p.get("last_name", "").lower():
                return p["id"]
    except Exception as e:
        print(f"  [BDL] find_player error: {e}", file=sys.stderr)
    return None


def fetch_bdl_gamelog(api_key: str, season_year: int) -> list:
    try:
        pid = find_wemby_bdl(api_key)
        if not pid:
            print("  [BDL] Joueur introuvable", file=sys.stderr)
            return []

        games, cursor = [], None
        while True:
            params = {"player_ids[]": pid, "seasons[]": season_year, "per_page": 100}
            if cursor:
                params["cursor"] = cursor
            r = SESSION.get(
                f"{BDLAPI}/stats",
                params=params,
                headers={"Authorization": api_key},
                timeout=20,
            )
            r.raise_for_status()
            body = r.json()

            for row in body.get("data", []):
                try:
                    g          = row.get("game", {})
                    player_tid = row.get("team", {}).get("id")
                    is_home    = g.get("home_team_id") == player_tid
                    home_s     = g.get("home_team_score", 0) or 0
                    away_s     = g.get("visitor_team_score", 0) or 0
                    opp_team   = g.get("visitor_team" if is_home else "home_team", {})
                    opp_abbr   = opp_team.get("abbreviation", "???")
                    team_score = home_s if is_home else away_s
                    opp_score  = away_s if is_home else home_s

                    games.append({
                        "date":       (g.get("date", ""))[:10],
                        "opponent":   opp_abbr,
                        "home":       is_home,
                        "wl":         "W" if team_score > opp_score else "L",
                        "pts":        row.get("pts") or 0,
                        "reb":        row.get("reb") or 0,
                        "ast":        row.get("ast") or 0,
                        "blk":        row.get("blk") or 0,
                        "stl":        row.get("stl") or 0,
                        "fg":         row.get("fgm") or 0,
                        "fga":        row.get("fga") or 0,
                        "fg3":        row.get("fg3m") or 0,
                        "fg3a":       row.get("fg3a") or 0,
                        "ft":         row.get("ftm") or 0,
                        "fta":        row.get("fta") or 0,
                        "plus_minus": 0,
                        "score_team": team_score,
                        "score_opp":  opp_score,
                    })
                except Exception:
                    continue

            cursor = body.get("meta", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.3)

        print(f"  [BDL] {season_year}-{season_year+1}: {len(games)} matchs")
        return sorted(games, key=lambda x: x["date"])

    except Exception as e:
        print(f"  [BDL] Erreur: {e}", file=sys.stderr)
        return []


# ── NBA Stats API (fallback) ──────────────────────────────

NBA_HEADERS = {
    **SESSION.headers,
    "Referer":            "https://www.nba.com/",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token":  "true",
}

def fetch_nba_gamelog(season: str) -> list:
    url = (
        "https://stats.nba.com/stats/playergamelog"
        f"?PlayerID={WEMBY_ID_NBA}&Season={season}&SeasonType=Regular+Season"
    )
    try:
        r = requests.get(url, headers=NBA_HEADERS, timeout=20)
        r.raise_for_status()
        rs      = r.json()["resultSets"][0]
        headers = rs["headers"]
        idx     = {h: i for i, h in enumerate(headers)}
        games   = []
        for row in rs["rowSet"]:
            try:
                matchup  = row[idx["MATCHUP"]]
                at_away  = "@" in matchup
                opp      = matchup.split("@")[-1].strip() if at_away else matchup.split("vs.")[-1].strip()
                games.append({
                    "date":       fmt_date(row[idx["GAME_DATE"]]),
                    "opponent":   opp,
                    "home":       not at_away,
                    "wl":         row[idx["WL"]],
                    "pts":        row[idx["PTS"]] or 0,
                    "reb":        row[idx["REB"]] or 0,
                    "ast":        row[idx["AST"]] or 0,
                    "blk":        row[idx["BLK"]] or 0,
                    "stl":        row[idx["STL"]] or 0,
                    "fg":         row[idx["FGM"]] or 0,
                    "fga":        row[idx["FGA"]] or 0,
                    "fg3":        row[idx["FG3M"]] or 0,
                    "fg3a":       row[idx["FG3A"]] or 0,
                    "ft":         row[idx["FTM"]] or 0,
                    "fta":        row[idx["FTA"]] or 0,
                    "plus_minus": row[idx["PLUS_MINUS"]] or 0,
                    "score_team": 0,
                    "score_opp":  0,
                })
            except Exception:
                continue
        print(f"  [NBA] {season}: {len(games)} matchs")
        return games
    except Exception as e:
        print(f"  [NBA] Erreur {season}: {e}", file=sys.stderr)
        return []


# ── Main ──────────────────────────────────────────────────

def main():
    data    = load()
    api_key = os.environ.get("BALLDONTLIE_API_KEY", "").strip()

    for season_str in CURRENT_SEASONS:
        year     = int(season_str.split("-")[0])
        existing = data.setdefault("game_logs", {}).setdefault(season_str, [])
        print(f"\n── Saison {season_str} ({len(existing)} matchs existants) ──")

        new_games = []

        if api_key:
            print("  Tentative BallDontLie…")
            new_games = fetch_bdl_gamelog(api_key, year)

        if not new_games:
            print("  Tentative ESPN…")
            new_games = fetch_espn_gamelog(season_str)

        if not new_games:
            print("  Tentative NBA Stats…")
            new_games = fetch_nba_gamelog(season_str)

        if new_games:
            data["game_logs"][season_str] = merge_games(existing, new_games)
        else:
            print(f"  Aucune source disponible — données conservées")

    print("\n── Moyennes de carrière ──")
    avgs = fetch_espn_averages()
    if avgs:
        non_nba = [s for s in data.get("career_averages", []) if s.get("league") != "NBA"]
        data["career_averages"] = non_nba + avgs

    save(data)
    print("\n[✓] Terminé.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERREUR CRITIQUE] {e}", file=sys.stderr)
        # Toujours sauvegarder l'horodatage même en cas d'erreur
        try:
            d = load()
            save(d)
        except Exception:
            pass
        sys.exit(0)   # Ne jamais faire échouer le workflow
