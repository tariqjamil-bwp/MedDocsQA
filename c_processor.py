# --- START OF FILE c_processor.py ---

import os
from pathlib import Path
import logging
from typing import Union
import time
import sys

# --- Project-specific Imports ---
from qa_agent import call_qa_agent
from utils import process_json_response, get_question_numbers_from_json, read_qa_from_json, get_paths
from utils_model import get_available_gemini_models
from agno.exceptions import ModelProviderError

# Get the logger for this module. The root logger is configured in your main app.
logger = logging.getLogger(__name__)

# --- Module-level Configuration ---
# This list is lazy-loaded on the first actual agent call.
MODELS = []

# #############################################################################
# --- Main Processor Function ---
# #############################################################################

def main(paths, subject_file: Union[str, Path], overwrite: bool = True):
    """
    Processes a parsed JSON file of question blocks, calling an AI agent for each.
    This script is resilient to interruptions and API failures.

    Args:
        paths (ProjectPaths): A dataclass object with all project paths.
        subject_file (Union[str, Path]): The name of the JSON file from the '2Parsed'
                                         directory (e.g., "Cardiology.json").
        overwrite (bool): If True, will clear the final processed JSON file and
                          start from scratch. Defaults to True.
    """
    # --- 1. Initialization and Path Setup ---
    logger.info(f"--- Starting AI Processing for: {subject_file} ---")
    if not subject_file:
        raise ValueError("A 'subject_file' (e.g., 'Cardiology.json') must be provided.")

    src_file_path = paths.PARSED_DIR / subject_file
    subject = src_file_path.stem
    final_output_file_path = paths.PROCESSED_DIR / f"{subject}_processed.json"
    paths.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # --- 2. Load Source Questions ---
    if not src_file_path.exists():
        logger.error(f"Source file not found: {src_file_path}")
        return
    logger.info(f"Loading questions from: '{src_file_path.name}'")
    qa_list = read_qa_from_json(input_filepath=src_file_path)
    if not qa_list:
        logger.warning(f"No questions found in '{src_file_path.name}'. Nothing to process.")
        return

    # --- 3. Handle Overwrite and Resume Logic ---
    if overwrite and final_output_file_path.exists():
        logger.info(f"Overwrite is True. Deleting existing file: {final_output_file_path.name}")
        final_output_file_path.unlink()
    questions_in_json = get_question_numbers_from_json(final_output_file_path)
    is_first_question = not bool(questions_in_json)
    logger.info(f"Found {len(questions_in_json)} already processed questions which will be skipped.")

    # --- 4. Main Processing Loop ---
    last_successful_model_idx = 0
    try:
        for question in qa_list:
            qa_no = question.get('question_number')
            qa_body = question.get('block', "NIL")

            if qa_no in questions_in_json:
                logger.info(f"Question {qa_no} already exists. Skipping.")
                continue

            # --- Lazy Loading of Models ---
            global MODELS
            if not MODELS:
                logger.info("First agent call. Fetching available Gemini models...")
                MODELS = get_available_gemini_models()
                if not MODELS:
                    logger.error("No available models found. Cannot proceed. Check API key and connectivity.")
                    return
                logger.info(f"Models acquired: {MODELS}")

            logger.info(f"--- Processing Question {qa_no}/{len(qa_list)} from file {subject} ---")

            # --- Centralized and Simplified Path Management ---
            # Define a temporary directory within the project for intermediate files.
            tmp_dir = paths.UPROJ_DIR / "tmp"
            tmp_dir.mkdir(exist_ok=True)

            # Define the ONE destination path for the final, clean JSON from the agent.
            agent_json_output_path = tmp_dir / f"{subject.lower()}_qa{qa_no}.json"

            # --- Resilient AI Agent Call with Retries ---
            resp_code = -1
            max_retries = 5
            base_delay_seconds = 10
            for attempt in range(max_retries):
                # Cycle through available models on each retry
                model_to_try = MODELS[(last_successful_model_idx + attempt) % len(MODELS)]
                try:
                    logger.info(f"Attempt {attempt + 1}/{max_retries}: Calling Agent with model: '{model_to_try}'")
                    
                    # --- Simplified function call ---
                    resp_code = call_qa_agent(
                        qa_body=qa_body,
                        subject=subject,
                        model_choice=model_to_try,
                        output_file=agent_json_output_path # Pass the single destination path
                    )
                    
                    if resp_code == 0:
                        logger.info(f"Agent call successful with '{model_to_try}'.")
                        last_successful_model_idx = MODELS.index(model_to_try)
                        break # Exit retry loop on success
                    else:
                        logger.warning(f"Agent call failed with code {resp_code}. Retrying...")

                except ModelProviderError as e:
                    if '429' in str(e): # Handle rate limiting
                        delay = base_delay_seconds * (2 ** attempt)
                        logger.warning(f"Rate limit exceeded (429). Waiting {delay} seconds before retrying...")
                        time.sleep(delay)
                    else:
                        logger.error(f"A ModelProviderError occurred: {e}. Trying next model.", exc_info=False)
                except Exception as e:
                    logger.error(f"An unexpected exception occurred during agent call: {e}. Retrying.", exc_info=True)

            # --- Process Agent Response ---
            if resp_code != 0:
                logger.error(f"Failed to get a valid response for question {qa_no} after all retries. Skipping.")
                continue

            # Merge the temporary JSON into the final aggregated file
            ret_code = process_json_response(agent_json_output_path, final_output_file_path, is_first_question)

            if ret_code == 0:
                is_first_question = False
                questions_in_json.append(str(qa_no))
                # Clean up the successful intermediate file
                #if agent_json_output_path.exists():
                #    agent_json_output_path.unlink()
                logger.error(f"Processed response for Question {qa_no} successfully written to file: {final_output_file_path}\n")
            else:
                logger.error(f"Failed to save processed response for Question {qa_no}.\nThe temp file will be kept for debugging at: {agent_json_output_path}")

            time.sleep(2) # Brief pause to respect API rate limits between questions

    except KeyboardInterrupt:
        logger.warning("\n--- KEYBOARD INTERRUPT DETECTED. Stopping AI processing gracefully. ---")
        sys.exit(0)

    # --- 5. Finalization ---
    logger.info(f"--- AI Processing Step Completed for {subject}! ---\n")

# #############################################################################
# --- Standalone Test Block ---
# #############################################################################
if __name__ == "__main__":
    # This block allows you to run this script directly for testing purposes.
    _user_projects_root = Path(__file__).resolve().parent
    _project_name = "DRHASSAN" # Default project for testing
    
    # Configure logging for standalone run
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logger.info(f"--- Running {Path(__file__).name} in Standalone Test Mode ---")
    
    try:
        _paths = get_paths(_user_projects_root, _project_name)
        # Example call: process Cardiology.json, but don't overwrite if it exists (for resume testing)
        main(paths=_paths, subject_file="Cardiology.json", overwrite=False)
    except FileNotFoundError as e:
        logger.error(f"Setup Error: Could not find project '{_project_name}'. Please ensure the folder exists. Details: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the standalone test run: {e}", exc_info=True)

# --- END OF FILE c_processor.py ---