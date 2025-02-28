import json
import urllib3
import requests
from requests.exceptions import RequestException

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ScraperAPI proxy setup
SCRAPERAPI_KEY = "ecf457a0b5d6ab754c5e422f430e0fc5"
PROXY = f"http://scraperapi:{SCRAPERAPI_KEY}@proxy-server.scraperapi.com:8001"
PROXIES = {"https": PROXY}

def fetch_player_data(player_id):
    url = f"https://api.prizepicks.com/players/{player_id}"
    try:
        response = requests.get(url, proxies=PROXIES, verify=False)
        # print(response)
        response.raise_for_status()
        print(f"Success for Player {player_id}!")
        return response.json()
    except RequestException as e:
        print(f"Failed to fetch data for player {player_id}: {e}")
        return None

def main():
    # Load player IDs
    with open("data/unrivaled/player_ids.json", "r") as f:
        player_ids = json.loads(f.read())

    # Load projections
    with open("data/unrivaled/unr_bets.json", "r") as f:
        projections = json.load(f)

    enriched_players = []

    # Fetch player data and merge with projections
    for projection in projections["data"]:
        if projection["attributes"].get("stat_display_name") == "Points":
            player_id = projection["relationships"]["new_player"]["data"]["id"]
            player_data = fetch_player_data(player_id)
            if player_data:
                enriched_players.append({
                    "Player ID": player_id,
                    "Player Data": player_data["data"]["attributes"],
                    "Projection Data": projection["attributes"]
                })

    # Write enriched data to unr_enriched_players.json
    with open("/Users/ajoyner/unrivaled_ai_sportsbet/data/unrivaled/unr_enriched_players.json", "w") as f:
        json.dump(enriched_players, f, indent=4)

    print("Enriched players data saved to unr_enriched_players.json.")

if __name__ == "__main__":
    main()
