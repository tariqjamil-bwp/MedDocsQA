# --- START OF FILE b_parser.py ---

import os
from pathlib import Path
import logging
from typing import Union

# We import get_paths here only for the standalone testing block at the end.
# In the main pipeline, 'paths' is passed in from main.py.
from utils import get_paths, extract_and_save_qa

# Get the logger for this module. The logger is configured in main.py.
logger = logging.getLogger(__name__)

# #############################################################################
# #############################################################################

def main(paths, subject_file: Union[str, Path], overwrite: bool = True) -> Union[Path, None]:
    """
    Parses a single text file from the '1Texted' directory, splits it into
    question blocks based on a regex pattern, and saves the structured data
    as a single JSON file in the '2Parsed' directory.

    Args:
        paths (ProjectPaths): A dataclass object with all necessary project paths.
        subject_file (Union[str, Path]): The name of the text file to process (e.g., "Cardiology.txt").
        overwrite (bool): If True, existing JSON files will be overwritten. Defaults to True.

    Returns:
        Union[Path, None]: The path to the created JSON file, or None if an error occurred.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1. Initialization and Setup ---
    # Define file extensions and get the relevant directory paths from the 'paths' object.
    # Using pathlib.Path ensures that all paths are handled correctly on any OS, including Windows.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info(f"--- Starting Text to JSON Parsing for: {subject_file} ---")
    SRC_EXT = ".txt"
    DST_EXT = ".json"
    src_dir = paths.TEXTED_DIR
    dst_dir = paths.PARSED_DIR

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2. Input File Validation ---
    # Extract the base name (subject) and extension from the input file.
    # This handles both string and Path objects gracefully.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # Using Path() makes this robust for different input types and OSes.
    input_path = Path(subject_file)
    subject = input_path.stem  # e.g., "Cardiology"
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 3. Directory and File Path Construction ---
    # Create the full, absolute paths for the source and destination files.
    # Ensure the destination directory exists.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    dst_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Source Directory: {src_dir}")
    logger.info(f"Destination Directory: {dst_dir}")

    # Construct the full paths for source and destination files.
    src_file_path = src_dir / f"{subject}{SRC_EXT}"
    dst_file_path = dst_dir / f"{subject}{DST_EXT}"

    # Verify that the source text file actually exists before proceeding.
    if not src_file_path.exists():
        logger.error(f"Source file not found at the expected path: {src_file_path}")
        return None

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 4. Overwrite Check ---
    # If the destination file already exists and we are not in overwrite mode,
    # log it and exit gracefully.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    if dst_file_path.exists() and not overwrite:
        logger.info(f"Destination file '{dst_file_path.name}' already exists. Skipping.")
        return dst_file_path

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 5. Text Parsing and JSON Saving ---
    # Call the utility function to perform the actual parsing and save the result.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info(f"Parsing: '{src_file_path.name}' -> '{dst_file_path.name}'")
    try:
        extract_and_save_qa(src_file_path, dst_file_path)
        logger.info(f"Successfully parsed and saved questions to '{dst_file_path.name}'.")
    except Exception as e:
        logger.error(f"Failed to parse '{src_file_path.name}'. Error: {e}")
        return None

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 6. Finalization ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info("--- Parsing Step Completed! ---\n")
    return dst_file_path

# #############################################################################
# #############################################################################

if __name__ == "__main__":
    """
    This block allows the script to be run directly for testing purposes.
    It sets up minimal configuration for paths and logging to test the 'main' function.
    To run, execute 'python b_parser.py' from your code directory.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- Standalone Test Setup ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # Define project root and name for testing.
    # Path(__file__).resolve().parent gives the 'code' directory.
    _user_projects_root = Path(__file__).resolve().parent
    _project_name = "DRHASSAN"
    
    # Configure basic logging for console output.
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info(f"--- Running {Path(__file__).name} in Standalone Test Mode ---")
    
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- Test Execution ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        # Get the project paths dataclass.
        _paths = get_paths(_user_projects_root, _project_name)
        
        # Call the main function with a test file and overwrite enabled.
        # main(paths=_paths, subject_file="Endocrinology.txt", overwrite=True)
        main(paths=_paths, subject_file="Endocrinology.txt", overwrite=True)
        main(paths=_paths, subject_file="Cardiology.txt", overwrite=True)

    except FileNotFoundError as e:
        logger.error(f"Setup Error: Could not find project '{_project_name}'. {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the test run: {e}")