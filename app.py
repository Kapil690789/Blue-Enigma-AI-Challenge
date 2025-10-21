# app.py
import streamlit as st
from pymongo import MongoClient
import google.generativeai as genai
import config
import utils

st.set_page_config(
    page_title="Vietnam Travel Assistant",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for better visuals ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #FF6B35;
        font-size: 2.5em;
        font-weight: bold;
        margin-bottom: 0.5em;
    }
    .cache-badge {
        background-color: #4CAF50;
        color: white;
        padding: 0.3em 0.8em;
        border-radius: 0.3em;
        font-size: 0.8em;
        font-weight: bold;
    }
    .info-box {
        background-color: #E3F2FD;
        padding: 1em;
        border-radius: 0.5em;
        border-left: 4px solid #1976D2;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">✈️ Multi-Modal Vietnam Travel Assistant</div>', unsafe_allow_html=True)
st.caption("🚀 Powered by Gemini 2.5 Flash, MongoDB Atlas, and Intelligent Query Caching")

# --- Initialize Clients ---
@st.cache_resource
def init_clients():
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        client = MongoClient(config.MONGO_URI)
        db = client[config.MONGO_DATABASE_NAME]
        collection = db[config.MONGO_COLLECTION_NAME]
        client.admin.command('ping')
        print("✓ MongoDB connection successful")
        return collection
    except Exception as e:
        st.error(f"❌ Error initializing clients: {e}")
        return None

collection = init_clients()

if collection is None:
    st.error("❌ Database connection failed. The app cannot continue.")
    st.stop()

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processed_image_id" not in st.session_state:
    st.session_state.processed_image_id = None
if "cache_stats" not in st.session_state:
    st.session_state.cache_stats = {"hits": 0, "misses": 0}

# --- Sidebar: Image Upload & Info ---
with st.sidebar:
    st.header("📸 Image Analysis")
    st.write("Upload a picture of a Vietnamese landmark, dish, or scene!")
    
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None and uploaded_file.file_id != st.session_state.processed_image_id:
        with st.spinner("🔍 Analyzing image..."):
            image_bytes = uploaded_file.getvalue()
            image_description = utils.describe_image(image_bytes)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.image(image_bytes, use_column_width=True)
            with col2:
                st.info(f"📄 {uploaded_file.name}")
            
            st.session_state.messages.append({
                "role": "user",
                "content": f"[Image Uploaded: {uploaded_file.name}]"
            })
            st.session_state.messages.append({
                "role": "assistant",
                "content": image_description
            })
            st.session_state.processed_image_id = uploaded_file.file_id
            st.rerun()
    
    # --- Cache Statistics ---
    st.divider()
    st.subheader("📊 Cache Performance")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Cache Hits", st.session_state.cache_stats["hits"])
    with col2:
        st.metric("Cache Misses", st.session_state.cache_stats["misses"])
    
    if st.session_state.cache_stats["hits"] + st.session_state.cache_stats["misses"] > 0:
        hit_rate = st.session_state.cache_stats["hits"] / (
            st.session_state.cache_stats["hits"] + st.session_state.cache_stats["misses"]
        ) * 100
        st.progress(hit_rate / 100, text=f"Hit Rate: {hit_rate:.1f}%")
    
    # --- Info Section ---
    st.divider()
    st.subheader("ℹ️ About This App")
    st.markdown("""
    **Features:**
    - 🌐 Multi-modal: Text + Image input
    - 🔍 Semantic search with MongoDB Atlas
    - 💾 Intelligent query caching
    - 🧠 Context-aware conversations
    - 📊 Real-time cache analytics
    """)

# --- Main Chat Interface ---
st.header("💬 Chat with Your Assistant")

# Display conversation history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask me about travel in Vietnam..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("⏳ Thinking..."):
            # Get query embedding
            query_embedding = utils.get_embedding(prompt)
            
            if not query_embedding:
                st.error("❌ Could not process query.")
                st.stop()
            
            # Check cache for similar response
            cached_entry = utils.find_cached_similar_response(query_embedding, collection)
            
            if cached_entry:
                response = cached_entry["response"]
                st.session_state.cache_stats["hits"] += 1
                with st.info("✨ Response from smart cache (similar query found)", icon="📦"):
                    st.markdown(response)
            else:
                # Cache miss: perform full RAG
                st.session_state.cache_stats["misses"] += 1
                
                vector_matches = utils.mongodb_vector_search(query_embedding, collection)
                relational_context = utils.fetch_relational_context(vector_matches, collection)
                prompt_for_llm = utils.build_prompt(
                    prompt,
                    vector_matches,
                    relational_context,
                    st.session_state.messages[:-1]  # Exclude current message
                )
                
                response = utils.call_gemini_rest(prompt_for_llm)
                
                # Cache the response
                utils.cache_response(prompt, query_embedding, response, collection)
                
                st.markdown(response)
            
            st.session_state.messages.append({"role": "assistant", "content": response})

# --- Footer ---
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("🧠 Powered by Gemini 2.5 Flash")
with col2:
    st.caption("📦 Data: MongoDB Atlas")
with col3:
    st.caption("⚡ Messages: " + str(len(st.session_state.messages)))