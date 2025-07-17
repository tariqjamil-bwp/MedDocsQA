# --- START OF FILE app.py ---

import streamlit as st
from pathlib import Path
import logging
import time
import json
import os
import sys
import subprocess

# --- Configure logging to print to the command window (console) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Explicitly direct logs to standard output
)

# --- Import your project's functions ---
from utils import get_paths, ProjectPaths
from utils2 import convert_json_to_docx, sort_json_file
import a_converter
import b_parser
import c_processor

# #############################################################################
# --- UI HELPER FUNCTIONS ---
# #############################################################################

def get_next_filename(path: Path) -> Path:
    if not path.exists(): return path
    i = 1
    while True:
        new_path = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not new_path.exists(): return new_path
        i += 1

def open_file_in_explorer(path: Path):
    directory = path.resolve().parent
    if sys.platform.startswith('win'): os.startfile(directory)
    elif sys.platform.startswith('darwin'): subprocess.call(['open', directory])
    else: subprocess.call(['xdg-open', directory])

def display_results(message: str, file_path: Path):
    st.success(message)
    st.code(str(file_path.resolve()), language=None)
    if st.button(f"📂 Open Containing Folder", key=f"open_{file_path.stem}_{file_path.stat().st_mtime}"):
        open_file_in_explorer(file_path)

# #############################################################################
# --- INITIAL SETUP & CONFIGURATION ---
# #############################################################################

st.set_page_config(page_title="Medical Book Processing Pipeline", layout="wide")
st.title("👨‍⚕️ Medical Book Processing Pipeline")

APP_ROOT = Path(__file__).resolve().parent
PROJECTS_ROOT = APP_ROOT / "Projects"
PROJECTS_ROOT.mkdir(exist_ok=True)

with st.expander("STEP 0: Select or Create Project", expanded=True):
    project_folders = [f.name for f in PROJECTS_ROOT.iterdir() if f.is_dir()]
    
    st.markdown("##### Create a New Project")
    new_project_name = st.text_input("New Project Name:", placeholder="e.g., Endocrinology_Study")
    if st.button("Create Project"):
        if new_project_name:
            new_project_path = PROJECTS_ROOT / new_project_name
            if not new_project_path.exists():
                (new_project_path / "0Source").mkdir(parents=True, exist_ok=True)
                st.success(f"Project '{new_project_name}' created successfully!")
                time.sleep(1); st.rerun()
            else: st.warning(f"Project '{new_project_name}' already exists.")
        else: st.warning("Please enter a name for the new project.")

    st.markdown("---")
    st.markdown("##### Select an Existing Project")
    if not project_folders:
        st.warning("No projects found. Please create one above."); st.stop()

    default_index = project_folders.index("DRHASSAN") if "DRHASSAN" in project_folders else 0
    selected_project = st.selectbox("Choose your project:", project_folders, index=default_index)

try:
    paths = get_paths(APP_ROOT, selected_project)
    st.sidebar.success(f"Active Project: **{selected_project}**")
except FileNotFoundError:
    st.error(f"Could not load project '{selected_project}'."); st.stop()

# #############################################################################
# --- PIPELINE STEPS ---
# #############################################################################

with st.expander("STEP 1: Upload PDF to Source Folder"):
    st.markdown(f"Upload a PDF file. It will be saved to `{paths.SRCFILE_DIR.relative_to(APP_ROOT)}`.")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", key=f"uploader_{selected_project}")
    if uploaded_file and st.button("Save Uploaded PDF"):
        save_path = paths.SRCFILE_DIR / uploaded_file.name
        with open(save_path, "wb") as f: f.write(uploaded_file.getbuffer())
        display_results(f"File '{uploaded_file.name}' saved!", save_path)
        time.sleep(2); st.rerun()

with st.expander("STEP 2: Convert PDF to Text File"):
    st.markdown(f"Select a PDF from `0Source` to convert into a text file in `1Texted`.")
    pdf_files = list(paths.SRCFILE_DIR.glob("*.pdf"))
    selected_pdf = st.selectbox("Select a source PDF:", pdf_files, format_func=lambda p: p.name, key=f"pdf_select_{selected_project}")

    if selected_pdf:
        default_dest_path = paths.TEXTED_DIR / f"{selected_pdf.stem}.txt"
        
        # --- Confirmation Logic ---
        if default_dest_path.exists():
            st.warning(f"Output file `{default_dest_path.name}` already exists.")
            col1, col2, _ = st.columns([1, 2, 3])
            
            if col1.button("Overwrite It", key=f"overwrite_btn_{selected_project}"):
                with st.spinner(f"Overwriting '{default_dest_path.name}'..."):
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    display_results("File overwritten successfully!", default_dest_path)
                time.sleep(2); st.rerun()

            if col2.button("Save as New (Recommended)", key=f"save_new_btn_{selected_project}"):
                final_dest_path = get_next_filename(default_dest_path)
                with st.spinner(f"Saving new file '{final_dest_path.name}'..."):
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    if default_dest_path.exists(): default_dest_path.rename(final_dest_path)
                    display_results("New file saved successfully!", final_dest_path)
                time.sleep(2); st.rerun()
        else:
            if st.button("Convert to Text"):
                with st.spinner(f"Converting '{selected_pdf.name}'..."):
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    display_results("Conversion successful!", default_dest_path)
                time.sleep(2); st.rerun()

