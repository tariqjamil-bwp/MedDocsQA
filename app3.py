# --- START OF FILE app.py ---

import streamlit as st
from pathlib import Path
import logging
import json
import os
import sys
import subprocess

# --- Import your project's utility and pipeline functions ---
# It's assumed these files exist alongside app.py:
# utils.py, utils2.py, a_converter.py, b_parser.py, c_processor.py
from utils import get_paths, ProjectPaths
from utils2 import convert_json_to_docx, sort_json_file
import a_converter
import b_parser
import c_processor

# #############################################################################
# --- UI HELPER FUNCTIONS ---
# #############################################################################

def get_next_filename(path: Path) -> Path:
    """Finds the next available filename to avoid overwriting (e.g., file_1.txt, file_2.txt)."""
    if not path.exists():
        return path
    i = 1
    while True:
        # Create a new path with an incrementing suffix
        new_path = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not new_path.exists():
            return new_path
        i += 1

def open_file_in_explorer(path: Path):
    """Opens the system's file explorer to the directory containing the given path."""
    directory = path.resolve().parent
    if sys.platform.startswith('win'):
        os.startfile(directory)
    elif sys.platform.startswith('darwin'):  # macOS
        subprocess.call(['open', directory])
    else:  # Linux
        subprocess.call(['xdg-open', directory])

def display_results(container, title: str, file_path: Path):
    """A helper to display file creation results consistently within a container."""
    container.markdown(f"**{title}**")
    container.code(str(file_path.resolve()), language=None)
    # Use the file's stem for a unique key to prevent Streamlit widget ID errors
    if container.button(f"📂 Open Containing Folder", key=f"open_res_{file_path.stem}"):
        open_file_in_explorer(file_path)

def display_log_entry(container, log_entry, index):
    """Displays a single, persistent log entry in the Activity Log."""
    msg_type = log_entry.get("type", "info")
    message = log_entry.get("message", "")
    file_path = log_entry.get("file_path")

    # Display message with appropriate color
    if msg_type == "success": container.success(message)
    elif msg_type == "error": container.error(message)
    else: container.info(message)
    
    # If a file path is associated, display it and provide an "Open" button
    if file_path:
        container.code(str(file_path.resolve()), language=None)
        if container.button(f"📂 Open Containing Folder", key=f"open_log_{index}_{file_path.stem}"):
            open_file_in_explorer(file_path)
    container.divider()

def get_expander_label(step_num, title):
    """Generates a label for an expander to show the active step with an arrow."""
    if st.session_state.active_step == step_num:
        return f"➡️ STEP {step_num}: {title}"
    return f"STEP {step_num}: {title}"

# #############################################################################
# --- INITIAL SETUP & CONFIGURATION ---
# #############################################################################

# Configure the Streamlit page
st.set_page_config(page_title="Medical Book Processing Pipeline", layout="wide")
st.title("👨‍⚕️ Dr. M. Hassan's Medical Book Processing Pipeline")

# Configure logging only once per session
if 'logging_configured' not in st.session_state:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
    st.session_state.logging_configured = True

# Initialize session state variables to manage the UI's state across reruns
if 'active_step' not in st.session_state: st.session_state.active_step = 1
if 'activity_log' not in st.session_state: st.session_state.activity_log = []

def reset_workflow():
    """Resets the UI to the beginning of the workflow, called when the project changes."""
    st.session_state.active_step = 1
    st.session_state.activity_log = []

# Define the main layout columns for the app
control_column, live_run_column = st.columns([1, 2])

