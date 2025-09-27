#!/usr/bin/env python3
"""
Debug script to examine RSDN HTML structure
"""

import requests
from bs4 import BeautifulSoup
import sys

def analyze_rsdn_structure():
    """Analyze the HTML structure of RSDN forum"""
    print("🔍 Analyzing RSDN HTML structure...")
    
    try:
        # Get the page
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        response = session.get("https://rsdn.org/forum/", timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all tables
        tables = soup.find_all('table')
        print(f"📊 Found {len(tables)} tables")
        
        for i, table in enumerate(tables):
            rows = table.find_all('tr')
            print(f"\nTable {i+1}: {len(rows)} rows")
            
            # Check first few rows
            for j, row in enumerate(rows[:5]):
                cells = row.find_all(['td', 'th'])
                if cells:
                    cell_texts = [cell.get_text().strip()[:50] for cell in cells]
                    print(f"  Row {j+1}: {len(cells)} cells - {cell_texts}")
                    
                    # Look for time patterns
                    for k, cell in enumerate(cells):
                        text = cell.get_text().strip()
                        if any(time_word in text.lower() for time_word in ['мин', 'час', 'дн']):
                            print(f"    ⏰ Found time pattern in cell {k+1}: '{text}'")
                        
                        # Look for forum names
                        if any(forum in text.lower() for forum in ['life', 'network', 'flame', 'abroad', 'humour']):
                            print(f"    📂 Found forum name in cell {k+1}: '{text}'")
                        
                        # Look for links (topics)
                        links = cell.find_all('a')
                        if links:
                            for link in links:
                                href = link.get('href', '')
                                if '/forum/' in href and '/message/' in href:
                                    print(f"    🔗 Found topic link in cell {k+1}: '{link.get_text().strip()[:30]}...' -> {href}")
        
        # Look for div containers that might hold the forum content
        print(f"\n🔍 Looking for div containers...")
        divs = soup.find_all('div')
        print(f"Found {len(divs)} div elements")
        
        # Look for any elements that might contain the forum data
        print(f"\n🎯 Looking for forum message patterns in all elements...")
        
        # Try to find elements containing time patterns
        time_elements = []
        for element in soup.find_all(text=True):
            text = element.strip()
            if text and any(time_word in text for time_word in ['мин', 'час', 'дн']):
                time_elements.append((element.parent.name if element.parent else 'unknown', text))
        
        print(f"Found {len(time_elements)} elements with time patterns:")
        for tag, text in time_elements[:10]:  # Show first 10
            print(f"  ⏰ <{tag}>: {text}")
        
        # Look for forum names
        forum_elements = []
        for element in soup.find_all(text=True):
            text = element.strip()
            if text and any(forum in text for forum in ['life', 'network', 'flame', 'abroad', 'humour']):
                forum_elements.append((element.parent.name if element.parent else 'unknown', text))
        
        print(f"\nFound {len(forum_elements)} elements with forum names:")
        for tag, text in forum_elements[:10]:  # Show first 10
            print(f"  📂 <{tag}>: {text}")
        
        # Check if it's using CSS grid, flexbox, or divs instead of tables
        print(f"\n🎨 Checking for CSS-based layouts...")
        
        # Look for CSS classes that might indicate forum structure
        all_classes = set()
        for element in soup.find_all(class_=True):
            if isinstance(element.get('class'), list):
                all_classes.update(element.get('class'))
            else:
                all_classes.add(element.get('class'))
        
        forum_related_classes = [cls for cls in all_classes if any(keyword in cls.lower() for keyword in ['forum', 'message', 'topic', 'post', 'row', 'list', 'item'])]
        print(f"Forum-related CSS classes: {forum_related_classes}")
        
        # Try to find the main content area
        main_content = soup.find('main') or soup.find('div', {'id': 'content'}) or soup.find('div', {'class': 'content'})
        if main_content:
            print(f"\n🎯 Found main content area: <{main_content.name}> with classes: {main_content.get('class')}")
            inner_structure = main_content.find_all(['table', 'div', 'ul', 'ol'])[:5]
            for elem in inner_structure:
                print(f"  Contains: <{elem.name}> with classes: {elem.get('class')}")
        
        # Look for script tags that might load content dynamically
        scripts = soup.find_all('script', src=True)
        print(f"\n📜 Found {len(scripts)} external scripts (content might be loaded dynamically)")
        
        # Check if content is in plain text format (maybe it's not HTML table based)
        print(f"\n📄 Checking for plain text forum structure...")
        
        # Get all text and look for the pattern we saw in the webpage fetch
        all_text = soup.get_text()
        
        # Look for the specific pattern: time | forum | title | author | replies | last_author
        import re
        
        # Pattern for forum messages: starts with time, has | separators
        pattern = r'(\d+\s*(мин|час|дн).*?)\s*\|\s*(\w+.*?)\s*\|\s*(.*?)\s*\|\s*(\w+.*?)\s*\|\s*(\d+)\s*\|\s*(\w+.*?)\s*\|'
        matches = re.findall(pattern, all_text, re.MULTILINE)
        
        print(f"Found {len(matches)} potential forum message matches:")
        for match in matches[:5]:
            print(f"  📝 {match}")
        
        # Save the HTML for manual inspection
        with open('rsdn_debug.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"\n💾 Saved full HTML to 'rsdn_debug.html' for manual inspection")
        
        # Save the raw text for analysis
        with open('rsdn_debug.txt', 'w', encoding='utf-8') as f:
            f.write(all_text)
        print(f"💾 Saved full text content to 'rsdn_debug.txt'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error analyzing RSDN structure: {e}")
        return False

if __name__ == "__main__":
    analyze_rsdn_structure()