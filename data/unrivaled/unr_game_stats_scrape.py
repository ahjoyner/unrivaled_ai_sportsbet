import requests
from bs4 import BeautifulSoup
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import unr_play_by_play_scrape as pbp

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
    """Format player names correctly from scraped data."""
    name_part = player_href.split("/player/")[1].rsplit("-", 1)[0]
    formatted_name = name_part.replace("-", " ").title()
    return formatted_name

def scrape_game_stats(game_url, game_id, game_date):
    """Scrape game statistics and return DataFrame and metadata."""
    response = requests.get(game_url)
    soup = BeautifulSoup(response.content, "html.parser")

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
    """Insert game metadata into Firestore."""
    game_id, game_date, home_team, away_team, home_team_pts, away_team_pts = game_metadata

    db.collection("games").document(game_id).set({
        "game_date": game_date,
        "home_team": home_team,
        "away_team": away_team,
        "home_team_score": home_team_pts,
        "away_team_score": away_team_pts
    }, merge=True)
    
    print(f"Inserted/Updated game metadata for game_id: {game_id}")

def insert_game_stats_into_firestore(game_stats_df):
    """Insert player game stats into Firestore."""
    for _, row in game_stats_df.iterrows():
        player_name = row["player_name"]
        game_id = row["game_id"]

        game_stats = row.to_dict()
        del game_stats["player_name"]

        db.collection("players").document(player_name).collection("games").document(game_id).set(game_stats)

    print(f"Inserted/Updated {len(game_stats_df)} records into Firestore.")

def scrape_and_store_all_games():
    """Main function to scrape and store all game data."""
    game_data = get_game_links_with_dates()
    all_game_stats = []

    for game_link, game_id, game_date in game_data:
        print(f"🔄 Scraping game stats from: {game_link} (Date: {game_date})")
        game_stats_df, game_metadata = scrape_game_stats(game_link, game_id, game_date)

        if game_stats_df is not None and game_metadata is not None:
            all_game_stats.append(game_stats_df)
            insert_game_metadata_into_firestore(game_metadata)

        print(f"🎥 Scraping play-by-play for game: {game_id}")
        play_by_play_df = pbp.scrape_play_by_play(game_id, game_date, db)
        if play_by_play_df is not None:
            insert_play_by_play_into_firestore(game_id, play_by_play_df)

    if all_game_stats:
        final_df = pd.concat(all_game_stats, ignore_index=True)
        insert_game_stats_into_firestore(final_df)
        final_df.to_csv("data/unrivaled/csv/unrivaled_game_stats.csv", index=False)
        print("✅ Game stats saved to CSV and Firestore.")
    else:
        print("⚠ No game stats were scraped.")

def insert_play_by_play_into_firestore(game_id, play_by_play_df):
    """Insert play-by-play data into Firestore."""
    for _, row in play_by_play_df.iterrows():
        event_id = f"{row['quarter']}_{row['time'].replace(':', '')}"
        db.collection("games").document(game_id).collection("play_by_play").document(event_id).set(row.to_dict())

    print(f"✅ Inserted {len(play_by_play_df)} play-by-play records for game_id: {game_id}")

if __name__ == "__main__":
    scrape_and_store_all_games()
