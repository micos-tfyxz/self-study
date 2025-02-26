# Main Programs

### create_materal.py
This project is designed to create structured educational materials for teaching kids math (or other subjects) using an AI-powered chatbot. The materials are generated in JSON format, which includes sections, subsections, lecture notes, and quizzes. The project leverages OpenAI's GPT-4 model to generate content dynamically.

Features:

Dynamic Content Generation: Uses OpenAI's GPT-4 to create educational modules with titles, subsections, detailed lecture notes, and quizzes.

JSON Output: Saves the generated content in a structured JSON format for easy integration into educational platforms.

Auto-Correction: Includes a utility to auto-correct structural inconsistencies in the generated JSON files.

Validation: Provides a validation function to ensure the JSON file adheres to the expected format.

### English_version.py / Chinese_version.py:

Function: Full executable scripts.

Language-Specific Optimization:

Chinese Version: Prioritizes Chinese webpages (via hl="zh-CN" in SerpAPI), leveraging richer directory structures in Chinese academic resources.

English Version: Targets English content but yields fewer valid directories due to inconsistent formatting on English pages.

# Modular Components

### api.py:

Function: Handles Google Search via SerpAPI.

Key Features:

Returns top search results for a query.

Configurable language/region settings (e.g., gl="cn" for China).

### book.py:

Function: Extracts book titles from webpages.

Logic:

Uses regex to identify Chinese book titles enclosed in 《》 and associated with author names.

Filters invalid titles based on character ratios and formatting.

### list.py:

Function: Extracts and validates table-of-contents (TOC) entries from webpages.

Logic:

Regex-based pattern matching for chapter headings (e.g., Chapter 1, 第1章).

Excludes non-chapter sections (e.g., prefaces, appendices).

Validates entries by length, Chinese character ratio, and numbering consistency.

### key workflow:

1. User Input & Initial Book Search
Input: User specifies a subject (e.g., "地理经典教材").

Google Search: Uses SerpAPI to fetch top 5 relevant Chinese webpages related to the subject.

Book Extraction: Scrapes candidate book titles from these pages, focusing on titles enclosed in Chinese quotation marks 《》 and associated with author names.

2. Book Selection & Directory Scraping
User Interaction: Displays extracted books and prompts the user to select one（e.g., "人文地理学"）.

Directory Search: Performs a second Google search using the selected book name + "目录" (directory) to find table-of-contents (TOC) pages.

TOC Extraction:

Fetches HTML content from candidate URLs.

Uses regex and heuristics to identify valid directory entries (e.g., filtering out non-chapter sections like prefaces or appendices).

Validates entries based on length, Chinese character ratio, and relevance.

3. Directory Processing & Validation
Hierarchy Classification: Separates entries into primary/secondary sections based on prefix patterns (e.g., Chapter 1 vs. Section 1.1).

Selection Criteria:

Prioritizes sections with ≥30 valid entries (primary > secondary).

Sorts entries by their original order in the source text.

Fallback Mechanism: If automated extraction fails, allows manual URL input for TOC retrieval.

4. OpenAI-Based Content Expansion
Prompt Engineering: Sends the cleaned TOC to GPT-4o with a structured prompt to generate:

A 2-sentence description per chapter (explanation + learning objectives).

Output format: JSON with section_number (e.g., "chapter1") and description keys.

JSON Sanitization: Uses fix_json_content to handle formatting errors in OpenAI’s response.

5. Output Generation
File Saving:

Stores the final JSON in an output folder.

Filename derived from the sanitized subject name (e.g., 地理经典教材.json)