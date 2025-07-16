# --- START OF FILE app.py ---

import streamlit as st
from pathlib import Path
import logging
import time
import json
import os
import sys
import subprocess

# --- Import your project's functions ---
# These imports assume app.py is in the same 'code' directory as the other scripts.
from utils import get_paths, ProjectPaths
from utils2 import convert_json_to_docx, sort_json_file
import a_converter
import b_parser
import c_processor

# #############################################################################
# --- UI HELPER FUNCTIONS ---
# #############################################################################

def get_next_filename(path: Path) -> Path:
    """
    Checks if a file exists. If so, it appends a number (e.g., file_1.txt).
    """
    if not path.exists():
        return path
    
    i = 1
    while True:
        new_path = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not new_path.exists():
            return new_path
        i += 1

def open_file_in_explorer(path: Path):
    """
    Opens the file's containing directory in the system's file explorer.
    Works on Windows, macOS, and Linux.
    """
    directory = path.resolve().parent
    if sys.platform.startswith('win'):
        os.startfile(directory)
    elif sys.platform.startswith('darwin'): # macOS
        subprocess.call(['open', directory])
    else: # Linux
        subprocess.call(['xdg-open', directory])

def display_results(message: str, file_path: Path):
    """
    A standardized way to show success messages with a path and an "Open Folder" button.
    """
    st.success(message)
    st.code(str(file_path.resolve()), language=None) 
    if st.button(f"📂 Open Containing Folder", key=f"open_{file_path.stem}_{file_path.stat().st_mtime}"):
        open_file_in_explorer(file_path)

# Custom log handler
class StreamlitLogHandler(logging.Handler):
    def __init__(self, container):
        super().__init__()
        self.container = container
        self.log_records = []

    def emit(self, record):
        self.log_records.append(self.format(record))
        self.container.text_area("Live Log", "".join(self.log_records), height=300)

# #############################################################################
# --- INITIAL SETUP & CONFIGURATION ---
# #############################################################################

st.set_page_config(page_title="Medical Book Processing Pipeline", layout="wide")
st.title("👨‍⚕️ Medical Book Processing Pipeline")

if 'paths' not in st.session_state:
    try:
        user_projects_root = Path(__file__).resolve().parent
        project_name = "DRHASSAN"
        paths = get_paths(user_projects_root, project_name)
        for _, dir_path in paths.__dict__.items():
            dir_path.mkdir(parents=True, exist_ok=True)
        st.session_state.paths = paths
        st.success(f"Project '{project_name}' initialized successfully.")
    except FileNotFoundError:
        st.error(f"CRITICAL ERROR: The directory `Projects/{project_name}` was not found. Please create it.")
        st.stop()

paths: ProjectPaths = st.session_state.paths

# #############################################################################
# --- STEP 1: UPLOAD PDF ---
# #############################################################################
with st.expander("STEP 1: Upload PDF to Source Folder", expanded=True):
    st.markdown("Upload a PDF file containing medical questions. It will be saved to the `0Source` folder.")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file:
        save_path = paths.SRCFILE_DIR / uploaded_file.name
        if st.button("Save Uploaded PDF"):
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            display_results(f"File '{uploaded_file.name}' saved successfully!", save_path)
            time.sleep(2)
            st.rerun()

# #############################################################################
# --- STEP 2: CONVERT PDF TO TEXT ---
# #############################################################################
with st.expander("STEP 2: Convert PDF to Text File"):
    st.markdown("Select a PDF from `0Source` to convert into a text file in `1Texted`.")
    
    pdf_files = list(paths.SRCFILE_DIR.glob("*.pdf"))
    selected_pdf = st.selectbox("Select a source PDF:", options=pdf_files, format_func=lambda p: p.name, key="pdf_select")
    
    overwrite_a = st.checkbox("Overwrite existing text file?", value=True, key="overwrite_a")
    st.caption("If unchecked, a new file like `filename_1.txt` will be created if `filename.txt` exists.")

    if st.button("Convert to Text"):
        if selected_pdf:
            default_dest_path = paths.TEXTED_DIR / f"{selected_pdf.stem}.txt"
            final_dest_path = default_dest_path

            if not overwrite_a and default_dest_path.exists():
                final_dest_path = get_next_filename(default_dest_path)
            
            with st.spinner(f"Converting '{selected_pdf.name}'..."):
                try:
                    # Backend script always writes to the default path. We rename it if needed.
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    
                    if default_dest_path != final_dest_path and default_dest_path.exists():
                        default_dest_path.rename(final_dest_path)

                    display_results("Conversion successful!", final_dest_path)
                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")
            time.sleep(2)
            st.rerun()

