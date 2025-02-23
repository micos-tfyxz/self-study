import requests
from bs4 import BeautifulSoup
import re

def fetch_html_content(url):
    """Fetch HTML content from a URL."""
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()  # Check if the request succeeded
        return response.text
    except requests.RequestException as e:
        print(f"Failed to fetch webpage content: {e}")
        return None

def extract_text_from_html(html_content):
    """Extract plain text from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    # Extract all text content with line breaks between tags
    text = soup.get_text(separator='\n')
    return text

def extract_directory_from_text(text):
    """
    Extract directory items from text.
    :param text: Input text content
    :return: List of extracted directory items
    """
    # Regex pattern to match directory formats:
    # 1. Chinese "第X章/节" (Chapter/Section X)
    # 2. English "Chapter X", "Section X", "Part X", "Volume X", "Unit X", "Module X"
    # 3. Numeric prefixes (e.g., "1. Title" or "1: Title")
    # 4. Numeric prefix followed by space and title (e.g., "1 Title")
    pattern = re.compile(
        r'('
        r'第[零一二三四五六七八九十百千万0-9]+[章节]|'  # Chinese chapter/section
        r'Chapter\s*\d+|'  # English "Chapter X"
        r'Section\s*\d+|'  # English "Section X"
        r'Part\s*\d+|'  # English "Part X"
        r'Volume\s*\d+|'  # English "Volume X"
        r'Unit\s*\d+|'  # English "Unit X"
        r'Module\s*\d+|'  # English "Module X"
        r'\d+\s*[:：.]\s*|'  # Numeric prefixes (e.g., "1. Title" or "1: Title")
        r'\d+\s+'  # Numeric prefix + space + title (e.g., "1 Title")
        r')\s*[:：]?\s*(.*)',  # Capture title
        re.IGNORECASE
    )

    # Patterns to exclude
    exclude_patterns = [
        r'©\d{4}\s*\w+',  # Exclude copyright info (e.g., "©2025 Baidu")
        r'\d+\s*页',  # Exclude page numbers (e.g., "738 页")
        r'^\d+$',  # Exclude pure numbers
        r'^\d+\s*[^\w\s]+$',  # Exclude numbers with symbols (e.g., "1.", "2:")
    ]

    # Keywords to exclude (case-insensitive)
    exclude_keywords = ["appendices"]

    # Extract directory items
    directory_items = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Check exclusion patterns
        if any(re.search(pattern, line) for pattern in exclude_patterns):
            continue

        # Check exclusion keywords
        if any(keyword.lower() in line.lower() for keyword in exclude_keywords):
            continue

        # Match chapter/section titles
        match = pattern.search(line)
        if match:
            title = match.group(2).strip()
            if title:  # Ensure non-empty title
                directory_items.append(title)

    return directory_items

def main():
    # User input for URL
    url = input("Enter the target webpage URL: ")

    # Fetch HTML content
    html_content = fetch_html_content(url)
    if not html_content:
        return

    # Extract text
    text = extract_text_from_html(html_content)

    # Extract directory items
    directory = extract_directory_from_text(text)
    if directory:
        print("Extracted directory items:")
        for i, item in enumerate(directory, 1):
            print(f"{i}. {item}")
    else:
        print("No directory content extracted.")

if __name__ == "__main__":
    main()