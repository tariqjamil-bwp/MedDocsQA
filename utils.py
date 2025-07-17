# --- START OF FILE utils.py ---

import warnings
import re
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Union
from dataclasses import dataclass

# Suppress warnings from the docling library if any
warnings.filterwarnings("ignore")

# Import third-party libraries for document conversion
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Get a logger for this module. The root logger is configured in main.py.
logger = logging.getLogger(__name__)

# #############################################################################
# --- 1. Project Path Configuration ---
# #############################################################################

@dataclass
class ProjectPaths:
    """A dataclass to hold all essential directory paths for a project."""
    UPROJ_DIR: Path
    SRCFILE_DIR: Path
    TEXTED_DIR: Path
    PARSED_DIR: Path
    PROCESSED_DIR: Path
    OUTPUT_DIR: Path

# #############################################################################

def get_paths(user_projects_root: Path, project_name: str) -> ProjectPaths:
    """
    Constructs and returns a ProjectPaths object containing absolute paths for all
    necessary project directories. This ensures all path handling is consistent
    and OS-agnostic (works on Windows, Linux, etc.).

    Args:
        user_projects_root (Path): The root directory where the 'Projects' folder is located.
        project_name (str): The specific project folder name inside 'Projects'.

    Returns:
        ProjectPaths: A dataclass with all project-specific directory paths.

    Raises:
        FileNotFoundError: If the base project directory does not exist.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1a. Define Base Path ---
    # The expected structure is '.../code/Projects/PROJECT_NAME/'
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    base_path = user_projects_root / "Projects" / project_name
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1b. Validate Path Existence ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    if not base_path.exists():
        logger.error(f"Project base path does not exist: {base_path}")
        raise FileNotFoundError(f"Project base path does not exist: {base_path}")
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1c. Create and Return Dataclass ---
    # Populate the dataclass with standardized sub-directory paths.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    return ProjectPaths(
        UPROJ_DIR=base_path,
        SRCFILE_DIR=base_path / "0Source",
        TEXTED_DIR=base_path / "1Texted",
        PARSED_DIR=base_path / "2Parsed",
        PROCESSED_DIR=base_path / "3Processed",
        OUTPUT_DIR=base_path / "OUTPUT"
    )

# #############################################################################
# --- 2. File Processing and Conversion Functions ---
# #############################################################################

def extract_pdf_to_text(pdf_path: Union[str, Path], dst_path: Union[str, Path]):
    """
    Uses the 'docling' library to convert a PDF file to a clean Markdown-like
    text file, removing embedded image placeholders.

    Args:
        pdf_path (Union[str, Path]): The path to the source PDF file.
        dst_path (Union[str, Path]): The path where the output text file will be saved.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2a. Configure and Run Docling Converter ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info(f"Parsing '{Path(pdf_path).name}' with Docling...")
    pipeline_options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    pipeline_options.table_structure_options.do_cell_matching = True

    doc_converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    result = doc_converter.convert(pdf_path)
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2b. Clean and Save Output ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    text_output = result.document.export_to_markdown()
    text_cleaned = re.sub(r"<!--\s*image\s*-->", "", text_output)

    with open(dst_path, "w", encoding="utf-8") as dst_file:
        dst_file.write(text_cleaned)
    logger.info(f"Text file saved to: '{Path(dst_path).name}'")

# #############################################################################

def extract_and_save_qa(input_filepath: Union[str, Path], output_filepath: Union[str, Path]):
    """
    Reads a text file, splits it into question blocks using a regex pattern,
    and saves the result as a list of dictionaries in a JSON file.

    Args:
        input_filepath (Union[str, Path]): Path to the source text file.
        output_filepath (Union[str, Path]): Path where the output JSON will be saved.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2c. Read and Split Content ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    input_filepath = Path(input_filepath)
    if not input_filepath.exists():
        raise FileNotFoundError(f"Error: The file '{input_filepath}' was not found.")

    with open(input_filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # *** CRITICAL FIX: This regex is now more flexible. ***
    # It handles "Question#10", "Question # 10", etc. by making spaces optional (`\s*`).
    split_pattern = r'(?=^[^\n]{0,10}\s*Question\s*#\s*\d+)'
    parts = re.split(split_pattern, content, flags=re.MULTILINE | re.IGNORECASE)

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2d. Structure and Validate Data ---
    # Create a list of dictionaries, one for each question block.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    qa_list: List[Dict[str, Any]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # This second regex for extraction is also made more flexible.
        num_match = re.search(r'Question\s*#\s*(\d+[a-zA-Z]?)', part, re.IGNORECASE)
        if num_match:
            question_number = num_match.group(1)
            qa_list.append({'question_number': question_number, 'block': part})
        else:
            # This helps debug cases where a block is split but a number isn't found
            if len(part) > 50: # Avoid logging tiny fragments
                logger.warning(f"Could not extract question number from block: {part[:100]}...")


    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2e. Save Structured Data to JSON ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    with open(output_filepath, 'w', encoding='utf-8') as f:
        json.dump(qa_list, f, indent=2)
    logger.info(f"Found and saved {len(qa_list)} questions to '{Path(output_filepath).name}'.")


# #############################################################################
# --- 3. JSON Handling Functions ---
# #############################################################################

def read_qa_from_json(input_filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Reads and parses a JSON file that contains a list of QA dictionaries.

    Args:
        input_filepath (Union[str, Path]): Path to the source JSON file.

    Returns:
        List[Dict[str, Any]]: A list of question dictionaries.
    """
    input_filepath = Path(input_filepath)
    if not input_filepath.exists():
        raise FileNotFoundError(f"Error: The file '{input_filepath}' was not found.")

    with open(input_filepath, 'r', encoding='utf-8') as f:
        qa_list = json.load(f)
    
    return qa_list

