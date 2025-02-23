import json
import openai
import requests
from bs4 import BeautifulSoup
import re
from serpapi import GoogleSearch
import os

# ---------------- OpenAI API 部分 ----------------
# 设置 OpenAI API Key
openai_client = openai.OpenAI(api_key="")

def expand_section_content(toc_text):
    """
    调用 OpenAI API 扩充书籍目录内容

    参数：
        toc_text (str): 包含目录标题的文本（每行代表一个章节标题，排序结果即为最终顺序）

    返回：
        API 返回的扩充说明（预期为 JSON 格式字符串）
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
        model="gpt-4o",  # 根据实际情况选择模型
        messages=[
            {"role": "system", "content": "You are a professional academic writing assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=3000,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content.strip()

# ---------------- SERPAPI 及书籍目录提取代码 ----------------
SERPAPI_API_KEY = ""  # 请替换为你的 SERPAPI API Key

def google_search(query, num_results=5):
    """
    使用 SerpAPI 进行 Google 搜索，并返回前 num_results 个结果的链接
    """
    params = {
        "q": query,
        "hl": "zh-CN",    # 设置语言为中文
        "gl": "cn",       # 设置地区为中国
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
    从指定 URL 获取网页内容
    """
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"无法获取网页内容：{e}")
        return None

def extract_text_from_html(html_content):
    """
    从 HTML 内容中提取纯文本
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator='\n')
    return text

def chinese_to_int(chinese_str):
    """
    将中文数字转换为整数，支持“十”、“十一”、“二十”、“二十一”等常见形式
    """
    mapping = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    if chinese_str == "十":
        return 10
    if chinese_str.startswith("十"):
        return 10 + chinese_to_int(chinese_str[1:]) if len(chinese_str) > 1 else 10
    if "十" in chinese_str:
        parts = chinese_str.split("十")
        tens = mapping.get(parts[0], 1)  # 若前面为空，默认为 1
        ones = chinese_to_int(parts[1]) if parts[1] else 0
        return tens * 10 + ones
    return mapping.get(chinese_str[0], 0)

def parse_chapter_number(prefix):
    """
    尝试从前缀中解析章节号，优先解析阿拉伯数字，其次解析中文数字
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
    将前缀中的数字（阿拉伯或中文）归一化为 '#'
    """
    return re.sub(r'[0-9零一二三四五六七八九十]+', '#', prefix)

def extract_directory_tuples_from_text(text):
    """
    使用正则表达式从文本中提取目录项，返回元组列表：(raw_prefix, title, order_index)
      raw_prefix：匹配到的章节编号前缀
      title：章节标题
      order_index：所在行的顺序（用于排序备用）
    """
    pattern = re.compile(
        r'('
        r'第[零一二三四五六七八九十]+[章节]|'  # 中文格式，如“第1章”
        r'Chapter\s*\d+|'                   # 英文格式，如“Chapter 1”
        r'Section\s*\d+|'
        r'Part\s*\d+|'
        r'Volume\s*\d+|'
        r'Unit\s*\d+|'
        r'Module\s*\d+|'
        r'\d+\s*[:：.]\s*|'                 # 阿拉伯数字后跟标点
        r'\d+\s+'                           # 阿拉伯数字加空格
        r')\s*[:：]?\s*(.*)',
        re.IGNORECASE
    )
    # 排除规则：版权、页码等
    exclude_patterns = [
        r'©\d{4}\s*\w+',
        r'\d+\s*页',
        r'^\d+$',
        r'^\d+\s*[^\w\s]+$',
    ]
    # 针对目录页面排除的关键词，如 appendices
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
    判断目录项是否有效：
      1. 不包含乱码（如 '�'）
      2. 长度至少 3 个字符
      3. 中文字符比例至少 30%
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
    排除常见的非章节内容，如“版权”、“前言”、“序言”、“附录”等
    """
    exclude_words = ["版权", "前言", "序言", "致谢", "附录", "参考文献", "索引", "目录", "说明", "序章", "楔子", "后记"]
    for word in exclude_words:
        if word in title:
            return False
    return True

def filter_entries(entries):
    """
    过滤提取到的目录项：只保留有效且相关的章节标题
    """
    filtered = []
    for raw_prefix, title, order in entries:
        if is_valid_directory_item(title) and is_relevant_directory_item(title):
            filtered.append((raw_prefix, title, order))
    return filtered

