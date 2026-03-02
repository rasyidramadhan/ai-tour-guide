import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from src.loader import load_config
from src.rag import RAG
from src.engine import initialize_models
from src.docs import DocumentRepository
from src.hotel_service import HotelService
from src.tools import HotelBookingTools, TimeService, get_hotel_tools
from src.agent import create_agent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

service_state = {}

class ChatRequest(BaseModel):
    question: str
    top_k: int = 3

class ChatResponse(BaseModel):
    question: str
    answer: str
    time_taken: float

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing GenAI services...")
    config = load_config()
    
    try:
        logger.info("Loading models...")
        llm, embedder = initialize_models(config["llm_model"])
        service_state['llm'] = llm
        service_state['embedder'] = embedder
        service_state['config'] = config
        
        logger.info("Connecting to Qdrant vector database...")
        repo = DocumentRepository(
            server=config["qdrant_url"],
            collection_name=config["collection_name"],
            embedding_model_name=config["embedding_model"]
        )
        service_state['repo'] = repo
        rag_service = RAG(repo=repo, embedder=embedder, llm=llm)
        service_state['rag'] = rag_service
        
        logger.info("Initializing Hotel Service...")
        default_payment_info = {
            "card_number": "****-****-****-1234",
            "cvv": "***",
            "expiry_date": "12/25",
            "method": "Debit Card"
        }
        hotel_service = HotelService(user_payment_info=default_payment_info)
        service_state['hotel_service'] = hotel_service
        
        logger.info("Initializing Hotel Booking Tools...")
        hotel_tools = HotelBookingTools(hotel_service)
        time_service = TimeService()
        service_state['hotel_tools'] = hotel_tools
        service_state['time_service'] = time_service
        service_state['tools_dict'] = get_hotel_tools(hotel_service)
        
        logger.info("Initializing LLM Agent with tool calling...")
        agent = create_agent(llm, embedder, hotel_service)
        service_state['agent'] = agent
        
        logger.info("✅ Hotel Booking Tools initialized successfully")
        logger.info("✅ LLM Agent with tool calling initialized successfully")
        
        if repo.connected:
            logger.info("✅ GenAI services initialized successfully with Qdrant")
        else:
            logger.warning("⚠️ GenAI services initialized without Qdrant (limited functionality)")
            logger.warning("To enable full RAG features, start Qdrant: docker run -p 6333:6333 qdrant/qdrant")
        
        logger.info("✅ Hotel Service initialized successfully")
    
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise
    
    yield
    
    logger.info("Shutting down services...")
    if service_state.get('hotel_service'):
        service_state['hotel_service'].close_crawler()
    service_state.clear()
    logger.info("Services cleaned up")

app = FastAPI(
    title="Aizu 🤖 - Digital Tour Guide 🏖️⛰️",
    description="AI-powered travel guide using RAG (Retrieval-Augmented Generation)",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not service_state.get('agent'):
        raise HTTPException(status_code=400, detail="Agent service not initialized")
    
    try:
        agent = service_state['agent']
        
        logger.info(f"Processing question: {request.question}")
        agent_result = agent.process_with_tools(request.question)
        logger.info(f"Agent result: {agent_result}")
        
        if agent_result.get("tool_called"):
            result_chat = ChatResponse(
                question=request.question,
                answer=agent_result["answer"],
                time_taken=0.0
            )
            logger.info(f"✅ Tool called: {agent_result.get('tool_name')} | Intent: {agent_result.get('intent')}")
        else:
            if service_state.get('rag'):
                rag_response = service_state['rag'].process(request.question, top_k=request.top_k)
                result_chat = ChatResponse(
                    question=request.question,
                    answer=rag_response["answer"],
                    time_taken=rag_response["time execution"]
                )
            else:
                result_chat = ChatResponse(
                    question=request.question,
                    answer=agent_result["answer"],
                )
        
        return result_chat

    except Exception as e:
        logger.error(f"❌ Error processing chat: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.get("/")
async def root():
    return {
        "message": "Welcome to Aizu 🤖 - Digital Tour Guide 🏖️⛰️",
        "docs": "/docs",
        "endpoints": {
            "chat": "/chat (POST) - Chat dengan AI tour guide (automatic tool calling)",
            "status_booking": "/Status_Booking (GET) - Lihat detail pemesanan"
        }
    }

@app.get("/Status_Booking")
async def get_booking_status():
    if not service_state.get('hotel_service'):
        raise HTTPException(status_code=400, detail="Hotel service not initialized")
    
    try:
        hotel_service = service_state['hotel_service']
        
        if not hotel_service.last_booking:
            return {
                "status": "no_booking",
                "message": "Tidak ada pemesanan. Silakan pesan hotel terlebih dahulu.",
                "booking_details": None
            }
        
        booking = hotel_service.last_booking
        
        return {
            "status": "success",
            "message": "Detail pemesanan Anda",
            "booking_details": {
                "confirmation_number": booking.get("confirmation_number"),
                "booking_status": booking.get("message"),
                "location": booking.get("booking_details", {}).get("location"),
                "hotel_name": booking.get("booking_details", {}).get("hotel_name"),
                "room_type": booking.get("booking_details", {}).get("room_type"),
                "check_in": booking.get("booking_details", {}).get("check_in"),
                "check_out": booking.get("booking_details", {}).get("check_out"),
                "total_price": booking.get("booking_details", {}).get("total_price"),
                "currency": booking.get("booking_details", {}).get("currency"),
                "payment_method": booking.get("payment_info", {}).get("method"),
                "payment_status": booking.get("payment_info", {}).get("status"),
                "booking_time": booking.get("payment_info", {}).get("timestamp")
            },
            "booking_history": [
                {
                    "confirmation_number": b.get("confirmation_number"),
                    "location": b.get("booking_details", {}).get("location"),
                    "check_in": b.get("booking_details", {}).get("check_in"),
                    "total_price": b.get("booking_details", {}).get("total_price")
                }
                for b in hotel_service.booking_history
            ]
        }
    
    except Exception as e:
        logger.error(f"Error getting booking status: {e}")
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
