import json
import urllib3
import requests
from requests.exceptions import RequestException
import firebase_admin
from firebase_admin import credentials, firestore

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ScraperAPI proxy setup
SCRAPERAPI_KEY = "ecf457a0b5d6ab754c5e422f430e0fc5"
PROXY = f"http://scraperapi:{SCRAPERAPI_KEY}@proxy-server.scraperapi.com:8001"
PROXIES = {"https": PROXY}

# Firebase setup
FIRESTORE_COLLECTION = "prop_lines"  # Firestore collection name

# Initialize Firestore using your existing method
cred = credentials.Certificate("secrets/firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client(database_id="unrivaled-db")

def clear_firestore_collection(collection_name):
    """Clear all documents in a Firestore collection."""
    print(f"Clearing collection: {collection_name}")
    docs = db.collection(collection_name).stream()
    for doc in docs:
        doc.reference.delete()
    print(f"Collection {collection_name} cleared.")

def upload_to_firestore(collection_name, player_id, data):
    """Upload data to Firestore under a specific player_id."""
    doc_ref = db.collection(collection_name).document(player_id)
    doc_ref.set(data)
    print(f"Uploaded data for Player {player_id} to Firestore.")

def fetch_player_data(player_id):
    """Fetch player data from the API."""
    url = f"https://api.prizepicks.com/players/{player_id}"
    try:
        response = requests.get(url, proxies=PROXIES, verify=False)
        response.raise_for_status()
        print(f"Success for Player {player_id}!")
        return response.json()
    except RequestException as e:
        print(f"Failed to fetch data for player {player_id}: {e}")
        return None

def main():
    # Clear the prop_lines collection before uploading new data
    clear_firestore_collection(FIRESTORE_COLLECTION)

    # Load player IDs
    with open("data/unrivaled/player_ids.json", "r") as f:
        player_ids = json.loads(f.read())

    # Load projections
    with open("data/unrivaled/unr_bets.json", "r") as f:
        projections = json.load(f)

    # Fetch player data and merge with projections
    for projection in projections["data"]:
        if projection["attributes"].get("stat_display_name") == "Points":
            player_id = projection["relationships"]["new_player"]["data"]["id"]
            player_data = fetch_player_data(player_id)
            if player_data:
                # Prepare data for Firestore
                firestore_data = {
                    "player_data": player_data["data"]["attributes"],
                    "projection_data": projection["attributes"]
                }

                # Upload data to Firestore
                upload_to_firestore(FIRESTORE_COLLECTION, player_id, firestore_data)

    print("Enriched players data uploaded to Firestore.")

if __name__ == "__main__":
    main()
