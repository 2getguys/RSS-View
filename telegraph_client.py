from telegraph import Telegraph
from config import TELEGRAPH_ACCESS_TOKEN
from typing import Optional
import re

# Initialize the Telegraph client
telegraph = Telegraph(access_token=TELEGRAPH_ACCESS_TOKEN)

def clean_html_for_telegraph(html_content: str) -> str:
    """
    Cleans HTML content to be compatible with Telegraph.
    Telegraph only supports: p, br, strong, em, u, s, code, pre, blockquote, h3, h4, img, a
    """
    # Remove document structure tags (html, head, body, etc.)
    html_content = re.sub(r'</?html[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?head[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?body[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?doctype[^>]*>', '', html_content, flags=re.IGNORECASE)
    
    # Convert h1 and h2 to h3 (Telegraph doesn't support h1, h2)
    html_content = re.sub(r'<h[12]([^>]*)>', r'<h3\1>', html_content)
    html_content = re.sub(r'</h[12]>', r'</h3>', html_content)
    
    # Convert h5, h6 to h4
    html_content = re.sub(r'<h[56]([^>]*)>', r'<h4\1>', html_content)
    html_content = re.sub(r'</h[56]>', r'</h4>', html_content)
    
    # Remove any other unsupported tags but keep their content
    unsupported_tags = ['div', 'span', 'section', 'article', 'header', 'footer', 'nav', 'aside', 'main', 'figure', 'figcaption']
    for tag in unsupported_tags:
        html_content = re.sub(f'<{tag}[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(f'</{tag}>', '', html_content, flags=re.IGNORECASE)
    
    # Remove attributes from supported tags (Telegraph doesn't like attributes)
    html_content = re.sub(r'<(p|h3|h4|strong|em|u|s|code|pre|blockquote|br)\s+[^>]*>', r'<\1>', html_content, flags=re.IGNORECASE)
    
    # Clean img tags - keep only src attribute
    html_content = re.sub(r'<img[^>]*src="([^"]*)"[^>]*>', r'<img src="\1">', html_content, flags=re.IGNORECASE)
    
    # Remove empty paragraphs and extra whitespace
    html_content = re.sub(r'<p>\s*</p>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<p>\s*&nbsp;\s*</p>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'\s+', ' ', html_content)  # Normalize whitespace
    html_content = re.sub(r'\n\s*\n', '\n', html_content)  # Remove extra newlines
    
    return html_content.strip()

def create_telegraph_page(title: str, content_html: str) -> Optional[str]:
    """
    Creates a new page on Telegraph.

    Args:
        title: The title of the page.
        content_html: The HTML content of the page.

    Returns:
        The URL of the created page, or None if creation fails.
    """
    try:
        # Clean HTML content for Telegraph compatibility
        cleaned_html = clean_html_for_telegraph(content_html)
        print(f"📄 Creating Telegraph page with {len(cleaned_html)} chars of cleaned HTML")
        
        # You can optionally specify an author_name and author_url
        response = telegraph.create_page(
            title=title,
            html_content=cleaned_html,
            author_name="журналіст" # You can customize this
        )
        return response['url']
    except Exception as e:
        print(f"Error creating Telegraph page: {e}")
        return None
