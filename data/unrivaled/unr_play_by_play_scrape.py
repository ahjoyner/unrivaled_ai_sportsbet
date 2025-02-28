import requests
from bs4 import BeautifulSoup
import pandas as pd
import mysql.connector
import re
import unicodedata
from difflib import get_close_matches

# Base URL for Unrivaled
BASE_URL = "https://www.unrivaled.basketball"

def normalize_text(text):
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')

def scrape_play_by_play(game_id, game_date):
    """
    Scrape play-by-play data for a specific game.
    """
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Joynera4919",
        database="unrivaled"
    )
    cursor = connection.cursor()

    # Load player stats
    cursor.execute("SELECT name FROM player_stats")
    player_stats = {row[0] for row in cursor.fetchall()}

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

        # Extract time and handle Q4 (time is ".")
        time = tds[0].text.strip() if tds[0].text.strip() != "." else ""
        # print(time)

        # Extract quarter (Q1, Q2, etc.)
        quarter_div = tds[1].find("div")
        # print(quarter_div.text.strip())
        quarter = quarter_div.text.strip() if quarter_div else ""

        # Extract play description and team logo
        play_desc = ' '.join([
            text.strip() for text in tds[1].find_all(string=True, recursive=False)
        ])

        # Replace double spaces with a single space in the play description
        play_desc = re.sub(r"\s+", " ", play_desc).strip()
        play_desc = normalize_text(play_desc)
        # print(play_desc)

        team_img = tds[1].find("img", alt=True)
        team = team_img["alt"].replace(" Logo", "") if team_img and "Logo" in team_img["alt"] else None

        # Extract scores
        score = tds[2].text.strip()
        home_score, away_score = score.split("-") if "-" in score else ("", "")

        # Extract player from play description
        player = extract_player(play_desc, player_stats)
        # print(player)

        plays.append({
            "game_id": game_id,
            "game_date": game_date,
            "quarter": quarter,
            "time": time,
            "play_description": play_desc,
            "home_score": home_score,
            "away_score": away_score,
            "team": team,    # Team involved in the play
            "player": player # Player involved (if any)
        })

    columns = [
        "game_id", "game_date", "quarter", "time", "play_description",
        "home_score", "away_score", "team", "player"
    ]
    # for play in plays:
        # print(play)
    return pd.DataFrame(plays, columns=columns)

def extract_player(play_desc, player_stats):
    play_desc = normalize_text(play_desc)
    """
    Extract the player name from the play description using regex.
    If an exact match is not found in player_stats, attempt to find a close match.
    """
    patterns = [
        r"^([A-Za-z]+(?: [A-Za-z\-]+)+) (makes|misses|assist|defensive rebound|offensive rebound|bad pass|personal foul|steal|block|turnover|free throw|bad pass turnover)",
        r"([A-Za-z]+(?: [A-Za-z\-]+)+)(?=\s*\() defensive rebound",
        r"([A-Za-z]+(?: [A-Za-z\-]+)+)(?=\s*\() offensive rebound",
        r"([A-Za-z]+(?: [A-Za-z\-]+)+)(?=\s*\() assist",
        r"([A-Za-z]+(?: [A-Za-z\-]+)+)(?=\s*\() personal foul",
        r"([A-Za-z]+(?: [A-Za-z\-]+)+) bad pass turnover",
    ]
    
    extracted_player = None

    # Try extracting player name using regex
    for pattern in patterns:
        match = re.search(pattern, play_desc)
        if match:
            extracted_player = match.group(1).strip()
            break

    if extracted_player:
        # If the player exists in player_stats, return exact match
        if extracted_player in player_stats:
            return extracted_player

        # Otherwise, find the closest match from player_stats
        closest_matches = get_close_matches(extracted_player, player_stats, n=1, cutoff=0.8)
        if closest_matches:
            return closest_matches[0]  # Use the closest matched name

    return None  # No valid match found


def insert_play_by_play_into_database(play_by_play_df):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Joynera4919",
            database="unrivaled"
        )
        cursor = connection.cursor()

        for _, row in play_by_play_df.iterrows():
            data = (
                row["game_id"],
                row["game_date"],
                row["quarter"],
                row["time"],
                row["play_description"],
                int(row["home_score"]) if row["home_score"] else 0,
                int(row["away_score"]) if row["away_score"] else 0,
                row["team"],
                row["player"]
            )

            sql_query = """
            INSERT INTO play_by_play 
                (game_id, game_date, quarter, time, play_description, home_score, away_score, team, player)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                player = VALUES(player);
            """
            cursor.execute(sql_query, data)

        connection.commit()
        print(f"Inserted {len(play_by_play_df)} plays into the play_by_play table.")
    
    except mysql.connector.Error as e:
        print(f"Error inserting play-by-play: {e}")
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def test_scrape():
    """
    Test the scraper with a specific game link.
    """
    game_id = "sjrwaj31kq62"  # Example game ID
    game_date = "2023-10-01"  # Example date

    # Scrape play-by-play data
    play_by_play_df = scrape_play_by_play(game_id, game_date)
    
    if play_by_play_df is not None:
        print(play_by_play_df.head())  # Display the first few rows
        play_by_play_df.to_csv(f"data/unrivaled/csv/pay_by_play/play_by_play_{game_id}.csv", index=False)  # Save to CSV
        print(f"Play-by-play data saved to play_by_play_{game_id}.csv")
