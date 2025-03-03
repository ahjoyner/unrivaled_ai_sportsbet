import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

# Load env vars
load_dotenv("../../unrivaled-dash/.env.local")

# Firebase Setup
cred = credentials.Certificate("../../secrets/firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client(database_id="unrivaled-db")

# DeepSeek API Settings
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
