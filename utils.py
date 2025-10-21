# utils.py
import requests
import config
import google.generativeai as genai
from pymongo.collection import Collection
import base64
import time
import hashlib
import json
from datetime import datetime, timedelta

# --- Model Configuration ---
EMBEDDING_MODEL_NAME = 'models/text-embedding-004'
CHAT_MODEL_NAME = 'gemini-2.5-flash'
TOP_K_VEC_SEARCH = 5
CACHE_TTL_SECONDS = 3600  # 1 hour cache
SIMILARITY_THRESHOLD = 0.92  # For query similarity

genai.configure(api_key=config.GEMINI_API_KEY)

# --- Embedding Function ---
def get_embedding(text: str) -> list[float]:
    """Generate embedding for text using Gemini."""
    if not text.strip():
        return []
    try:
        return genai.embed_content(
            model=EMBEDDING_MODEL_NAME,
            content=text,
            task_type="retrieval_query"
        )['embedding']
    except Exception as e:
        print(f"Error in get_embedding: {e}")
        return []

# --- Database Functions ---
def mongodb_vector_search(query_embedding: list[float], collection: Collection) -> list[dict]:
    """Perform vector search on MongoDB collection."""
    if not query_embedding:
        return []
    pipeline = [
        {
            "$vectorSearch": {
                "index": config.MONGO_VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 100,
                "limit": TOP_K_VEC_SEARCH
            }
        },
        {"$project": {"embedding": 0, "_id": 0, "score": {"$meta": "vectorSearchScore"}}}
    ]
    try:
        return list(collection.aggregate(pipeline))
    except Exception as e:
        print(f"Error in mongodb_vector_search: {e}")
        return []

def fetch_relational_context(search_results: list[dict], collection: Collection) -> list[dict]:
    """Fetch related nodes based on connections."""
    if not search_results:
        return []
    target_ids = [
        conn.get('target')
        for doc in search_results
        if 'connections' in doc
        for conn in doc['connections']
    ]
    if not target_ids:
        return []
    try:
        return list(collection.find(
            {"id": {"$in": list(set(target_ids))}},
            {"_id": 0, "embedding": 0}
        ))
    except Exception as e:
        print(f"Error in fetch_relational_context: {e}")
        return []

# --- NEW: Query Caching with Similarity ---
def compute_query_hash(query: str) -> str:
    """Create a hash for quick cache lookup."""
    return hashlib.md5(query.strip().lower().encode()).hexdigest()

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a ** 2 for a in vec1) ** 0.5
    magnitude2 = sum(b ** 2 for b in vec2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)

def find_cached_similar_response(
    query_embedding: list[float],
    collection: Collection
) -> dict | None:
    """Search for cached response to similar query."""
    try:
        # Look for cache entries from last hour
        cutoff_time = datetime.utcnow() - timedelta(seconds=CACHE_TTL_SECONDS)
        
        cache_entries = list(collection.find(
            {
                "is_cache": True,
                "cached_at": {"$gte": cutoff_time}
            },
            {"_id": 0}
        ).limit(50))  # Check recent 50 cache entries
        
        best_match = None
        best_similarity = 0
        
        for entry in cache_entries:
            if "query_embedding" in entry:
                sim = cosine_similarity(query_embedding, entry["query_embedding"])
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = entry
        
        if best_similarity >= SIMILARITY_THRESHOLD and best_match:
            return best_match
        
        return None
    except Exception as e:
        print(f"Error finding cached response: {e}")
        return None

def cache_response(
    query: str,
    query_embedding: list[float],
    response: str,
    collection: Collection
) -> None:
    """Store query-response pair in cache."""
    try:
        cache_entry = {
            "is_cache": True,
            "query": query,
            "query_embedding": query_embedding,
            "response": response,
            "cached_at": datetime.utcnow(),
            "query_hash": compute_query_hash(query)
        }
        collection.insert_one(cache_entry)
    except Exception as e:
        print(f"Error caching response: {e}")

