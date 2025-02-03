import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import mysql.connector
from difflib import SequenceMatcher

# Function to match names
def get_player_id_and_position(player_name, enriched_data):
    """
    Get player_id and position from enriched data if the name matches.
    """
    for player in enriched_data:
        enriched_name = player["Player Data"]["name"]
        match_ratio = SequenceMatcher(None, player_name.lower(), enriched_name.lower()).ratio()
        if match_ratio > 0.8:  # Set threshold for a match
            return player["Player ID"], player["Player Data"].get("position", "Unknown")
    return None, "Unknown"

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

        # Extract stats
        stats = [col.text.strip() for col in cols[2:]]
        players.append([player_id, player_name, team_name, position] + stats)
    
    # Define columns
    columns = [
        "player_id", "name", "team", "position", "gp", "min", "pts", 
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
                player_id, name, team, position, gp, min, pts, offensive_rebounds, 
                defensive_rebounds, reb, ast, stl, blk, 
                turnovers, pf
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                gp = VALUES(gp), min = VALUES(min), pts = VALUES(pts),
                offensive_rebounds = VALUES(offensive_rebounds), 
                defensive_rebounds = VALUES(defensive_rebounds),
                reb = VALUES(reb), ast = VALUES(ast),
                stl = VALUES(stl), blk = VALUES(blk),
                turnovers = VALUES(turnovers), pf = VALUES(pf),
                position = VALUES(position);
            """
            data = (
                row["player_id"], row["name"], row["team"], row["position"], int(row["gp"]), float(row["min"]), float(row["pts"]),
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
    with open("data/unrivaled/unr_enriched_players.json", "r") as f:
        enriched_data = json.load(f)
    
    # Scrape player stats
    player_stats_df = scrape_player_stats(enriched_data)
    
    # Insert scraped data into the MySQL database
    insert_into_database(player_stats_df)
    player_stats_df.to_csv("data/unrivaled/csv/unrivaled_player_stats.csv", index=False)
    
    # Print the scraped DataFrame (optional)
    print(player_stats_df)
