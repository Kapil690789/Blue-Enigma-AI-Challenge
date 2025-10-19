# load_to_mongodb.py
import json
import config
from tqdm import tqdm
from pymongo import MongoClient
import google.generativeai as genai

# --- Configuration ---
DATA_FILE = "vietnam_travel_dataset.json" # Make sure this file is in your project folder
EMBEDDING_MODEL = 'models/text-embedding-004'
BATCH_SIZE = 100 # How many documents to embed and insert at once

# --- Initialize Clients ---
print("Initializing clients...")
genai.configure(api_key=config.GEMINI_API_KEY)
try:
    client = MongoClient(config.MONGO_URI)
    db = client[config.MONGO_DATABASE_NAME]
    collection = db[config.MONGO_COLLECTION_NAME]
    # Test connection
    client.admin.command('ping')
    print("MongoDB connection successful.")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    exit()

def get_gemini_embeddings(texts: list[str]) -> list[list[float]]:
    """Generates embeddings for a list of texts using the Gemini API."""
    if not texts:
        return []
    try:
        # The new API for embeddings
        result = genai.embed_content(model=EMBEDDING_MODEL, content=texts, task_type="retrieval_document")
        return result['embedding']
    except Exception as e:
        print(f"An error occurred while generating embeddings: {e}")
        return [[] for _ in texts] # Return empty embeddings on error for robustness

def main():
    """Main function to process and upload data."""
    print("Loading data from JSON file...")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    # Clear existing data in the collection to avoid duplicates on re-runs
    print(f"Deleting existing documents from '{config.MONGO_COLLECTION_NAME}' collection...")
    collection.delete_many({})
    print("Existing documents cleared.")
    
    documents_to_upload = []
    for node in tqdm(nodes, desc="Preparing documents"):
        # The text to be embedded is crucial for good search results.
        # We combine the most important fields into a single string.
        semantic_text = node.get("semantic_text") or (node.get("description") or "")[:1000]
        if not semantic_text.strip():
            continue
        
        # We will store the original data along with the text prepared for embedding
        node['text_for_embedding'] = semantic_text
        documents_to_upload.append(node)
        
    print(f"\nPreparing to process and upsert {len(documents_to_upload)} documents to MongoDB...")

    # Process documents in batches
    for i in tqdm(range(0, len(documents_to_upload), BATCH_SIZE), desc="Embedding and Uploading Batches"):
        batch_docs = documents_to_upload[i:i + BATCH_SIZE]
        texts_to_embed = [doc['text_for_embedding'] for doc in batch_docs]
        
        embeddings = get_gemini_embeddings(texts_to_embed)
        
        # Add the generated embedding to each document
        for doc, embedding in zip(batch_docs, embeddings):
            if embedding: # Only add if embedding was successful
                doc['embedding'] = embedding
        
        # Insert the batch into MongoDB
        valid_docs = [doc for doc in batch_docs if 'embedding' in doc]
        if valid_docs:
            collection.insert_many(valid_docs)

    print("\nAll items and embeddings uploaded successfully to MongoDB Atlas.")
    print(f"Total documents in collection: {collection.count_documents({})}")

if __name__ == "__main__":
    main()