with st.expander("STEP 3: Parse Text to Raw Question JSON"):
    st.markdown("Select a text file from `1Texted` to parse into structured JSON in `2Parsed`.")
    text_files = list(paths.TEXTED_DIR.glob("*.txt"))
    selected_text = st.selectbox("Select a source text file:", text_files, format_func=lambda p: p.name, key=f"text_select_{selected_project}")
    
    if st.button("Parse Text File"):
        if selected_text:
            default_dest_path = paths.PARSED_DIR / f"{selected_text.stem}.json"
            final_dest_path = get_next_filename(default_dest_path) if default_dest_path.exists() else default_dest_path
            
            with st.spinner(f"Parsing '{selected_text.name}'..."):
                b_parser.main(paths=paths, subject_file=selected_text.name, overwrite=True)
                if default_dest_path != final_dest_path and default_dest_path.exists():
                    default_dest_path.rename(final_dest_path)
                with open(final_dest_path, 'r', encoding='utf-8') as f: data = json.load(f)
                display_results(f"Parsing successful! Found {len(data)} question blocks.", final_dest_path)
            time.sleep(2); st.rerun()

with st.expander("STEP 4: Process JSON with Gemini AI"):
    st.markdown("Select a parsed JSON from `2Parsed` to process with the AI Agent.")
    parsed_files = list(paths.PARSED_DIR.glob("*.json"))
    selected_parsed_json = st.selectbox("Select a parsed JSON file:", parsed_files, format_func=lambda p: p.name, key=f"parsed_select_{selected_project}")

    if selected_parsed_json:
        final_file = paths.PROCESSED_DIR / f"{selected_parsed_json.stem}_processed.json"
        
        def run_processor(overwrite_flag: bool):
            with st.spinner(f"Processing with AI (Overwrite={overwrite_flag})... This may take a long time..."):
                logging.info(f"Starting AI Processor for '{selected_parsed_json.name}' with overwrite set to {overwrite_flag}.")
                c_processor.main(paths=paths, subject_file=selected_parsed_json.name, overwrite=overwrite_flag)
                display_results("AI processing completed!", final_file)
            time.sleep(2); st.rerun()

        if final_file.exists():
            st.warning(f"Processed file `{final_file.name}` already exists.")
            col1, col2, _ = st.columns([2, 2, 2])
            if col1.button("Resume Incomplete Job", key=f"resume_btn_{selected_project}"):
                run_processor(overwrite_flag=False)
            if col2.button("Re-Process from Scratch", key=f"reprocess_btn_{selected_project}"):
                run_processor(overwrite_flag=True)
        else:
            if st.button("Process with AI"):
                run_processor(overwrite_flag=True) # First run is always a full run

with st.expander("STEP 5: Sort Processed JSON File"):
    st.markdown("Sort a `_processed.json` file from `3Processed`.")
    processed_files_to_sort = list(paths.PROCESSED_DIR.glob("*_processed.json"))
    selected_to_sort = st.selectbox("Select a processed JSON to sort:", processed_files_to_sort, format_func=lambda p: p.name, key=f"sort_select_{selected_project}")
    
    if st.button("Sort File"):
        if selected_to_sort:
            output_path = selected_to_sort.with_name(f"{selected_to_sort.stem}_sorted.json")
            final_path = get_next_filename(output_path) if output_path.exists() else output_path
            with st.spinner(f"Sorting '{selected_to_sort.name}'..."):
                sort_json_file(input_path=selected_to_sort, output_path=final_path, sort_key="updated_correct_choice_text")
                display_results("File sorted successfully!", final_path)
            time.sleep(2); st.rerun()

with st.expander("STEP 6: Create Word (DOCX) Document"):
    st.markdown("Select any JSON file from `3Processed` to generate a DOCX file in `OUTPUT`.")
    json_for_docx = list(paths.PROCESSED_DIR.glob("*.json"))
    selected_json_for_docx = st.selectbox("Select JSON for DOCX creation:", json_for_docx, format_func=lambda p: p.name, key=f"docx_select_{selected_project}")
    
    if st.button("Create Word Document"):
        if selected_json_for_docx:
            docx_path = paths.OUTPUT_DIR / f"{selected_json_for_docx.stem}.docx"
            final_path = get_next_filename(docx_path) if docx_path.exists() else docx_path
            with st.spinner(f"Generating DOCX for '{selected_json_for_docx.name}'..."):
                convert_json_to_docx(selected_json_for_docx, final_path)
                display_results("DOCX file created successfully!", final_path)
            time.sleep(2); st.rerun()