import requests
from bs4 import BeautifulSoup
import re

def extract_book_titles_with_authors(text, max_titles=5):
    """
    Extract book titles enclosed in 《》 from text, requiring Chinese names to appear before/after the title.
    :param text: Input text content
    :param max_titles: Maximum number of book titles to extract (default: 5)
    :return: List of extracted book titles
    """
    # Regex pattern to match book titles in 《》 with adjacent Chinese names (2-4 characters)
    pattern = r'([\u4e00-\u9fa5]{2,4})《([^《》]+)》|《([^《》]+)》([\u4e00-\u9fa5]{2,4})'
    
    # Find all matches
    matches = re.findall(pattern, text)
    
    # Extract unique book titles using set
    book_titles = set()
    for match in matches:
        if len(book_titles) >= max_titles:
            break  # Stop when maximum limit is reached
        if match[1]:  # Case: title follows a name
            book_titles.add(match[1])
        elif match[2]:  # Case: title precedes a name
            book_titles.add(match[2])
    
    return list(book_titles)[:max_titles]  # Ensure output doesn't exceed max_titles

def extract_books_from_url(url, max_titles=5):
    """
    Extract book titles from a given URL.
    :param url: Target webpage URL
    :param max_titles: Maximum number of titles to extract (default: 5)
    :return: List of extracted book titles
    """
    try:
        print(f"Accessing URL: {url}")  # Translated UI message
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()

        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract text content from webpage
        text = soup.get_text()

        # Extract book titles
        books = extract_book_titles_with_authors(text, max_titles)

        # Return non-empty results
        if not books:
            print("No relevant book titles found.")  
        return books

    except requests.RequestException as e:
        print(f"Request failed: {e}")  
        return []


# Main program
if __name__ == "__main__":
    # User inputs the URL
    url = input("Enter the target webpage URL: ")  

    # Extract book titles
    books = extract_books_from_url(url)

    if books:
        print("Extracted book titles:")  
        for i, book in enumerate(books, 1):
            print(f"{i}. {book}")
    else:
        print("No content extracted.")  