# visualize_from_mongodb.py
import config
from pymongo import MongoClient
from tqdm import tqdm
import json
import os

print("🚀 Initializing graph visualization...")

def build_graph_from_mongo(collection, output_html="mongo_graph_viz.html"):
    """Build interactive network graph from MongoDB data - NO PYVIS DEPENDENCY."""
    print("\n📊 Building interactive graph visualization...")
    
    # Fetch all nodes
    print("📥 Fetching nodes from MongoDB...")
    all_nodes = list(collection.find(
        {"is_cache": {"$ne": True}},
        {"id": 1, "name": 1, "type": 1, "connections": 1, "description": 1, "_id": 0}
    ))
    
    print(f"✓ Found {len(all_nodes)} nodes")
    
    if len(all_nodes) == 0:
        print("❌ No nodes found in MongoDB!")
        return
    
    # Prepare data for vis.js
    print("🔄 Preparing graph data...")
    
    # Define colors
    type_colors = {
        "City": "#FF6B35",
        "Landmark": "#004E89",
        "Food": "#F77F00",
        "Activity": "#06A77D",
        "Region": "#D62828",
        "Experience": "#9D4EDD",
        "Beach": "#00D9FF",
        "Mountain": "#8B4513",
        "Temple": "#FFD700"
    }
    
    # Build nodes for vis.js
    nodes_data = []
    node_count = 0
    for node in tqdm(all_nodes, desc="Processing nodes"):
        node_id = node.get("id", "unknown")
        node_name = node.get("name", "Unknown")
        node_type = node.get("type", "Unknown")
        node_desc = node.get("description", "")[:60]
        
        color = type_colors.get(node_type, "#A9A9A9")
        
        nodes_data.append({
            "id": node_id,
            "label": node_name,
            "title": f"{node_name}\nType: {node_type}\n{node_desc}",
            "color": color,
            "size": 25
        })
        node_count += 1
    
    print(f"✓ Prepared {node_count} nodes")
    
    # Build edges for vis.js
    print("🔗 Preparing connections...")
    edges_data = []
    edge_count = 0
    edges_set = set()  # Prevent duplicate edges
    
    for node in tqdm(all_nodes, desc="Processing edges"):
        source_id = node.get("id")
        connections = node.get("connections", [])
        
        for conn in connections:
            target_id = conn.get("target")
            
            if source_id and target_id:
                # Create edge key to avoid duplicates
                edge_key = tuple(sorted([source_id, target_id]))
                
                if edge_key not in edges_set:
                    edges_data.append({
                        "from": source_id,
                        "to": target_id,
                        "color": "#FF9500",
                        "width": 2
                    })
                    edges_set.add(edge_key)
                    edge_count += 1
    
    print(f"✓ Prepared {edge_count} connections")
    
    # Generate HTML with vis.js
    print("💾 Generating HTML...")
    
    # Convert Python lists to JSON FIRST
    nodes_json = json.dumps([
        {
            "id": n["id"],
            "label": n["label"],
            "title": n["title"],
            "color": n["color"],
            "size": n["size"]
        }
        for n in nodes_data
    ])
    
    edges_json = json.dumps(edges_data)
    
    # Now build HTML with proper JSON data
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vietnam Travel Knowledge Graph</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet" type="text/css" />
    <style type="text/css">
        * {{
            -webkit-user-select: none;
            -moz-user-select: none;
            -ms-user-select: none;
            -o-user-select: none;
            user-select: none;
        }}
        html, body {{
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        #mynetwork {{
            width: 100%;
            height: 100%;
            background-color: #0f0f0f;
            position: relative;
        }}
        .info {{
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(0, 0, 0, 0.92);
            color: #fff;
            padding: 20px;
            border-radius: 10px;
            max-width: 340px;
            font-size: 13px;
            z-index: 100;
            border: 2px solid #FF6B35;
            box-shadow: 0 8px 32px rgba(0,0,0,0.7);
            line-height: 1.6;
        }}
        .info h3 {{
            margin: 0 0 12px 0;
            color: #FF6B35;
            font-size: 18px;
            font-weight: 600;
        }}
        .info p {{
            margin: 8px 0;
        }}
        .stats {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #FF6B35;
            font-size: 12px;
            color: #aaa;
        }}
        .legend {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(0, 0, 0, 0.92);
            color: #fff;
            padding: 16px;
            border-radius: 10px;
            font-size: 12px;
            z-index: 100;
            border: 2px solid #FF6B35;
            box-shadow: 0 8px 32px rgba(0,0,0,0.7);
        }}
        .legend-title {{
            color: #FF6B35;
            font-weight: 600;
            margin-bottom: 10px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 10px;
            border: 1px solid rgba(255,255,255,0.3);
        }}
        .top-right {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.92);
            color: #fff;
            padding: 16px;
            border-radius: 10px;
            font-size: 12px;
            z-index: 100;
            border: 2px solid #FF6B35;
            box-shadow: 0 8px 32px rgba(0,0,0,0.7);
            max-width: 250px;
        }}
        .top-right h4 {{
            margin: 0 0 8px 0;
            color: #FF6B35;
            font-size: 14px;
        }}
        .top-right p {{
            margin: 4px 0;
            font-size: 11px;
            color: #aaa;
        }}
    </style>
