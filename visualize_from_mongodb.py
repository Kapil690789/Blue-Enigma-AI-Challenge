# visualize_from_mongodb.py
import config
from pymongo import MongoClient
from pyvis.network import Network
from tqdm import tqdm
import os

def build_graph_from_mongo(collection, output_html="mongo_graph_viz.html"):
    net = Network(height="900px", width="100%", notebook=False, directed=True, bgcolor="#222222", font_color="white")
    
    all_nodes = list(collection.find({}, {"id": 1, "name": 1, "type": 1, "connections": 1, "_id": 0}))
    
    for node in tqdm(all_nodes, desc="Adding nodes"):
        net.add_node(node.get("id"), label=node.get("name"), title=f"{node.get('name')}\nType: {node.get('type')}")
        
    for node in tqdm(all_nodes, desc="Adding connections"):
        for conn in node.get("connections", []):
            if node.get("id") and conn.get("target"):
                net.add_edge(node.get("id"), conn.get("target"), title=conn.get("relation"))
    
    # --- FIX: NEW, MORE RELIABLE SAVE METHOD ---
    try:
        html_content = net.generate_html()
        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Graph visualization saved to {os.path.abspath(output_html)}")
    except Exception as e:
        print(f"Error saving HTML file: {e}")

def main():
    try:
        client = MongoClient(config.MONGO_URI)
        db = client[config.MONGO_DATABASE_NAME]
        collection = db[config.MONGO_COLLECTION_NAME]
        client.admin.command('ping')
        print("MongoDB connection successful.")
        build_graph_from_mongo(collection)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()