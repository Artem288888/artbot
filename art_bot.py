import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import telebot
import time
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()

BOT_TOKEN = '7650951016:AAE1sBUl6Lq-Y9xwbjyyoDlcPhQsWyYpnR4'
CHAT_ID = '6854620915'

bot = telebot.TeleBot(BOT_TOKEN)

SEEN_FILE = 'seen_plates.txt'

def load_seen_plates():
    if not os.path.exists(SEEN_FILE):
        logger.info("Файл з раніше побаченими номерами не знайдено, створюємо новий.")
        return set()
    with open(SEEN_FILE, 'r', encoding='utf-8') as f:
        plates = set(line.strip() for line in f if line.strip())
        logger.info(f"Завантажено {len(plates)} номерів з файлу.")
        return plates

def save_seen_plates(plates):
    with open(SEEN_FILE, 'a', encoding='utf-8') as f:
        for plate in plates:
            f.write(plate + '\n')
    logger.info(f"Збережено {len(plates)} нових номерів у файл.")

seen_plates = load_seen_plates()

def is_interesting_plate(plate):
    plate_str = plate.replace(" ", "").upper()
    zeros = plate_str.count("0")
    sevens = plate_str.count("7")
    return (
        zeros >= 2 or
        sevens >= 2 or
        "0707" in plate_str or
        "7707" in plate_str
    )

def fetch_plates_with_selenium():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)
    url = "https://opendata.hsc.gov.ua/check-leisure-license-plates/?region=Львівська&tsc=Весь+регіон&type_venichle=light_car_and_truck"
    driver.get(url)

    all_plates = set()
    wait = WebDriverWait(driver, 10)

    while True:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))

            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            if not rows:
                logger.warning("Не знайдено рядків у таблиці.")
                break

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if cols:
                    plate = cols[0].text.strip()
                    all_plates.add(plate)

            # --- ОНОВЛЕНИЙ БЛОК ПАГІНАЦІЇ ---
            next_button = None
            buttons = driver.find_elements(By.CSS_SELECTOR, "a.paginate_button.next")
            for b in buttons:
                logger.info(f"Кнопка пагінації: текст='{b.text}', id='{b.get_attribute('id')}', клас='{b.get_attribute('class')}'")
                if b.text.strip() == "Наступна":
                    next_button = b
                    break

            if not next_button:
                logger.info("Кнопка 'Наступна' не знайдена (по класу і тексту), завершуємо.")
                break

            classes = next_button.get_attribute("class")
            if "disabled" in classes:
                logger.info("Кнопка 'Наступна' відключена — кінець пагінації.")
                break

            logger.info("Переходимо на наступну сторінку.")
            next_button.click()

            wait.until(EC.staleness_of(rows[0]))
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))

            time.sleep(1)

        except TimeoutException:
            logger.info("Таймаут очікування пагінації, завершуємо.")
            break
        except NoSuchElementException as e:
            logger.info(f"Кнопку 'Наступна' не знайдено або не вдається натиснути, завершуємо. {e}")
            break
        except Exception as e:
            logger.error(f"Несподівана помилка: {e}")
            break

    driver.quit()
    return list(all_plates)

def check_site():
    logger.info("Починаємо перевірку сайту...")

    plates = fetch_plates_with_selenium()
    if not plates:
        logger.warning("Не вдалося завантажити номери.")
        return

    new_matches = []
    for plate in plates:
        if plate not in seen_plates and is_interesting_plate(plate):
            seen_plates.add(plate)
            new_matches.append(plate)

    if new_matches:
        logger.info(f"Знайдено {len(new_matches)} нових цікавих номерів: {new_matches}")
        for plate in new_matches:
            try:
                bot.send_message(CHAT_ID, f"🆕 Знайдено цікавий номер: {plate}")
            except Exception as e:
                logger.error(f"Помилка надсилання повідомлення в Telegram: {e}")
        save_seen_plates(new_matches)
    else:
        logger.info("Нових цікавих номерів не знайдено.")

    try:
        bot.send_message(CHAT_ID, "✅ Перевірку завершено. Чекаємо 5 хв і починаємо знову.")
    except Exception as e:
        logger.error(f"Помилка надсилання завершального повідомлення: {e}")

def background_checker():
    try:
        bot.send_message(CHAT_ID, "🤖 Бот запущено. Починаємо моніторинг номерів.")
    except Exception as e:
        logger.error(f"Помилка надсилання стартового повідомлення: {e}")

    while True:
        try:
            logger.info("Запуск перевірки сайту (фоновий потік).")
            check_site()
        except Exception as e:
            logger.error(f"Помилка у фонового циклі: {e}")
        logger.info("Чекаємо 5 хвилин перед наступною перевіркою...")
        time.sleep(300)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running.")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_web_server():
    port = int(os.getenv("PORT", "10000"))
    logger.info(f"Запускаємо вебсервер на порті {port}")
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()

    background_checker()
