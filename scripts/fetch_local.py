"""
fetch_local.py — Lance ce script sur TON ORDINATEUR pour mettre à jour les stats.

Usage :
    python scripts/fetch_local.py

Pas besoin de clé API. Fonctionne depuis n'importe quelle connexion personnelle.
"""

import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "wemby_stats.json"
WEMBY_ID  = 1641705

NBA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":              "application/json, text/plain, */*",
    "Accept-Language":     "fr-FR,fr;q=0.9,en-US;q=0.8",
    "Referer":             "https://www.nba.com/",
    "x-nba-stats-origin":  "stats",
    "x-nba-stats-token":   "true",
    "Connection":          "keep-alive",
}

def fmt_date(raw):
    for fmt in ("%b %d, %Y", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:20].strip(), fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return raw[:10]

def fetch_gamelog(season):
    url = (
        f"https://stats.nba.com/stats/playergamelog"
        f"?PlayerID={WEMBY_ID}&Season={season}&SeasonType=Regular+Season"
    )
    print(f"  Récupération {season}…")
    time.sleep(1)
    r = requests.get(url, headers=NBA_HEADERS, timeout=20)
    r.raise_for_status()
    rs      = r.json()["resultSets"][0]
    headers = rs["headers"]
    idx     = {h: i for i, h in enumerate(headers)}
    games   = []
    for row in rs["rowSet"]:
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
    print(f"  ✓ {len(games)} matchs récupérés")
    return sorted(games, key=lambda x: x["date"])

def main():
    print("=== Mise à jour stats Wembanyama ===\n")
    data = json.loads(DATA_PATH.read_text())

    for season in ["2023-24", "2024-25"]:
        try:
            games = fetch_gamelog(season)
            data.setdefault("game_logs", {})[season] = games
        except Exception as e:
            print(f"  ✗ Erreur {season}: {e}")

    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    total = sum(len(g) for g in data["game_logs"].values())
    print(f"\n✓ {total} matchs sauvegardés dans data/wemby_stats.json")
    print("\nMaintenant dans ton terminal :")
    print("  git add data/wemby_stats.json")
    print("  git commit -m 'update: stats wemby'")
    print("  git push origin main")

if __name__ == "__main__":
    main()
