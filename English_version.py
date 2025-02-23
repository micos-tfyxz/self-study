import json
import openai
import requests
from bs4 import BeautifulSoup
import re
from serpapi import GoogleSearch
import os

# ----------------- OpenAI API Section -----------------
# Set OpenAI API Key
openai_client = openai.OpenAI(api_key="")

def expand_section_content(toc_text):
    """
    Call OpenAI API to expand book table of contents
    
    Parameters:
        toc_text (str): Text containing chapter titles (each line represents a chapter title, sorted order as final sequence)
    
    Returns:
        Expanded content from API (expected to be JSON-formatted string)
    """
    prompt = f"""
I have the following table of contents for a book:
{toc_text}

For each chapter title, generate a chapter description in English consisting of exactly two sentences. The first sentence should provide a supplementary explanation of the chapter title, and the second sentence should state the learning objectives for the chapter. Do not include any additional information.

Format the output as a JSON object with one key "sections". The value of "sections" is an array where each element is an object with the following keys:
- "section_number": a string in the format "chapter1", "chapter2", etc., corresponding to the sorted order.
- "description": the two-sentence chapter description.

Make sure the output is valid JSON and does not include any extra text.
"""
    response = openai_client.chat.completions.create(
        model="gpt-4o",  # Choose model based on actual needs
        messages=[
            {"role": "system", "content": "You are a professional academic writing assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=3000,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content.strip()

# ----------------- SERPAPI & Book TOC Extraction -----------------
SERPAPI_API_KEY = ""  # Replace with your SERPAPI API Key

def google_search(query, num_results=5):
    """
    Perform Google search using SerpAPI and return top num_results links
    """
    params = {
        "q": query,
        "hl": "zh-CN",    # Set language to Chinese
        "gl": "cn",       # Set region to China
        "num": num_results,
        "api_key": SERPAPI_API_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    urls = []
    if "organic_results" in results:
        for result in results["organic_results"][:num_results]:
            urls.append(result["link"])
    return urls

def fetch_html_content(url):
    """
    Fetch HTML content from the specified URL
    """
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Failed to fetch content: {e}")
        return None

def extract_text_from_html(html_content):
    """
    Extract plain text from HTML content
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator='\n')
    return text

def chinese_to_int(chinese_str):
    """
    Convert Chinese numerals to integer. Supports common forms like 十, 十一, 二十, 二十一, etc.
    """
    mapping = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    if chinese_str == "十":
        return 10
    if chinese_str.startswith("十"):
        return 10 + chinese_to_int(chinese_str[1:]) if len(chinese_str) > 1 else 10
    if "十" in chinese_str:
        parts = chinese_str.split("十")
        tens = mapping.get(parts[0], 1)  # Default to 1 if empty
        ones = chinese_to_int(parts[1]) if parts[1] else 0
        return tens * 10 + ones
    return mapping.get(chinese_str[0], 0)

def parse_chapter_number(prefix):
    """
    Attempt to parse chapter number from prefix. Prioritizes Arabic numerals, then Chinese numerals.
    """
    m = re.search(r'\d+', prefix)
    if m:
        try:
            return int(m.group())
        except:
            pass
    m_cn = re.search(r'[零一二三四五六七八九十]+', prefix)
    if m_cn:
        try:
            return chinese_to_int(m_cn.group())
        except:
            return None
    return None

def normalize_prefix(prefix):
    """
    Normalize numbers (Arabic/Chinese) in prefix to '#'
    """
    return re.sub(r'[0-9零一二三四五六七八九十]+', '#', prefix)

def extract_directory_tuples_from_text(text):
    """
    Extract TOC items using regex. Returns list of tuples: (raw_prefix, title, order_index)
      raw_prefix: matched chapter number prefix
      title: chapter title
      order_index: line order (for backup sorting)
    """
    pattern = re.compile(
        r'('
        r'第[零一二三四五六七八九十]+[章节]|'  # Chinese format, e.g., "Chapter 1"
        r'Chapter\s*\d+|'                   # English formats
        r'Section\s*\d+|'
        r'Part\s*\d+|'
        r'Volume\s*\d+|'
        r'Unit\s*\d+|'
        r'Module\s*\d+|'
        r'\d+\s*[:：.]\s*|'                 # Arabic numerals with punctuation
        r'\d+\s+'                           # Arabic numerals with space
        r')\s*[:：]?\s*(.*)',
        re.IGNORECASE
    )
    # Exclusion patterns: copyright, page numbers, etc.
    exclude_patterns = [
        r'©\d{4}\s*\w+',
        r'\d+\s*页',
        r'^\d+$',
        r'^\d+\s*[^\w\s]+$',
    ]
    # Keywords to exclude from TOC pages
    exclude_keywords = ["appendices"]
    results = []
    for idx, line in enumerate(text.split('\n')):
        line = line.strip()
        if not line:
            continue
        if any(re.search(pat, line) for pat in exclude_patterns):
            continue
        if any(keyword.lower() in line.lower() for keyword in exclude_keywords):
            continue
        m = pattern.search(line)
        if m:
            raw_prefix = m.group(1).strip() if m.group(1) else ""
            title = m.group(2).strip() if m.group(2) else ""
            if title:
                results.append((raw_prefix, title, idx))
    return results

def is_valid_directory_item(title):
    """
    Validate TOC item:
      1. No garbled characters (e.g., '�')
      2. Minimum 3 characters
      3. At least 30% Chinese characters
    """
    if "�" in title:
        return False
    title = title.strip()
    if len(title) < 3:
        return False
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', title)
    if len(title) > 0 and (len(chinese_chars) / len(title)) < 0.3:
        return False
    return True

def is_relevant_directory_item(title):
    """
    Exclude common non-chapter content: copyright, preface, appendices, etc.
    """
    exclude_words = ["版权", "前言", "序言", "致谢", "附录", "参考文献", "索引", "目录", "说明", "序章", "楔子", "后记"]
    for word in exclude_words:
        if word in title:
            return False
    return True

def filter_entries(entries):
    """
    Filter TOC entries: keep only valid and relevant chapter titles
    """
    filtered = []
    for raw_prefix, title, order in entries:
        if is_valid_directory_item(title) and is_relevant_directory_item(title):
            filtered.append((raw_prefix, title, order))
    return filtered

def classify_directory_entries(entries):
    """
    Classify entries into primary/secondary based on normalized prefix:
      Entries matching the first entry's normalized prefix are primary, others secondary.
    Returns two lists: (primary_entries, secondary_entries)
    """
    if not entries:
        return [], []
    first_entry = entries[0]
    primary_norm = normalize_prefix(first_entry[0])
    first_level = []
    second_level = []
    for raw_prefix, title, order in entries:
        if normalize_prefix(raw_prefix) == primary_norm:
            first_level.append((raw_prefix, title, order))
        else:
            second_level.append((raw_prefix, title, order))
    return first_level, second_level

def select_directory(entries):
    """
    Select TOC entries based on criteria:
      - If primary entries ≥30, return primary
      - Else if secondary entries ≥30, return secondary
      - Else return None (invalid TOC)
    Also returns selection indicator (1 for primary, 2 for secondary).
    """
    first_level, second_level = classify_directory_entries(entries)
    if len(first_level) >= 30:
        return first_level, 1
    elif len(second_level) >= 30:
        return second_level, 2
    else:
        return None, None

def sort_directory_entries(entries):
    """
    Sort TOC entries: directly by their original order in text (order field)
    """
    return sorted(entries, key=lambda x: x[2])

def final_sort_titles(titles):
    """
    Process final extracted titles:
    Remove all numbers from titles while preserving original order.
    """
    cleaned_titles = [re.sub(r'\d+', '', t).strip() for t in titles]
    return cleaned_titles

def extract_book_titles_with_authors(text, max_titles=5):
    """
    Extract book titles enclosed in Chinese book title marks 《》, requiring adjacent author names
    """
    pattern = r'([\u4e00-\u9fa5]{2,4})《([^《》]+)》|《([^《》]+)》([\u4e00-\u9fa5]{2,4})'
    matches = re.findall(pattern, text)
    book_titles = set()
    for match in matches:
        if len(book_titles) >= max_titles:
            break
        if match[1]:
            title = match[1].strip()
            if title:
                book_titles.add(title)
        elif match[2]:
            title = match[2].strip()
            if title:
                book_titles.add(title)
    return list(book_titles)[:max_titles]

def extract_books_from_url(url, max_titles=5):
    """
    Extract book titles from specified URL
    """
    try:
        print(f"Accessing URL: {url}")
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        if not text.strip():
            print("Empty webpage content. Skipping.")
            return []
        books = extract_book_titles_with_authors(text, max_titles)
        if not books:
            print("No relevant book titles found.")
        return books
    except requests.RequestException as e:
        print(f"Network request failed: {e}")
        return []

def fix_json_content(raw_content):
    """
    Attempt to fix JSON formatting errors and return corrected dict.
    1. Try direct parsing first.
    2. If failed, extract content between first '{' and last '}' and retry.
    3. Raise exception if still failed.
    """
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        start_index = raw_content.find('{')
        end_index = raw_content.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            fixed_content = raw_content[start_index:end_index+1]
            try:
                return json.loads(fixed_content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to fix JSON: {e}")
        else:
            raise ValueError("No valid JSON object boundaries found")

def save_json_to_file(data, filename):
    """
    Save JSON data to specified file under 'output' directory.
    Creates directory if not exists.
    """
    output_dir = os.path.join(os.getcwd(), "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Expanded TOC saved to: {filepath}")

def sanitize_filename(filename):
    """
    Sanitize string to valid filename (replace illegal characters)
    """
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def main():
    print("Welcome to Book TOC Extraction System")
    
    # Step 1: Get subject from user and search related web pages
    subject = input("Enter the subject you want to learn: ").strip()
    if not subject:
        print("Subject cannot be empty!")
        return
    print("Searching for related web pages...")
    subject_urls = google_search(subject, num_results=5)
    if not subject_urls:
        print("No related web pages found.")
        return
    
    # Step 2: Extract candidate book titles from search results
    candidate_books = set()
    for url in subject_urls:
        print(f"\nAnalyzing webpage: {url}")
        books = extract_books_from_url(url, max_titles=5)
        if books:
            for book in books:
                if book and book.strip():
                    candidate_books.add(book.strip())
    candidate_books = list(candidate_books)
    if not candidate_books:
        print("No book titles extracted.")
        return
    print("\nExtracted book titles:")
    for idx, book in enumerate(candidate_books, 1):
        print(f"{idx}. {book}")
    
    # Let user select a book
    while True:
        try:
            choice = int(input("Select a book number: "))
            if 1 <= choice <= len(candidate_books):
                selected_book = candidate_books[choice - 1]
                break
            else:
                print("Invalid number.")
        except ValueError:
            print("Please enter a number.")
    print(f"\nSelected book: {selected_book}")
    
    # Step 3: Search for book's TOC pages using selected title
    print("\nSearching for book TOC pages...")
    book_query = f"{selected_book} table of contents"
    book_urls = google_search(book_query, num_results=5)
    if not book_urls:
        print("No TOC pages found.")
        return
    
    # Step 4: Process search results to extract TOC
    final_directory = None
    final_url = None
    for url in book_urls:
        print(f"\nAttempting to extract TOC from: {url}")
        html = fetch_html_content(url)
        if not html or not html.strip():
            print("Empty webpage. Skipping.")
            continue
        text = extract_text_from_html(html)
        if not text.strip():
            print("No text extracted. Skipping.")
            continue
        
        entries = extract_directory_tuples_from_text(text)
        if not entries:
            print("No TOC entries found. Skipping.")
            continue
        entries = filter_entries(entries)
        if not entries:
            print("No valid entries after filtering. Skipping.")
            continue
        selected_entries, level = select_directory(entries)
        if not selected_entries:
            print("Insufficient valid entries (minimum 30). Skipping.")
            continue
        sorted_entries = sort_directory_entries(selected_entries)
        final_titles = [title for (_, title, _) in sorted_entries]
        if final_titles and len(final_titles) >= 30:
            final_directory = final_titles
            final_url = url
            break
        else:
            print("Sorted entries insufficient. Trying next URL.")
    
    # Fallback if no valid TOC found
    if final_directory is None:
        print("\nFailed to extract valid TOC after multiple attempts.")
        while True:
            print("\nOptions:")
            print("1. Manually provide TOC webpage URL")
            print("2. Reselect book")
            user_choice = input("Enter 1 or 2: ").strip()
            if user_choice == "1":
                custom_url = input("Enter TOC webpage URL: ").strip()
                html = fetch_html_content(custom_url)
                if not html or not html.strip():
                    print("Invalid URL. Try again.")
                    continue
                text = extract_text_from_html(html)
                if not text.strip():
                    print("No text extracted. Try again.")
                    continue
                entries = extract_directory_tuples_from_text(text)
                entries = filter_entries(entries)
                if not entries:
                    print("No valid entries. Try again.")
                    continue
                selected_entries, level = select_directory(entries)
                if not selected_entries:
                    print("Insufficient entries. Try again.")
                    continue
                sorted_entries = sort_directory_entries(selected_entries)
                final_titles = [title for (_, title, _) in sorted_entries]
                if final_titles and len(final_titles) >= 30:
                    final_directory = final_titles
                    final_url = custom_url
                    break
                else:
                    print("Insufficient sorted entries. Try again.")
                    continue
            elif user_choice == "2":
                print("Reselecting book...")
                return main()  # Restart process
            else:
                print("Invalid choice.")
    
    if final_directory:
        # Final processing: remove numbers from titles
        final_sorted_titles = final_sort_titles(final_directory)
        toc_text = "\n".join(final_sorted_titles)
        
        print("\nCalling OpenAI API to expand TOC...")
        expanded_contents = expand_section_content(toc_text)
        
        try:
            fixed_data = fix_json_content(expanded_contents)
        except ValueError as e:
            print(f"JSON fix error: {e}")
            return
        
        filename = f"{sanitize_filename(subject)}.json"
        save_json_to_file(fixed_data, filename)
    else:
        print("Failed to extract valid TOC.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Runtime error: {e}")
