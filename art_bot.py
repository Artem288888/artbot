# --- Додано для Render: Фейковий вебсервер ---
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def run_fake_web_server():
    import os
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running.")

    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()

threading.Thread(target=run_fake_web_server, daemon=True).start()
# --- Кінець вставки ---

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import telebot
import time
import os

# --- Твої дані ---
BOT_TOKEN = '7650951016:AAE1sBUl6Lq-Y9xwbjyyoDlcPhQsWyYpnR4'
CHAT_ID = '6854620915'

# --- Телеграм бот ---
bot = telebot.TeleBot(BOT_TOKEN)

# --- Файл для збереження побачених номерів ---
SEEN_FILE = 'seen_plates.txt'

def load_seen_plates():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_seen_plates(plates):
    with open(SEEN_FILE, 'a', encoding='utf-8') as f:
        for plate in plates:
            f.write(plate + '\n')

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
    print("Крок 1: Завантаження сайту")
    service = Service(r'C:\Users\Admin\Desktop\бот\chromedriver.exe')
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(service=service, options=options)

    try:
        url = "https://opendata.hsc.gov.ua/check-leisure-license-plates/"
        driver.get(url)

        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'select[name="region"]'))
        )
        oblast_select = driver.find_element(By.CSS_SELECTOR, 'select[name="region"]')
        for option in oblast_select.find_elements(By.TAG_NAME, "option"):
            if option.text.strip() == "Львівська":
                option.click()
                break

        time.sleep(1)

        tsc_select = driver.find_element(By.CSS_SELECTOR, 'select[name="tsc"]')
        for option in tsc_select.find_elements(By.TAG_NAME, "option"):
            if option.text.strip() == "Весь регіон":
                option.click()
                break

        time.sleep(1)

        type_select = driver.find_element(By.CSS_SELECTOR, 'select[name="type_venichle"]')
        for option in type_select.find_elements(By.TAG_NAME, "option"):
            if option.get_attribute("value") == "light_car_and_truck":
                option.click()
                break

        time.sleep(1)

        view_button = driver.find_element(By.XPATH, '//input[@type="submit" and @value="ПЕРЕГЛЯНУТИ"]')
        view_button.click()
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

            for plate in new_matches:
                bot.send_message(CHAT_ID, f"🆕 Знайдено цікавий номер: {plate}")

            if new_matches:
                save_seen_plates(new_matches)

            try:
                next_button = driver.find_element(By.XPATH, '//a[contains(text(), "Наступна")]')
                classes = next_button.get_attribute("class")
                if 'disabled' in classes:
                    break
                else:
                    next_button.click()
                    time.sleep(3)
            except Exception:
                break

    except Exception as e:
        print(f"🔴 Сталася помилка в check_site: {e}")
    finally:
        bot.send_message(CHAT_ID, "✅ Перевірку завершено. Чекаємо 5 хв і починаємо знову.")
        driver.quit()

if __name__ == "__main__":
    print("Бот запущено. Очікуємо нових номерів...")

    try:
        bot.send_message(CHAT_ID, "🔧 Тестове повідомлення від бота!")
    except Exception as e:
        print(f"Помилка надсилання повідомлення: {e}")

    while True:
        try:
            check_site()
        except Exception as e:
            print(f"Помилка: {e}")
        time.sleep(300)


