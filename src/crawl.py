import time
import logging
import platform
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from src.loader import load_config

logger = logging.getLogger(__name__)

class WebCrawler:
    def __init__(self, headless=True, max_results=10):
        self.max_results = max_results
        options = webdriver.ChromeOptions()
        options.add_argument("--incognito")

        if headless:
            options.add_argument("--headless=new")

        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        if platform.system() == "Linux":
            options.binary_location = "/usr/bin/chromium"
            service = Service("/usr/bin/chromedriver")
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)

    def crawl(self, destination: str, city: str) -> List[str]:
        url = load_config(["url_maps"])

        try:
            self.driver.get(url)
            time.sleep(3)

            try:
                consent_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, '//button//span[contains(text(),"Accept")]')
                    )
                )
                consent_button.click()
                time.sleep(2)
            except:
                pass

            search_box = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )

            query = f"{destination} di {city}"
            logger.info(f"Search {query}")

            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)

            time.sleep(5)

            return self._extract_results(city)

        except Exception as e:
            logger.error(f"Error saat crawling: {e}", exc_info=True)
            return []

    def _extract_results(self, city: str) -> List[str]:
        results = []
        try:
            feed_xpath = '//div[@role="feed"]'
            result_el = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, feed_xpath))
            )
            
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'hfpxzc'))
                )
            except Exception as e:
                logger.warning(f"Card timeout or slow: {e}")
            
            time.sleep(2)

            last_count = 0
            try_cnt = 5

            while True:
                elements = result_el.find_elements(By.CLASS_NAME, 'hfpxzc')
                
                if not elements:
                    elements = result_el.find_elements(By.XPATH, './/a[contains(@href, "/place/")]')

                current_count = len(elements)
                
                if current_count >= self.max_results:
                    break
                if current_count == 0:
                    logger.warning("Data is completely empty from Google Maps.")
                    break

                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", result_el)
                time.sleep(3)

                if current_count == last_count:
                    try_cnt -= 1
                    if try_cnt <= 0:
                        break
                else:
                    last_count = current_count
                    try_cnt = 5

            for place in elements:
                if len(results) >= self.max_results:
                    break
                    
                try:
                    name = place.get_attribute("aria-label")
                    if name and name.strip() and f"{name.strip()}, {city}" not in results:
                        results.append(f"{name.strip()}, {city}")

                except Exception:
                    continue

            logger.info(f"Total results collected: {len(results)}")
            return results

        except Exception as e:
            logger.error(f"Error while extracting results: {e}", exc_info=True)
            return results

    def _format_result(self, text: str, city: str) -> Optional[str]:
        try:
            text = text.replace("\n", " ").strip()

            if len(text) < 2:
                return None

            return f"{text}, {city}"

        except Exception as e:
            logger.warning(f"Format error: {e}")
            return None

    def search_holiday_destinations(
        self,
        city: str,
        destination_type: str = "destinasi wisata"
    ) -> List[str]:

        logger.info(f"Mencari {destination_type} di {city}")
        return self.crawl(destination_type, city)

    def batch_search(
        self,
        cities: List[str],
        destination_types: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:

        if destination_types is None:
            destination_types = [
                "destinasi wisata",
                "hotel",
                "pantai",
                "gunung"
            ]

        all_results = {}

        for city in cities:
            city_results = []

            for dest_type in destination_types:
                results = self.search_holiday_destinations(city, dest_type)
                city_results.extend(results)
                time.sleep(2)

            all_results[city] = list(set(city_results))

        return all_results

    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")
