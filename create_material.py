import openai
import json
import os
import time

# OpenAI API client setup
openai_client = openai.OpenAI(api_key="")

# Prompt template
PROMPT_TEMPLATE = """
Design an educational module for teaching kids math through an AI bot chat for section [section_number]={section_number}. 
Each section should include:
1. A short and informative title with the key "title".
2. 3-5 subsections that divide the topic into subtopics with logical progression.
3. Each subsection should have:
   - A title for the subsection.
   - A detailed lecture note in Markdown language that is at least 1000 tokens long, using text and equations (use LaTeX for equations with inline $xxx$ or display $$xxx$$ formatting).
   - Interactive questions or instructions for students to try (e.g., "Can you solve this equation?").
4. At the end of each subsection, create 5 quizzes with ascending difficulty for students to attempt.

Return the response as a JSON object with the following format:
{{
    "title": "Section Title",
    "subsections": [
        {{
            "subsection_number": "in the form of [section_number].1",
            "subsection_title": "Subsection 1 Title",
            "content": "Teaching material with logical flow, using text and equations, for Subsection 1",
            "quiz": [
                "Quiz Question 1",
                "Quiz Question 2",
                "Quiz Question 3",
                "Quiz Question 4",
                "Quiz Question 5"
            ]
        }},
        {{
            "subsection_number": "in the form of [section_number].2",
            "title": "Subsection 2 Title",
            "content": "Teaching material with logical flow, using text and equations, for Subsection 2",
            "quiz": [
                "Quiz Question 1",
                "Quiz Question 2",
                "Quiz Question 3",
                "Quiz Question 4",
                "Quiz Question 5"
            ]
        }}
    ]
}}
"""
subject = input("please input the subject you want to learn: ")
def create_material(save_file, start_section=None):
    try:
        # Load initial JSON structure
        with open(f'{subject}.json', 'r',encoding='utf-8') as file:
            kumon_data = json.load(file)

        # Load existing data from save_file if it exists
        if os.path.exists(save_file):
            with open(save_file, 'r',encoding='utf-8') as file:
                processed_data = json.load(file)
        else:
            processed_data = {"sections": []}

        # Convert existing sections to a set for quick lookup
        processed_sections = {sec['section_number'] for sec in processed_data['sections']}

        # Iterate over each section in the initial JSON
        for index, section in enumerate(kumon_data['sections']):

            if start_section and section['section_number'] < start_section: # make sure section number of comparable
                continue

            if section['section_number'] in processed_sections:
                print(f"Skipping already processed section {section['section_number']}.")
                continue

            print(f"\nProcessing section {section['section_number']} ...")
            start_time = time.time()

            prompt = PROMPT_TEMPLATE.format(section_number=section['section_number'])
            messages = [
                {"role": "system", "content": f"You are an AI assistant creating educational material for {subject}."},
                {"role": "user", "content": f"Create Kumon-style material for the topic: {section['description']}. {prompt}"}
            ]
            
            completion = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            
            # Parse the API response and update the current section
            api_response = json.loads(completion.choices[0].message.content)

            # Decode Unicode characters in quizzes
            # for subsection in api_response.get('subsections', []):
            #     subsection['quiz'] = [q.encode('utf-8').decode('unicode_escape') for q in subsection['quiz']]
            
            # Construct a new dictionary with the desired key order
            ordered_section = {
                "section_number": section['section_number'],
                "description": section['description'],
                **api_response
            }

            # Append the ordered dictionary to processed_data
            processed_data['sections'].append(ordered_section)

            end_time = time.time()
            print(f"Writing to {save_file}. Processing time: {end_time-start_time:.2f} seconds.")
            
            # Save after each iteration
            with open(save_file, 'w') as file:
                json.dump(processed_data, file, indent=4)
        
        print(f"{subject} material created successfully.")
    except Exception as e:
        print(f"error: {str(e)}")



