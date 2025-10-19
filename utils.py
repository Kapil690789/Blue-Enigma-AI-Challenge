# utils.py
import requests
import config
import google.generativeai as genai
from pymongo.collection import Collection
import base64
import time

# --- Model Configuration ---
EMBEDDING_MODEL_NAME = 'models/text-embedding-004'
CHAT_MODEL_NAME = 'gemini-2.5-flash'
TOP_K_VEC_SEARCH = 5

# --- Embedding Function ---
def get_embedding(text: str) -> list[float]:
    if not text.strip(): return []
    try:
        return genai.embed_content(model=EMBEDDING_MODEL_NAME, content=text, task_type="retrieval_query")['embedding']
    except Exception as e:
        print(f"Error in get_embedding: {e}")
        return []

# --- Database Functions ---
def mongodb_vector_search(query_embedding: list[float], collection: Collection) -> list[dict]:
    if not query_embedding: return []
    pipeline = [
        {"$vectorSearch": {"index": config.MONGO_VECTOR_INDEX_NAME, "path": "embedding", "queryVector": query_embedding, "numCandidates": 100, "limit": TOP_K_VEC_SEARCH}},
        {"$project": {"embedding": 0, "_id": 0, "score": {"$meta": "vectorSearchScore"}}}
    ]
    try:
        return list(collection.aggregate(pipeline))
    except Exception as e:
        print(f"Error in mongodb_vector_search: {e}")
        return []

def fetch_relational_context(search_results: list[dict], collection: Collection) -> list[dict]:
    if not search_results: return []
    target_ids = [conn.get('target') for doc in search_results if 'connections' in doc for conn in doc['connections']]
    if not target_ids: return []
    try:
        return list(collection.find({"id": {"$in": list(set(target_ids))}}, {"_id": 0, "embedding": 0}))
    except Exception as e:
        print(f"Error in fetch_relational_context: {e}")
        return []

# --- Gemini REST API Call Functions ---
def call_gemini_rest(prompt: str) -> str:
    # This function remains the same
    api_url = f"https://generativelanguage.googleapis.com/v1/models/{CHAT_MODEL_NAME}:generateContent?key={config.GEMINI_API_KEY}"
    payload = { "contents": [{"parts": [{"text": prompt}]}], "safetySettings": [ {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}, ] }
    try:
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Error in call_gemini_rest: {e}")
        return "Sorry, an error occurred while contacting the AI."

def build_prompt(user_query: str, vector_results: list, relational_results: list, history: list) -> str:
    # This function remains the same
    vec_context_str = "\n".join([f"- {item.get('name')} ({item.get('type')}, Score: {item.get('score', 0):.2f}): {item.get('description', '')[:120]}..." for item in vector_results])
    rel_context_str = "\n".join([f"- {item.get('name')} ({item.get('type')}): {item.get('description', '')[:120]}..." for item in relational_results])
    history_str = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])
    return f"""You are an expert travel assistant for Vietnam. Use ONLY the provided context below to answer the user's question. Be concise and helpful. If the context does not contain the answer, say so.
## Conversation History:
{history_str if history_str else "No previous messages."}
## Context from Semantic Search (most relevant):
{vec_context_str if vec_context_str else "No search results found."}
## Context from Related Items:
{rel_context_str if rel_context_str else "No related items found."}
Based on all available information, answer the user's current question.
User's Current Question: "{user_query}"
"""

# --- NEW ROBUST VERSION with RETRIES ---
def describe_image(image_bytes: bytes) -> str:
    api_url = f"https://generativelanguage.googleapis.com/v1/models/{CHAT_MODEL_NAME}:generateContent?key={config.GEMINI_API_KEY}"
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    payload = { "contents": [{"parts": [{"text": "You are an expert in Vietnamese culture and travel. Describe this image in detail. If it's a landmark, name it. If it's food, identify the dish. Provide some interesting context or history about what you see."}, {"inline_data": {"mime_type": "image/jpeg", "data": encoded_image}}]}], "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}] }
    
    # Retry logic: Try up to 3 times
    for i in range(3):
        try:
            print(f"Attempting to call Gemini Vision API (Attempt {i+1}/3)...")
            response = requests.post(api_url, json=payload, timeout=45) # Increased timeout
            response.raise_for_status()
            data = response.json()
            print("Gemini Vision API call successful.")
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.Timeout:
            print(f"Attempt {i+1} timed out. Retrying in 2 seconds...")
            time.sleep(2)
        except Exception as e:
            print(f"An error occurred on attempt {i+1}: {e}")
            time.sleep(2)
            
    return "Sorry, I was unable to analyze the image after multiple attempts. The API seems to be unresponsive."