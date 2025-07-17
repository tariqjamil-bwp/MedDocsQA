# --- START OF FILE app.py ---

import streamlit as st
from pathlib import Path
import logging
import time
import json
import os
import sys
import subprocess
from datetime import datetime # Import the datetime module

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

def display_log_entry(container, log_entry, index):
    """Displays a single, persistent log entry with a timestamp."""
    msg_type = log_entry.get("type", "info")
    message = log_entry.get("message", "")
    file_path = log_entry.get("file_path")
    timestamp = log_entry.get("timestamp", "") # Get the timestamp

    # Prepend the timestamp to the message for a cleaner look
    full_message = f"[{timestamp}] {message}"

    if msg_type == "success":
        container.success(full_message)
    elif msg_type == "error":
        container.error(full_message)
    else: # Default to info
        container.info(full_message)
    
    if file_path:
        container.code(str(file_path.resolve()), language=None)
        if container.button(f"📂 Open Containing Folder", key=f"open_{index}_{file_path.stem}"):
            open_file_in_explorer(file_path)
    
    container.divider()


def get_expander_label(step_num, title):
    """Adds a visual cue to the active step's expander label."""
    if st.session_state.active_step == step_num:
        return f"➡️ STEP {step_num}: {title}"
    return f"STEP {step_num}: {title}"

