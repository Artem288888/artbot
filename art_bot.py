import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import telebot
import time
import os
from webdriver_manager.chrome import ChromeDriverManager  # <-- додано

# --- Налаштування логування ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()

# --- Фейковий вебсервер для Render ---
def run_fake_web_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running.")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

    port = int(os.getenv("PORT", "10000"))
    logger.info(f"Запускаємо вебсервер на порті {port}")
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()

threading.Thread(target=run_fake_web_server, daemon=True).start()

# --- Твої дані ---
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

def check_site():
    logger.info("Починаємо перевірку сайту...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # Ось тут використовуємо webdriver_manager
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        url = "https://opendata.hsc.gov.ua/check-leisure-license-plates/"
        driver.get(url)
        logger.info("Сторінка завантажена.")

        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'select[name="region"]'))
        )
        oblast_select = driver.find_element(By.CSS_SELECTOR, 'select[name="region"]')
        for option in oblast_select.find_elements(By.TAG_NAME, "option"):
            if option.text.strip() == "Львівська":
                option.click()
                logger.info("Вибрано регіон Львівська.")
                break
        time.sleep(1)

        tsc_select = driver.find_element(By.CSS_SELECTOR, 'select[name="tsc"]')
        for option in tsc_select.find_elements(By.TAG_NAME, "option"):
            if option.text.strip() == "Весь регіон":
                option.click()
                logger.info("Вибрано 'Весь регіон'.")
                break
        time.sleep(1)

        type_select = driver.find_element(By.CSS_SELECTOR, 'select[name="type_venichle"]')
        for option in type_select.find_elements(By.TAG_NAME, "option"):
            if option.get_attribute("value") == "light_car_and_truck":
                option.click()
                logger.info("Вибрано тип транспорту 'легкові авто і вантажівки'.")
                break
        time.sleep(1)

        view_button = driver.find_element(By.XPATH, '//input[@type="submit" and @value="ПЕРЕГЛЯНУТИ"]')
        view_button.click()
        logger.info("Натиснуто кнопку ПЕРЕГЛЯНУТИ.")
        time.sleep(3)

        while True:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

            new_matches = []

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if not cols:
                    continue
                plate = cols[0].text.strip()

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
                logger.info("Нових цікавих номерів не знайдено на цій сторінці.")

            try:
                next_button = driver.find_element(By.XPATH, '//a[contains(text(), "Наступна")]')
                classes = next_button.get_attribute("class")
                if 'disabled' in classes:
                    logger.info("Наступна сторінка недоступна, завершуємо перевірку.")
                    break
                else:
                    next_button.click()
                    logger.info("Переходимо на наступну сторінку...")
                    time.sleep(3)
            except Exception as e:
                logger.info(f"Кнопка 'Наступна' не знайдена або помилка: {e}, завершуємо перевірку.")
                break

    except Exception as e:
        logger.error(f"🔴 Сталася помилка в check_site: {e}")
    finally:
        try:
            bot.send_message(CHAT_ID, "✅ Перевірку завершено. Чекаємо 5 хв і починаємо знову.")
        except Exception as e:
            logger.error(f"Помилка надсилання завершального повідомлення: {e}")
        driver.quit()

if __name__ == "__main__":
    logger.info("Бот запущено. Очікуємо нових номерів...")

    try:
        bot.send_message(CHAT_ID, "🔧 Тестове повідомлення від бота!")
        logger.info("Тестове повідомлення надіслано успішно.")
    except Exception as e:
        logger.error(f"Помилка надсилання тестового повідомлення: {e}")

    while True:
        try:
            logger.info("Запуск перевірки сайту.")
            check_site()
        except Exception as e:
            logger.error(f"Помилка у головному циклі: {e}")
        logger.info("Чекаємо 5 хвилин перед наступною перевіркою...")
        time.sleep(300)
