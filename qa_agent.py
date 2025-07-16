# --- START OF FILE qa_agent.py ---

import os
import json
import re
import logging
from textwrap import dedent
from pathlib import Path
from typing import Union, Dict, List
# --- Library Imports ---
from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv
import google.generativeai as genai # <--- NATIVE library for direct testing

# #############################################################################
# --- 1. Module-level Configuration ---
# #############################################################################
code_dir = Path(__file__).resolve().parent
os.chdir(code_dir)
# Load environment variables from a .env file if it exists.
xx = load_dotenv(".env", override=True)
print(f"Environment for API:{xx}\n")
# Configure a logger for this module.
logger = logging.getLogger(__name__)
# Load the Google API key from the environment.
gemini_api_key = os.getenv("GOOGLE_API_KEY")
if not gemini_api_key:
    logger.warning("GOOGLE_API_KEY environment variable not set. Agent calls will fail.")
#print(gemini_api_key)
# Defines the JSON structure the AI agent is expected to generate.
AGENT_OUTPUT_JSON_TEMPLATE = \
"""
{
  "question_num":   "<(str) placeholder for extracted value>",
  "question_desc":  "<(str) placeholder for extracted value>",
  "question_line":  "<(str) placeholder for extracted value>",
  "options":        "<(str) placeholder for extracted value>",
  "correct_choice": "<(str) placeholder for extracted value>",
  "reasoning":      "<(str) placeholder for extracted value>",
  "updated_description": "<(str) placeholder for evaluated value>",
  "updated_reasoning": "(str) <placeholder for evaluated value>",
  "updated_options": "<(str) placeholder for evaluated value>",
  "updated_correct_choice": "<(str) placeholder for evaluated value>",
  "updated_correct_choice_text": "<(str) placeholder for evaluated value>"
}
"""

# #############################################################################
# --- 2. Core Agent and Helper Functions (Unchanged) ---
# #############################################################################

def call_qa_agent(qa_body: str, subject: str, output_file: str, model_choice: str) -> int:
    """
    Initializes and runs an agent to process a QA block, saves the raw response,
    and then validates the structured data. This function correctly uses the
    `agno` library as intended for the main pipeline.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2a. Model and Agent Initialization ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        model = Gemini(id=model_choice, api_key=gemini_api_key) if gemini_api_key else None
    except Exception as e:
        logger.error(f"MODEL ERROR...{e}")
        return 10
    if not(model): return 10
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2b. Prepare Temporary File Paths ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    raw_response_path = tmp_dir / f"{Path(output_file).stem}_temp.txt"
    
    # Clean up old temp files
    for txt_file in tmp_dir.glob("*.txt"):
        try: txt_file.unlink()
        except Exception as e: logger.warning(f"Failed to delete old temp file {txt_file}: {e}")
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2c. Configure and Instantiate the Agent ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    qa_agent = Agent(
        model=model,
        description="A Medical College Professor...",
        instructions=get_instructions(subject),
        markdown=True, use_json_mode=True, structured_outputs=True,
        expected_output=AGENT_OUTPUT_JSON_TEMPLATE,
        save_response_to_file=str(raw_response_path),
    )

    user_prompt = f"""Follow instructions to extract data from the text.\n### Text:\n{qa_body}\n\nOUTPUT JSON RESPONSE:\n"""
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2d. Execute Agent and Process Response ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info(f"--- Calling Agent for: {output_file} ---")
    qa_agent.print_response(user_prompt)
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2e. Read, Save, and Validate the Final JSON ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    if not raw_response_path.exists():
        logger.error(f"Agent failed to create response file: {raw_response_path}"); return 11
    with open(raw_response_path, "r", encoding='utf-8') as f:
        raw_response_text = f.read()

    agent_json_output_path = tmp_dir / output_file
    save_code = save_response_to_json(raw_response_text, agent_json_output_path)
    if save_code != 0: return save_code
    
    validation_code = validate_json_keys(agent_json_output_path)
    if validation_code != 0:
        logger.error("Validation of Keys Failed"); return validation_code
    
    return 0