# #############################################################################
# --- STEP 3: PARSE TEXT TO JSON ---
# #############################################################################
with st.expander("STEP 3: Parse Text to Raw Question JSON"):
    st.markdown("Select a text file from `1Texted` to parse into structured JSON in `2Parsed`.")

    text_files = list(paths.TEXTED_DIR.glob("*.txt"))
    selected_text = st.selectbox("Select a source text file:", options=text_files, format_func=lambda p: p.name, key="text_select")

    overwrite_b = st.checkbox("Overwrite existing parsed JSON?", value=True, key="overwrite_b")
    st.caption("If unchecked, a new file like `filename_1.json` will be created if `filename.json` exists.")

    if st.button("Parse Text File"):
        if selected_text:
            default_dest_path = paths.PARSED_DIR / f"{selected_text.stem}.json"
            final_dest_path = default_dest_path

            if not overwrite_b and default_dest_path.exists():
                final_dest_path = get_next_filename(default_dest_path)

            with st.spinner(f"Parsing '{selected_text.name}'..."):
                try:
                    # Backend script always writes to the default path. We rename it if needed.
                    b_parser.main(paths=paths, subject_file=selected_text.name, overwrite=True)
                    
                    if default_dest_path != final_dest_path and default_dest_path.exists():
                        default_dest_path.rename(final_dest_path)

                    with open(final_dest_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    display_results(f"Parsing successful! Found {len(data)} question blocks.", final_dest_path)
                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")
            time.sleep(2)
            st.rerun()

# #############################################################################
# --- STEP 4: PROCESS WITH AI AGENT ---
# #############################################################################
with st.expander("STEP 4: Process JSON with Gemini AI"):
    st.markdown("Select a parsed JSON from `2Parsed` to process with the AI Agent. Results are in `3Processed`.")

    parsed_files = list(paths.PARSED_DIR.glob("*.json"))
    selected_parsed_json = st.selectbox("Select a parsed JSON file:", options=parsed_files, format_func=lambda p: p.name, key="parsed_json_select")
    
    overwrite_c = st.checkbox("Overwrite and re-process all questions?", value=False, key="overwrite_c")
    st.caption("If unchecked (recommended), the script will resume an incomplete job. Check only for a full re-run.")

    if st.button("Process with AI"):
        if selected_parsed_json:
            final_file = paths.PROCESSED_DIR / f"{selected_parsed_json.stem}_processed.json"
            
            log_container = st.empty()
            handler = StreamlitLogHandler(log_container)
            logger = logging.getLogger()
            logger.addHandler(handler)
            
            with st.spinner(f"Processing '{selected_parsed_json.name}' with AI. This may take a long time..."):
                try:
                    c_processor.main(paths=paths, subject_file=selected_parsed_json.name, overwrite=overwrite_c)
                    display_results("AI processing completed!", final_file)
                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")
                finally:
                    logger.removeHandler(handler)
            time.sleep(2)
            st.rerun()

# #############################################################################
# --- STEP 5: SORT PROCESSED JSON ---
# #############################################################################
with st.expander("STEP 5: Sort Processed JSON File"):
    st.markdown("Sort a `_processed.json` file from `3Processed` by the corrected answer text.")

    processed_files_to_sort = list(paths.PROCESSED_DIR.glob("*_processed.json"))
    selected_to_sort = st.selectbox("Select a processed JSON to sort:", options=processed_files_to_sort, format_func=lambda p: p.name, key="sort_select")
    
    overwrite_d = st.checkbox("Overwrite existing sorted file?", value=True, key="overwrite_d")
    st.caption("If unchecked, a new `..._sorted_1.json` file will be created if the sorted version exists.")

    if st.button("Sort File"):
        if selected_to_sort:
            output_path = selected_to_sort.with_name(f"{selected_to_sort.stem}_sorted.json")
            
            if not overwrite_d and output_path.exists():
                output_path = get_next_filename(output_path)

            with st.spinner(f"Sorting '{selected_to_sort.name}'..."):
                try:
                    sort_json_file(input_path=selected_to_sort, output_path=output_path, sort_key="updated_correct_choice_text")
                    display_results("File sorted successfully!", output_path)
                except Exception as e:
                    st.error(f"An unexpected error occurred during sorting: {e}")
            time.sleep(2)
            st.rerun()

# #############################################################################
# --- STEP 6: CREATE WORD DOCUMENT ---
# #############################################################################
with st.expander("STEP 6: Create Word (DOCX) Document"):
    st.markdown("Select any JSON file from `3Processed` to generate a DOCX file in `OUTPUT`.")

    json_for_docx = list(paths.PROCESSED_DIR.glob("*.json"))
    selected_json_for_docx = st.selectbox("Select JSON for DOCX creation:", options=json_for_docx, format_func=lambda p: p.name, key="docx_select")

    overwrite_e = st.checkbox("Overwrite existing DOCX file?", value=True, key="overwrite_e")
    st.caption("If unchecked, a new file like `filename_1.docx` will be created if `filename.docx` exists.")

    if st.button("Create Word Document"):
        if selected_json_for_docx:
            docx_path = paths.OUTPUT_DIR / f"{selected_json_for_docx.stem}.docx"
            
            if not overwrite_e and docx_path.exists():
                docx_path = get_next_filename(docx_path)

            with st.spinner(f"Generating DOCX for '{selected_json_for_docx.name}'..."):
                try:
                    convert_json_to_docx(selected_json_for_docx, docx_path)
                    display_results("DOCX file created successfully!", docx_path)
                except Exception as e:
                    st.error(f"An error occurred during DOCX creation: {e}")
                    st.warning("Ensure 'pypandoc' is installed (`pip install pypandoc`) and Pandoc is on your system's PATH.")