def auto_correct_json(file_path: str, save_path: str) -> None:
    """
    Auto-corrects structural inconsistencies in a Kumon JSON file to ensure it passes the followup validation.
    The function fixes issues such as missing or incorrect keys in subsections.

    :param file_path: Path to the input JSON file to be corrected.
    :param save_path: Path to save the corrected JSON file.
    """
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)

        # Extract sections
        sections = data.get("sections", [])
        if not isinstance(sections, list):
            raise ValueError("The 'sections' field is not a list.")

        for section in sections:
            # Validate and fix subsections
            subsections = section.get("subsections", [])
            if not isinstance(subsections, list):
                section["subsections"] = []  # Reset to an empty list if it's invalid
                continue

            for subsection in subsections:
                if not isinstance(subsection, dict):
                    subsections.remove(subsection)  # Remove invalid subsection entries
                    continue

                # Check and fix subsection title mismatch
                if "title" in subsection:
                    subsection["subsection_title"] = subsection.pop("title")

                # Ensure mandatory keys exist with default values
                mandatory_keys = {
                    "subsection_number": "unknown",
                    "subsection_title": "Untitled Subsection",
                    "content": "",
                    "quiz": []
                }
                for key, default_value in mandatory_keys.items():
                    if key not in subsection:
                        subsection[key] = default_value

        # Save the corrected JSON file
        with open(save_path, 'w') as file:
            json.dump(data, file, indent=4)
        print(f"Auto-corrected JSON file saved to: {save_path}")

    except json.JSONDecodeError:
        print("Error: Invalid JSON file format.")
    except Exception as e:
        print(f"Error: {str(e)}")




def validate_json_format(file_path: str) -> str:
    """
    Validate the format of a JSON file containing sections and subsections.
    Ensures all sections have the same structure as the first section.
    Relaxes the check for the number of "subsection_number" under "subsections".
    
    :param file_path: Path to the JSON file.
    :return: A message indicating whether the file is correct or identifying issues.
    """
    errors = []  # Collect all errors

    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        # Extract all sections
        sections = data.get("sections", [])
        if not isinstance(sections, list) or not sections:
            return "Issue: JSON file has no 'sections' key or the value is not a list."

        # Use the first section as a template
        template_section = sections[0]
        template_keys = set(template_section.keys())
        template_sub_keys = set(template_section.get("subsections", [{}])[0].keys() if template_section.get("subsections") else [])

        # Validate each section
        for section in sections:
            if not isinstance(section, dict):
                errors.append("Issue: Section is not a dictionary.")
                continue

            # Check section-level keys
            section_keys = set(section.keys())
            if section_keys != template_keys:
                errors.append(
                    f"Issue: Section {section.get('section_number', 'unknown')} has mismatched keys: "
                    f"{section_keys - template_keys} or missing keys: {template_keys - section_keys}"
                )

            # Check subsection structure
            subsections = section.get("subsections", [])
            if not isinstance(subsections, list):
                errors.append(f"Issue: Section {section.get('section_number', 'unknown')} 'subsections' is not a list.")
                continue

            for subsection in subsections:
                if not isinstance(subsection, dict):
                    errors.append(
                        f"Issue: Subsection in Section {section.get('section_number', 'unknown')} is not a dictionary."
                    )
                    continue

                subsection_keys = set(subsection.keys())
                if subsection_keys != template_sub_keys:
                    errors.append(
                        f"Issue: Subsection {subsection.get('subsection_number', 'unknown')} in "
                        f"Section {section.get('section_number', 'unknown')} has mismatched keys: "
                        f"{subsection_keys - template_sub_keys} or missing keys: {template_sub_keys - subsection_keys}"
                    )

        if not errors:
            return "The JSON file format is fully correct."
        else:
            return "\n".join(errors)

    except json.JSONDecodeError:
        return "Issue: Invalid JSON file format."
    except Exception as e:
        return f"Issue: {str(e)}"



if __name__ == "__main__":


    #create_material(save_file=f'{subject}_material.json')

    #auto_correct_json(f'{subject}_material.json', f'{subject}_material_corrected.json')

    result = validate_json_format(f'{subject}_material_corrected.json')
    print(result)