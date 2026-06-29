# RAG Chatbot

A production-ready RAG (Retrieval-Augmented Generation) chatbot built with **LangGraph**, **MongoDB Atlas**, hybrid retrieval, and Cohere reranking.

## Architecture

```
User Query
    │
    ▼
┌─────────────────┐
│  FastAPI Server  │
└────────┬────────┘
         │
    ┌────▼────┐
    │ LangGraph│
    │  Agent   │
    └────┬────┘
         │
    ┌────▼────────────┐
    │  Router Node     │ ← Decides: RAG or General Chat?
    └────┬────────────┘
         │
    ┌────┴──────────────┐
    │                   │
    ▼                   ▼
 RAG Search       General Chat
 (Hybrid Retrieval)  (Plain LLM)
    │
    ├── Dense Search (MongoDB Atlas Vector Search)
    ├── Full-Text Search (MongoDB Native Text Index)
    ├── RRF Fusion
    └── Cohere Reranking
```

## Setup

### 1. Prerequisites

- Python 3.12+
- MongoDB Atlas cluster (with a configured Vector Search index named `vector_index` on the `document_chunks` collection)
- API keys: Google AI, Cohere, (optional) Groq

### 2. Install Dependencies

```bash
pip install -r requirements.txt
# or using uv
uv sync
```

### 3. Configure Environment

Edit `.env` with your actual keys, MongoDB URI (`MONGO_URL`), and database name (`DB_NAME`).

### 4. Start the Server

```bash
python main.py
# or
uvicorn main:app --reload
```

### 5. Access API Docs

Open `http://localhost:8000/docs` for the Swagger UI.

## API Endpoints

| Method   | Endpoint                       | Description                     |
| -------- | ------------------------------ | ------------------------------- |
| `POST` | `/api/users`                 | Create a new user               |
| `POST` | `/api/threads`               | Create a conversation thread    |
| `GET`  | `/api/threads/{id}/messages` | Get thread messages             |
| `POST` | `/api/chat`                  | Send a message, get AI response |
| `POST` | `/api/documents/upload`      | Upload a document for ingestion |
| `GET`  | `/api/documents/{id}`        | Check document status           |

## Key Design Decisions

- **Hybrid retrieval** (dense + full-text) instead of pure vector search
- **RRF fusion** instead of naive score concatenation
- **Reranking before generation** for maximum accuracy
- **Chunk-level indexing** instead of document-level
- **Versioned embeddings** for safe re-embedding in the future
- **Rolling summary + recent messages** for conversation memory
- **LangGraph** for easy tool extensibility in future parts


uv run python main.py

npm run dev
