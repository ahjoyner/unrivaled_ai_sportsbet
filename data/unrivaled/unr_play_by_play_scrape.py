import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import unicodedata
from difflib import get_close_matches
import re

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

        player = extract_player_name(play_desc, db)

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

def extract_player_name(play_description, db):
    """
    Extract the player name from the play description.
    Check if the matched name exists in the `players/` collection in Firestore.
    Returns the exact player name from Firestore if found, otherwise None.
    """
    # Define a regex pattern to match player names at the start of the description
    # Supports names like "Skylar Diggins-Smith", "Katie Lou Samuelson", "A'ja Wilson", etc.
    player_name_pattern = r"^([A-Z][a-z]+(?:['-]?[A-Z]?[a-z]+)*(?:\s[A-Z][a-z]+(?:['-]?[A-Z]?[a-z]+)*)*)"

    # Search for the player name in the play description
    match = re.match(player_name_pattern, play_description)
    if not match:
        return None  # Return None if no player name is found

    # Extract the matched player name
    matched_name = match.group(1).strip().replace(" ", "_")

    # Fetch all player names from the `players/` collection
    players_ref = db.collection("players").stream()
    player_names = {doc.id.lower(): doc.id for doc in players_ref}  # Map lowercase names to original names

    # Check if the matched name exists in the `players/` collection (case-insensitive)
    lowercase_matched_name = matched_name.lower()
    if lowercase_matched_name in player_names:
        return player_names[lowercase_matched_name]  # Return the exact name from Firestore

    return None  # Return None if the matched name is not in the `players/` collection

