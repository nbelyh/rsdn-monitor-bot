"""
Text cleaning utilities for RSDN message content.
Removes greeting patterns, quotes, and HTML tags.
"""
import re
import html


def clean_message_text(text: str, max_length: int = 200) -> str:
    """
    Clean message text by removing HTML, quotes, and greetings.
    
    Strategy: Skip all quote blocks at the beginning, then take the first real content.
    
    Args:
        text: Raw message text (may contain HTML)
        max_length: Maximum length (default: 200)
        
    Returns:
        Cleaned text, truncated to max_length
    """
    if not text:
        return ""
    
    # Remove HTML tags and decode entities
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    
    # Split into lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Find where actual content starts (skip all quotes/greetings at the beginning)
    content_start_idx = None
    for i, line in enumerate(lines):
        # Skip if it's a greeting or quote marker
        is_quote = (line.startswith('>') or 
                   re.match(r'^[\w.]+>>', line) or  # Match wl.>> style (with dot)
                   re.match(r'^[\w.]+>', line) or   # Match O>, M>, wl.> style
                   'Здравствуйте,' in line or
                   'писали:' in line)
        
        # Found first line that's actual content
        if not is_quote and len(line) > 10:
            content_start_idx = i
            break
    
    # If we found content, take from there to end
    if content_start_idx is not None:
        clean_lines = lines[content_start_idx:]
    else:
        # No content found, return empty
        return ""
    
    # Join and cleanup
    text = ' '.join(clean_lines)
    text = ' '.join(text.split())  # Remove extra whitespace
    
    # Truncate at word boundary
    if max_length and len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + "..."
    
    return text


def clean_html_element(element, max_length: int = 200) -> str:
    """
    Extract and clean text from BeautifulSoup element.
    Skips quote blocks and greetings.
    """
    if not element:
        return ""
    
    text_parts = []
    
    # Get text nodes, skip quote blocks
    for child in element.descendants:
        if hasattr(child, 'name') and child.name in ['div', 'span']:
            classes = ' '.join(child.get('class', []))
            if 'quote' in classes.lower():
                continue
        
        if hasattr(child, 'string') and child.string:
            text = child.string.strip()
            if (len(text) > 5 and 
                not text.startswith('Здравствуйте,') and
                not text.startswith('>') and
                'писали:' not in text):
                text_parts.append(text)
    
    if text_parts:
        content = ' '.join(text_parts)
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'Здравствуйте,\s+\w+,\s+Вы\s+писали:', '', content).strip()
    else:
        # Fallback: use full text
        content = clean_message_text(element.get_text(strip=True), max_length=None)
    
    # Truncate
    if max_length and len(content) > max_length:
        content = content[:max_length].rsplit(' ', 1)[0] + "..."
    
    return content