def add_log_entry(log_type: str, message: str, file_path: Path = None):
    """A centralized function to add entries to the activity log."""
    st.session_state.activity_log.insert(0, {
        "type": log_type,
        "message": message,
        "file_path": file_path,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

# #############################################################################
# --- INITIAL SETUP & CONFIGURATION ---
# #############################################################################

st.set_page_config(page_title="Medical Book Processing Pipeline", layout="wide")
st.title("👨‍⚕️ Dr. M. Hassan's Medical Book Processing Pipeline")

# Configure root logger ONCE per session
if 'logging_configured' not in st.session_state:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
    st.session_state.logging_configured = True

# Session state for workflow, abort logic, and persistent logging
if 'active_step' not in st.session_state: st.session_state.active_step = 1
if 'processing_active' not in st.session_state: st.session_state.processing_active = False
if 'activity_log' not in st.session_state: st.session_state.activity_log = []

def reset_workflow():
    st.session_state.active_step = 1
    st.session_state.activity_log = [] # Clear log on project change

control_column, live_run_column = st.columns([1, 2])

# #############################################################################
# --- COLUMN 1: CONTROL PANEL ---
# #############################################################################
with control_column:
    st.header("Control Panel")

    APP_ROOT = Path(__file__).resolve().parent
    PROJECTS_ROOT = APP_ROOT / "Projects"
    PROJECTS_ROOT.mkdir(exist_ok=True)

    with st.expander(get_expander_label(0, "Select Project"), expanded=True):
        project_folders = [f.name for f in PROJECTS_ROOT.iterdir() if f.is_dir()]
        if not project_folders: st.error("No project folders found. Please create one manually."); st.stop()
        default_index = project_folders.index("DRHASSAN") if "DRHASSAN" in project_folders else 0
        selected_project = st.selectbox("Select Project:", project_folders, index=default_index, label_visibility="collapsed", on_change=reset_workflow)

    try:
        paths = get_paths(APP_ROOT, selected_project)
        st.sidebar.success(f"Active Project: **{selected_project}**")
    except FileNotFoundError: st.error(f"Could not load project '{selected_project}'."); st.stop()

    with st.expander(get_expander_label(1, "Upload PDF"), expanded=st.session_state.active_step == 1):
        uploaded_file = st.file_uploader("Choose a PDF", type="pdf", key=f"uploader_{selected_project}")
        if uploaded_file and st.button("Save Uploaded PDF"):
            save_path = paths.SRCFILE_DIR / uploaded_file.name
            with open(save_path, "wb") as f: f.write(uploaded_file.getbuffer())
            add_log_entry("success", f"**Step 1 Complete!** Saved: '{uploaded_file.name}'", save_path)
            st.session_state.active_step = 2; st.rerun()

    with st.expander(get_expander_label(2, "PDF to Text"), expanded=st.session_state.active_step == 2):
        pdf_files = list(paths.SRCFILE_DIR.glob("*.pdf"))
        selected_pdf = st.selectbox("Select PDF:", pdf_files, format_func=lambda p: p.name, key=f"pdf_select_{selected_project}", label_visibility="collapsed")
        if selected_pdf:
            dest_path = paths.TEXTED_DIR / f"{selected_pdf.stem}.txt"
            if dest_path.exists():
                st.warning(f"`{dest_path.name}` exists."); c1, c2 = st.columns(2)
                if c1.button("Overwrite", key="overwrite_s2"):
                    st.session_state.current_action = f"**Step 2 in Progress:** Overwriting with input '{selected_pdf.name}'..."
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    add_log_entry("success", "**Step 2 Complete!** Overwritten file:", dest_path)
                    st.session_state.active_step = 3; st.session_state.current_action = None; st.rerun()
                if c2.button("Save as New", key="save_new_s2"):
                    st.session_state.current_action = f"**Step 2 in Progress:** Converting input '{selected_pdf.name}'..."
                    new_path = get_next_filename(dest_path); a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    if dest_path.exists(): dest_path.rename(new_path)
                    add_log_entry("success", "**Step 2 Complete!** Saved as new file:", new_path)
                    st.session_state.active_step = 3; st.session_state.current_action = None; st.rerun()
            else:
                if st.button("Convert to Text", key="convert_s2"):
                    st.session_state.current_action = f"**Step 2 in Progress:** Converting input '{selected_pdf.name}'..."
                    a_converter.main(paths=paths, subject_file=selected_pdf.name, overwrite=True)
                    add_log_entry("success", "**Step 2 Complete!** Created output:", dest_path)
                    st.session_state.active_step = 3; st.session_state.current_action = None; st.rerun()

    with st.expander(get_expander_label(3, "Parse to JSON"), expanded=st.session_state.active_step == 3):
        text_files = list(paths.TEXTED_DIR.glob("*.txt"))
        selected_text = st.selectbox("Select Text File:", text_files, format_func=lambda p: p.name, key=f"text_select_{selected_project}", label_visibility="collapsed")
        if st.button("Parse Text File", key="parse_s3") and selected_text:
            st.session_state.current_action = f"**Step 3 in Progress:** Parsing input '{selected_text.name}'..."
            dest_path = paths.PARSED_DIR / f"{selected_text.stem}.json"; final_path = get_next_filename(dest_path) if dest_path.exists() else dest_path
            b_parser.main(paths=paths, subject_file=selected_text.name, overwrite=True)
            if dest_path != final_path and dest_path.exists(): dest_path.rename(final_path)
            with open(final_path, 'r', encoding='utf-8') as f: data = json.load(f)
            add_log_entry("success", f"**Step 3 Complete!** Parsed {len(data)} questions to output:", final_path)
            st.session_state.active_step = 4; st.session_state.current_action = None; st.rerun()

    with st.expander(get_expander_label(4, "Process with AI & Sort"), expanded=st.session_state.active_step == 4):
        parsed_files = list(paths.PARSED_DIR.glob("*.json"))
        selected_parsed = st.selectbox("Select Parsed JSON:", parsed_files, format_func=lambda p: p.name, key=f"parsed_select_{selected_project}", label_visibility="collapsed")
        if selected_parsed:
            final_file = paths.PROCESSED_DIR / f"{selected_parsed.stem}_processed.json"
            def run_processor_and_sorter(overwrite: bool):
                st.session_state.processing_active = True
                st.session_state.current_action = f"**Step 4 in Progress:** Processing '{selected_parsed.name}' with AI. See console for detailed logs..."
                c_processor.main(paths=paths, subject_file=selected_parsed.name, overwrite=overwrite)
                st.session_state.processing_active = False
                abort_file_path = paths.UPROJ_DIR / "tmp" / "abort_flag.txt"
                if abort_file_path.exists():
                    add_log_entry("error", "Processing was aborted by user.")
                    abort_file_path.unlink()
                else:
                    add_log_entry("success", "✅ **AI Processing Complete!** Created output:", final_file)
                    st.session_state.current_action = "Step 4 in Progress: Automatically sorting..."
                    sorted_dest_path = final_file.with_name(f"{final_file.stem}_sorted.json")
                    sort_json_file(input_path=final_file, output_path=sorted_dest_path, sort_key="updated_correct_choice_text")
                    add_log_entry("success", "✅ **Automatic Sorting Complete!** Created output:", sorted_dest_path)
                st.session_state.active_step = 5; st.session_state.current_action = None; st.rerun()
            if final_file.exists():
                st.warning(f"`{final_file.name}` exists."); c1, c2 = st.columns(2)
                if c1.button("Resume Job", key="resume_s4"): run_processor_and_sorter(False)
                if c2.button("Re-Process All", key="reprocess_s4"): run_processor_and_sorter(True)
            else:
                if st.button("Process & Sort", key="process_s4"): run_processor_and_sorter(True)

    with st.expander(get_expander_label(5, "Create Word Document"), expanded=st.session_state.active_step == 5):
        json_files = sorted(list(paths.PROCESSED_DIR.glob("*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        selected_json = st.selectbox("Select JSON for DOCX:", json_files, format_func=lambda p: p.name, key=f"docx_select_{selected_project}", label_visibility="collapsed")
        if st.button("Create DOCX", key="docx_s6") and selected_json:
            st.session_state.current_action = f"**Step 5 in Progress:** Creating DOCX from input '{selected_json.name}'..."
            dest_path = paths.OUTPUT_DIR / f"{selected_json.stem}.docx"; final_path = get_next_filename(dest_path) if dest_path.exists() else dest_path
            convert_json_to_docx(selected_json, final_path)
            add_log_entry("success", "**Step 5 Complete!** Created DOCX file:", final_path)
            st.session_state.current_action = None; st.rerun()

# #############################################################################
# --- SIDEBAR & ABORT BUTTON ---
# #############################################################################
if st.session_state.processing_active:
    st.sidebar.error("AI Processing is Active")
    if st.sidebar.button("🛑 ABORT MISSION"):
        tmp_dir = paths.UPROJ_DIR / "tmp"; tmp_dir.mkdir(exist_ok=True)
        (tmp_dir / "abort_flag.txt").touch()
        st.sidebar.error("Abort signal sent! Process will stop soon.")
        st.session_state.processing_active = False; st.rerun()

# #############################################################################
# --- COLUMN 2: ACTIVITY LOG ---
# #############################################################################
with live_run_column:
    st.header(f"Activity Log (Last Update: {datetime.now().strftime('%H:%M:%S')})")

    # Display a temporary "in-progress" message if an action is running
    if st.session_state.get("current_action"):
        st.info(st.session_state.current_action)

    # Use st.container() to create a scrollable area for the persistent log
    log_container = st.container(height=800, border=True)

    if not st.session_state.activity_log:
        log_container.info("Results from your actions will appear here. See the console window for detailed process logs.")
    else:
        # Display the persistent log history inside the container
        for i, entry in enumerate(st.session_state.activity_log):
            display_log_entry(log_container, entry, i)