"""
fetch_local.py — Lance ce script sur TON ORDINATEUR pour mettre à jour les stats.

Usage :
    pip install nba_api
    python scripts/fetch_local.py
"""

import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "wemby_stats.json"
WEMBY_ID  = 1641705

try:
    from nba_api.stats.endpoints import playergamelog
except ImportError:
    print("Installation de nba_api...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "nba_api"])
    from nba_api.stats.endpoints import playergamelog

def fmt_date(raw):
    for fmt in ("%b %d, %Y", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:20].strip(), fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return raw[:10]

def fetch_gamelog(season):
    print(f"  Récupération {season}…")
    time.sleep(2)
    gl  = playergamelog.PlayerGameLog(
        player_id=WEMBY_ID,
        season=season,
        season_type_all_star="Regular Season",
        timeout=60,
    )
    df = gl.get_data_frames()[0]
    games = []
    for _, row in df.iterrows():
        matchup = row["MATCHUP"]
        at_away = "@" in matchup
        opp     = matchup.split("@")[-1].strip() if at_away else matchup.split("vs.")[-1].strip()
        games.append({
            "date":       fmt_date(row["GAME_DATE"]),
            "opponent":   opp,
            "home":       not at_away,
            "wl":         row["WL"],
            "pts":        int(row["PTS"] or 0),
            "reb":        int(row["REB"] or 0),
            "ast":        int(row["AST"] or 0),
            "blk":        int(row["BLK"] or 0),
            "stl":        int(row["STL"] or 0),
            "fg":         int(row["FGM"] or 0),
            "fga":        int(row["FGA"] or 0),
            "fg3":        int(row["FG3M"] or 0),
            "fg3a":       int(row["FG3A"] or 0),
            "ft":         int(row["FTM"] or 0),
            "fta":        int(row["FTA"] or 0),
            "plus_minus": int(row["PLUS_MINUS"] or 0),
            "score_team": 0,
            "score_opp":  0,
        })
    print(f"  ✓ {len(games)} matchs récupérés")
    return sorted(games, key=lambda x: x["date"])

def main():
    print("=== Mise à jour stats Wembanyama ===\n")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    for season in ["2023-24", "2024-25"]:
        try:
            games = fetch_gamelog(season)
            data.setdefault("game_logs", {})[season] = games
        except Exception as e:
            print(f"  ✗ Erreur {season}: {e}")

    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(g) for g in data["game_logs"].values())
    print(f"\n✓ {total} matchs sauvegardés dans data/wemby_stats.json")
    print("\nMaintenant dans ton terminal :")
    print("  git add data/wemby_stats.json")
    print("  git commit -m 'update: stats wemby'")
    print("  git push origin main")

if __name__ == "__main__":
    main()