# #############################################################################

def get_question_numbers_from_json(json_path: Union[str, Path]) -> List[str]:
    """
    Reads a processed JSON file and extracts a list of all 'question_num' values.
    This is used to check which questions have already been processed to allow
    for resuming an interrupted job.

    Args:
        json_path (Union[str, Path]): Path to the JSON file.

    Returns:
        List[str]: A list of question numbers found in the file. Returns an empty
                   list if the file doesn't exist or is invalid.
    """
    json_path = Path(json_path)
    if not json_path.exists():
        return []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            logger.warning(f"File '{json_path.name}' does not contain a JSON list. Cannot get question numbers.")
            return []
        
        return [qa.get("question_num") for qa in data if "question_num" in qa]
    
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error reading or parsing '{json_path.name}': {e}")
        return []

# #############################################################################

def process_json_response(resp_data_file: Path, output_file_path: Path, is_first_question: bool) -> int:
    """
    Reads a single-question JSON response, appends it to the main processed
    JSON file, sorts the entire list by question number, and saves the result.

    Args:
        resp_data_file (Path): Path to the temporary JSON file from the AI agent.
        output_file_path (Path): Path to the final, aggregated `_processed.json` file.
        is_first_question (bool): True if this is the first record being added to the file.

    Returns:
        int: 0 for success, non-zero for failure.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 3a. Load New Response Data ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        with open(resp_data_file, 'r', encoding='utf-8') as f:
            resp_data = json.load(f)
        if not isinstance(resp_data, dict) or "question_num" not in resp_data:
            logger.error(f"Response in {resp_data_file.name} is not a valid dictionary or is missing 'question_num'.")
            return 1
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error reading or parsing agent response file '{resp_data_file.name}': {e}")
        return 2

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 3b. Load Existing Data ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    existing_data = []
    if not is_first_question and output_file_path.exists():
        try:
            with open(output_file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            if not isinstance(existing_data, list):
                logger.warning(f"'{output_file_path.name}' is malformed; starting a new list.")
                existing_data = []
        except json.JSONDecodeError:
            logger.warning(f"'{output_file_path.name}' is not valid JSON; starting a new list.")
            existing_data = []

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 3c. Append New Data (No Duplicates) ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    seen_nums = {qa.get("question_num") for qa in existing_data if qa.get("question_num")}
    if resp_data.get("question_num") not in seen_nums:
        existing_data.append(resp_data)
    else:
        logger.warning(f"Duplicate question_num {resp_data.get('question_num')} found. Skipping append.")

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 3d. Sort the Combined Data (As Requested) ---
    # This keeps the file sorted at all times. The key function handles
    # non-integer question numbers (e.g., '15a') gracefully.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    def sort_key(item):
        """
        A smart sort key that handles numbers and letters in 'question_num'.
        It explicitly converts the numeric part to an integer for correct sorting.
        """
        num_str = item.get("question_num", "0")
        
        # Use regex to find the leading numeric part of the string.
        match = re.match(r'(\d+)', str(num_str))
        
        if match:
            # Convert the found digits to an integer.
            num_part = int(match.group(1))
            # The rest of the string after the number is used for secondary sorting (e.g., 'a' in '15a').
            str_part = str(num_str)[len(match.group(1)):]
            return (num_part, str_part)
        
        # If no number is found, treat it as a low-priority string sort.
        # Placing malformed/non-numeric question numbers at the end.
        return (float('inf'), str(num_str))

    try:
        existing_data.sort(key=sort_key)
    except (ValueError, TypeError) as e:
        logger.error(f"Could not sort data by 'question_num'. Error: {e}")
        # We can still proceed without sorting if it fails.
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 3e. Write Updated Data to File ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4)
        return 0 # Success
    except PermissionError as e:
        logger.error(f"Permission error writing to '{output_file_path}': {e}")
        return 4