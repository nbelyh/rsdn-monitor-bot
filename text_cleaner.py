"""
Text cleaning utilities for RSDN message content.
Removes greeting patterns, quotes, and HTML tags.
"""
import re
import html


def clean_message_text(text: str, max_length: int = 200) -> str:
    """
    Clean message text by removing HTML, quotes, and greetings.
    
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
    
    # Filter lines: skip greetings and quotes
    lines = [line.strip() for line in text.split('\n')]
    clean_lines = []
    
    skip_next = False
    for line in lines:
        if skip_next:
            skip_next = False
            continue
        
        # Skip greeting + next line (usually a quote)
        if 'Здравствуйте,' in line and 'писали:' in line:
            skip_next = True
            continue
        
        # Keep lines that are: long enough, not quotes, not greetings
        if (len(line) > 10 and 
            not line.startswith('>') and
            not re.match(r'^\w+>', line) and
            'писали:' not in line):
            clean_lines.append(line)
    
    # Join and cleanup
    text = ' '.join(clean_lines) if clean_lines else text
    text = ' '.join(text.split())  # Remove extra whitespace
    text = re.sub(r'Здравствуйте,\s+\w+,\s+Вы\s+писали:', '', text).strip()
    
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
