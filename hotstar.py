import json
import re
import logging
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
import time

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

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

def scrape_episode_data_requests(url):
    """Scrape episode data using requests and BeautifulSoup"""
    try:
        logging.info(f"Scraping URL with requests: {url}")
        
        # Headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        # Make request
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to find episode data (this might need adjustment based on actual HTML structure)
        # Since we can't see the dynamic content, we'll try different approaches
        
        # Look for JSON data in script tags (common pattern)
        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            try:
                data = json.loads(script.string)
                if 'name' in data and 'description' in data:
                    show_name = format_name_from_url(url)
                    return {
                        "title": data.get('name', 'Title not found'),
                        "description": data.get('description', 'Description not available'),
                        "date": data.get('datePublished', 'Date not available'),
                        "name": show_name,
                        "status": "success"
                    }
            except json.JSONDecodeError:
                continue
        
        # Look for meta tags
        title = soup.find('meta', property='og:title')
        description = soup.find('meta', property='og:description')
        
        show_name = format_name_from_url(url)
        
        return {
            "title": title['content'] if title else "Title not found",
            "description": description['content'] if description else "Description not available", 
            "date": "Date extraction not available with this method",
            "name": show_name,
            "status": "partial_success",
            "note": "Limited data available without JavaScript execution"
        }
        
    except requests.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        show_name = format_name_from_url(url)
        logging.error(f"Error scraping {url}: {error_msg}")
        
        return {
            "error": error_msg,
            "name": show_name,
            "status": "error",
            "title": "Request failed",
            "description": "Could not fetch page data",
            "date": "N/A"
        }
    
    except Exception as e:
        error_msg = str(e)
        show_name = format_name_from_url(url)
        logging.error(f"Error scraping {url}: {error_msg}")
        
        return {
            "error": error_msg,
            "name": show_name,
            "status": "error",
            "title": "Error occurred",
            "description": "Could not process page data",
            "date": "N/A"
        }

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "message": "Hotstar scraper API is running (Requests-based)",
        "endpoints": ["/scrape"],
        "note": "This version uses requests instead of Selenium for free tier compatibility"
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
            result = scrape_episode_data_requests(url)
            results.append(result)
            # Add delay between requests
            if i < len(urls):
                time.sleep(1)
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
            "successful": len([r for r in results if r.get("status") in ["success", "partial_success"]]),
            "failed": len([r for r in results if r.get("status") == "error"])
        },
        "method": "requests-based (free tier compatible)"
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
    app.run(host='0.0.0.0', port=5000, debug=True)