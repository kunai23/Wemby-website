"""
fetch_stats.py — Récupère les stats Wembanyama via un vrai navigateur (Playwright)
Ce script ouvre Chrome en mode headless, intercepte les requêtes NBA et extrait les données.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
DATA_PATH   = ROOT / "data" / "wemby_stats.json"
WEMBY_ID    = 1641705
SEASONS     = {"2023-24": "2023-24", "2024-25": "2024-25"}

def save(data: dict):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[✓] Sauvegardé → {DATA_PATH}")

def load() -> dict:
    return json.loads(DATA_PATH.read_text())

def fmt_date(raw: str) -> str:
    for fmt in ("%b %d, %Y", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:20].strip(), fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return raw[:10]

def parse_nba_gamelog(response_json: dict) -> list:
    """Parse stats.nba.com playergamelog response."""
    try:
        rs      = response_json["resultSets"][0]
        headers = rs["headers"]
        idx     = {h: i for i, h in enumerate(headers)}
        games   = []
        for row in rs["rowSet"]:
            try:
                matchup = row[idx["MATCHUP"]]
                at_away = "@" in matchup
                opp     = matchup.split("@")[-1].strip() if at_away else matchup.split("vs.")[-1].strip()
                games.append({
                    "date":       fmt_date(row[idx["GAME_DATE"]]),
                    "opponent":   opp.strip(),
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
        return games
    except Exception as e:
        print(f"  [parse] Erreur: {e}", file=sys.stderr)
        return []

def fetch_season_browser(season: str) -> list:
    """Utilise Playwright pour intercepter les réponses NBA."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [browser] Playwright non installé", file=sys.stderr)
        return []

    print(f"  [browser] Ouverture Chrome headless pour {season}…")
    captured = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = context.new_page()

            def on_response(response):
                if "playergamelog" in response.url and "PlayerID" in response.url:
                    try:
                        data = response.json()
                        games = parse_nba_gamelog(data)
                        if games:
                            captured.extend(games)
                            print(f"  [browser] Intercepté: {len(games)} matchs")
                    except Exception:
                        pass

            page.on("response", on_response)

            url = (
                f"https://www.nba.com/stats/player/{WEMBY_ID}/traditional"
                f"?PerMode=Totals&Season={season}&SeasonType=Regular%20Season"
            )
            print(f"  [browser] Navigation → {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                page.wait_for_timeout(8000)

            page.wait_for_timeout(4000)
            browser.close()

    except Exception as e:
        print(f"  [browser] Erreur: {e}", file=sys.stderr)

    return captured

def merge_games(existing: list, new_games: list) -> list:
    keys  = {(g["date"], g["opponent"]) for g in existing}
    added = 0
    for g in new_games:
        k = (g["date"], g["opponent"])
        if k not in keys:
            existing.append(g)
            keys.add(k)
            added += 1
    print(f"  → {added} nouveaux matchs (total: {len(existing)})")
    return sorted(existing, key=lambda x: x["date"])

def main():
    data = load()

    for season_str in ["2023-24", "2024-25"]:
        existing = data.setdefault("game_logs", {}).setdefault(season_str, [])
        print(f"\n── Saison {season_str} ({len(existing)} matchs existants) ──")
        new_games = fetch_season_browser(season_str)
        if new_games:
            data["game_logs"][season_str] = merge_games(existing, new_games)
        else:
            print("  Aucun match récupéré — données conservées")

    save(data)
    print("\n[✓] Terminé.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERREUR] {e}", file=sys.stderr)
        try:
            save(load())
        except Exception:
            pass
        sys.exit(0)
