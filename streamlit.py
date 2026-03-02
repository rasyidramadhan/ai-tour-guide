import streamlit as st
import time
import base64
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from src.loader import load_config
from src.engine import initialize_models
from src.hotel_service import HotelService
from src.agent import create_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def set_background(image):
    with open(image, "rb") as f:
        data = f.read()

    encoded = base64.b64encode(data).decode()
    page_bg = f"""
    <style>
    .stApp {{
        background-image: url("data:image/jpg;base64,{encoded}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    </style>
    """
    st.markdown(page_bg, unsafe_allow_html=True)
set_background("assets/bg.jpg")

st.set_page_config(page_title="Aizu 🤖 - AI Tour Guide", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "last_response_time" not in st.session_state:
    st.session_state.last_response_time = None
if "booking_intent" not in st.session_state:
    st.session_state.booking_intent = False
if "booking_status" not in st.session_state:
    st.session_state.booking_status = None
if "last_booking_details" not in st.session_state:
    st.session_state.last_booking_details = None
if "last_intent" not in st.session_state:
    st.session_state.last_intent = None
if "payment_info" not in st.session_state:
    st.session_state.payment_info = {
        "card_number": "1234567890",
        "method": "credit_card"
    }

@st.cache_resource
def initialize_services():
    logger.info("Initializing services...")
    config = load_config()
    llm, embedder = initialize_models(config["llm_model"])
    
    payment_info = st.session_state.get("payment_info", {
        "card_number": "1234567890",
        "method": "credit_card"
    })
    
    hotel_service = HotelService(user_payment_info=payment_info)
    agent = create_agent(llm, embedder, hotel_service)
    return agent

def detect_booking_intent(intent: str, query: str) -> bool:
    booking_keywords = ["pesan", "booking", "pesan hotel", "booking sekarang", "konfirmasi"]
    booking_intents = ["execute_booking", "search_hotels", "search_destinations", "get_recommendations"]
    
    query_lower = query.lower()
    has_booking_keyword = any(kw in query_lower for kw in booking_keywords)
    has_booking_intent = intent in booking_intents
    
    return has_booking_keyword or has_booking_intent

try:
    st.session_state.agent = initialize_services()
except Exception as e:
    logger.error(f"Error initializing services: {e}")
    st.error(f"Error initializing services: {e}")

with st.sidebar:
    st.header("⚙️ Settings")
    
    with st.expander("💳 Informasi Pembayaran", expanded=True):
        st.info("ℹ️ Isi data pembayaran untuk proses booking. Gunakan kartu test untuk demo.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.payment_info["card_number"] = st.text_input(
                "Nomor Kartu:",
                value=st.session_state.payment_info.get("card_number", "1234567890"),
                placeholder="1234567890"
            )
        
        with col2:
            st.session_state.payment_info["method"] = st.selectbox(
                "Metode Pembayaran:",
                ["credit_card", "debit_card", "bank_transfer"],
                index=0
            )
        
        st.success("✅ Data pembayaran siap digunakan")
    
    st.divider()
    st.write("**📌 Test Card untuk Demo:**")
    st.warning("💡 Gunakan data di bawah untuk testing:")
    st.code("Nomor: 1234567890\nMetode: credit_card")

col1, col2 = st.columns([3, 1])
with col1:
    st.title("Aizu 🤖 - AI Tour Guide 🏖️⛰️")
    st.markdown("Asisten Perjalanan & Booking Hotel Anda di Indonesia 🇮🇩")

with col2:
    time_placeholder = st.empty()
    
    def update_time():
        tz = ZoneInfo("Asia/Jakarta")
        current_time = datetime.now(tz).strftime("%d/%m/%Y")
        return current_time
    
    time_placeholder.metric("Tanggal", update_time())

st.divider()

chat_container = st.container(border=True)
with chat_container:
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.write(message["content"])

st.divider()

col1, col2, col3, col4 = st.columns([4, 0.8, 0.8, 0.8])

with col1:
    user_input = st.text_input(
        "💬 Tanyakan sesuatu...",
        placeholder="Contoh: Pesan hotel di Yogyakarta untuk minggu depan",
        label_visibility="collapsed",
        key="user_input"
    )

with col2:
    send_button = st.button("📤 Kirim", use_container_width=True, key="send_button")

with col3:
    if st.session_state.booking_intent and st.session_state.booking_status is None:
        confirm_button = st.button("✅Konfirmasi", use_container_width=True, key="confirm_btn")
    else:
        confirm_button = False
        st.button("✅Konfirmasi", use_container_width=True, key="confirm_btn", disabled=True)

with col4:
    if st.session_state.booking_intent and st.session_state.booking_status is None:
        cancel_button = st.button("❌Batalkan", use_container_width=True, key="cancel_btn")
    else:
        cancel_button = False
        st.button("❌Batalkan", use_container_width=True, key="cancel_btn", disabled=True)

if confirm_button:
    if st.session_state.agent and st.session_state.agent.hotel_service:
        st.session_state.agent.hotel_service.update_payment_info(st.session_state.payment_info)
        logger.info("✅ Payment info updated di HotelService")
    
    st.session_state.booking_status = "confirmed"
    confirmation_msg = "✅ Pesanan Anda telah dikonfirmasi! Terima kasih telah menggunakan layanan Aizu."
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"✅ **PESANAN DIKONFIRMASI**\n\n{confirmation_msg}"
    })
    st.session_state.booking_intent = False
    st.rerun()

