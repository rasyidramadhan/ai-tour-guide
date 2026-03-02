# Aizu 🤖 - Digital Tour Guide 🏖️⛰️

AI-powered travel guide application using **RAG (Retrieval-Augmented Generation)** technology.

## Overview

Aizu is a GenAI application that provides intelligent travel recommendations and tourism information using:
- **Mini-local LLM (Large Language Model)**: for generating responses
- **Embeddings**: Sentence Transformers for semantic search
- **Vector Database**: Qdrant for storing and retrieving documents
- **RAG Pipeline**: LangGraph for orchestrating the retrieval and generation workflow

## Project Structure

```
├── swagger.py              # FastAPI application entry point
├── config/
│   └── inference.yaml      # Configuration for models and services
├── src/
│   ├── engine.py           # LLM and embedding model initialization
│   ├── rag.py              # RAG pipeline implementation
│   ├── docs.py             # Document repository Qdrant integration
│   ├── crawl.py            # Crawling to google maps for destination/hotels
│   └── tour.txt            # System prompt for the tour guide
│   ├── agent.py            # Travel agent initialization
│   ├── hotel_service.py    # Hotel booking initialization
│   ├── tools.py            # Tools for status booking
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Features

✨ **Key Features:**
- **Intelligent Retrieval**: Semantic search across document database
- **Context-Aware Generation**: Uses retrieved context to generate accurate answers
- **RAG Pipeline**: Combines retrieval and generation for improved accuracy
- **RESTful API**: Fast and easy-to-use API endpoints
- **Configurable**: YAML-based configuration system
- **Logging**: Comprehensive logging for debugging and monitoring

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/rasyidramadhan/ai-tour-guide.git
```

### 2. Create Python Environment
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Setup Qdrant (Vector Database) and Docker
```bash
# Using Docker
docker run -p 6333:6333 -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant
```
Build & Run Semua Service
```bash
docker compose up --build -d
```
Check log:
```
docker compose logs -f aizu-app
```

### 5. Running Start the Application
```bash
uv run streamlit run streamlit.py
```

### API Endpoints

#### 1. Health Check
Response:
```json
{
  "collection_name": "tour-guides",
  "qdrant_url": "http://localhost:6333",
}
```

#### 2. Chat Endpoint (with Automatic Tool Calling)
```bash
POST /chat
Content-Type: application/json

{
  "question": "Tolong carikan hotel di Bali untuk liburan besok",
  "top_k": 3
}
```

Response (dengan automatic tool calling):
```json
{
  "question": "Tolong carikan hotel di Bali untuk liburan besok",
  "answer": "✅ Hotel ditemukan di Bali (5 malam):\n\n1. Grand Hotel Bali Resort, Bali\n2. Seaside Resort Bali, Bali\n3. ...",
}
```

#### Chat Endpoint Features

**LLM Agent dengan Automatic Tool Calling:**
- ✅ **Intent Detection**: Automatically detects the intent of user queries
- ✅ **Entity Extraction**: Extracts location, date, and budget from queries
- ✅ **Tool Calling**: Automatically calls the appropriate tools
- ✅ **Web Crawler Integration**: Runs a web crawler in the background
- ✅ **Fallback to RAG**: For general chats, use the RAG knowledge base

## Configuration

Edit `config/inference.yaml` to customize:

```yaml

# Vector Database
qdrant_url: "http://localhost:6333"
collection_name: "tour-guides"

# RAG Settings
rag_config:
  top_k: 3              # Documents to retrieve
  min_similarity: 0.3   # Minimum similarity threshold
```

## Architecture

### RAG Pipeline Flow

```
User Query
    ↓
Embed Query (Embedding Model)
    ↓
Retrieve Documents (Vector Database)
    ↓
Format Context
    ↓
Generate Answer (LLM)
    ↓
Return Response
```

### Component Descriptions

| Component | Purpose |
|-----------|---------|
| `swagger.py` | FastAPI application with REST endpoints |
| `engine.py` | LLM and Embedding model initialization |
| `rag.py` | RAG pipeline orchestration using LangGraph |
| `docs.py` | Vector database integration with Qdrant |
| `tour.txt` | System prompt for consistent guide behavior |
| `agent.py` | LLM Agent dengan automatic tool calling |
| `tools.py` | Hotel booking tools & time service |
| `hotel_service.py` | Hotel search & booking management |
| `streamlit.py` | UI application |

## LLM Agent with Automatic Tool Calling

### Overview

LLMAgent is an intelligent system that can:
1. **Understand User Intent**: Detect what the user wants from the query
2. **Extract Entities**: Retrieve important information (location, date, budget)
3. **Call Tools Automatically**: Run appropriate tools without requiring user specification
4. **Format Results**: Display results in a user-friendly format

### Flow Diagram

