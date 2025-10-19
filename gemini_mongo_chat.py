# gemini_mongo_chat.py
import config
import requests
import json
from pymongo import MongoClient
import google.generativeai as genai

# --- Configuration ---
CHAT_MODEL_NAME = 'gemini-2.5-flash' # Using the model you confirmed works!
EMBEDDING_MODEL_NAME = 'models/text-embedding-004'
TOP_K_VEC_SEARCH = 5

# --- Initialize Clients ---
# We still use the genai library for embeddings as it's working well.
genai.configure(api_key=config.GEMINI_API_KEY) 

try:
    client = MongoClient(config.MONGO_URI)
    db = client[config.MONGO_DATABASE_NAME]
    collection = db[config.MONGO_COLLECTION_NAME]
    client.admin.command('ping')
    print("MongoDB connection successful.")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    exit()

# --- Helper Functions (No changes here) ---
def get_embedding(text: str) -> list[float]:
    if not text.strip(): return []
    try:
        return genai.embed_content(model=EMBEDDING_MODEL_NAME, content=text, task_type="retrieval_query")['embedding']
    except Exception as e:
        print(f"An error occurred while generating query embedding: {e}")
        return []

def mongodb_vector_search(query_embedding: list[float]) -> list[dict]:
    if not query_embedding: return []
    pipeline = [
        {"$vectorSearch": {"index": config.MONGO_VECTOR_INDEX_NAME, "path": "embedding", "queryVector": query_embedding, "numCandidates": 100, "limit": TOP_K_VEC_SEARCH}},
        {"$project": {"embedding": 0, "_id": 0, "score": {"$meta": "vectorSearchScore"}}}
    ]
    try:
        return list(collection.aggregate(pipeline))
    except Exception as e:
        print(f"Error during vector search: {e}")
        return []

def fetch_relational_context(search_results: list[dict]) -> list[dict]:
    if not search_results: return []
    target_ids = [conn.get('target') for doc in search_results if 'connections' in doc for conn in doc['connections']]
    if not target_ids: return []
    try:
        return list(collection.find({"id": {"$in": list(set(target_ids))}}, {"_id": 0, "embedding": 0}))
    except Exception as e:
        print(f"Error fetching relational context: {e}")
        return []

def build_prompt(user_query: str, vector_results: list, relational_results: list, history: list):
    vec_context_str = "\n".join([f"- {item.get('name')} ({item.get('type')}, Score: {item.get('score', 0):.2f}): {item.get('description', '')[:120]}..." for item in vector_results])
    rel_context_str = "\n".join([f"- {item.get('name')} ({item.get('type')}): {item.get('description', '')[:120]}..." for item in relational_results])
    
    # For the REST API, we'll build the history directly into the prompt string
    history_str = "\n".join([f"Previous User Question: {entry['user']}\nPrevious Assistant Answer: {entry['assistant']}" for entry in history])

    return f"""You are an expert travel assistant for Vietnam. Use ONLY the provided context below to answer the user's question. Be concise and helpful. If the context does not contain the answer, say so.

## Conversation History:
{history_str}

## Context from Semantic Search (most relevant):
{vec_context_str}

## Context from Related Items:
{rel_context_str}

Based on all available information, answer the user's current question.
User's Current Question: "{user_query}"
"""

# --- NEW: Function to call Gemini via REST API ---
def call_gemini_rest(prompt: str) -> str:
    """Calls the Gemini API using a direct requests.post call."""
    api_url = f"https://generativelanguage.googleapis.com/v1/models/{CHAT_MODEL_NAME}:generateContent?key={config.GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # Adding safety settings to prevent the model from blocking valid responses
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }
    
    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status() # Raises an exception for bad status codes (4xx or 5xx)
        data = response.json()
        
        # Extract the text from the response
        return data["candidates"][0]["content"]["parts"][0]["text"]
        
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Gemini REST API: {e}")
        if 'response' in locals() and response is not None:
            print("Response text:", response.text)
        return "Sorry, I encountered a technical error. Please try again."
    except (KeyError, IndexError) as e:
        print(f"Error parsing Gemini response: {e}")
        print("Full response data:", data)
        return "Sorry, I received an unexpected response from the AI."

def interactive_chat():
    print("\n--- Gemini Powered Vietnam Travel Assistant ---")
    print("Type 'exit' or 'quit' to end the chat.")
    conversation_history = []
    
    while True:
        query = input("\nEnter your travel question: ").strip()
        if not query: continue
        if query.lower() in ("exit", "quit"):
            print("Goodbye!"); break

        query_embedding = get_embedding(query)
        if not query_embedding:
            print("Sorry, I couldn't process your query."); continue

        vector_matches = mongodb_vector_search(query_embedding)
        relational_context = fetch_relational_context(vector_matches)
        prompt = build_prompt(query, vector_matches, relational_context, conversation_history)
        
        print("\n--- Assistant's Answer ---")
        
        # --- MODIFIED: Call our new REST function ---
        full_response = call_gemini_rest(prompt)
        print(full_response) # Print the full response at once
        
        print("\n--------------------------\n")
        conversation_history.append({"user": query, "assistant": full_response})

if __name__ == "__main__":
    interactive_chat()