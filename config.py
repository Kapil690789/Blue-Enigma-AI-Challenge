# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- MongoDB Configuration ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DATABASE_NAME = "travel_db"
MONGO_COLLECTION_NAME = "vietnam_travel"
MONGO_VECTOR_INDEX_NAME = "vector_index"

# --- Application Configuration ---
EMBEDDING_MODEL = "models/text-embedding-004"
CHAT_MODEL = "gemini-2.5-flash"
TOP_K_RESULTS = 5

# --- Cache Configuration ---
CACHE_TTL_SECONDS = 3600  # 1 hour
SIMILARITY_THRESHOLD = 0.92  # For query matching

# Validation
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found in environment variables!")
if not MONGO_URI:
    raise ValueError("❌ MONGO_URI not found in environment variables!")

print("✓ Configuration loaded successfully")