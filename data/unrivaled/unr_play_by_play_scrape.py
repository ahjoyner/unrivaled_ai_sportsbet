import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import unicodedata
from difflib import get_close_matches

# Base URL for Unrivaled
BASE_URL = "https://www.unrivaled.basketball"

def normalize_text(text):
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')

def scrape_play_by_play(game_id, game_date, db):
    """
    Scrape play-by-play data for a specific game.
    """
    # Get list of player names from Firestore
    player_stats_ref = db.collection("players").stream()
    player_stats = {doc.id for doc in player_stats_ref}  # Use player_name as the key

    url = f"{BASE_URL}/game/{game_id}/play-by-play"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve play-by-play for game {game_id}")
        return None

    soup = BeautifulSoup(response.content, "html.parser")
    tbody = soup.find("tbody")

    if not tbody:
        print(f"No play-by-play data found for game {game_id}")
        return None

    plays = []
    for row in tbody.find_all("tr"):
        tds = row.find_all("td")

        time = tds[0].text.strip() if tds[0].text.strip() != "." else ""
        quarter_div = tds[1].find("div")
        quarter = quarter_div.text.strip() if quarter_div else ""

        play_desc = ' '.join([text.strip() for text in tds[1].find_all(string=True, recursive=False)])
        play_desc = re.sub(r"\s+", " ", play_desc).strip()
        play_desc = normalize_text(play_desc)

        team_img = tds[1].find("img", alt=True)
        team = team_img["alt"].replace(" Logo", "") if team_img and "Logo" in team_img["alt"] else None

        score = tds[2].text.strip()
        home_score, away_score = score.split("-") if "-" in score else ("", "")

        player = extract_player(play_desc, player_stats)

        plays.append({
            "game_id": game_id,
            "game_date": game_date,
            "quarter": quarter,
            "time": time,
            "play_description": play_desc,
            "home_score": home_score,
            "away_score": away_score,
            "team": team,
            "player": player
        })

    return pd.DataFrame(plays)

def extract_player(play_desc, player_stats):
    play_desc = normalize_text(play_desc)
    patterns = [
        r"^([A-Za-z]+(?: [A-Za-z\-]+)+) (makes|misses|assist|defensive rebound|offensive rebound|bad pass|personal foul|steal|block|turnover|free throw|bad pass turnover)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, play_desc)
        if match:
            extracted_player = match.group(1).strip()
            closest_matches = get_close_matches(extracted_player, player_stats, n=1, cutoff=0.8)
            return closest_matches[0] if closest_matches else None
    return None

def insert_play_by_play_into_firestore(play_by_play_df, db):
    index = 0
    for _, row in play_by_play_df.iterrows():
        game_id = str(row["game_id"])
        if row['quarter'] == "Q4":
            event_id = f"{row['quarter']}_{index}"  # Unique event ID
        else:
            event_id = f"{row['quarter']}_{row['time'].replace(':', '')}"  # Unique event ID

        db.collection("games").document(game_id).collection("play_by_play").document(event_id).set(row.to_dict())
        index += 1

    print(f"✅ Uploaded {len(play_by_play_df)} play-by-play events to Firestore.")
