import requests
from bs4 import BeautifulSoup
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import unr_play_by_play_scrape as pbp
import asyncio
import aiohttp
from fuzzywuzzy import fuzz

# Initialize Firebase
cred = credentials.Certificate("secrets/firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client(database_id="unrivaled-db")

# Base URL for Unrivaled schedule
BASE_URL = "https://www.unrivaled.basketball"
SCHEDULE_URL = f"{BASE_URL}/schedule"

def convert_to_firestore_date(date_str):
    """Convert date to Firestore format (YYYY-MM-DD)."""
    parsed_date = datetime.strptime(date_str, "%A, %B %d, %Y")
    return parsed_date.strftime("%Y-%m-%d")

def get_game_links_with_dates():
    """Scrape game links and their corresponding dates."""
    response = requests.get(SCHEDULE_URL)
    soup = BeautifulSoup(response.content, "html.parser")

    game_data = []
    date_containers = soup.find_all("div", class_="flex row-12 p-12")

    for container in date_containers:
        date = container.find("span", class_="uppercase weight-500").text.strip()
        date_text = convert_to_firestore_date(date)

        game_links = container.find_all("a", href=True)
        for a_tag in game_links:
            if "box-score" in a_tag["href"]:
                href = a_tag["href"]
                game_id = href.split("/")[2]
                game_link = f"{BASE_URL}{href}"
                game_data.append((game_link, game_id, date_text))

    return game_data

def format_player_name(player_href):
    """Format player names correctly from scraped data and match with Firebase names."""
    name_part = player_href.split("/player/")[1].rsplit("-", 1)[0]
    formatted_name = name_part.replace("-", " ").title()

    # Fetch all player names from the `players/` collection
    players_ref = db.collection("players").stream()
    player_names = [doc.id for doc in players_ref]  # Get all player names from Firebase

    # Find the best match in the Firebase collection
    best_match = None
    best_score = 0

    for player_name in player_names:
        # Calculate similarity score using fuzzy matching
        score = fuzz.ratio(formatted_name.lower(), player_name.lower())
        if score > best_score:
            best_score = score
            best_match = player_name

    # If the best match has a similarity score of 90% or higher, use the Firebase name
    if best_score >= 90:
        return best_match

    # Otherwise, return the formatted name
    return formatted_name

async def scrape_game_stats(session, game_url, game_id, game_date):
    """Scrape game statistics asynchronously and return DataFrame and metadata."""
    async with session.get(game_url) as response:
        content = await response.text()
        soup = BeautifulSoup(content, "html.parser")

        teams_div = soup.find_all("div", class_="scrollbar-none")
        team_names = [div.find("h4").text.strip() for div in teams_div if div.find("h4")]

        if len(team_names) != 2:
            print(f"Error extracting team names from {game_url}")
            return None, None

        home_team, away_team = team_names[0], team_names[1]
        home_team_pts, away_team_pts = 0, 0

        team_tables = [table for table in (div.find("table") for div in teams_div) if table is not None]
        
        if len(team_tables) == 2:
            try:
                home_team_pts = int(team_tables[0].find("tr", class_="weight-500").find_all("td")[-1].text.strip())
                away_team_pts = int(team_tables[1].find("tr", class_="weight-500").find_all("td")[-1].text.strip())
            except Exception as e:
                print(f"Error scraping team points: {e}")

        game_metadata = (game_id, game_date, home_team, away_team, home_team_pts, away_team_pts)

        players_stats = []
        tables = soup.find_all("table")

        for team, table in zip(team_names, tables):
            opponent = away_team if team == home_team else home_team
            rows = table.find("tbody").find_all("tr")

            for row in rows:
                cols = row.find_all("td")
                if cols[0].text.strip().upper() == "TEAM":
                    break

                player_link = cols[0].find("a")
                if player_link and "href" in player_link.attrs:
                    player_href = player_link["href"]
                    player_name = format_player_name(player_href)
                    print(player_name)
                else:
                    continue

                stats = [col.text.strip() if col.text.strip() else "0" for col in cols[1:]]

                if stats[0] == "DNP":
                    stats = ["0"] * 13

                players_stats.append([game_id, game_date, team, opponent, player_name] + stats)

        columns = [
            "game_id", "game_date", "team", "opponent", "player_name",
            "min", "fg", "three_pt", "ft", "reb", "offensive_rebounds", "defensive_rebounds", 
            "ast", "stl", "blk", "turnovers", "pf", "pts"
        ]

        return pd.DataFrame(players_stats, columns=columns), game_metadata

def insert_game_metadata_into_firestore(game_metadata):
    """Insert game metadata into Firestore under games/{game_id}."""
    game_id, game_date, home_team, away_team, home_team_pts, away_team_pts = game_metadata

    # Check if the game metadata already exists
    game_ref = db.collection("games").document(game_id)
    game_doc = game_ref.get()

    if game_doc.exists:
        print(f"⏩ Game metadata for game_id: {game_id} already exists in Firestore. Skipping...")
        return  # Skip if the game metadata already exists

    # Insert the game metadata into Firestore
    game_ref.set({
        "game_date": game_date,
        "home_team": home_team,
        "away_team": away_team,
        "home_team_score": home_team_pts,
        "away_team_score": away_team_pts
    }, merge=True)
    
    print(f"✅ Inserted/Updated game metadata for game_id: {game_id}")

def insert_game_stats_into_firestore(game_stats_df):
    """
    Insert player game stats into Firestore under players/{player_name}/games/{game_id}.
    Use the exact name from the `players/` collection for matching.
    """
    # Fetch all player names from the `players/` collection
    players_ref = db.collection("players").stream()
    player_names = {doc.id.lower(): doc.id for doc in players_ref}  # Map lowercase names to original names

    for _, row in game_stats_df.iterrows():
        # Get the player name from the DataFrame
        player_name = row["player_name"].replace(" ", "_")
        print(player_name)
        lowercase_player_name = player_name.lower()

        # Check if the player name exists in the `players/` collection (case-insensitive)
        if lowercase_player_name not in player_names:
            print(f"⚠ Player {player_name} not found in `players/` collection. Skipping...")
            continue  # Skip if the player name is not in the `players/` collection

        # Use the exact name from the `players/` collection
        exact_player_name = player_names[lowercase_player_name]
        game_id = row["game_id"]

        # Check if the game stats already exist for this player
        game_stats_ref = db.collection("players").document(exact_player_name).collection("games").document(game_id)
        game_stats_doc = game_stats_ref.get()

        if game_stats_doc.exists:
            print(f"⏩ Game stats for player {exact_player_name} (game_id: {game_id}) already exist in Firestore. Skipping...")
            continue  # Skip if the game stats already exist

        # Prepare the game stats data
        game_stats = row.to_dict()
        del game_stats["player_name"]  # Remove the player_name field since it's already in the document path

        # Insert the game stats into Firestore
        game_stats_ref.set(game_stats)
        print(f"✅ Inserted/Updated game stats for player {exact_player_name} (game_id: {game_id})")

    print(f"Inserted/Updated {len(game_stats_df)} records into Firestore.")

async def scrape_and_store_game(session, game_link, game_id, game_date):
    """Scrape and store data for a single game asynchronously."""
    # Check if the game already exists in Firestore
    game_ref = db.collection("games").document(game_id)
    game_doc = game_ref.get()

    if game_doc.exists:
        print(f"⏩ Game {game_id} already exists in Firestore. Skipping...")
        return  # Skip this game if it already exists

    print(f"🔄 Scraping game stats from: {game_link} (Date: {game_date})")
    game_stats_df, game_metadata = await scrape_game_stats(session, game_link, game_id, game_date)

    if game_stats_df is not None and game_metadata is not None:
        insert_game_metadata_into_firestore(game_metadata)
        insert_game_stats_into_firestore(game_stats_df)

    print(f"🎥 Scraping play-by-play for game: {game_id}")
    play_by_play_df = pbp.scrape_play_by_play(game_id, game_date, db)
    if play_by_play_df is not None:
        insert_play_by_play_into_firestore(game_id, play_by_play_df)

async def scrape_and_store_all_games():
    """Main function to scrape and store all game data asynchronously."""
    game_data = get_game_links_with_dates()

    async with aiohttp.ClientSession() as session:
        tasks = [scrape_and_store_game(session, game_link, game_id, game_date) for game_link, game_id, game_date in game_data]
        await asyncio.gather(*tasks)

    print("✅ All games scraped and stored.")

def insert_play_by_play_into_firestore(game_id, play_by_play_df):
    """Insert play-by-play data into Firestore with proper event_id sorting."""
    q4_index = 0  # Incremental index for Q4 events

    for _, row in play_by_play_df.iterrows():
        quarter = row["quarter"]
        time = row["time"]

        if quarter == "Q4":
            # For Q4, use an incremental index since it's untimed
            event_id = f"{quarter}_{q4_index:04d}"  # Pad with leading zeros for consistent sorting
            q4_index += 1  # Increment the index for the next Q4 event
        else:
            # Handle both "MM:SS" and "0:SS.S" time formats
            if ":" in time:
                # Split into minutes and seconds
                minutes, seconds = time.split(':')
                # Handle seconds with milliseconds (e.g., "58.9")
                seconds = seconds.split('.')[0]  # Ignore milliseconds
                total_seconds = int(minutes) * 60 + int(seconds)
            else:
                # Handle "SS.S" format (e.g., "58.9")
                try:
                    total_seconds = int(float(time))  # Convert to total seconds
                except ValueError:
                    print(f"⚠ Skipping row with invalid time format: {time}")
                    continue

            event_id = f"{quarter}_{total_seconds:04d}"  # Pad with leading zeros for consistent sorting

        # Insert the play-by-play event into Firestore
        db.collection("games").document(game_id).collection("play_by_play").document(event_id).set(row.to_dict())

    print(f"✅ Uploaded {len(play_by_play_df)} play-by-play events to Firestore.")

if __name__ == "__main__":
    asyncio.run(scrape_and_store_all_games())