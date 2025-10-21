# gemini_mongo_chat.py
import config
import requests
import json
from pymongo import MongoClient
import google.generativeai as genai
import utils

# --- Configuration ---
CHAT_MODEL_NAME = 'gemini-2.5-flash'
EMBEDDING_MODEL_NAME = 'models/text-embedding-004'
TOP_K_VEC_SEARCH = 5

# --- Initialize Clients ---
print("🚀 Initializing MongoDB and Gemini clients...")
genai.configure(api_key=config.GEMINI_API_KEY)

try:
    client = MongoClient(config.MONGO_URI)
    db = client[config.MONGO_DATABASE_NAME]
    collection = db[config.MONGO_COLLECTION_NAME]
    client.admin.command('ping')
    print("✓ MongoDB connection successful")
except Exception as e:
    print(f"❌ Error connecting to MongoDB: {e}")
    exit(1)

def interactive_chat():
    """Run interactive chat session with caching support."""
    print("\n" + "="*60)
    print("🎉 Welcome to Vietnam Travel Assistant (CLI)")
    print("="*60)
    print("Features:")
    print("  • Semantic search on MongoDB Atlas")
    print("  • Intelligent query caching")
    print("  • Multi-turn conversation history")
    print("  • Powered by Gemini 2.5 Flash")
    print("\nType 'exit' or 'quit' to end the chat")
    print("="*60 + "\n")
    
    conversation_history = []
    cache_stats = {"hits": 0, "misses": 0}
    
    while True:
        # Get user input
        try:
            query = input("\n📝 You: ").strip()
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        
        if not query:
            print("⚠️ Please enter a question.")
            continue
        
        if query.lower() in ("exit", "quit"):
            print("\n👋 Thank you for using Vietnam Travel Assistant!")
            print(f"\n📊 Final Cache Statistics:")
            print(f"   Cache Hits: {cache_stats['hits']}")
            print(f"   Cache Misses: {cache_stats['misses']}")
            if cache_stats['hits'] + cache_stats['misses'] > 0:
                hit_rate = cache_stats['hits'] / (cache_stats['hits'] + cache_stats['misses']) * 100
                print(f"   Hit Rate: {hit_rate:.1f}%")
            break
        
        # Get query embedding
        query_embedding = utils.get_embedding(query)
        if not query_embedding:
            print("❌ Sorry, I couldn't process your query. Please try again.")
            continue
        
        # Check cache for similar response
        cached_entry = utils.find_cached_similar_response(query_embedding, collection)
        
        if cached_entry:
            print("\n" + "="*60)
            print("💾 Response from Cache (Similar Query Found)")
            print("="*60)
            print(f"\n🤖 Assistant:\n{cached_entry['response']}")
            cache_stats['hits'] += 1
        else:
            # Cache miss: perform full RAG
            cache_stats['misses'] += 1
            
            print("\n⏳ Thinking...")
            
            # Perform vector search
            vector_matches = utils.mongodb_vector_search(query_embedding, collection)
            
            # Fetch relational context
            relational_context = utils.fetch_relational_context(vector_matches, collection)
            
            # Build comprehensive prompt
            prompt_for_llm = utils.build_prompt(
                query,
                vector_matches,
                relational_context,
                conversation_history
            )
            
            # Get response from Gemini
            response = utils.call_gemini_rest(prompt_for_llm)
            
            # Cache the response
            utils.cache_response(query, query_embedding, response, collection)
            
            print("\n" + "="*60)
            print("🤖 Assistant:")
            print("="*60)
            print(f"\n{response}")
        
        # Add to conversation history
        conversation_history.append({"role": "user", "content": query})
        conversation_history.append({"role": "assistant", "content": cached_entry.get('response') if cached_entry else response})
        
        # Print cache statistics after every query
        total_queries = cache_stats['hits'] + cache_stats['misses']
        if total_queries > 0:
            hit_rate = cache_stats['hits'] / total_queries * 100
            print(f"\n📊 Cache Stats: {cache_stats['hits']} hits, {cache_stats['misses']} misses ({hit_rate:.1f}% hit rate)")
        
        print("\n" + "-"*60)

if __name__ == "__main__":
    interactive_chat()