```
User Query: "Tolong carikan hotel di Bali untuk liburan besok"
        ↓
LLMAgent.detect_intent()
        ↓
Intent: "search_hotels"
Entities: {"location": "Bali", "dates": "besok (5 hari)"}
        ↓
LLMAgent.call_tool("search_hotels", entities)
        ↓
HotelBookingTools.search_hotels()
        ↓
WebCrawler.search_holiday_destinations()
        ↓
Format dan Display Results:
"✅ Hotel ditemukan di Bali (5 malam):
 1. Grand Hotel Bali, Bali
 2. Seaside Resort, Bali
 ..."
```

### Supported Intents

| Intent | Keywords | Tool | Output |
|--------|----------|------|--------|
| search_hotels | hotels, accommodations, bookings | `search_hotels()` | List of hotels in a location |
| search_destinations | destinations, vacations, tourist attractions | `search_destinations()` | List of various destinations |
| get_recommendations | recommendations, suggestions, best | `get_recommendations()` | Recommendations with budget |
| check_time | hour, time, now | `get_current_time()` | Current time |
| chat | (anything else) | RAG Knowledge Base | General answer |

### Implementation Files
- `src/llm_agent.py`: Main LLMAgent class with intent detection & calling tools
- `src/tools.py`: HotelBookingTools & TimeService to execute operations
- `test_llm_agent.py`: Test suite with various scenarios


## System Prompt

The system prompt (`src/holiday.txt`) defines the behavior and personality of Aizu. You can customize this to change the guide's personality and expertise.

## Performance Tips

1. **Increase top_k**: For more thorough document retrieval
2. **Adjust temperature**: Lower = more deterministic, Higher = more creative
3. **Use faster embeddings**: Smaller models if speed is critical
4. **Batch queries**: Process multiple queries together
5. **Cache embeddings**: Store frequently used embeddings

## Hotel Service - Holiday Booking Integration

### Overview

HotelService is an integrated module that allows users to search for holiday destinations based on their calendar and make hotel reservations. This module uses `WebCrawler` from `app/crawl.py` to search for destination information in various provinces in Indonesia.

### Features

✨ **Hotel Service Features:**
- **Calendar Check**: Validate user vacation dates in real-time
- **Destination Search**: Search for vacation destinations in 15+ provinces in Indonesia
- **Hotel Search**: Search for hotels by location and date
- **Smart Recommendations**: Destination recommendations based on budget and preferences
- **Booking Management**: Execute bookings with payment info validation
- **Confirmation**: Generate a unique booking confirmation number


### Destination Types

Destination recommendations can be filtered by type:
- **pantai**: Sea and beach
- **gunung**: Mountains and nature
- **budaya**: Culture
- **all**: All type destination

### Implementation Details

Workflow:

1. User provides vacation dates via a prompt
2. HotelService validates the user's calendar
3. WebCrawler searches for destinations in various provinces
4. Results are returned with hotel information and prices
5. User can make a booking with secure payment information

## Hotel Booking Tools - LLM Integration

### Overview

This system tool allows LLM to automatically access hotel booking features through the API. LLM can call these tools to provide more accurate and personalized vacation recommendations to users.

### Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| **search_destinations** | Search for holiday destinations by date | `start_date`, `end_date`, `destination_type` |
| **search_hotels** | Search for hotels in a location for a specific date | `location`, `start_date`, `end_date` |
| **get_recommendations** | Get destination recommendations based on your budget | `budget`, `destination_type` |
| **execute_booking** | Make a hotel booking (simulate) | `location`, `hotel_name`, `room_type`, `start_date`, `end_date`, `total_price` |
| **cancel_booking** | Cancel a confirmed booking | `booking_reference` |
### Tool Endpoints

#### 1. List Available Tools
```bash
GET /tools/list
```

Response:
```json
{
  "status": "success",
  "total_tools": 5,
  "tools": {
    "search_destinations": {
      "description": "Cari destinasi liburan berdasarkan tanggal dan tipe...",
      "parameters": {...}
    },
    ...
  }
}
```

#### 2. Execute Tool
```bash
POST /tools/execute
Content-Type: application/json

{
  "tool_name": "search_destinations",
  "parameters": {
    "start_date": "2026-03-10",
    "end_date": "2026-03-15",
    "destination_type": "pantai"
  }
}
```

Response:
```json
{
  "status": "success",
  "tool_name": "search_destinations",
  "result": {
    "success": true,
    "message": "Menemukan 4 destinasi untuk pantai",
    "destinations": [
      "Pantai Senggigi, Lombok",
      "Pantai Kuta Bali, Bali",
      ...
    ],
    "total_found": 4
  }
}
```

## Future Enhancements

- Multi-language support
- Document management dashboard
- Analytics and monitoring
- Model quantization for faster inference
- Caching layer for frequently asked questions
- User feedback mechanism
- **Integration dengan Google Calendar untuk auto-sync liburan**
- **Real-time price comparison dari berbagai OTA**
- **Currency conversion support**
- **Travel insurance packages**
- **Advanced tool chaining untuk complex booking scenarios**
- **Multi-agent collaboration untuk better recommendations**


## Support

For issues or questions, please open an issue on the repository.

---

**Built with ❤️ using FastAPI, LangChain, and Qdrant**
##### **Created by: Rasyid Ramadhan - 2026**
Technical LLM
