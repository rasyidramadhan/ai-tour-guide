import logging
import random
import string
from datetime import datetime
from typing import List, Dict, Optional
from src.crawl import WebCrawler

logger = logging.getLogger(__name__)

class HotelService:
    def __init__(self, user_payment_info: Dict):
        self.user_payment_info = user_payment_info
        self.crawler = WebCrawler(headless=True)
        self.search_history = []
        self.booking_history = []
        self.last_booking = None
        self.provinces = [
            "Nanggroe Aceh Darussalam", "Sumatera Utara", "Sumatera Barat", "Riau",
            "Kepulauan Riau", "Jambi", "Bengkulu", "Sumatera Selatan",
            "Kepulauan Bangka Belitung", "Lampung", "Jakarta", "Jawa Barat",
            "Banten", "Jawa Tengah", "Yogyakarta", "Jawa Timur", "Bali",
            "Nusa Tenggara Barat", "Nusa Tenggara Timur", "Kalimantan Barat",
            "Kalimantan Tengah", "Kalimantan Selatan", "Kalimantan Timur",
            "Kalimantan Utara", "Sulawesi Utara", "Gorontalo", "Sulawesi Tengah",
            "Sulawesi Barat", "Sulawesi Selatan", "Sulawesi Tenggara", "Maluku",
            "Maluku Utara", "Papua", "Papua Barat", "Papua Selatan",
            "Papua Tengah", "Papua Pegunungan", "Papua Barat Daya",
        ]

    def check_user_calendar(self, user_dates: Dict) -> bool:
        try:
            start_val = user_dates.get("start_date")
            end_val = user_dates.get("end_date")

            if start_val is None or end_val is None:
                return True

            start_date = datetime.strptime(str(start_val), "%d-%m-%Y")
            end_date = datetime.strptime(str(end_val), "%d-%m-%Y")

            if start_date >= end_date:
                logger.warning("End date must be greater than start date")
                return False

            if start_date.date() < datetime.now().date():
                logger.warning("Date must be in the future")
                return False

            logger.info(f"✅ Calender valid: {start_date.date()} - {end_date.date()}")
            return True

        except Exception as e:
            logger.error(f"Date validation error: {e}")
            return True
        
        except Exception as e:
            logger.error(f"Date validation error: {e}", exc_info=True)
            return False

    def search_destinations_by_date(
        self,
        dates: Dict,
        preferences: Optional[Dict] = None,
        location: Optional[str] = None
    ) -> List[Dict]:

        logger.info(f"DEBUG raw location param: {location}")

        if not self.check_user_calendar(dates):
            return []

        if location and location.strip():
            search_provinces = [location.strip()]
        else:
            search_provinces = self.provinces

        destinations = []
        for province in search_provinces:
            logger.info(f"Searching for destinations in {province}...")

            try:
                dest_type = preferences.get("type", "hotel") if preferences else "hotel"

                results = self.crawler.search_holiday_destinations(
                    city=province,
                    destination_type=dest_type
                )

                if results:
                    for result in results:
                        destinations.append({
                            "province": province,
                            "destination": result,
                            "start_date": dates.get("start_date", "Kapan saja"),
                            "end_date": dates.get("end_date", "Kapan saja"),
                            "preferences": preferences or {}
                        })

                    logger.info(f"✅ {len(results)} ditemukan di {province}")

            except Exception as e:
                logger.warning(f"Error on {province}: {e}")

        logger.info(f"📍 Total destinations found: {len(destinations)}")
        return destinations

    def search_hotels(self, location: str, dates: Dict) -> Dict:
        if not self.check_user_calendar(dates):
            return {"error": "Tanggal tidak valid"}

        logger.info(f"Searching for hotels in {location}...")

        results = self.crawler.search_holiday_destinations(
            city=location,
            destination_type="hotel"
        )

        if not results:
            return {"error": f"Tidak ada hotel di {location}"}

        return {
            "location": location,
            "check_in": dates.get("start_date", "Kapan saja"),
            "check_out": dates.get("end_date", "Kapan saja"),
            "hotels_found": results[:10] 
        }

    def execute_booking(self, booking_details: Dict) -> Dict:
        logger.info(f"Processing bookings for {booking_details.get('hotel_name')}...")

        try:
            if not self.user_payment_info:
                return {
                    "success": False,
                    "message": "Informasi pembayaran tidak tersedia. Harap tambahkan metode pembayaran terlebih dahulu."
                }

            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            conf_number = f"BKG-{random_str}"

            booking_record = {
                "confirmation_number": conf_number,
                "booking_details": booking_details,
                "payment_info": self.user_payment_info,
                "status": "Confirmed",
                "timestamp": datetime.now().isoformat()
            }

            self.booking_history.append(booking_record)
            self.last_booking = booking_record

            return {
                "success": True,
                "message": "Booking berhasil diproses.",
                "confirmation_number": conf_number,
                "booking_details": booking_details,
                "payment_info": self.user_payment_info
            }
            
        except Exception as e:
            logger.error(f"Error saat memproses booking: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Terjadi kesalahan internal saat booking: {str(e)}"
            }

    def get_booking_recommendations(self, budget: float, preferences: Dict) -> List[Dict]:
        logger.info(f"Looking for recommendations on a budget {budget}")
        return []

    def update_payment_info(self, payment_info: Dict):
        self.user_payment_info = payment_info
        logger.info(f"💳 Payment information updated successfully")

    def close_crawler(self):
        if self.crawler:
            self.crawler.driver.quit() 
            logger.info("Crawler closed")