def classify_directory_entries(entries):
    """
    根据归一化后的前缀将目录项分为一级和二级：
      与第一项归一化后的前缀相同的为一级，否则为二级。
    返回两个列表：(一级目录, 二级目录)
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
    根据提取规则选择目录项：
      - 如果一级目录数量 ≥ 30，则返回一级目录；
      - 否则如果二级目录数量 ≥ 30，则返回二级目录；
      - 否则返回 None 表示目录无效。
    同时返回一个指示标（1 表示一级，2 表示二级）。
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
    对目录项进行排序：
    直接按照它们在文本中出现的顺序（order 字段）排序，不解析标题中的数字。
    """
    return sorted(entries, key=lambda x: x[2])

def final_sort_titles(titles):
    """
    对最终提取到的目录标题进行处理：
    删除标题中的所有数字，并保持原出现顺序不变。
    """
    cleaned_titles = [re.sub(r'\d+', '', t).strip() for t in titles]
    return cleaned_titles

def extract_book_titles_with_authors(text, max_titles=5):
    """
    从文本中提取用书名号《》括起来的书名，同时要求前后出现人名
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
    从指定 URL 中提取书籍标题
    """
    try:
        print(f"正在访问链接：{url}")
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        if not text.strip():
            print("网页内容为空，跳过该链接。")
            return []
        books = extract_book_titles_with_authors(text, max_titles)
        if not books:
            print("未找到相关书籍标题。")
        return books
    except requests.RequestException as e:
        print(f"网络请求失败：{e}")
        return []

def fix_json_content(raw_content):
    """
    尝试修正生成的 JSON 内容中可能存在的格式错误，并返回修正后的字典。
    1. 首先尝试直接解析。
    2. 如果解析失败，则提取第一个 '{' 到最后一个 '}' 之间的内容后重新解析。
    3. 如果仍然失败，则抛出异常。
    """
    try:
        # 尝试直接解析
        return json.loads(raw_content)
    except json.JSONDecodeError:
        # 定位第一个 '{' 和最后一个 '}'
        start_index = raw_content.find('{')
        end_index = raw_content.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            fixed_content = raw_content[start_index:end_index+1]
            try:
                return json.loads(fixed_content)
            except json.JSONDecodeError as e:
                raise ValueError(f"无法修正JSON内容: {e}")
        else:
            raise ValueError("无法找到有效的JSON对象边界")

