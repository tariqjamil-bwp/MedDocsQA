# --- START OF FILE main.py ---

import os
import logging
from pathlib import Path
from typing import Union

# Import the main functions from the pipeline modules
from a_converter import main as run_converter
from b_parser import main as run_parser
from c_processor import main as run_processor
from utils import get_paths
from utils2 import convert_json_to_docx, sort_json_file

# #############################################################################
# --- Main Pipeline Orchestrator ---
# #############################################################################

def main(project_name: str, subject_file: Union[str, Path], overwrite_steps: bool = False):
    """
    Main workflow orchestrator for the document processing pipeline.

    This function executes the following steps in sequence:
    1.  Setup: Configures paths and logging.
    2.  Converter: Converts a source PDF to a text file.
    3.  Parser: Parses the text file into a structured JSON of question blocks.
    4.  Processor: Uses an AI agent to process each question block into a final, detailed JSON.
    5.  Output Generation: Creates final DOCX outputs from the processed JSON.

    Args:
        project_name (str): The name of the project folder inside the 'Projects' directory.
        subject_file (Union[str, Path]): The name of the source PDF file (e.g., "Cardiology.pdf").
        overwrite_steps (bool): If True, allows intermediate steps to overwrite existing files.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1. SETUP: Paths and Logging ---
    # Establish a consistent environment for the application to run in.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    code_dir = Path(__file__).resolve().parent
    os.chdir(code_dir)  # Set CWD to the 'code' directory for consistent relative paths

    # Configure logging to write to both a file and the console.
    log_dir = code_dir / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f'{project_name}.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a'), # Append to the log file
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info(f"===========================================================")
    logger.info(f"--- Starting New Pipeline Run for Project: {project_name} ---")
    logger.info(f"Current Working Directory: {os.getcwd()}")

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2. PATHS and PRE-FLIGHT CHECKS ---
    # Get all project paths and verify the source file exists before starting.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        paths = get_paths(code_dir, project_name)
    except FileNotFoundError as e:
        logger.error(f"HALTING: Project setup failed. {e}")
        return

    # *** CRITICAL: Ensure the initial source PDF exists before doing any work. ***
    source_pdf_path = paths.SRCFILE_DIR / subject_file
    if not source_pdf_path.exists():
        logger.error(f"HALTING: Source file not found at '{source_pdf_path}'. Please check the filename and location.")
        return

    subject = source_pdf_path.stem  # e.g., "Cardiology"
    logger.info(f"Processing Subject: {subject}")
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 3. WORKFLOW EXECUTION ---
    # Each step depends on the successful completion of the previous one.
    # If a step returns None, it indicates failure, and the pipeline halts.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    
    # --- Step 3a: Converter (PDF -> Text) ---
    texted_file_path = run_converter(paths=paths, subject_file=source_pdf_path, overwrite=overwrite_steps)
    if not texted_file_path:
        logger.error("HALTING: PDF to Text conversion failed. See logs above.")
        return

    # --- Step 3b: Parser (Text -> JSON Blocks) ---
    json_parsed_path = run_parser(paths=paths, subject_file=texted_file_path, overwrite=overwrite_steps)
    if not json_parsed_path:
        logger.error("HALTING: Text to JSON parsing failed. See logs above.")
        return

    # --- Step 3c: Processor (JSON Blocks -> Final Processed JSON) ---
    # The processor handles its own overwrite logic internally for resuming jobs.
    run_processor(paths=paths, subject_file=json_parsed_path.name, overwrite=overwrite_steps)
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 4. OUTPUT GENERATION ---
    # Create the final .docx files from the processed data.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info("--- Starting Final Output Generation ---")
    json_processed_path = paths.PROCESSED_DIR / f"{subject}_processed.json"
    
    if not json_processed_path.exists():
        logger.warning(f"Could not find processed file '{json_processed_path.name}'. Skipping DOCX generation.")
        return
        
    # --- 4a: Create Unsorted DOCX ---
    logger.info("Creating DOCX from original (numerically sorted) order...")
    docx_path_unsorted = paths.OUTPUT_DIR / f"{subject}_processed_numeric_order.docx"
    convert_json_to_docx(json_processed_path, docx_path_unsorted)
    
    # --- 4b: Sort by a different key (e.g., Correct Choice Text) ---
    logger.info("Sorting processed JSON by correct choice text...")
    json_sorted_path = paths.PROCESSED_DIR / f"{subject}_processed_sorted_by_choice.json"
    sort_json_file(
        input_path=json_processed_path,
        output_path=json_sorted_path,
        sort_key="updated_correct_choice_text"
    )

    # --- 4c: Create Sorted DOCX ---
    if json_sorted_path.exists():
        logger.info("Creating DOCX from text-sorted data...")
        docx_path_sorted = paths.OUTPUT_DIR / f"{subject}_processed_sorted_by_choice.docx"
        convert_json_to_docx(json_sorted_path, docx_path_sorted)
    else:
        logger.warning(f"Could not find sorted file '{json_sorted_path.name}' to convert.")

    logger.info("--- Pipeline Finished Successfully! ---")
    logger.info(f"===========================================================\n")

# #############################################################################
# --- Script Entry Point ---
# #############################################################################

if __name__ == "__main__":
    """
    This block is the main entry point when running the script from the command line.
    Define your project and source file here.
    """
    # --- Configuration ---
    PROJECT_NAME = "DRHASSAN"
    SUBJECT_FILE = "Cardiology.pdf"
    
    # Set to True to force all steps to re-run and overwrite existing files.
    # Set to False to allow steps to skip if their output already exists (faster).
    OVERWRITE_EXISTING_FILES = False

    # --- Execution ---
    main(project_name=PROJECT_NAME, subject_file=SUBJECT_FILE, overwrite_steps=OVERWRITE_EXISTING_FILES)