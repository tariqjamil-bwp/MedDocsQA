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
# --- 2. Core Agent and Helper Functions ---
# #############################################################################

def call_qa_agent(
    qa_body: str,
    subject: str,
    model_choice: str,
    output_file: Path  # This is the final destination for the clean JSON
) -> int:
    """
    Initializes and runs an agent to process a QA block.
    It internally creates a temporary file for the raw agent response and cleans up afterward.
    The final, clean JSON is saved to the 'output_file' path provided by the caller.
    """
    # --- Model Initialization ---
    try:
        model = Gemini(id=model_choice, api_key=gemini_api_key) if gemini_api_key else None
        if not model:
            logger.error("Failed to initialize Gemini model. API key might be missing or invalid.")
            return 10
    except Exception as e:
        logger.error(f"MODEL ERROR: Could not instantiate Gemini model. Details: {e}")
        return 10

    # --- Internal temporary file management ---
    # The raw text file is an implementation detail of this function.
    raw_response_path = output_file.with_name(f"{output_file.stem}_temp_raw.txt")

    # Clean up old temp file if it exists from a previous failed run
    if raw_response_path.exists():
        try:
            raw_response_path.unlink()
        except Exception as e:
            logger.warning(f"Could not delete old temp file {raw_response_path.name}: {e}")

    # --- Configure and Instantiate the Agent ---
    qa_agent = Agent(
        model=model,
        description="A Medical College Professor...",
        instructions=get_instructions(subject),
        markdown=True, use_json_mode=True, structured_outputs=True,
        expected_output=AGENT_OUTPUT_JSON_TEMPLATE,
        save_response_to_file=str(raw_response_path), # Agent saves to our internal temp file
    )

    user_prompt = f"""Follow instructions to extract data from the text.\n### Text:\n{qa_body}\n\nOUTPUT JSON RESPONSE:\n"""

    # --- Execute Agent and Process Response ---
    logger.info(f"--- Calling Agent for question in: {subject} ---")
    qa_agent.print_response(user_prompt)

    # --- Read, Save, and Validate the Final JSON ---
    if not raw_response_path.exists():
        logger.error(f"Agent failed to create its raw response file: {raw_response_path}")
        return 11

    with open(raw_response_path, "r", encoding='utf-8') as f:
        raw_response_text = f.read()

    # Save the cleaned response to the final destination path provided by the caller
    save_code = save_response_to_json(raw_response_text, output_file)

    # --- Automatic Cleanup ---
    # Clean up the internal temporary file now that we're done with it.
    if raw_response_path.exists():
        raw_response_path.unlink()

    if save_code != 0:
        return save_code

    # Validate the final, clean JSON file
    validation_code = validate_json_keys(output_file)
    if validation_code != 0:
        logger.error("Validation of agent's output JSON keys failed.")
        return validation_code

    return 0

def save_response_to_json(response: Union[str, Dict], filename: Union[str, Path]) -> int:
    """Saves a raw text response to a clean JSON file."""
    filename = Path(filename)
    if isinstance(response, str):
        # Strip Markdown code fences for JSON
        response = re.sub(r'^```json\s*|\s*```$', '', response.strip(), flags=re.MULTILINE)
        if not response:
            logger.error("Agent response is empty after stripping markdown fences."); return 2
        try:
            response_dict = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received from agent: {e}\nContent snippet: {response[:500]}"); return 3
    else:
        response_dict = response

    if not isinstance(response_dict, dict):
        logger.error("Processed agent response is not a dictionary."); return 4

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response_dict, f, indent=4)
        return 0
    except (IOError, PermissionError) as e:
        logger.error(f"File system error writing to {filename}: {e}"); return 1