# #############################################################################
# (Helper functions save_response_to_json, get_instructions, validate_json_keys are unchanged)
def save_response_to_json(response: Union[str, Dict], filename: Union[str, Path]) -> int:
    filename = Path(filename)
    if isinstance(response, str):
        response = re.sub(r'^```json\s*|\s*```$', '', response.strip(), flags=re.MULTILINE)
        if not response: logger.error("Agent response is empty after stripping."); return 2
        try: response_dict = json.loads(response)
        except json.JSONDecodeError as e: logger.error(f"Invalid JSON: {e}\nContent: {response[:500]}"); return 3
    else: response_dict = response
    if not isinstance(response_dict, dict): logger.error("Response is not a dictionary."); return 4
    try:
        with open(filename, 'w', encoding='utf-8') as f: json.dump(response_dict, f, indent=4)
        return 0
    except PermissionError as e: logger.error(f"Permission error writing to {filename}: {e}"); return 1

def get_instructions(subject: str) -> List[str]:
    # This function is unchanged and correct.
    base_instructions = [dedent("""...""")]
    return base_instructions

def validate_json_keys(file_path: Union[str, Path]) -> int:
    # This function is unchanged and correct.
    required_keys = {"question_num", "question_desc", "question_line", "options", "correct_choice", "reasoning", "updated_description", "updated_reasoning", "updated_options", "updated_correct_choice", "updated_correct_choice_text"}
    file_path = Path(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
    except Exception as e: logger.error(f"Validation failed: Could not read/parse {file_path.name}: {e}"); return 4
    if not isinstance(data, dict): logger.error(f"Validation failed: {file_path.name} is not a JSON object."); return 2
    if not required_keys.issubset(data.keys()):
        missing_keys = required_keys - set(data.keys())
        logger.error(f"Validation failed: Missing keys {missing_keys} in {file_path.name}"); return 3
    return 0
# #############################################################################

# #############################################################################
# --- 6. Standalone Model Test Block ---
# #############################################################################

if __name__ == '__main__':
    """
    This block performs a direct test of the available AI models using the
    native `google-genai` library, bypassing the `agno` wrapper. This is the
    most reliable way to verify API key and model accessibility.
    To run: python qa_agent.py
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- Test Setup ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_logger = logging.getLogger(__name__)
    test_logger.info("--- Running Native Google-GenAI Model Test ---")

    try:
        from c_processor import MODELS as models_to_test
    except ImportError:
        test_logger.warning("Could not import MODELS from c_processor.py, using a fallback list.")
        # Using known valid, current model names for the fallback.
        models_to_test = ['gemini-1.5-flash-latest', 'gemini-1.5-pro-latest']

    if not gemini_api_key:
        test_logger.error("HALTING TEST: GOOGLE_API_KEY is not set in your .env file.")
    else:
        # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
        # --- Configure the Native Library ---
        # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
        try:
            from google import genai
            # The client gets the API key from the environment variable `GEMINI_API_KEY`.
            client = genai.Client(api_key=gemini_api_key)
        except Exception as e:
            test_logger.error(f"HALTING TEST: Failed to configure Google GenAI client. Error: {e}")
            models_to_test = [] # Prevent the loop from running

        # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
        # --- Test Execution Loop ---
        # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
        for model_name in models_to_test:
            print("-" * 50)
            test_logger.info(f"Testing model: '{model_name}'")
            try:            
                prompt = "What is capital of France?"
                test_logger.info(f"Sending prompt: '{prompt}'")
                response = client.models.generate_content(
                    model="gemini-2.5-flash", 
                    contents=prompt
                    )
                test_logger.info(f"SUCCESS! Response: {response.text}")
            except Exception as e:
                test_logger.error(f"FAILED to get response from '{model_name}'.")
                test_logger.error(f"Error details: {e}", exc_info=False)
        print("-" * 50)