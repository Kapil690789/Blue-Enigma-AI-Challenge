# load_to_mongodb.py
import json
import config
from tqdm import tqdm
from pymongo import MongoClient
import google.generativeai as genai
import time

# --- Configuration ---
DATA_FILE = "vietnam_travel_dataset.json"
EMBEDDING_MODEL = 'models/text-embedding-004'
BATCH_SIZE = 50
MAX_RETRIES = 3
RETRY_DELAY = 2

# --- Initialize Clients ---
print("🚀 Initializing clients...")
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

def get_gemini_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings with retry logic."""
    if not texts:
        return []
    
    for attempt in range(MAX_RETRIES):
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=texts,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"⚠️ Embedding attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"   Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"❌ Failed to embed batch after {MAX_RETRIES} attempts")
                return [[] for _ in texts]

def main():
    """Main function to process and upload data."""
    print("\n📂 Loading data from JSON file...")
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            nodes = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {DATA_FILE} not found!")
        exit(1)
    except json.JSONDecodeError:
        print(f"❌ Error: {DATA_FILE} is not valid JSON!")
        exit(1)
    
    print(f"✓ Loaded {len(nodes)} nodes from dataset")
    
    # Clear existing data
    print(f"\n🗑️ Clearing existing documents from collection...")
    result = collection.delete_many({})
    print(f"✓ Deleted {result.deleted_count} documents")
    
    # Prepare documents
    print(f"\n📝 Preparing documents for embedding...")
    documents_to_upload = []
    
    for node in tqdm(nodes, desc="Processing nodes"):
        # Skip nodes without proper data
        if not node.get("id") or not node.get("name"):
            continue
        
        # Create semantic text for embedding
        semantic_text = node.get("semantic_text") or node.get("description", "")
        
        if not semantic_text.strip():
            continue
        
        node['text_for_embedding'] = semantic_text
        documents_to_upload.append(node)
    
    print(f"\n✓ Prepared {len(documents_to_upload)} documents for embedding")
    
    if not documents_to_upload:
        print("❌ No documents to upload!")
        exit(1)
    
    # Process in batches
    print(f"\n🔄 Embedding and uploading in batches of {BATCH_SIZE}...")
    total_embedded = 0
    failed_docs = []
    
    for i in tqdm(range(0, len(documents_to_upload), BATCH_SIZE), desc="Processing Batches"):
        batch_docs = documents_to_upload[i:i + BATCH_SIZE]
        texts_to_embed = [doc['text_for_embedding'] for doc in batch_docs]
        
        # Get embeddings for batch
        embeddings = get_gemini_embeddings(texts_to_embed)
        
        # Match embeddings with documents
        docs_with_embeddings = []
        for doc, embedding in zip(batch_docs, embeddings):
            if embedding:  # Only add if embedding was successful
                doc['embedding'] = embedding
                docs_with_embeddings.append(doc)
            else:
                failed_docs.append(doc.get('name', 'Unknown'))
        
        # Insert batch into MongoDB
        if docs_with_embeddings:
            try:
                collection.insert_many(docs_with_embeddings)
                total_embedded += len(docs_with_embeddings)
            except Exception as e:
                print(f"\n⚠️ Error inserting batch: {e}")
    
    # Summary
    print(f"\n{'='*50}")
    print(f"✓ Embedding and upload complete!")
    print(f"  - Total documents embedded: {total_embedded}")
    print(f"  - Failed documents: {len(failed_docs)}")
    
    if failed_docs:
        print(f"  - Failed: {', '.join(failed_docs[:5])}")
        if len(failed_docs) > 5:
            print(f"    ... and {len(failed_docs) - 5} more")
    
    total_in_collection = collection.count_documents({})
    print(f"  - Total documents in collection: {total_in_collection}")
    
    # Create vector search index if not exists
    print(f"\n📑 Setting up vector search index...")
    try:
        collection.create_search_index(
            model={
                "definition": {
                    "mappings": {
                        "dynamic": True,
                        "fields": {
                            "embedding": {
                                "type": "vector",
                                "dimensions": 768,
                                "similarity": "cosine"
                            }
                        }
                    }
                },
                "name": config.MONGO_VECTOR_INDEX_NAME
            }
        )
        print(f"✓ Vector search index created/verified")
    except Exception as e:
        if "already exists" in str(e):
            print(f"✓ Vector search index already exists")
        else:
            print(f"⚠️ Note on vector index: {e}")
    
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
    print("🎉 Data loading pipeline completed successfully!")