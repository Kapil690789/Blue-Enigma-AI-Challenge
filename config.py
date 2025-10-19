# config.py
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

MONGO_DATABASE_NAME = "travel_db"
MONGO_COLLECTION_NAME = "vietnam_travel"
MONGO_VECTOR_INDEX_NAME = "vector_index"