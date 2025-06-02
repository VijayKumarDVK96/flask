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

def extract_hotstar_api_data(url):
    """Try to find Hotstar's internal API endpoints and extract data"""
    try:
        logging.info(f"Attempting to extract API data for: {url}")
        
        # Headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        # Get the main page first
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse HTML to look for data
        soup = BeautifulSoup(response.content, 'html.parser')
        show_name = format_name_from_url(url)
        
        # Strategy 1: Look for JSON-LD structured data
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                logging.info(f"Found JSON-LD data: {json.dumps(data, indent=2)[:200]}...")
                
                if isinstance(data, dict):
                    title = data.get('name') or data.get('title')
                    description = data.get('description')
                    date = data.get('datePublished') or data.get('uploadDate')
                    
                    if title or description:
                        return {
                            "title": title or "Title not available",
                            "description": description or "Description not available",
                            "date": date or "Date not available",
                            "name": show_name,
                            "status": "success",
                            "source": "JSON-LD"
                        }
            except (json.JSONDecodeError, AttributeError) as e:
                logging.error(f"Error parsing JSON-LD: {e}")
                continue
        
        # Strategy 2: Look for inline JavaScript with show data
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                script_content = script.string
                
                # Look for common patterns in JavaScript data
                patterns = [
                    r'"title"\s*:\s*"([^"]+)"',
                    r'"name"\s*:\s*"([^"]+)"',
                    r'"description"\s*:\s*"([^"]+)"',
                    r'"synopsis"\s*:\s*"([^"]+)"',
                    r'"releaseDate"\s*:\s*"([^"]+)"',
                    r'"publishedTime"\s*:\s*"([^"]+)"'
                ]
                
                extracted_data = {}
                for pattern in patterns:
                    matches = re.findall(pattern, script_content, re.IGNORECASE)
                    if matches:
                        field_name = pattern.split('"')[1]
                        extracted_data[field_name] = matches[0]
                
                if extracted_data:
                    return {
                        "title": extracted_data.get('title') or extracted_data.get('name') or "Title found in JS",
                        "description": extracted_data.get('description') or extracted_data.get('synopsis') or "Description found in JS",
                        "date": extracted_data.get('releaseDate') or extracted_data.get('publishedTime') or "Date found in JS",
                        "name": show_name,
                        "status": "success",
                        "source": "JavaScript extraction",
                        "extracted_fields": list(extracted_data.keys())
                    }
        
        # Strategy 3: Enhanced meta tag extraction
        meta_data = {}
        
        # Common meta tags
        meta_tags = [
            ('og:title', 'title'),
            ('og:description', 'description'),
            ('twitter:title', 'title'),
            ('twitter:description', 'description'),
            ('description', 'description'),
            ('og:updated_time', 'date'),
            ('article:published_time', 'date')
        ]
        
        for meta_name, field in meta_tags:
            meta = soup.find('meta', attrs={'property': meta_name}) or soup.find('meta', attrs={'name': meta_name})
            if meta and meta.get('content'):
                if field not in meta_data:  # Only use first occurrence
                    meta_data[field] = meta['content']
        
        # Also check title tag
        title_tag = soup.find('title')
        if title_tag and not meta_data.get('title'):
            meta_data['title'] = title_tag.get_text().strip()
        
        if meta_data:
            return {
                "title": meta_data.get('title', 'Title not available'),
                "description": meta_data.get('description', 'Description not available'),
                "date": meta_data.get('date', 'Date not available'),
                "name": show_name,
                "status": "success",
                "source": "Meta tags",
                "found_meta": list(meta_data.keys())
            }
        
        # Strategy 4: Try to find content ID and make direct API call
        content_id_match = re.search(r'/(\d+)/?$', url)
        if content_id_match:
            content_id = content_id_match.group(1)
            logging.info(f"Found content ID: {content_id}")
            
            # Try common Hotstar API endpoints
            api_urls = [
                f"https://api.hotstar.com/o/v1/show/detail?contentId={content_id}",
                f"https://api.hotstar.com/h/v2/show/{content_id}",
                f"https://api.hotstar.com/o/v1/content/{content_id}"
            ]
            
            for api_url in api_urls:
                try:
                    api_response = session.get(api_url, timeout=10)
                    if api_response.status_code == 200:
                        api_data = api_response.json()
                        logging.info(f"API response: {json.dumps(api_data, indent=2)[:300]}...")
                        
                        # Try to extract data from API response
                        if 'body' in api_data and 'results' in api_data['body']:
                            result = api_data['body']['results']
                            return {
                                "title": result.get('title') or result.get('name') or "API Title",
                                "description": result.get('description') or result.get('synopsis') or "API Description",
                                "date": result.get('releaseDate') or result.get('publishedTime') or "API Date",
                                "name": show_name,
                                "status": "success",
                                "source": f"Hotstar API ({api_url})"
                            }
                except Exception as e:
                    logging.error(f"API call failed for {api_url}: {e}")
                    continue
        
        # If all strategies fail, return what we have
        return {
            "title": "Unable to extract title",
            "description": "Unable to extract description - content may be loaded dynamically",
            "date": "Unable to extract date",
            "name": show_name,
            "status": "limited_data",
            "source": "Fallback",
            "note": "All extraction strategies failed - may need browser automation"
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
        "message": "Enhanced Hotstar scraper API",
        "endpoints": ["/scrape", "/scrape/<path:show_url>"],
        "strategies": [
            "JSON-LD structured data",
            "JavaScript content extraction", 
            "Enhanced meta tag parsing",
            "Direct API endpoint attempts"
        ]
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
            result = extract_hotstar_api_data(url)
            results.append(result)
            # Add delay between requests
            if i < len(urls):
                time.sleep(2)  # Increased delay to be respectful
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
            "limited_data": len([r for r in results if r.get("status") == "limited_data"]),
            "failed": len([r for r in results if r.get("status") == "error"])
        },
        "method": "Enhanced extraction with multiple strategies"
    }
    
    return jsonify(response)

@app.route('/test-single/<path:show_url>')
def test_single_url(show_url):
    """Test endpoint for a single URL"""
    if not show_url.startswith('http'):
        show_url = 'https://' + show_url
    
    result = extract_hotstar_api_data(show_url)
    return jsonify({
        "url": show_url,
        "result": result
    })

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