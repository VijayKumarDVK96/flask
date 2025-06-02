import json
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from flask import Flask, jsonify
import re
import tempfile
import shutil

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

def configure_chrome_options():
    """Configures Chrome options for headless browsing in cloud environment."""
    options = webdriver.ChromeOptions()
    
    # Essential options for cloud deployment
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--disable-javascript")
    options.add_argument("--disable-css")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36")
    
    # Memory optimization
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=4096")
    
    # Disable logging
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Create unique user data directory
    user_data_dir = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    
    return options, user_data_dir

def format_name_from_url(url):
    """Extracts and formats the show name from the URL."""
    try:
        match = re.search(r'shows/([^/]+)/', url)
        if match:
            slug = match.group(1)
            return ' '.join(word.capitalize() for word in slug.split('-'))
        return "Unknown Show"
    except Exception as e:
        logging.error(f"Error formatting name from URL {url}: {str(e)}")
        return "Unknown Show"

def scrape_episode_data(url):
    driver = None
    user_data_dir = None
    
    try:
        logging.info(f"Scraping URL: {url}")
        
        # Configure Chrome options
        options, user_data_dir = configure_chrome_options()
        logging.info(f"User data directory: {user_data_dir}")
        
        # Initialize driver with service
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        # Create wait object
        wait = WebDriverWait(driver, 20)
        
        # Navigate to URL
        driver.get(url)
        logging.info(f"Page loaded for: {url}")
        
        # Wait for episode cards container to appear
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="episode-card"]')))
            logging.info("Episode cards found")
        except Exception as e:
            logging.error(f"Episode cards not found: {str(e)}")
            raise Exception("Episode cards not found on page")
        
        # Scroll to trigger lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)  # Increased wait time
        
        # Get episode cards
        episodes = driver.find_elements(By.CSS_SELECTOR, '[data-testid="episode-card"]')
        
        if not episodes:
            raise Exception("No episodes found after page load")
        
        first_episode = episodes[0]
        logging.info(f"Found {len(episodes)} episodes, processing first one")
        
        # Extract title
        try:
            title_element = first_episode.find_element(By.TAG_NAME, "h3")
            title = title_element.text.strip()
        except Exception as e:
            logging.error(f"Error extracting title: {str(e)}")
            title = "Title not found"
        
        # Extract description
        try:
            description_element = first_episode.find_element(By.CSS_SELECTOR, "p[class*='ON_IMAGE_ALT2']")
            description = driver.execute_script("return arguments[0].textContent;", description_element).strip()
        except Exception as e:
            logging.error(f"Error extracting description: {str(e)}")
            description = "Description not available"
        
        # Extract date
        try:
            date_container = first_episode.find_element(By.CSS_SELECTOR, "div.LABEL_CAPTION2_MEDIUM")
            date_spans = date_container.find_elements(By.CSS_SELECTOR, "span.ON_IMAGE.LABEL_CAPTION1_SEMIBOLD")
            if len(date_spans) > 1:
                date_text = driver.execute_script("return arguments[0].textContent;", date_spans[1]).strip()
            else:
                date_text = "Date not available"
        except Exception as e:
            logging.error(f"Error extracting date: {str(e)}")
            date_text = "Date not available"
        
        # Format show name
        show_name = format_name_from_url(url)
        
        result = {
            "title": title,
            "description": description,
            "date": date_text,
            "name": show_name,
            "status": "success"
        }
        
        logging.info(f"Successfully scraped data for: {show_name}")
        return result
        
    except Exception as e:
        error_msg = str(e)
        show_name = format_name_from_url(url)
        logging.error(f"Error scraping {url}: {error_msg}")
        
        return {
            "error": error_msg,
            "name": show_name,
            "status": "error",
            "title": "Error occurred",
            "description": "Could not fetch episode data",
            "date": "N/A"
        }
    
    finally:
        # Clean up resources
        if driver:
            try:
                driver.quit()
                logging.info("Driver closed successfully")
            except Exception as e:
                logging.error(f"Error closing driver: {str(e)}")
        
        if user_data_dir and os.path.exists(user_data_dir):
            try:
                shutil.rmtree(user_data_dir, ignore_errors=True)
                logging.info("Temp directory cleaned up")
            except Exception as e:
                logging.error(f"Error cleaning up temp directory: {str(e)}")

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "message": "Hotstar scraper API is running",
        "endpoints": ["/scrape"]
    })

@app.route('/scrape')
def serve_multiple_data():
    """Main endpoint to scrape multiple Hotstar shows"""
    urls = [
        "https://www.hotstar.com/in/shows/pandian-stores-2/1260000603",
        "https://www.hotstar.com/in/shows/ayyanar-thunai/1271388570",
        "https://www.hotstar.com/in/shows/baakiyalakshmi/1260022970"
    ]
    
    results = []
    
    for i, url in enumerate(urls, 1):
        logging.info(f"Processing URL {i}/{len(urls)}: {url}")
        try:
            result = scrape_episode_data(url)
            results.append(result)
            # Add delay between requests to avoid being blocked
            if i < len(urls):
                time.sleep(2)
        except Exception as e:
            logging.error(f"Failed to process URL {url}: {str(e)}")
            results.append({
                "error": f"Failed to process: {str(e)}",
                "name": format_name_from_url(url),
                "status": "error",
                "title": "Processing failed",
                "description": "Could not process this URL",
                "date": "N/A"
            })
    
    # Return results with summary
    response = {
        "results": results,
        "summary": {
            "total_requested": len(urls),
            "successful": len([r for r in results if r.get("status") == "success"]),
            "failed": len([r for r in results if r.get("status") == "error"])
        }
    }
    
    return jsonify(response)

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logging.error(f"Internal server error: {str(error)}")
    return jsonify({
        "error": "Internal server error",
        "message": "Something went wrong on the server",
        "status": "error"
    }), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "error": "Endpoint not found",
        "message": "The requested endpoint does not exist",
        "status": "error"
    }), 404

if __name__ == '__main__':
    # For development
    app.run(host='0.0.0.0', port=5000, debug=True)