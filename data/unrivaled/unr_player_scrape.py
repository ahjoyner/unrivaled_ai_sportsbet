import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import mysql.connector
from difflib import SequenceMatcher
import unicodedata

def normalize_text(text):
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')

# Function to match names
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

# Function to generate headshot URL
def generate_headshot_url(player_name, team_name):
    """
    Generate the headshot URL based on player name and team name.
    """
    # Format player name and team name for the URL
    formatted_player_name = player_name.lower().replace(' ', '-')
    formatted_team_name = team_name.lower().replace(' ', '-')
    
    # Special case for Lunar-Owls
    if formatted_team_name == "lunar-owls":
        formatted_team_name = "lunar-owls"
    
    # Generate the headshot URL
    headshot_url = f"https://pub-ad8cc693759b4b55a181a76af041efa0.r2.dev/players/{formatted_player_name}/images/{formatted_team_name}-headshot.jpg?v=1738721238937"
    return headshot_url

# Function to scrape player stats
def scrape_player_stats(enriched_data):
    url = "https://www.unrivaled.basketball/stats/player"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    
    players = []
    
    tbody = soup.find("tbody")
    rows = tbody.find_all("tr")
    
    for row in rows:
        cols = row.find_all("td")
        
        # Skip the row number
        player_name = cols[1].find("a").text.strip()  # Player name
        team_img_src = cols[1].find("img")["src"]  # Extract img src
        team_name = team_img_src.split("/teams/")[1].split("/images/")[0].replace('-', ' ').title()  # Extract team name
        
        # Get player_id from enriched data
        player_id, position = get_player_id_and_position(player_name, enriched_data)

        # Generate headshot URL
        normalized_enriched = normalize_text(player_name)
        headshot_url = generate_headshot_url(normalized_enriched, team_name)

        # Extract stats
        stats = [col.text.strip() for col in cols[2:]]
        players.append([player_id, normalized_enriched, team_name, position, headshot_url] + stats)
    
    # Define columns
    columns = [
        "player_id", "name", "team", "position", "headshot_url", "gp", "min", "pts", 
        "offensive_rebounds", "defensive_rebounds", "reb", 
        "ast", "stl", "blk", "turnovers", "pf"
    ]
    
    # Create DataFrame
    player_stats_df = pd.DataFrame(players, columns=columns)
    return player_stats_df

# Function to insert data into MySQL database
def insert_into_database(player_stats_df):
    try:
        # Connect to the database
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Joynera4919",
            database="unrivaled"
        )
        cursor = connection.cursor()
        
        # Insert each row into the player_stats table
        for _, row in player_stats_df.iterrows():
            if not row["player_id"]:
                print(f"Skipping player '{row['name']}' due to missing player_id.")
                continue

            sql_query = """
            INSERT INTO player_stats (
                player_id, name, team, position, headshot_url, gp, min, pts, offensive_rebounds, 
                defensive_rebounds, reb, ast, stl, blk, 
                turnovers, pf
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                gp = VALUES(gp), min = VALUES(min), pts = VALUES(pts),
                offensive_rebounds = VALUES(offensive_rebounds), 
                defensive_rebounds = VALUES(defensive_rebounds),
                reb = VALUES(reb), ast = VALUES(ast),
                stl = VALUES(stl), blk = VALUES(blk),
                turnovers = VALUES(turnovers), pf = VALUES(pf),
                position = VALUES(position),
                headshot_url = VALUES(headshot_url);
            """
            data = (
                row["player_id"], row["name"], row["team"], row["position"], row["headshot_url"], 
                int(row["gp"]), float(row["min"]), float(row["pts"]),
                float(row["offensive_rebounds"]), float(row["defensive_rebounds"]), float(row["reb"]),
                float(row["ast"]), float(row["stl"]), float(row["blk"]),
                float(row["turnovers"]), float(row["pf"])
            )
            cursor.execute(sql_query, data)
        
        # Commit the transaction
        connection.commit()
        print(f"Inserted/Updated {len(player_stats_df)} records into the player_stats table.")
    
    except mysql.connector.Error as e:
        print(f"Error: {e}")
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Main execution
if __name__ == "__main__":
    # Load enriched player data
    with open("/Users/ajoyner/Desktop/unrivaled_ai_sportsbet/data/unrivaled/unr_enriched_players.json", "r") as f:
        enriched_data = json.load(f)
    
    # Scrape player stats
    player_stats_df = scrape_player_stats(enriched_data)
    
    # Insert scraped data into the MySQL database
    insert_into_database(player_stats_df)
    player_stats_df.to_csv("data/unrivaled/csv/unrivaled_player_stats.csv", index=False)
    
    # Print the scraped DataFrame (optional)
    print(player_stats_df)