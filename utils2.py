# --- START OF FILE utils2.py ---

import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Union

# Attempt to import pypandoc. If it's not installed, document conversion will fail gracefully.
try:
    import pypandoc
except ImportError:
    pypandoc = None

# Get a logger for this module. The root logger is configured in main.py.
logger = logging.getLogger(__name__)

# #############################################################################
# --- 1. Markdown and DOCX Conversion ---
# #############################################################################

# This template defines the structure for each question in the final output files.
OUTPUT_TEMPLATE = """
## Question #: {{question_num}}

**CLINICAL SCENARIO:**
{{question_desc}}

**QUESTION LINE:**
{{question_line}}

**ORIGINAL OPTIONS:**
{{options}}

**ORIGINAL CORRECT CHOICE:**
{{correct_choice}}

**ORIGINAL REASONING:**
{{reasoning}}

---

**!REFINED DESCRIPTION:**
{{updated_description}}

**!ALPHABETIZED OPTIONS:**
{{updated_options}}

**!CORRECT CHOICE (Letter):**
{{updated_correct_choice}}

**!CORRECT CHOICE (Text):**
{{updated_correct_choice_text}}

**!REFINED REASONING:**
{{updated_reasoning}}


"""

# #############################################################################

def render_question_md(question: dict) -> str:
    """
    Renders a single question dictionary into a Markdown string using the template.
    It safely handles missing keys by defaulting to an empty string.
    """
    # Create a copy to avoid modifying the original dictionary
    q = question.copy()
    
    # Ensure all expected keys are present, defaulting to a placeholder if not
    keys = [
        "question_num", "question_desc", "question_line", "options",
        "correct_choice", "reasoning", "updated_description",
        "updated_options", "updated_correct_choice",
        "updated_correct_choice_text", "updated_reasoning"
    ]
    for key in keys:
        q.setdefault(key, "[N/A]")

    # Replace placeholders in the template
    # Using a loop makes it more maintainable than a long chain of .replace()
    md_string = OUTPUT_TEMPLATE
    for key, value in q.items():
        md_string = md_string.replace(f"{{{{{key}}}}}", str(value))
        
    return md_string

# #############################################################################

def convert_json_to_docx(json_path: Union[str, Path], docx_path: Union[str, Path]):
    """
    Converts a JSON file (containing a list of question objects) into a DOCX file
    by first creating an intermediate Markdown file in the 'tmp' directory.

    Args:
        json_path (Union[str, Path]): Path to the source JSON file.
        docx_path (Union[str, Path]): Path where the final DOCX file will be saved.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1a. Pre-flight Checks ---
    # Check if pypandoc is available.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    if pypandoc is None:
        logger.error("`pypandoc` is not installed. Cannot convert to DOCX. Please run 'pip install pypandoc'.")
        return
        
    json_path = Path(json_path)
    docx_path = Path(docx_path)

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1b. Read and Validate Source JSON ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        if not isinstance(questions, list):
            logger.error(f"Input file '{json_path.name}' must contain a list of question objects.")
            return
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error reading source file '{json_path.name}': {e}")
        return

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1c. Create Intermediate Markdown File ---
    # This file is created in the 'tmp' directory.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # Using Path.name is robust and works on all operating systems.
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    md_path = tmp_dir / f"{json_path.stem}.md"

    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            for q in questions:
                if isinstance(q, dict):
                    f.write(render_question_md(q))
                else:
                    logger.warning(f"Skipping non-dictionary item in '{json_path.name}': {q}")
        logger.info(f"Intermediate Markdown file saved to: {md_path}")
    except IOError as e:
        logger.error(f"Error writing to temporary file '{md_path}': {e}")
        return

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1d. Convert Markdown to DOCX ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        docx_path.parent.mkdir(parents=True, exist_ok=True)
        pypandoc.convert_file(md_path, 'docx', outputfile=str(docx_path))
        logger.info(f"Successfully converted to DOCX: '{docx_path.name}'")
    except Exception as e:
        logger.error(f"Error converting to .docx using pypandoc: {e}")
        logger.error("Please ensure Pandoc is installed and accessible in your system's PATH.")
        
# #############################################################################
# --- 2. JSON Sorting Utility ---
# #############################################################################

def sort_json_file(input_path: Path, output_path: Path, sort_key: str, reverse: bool = False):
    """
    Reads a JSON file (list of objects), sorts it by a specified key,
    and writes the result to a new file. It intelligently handles sorting
    for both numeric and alphanumeric string values.

    Args:
        input_path (Path): Path to the input JSON file.
        output_path (Path): Path where the sorted JSON file will be saved.
        sort_key (str): The dictionary key to sort by (e.g., "question_num").
        reverse (bool): If True, sorts in descending order.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2a. Read and Validate Input JSON ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info(f"Attempting to sort '{input_path.name}' by key '{sort_key}'...")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise TypeError("JSON content is not a list of objects.")
    except FileNotFoundError:
        logger.error(f"Sort error: Input file not found at {input_path}")
        return
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Sort error: Could not read or parse JSON file '{input_path.name}': {e}")
        return

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2b. Define Smart Sort Key ---
    # This handles "2" vs "10" correctly, and also "12a" vs "12b".
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    def smart_sort_key(item: Dict[str, Any]):
        if sort_key not in item:
            # Place items with missing keys at the very end
            return (float('inf'),)

        value = item[sort_key]
        
        if isinstance(value, str):
            # For "question_num", we expect num + optional letter
            if sort_key == "question_num":
                match = re.match(r'(\d+)([a-zA-Z]*)', value)
                if match:
                    return (int(match.group(1)), match.group(2))
            # For other string keys, just return the lowercase string
            return (float('-inf'), value.lower())
        
        # For non-string values (like numbers), return them directly
        return (float('-inf'), value)

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2c. Sort and Save Data ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        sorted_data = sorted(data, key=smart_sort_key, reverse=reverse)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, indent=4)
        logger.info(f"Successfully sorted data and saved to '{output_path.name}'.")
    except TypeError as e:
        logger.error(f"Sort error: Key '{sort_key}' has mixed, un-sortable data types. Details: {e}")
    except IOError as e:
        logger.error(f"Sort error: Could not write to output file '{output_path}': {e}")