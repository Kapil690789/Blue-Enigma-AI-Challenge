import streamlit as st
from pymongo import MongoClient
import google.generativeai as genai
import config
import utils

st.set_page_config(page_title="Vietnam Travel Assistant", page_icon="✈️", layout="wide")

st.title("✈️ Multi-Modal Vietnam Travel Assistant")
st.caption("Powered by Gemini and MongoDB Atlas.")

@st.cache_resource
def init_clients():
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        client = MongoClient(config.MONGO_URI)
        db = client[config.MONGO_DATABASE_NAME]
        collection = db[config.MONGO_COLLECTION_NAME]
        client.admin.command('ping')
        return collection
    except Exception as e:
        st.error(f"Error initializing clients: {e}")
        return None

collection = init_clients()

if collection is None:
    st.error("Database connection failed. The app cannot continue.")
    st.stop()

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processed_image_id" not in st.session_state:
    st.session_state.processed_image_id = None

# --- UI Components ---
with st.sidebar:
    st.header("Image Analysis")
    st.write("Have a picture of a landmark or food? Upload it here!")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    
    # --- LOOP FIX: Only process a new, unprocessed image ---
    if uploaded_file is not None and uploaded_file.file_id != st.session_state.processed_image_id:
        with st.spinner("Analyzing image..."):
            image_bytes = uploaded_file.getvalue()
            image_description = utils.describe_image(image_bytes)
            
            st.image(image_bytes, caption="Analyzed Image", width='stretch') # WARNING FIX
            
            # Update session state and flag the image as processed
            st.session_state.messages.append({"role": "user", "content": f"I uploaded an image ({uploaded_file.name})."})
            st.session_state.messages.append({"role": "assistant", "content": image_description})
            st.session_state.processed_image_id = uploaded_file.file_id
            st.rerun()

st.header("Chat with your Assistant")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me about travel in Vietnam..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            query_embedding = utils.get_embedding(prompt)
            if not query_embedding:
                st.error("Could not process query.")
            else:
                vector_matches = utils.mongodb_vector_search(query_embedding, collection)
                relational_context = utils.fetch_relational_context(vector_matches, collection)
                prompt_for_llm = utils.build_prompt(prompt, vector_matches, relational_context, st.session_state.messages)
                response = utils.call_gemini_rest(prompt_for_llm)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})