"""
fetch_stats.py — Récupère les stats Wembanyama via RapidAPI (API-NBA).

Setup (1 fois) :
  1. Créer un compte gratuit sur rapidapi.com (pas de carte bleue)
  2. Chercher "API-NBA" → Subscribe (plan Basic, gratuit, 100 req/jour)
  3. Copier la clé depuis https://rapidapi.com/api-sports/api/api-nba
  4. Dans GitHub : Settings → Secrets → New secret
     Nom : RAPIDAPI_KEY  /  Valeur : ta_clé
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "wemby_stats.json"

RAPID_HOST = "api-nba-v1.p.rapidapi.com"
RAPID_BASE = f"https://{RAPID_HOST}"

WEMBY_ID_RAPID = None   # sera résolu dynamiquement

def save(data: dict):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[✓] Sauvegardé → {DATA_PATH}")

def load() -> dict:
    return json.loads(DATA_PATH.read_text())

def rapid_headers(api_key: str) -> dict:
    return {
        "X-RapidAPI-Key":  api_key,
        "X-RapidAPI-Host": RAPID_HOST,
        "Accept":          "application/json",
    }

# ── Trouver l'ID RapidAPI de Wemby ──────────────────────

def find_wemby_id(api_key: str) -> str | None:
    try:
        r = requests.get(
            f"{RAPID_BASE}/players",
            params={"name": "wembanyama", "season": "2024"},
            headers=rapid_headers(api_key),
            timeout=15,
        )
        if r.status_code == 401:
            print("[RapidAPI] ❌ Clé invalide ou quota dépassé", file=sys.stderr)
            return None
        r.raise_for_status()
        players = r.json().get("response", [])
        for p in players:
            ln = (p.get("lastname") or "").lower()
            if "wembanyama" in ln:
                pid = str(p["id"])
                print(f"  [RapidAPI] Joueur trouvé : {p['firstname']} {p['lastname']} (id={pid})")
                return pid
        print("  [RapidAPI] Joueur introuvable dans la réponse", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [RapidAPI] find error: {e}", file=sys.stderr)
        return None

# ── Récupérer les stats match par match ─────────────────

SEASON_MAP = {"2023-24": "2023", "2024-25": "2024"}

def fetch_rapid_gamelog(api_key: str, player_id: str, season_str: str) -> list:
    season = SEASON_MAP.get(season_str)
    if not season:
        return []
    try:
        r = requests.get(
            f"{RAPID_BASE}/players/statistics",
            params={"id": player_id, "season": season},
            headers=rapid_headers(api_key),
            timeout=20,
        )
        r.raise_for_status()
        stats = r.json().get("response", [])
        print(f"  [RapidAPI] {season_str}: {len(stats)} entrées reçues")

        games_by_id: dict[str, dict] = {}
        for row in stats:
            try:
                game   = row.get("game", {})
                gid    = str(game.get("id", ""))
                team   = row.get("team", {})
                teams  = game.get("teams", {})
                home_t = teams.get("home", {})
                away_t = teams.get("visitors", {})
                is_home = team.get("id") == home_t.get("id")
                home_s  = game.get("scores", {}).get("home", {}).get("points") or 0
                away_s  = game.get("scores", {}).get("visitors", {}).get("points") or 0
                team_score = home_s if is_home else away_s
                opp_score  = away_s if is_home else home_s
                opp_team   = home_t if not is_home else away_t
                opp_abbr   = opp_team.get("code") or opp_team.get("nickname", "???")

                date_raw = game.get("date", {})
                if isinstance(date_raw, dict):
                    date_str = (date_raw.get("start") or "")[:10]
                else:
                    date_str = str(date_raw)[:10]

                def i(k): return int(row.get(k) or 0)
                def f(k): return float(row.get(k) or 0)

                fg  = i("fgm"); fga  = i("fga")
                fg3 = i("tpm"); fg3a = i("tpa")
                ft  = i("ftm"); fta  = i("fta")
                pts = i("points"); reb = i("totReb"); ast = i("assists")
                blk = i("blocks"); stl = i("steals")

                games_by_id[gid] = {
                    "date":       date_str,
                    "opponent":   opp_abbr,
                    "home":       is_home,
                    "wl":         "W" if team_score > opp_score else "L",
                    "pts":        pts, "reb": reb, "ast": ast,
                    "blk":        blk, "stl": stl,
                    "fg":         fg,  "fga":  fga,
                    "fg3":        fg3, "fg3a": fg3a,
                    "ft":         ft,  "fta":  fta,
                    "plus_minus": 0,
                    "score_team": int(team_score),
                    "score_opp":  int(opp_score),
                }
            except Exception:
                continue

        result = sorted(games_by_id.values(), key=lambda x: x["date"])
        print(f"  [RapidAPI] {len(result)} matchs uniques")
        return result

    except Exception as e:
        print(f"  [RapidAPI] fetch error: {e}", file=sys.stderr)
        return []

# ── Merge ────────────────────────────────────────────────

def merge_games(existing: list, new_games: list) -> list:
    keys  = {(g["date"], g["opponent"]) for g in existing}
    added = 0
    for g in new_games:
        k = (g["date"], g["opponent"])
        if k not in keys:
            existing.append(g)
            keys.add(k)
            added += 1
    print(f"  → {added} nouveaux matchs ajoutés (total: {len(existing)})")
    return sorted(existing, key=lambda x: x["date"])

# ── Main ─────────────────────────────────────────────────

def main():
    api_key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not api_key:
        print("⚠️  RAPIDAPI_KEY manquant — voir instructions dans le script", file=sys.stderr)
        print("   → rapidapi.com → chercher 'API-NBA' → Subscribe (gratuit) → copier la clé")
        print("   → GitHub : Settings → Secrets → RAPIDAPI_KEY")
        save(load())
        return

    data = load()
    print(f"\n[RapidAPI] Clé détectée ✓")

    player_id = find_wemby_id(api_key)
    if not player_id:
        print("Impossible de trouver Wemby — abandon")
        save(data)
        return

    for season_str in ["2023-24", "2024-25"]:
        existing = data.setdefault("game_logs", {}).setdefault(season_str, [])
        print(f"\n── Saison {season_str} ({len(existing)} matchs existants) ──")
        new_games = fetch_rapid_gamelog(api_key, player_id, season_str)
        if new_games:
            data["game_logs"][season_str] = merge_games(existing, new_games)
        else:
            print("  Aucun match récupéré")

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