def get_instructions(subject: str) -> List[str]:
    INSTRUCTIONS = [
        dedent("""
        **Persona:** You are a meticulous Medical College Professor specializing in creating and analyzing exam questions.
        Your task is to deconstruct a given medical question-answer block into its core components.
        """),
        
        dedent("""
        **Input Analysis:**
        You will receive a text block containing the following parts, which you must identify and segregate:
        - `question_num`: {str) The identifier for the question in str form with quotes (e.g., "1","2" etc. ). Only extract digit part of the string after Question # <digit>.
        - `question_desc`: (str) The clinical scenario or background information.
        - `question_line`: (str) The specific question, usually ending with a question mark.
        - `options`: upto 8 enumerated lines containing multiple-choice answers, starting with numerals, e.g., 'a)', 'b)', etc.
        - `correct_choice`: (str) A short statement identifying the correct option (e.g., "Correct answer is a.").
        - `reasoning`: (str) The detailed explanation of the reasonong behind correct choice, and possibly reasons why incorrect choices are not logical. 
        """),
        
        dedent("""**IMPORTANT**: 'DO NOT MODIFY THE ORIGINAL TEXT, OR ADD YOUR OWN COMMENTARY'"""),
        
        dedent("""
        **Output Generation:**
        The Output should be in Markdown format as per output template. 
        *INSTRUCTIONS*:
        Additionally, you will create two modified fields alongside the original fields:
        1.  `updated_description`: (str) Rewrite the `question_desc` to be more concise. Remove filler words or less critical information while retaining the core clinical details.
        2.  updated_reasoning': (str) Summarize the `reasoning`. Focus on the primary justification for the correct answer and briefly state why the main distractors are incorrect.
        3. remove any preceeding characters before 'choice' numerals in options, e.g. '-' or whitespaces."""),
        
        dedent("""
        **Options Handling:**
        1. If the 'options' numerals errorneously doesn't start with 1st numeral in series (e.g. 'a', '1', 'i' as the case may be), CORRECT them to start with 1st numeral in the series and follow the sequence. Usually it does not require 'correct_choice' line adjustment.
        
        2. Rearrange Options values in Alphabetical Order and reassign numeral in the series starting with 1st numeral in series. 
        
        3. While performing the above actions, MAKE SURE that 'correct_choice' line also reflects the change and point to the correct choice numeral.
        
        4. Remember the modified (from above 1,2) choice_lines as 'updated_options' (str) for expected_output format.
        5. Remember the modified (from above 3) 'correct_choice' line as 'updated_correct_choice' (str) for expected_output format.
        6. Create a new field 'correct_choice_text' (str) by appropriate referencing the correct_choice to the 'updated_options' for expected_output format.
        4. Ensure that each of the choice under Option is placed at a separate new line.
        
        OPTIONS EXAMPLE:
        Options: (original)
        f) Partial or absence seizures
        g) Botulinum toxicity
        h) Guillain-Barre syndrome
        
        'Correct Choice' is b.
        
        CHAIN OF THOUGHT:
        step 1. correct the sequence to start with 1st series letter.
        Options:
        a) Partial or absence seizures
        b) Botulinum toxicity
        c) Guillain-Barre syndrome
        
        'Correct Choice' is b. (PRESERVE its value: 'Botulinum toxicity'). 
        
        step 2: Rearrange in alphabetical order
        Options:
        a) Botulinum toxicity
        b) Guillain-Barre syndrome
        c) Partial or absence seizures
        
        Step 3: Think of 'correct choice' line. It was pointing to 'Botulinum toxicity'. Now that choice has moved to position 'a)'
        'updated_correct_choice' is 'a'
        
        step 4: Consolidate 
        Options:
        a) Botulinum toxicity
        b) Guillain-Barre syndrome
        c) Partial or absence seizures
        
        'updated_correct_choice' is 'a'
        'updated_correct_choice_text': "Botulinum toxicity" 
        
        """),

        dedent("""
        **Final Checks:**
        - Ensure your entire output is in JSON OBJECT FORMAT.
        - All keys/fields must be present.
        - The content for each field must be accurately extracted or generated as per these instructions.
        """),       
    ]
    
    new_instr = []
    if os.path.exists("xtra_instrcutions.txt"):
        with open('xtra_instrcutions.txt') as f:
            new_instr = f.readlines()
    
    if new_instr:
        return INSTRUCTIONS+new_instr
    
    return INSTRUCTIONS

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