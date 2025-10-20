AI Engineer Challenge: Improvements & Architectural Enhancements

Introduction

Upon reviewing the initial challenge, I recognized an opportunity to not only debug the existing semi-functional system but to re-architect it using a more modern, unified, and powerful technology stack. My goal was to build a robust, scalable, and highly performant multi-modal assistant that goes beyond the original requirements.

This document outlines the key improvements and strategic decisions made during the development process.

1. Architectural Overhaul: Unified Database with MongoDB Atlas

The original architecture proposed a multi-database setup using Pinecone for vector search and Neo4j for graph relationships. While functional, this approach introduces significant complexity in data synchronization, infrastructure management, and querying.

I made the strategic decision to consolidate both data types into a single, unified backend using MongoDB Atlas.

Key Benefits of this Approach:

Simplified Infrastructure: By leveraging MongoDB's native Atlas Vector Search, the need for a separate vector database like Pinecone is eliminated. This reduces the number of services to manage, configure, and maintain, drastically lowering operational overhead.

Unified Data Pipeline: Data loading is streamlined into a single script (load_to_mongodb.py) that handles both the raw document data and the generation and storage of vector embeddings. This eliminates the risk of data inconsistencies between two separate databases.

Simplified Querying: Both semantic (vector) search and relational lookups (simulating the graph context) are performed against a single database collection. This simplifies the application logic in the backend, making the code cleaner and easier to maintain.

This unified architecture is inherently more scalable and aligns with modern best practices for building complex AI applications.

2. Upgraded AI Core: Google Gemini & Advanced Embeddings

To enhance the AI's capabilities, I upgraded the entire language and embedding model suite from the proposed OpenAI models to Google's state-of-the-art Gemini models.

Core LLM: The application is powered by gemini-2.5-flash, a model known for its exceptional speed and multi-modal capabilities, ensuring fast and intelligent responses.

Embedding Model: For generating vector embeddings, I used models/text-embedding-004, Google's latest and most efficient text embedding model. This choice ensures high-quality semantic understanding, leading to more accurate search results.

Robust API Integration: During development, I diagnosed and resolved API instability by implementing a direct REST API integration using Python's requests library. To ensure reliability, I engineered a retry mechanism with timeouts for the vision model, making the application resilient to temporary network issues or slow API responses.

3. Advanced Features & Enhanced User Experience (Bonus Innovation)

I went beyond the core requirements to build a truly interactive and feature-rich application.

a. Multi-Modal Capability with Gemini Vision

The most significant enhancement is the addition of multi-modal input. The assistant is no longer limited to text. Using the power of Gemini, the app now features an image analysis tool:

Users can upload an image of a Vietnamese landmark, dish, or scene.

The application sends the image to the Gemini Vision API.

The assistant provides a detailed description of the image and then uses that information as context for subsequent text-based questions, creating a seamless multi-modal conversation.

b. Interactive Web UI with Streamlit

Instead of a basic command-line interface, I developed a full-fledged, user-friendly web application using Streamlit.

This provides a vastly superior user experience, making the tool intuitive and accessible.

It features a clean layout with a dedicated area for image analysis and a real-time chat interface.

This demonstrates the ability to build not just backend logic, but complete, user-facing AI products.

c. Contextual Conversation History

The assistant now maintains a conversation history. It remembers previous questions and answers, allowing for natural, multi-turn dialogues. This is crucial for a real-world assistant, as users can ask follow-up questions without having to repeat the context.