def save_json_to_file(data, filename):
    """
    保存JSON数据到指定文件中，文件将保存在当前工作目录下的 'output' 文件夹中。
    如果文件夹不存在，则创建该文件夹。
    """
    output_dir = os.path.join(os.getcwd(), "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"扩充后的目录内容已保存到文件: {filepath}")

def sanitize_filename(filename):
    """
    将字符串处理成合法的文件名（替换掉非法字符）
    """
    # 替换非法字符（例如 \ / : * ? " < > |）
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def main():
    print("欢迎使用书籍目录提取系统")
    
    # 步骤1：询问用户想学习的学科并搜索相关网页
    subject = input("请输入你想学习的学科：").strip()
    if not subject:
        print("学科名称不能为空！")
        return
    print("正在搜索与该学科相关的网页，请稍候...")
    subject_urls = google_search(subject, num_results=5)
    if not subject_urls:
        print("未找到与该学科相关的网页。")
        return
    
    # 步骤2：从搜索结果中提取候选书籍标题
    candidate_books = set()
    for url in subject_urls:
        print(f"\n正在分析网页：{url}")
        books = extract_books_from_url(url, max_titles=5)
        if books:
            for book in books:
                if book and book.strip():
                    candidate_books.add(book.strip())
    candidate_books = list(candidate_books)
    if not candidate_books:
        print("未能从相关网页中提取到书籍名称。")
        return
    print("\n提取到以下书籍名称：")
    for idx, book in enumerate(candidate_books, 1):
        print(f"{idx}. {book}")
    
    # 让用户选择一本书
    while True:
        try:
            choice = int(input("请选择一本书的编号："))
            if 1 <= choice <= len(candidate_books):
                selected_book = candidate_books[choice - 1]
                break
            else:
                print("请输入有效的编号。")
        except ValueError:
            print("请输入数字。")
    print(f"\n你选择的书籍是：{selected_book}")
    
    # 步骤3：使用所选书名作为关键词搜索该书的目录网页
    print("\n正在搜索该书的目录网页，请稍候...")
    book_query = f"{selected_book} 目录"
    book_urls = google_search(book_query, num_results=5)
    if not book_urls:
        print("未找到与该书目录相关的网页。")
        return
    
    # 步骤4：遍历搜索结果，提取并处理目录
    final_directory = None
    final_url = None
    for url in book_urls:
        print(f"\n尝试从网页提取目录：{url}")
        html = fetch_html_content(url)
        if not html or not html.strip():
            print("网页内容为空，跳过该链接。")
            continue
        text = extract_text_from_html(html)
        if not text.strip():
            print("提取到的文本为空，跳过该链接。")
            continue
        
        entries = extract_directory_tuples_from_text(text)
        if not entries:
            print("未提取到目录项，跳过该链接。")
            continue
        entries = filter_entries(entries)
        if not entries:
            print("过滤后无有效目录项，跳过该链接。")
            continue
        selected_entries, level = select_directory(entries)
        if not selected_entries:
            print("有效的一级或二级目录项不足30个，跳过该链接。")
            continue
        sorted_entries = sort_directory_entries(selected_entries)
        final_titles = [title for (_, title, _) in sorted_entries]
        if final_titles and len(final_titles) >= 30:
            final_directory = final_titles
            final_url = url
            break
        else:
            print("排序后目录项数量不足30个，尝试下一个链接。")
    
    # 若遍历多个链接后仍未提取到有效目录，则提示用户选择后续操作
    if final_directory is None:
        print("\n经过多个链接的尝试，仍未提取到有效且数量不少于30项的目录。")
        while True:
            print("\n请选择后续操作：")
            print("1. 手动提供包含目录内容的网页链接，由系统提取目录。")
            print("2. 重新选择书籍名称。")
            user_choice = input("请输入1或2：").strip()
            if user_choice == "1":
                custom_url = input("请提供包含目录内容的网页链接：").strip()
                html = fetch_html_content(custom_url)
                if not html or not html.strip():
                    print("该链接的网页内容为空，请提供其他链接。")
                    continue
                text = extract_text_from_html(html)
                if not text.strip():
                    print("提取到的文本为空，请提供其他链接。")
                    continue
                entries = extract_directory_tuples_from_text(text)
                entries = filter_entries(entries)
                if not entries:
                    print("该链接未提取到有效目录项，请提供其他链接。")
                    continue
                selected_entries, level = select_directory(entries)
                if not selected_entries:
                    print("该链接的有效目录项不足30个，请提供其他链接。")
                    continue
                sorted_entries = sort_directory_entries(selected_entries)
                final_titles = [title for (_, title, _) in sorted_entries]
                if final_titles and len(final_titles) >= 30:
                    final_directory = final_titles
                    final_url = custom_url
                    break
                else:
                    print("排序后目录项数量不足30个，请提供其他链接。")
                    continue
            elif user_choice == "2":
                print("重新选择书籍名称。")
                return main()  # 重新开始书籍选择流程
            else:
                print("无效选项，请输入1或2。")
    
    if final_directory:
        # 对最终提取到的目录标题进行总排序处理：删除标题中的数字，保持原出现顺序不变。
        final_sorted_titles = final_sort_titles(final_directory)
        # 将目录列表拼接成 OpenAI API 所需的 prompt 内容
        toc_text = "\n".join(final_sorted_titles)
        
        print("\n正在调用 OpenAI API 对目录进行扩充说明，请稍候...")
        expanded_contents = expand_section_content(toc_text)
        
        # 调用 fix_json_content 函数修正返回的 JSON 内容格式
        try:
            fixed_data = fix_json_content(expanded_contents)
        except ValueError as e:
            print(f"修正JSON内容时出错：{e}")
            return
        
        # 使用用户输入的学科名称生成 JSON 文件名，先进行合法化处理
        filename = f"{sanitize_filename(subject)}.json"
        # 保存修正后的 JSON 数据到 output 文件夹下的文件中
        save_json_to_file(fixed_data, filename)
    else:
        print("未能提取到有效的书籍目录。")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"程序运行过程中发生错误：{e}")
