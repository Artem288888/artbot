import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import requests
from bs4 import BeautifulSoup
import telebot
import time
import os

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

def fetch_plates_page(page=1):
    url = "https://opendata.hsc.gov.ua/check-leisure-license-plates/"
    params = {
        "region": "Львівська",
        "tsc": "Весь регіон",
        "type_venichle": "light_car_and_truck",
        "page": page
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        logger.error(f"Помилка при запиті сторінки {page}: {e}")
        return None

def parse_plates(html):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find("table")
    if not table:
        logger.warning("Таблиця не знайдена на сторінці!")
        return []

    plates = []
    rows = table.tbody.find_all("tr") if table.tbody else table.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if cols and len(cols) > 0:
            plate = cols[0].text.strip()
            plates.append(plate)
    return plates

def check_site():
    logger.info("Починаємо перевірку сайту...")
    page = 1
    new_found = []

    while True:
        html = fetch_plates_page(page)
        if not html:
            break

        plates = parse_plates(html)
        if not plates:
            logger.info(f"Немає номерів на сторінці {page}, завершуємо.")
            break

        new_matches = []
        for plate in plates:
            if plate not in seen_plates and is_interesting_plate(plate):
                seen_plates.add(plate)
                new_matches.append(plate)

        if new_matches:
            logger.info(f"Знайдено {len(new_matches)} нових цікавих номерів на сторінці {page}: {new_matches}")
            for plate in new_matches:
                try:
                    bot.send_message(CHAT_ID, f"🆕 Знайдено цікавий номер: {plate}")
                except Exception as e:
                    logger.error(f"Помилка надсилання повідомлення в Telegram: {e}")
            save_seen_plates(new_matches)
            new_found.extend(new_matches)
        else:
            logger.info(f"Нових цікавих номерів не знайдено на сторінці {page}.")

        # Перевіряємо, чи є кнопка "Наступна"
        soup = BeautifulSoup(html, 'html.parser')
        next_button = soup.find('a', string="Наступна")

        if not next_button:
            logger.info("Кнопка 'Наступна' не знайдена, завершуємо перевірку.")
            break

        button_classes = next_button.get('class', [])
        if 'disabled' in button_classes:
            logger.info("Кнопка 'Наступна' відключена, завершуємо перевірку.")
            break

        logger.info(f"Переходимо на наступну сторінку: {page + 1}")
        page += 1
        time.sleep(2)

    if new_found:
        logger.info(f"Загалом знайдено {len(new_found)} нових цікавих номерів.")
    else:
        logger.info("Нема нових цікавих номерів за цю перевірку.")

    try:
        bot.send_message(CHAT_ID, "✅ Перевірку завершено. Чекаємо 5 хв і починаємо знову.")
    except Exception as e:
        logger.error(f"Помилка надсилання завершального повідомлення: {e}")

def background_checker():
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
    logger.info("Бот запущено. Очікуємо нових номерів...")

    try:
        bot.send_message(CHAT_ID, "🔧 Тестове повідомлення від бота!")
        logger.info("Тестове повідомлення надіслано успішно.")
    except Exception as e:
        logger.error(f"Помилка надсилання тестового повідомлення: {e}")

    # Запускаємо перевірку сайту у фоновому потоці
    checker_thread = threading.Thread(target=background_checker, daemon=True)
    checker_thread.start()

    # Запускаємо вебсервер у головному потоці
    run_web_server()