</head>
<body>
    <div id="mynetwork"></div>
    
    <div class="info">
        <h3>🗺️ Vietnam Travel Graph</h3>
        <p>Interactive knowledge graph of Vietnamese destinations, landmarks, and travel experiences.</p>
        <p><strong>Explore:</strong> Drag • Scroll to zoom • Click nodes for info</p>
        <div class="stats">
            <p><strong>360 nodes</strong> | <strong>{edge_count} connections</strong></p>
        </div>
    </div>
    
    <div class="legend">
        <div class="legend-title">Legend</div>
        <div class="legend-item"><div class="legend-color" style="background-color: #FF6B35;"></div> City</div>
        <div class="legend-item"><div class="legend-color" style="background-color: #004E89;"></div> Landmark</div>
        <div class="legend-item"><div class="legend-color" style="background-color: #F77F00;"></div> Food</div>
        <div class="legend-item"><div class="legend-color" style="background-color: #06A77D;"></div> Activity</div>
        <div class="legend-item"><div class="legend-color" style="background-color: #D62828;"></div> Region</div>
    </div>
    
    <div class="top-right">
        <h4>Graph Controls</h4>
        <p><strong>Drag:</strong> Pan the graph</p>
        <p><strong>Scroll:</strong> Zoom in/out</p>
        <p><strong>Click:</strong> Node information</p>
        <p><strong>Double-click:</strong> Center view</p>
    </div>

    <script type="text/javascript">
        // Node data
        var nodesData = new vis.DataSet({nodes_json});
        
        // Edge data
        var edgesData = new vis.DataSet({edges_json});
        
        // Container
        var container = document.getElementById('mynetwork');
        
        // Data
        var data = {{
            nodes: nodesData,
            edges: edgesData
        }};
        
        // Options
        var options = {{
            physics: {{
                enabled: true,
                barnesHut: {{
                    gravitationalConstant: -26000,
                    centralGravity: 0.3,
                    springLength: 200,
                    springConstant: 0.04
                }},
                maxVelocity: 50
            }},
            nodes: {{
                font: {{
                    color: 'white',
                    size: 13
                }},
                scaling: {{
                    min: 10,
                    max: 30
                }},
                shadow: true
            }},
            edges: {{
                color: {{
                    inherit: false
                }},
                smooth: {{
                    type: 'continuous'
                }},
                shadow: false
            }},
            interaction: {{
                navigationButtons: true,
                keyboard: true
            }}
        }};
        
        // Initialize network
        var network = new vis.Network(container, data, options);
        
        // Fit to screen
        setTimeout(function() {{
            network.fit();
        }}, 100);
    </script>
</body>
</html>
"""
    
    # Write to file
    try:
        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        abs_path = os.path.abspath(output_html)
        print(f"\n✅ SUCCESS! Graph visualization created!")
        print(f"   📍 File: {abs_path}")
        print(f"   🌐 Open in browser: file://{abs_path}")
        print(f"   📊 Graph Stats:")
        print(f"      • Nodes: {node_count}")
        print(f"      • Connections: {edge_count}")
        print(f"\n💡 Command to open: open mongo_graph_viz.html")
        
    except Exception as e:
        print(f"❌ Error writing file: {e}")

def main():
    try:
        client = MongoClient(config.MONGO_URI)
        db = client[config.MONGO_DATABASE_NAME]
        collection = db[config.MONGO_COLLECTION_NAME]
        
        client.admin.command('ping')
        print("✓ MongoDB connection successful")
        
        count = collection.count_documents({"is_cache": {"$ne": True}})
        print(f"✓ Found {count} documents in collection")
        
        if count == 0:
            print("\n❌ No data found! Run: python load_to_mongodb.py")
            return
        
        build_graph_from_mongo(collection)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()