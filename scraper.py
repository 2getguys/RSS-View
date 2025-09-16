import requests
import trafilatura
from bs4 import BeautifulSoup
from typing import Dict, Optional
import re

def scrape_article_content(url: str) -> Optional[Dict[str, str]]:
    """
    Scrapes the main content from a given article URL.
    Uses custom BeautifulSoup scraper first, falls back to trafilatura if needed.
    """
    try:
        # Fetch the webpage
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        raw_html = response.text
        
        print(f"📄 Fetched {len(raw_html)} chars of HTML from {url}")
        
        # Try our custom scraper first (it worked better!)
        result = scrape_with_beautifulsoup(raw_html, url)
        if result:
            print(f"✅ Custom scraper extracted content successfully")
            result['raw_html'] = raw_html
            return result
        
        # Fallback to trafilatura
        print("⚠️ Custom scraper failed, trying trafilatura...")
        result = scrape_with_trafilatura(raw_html, url)
        if result:
            print(f"✅ Trafilatura extracted content successfully")
            result['raw_html'] = raw_html
            return result
        
        print(f"❌ Both scrapers failed to extract content from {url}")
        return None
        
    except requests.RequestException as e:
        print(f"❌ Error fetching URL {url}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error processing content from {url}: {e}")
        return None

def scrape_with_beautifulsoup(raw_html: str, url: str) -> Optional[Dict[str, str]]:
    """
    Our original BeautifulSoup scraper that worked well.
    """
    try:
        soup = BeautifulSoup(raw_html, 'html.parser')

        # --- Title Extraction ---
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "No Title Found"
        # Clean title from punctuation
        title = title.rstrip('.,;:!?-–—').strip()

        # --- Content Container Identification ---
        article_body = (
            soup.find('article') or
            soup.find('div', class_='post-content') or
            soup.find('div', id='article-body') or
            soup.find('div', class_='article-body') or
            soup.find('div', class_='entry-content') or
            soup.find('div', class_='td-post-content') or
            soup.find('main')
        )

        if not article_body:
            print(f"Could not find a suitable article container on {url}, using <body> as fallback.")
            article_body = soup.find('body')
            if not article_body:
                return None

        # --- Pre-cleaning of the article body ---
        for element in article_body(['script', 'style', 'nav', 'footer', 'aside', 'form', 'iframe', 'header']):
            element.decompose()
        
        promotional_selectors = [
            '[class*="social"]', '[class*="share"]', '[class*="button"]', '[class*="ad"]', '[class*="promo"]',
            '[class*="sidebar"]', '[class*="comment"]', '[class*="related"]', '[class*="subscribe"]'
        ]
        for selector in promotional_selectors:
            for element in article_body.select(selector):
                element.decompose()

        # --- Rebuild content HTML, preserving order ---
        content_html = ""
        short_description = ""
        seen_images = set()
        main_image_url = None

        # Process all relevant tags in their document order
        for element in article_body.find_all(['p', 'h1', 'h2', 'h3', 'img', 'figure']):
            if element.name in ['p', 'h1', 'h2', 'h3']:
                text = element.get_text(strip=True)
                if not text or (len(text) < 20 and element.name == 'p'):
                    continue

                if element.name == 'p' and not short_description:
                    desc = text[:300] if len(text) > 300 else text
                    # Clean punctuation from end
                    desc = desc.rstrip('.,;:!?-–—').strip()
                    short_description = desc + ('...' if len(text) > 300 else '')

                content_html += f"<{element.name}>{text}</{element.name}>\n\n"

            elif element.name in ['img', 'figure']:
                img_tag = element if element.name == 'img' else element.find('img')
                if not img_tag:
                    continue

                img_src = img_tag.get('src') or img_tag.get('data-src') or ''
                
                if not img_src or not img_src.startswith('http') or img_src in seen_images:
                    continue
                
                if any(skip in img_src.lower() for skip in ['logo', 'avatar', 'icon', 'spinner', '.gif', 'data:image']):
                    continue

                content_html += f'<img src="{img_src}">\n\n'
                seen_images.add(img_src)
                if not main_image_url:
                    main_image_url = img_src

        if not content_html.strip():
            return None
            
        return {
            'title': title,
            'content_html': content_html,
            'image_url': main_image_url,
            'short_description': short_description
        }
        
    except Exception as e:
        print(f"BeautifulSoup scraper error: {e}")
        return None

def scrape_with_trafilatura(raw_html: str, url: str) -> Optional[Dict[str, str]]:
    """
    Trafilatura scraper as fallback.
    """
    try:
        # Extract metadata first
        metadata = trafilatura.extract_metadata(raw_html)
        
        # Extract main content as HTML
        content_html = trafilatura.extract(
            raw_html,
            output_format='html',
            include_images=True,
            include_links=False,
            include_tables=True,
            include_formatting=True,
            favor_precision=False,
            favor_recall=True,
            deduplicate=True,
            target_language='en'
        )
        
        if not content_html:
            return None
        
        # Get title from metadata
        title = "No Title Found"
        if metadata and metadata.title:
            title = metadata.title.strip()
        
        # Clean title from punctuation
        title = title.rstrip('.,;:!?-–—').strip()
        
        # Clean HTML for Telegraph
        cleaned_html = clean_trafilatura_html(content_html)
        
        # Extract short description and main image
        short_description = extract_short_description_from_html(cleaned_html)
        main_image_url = extract_main_image_from_html(cleaned_html)
        
        return {
            'title': title,
            'content_html': cleaned_html,
            'image_url': main_image_url,
            'short_description': short_description
        }
        
    except Exception as e:
        print(f"Trafilatura scraper error: {e}")
        return None

def clean_trafilatura_html(html_content: str) -> str:
    """Clean trafilatura HTML output."""
    if not html_content:
        return ""
    
    # Remove document structure tags
    html_content = re.sub(r'</?html[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?head[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?body[^>]*>', '', html_content, flags=re.IGNORECASE)
    
    # Convert headers to Telegraph format
    html_content = re.sub(r'<h[12]([^>]*)>', r'<h3\1>', html_content)
    html_content = re.sub(r'</h[12]>', r'</h3>', html_content)
    html_content = re.sub(r'<h[56]([^>]*)>', r'<h4\1>', html_content)
    html_content = re.sub(r'</h[56]>', r'</h4>', html_content)
    
    # Clean up
    html_content = re.sub(r'<p>\s*</p>', '', html_content)
    html_content = html_content.strip()
    
    return html_content

def extract_short_description_from_html(content_html: str) -> str:
    """Extract short description from HTML."""
    p_matches = re.findall(r'<p>([^<]+)</p>', content_html)
    for p_text in p_matches:
        if len(p_text.strip()) > 50:
            desc = p_text.strip()[:300]
            desc = desc.rstrip('.,;:!?-–—').strip()
            return desc + ('...' if len(p_text) > 300 else '')
    return ""

def extract_main_image_from_html(content_html: str) -> Optional[str]:
    """Extract main image from HTML."""
    img_match = re.search(r'<img src="([^"]+)"', content_html)
    if img_match:
        img_url = img_match.group(1)
        if not any(skip in img_url.lower() for skip in ['logo', 'avatar', 'icon', 'spinner', '.gif']):
            return img_url
    return None