import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from flask import Flask, jsonify
import re

app = Flask(__name__)

# Setup Chrome options
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--log-level=3")
options.add_experimental_option("excludeSwitches", ["enable-logging"])

def format_name_from_url(url):
    """Extracts and formats the show name from the URL."""
    match = re.search(r'shows/([^/]+)/', url)
    if match:
        slug = match.group(1)
        return ' '.join(word.capitalize() for word in slug.split('-'))
    return None

def scrape_episode_data(url):
    try:
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 15)
        driver.get(url)

        # Wait for episode cards container to appear
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '[data-testid="episode-card"]')))

        # Scroll to trigger lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # Get the first episode card
        episodes = driver.find_elements(By.CSS_SELECTOR, '[data-testid="episode-card"]')
        if not episodes:
            driver.quit()
            raise Exception(f"No episodes found for URL: {url}")
        first = episodes[0]

        # Title
        title = first.find_element(By.TAG_NAME, "h3").text

        # Description
        description_element = first.find_element(By.CSS_SELECTOR, "p[class*='ON_IMAGE_ALT2']")
        description = driver.execute_script("return arguments[0].textContent;", description_element).strip()

        # Date
        date_container = first.find_element(By.CSS_SELECTOR, "div.LABEL_CAPTION2_MEDIUM")
        date_spans = date_container.find_elements(By.CSS_SELECTOR, "span.ON_IMAGE.LABEL_CAPTION1_SEMIBOLD")
        date_text = driver.execute_script("return arguments[0].textContent;", date_spans[1]).strip()

        driver.quit()
        show_name = format_name_from_url(url)
        return {
            "title": title,
            "description": description,
            "date": date_text,
            "name": show_name
        }

    except Exception as e:
        if 'driver' in locals():
            driver.quit()
        show_name = format_name_from_url(url)
        return {"error": str(e), "name": show_name}

@app.route('/scrape')
def serve_multiple_data():
    urls = [
        "https://www.hotstar.com/in/shows/pandian-stores-2/1260000603",
        "https://www.hotstar.com/in/shows/ayyanar-thunai/1271388570",
        "https://www.hotstar.com/in/shows/baakiyalakshmi/1260022970"
    ]
    results = []
    for url in urls:
        results.append(scrape_episode_data(url))
    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)