if cancel_button:
    st.session_state.booking_status = "cancelled"
    cancellation_msg = "❌ Pesanan Anda telah dibatalkan. Silakan hubungi kami jika ada pertanyaan."
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"📋 **PESANAN DIBATALKAN**\n\n{cancellation_msg}"
    })
    st.session_state.booking_intent = False
    st.rerun()

if send_button and user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.processing = True
    st.session_state.booking_status = None
    st.rerun()

if st.session_state.processing and st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.spinner(""):
        processing_placeholder = st.empty()
        processing_placeholder.info("⏳ Aizu sedang menjawab pertanyaan Anda...")
        
        user_query = st.session_state.messages[-1]["content"]
        start_time = time.time()
        
        try:
            if st.session_state.agent:
                result = st.session_state.agent.process_with_tools(user_query)
                end_time = time.time()
                response_time = end_time - start_time
                st.session_state.last_response_time = response_time
                
                answer = result.get("answer", "Maaf, terjadi kesalahan dalam memproses pertanyaan Anda.")
                intent = result.get("intent", "chat")
                
                has_booking_intent = detect_booking_intent(intent, user_query)
                st.session_state.booking_intent = has_booking_intent
                st.session_state.last_intent = intent
                st.session_state.last_booking_details = result
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })
            else:
                st.error("❌ Services belum terinisialisasi")
        
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            st.error(f"Terjadi kesalahan: {str(e)}")
        
        finally:
            st.session_state.processing = False
            processing_placeholder.empty()
            st.rerun()

st.divider()

if st.session_state.booking_intent or st.session_state.booking_status:
    status_container = st.container(border=True)
    with status_container:
        st.subheader("📋 Status Pemesanan")
        
        if st.session_state.booking_status == "confirmed":
            st.write("Pesanan Anda kami proses ✅.")
            booking_details = st.session_state.last_booking_details or {}
            if booking_details.get("entities"):
                entities = booking_details["entities"]
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📍 **Lokasi:** {entities.get('location', 'N/A')}")
                    st.write(f"🏨 **Hotel:** {entities.get('hotel_name', 'N/A')}")
                with col2:
                    st.write(f"💬 **Intent:** {st.session_state.last_intent}")
                    if st.session_state.last_response_time is not None:
                        st.write(f"⏱️ **Waktu Respon:** {st.session_state.last_response_time:.2f}s")
                    else:
                        st.write(f"⏱️ **Waktu Respon:** N/A")
        
        elif st.session_state.booking_status == "cancelled":
            st.write("Pesanan Anda telah dibatalkan ❌.")
        
        else:
            st.warning("⏳ **MENUNGGU KONFIRMASI**")
            st.write("Silakan tinjau detail pesanan Anda dan klik tombol 'Konfirmasi' untuk melanjutkan.")
            booking_details = st.session_state.last_booking_details or {}
            if booking_details.get("entities"):
                entities = booking_details["entities"]
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📍 **Lokasi:** {entities.get('location', 'N/A')}")
                    st.write(f"🏨 **Hotel:** {entities.get('hotel_name', 'N/A')}")
                with col2:
                    st.write(f"💬 **Intent:** {st.session_state.last_intent}")
                    if st.session_state.last_response_time is not None:
                        st.write(f"⏱️ **Waktu Respon:** {st.session_state.last_response_time:.2f}s")
                    else:
                        st.write(f"⏱️ **Waktu Respon:** N/A")

if st.session_state.last_response_time is not None:
    st.divider()
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric("⏱️ Waktu Respon", f"{st.session_state.last_response_time:.2f}s")
    with metric_col2:
        total_questions = len([m for m in st.session_state.messages if m["role"] == "user"])
        st.metric("💬 Total Pertanyaan", total_questions)
    with metric_col3:
        total_responses = len([m for m in st.session_state.messages if m["role"] == "assistant"])
        st.metric("🤖 Total Jawaban", total_responses)
