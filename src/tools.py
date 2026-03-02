from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any
import logging
from src.hotel_service import HotelService

logger = logging.getLogger(__name__)


class TimeService:    
    def __init__(self, timezone: str = "Asia/Jakarta"):
        self.timezone = timezone

    def get_current_time(self) -> str:
        try:
            tz = ZoneInfo(self.timezone)
            current_time = datetime.now(tz)
            return current_time.strftime("%d-%m-%Y %H:%M")
        except Exception as e:
            logger.error(f"Error getting time: {e}")
            return f"Error getting time: {e}"

    def check_calendar(self, date_str: str) -> Dict[str, Any]:
        try:
            requested_date = datetime.strptime(date_str, "%d-%m-%Y")
            
            tz = ZoneInfo(self.timezone)
            current_date = datetime.now(tz).date()
            
            if requested_date.date() <= current_date:
                return {
                    "available": False,
                    "message": f"Tanggal {date_str} sudah terlewat atau hari ini. Pilih tanggal di masa depan.",
                    "date": date_str
                }
            
            days_ahead = (requested_date.date() - current_date).days
            
            return {
                "available": True,
                "message": f"Tanggal {date_str} tersedia ({days_ahead} hari dari sekarang)",
                "date": date_str,
                "days_ahead": days_ahead
            }
        
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return {
                "available": False,
                "message": f"Format tanggal tidak valid. Gunakan format DD-MM-YYYY",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error checking calendar: {e}")
            return {
                "available": False,
                "message": f"Error: {str(e)}",
                "error": str(e)
            }

    def validate_date_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        try:
            start = datetime.strptime(start_date, "%d-%m-%Y")
            end = datetime.strptime(end_date, "%d-%m-%Y")
            
            if end <= start:
                return {
                    "valid": False,
                    "message": "Tanggal akhir harus lebih besar dari tanggal awal"
                }
            
            duration = (end - start).days            
            tz = ZoneInfo(self.timezone)
            current_date = datetime.now(tz).date()
            
            if end.date() <= current_date:
                return {
                    "valid": False,
                    "message": "Tanggal liburan sudah terlewat"
                }
            
            return {
                "valid": True,
                "message": f"Range tanggal valid ({duration} malam)",
                "start_date": start_date,
                "end_date": end_date,
                "duration_days": duration
            }
        
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return {
                "valid": False,
            "message": "Format tanggal tidak valid. Gunakan DD-MM-YYYY (contoh: 22-01-2026)",
                "error": str(e)
            }

class HotelBookingTools:
    def __init__(self, hotel_service: HotelService):
        self.hotel_service = hotel_service
        self.time_service = TimeService()

    def search_destinations(self, location: str, start_date: str, end_date: str, destination_type: str) -> Dict[str, Any]:
        try:
            logger.info(f"Searching destinations: {destination_type} in {location} from {start_date} to {end_date}")
            
            validation = self.time_service.validate_date_range(start_date, end_date)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": validation["message"],
                    "destinations": []
                }
            
            dates = {"start_date": start_date, "end_date": end_date}
            preferences = {"type": destination_type}
            destinations = self.hotel_service.search_destinations_by_date(
                dates=dates,
                preferences=preferences,
                location=location
            )
            
            if destinations:
                destination_list = [d["destination"] for d in destinations]
                return {
                    "success": True,
                    "message": f"Menemukan {len(destination_list)} destinasi untuk {destination_type} di {location}",
                    "destinations": destination_list,
                    "location": location,
                    "start_date": start_date,
                    "end_date": end_date,
                    "duration_days": validation["duration_days"],
                    "total_found": len(destination_list)
                }
            else:
                return {
                    "success": False,
                    "message": f"Tidak menemukan destinasi {destination_type} untuk tanggal tersebut",
                    "destinations": [],
                    "start_date": start_date,
                    "end_date": end_date
                }
        
        except Exception as e:
            logger.error(f"Error searching destinations: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "destinations": []
            }

    def search_hotels(self, location: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        try:
            logger.info(f"Searching hotels in {location}: {start_date} to {end_date}")
            
            if start_date and end_date:
                validation = self.time_service.validate_date_range(start_date, end_date)
                if not validation.get("valid", False):
                    return {
                        "success": False,
                        "message": validation.get("message", "Format tanggal tidak valid"),
                        "location": location,
                        "hotels": []
                    }
            
            dates = {"start_date": start_date, "end_date": end_date}
            result = self.hotel_service.search_hotels(location, dates)
            
            if "error" in result:
                return {
                    "success": False,
                    "message": result["error"],
                    "location": location,
                    "hotels": []
                }
            
            hotels_data = result.get("hotels", result.get("hotels_found", []))
            
            if isinstance(hotels_data, list):
                hotel_list = hotels_data
            elif isinstance(hotels_data, str) and hotels_data.strip():
                hotel_list = hotels_data.split("\n")
            else:
                hotel_list = []
            
            return {
                "success": True,
                "message": f"Hotel ditemukan di {location}",
                "location": location,
                "check_in": result.get("check_in", "Kapan saja"),
                "check_out": result.get("check_out", "Kapan saja"),
                "duration_nights": result.get("duration_days", 0),
                "hotels": hotel_list,
                "payment_method": result.get("user_payment_method", "-")
            }
        
        except Exception as e:
            logger.error(f"Error searching hotels: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "location": location,
                "hotels": []
            }

    def get_recommendations(self, budget: float, destination_type: str) -> Dict[str, Any]:
        try:
            logger.info(f"Getting recommendations: budget={budget}, type={destination_type}")
            
            preferences = {"type": destination_type}
            recommendations = self.hotel_service.get_booking_recommendations(budget, preferences)
            
            if recommendations:
                return {
                    "success": True,
                    "message": f"Menemukan {len(recommendations)} rekomendasi destinasi",
                    "budget": budget,
                    "currency": "IDR",
                    "destination_type": destination_type,
                    "recommendations": recommendations,
                    "total_recommendations": len(recommendations)
                }
            else:
                return {
                    "success": False,
                    "message": "Tidak menemukan rekomendasi yang sesuai",
                    "budget": budget,
                    "recommendations": []
                }
        
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "recommendations": []
            }

    def execute_booking(self, location: str, hotel_name: str, room_type: str, 
                       start_date: str, end_date: str, total_price: float) -> Dict[str, Any]:
        try:
            logger.info(f"Executing booking: {hotel_name} at {location}")
            validation = self.time_service.validate_date_range(start_date, end_date)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": validation["message"],
                    "booking_reference": None
                }
            
            if not self.hotel_service.user_payment_info:
                return {
                    "success": False,
                    "message": "Informasi pembayaran tidak tersedia",
                    "booking_reference": None
                }
            
            booking_details = {
                "location": location,
                "hotel_name": hotel_name,
                "room_type": room_type,
                "check_in": start_date,
                "check_out": end_date,
                "total_price": total_price
            }
            
            result = self.hotel_service.execute_booking(booking_details)
            
            if result["success"]:
                logger.info(f"Booking successful: {result['confirmation_number']}")
                
                return {
                    "success": True,
                    "message": "Booking berhasil dikonfirmasi!",
                    "booking_reference": result["confirmation_number"],
                    "confirmation_number": result["confirmation_number"],
                    "location": location,
                    "hotel_name": hotel_name,
                    "room_type": room_type,
                    "check_in": start_date,
                    "check_out": end_date,
                    "duration_nights": validation["duration_days"],
                    "total_price": total_price,
                    "currency": "IDR",
                    "status": "Confirmed",
                    "payment_method": result.get("payment_info", {}).get("method"),
                    "booking_details": result.get("booking_details")
                }
            
            else:
                logger.warning(f"Booking failed: {result['message']}")
                return {
                    "success": False,
                    "message": result["message"],
                    "booking_reference": None,
                    "error": result.get("message")
                }
        
        except Exception as e:
            logger.error(f"Error executing booking: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "booking_reference": None
            }

    def cancel_booking(self, booking_reference: str) -> Dict[str, Any]:
        try:
            logger.info(f"Cancelling booking: {booking_reference}")
            
            if not booking_reference or len(booking_reference) < 5:
                return {
                    "success": False,
                    "message": "Nomor referensi booking tidak valid"
                }
            
            return {
                "success": True,
                "message": f"Booking {booking_reference} berhasil dibatalkan",
                "booking_reference": booking_reference,
                "refund_status": "Diproses",
                "refund_amount": "100%",
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error cancelling booking: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e)
            }

