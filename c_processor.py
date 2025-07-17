# --- START OF FILE c_processor.py ---

import os
from pathlib import Path
import logging
from typing import Union
import time
import sys # Import sys for exiting

from qa_agent import call_qa_agent
from utils import process_json_response, get_question_numbers_from_json, read_qa_from_json, get_paths
from agno.exceptions import ModelProviderError
from utils_model import get_available_gemini_models
# Get the logger for this module. The logger is configured in main.py.
logger = logging.getLogger(__name__)

# #############################################################################
# --- Module-level Configuration ---
# #############################################################################
MODELS = [] # Lazy-loaded
# #############################################################################
# --- Main Processor Function ---
# #############################################################################
def main(paths, subject_file: Union[str, Path], overwrite: bool = True):
    """
    Processes a parsed JSON file of question blocks. For each question, it calls
    an AI agent to extract structured data, then compiles the results into a
    single, final JSON file in the '3Processed' directory.

    This script is resilient:
    - It can resume an interrupted job, skipping already processed questions.
    - It cycles through multiple AI models if one fails.
    - It handles API rate limiting (429 errors) by waiting and retrying.

    Args:
        paths (ProjectPaths): A dataclass object with all project paths.
        subject_file (Union[str, Path]): The name of the JSON file from the '2Parsed'
                                         directory (e.g., "Cardiology.json").
        overwrite (bool): If True, will clear the final processed JSON file and
                          start from scratch. Defaults to True.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1. Initialization and Path Setup ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info(f"--- Starting AI Processing for: {subject_file} ---")
    if not subject_file:
        raise ValueError("A 'subject_file' (e.g., 'Cardiology.json') must be provided.")

    src_dir = paths.PARSED_DIR
    dst_dir = paths.PROCESSED_DIR
    dst_dir.mkdir(parents=True, exist_ok=True)

    src_file_path = src_dir / subject_file
    subject = src_file_path.stem
    final_output_file_path = dst_dir / f"{subject}_processed.json"

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2. Load Source Questions ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    if not src_file_path.exists():
        logger.error(f"Source file not found: {src_file_path}")
        return

    logger.info(f"Loading questions from: '{src_file_path.name}'")
    qa_list = read_qa_from_json(input_filepath=src_file_path)
    if not qa_list:
        logger.warning(f"No questions found in '{src_file_path.name}'. Nothing to process.")
        return

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 3. Handle Overwrite and Resume Logic ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    if overwrite and final_output_file_path.exists():
        logger.info(f"Overwrite is True. Deleting existing file: {final_output_file_path.name}")
        final_output_file_path.unlink()
        
    questions_in_json = get_question_numbers_from_json(final_output_file_path)
    is_first_question = not bool(questions_in_json)
    logger.info(f"Found {len(questions_in_json)} already processed questions.")

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 4. Main Processing Loop ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    last_successful_model_idx = 0
    try: # --- ADDED: Start of try block for KeyboardInterrupt ---
        for question in qa_list:
            qa_no = question.get('question_number')
            qa_body = question.get('block', "NIL")

            if qa_no in questions_in_json:
                logger.info(f"Question {qa_no} already exists in target file. Skipping.")
                continue
            
            # --- Lazy Loading of Models ---
            global MODELS
            if not MODELS:
                logger.info("First agent call. Fetching available Gemini models...")
                MODELS = get_available_gemini_models()
                if not MODELS:
                    logger.error("No available models found. Cannot proceed. Check API key and connectivity.")
                    return # Stop if no models are found
                logger.info(f"Models acquired: {MODELS}")

            logger.info(f"--- Processing Question {qa_no} from file {subject} ---")
            
            # --- 4b. Resilient AI Agent Call with Rate Limit Handling ---
            agent_output_file = paths.UPROJ_DIR / "tmp" / f"{subject.lower()}_qa{qa_no}.json"
            resp_code = -1
            
            max_retries = 5
            base_delay_seconds = 10

            for attempt in range(max_retries):
                model_to_try = MODELS[(last_successful_model_idx + (attempt % len(MODELS))) % len(MODELS)]
                
                try:
                    logger.info(f"Attempt {attempt + 1}/{max_retries}: Executing Agent using model: '{model_to_try}'")
                    resp_code = call_qa_agent(
                        qa_body=qa_body,
                        subject=subject,
                        output_file=agent_output_file.name,
                        model_choice=model_to_try,
                    )
                    if resp_code == 0:
                        logger.info(f"Agent call successful with '{model_to_try}'.")
                        last_successful_model_idx = MODELS.index(model_to_try)
                        break 
                    else:
                        logger.warning(f"Agent call failed with code {resp_code}. Retrying...")
                
                except ModelProviderError as e:
                    if '429' in str(e):
                        delay = base_delay_seconds * (2 ** attempt)
                        logger.warning(f"Rate limit exceeded (429). Waiting for {delay} seconds before retrying...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"A non-rate-limit ModelProviderError occurred: {e}. Trying next model/retry.", exc_info=False)
                
                except Exception as e:
                    logger.error(f"An unexpected exception occurred during call_qa_agent: {e}. Retrying.", exc_info=True)

            # --- 4c. Process Agent Response ---
            if resp_code != 0:
                logger.error(f"Failed to get a valid response for question {qa_no} after {max_retries} attempts. Skipping.")
                continue

            ret_code = process_json_response(agent_output_file, final_output_file_path, is_first_question)
            
            # --- 4d. Update State on Success ---
            if ret_code == 0:
                is_first_question = False
                questions_in_json.append(str(qa_no))
            else:
                logger.error(f"Failed to save processed response for Question {qa_no}. Skipping.")
            
            time.sleep(2)
            
    except KeyboardInterrupt: # --- ADDED: Catch Ctrl+C ---
        logger.warning("\n--- KEYBOARD INTERRUPT DETECTED. Stopping AI processing gracefully. ---")
        sys.exit(0) # Exit the script cleanly

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 5. Finalization ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info(f"--- AI Processing Step Completed for {subject}! ---\n")

# #############################################################################
# (The __main__ block for standalone testing remains the same)
# #############################################################################
if __name__ == "__main__":
    _user_projects_root = Path(__file__).resolve().parent
    _project_name = "DRHASSAN"
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info(f"--- Running {Path(__file__).name} in Standalone Test Mode ---")
    try:
        _paths = get_paths(_user_projects_root, _project_name)
        main(paths=_paths, subject_file="Cardiology.json", overwrite=False)
    except FileNotFoundError as e:
        logger.error(f"Setup Error: Could not find project '{_project_name}'. {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the test run: {e}", exc_info=True)