# --- Gemini REST API Call Functions ---
def call_gemini_rest(prompt: str, max_retries: int = 2) -> str:
    """Call Gemini API via REST with retry logic."""
    api_url = f"https://generativelanguage.googleapis.com/v1/models/{CHAT_MODEL_NAME}:generateContent?key={config.GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"Timeout on attempt {attempt + 1}. Retrying...")
                time.sleep(2)
            else:
                return "Sorry, the API is taking too long. Please try again."
        except Exception as e:
            print(f"Error in call_gemini_rest (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    return "Sorry, an error occurred while contacting the AI. Please try again."

# --- NEW: Context Summarization ---
def summarize_conversation_context(history: list) -> str:
    """Summarize conversation history when it gets too long."""
    if len(history) < 5:
        return ""
    
    history_text = "\n".join([
        f"User: {msg['content']}\nAssistant: {msg['content']}"
        if msg['role'] == 'assistant'
        else f"User: {msg['content']}"
        for msg in history[:6]  # Summarize first 6 messages
    ])
    
    summary_prompt = f"""Analyze this travel conversation and provide a 2-3 sentence summary of:
1. What the traveler is looking for
2. Their apparent preferences/interests
3. Any constraints mentioned (budget, time, accessibility)

Conversation:
{history_text}

Summary:"""
    
    try:
        summary = call_gemini_rest(summary_prompt)
        return summary.strip()
    except Exception as e:
        print(f"Error summarizing context: {e}")
        return ""

def build_prompt(
    user_query: str,
    vector_results: list,
    relational_results: list,
    history: list
) -> str:
    """Build comprehensive prompt with context, search results, and history."""
    
    # Format search results
    vec_context_str = "\n".join([
        f"- {item.get('name')} ({item.get('type')}, Score: {item.get('score', 0):.2f}): {item.get('description', '')[:150]}..."
        for item in vector_results
    ]) or "No search results found."
    
    # Format relational context
    rel_context_str = "\n".join([
        f"- {item.get('name')} ({item.get('type')}): {item.get('description', '')[:150]}..."
        for item in relational_results
    ]) or "No related items found."
    
    # Format history with smart summarization
    if len(history) > 6:
        summary = summarize_conversation_context(history)
        history_str = f"Context Summary: {summary}\n\nLast 3 exchanges:\n"
        history_str += "\n".join([
            f"User: {msg['content']}" if msg['role'] == 'user' else f"Assistant: {msg['content']}"
            for msg in history[-6:]
        ])
    else:
        history_str = "\n".join([
            f"User: {msg['content']}" if msg['role'] == 'user' else f"Assistant: {msg['content']}"
            for msg in history
        ]) or "No previous conversation."
    
    return f"""You are an expert travel assistant specializing in Vietnam. You provide helpful, accurate, and contextual travel advice.

## Conversation Context:
{history_str}

## Most Relevant Information (from Knowledge Base):
{vec_context_str}

## Related Destinations & Experiences:
{rel_context_str}

## Instructions:
- Use ONLY the provided knowledge base information to answer
- Be concise but comprehensive
- If information isn't available, acknowledge and suggest alternatives
- Consider the traveler's preferences from conversation history
- Provide practical, actionable recommendations

## Current Question:
{user_query}

## Your Response:"""

def describe_image(image_bytes: bytes, max_retries: int = 3) -> str:
    """Analyze image using Gemini Vision with robust retry logic."""
    api_url = f"https://generativelanguage.googleapis.com/v1/models/{CHAT_MODEL_NAME}:generateContent?key={config.GEMINI_API_KEY}"
    
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {
                    "text": "You are an expert in Vietnamese culture and travel. Analyze this image in detail:\n1. What is shown?\n2. If it's a landmark, name it and provide historical context\n3. If it's food, identify the dish and explain its cultural significance\n4. Suggest related travel activities or destinations\n5. Provide travel tips specific to this location/experience"
                },
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": encoded_image
                    }
                }
            ]
        }],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    for attempt in range(max_retries):
        try:
            print(f"Analyzing image (Attempt {attempt + 1}/{max_retries})...")
            response = requests.post(api_url, json=payload, timeout=45)
            response.raise_for_status()
            data = response.json()
            print("Image analysis successful!")
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.Timeout:
            print(f"Attempt {attempt + 1} timed out. Retrying in 2 seconds...")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    return "Sorry, I was unable to analyze the image after multiple attempts. Please try uploading a different image."