def get_hotel_tools(hotel_service: HotelService) -> Dict[str, Any]:
    tools = HotelBookingTools(hotel_service)
    return {
        "search_destinations": {
            "function": tools.search_destinations,
            "description": "Cari destinasi liburan berdasarkan tanggal dan tipe",
            "parameters": {
                "start_date": "Format DD-MM-YYYY",
                "end_date": "Format DD-MM-YYYY",
                "destination_type": "hotel, pantai, gunung, atau budaya"
            }
        },
        "search_hotels": {
            "function": tools.search_hotels,
            "description": "Cari hotel di destinasi untuk tanggal tertentu",
            "parameters": {
                "location": "Nama kota/destinasi",
                "start_date": "Format DD-MM-YYYY",
                "end_date": "Format DD-MM-YYYY"
            }
        },
        "get_recommendations": {
            "function": tools.get_recommendations,
            "description": "Dapatkan rekomendasi destinasi berdasarkan budget dan preferensi",
            "parameters": {
                "budget": "Budget dalam IDR",
                "destination_type": "Tipe destinasi"
            }
        },
        "execute_booking": {
            "function": tools.execute_booking,
            "description": "Execute booking hotel (simulasi/dummy)",
            "parameters": {
                "location": "Nama destinasi",
                "hotel_name": "Nama hotel",
                "room_type": "Tipe kamar",
                "start_date": "Format DD-MM-YYYY",
                "end_date": "Format DD-MM-YYYY",
                "total_price": "Harga total dalam IDR"
            }
        },
        "cancel_booking": {
            "function": tools.cancel_booking,
            "description": "Batalkan booking hotel",
            "parameters": {
                "booking_reference": "Nomor referensi booking"
            }
        }
    }