# #############################################################################
# --- COLUMN 1: CONTROL PANEL ---
# #############################################################################
with control_column:
    st.header("Control Panel")

    APP_ROOT = Path(__file__).resolve().parent
    PROJECTS_ROOT = APP_ROOT / "Projects"
    PROJECTS_ROOT.mkdir(exist_ok=True)

    # Expander 0: Project Selection (Always open)
    with st.expander(get_expander_label(0, "Select Project"), expanded=True):
        project_folders = [f.name for f in PROJECTS_ROOT.iterdir() if f.is_dir()]
        if not project_folders:
            st.error("No project folders found in the 'Projects' directory. Please create one.")
            st.stop()
        
        # Default to "DRHASSAN" project if it exists
        default_index = project_folders.index("DRHASSAN") if "DRHASSAN" in project_folders else 0
        selected_project = st.selectbox(
            "Select Project:", project_folders, index=default_index, label_visibility="collapsed", on_change=reset_workflow
        )

    # Load the paths for the selected project
    try:
        paths = get_paths(APP_ROOT, selected_project)
        st.sidebar.success(f"Active Project: **{selected_project}**")
    except FileNotFoundError:
        st.error(f"Could not load project '{selected_project}'. The directory structure might be incomplete.")
        st.stop()

    # Expander 1: PDF Upload
    with st.expander(get_expander_label(1, "Upload PDF"), expanded=st.session_state.active_step == 1):
        uploaded_file = st.file_uploader("Choose a PDF file to upload", type="pdf", key=f"uploader_{selected_project}")
        if uploaded_file and st.button("Save Uploaded PDF"):
            save_path = paths.SRCFILE_DIR / uploaded_file.name
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            # Log the success and advance the workflow
            st.session_state.activity_log.insert(0, {"type": "success", "message": f"**Step 1 Complete!** Saved: '{uploaded_file.name}'", "file_path": save_path})
            st.session_state.active_step = 2
            st.rerun()

    # Expander 2: PDF to Text Conversion
    with st.expander(get_expander_label(2, "PDF to Text"), expanded=st.session_state.active_step == 2):
        pdf_files = list(paths.SRCFILE_DIR.glob("*.pdf"))
        selected_pdf = st.selectbox("Select PDF to convert:", pdf_files, format_func=lambda p: p.name, key=f"pdf_select_{selected_project}", label_visibility="collapsed")
        if selected_pdf:
            dest_path = paths.TEXTED_DIR / f"{selected_pdf.stem}.txt"
            if dest_path.exists():
                st.warning(f"`{dest_path.name}` already exists.")
                c1, c2 = st.columns(2)
                if c1.button("Overwrite", key="overwrite_s2"):
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": "**Step 2 Complete!** Overwritten text file:", "file_path": dest_path})
                    st.session_state.active_step = 3; st.rerun()
                if c2.button("Save as New", key="save_new_s2"):
                    new_path = get_next_filename(dest_path)
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    if dest_path.exists(): dest_path.rename(new_path) # Rename after creation
                    st.session_state.activity_log.insert(0, {"type": "success", "message": "**Step 2 Complete!** Saved as new text file:", "file_path": new_path})
                    st.session_state.active_step = 3; st.rerun()
            else:
                if st.button("Convert to Text", key="convert_s2"):
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": "**Step 2 Complete!** Created text file:", "file_path": dest_path})
                    st.session_state.active_step = 3; st.rerun()

    # Expander 3: Parse Text to JSON
    with st.expander(get_expander_label(3, "Parse to JSON"), expanded=st.session_state.active_step == 3):
        text_files = list(paths.TEXTED_DIR.glob("*.txt"))
        selected_text = st.selectbox("Select Text File to parse:", text_files, format_func=lambda p: p.name, key=f"text_select_{selected_project}", label_visibility="collapsed")
        if selected_text:
            dest_path = paths.PARSED_DIR / f"{selected_text.stem}.json"
            # Logic to handle existing files
            if dest_path.exists():
                st.warning(f"`{dest_path.name}` already exists.")
                c1, c2 = st.columns(2)
                if c1.button("Overwrite", key="overwrite_s3"):
                    b_parser.main(paths=paths, subject_file=selected_text.name, overwrite=True)
                    with open(dest_path, 'r', encoding='utf-8') as f: data = json.load(f)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": f"**Step 3 Complete!** Parsed {len(data)} questions into overwritten file:", "file_path": dest_path})
                    st.session_state.active_step = 4; st.rerun()
                if c2.button("Save as New", key="save_new_s3"):
                    new_path = get_next_filename(dest_path)
                    b_parser.main(paths=paths, subject_file=selected_text.name, overwrite=True)
                    if dest_path.exists(): dest_path.rename(new_path) # Rename after creation
                    with open(new_path, 'r', encoding='utf-8') as f: data = json.load(f)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": f"**Step 3 Complete!** Parsed {len(data)} questions into new file:", "file_path": new_path})
                    st.session_state.active_step = 4; st.rerun()
            else:
                if st.button("Parse Text File", key="parse_s3"):
                    b_parser.main(paths=paths, subject_file=selected_text.name, overwrite=True)
                    with open(dest_path, 'r', encoding='utf-8') as f: data = json.load(f)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": f"**Step 3 Complete!** Parsed {len(data)} questions:", "file_path": dest_path})
                    st.session_state.active_step = 4; st.rerun()

    # Expander 4: Process with AI Agent and Auto-Sort
    with st.expander(get_expander_label(4, "Process with AI & Sort"), expanded=st.session_state.active_step == 4):
        parsed_files = list(paths.PARSED_DIR.glob("*.json"))
        selected_parsed = st.selectbox("Select Parsed JSON to process:", parsed_files, format_func=lambda p: p.name, key=f"parsed_select_{selected_project}", label_visibility="collapsed")
        if selected_parsed:
            final_file = paths.PROCESSED_DIR / f"{selected_parsed.stem}_processed.json"
            
            # This nested function runs the long-running tasks in the right-hand column
            def run_processor_and_sorter(overwrite: bool):
                with live_run_column:
                    # Clear the column and show a spinner for the main AI process
                    st.empty()
                    with st.spinner(f"Processing '{selected_parsed.name}'... This may take a while. Press Ctrl+C in the console to abort."):
                        c_processor.main(paths=paths, subject_file=selected_parsed.name, overwrite=overwrite)
                    
                    st.success("✅ AI Processing Finished.")
                    display_results(st, "Latest processed file:", final_file)
                    st.divider()

                    # Show a spinner for the automatic sorting process
                    with st.spinner("Automatically sorting file by correct answer text..."):
                        sorted_dest_path = final_file.with_name(f"{final_file.stem}_sorted_by_answer.json")
                        sort_json_file(input_path=final_file, output_path=sorted_dest_path, sort_key="updated_correct_choice_text")
                    st.success("✅ Automatic Sorting Complete!")
                    display_results(st, "Created sorted file:", sorted_dest_path)
                    st.divider()
                st.session_state.active_step = 5
                st.rerun()

            # UI logic to choose between resuming a job or starting fresh
            if final_file.exists():
                st.warning(f"`{final_file.name}` exists.")
                c1, c2 = st.columns(2)
                if c1.button("Resume Job", key="resume_s4"):
                    run_processor_and_sorter(overwrite=False)
                if c2.button("Re-Process All", key="reprocess_s4"):
                    run_processor_and_sorter(overwrite=True)
            else:
                if st.button("Process & Sort", key="process_s4"):
                    run_processor_and_sorter(overwrite=True)

    # Expander 5: Create Final Word Document
    with st.expander(get_expander_label(5, "Create Word Document"), expanded=st.session_state.active_step == 5):
        # Find all processed JSONs and list the newest one first
        json_files = sorted(list(paths.PROCESSED_DIR.glob("*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        selected_json = st.selectbox("Select JSON to create DOCX from:", json_files, format_func=lambda p: p.name, key=f"docx_select_{selected_project}", label_visibility="collapsed")
        if selected_json:
            dest_path = paths.OUTPUT_DIR / f"{selected_json.stem}.docx"
            # Logic to handle existing DOCX files
            if dest_path.exists():
                st.warning(f"`{dest_path.name}` exists.")
                c1, c2 = st.columns(2)
                if c1.button("Overwrite", key="overwrite_s5"):
                    convert_json_to_docx(selected_json, dest_path)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": "**Step 5 Complete!** Overwritten DOCX file:", "file_path": dest_path})
                    st.rerun()
                if c2.button("Save as New", key="save_new_s5"):
                    new_path = get_next_filename(dest_path)
                    convert_json_to_docx(selected_json, new_path)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": "**Step 5 Complete!** Saved as new DOCX file:", "file_path": new_path})
                    st.rerun()
            else:
                if st.button("Create DOCX", key="create_docx_s5"):
                    convert_json_to_docx(selected_json, dest_path)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": "**Step 5 Complete!** Created DOCX file:", "file_path": dest_path})
                    st.rerun()

# #############################################################################
# --- COLUMN 2: ACTIVITY LOG & DYNAMIC OUTPUT ---
# #############################################################################
with live_run_column:
    st.header("Activity Log")
    log_container = st.container(height=800, border=True)
    if not st.session_state.activity_log:
        log_container.info("Results from your actions will appear here as you complete each step.")
    else:
        # Display all logged activities, with the most recent at the top
        for i, entry in enumerate(st.session_state.activity_log):
            display_log_entry(log_container, entry, i)

# --- END OF FILE app.py ---