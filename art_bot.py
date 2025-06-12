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

# --- Завантажуємо збережені номери з файлу ---
def load_seen_plates():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

# --- Зберігаємо нові номери у файл ---
def save_seen_plates(plates):
    with open(SEEN_FILE, 'a', encoding='utf-8') as f:
        for plate in plates:
            f.write(plate + '\n')

seen_plates = load_seen_plates()

# --- Умова: чи є дві нулі або дві сімки і більше ---
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
    options.add_argument('--headless')  # Якщо хочеш бачити браузер — видали цей рядок
    driver = webdriver.Chrome(service=service, options=options)

    try:
        url = "https://opendata.hsc.gov.ua/check-leisure-license-plates/"
        driver.get(url)

        print("Крок 2: Очікування випадаючого списку 'Область'")
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'select[name="region"]'))
        )
        oblast_select = driver.find_element(By.CSS_SELECTOR, 'select[name="region"]')
        for option in oblast_select.find_elements(By.TAG_NAME, "option"):
            if option.text.strip() == "Львівська":
                option.click()
                print("Обрана область: Львівська")
                break

        time.sleep(1)

        # Вибір ТСЦ "Весь регіон"
        tsc_select = driver.find_element(By.CSS_SELECTOR, 'select[name="tsc"]')
        for option in tsc_select.find_elements(By.TAG_NAME, "option"):
            if option.text.strip() == "Весь регіон":
                option.click()
                print("Обрано ТСЦ: Весь регіон")
                break

        time.sleep(1)

        # Вибір типу транспорту: "Легковий, вантажний"
        type_select = driver.find_element(By.CSS_SELECTOR, 'select[name="type_venichle"]')
        for option in type_select.find_elements(By.TAG_NAME, "option"):
            if option.get_attribute("value") == "light_car_and_truck":
                option.click()
                print("Обрано тип транспорту: Легковий, вантажний")
                break

        time.sleep(1)

        # Натискаємо кнопку "ПЕРЕГЛЯНУТИ"
        view_button = driver.find_element(By.XPATH, '//input[@type="submit" and @value="ПЕРЕГЛЯНУТИ"]')
        view_button.click()
        print("Натиснута кнопка ПЕРЕГЛЯНУТИ")

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
                print(f"Знайдений номер: {plate}")

                if plate not in seen_plates and is_interesting_plate(plate):
                    seen_plates.add(plate)
                    new_matches.append(plate)

            for plate in new_matches:
                bot.send_message(CHAT_ID, f"🆕 Знайдено цікавий номер: {plate}")

            if new_matches:
                save_seen_plates(new_matches)

            # Натискаємо кнопку "Наступна"
            try:
                next_button = driver.find_element(By.XPATH, '//a[contains(text(), "Наступна")]')
                classes = next_button.get_attribute("class")
                if 'disabled' in classes:
                    print("Остання сторінка, зупиняємося.")
                    break
                else:
                    next_button.click()
                    print("Натиснута кнопка Наступна")
                    time.sleep(3)
            except Exception as e:
                print(f"Не вдалося знайти або клікнути кнопку 'Наступна': {e}")
                break

    except Exception as e:
        print(f"🔴 Сталася помилка в check_site: {e}")
        raise
    finally:
        bot.send_message(CHAT_ID, "✅ Перевірку завершено. Чекаємо 5 хв і починаємо знову.")
        driver.quit()
        print("Браузер закрито.")

if __name__ == "__main__":
    print("Бот запущено. Очікуємо нових номерів...")

    # Відправляємо тестове повідомлення
    try:
        bot.send_message(CHAT_ID, "🔧 Тестове повідомлення від бота!")
    except Exception as e:
        print(f"Помилка надсилання повідомлення: {e}")

    while True:
        try:
            check_site()
        except Exception as e:
            print(f"Помилка: {e}")
        time.sleep(300)  # Перевірка кожні 5 хвилин

