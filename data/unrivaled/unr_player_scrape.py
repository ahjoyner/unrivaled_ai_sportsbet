import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from difflib import SequenceMatcher
import unicodedata
from datetime import datetime
import os

cred = credentials.Certificate("secrets/firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client(database_id="unrivaled-db")

def normalize_text(text):
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')

def convert_to_firestore_date(date_str):
    """Convert date to Firestore format (YYYY-MM-DD)."""
    parsed_date = datetime.strptime(date_str, "%b %d, %Y")
    return parsed_date.strftime("%Y-%m-%d")

def get_player_id_and_position(player_name, enriched_data):
    """
    Get player_id and position from enriched data if the name matches.
    """
    normalized_input = normalize_text(player_name)
    for player in enriched_data:
        enriched_name = player["Player Data"]["name"]
        normalized_enriched = normalize_text(enriched_name)
        match_ratio = SequenceMatcher(None, normalized_input.lower(), normalized_enriched.lower()).ratio()
        if match_ratio > 0.8:  # Set threshold for a match
            return player["Player ID"], player["Player Data"].get("position", "Unknown")
    return None, "Unknown"

def generate_headshot_url(player_name, team_name):
    """
    Generate the headshot URL based on player name and team name.
    """
    formatted_player_name = player_name.lower().replace(' ', '-')
    formatted_team_name = team_name.lower().replace(' ', '-')
    
    if formatted_team_name == "lunar-owls":
        formatted_team_name = "lunar-owls"
    
    headshot_url = f"https://pub-ad8cc693759b4b55a181a76af041efa0.r2.dev/players/{formatted_player_name}/images/{formatted_team_name}-headshot.jpg?v=1738721238937"
    return headshot_url

def convert_stat(stat, index):
    try:
        if index == 0:  # gp should be int
            return int(stat)
        else:  # All other stats should be float
            return float(stat)
    except ValueError:
        return 0  # Default value for invalid data

def scrape_player_stats(enriched_data):
    url = "https://www.unrivaled.basketball/stats/player"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    
    players = []
    tbody = soup.find("tbody")
    rows = tbody.find_all("tr")
    
    for row in rows:
        cols = row.find_all("td")
        player_name = cols[1].find("a").text.strip()
        player_url = cols[1].find("a")["href"]
        team_img_src = cols[1].find("img")["src"]
        team_name = team_img_src.split("/teams/")[1].split("/images/")[0].replace('-', ' ').title()
        
        player_id, position = get_player_id_and_position(player_name, enriched_data)
        normalized_enriched = normalize_text(player_name)
        headshot_url = generate_headshot_url(normalized_enriched, team_name)

        # Convert stats to appropriate types
        stats = [convert_stat(col.text.strip(), idx) for idx, col in enumerate(cols[2:])]
        players.append([player_id, normalized_enriched, player_url, team_name, position, headshot_url] + stats)
    
    columns = [
        "player_id", "name", "player_url", "team", "position", "headshot_url", "gp", "min", "pts", 
        "offensive_rebounds", "defensive_rebounds", "reb", 
        "ast", "stl", "blk", "turnovers", "pf"
    ]
    
    player_stats_df = pd.DataFrame(players, columns=columns)
    return player_stats_df

def scrape_player_game_stats(player_url):
    """Scrape a player's game stats from their individual stats page."""
    response = requests.get("https://www.unrivaled.basketball/" + player_url)
    soup = BeautifulSoup(response.content, "html.parser")

    print("https://www.unrivaled.basketball/" + player_url)

    games = []
    tbody = soup.find("tbody")
    if not tbody:
        return games

    rows = tbody.find_all("tr")
    for row in rows:
        cols = row.find_all("td")

        game_link = cols[0].find("a")["href"]
        game_id = game_link.split("/game/")[1]

        date = cols[0].find("a").text.strip()
        game_date = convert_to_firestore_date(date)
        print(f"Found game date: {game_date}")

        min_played = int(cols[2].text.strip())
        fg = cols[3].text.strip().split("-")
        three_pt = cols[4].text.strip().split("-")
        ft = cols[5].text.strip().split("-")
        reb = int(cols[6].text.strip())
        offensive_rebounds = int(cols[7].text.strip())
        defensive_rebounds = int(cols[8].text.strip())
        ast = int(cols[9].text.strip())
        stl = int(cols[10].text.strip())
        blk = int(cols[11].text.strip())
        to = int(cols[12].text.strip())
        pf = int(cols[13].text.strip())
        pts = int(cols[14].text.strip())

        fg_made = int(fg[0]) if len(fg) == 2 else 0
        fg_attempted = int(fg[1]) if len(fg) == 2 else 0
        three_pt_made = int(three_pt[0]) if len(three_pt) == 2 else 0
        three_pt_attempted = int(three_pt[1]) if len(three_pt) == 2 else 0
        ft_made = int(ft[0]) if len(ft) == 2 else 0
        ft_attempted = int(ft[1]) if len(ft) == 2 else 0

        games.append({
            "game_id": game_id,
            "game_date": game_date,
            "min": min_played,
            "fg_m": fg_made,
            "fg_a": fg_attempted,
            "three_pt_m": three_pt_made,
            "three_pt_a": three_pt_attempted,
            "ft_m": ft_made,
            "ft_a": ft_attempted,
            "reb": reb,
            "offensive_rebounds": offensive_rebounds,
            "defensive_rebounds": defensive_rebounds,
            "ast": ast,
            "stl": stl,
            "blk": blk,
            "turnovers": to,
            "pf": pf,
            "pts": pts,
        })

    return games

def insert_into_firestore(player_stats_df):
    players_ref = db.collection("players").stream()
    player_names = {doc.id.lower(): doc.id for doc in players_ref} 

    for _, row in player_stats_df.iterrows():
        player_data = row.to_dict()
        player_name = player_data["name"]
        player_url = row["player_url"]

        # Replace spaces with underscores in the player name
        player_name_firestore = player_name.replace(" ", "_")

        player_game_stats = scrape_player_game_stats(player_url)
        
        del player_data["name"]
        del player_data["player_url"]

        # Save player data with the normalized player name
        db.collection("players").document(player_name_firestore).set(player_data)

        for game_stats in player_game_stats:
            game_id = game_stats["game_id"]
            # Save game stats under the normalized player name
            db.collection("players").document(player_name_firestore).collection("games").document(game_id).set(game_stats)

    print(f"Inserted/Updated {len(player_stats_df)} player records and their game stats into Firestore.")

if __name__ == "__main__":
    with open("/Users/ajoyner/unrivaled_ai_sportsbet/data/unrivaled/unr_enriched_players.json", "r") as f:
        enriched_data = json.load(f)
    
    player_stats_df = scrape_player_stats(enriched_data)
    insert_into_firestore(player_stats_df)
    player_stats_df.to_csv("data/unrivaled/csv/unrivaled_player_stats.csv", index=False)
    print(player_stats_df)