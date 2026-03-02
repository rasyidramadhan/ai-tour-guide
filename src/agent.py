import logging
import re
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.tools import HotelBookingTools, TimeService
from src.hotel_service import HotelService
from src.crawl import WebCrawler


logger = logging.getLogger(__name__)


class TravelAgent:    
    def __init__(self, llm, embedder, hotel_tools: HotelBookingTools, 
                 time_service: TimeService, hotel_service: HotelService):
        self.llm = llm
        self.embedder = embedder
        self.hotel_tools = hotel_tools
        self.time_service = time_service
        self.hotel_service = hotel_service
        self.web_crawler = WebCrawler(headless=True)
        self.prompts = self._load_prompts()
        logger.info("✅ WebCrawler initialized for agent")
    
    def _load_prompts(self) -> Dict[str, str]:
        try:
            prompt_file = os.path.join(os.path.dirname(__file__), "tour.txt")
            if not os.path.exists(prompt_file):
                logger.warning(f"Prompt file not found: {prompt_file}")
                return self._get_default_prompts()
            
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            prompts = {}
            sections = content.split('---')
            base_prompt = sections[0].strip() if len(sections) > 0 else ""
            prompts['base'] = base_prompt
            
            for i in range(1, len(sections), 2):
                if i < len(sections):
                    section_name = sections[i].strip().lower()
                    section_content = sections[i+1].strip() if i+1 < len(sections) else ""
                    if section_name and section_content:
                        prompts[section_name] = section_content
            
            logger.info(f"✅ Loaded {len(prompts)} prompt sections from tour.txt")
            return prompts
        
        except Exception as e:
            logger.error(f"Error loading prompts: {e}")
            return self._get_default_prompts()
    
    def _get_default_prompts(self) -> Dict[str, str]:
        return {
            'base': "Anda adalah Aizu, seorang pemandu wisata digital yang berpengalaman dan ramah.",
            'travel_planning': "Sebagai tour guide, jawab pertanyaan perjalanan dengan praktis.",
            'search_llm': "Berdasarkan informasi, berikan jawaban yang helpful.",
            'chat_general': "Jawab pertanyaan pengguna secara langsung dan ramah."
        }
    
    def _get_prompt(self, prompt_type: str) -> str:
        return self.prompts.get(prompt_type, self.prompts.get('base', ''))
    
    def _process_webcrawl_with_llm(self, tool_result: Dict[str, Any], user_query: str, intent: str) -> str:
        logger.info(f"Processing webcrawl results through LLM for intent: {intent}")
        
        try:
            context = ""
            
            if "hotels" in tool_result:
                hotels = tool_result.get("hotels", [])
                context = "Hotel tersedia:\n"
                for hotel in hotels[:5]:
                    context += f"• {hotel}\n"
            
            elif "destinations" in tool_result:
                destinations = tool_result.get("destinations", [])
                context = "Destinasi wisata:\n"
                for dest in destinations[:5]:
                    context += f"• {dest}\n"
            
            elif "recommendations" in tool_result:
                recs = tool_result.get("recommendations", [])
                context = "Rekomendasi destinasi:\n"
                for rec in recs[:5]:
                    context += f"• {rec.get('destination', '')}: {rec.get('description', '')}\n"
            
            else:
                return self.format_tool_result(tool_result)
            
            search_prompt_template = self._get_prompt('search_llm')
            
            prompt = f"""{search_prompt_template}
            Pertanyaan: {user_query}
            Data tersedia:
            {context}
            Jawab langsung tanpa mengulangi data:"""
            
            logger.debug(f"LLM Prompt: {prompt}")
            response = self.llm.invoke(prompt)
            
            answer = response.strip()
            lines = answer.split('\n')
            cleaned_lines = []
            for line in lines:
                if any(skip in line.lower() for skip in ['berdasarkan', 'pertanyaan:', 'data tersedia', 'jawab langsung']):
                    continue
                if line.strip():
                    cleaned_lines.append(line)
            
            cleaned_answer = '\n'.join(cleaned_lines) if cleaned_lines else answer
            logger.info("Webcrawl results processed through LLM successfully")
            return cleaned_answer
        
        except Exception as e:
            logger.error(f"Error processing webcrawl results with LLM: {e}")
            return self.format_tool_result(tool_result)
    
    def detect_intent(self, user_query: str) -> Dict[str, Any]:
        query_lower = user_query.lower()
        
        intents = {
            "execute_booking": {
                "keywords": ["pesan", "booking", "pesan hotel", "booking sekarang", "konfirmasi", "memesan"],
                "phrase_requirement": True
            },
            "search_hotels": {
                "keywords": ["cari hotel", "carikan hotel", "booking hotel", "akomodasi", "penginapan", "hotel di", "tunjukkan hotel"],
                "phrase_requirement": True
            },
            "search_destinations": {
                "keywords": [
                    "cari destinasi", "carikan destinasi", "tempat wisata", 
                    "objek wisata", "destinasi wisata", "tunjukkan destinasi", 
                    "wisata di"
                ],
                "phrase_requirement": True
            },
            "travel_planning": {
                "keywords": ["liburan", "perjalanan", "bagaimana cara ke", "cara ke", "transportasi", "caranya", "gimana ke", "naik apa", "dari"],
                "phrase_requirement": False
            },
            "get_recommendations": {
                "keywords": ["rekomendasi", "saran", "terbaik", "terdekat", "bagus"],
                "phrase_requirement": True
            },
            "check_time": {
                "keywords": ["jam berapa", "waktu", "jam ini"],
                "phrase_requirement": False
            }
        }
        
        detected_intent = None
        for intent, pattern in intents.items():
            for keyword in pattern["keywords"]:
                if keyword in query_lower:
                    detected_intent = intent
                    logger.info(f"Intent detected from keyword '{keyword}': {intent}")
                    break
            if detected_intent:
                break
        
        if not detected_intent:
            detected_intent = "chat"
            logger.debug(f"No specific intent matched, defaulting to 'chat'")
        
        entities = self._extract_entities(user_query, detected_intent)
        
        return {
            "intent": detected_intent,
            "entities": entities,
            "query": user_query
        }
    
    def _extract_entities(self, query: str, intent: str) -> Dict[str, Any]:
        entities = {}
        query_lower = query.lower()
        
        logger.debug(f"Extracting entities from query: {query_lower}")
        
        locations = [
            "Nanggroe Aceh Darussalam",
            "Sumatera Utara",
            "Sumatera Barat",
            "Riau",
            "Kepulauan Riau",
            "Jambi",
            "Bengkulu",
            "Sumatera Selatan",
            "Kepulauan Bangka Belitung",
            "Lampung",
            "Jakarta",
            "Jawa Barat",
            "Banten",
            "Jawa Tengah",
            "Yogyakarta",
            "Jawa Timur",
            "Bali",
            "Nusa Tenggara Barat",
            "Nusa Tenggara Timur",
            "Kalimantan Barat",
            "Kalimantan Tengah",
            "Kalimantan Selatan",
            "Kalimantan Timur",
            "Kalimantan Utara",
            "Sulawesi Utara",
            "Gorontalo",
            "Sulawesi Tengah",
            "Sulawesi Barat",
            "Sulawesi Selatan",
            "Sulawesi Tenggara",
            "Maluku",
            "Maluku Utara",
            "Papua",
            "Papua Barat",
            "Papua Selatan",
            "Papua Tengah",
            "Papua Pegunungan",
            "Papua Barat Daya",
        ]
        
        if intent == "travel_planning":
            extracted_locations = []
            for loc in locations:
                pattern = r'\b' + re.escape(loc.lower()) + r'\b'
                if re.search(pattern, query_lower):
                    extracted_locations.append(loc)
                    logger.debug(f"Found location: {loc}")            
        else:
            extracted_location = None
            for loc in locations:
                pattern = r'\b' + re.escape(loc.lower()) + r'\b'
                if re.search(pattern, query_lower):
                    extracted_location = loc
                    logger.debug(f"Found location: {loc}")
                    break
            
            if extracted_location:
                entities["location"] = extracted_location.title()
            else:
                logger.warning(f"No location found in query. Available locations: {locations[:5]}...")
        
        date_patterns = [
            r"(\d{1,2}[\s\-](?:januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember))",
            r"(\d{1,2}/\d{1,2})",
            r"(besok|lusa|minggu depan|bulan depan)",
            r"(\d{1,2}\s*(?:hari|malam)\s*(?:lagi)?)"
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, query_lower):
                entities["has_dates"] = True
                logger.debug("Found dates in query")
                break
        
        budget_match = re.search(r"(\d+)\s*(?:juta|ribu)", query_lower)
        if budget_match:
            amount = int(budget_match.group(1))
            entities["budget"] = amount * 1000000 if "juta" in budget_match.group() else amount * 1000
            logger.debug(f"Found budget: {entities['budget']}")
        
        dest_types = ["pantai", "gunung", "budaya", "alam", "tempat wisata", "destinasi wisata", "air terjun", "museum", "taman"]
        for dtype in dest_types:
            if dtype in query_lower:
                entities["destination_type"] = dtype
                logger.debug(f"Found destination type: {dtype}")
                break
        
        if any(k in query_lower for k in ["pesan", "memesan", "booking", "reservasi"]):
            hotel_keywords = [
                "resort", "hotel", "villa", "bungalow", "penthouse",
                "mandarin", "marriott", "hilton", "sheraton", "radisson",
                "novotel", "ibis", "swiss-belinn", "swiss-belhotel", "pullman", "sofitel",
                "mandalika", "amanjiwo", "raffles", "four seasons", "fairmont",
                "aryaduta", "mercure", "grand", "aston", "aston inn", "mitra", "santika"
            ]
            
            q_clean = re.sub(r'\b(pesan|memesan|booking|reservasi|tolong|ingin|saya|mau|carikan|cari)\b', '', query_lower).strip()
            
            for hotel in hotel_keywords:
                if hotel in q_clean:
                    parts = re.split(r'\s*\b(?:di|dari|untuk|sampai|pada|hingga|ke)\b\s*|\s*,\s*', q_clean)
                    
                    for part in parts:
                        if hotel in part:
                            entities["hotel_name"] = part.strip().title()
                            logger.debug(f"Found hotel name: {entities['hotel_name']}")
                            break
                    
                    if "hotel_name" in entities:
                        break
        
        logger.info(f"Extracted entities: {entities}")
        entities["query"] = query
        return entities
    
    def _extract_dates_from_query(self, query: str) -> Optional[Dict[str, str]]:
        try:
            query_lower = query.lower()
            tz = ZoneInfo("Asia/Jakarta")
            today = datetime.now(tz).date()
            
            date_matches = re.findall(r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})", query_lower)
            
            if date_matches:
                day, month, year = date_matches[0]
                start_date = datetime(int(year), int(month), int(day)).date()
                
                if len(date_matches) > 1:
                    day2, month2, year2 = date_matches[1]
                    end_date = datetime(int(year2), int(month2), int(day2)).date()
                else:
                    days_match = re.search(r"(\d+)\s*(?:hari|malam)", query_lower)
                    if days_match:
                        end_date = start_date + timedelta(days=int(days_match.group(1)))
                    else:
                        end_date = start_date + timedelta(days=3)
                
                logger.info(f"Specific date found: {start_date} to {end_date}")
                return {
                    "start_date": start_date.strftime("%d-%m-%Y"), 
                    "end_date": end_date.strftime("%d-%m-%Y")
                }
            
            relative_offsets = []
            
            if "sekarang" in query_lower or "hari ini" in query_lower:
                relative_offsets.append(0)
            if "besok" in query_lower:
                relative_offsets.append(1)
            if "lusa" in query_lower:
                relative_offsets.append(2)
            if "minggu depan" in query_lower:
                relative_offsets.append(7)
            if "bulan depan" in query_lower:
                relative_offsets.append(30)
            if "tahun depan" in query_lower:
                relative_offsets.append(365)
            
            if relative_offsets:
                relative_offsets.sort()
                start_date = today + timedelta(days=relative_offsets[0])
                
                if len(relative_offsets) > 1:
                    end_date = today + timedelta(days=relative_offsets[-1])
                else:
                    days_match = re.search(r"(\d+)\s*(?:hari|malam)", query_lower)
                    if days_match:
                        end_date = start_date + timedelta(days=int(days_match.group(1)))
                    else:
                        end_date = start_date + timedelta(days=3)
                
                logger.info(f"Relative time combination found: {start_date} to {end_date}")
                return {
                    "start_date": start_date.strftime("%d-%m-%Y"), 
                    "end_date": end_date.strftime("%d-%m-%Y")
                }
            
            days_match = re.search(r"(\d+)\s*(?:hari|malam)", query_lower)
            if days_match:
                duration = int(days_match.group(1))
                start_date = today + timedelta(days=1)
                end_date = start_date + timedelta(days=duration)
                return {"start_date": start_date.strftime("%d-%m-%Y"), "end_date": end_date.strftime("%d-%m-%Y")}
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting dates: {e}", exc_info=True)
            return None
        
    def _crawl_web_for_hotels(self, location: str, search_type: str = "hotel") -> List[str]:
        try:
            logger.info(f"Starting web crawl for {search_type} in {location}")
            crawled_results = self.web_crawler.search_holiday_destinations(location, search_type)
            
            if crawled_results:
                logger.info(f"✅ Web crawl successful: found {len(crawled_results)} results for {location}")
                return crawled_results
            else:
                logger.warning(f"Web crawl returned empty results for {location}, will use tool fallback")
                return []
        
        except Exception as e:
            logger.error(f"Error during web crawling for {location}: {e}")
            return []
    
    def _generate_travel_planning_answer(self, query: str, location: str, crawled_data: List[str] = None, source_location: str = None) -> str:
        try:
            logger.info(f"Generating travel planning answer for: {query}")
            
            context = ""
            if crawled_data and len(crawled_data) > 0:
                for item in crawled_data[:5]:
                    context += f"• {item}\n"
            
            destination_text = f"dari {source_location} ke {location}" if source_location else f"ke {location}"
            
            travel_prompt_template = self._get_prompt('travel_planning')
            
            prompt = f"""{travel_prompt_template}
            Pertanyaan: {query}
            Rute: {destination_text}
            Jawab langsung tanpa mengulangi pertanyaan:"""
            
            logger.debug(f"LLM Prompt for travel planning:\n{prompt}")
            response = self.llm.invoke(prompt)
            
            answer = response.strip()
            
            lines = answer.split('\n')
            cleaned_lines = []
            for line in lines:
                if any(skip in line.lower() for skip in ['pertanyaan:', 'rute:', 'jawab langsung', 'berikan jawaban']):
                    continue
                if line.strip():
                    cleaned_lines.append(line)
            
            cleaned_answer = '\n'.join(cleaned_lines)
            
            logger.info("✅ Travel planning answer generated successfully")
            return cleaned_answer if cleaned_answer else answer
        
        except Exception as e:
            logger.error(f"Error generating travel planning answer: {e}")
            source_text = f" dari {source_location}" if source_location else ""
            fallback = f"""Untuk perjalanan{source_text} ke {location}:

            📍 **Transportasi:** Terbang, kereta, atau bus tersedia
            ⏱️ **Waktu:** 4-6 jam perjalanan tergantung moda
            💰 **Biaya:** Bervariasi Rp 200rb-1.5jt tergantung pilihan
            📋 **Persiapan:** Buat jadwal 1-2 minggu sebelumnya
            🏖️ **Musim terbaik:** April-Oktober (musim kemarau)
            🎒 **Bawa:** Dokumen, uang tunai, proteksi matahari

            Ingin bantuan memesan hotel atau transportasi tertentu?"""
            return fallback
    
    def call_tool(self, intent: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Calling tool for intent: {intent} with entities: {entities}")
        
        try:
            if intent == "search_hotels":
                location = entities.get("location")
                if not location:
                    logger.warning(f"Location not extracted from query. Available entities: {entities}")
                    return {"success": False, "error": "Lokasi tidak ditemukan. Coba sebutkan nama Provinsinya"}
                
                logger.info(f"Initiating web crawl for hotels in {location}")
                
                query = entities.get("query", "")
                dates = self._extract_dates_from_query(query)
                
                start_date = dates["start_date"] if dates else None
                end_date = dates["end_date"] if dates else None
                
                if dates:
                    logger.info(f"Searching hotels in {location} from {start_date} to {end_date}")
                else:
                    logger.info(f"Searching hotels in {location} without specific dates")
                
                result = self.hotel_tools.search_hotels(
                    location=location,
                    start_date=start_date,
                    end_date=end_date
                )
                
                logger.info(f"Hotel search result: {result}")
                return result
            
            elif intent == "search_destinations":
                query = entities.get("query", "")
                dates = self._extract_dates_from_query(query)
                
                location = entities.get("location", "")
                dest_type = entities.get("destination_type", "destinasi wisata")
                
                if not location:
                    return {"success": False, "error": "Lokasi destinasi tidak ditemukan. Coba sebutkan nama Provinsinya."}

                logger.info(f"Initiating web crawl for destinations in {location}")
                
                start_date = dates["start_date"] if dates else None
                end_date = dates["end_date"] if dates else None
                
                result = self.hotel_tools.search_destinations(
                    location=location,
                    start_date=start_date,
                    end_date=end_date,
                    destination_type=dest_type
                )
                return result
            
            elif intent == "get_recommendations":
                budget = entities.get("budget")
                dest_type = entities.get("destination_type", "pantai")
                
                result = self.hotel_tools.get_recommendations(
                    budget=budget,
                    destination_type=dest_type
                )
                return result
            
            elif intent == "check_time":
                current_time = self.time_service.get_current_time()
                return {"success": True, "result": f"Waktu saat ini: {current_time}"}
            
            elif intent == "execute_booking":
                location = entities.get("location")
                hotel_name = entities.get("hotel_name", "")
                query = entities.get("query", "")
                dates = self._extract_dates_from_query(query)
                
                if not location:
                    return {"success": False, "error": "Mohon sebutkan lokasi hotel. Contoh: 'Pesan hotel di Yogyakarta'"}
                
                if not dates:
                    return {"success": False, "error": "Tanggal booking tidak jelas"}
                
                logger.info(f"Initiating web crawl for latest hotel information in {location}")
                logger.info(f"Executing booking for {hotel_name} in {location}")
                
                booking_details = {
                    "location": location,
                    "hotel_name": hotel_name,
                    "room_type": "Standard",
                    "check_in": dates["start_date"],
                    "check_out": dates["end_date"],
                    "total_price": None  
                }
                
                result = self.hotel_service.execute_booking(booking_details)
                return result
            
            elif intent == "travel_planning":
                logger.info(f"Processing travel planning question: {entities.get('location', 'unknown')}")
                
                location = entities.get("location", "")
                source_location = entities.get("source_location")
                query = entities.get("query", "")
                
                logger.info("Travel planning: using pure LLM for general guidance")
                answer = self._generate_travel_planning_answer(query, location, crawled_data=None, source_location=source_location)
                
                return {
                    "success": True,
                    "answer": answer,
                    "type": "travel_planning"
                }
            
            else:
                return None
        
        except Exception as e:
            logger.error(f"Error calling tool: {e}")
            return {"success": False, "error": str(e)}
    
    def format_tool_result(self, tool_result: Dict[str, Any]) -> str:
        if not tool_result:
            return "❌ Tidak ada hasil"
        
        if not tool_result.get("success"):
            error_msg = tool_result.get("error") or tool_result.get("message") or "Terjadi kesalahan"
            return f"❌ {error_msg}"
        
        if "hotels" in tool_result:
            hotels = tool_result.get("hotels", [])
            if hotels and len(hotels) > 0:
                location = tool_result.get("location", "")
                check_in = tool_result.get("check_in", "")
                check_out = tool_result.get("check_out", "")
                
                output = f"✅ Hotel tersedia di {location}\n"
                output += "Pilihan Hotel: \n"
                
                for i, hotel in enumerate(hotels[:10], 1):
                    if hotel.strip():
                        output += f"{i}. {hotel.strip()}\n"
                
                return output
            else:
                return "❌ Tidak menemukan hotel yang sesuai"
        
        if "destinations" in tool_result:
            destinations = tool_result.get("destinations", [])
            if destinations:
                output = f"✅ Menemukan {len(destinations)} destinasi:\n\n"
                for i, dest in enumerate(destinations[:10], 1):
                    output += f"{i}. {dest}\n"
                return output
            else:
                return "❌ Tidak menemukan destinasi yang sesuai"
        
        if "recommendations" in tool_result:
            recs = tool_result.get("recommendations", [])
            if recs:
                budget = tool_result.get("budget", 0)
                output = f"✅ Rekomendasi destinasi dengan budget Rp{budget:,.0f}:\n\n"
                for i, rec in enumerate(recs[:10], 1):
                    output += f"{i}. {rec.get('destination')} - {rec.get('rating')}\n"
                    output += f"   {rec.get('description')}\n"
                return output
            else:
                return "❌ Tidak menemukan rekomendasi"
        
        if "confirmation_number" in tool_result:
            confirmation_number = tool_result.get("confirmation_number")
            
            booking_details = tool_result.get("booking_details", {})
            location = booking_details.get("location", tool_result.get("location", ""))
            check_in = booking_details.get("check_in", tool_result.get("check_in", ""))
            check_out = booking_details.get("check_out", tool_result.get("check_out", ""))
            hotel_name = booking_details.get("hotel_name", tool_result.get("hotel_name", ""))
            
            output = f"✅ Pemesanan berhasil!\n\n"
            output += f"Nomor Konfirmasi: {confirmation_number}\n"
            
            if hotel_name:
                output += f"Hotel: {hotel_name}\n"
                
            output += f"Lokasi: {location}\n"
            output += f"Check-in: {check_in}\n"
            output += f"Check-out: {check_out}\n" 
                
            return output
        
        logger.warning(f"Unknown tool result format: {tool_result}")
        return f"✅ Hasil: {str(tool_result)[:100]}..."
    
    def _save_to_json_file(self, data: Dict[str, Any], output_dir: str = "output"):
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
        filepath = os.path.join(output_dir, f"log_{timestamp}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        logger.info(f"Output saved to {filepath}")
    
    def process_with_tools(self, user_query: str) -> Dict[str, Any]:
        logger.info(f"Processing query with tools: {user_query}")
        intent_result = self.detect_intent(user_query)
        intent = intent_result["intent"]
        entities = intent_result["entities"]
        
        logger.info(f"Detected intent: {intent}, entities: {entities}")
        
        tool_result = None
        
        if intent != "chat":
            tool_result = self.call_tool(intent, entities)
            
            if tool_result:
                if intent in ["get_recommendations"]:
                    answer = self._process_webcrawl_with_llm(tool_result, user_query, intent)
                    logger.info(f"Processed webcrawl results through LLM for intent: {intent}")
                elif intent == "travel_planning":
                    answer = tool_result.get("answer", "Maaf, tidak dapat memproses pertanyaan perjalanan Anda.")
                    logger.info(f"Travel planning answer: {answer[:100]}...")
                else:
                    answer = self.format_tool_result(tool_result)
                
                final_result = {
                    "success": True,
                    "intent": intent,
                    "tool_called": True,
                    "tool_name": intent,
                    "answer": answer,
                    "tool_result": tool_result,
                    "entities": entities
                }
                
                self._save_to_json_file(final_result)
                
                return final_result
        
        logger.info("Using pure LLM for chat/general question")
        base_context = self._get_prompt('base')
        chat_template = self._get_prompt('chat_general')
        
        chat_prompt = f"""{base_context}

        {chat_template}
        Pertanyaan: {user_query}
        Jawaban:"""
        
        try:
            llm_answer = self.llm.invoke(chat_prompt)
            logger.info("LLM chat response generated successfully")
            
            answer = llm_answer.strip()
            lines = answer.split('\n')
            cleaned_lines = []
            for line in lines:
                if any(skip in line.lower() for skip in ['Anda adalah Aizu', 'jawaban singkat', 'jawab pertanyaan']):
                    continue
                if line.strip() and not line.startswith('•'):
                    cleaned_lines.append(line)
            
            answer = '\n'.join(cleaned_lines) if cleaned_lines else answer
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            answer = "Saya siap membantu! Tanyakan tentang destinasi liburan, hotel, transportasi, atau hal lainnya. 😊"
        
        final_result = {
            "success": True,
            "intent": intent,
            "tool_called": False,
            "answer": answer.strip(),
            "entities": entities
        }

        self._save_to_json_file(final_result)

        return final_result


def create_agent(llm, embedder, hotel_service: HotelService) -> TravelAgent:
    hotel_tools = HotelBookingTools(hotel_service)
    time_service = TimeService()
    
    return TravelAgent(
        llm=llm,
        embedder=embedder,
        hotel_tools=hotel_tools,
        time_service=time_service,
        hotel_service=hotel_service
    )
