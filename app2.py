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
from utils import get_paths, ProjectPaths
# Ensure this import points to your file containing the clustering function
from utils2 import convert_json_to_docx, cluster_json_by_semantic_similarity
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
    if sys.platform.startswith('win'):
        os.startfile(directory)
    elif sys.platform.startswith('darwin'):
        subprocess.call(['open', str(directory)])
    else:
        subprocess.call(['xdg-open', str(directory)])

def display_results(container, title: str, file_path: Path):
    container.markdown(f"**{title}**")
    container.code(str(file_path.resolve()), language=None)
    if container.button(f"📂 Open Containing Folder", key=f"open_res_{file_path.stem}"):
        open_file_in_explorer(file_path)

def display_log_entry(container, log_entry, index):
    msg_type = log_entry.get("type", "info")
    message = log_entry.get("message", "")
    file_path = log_entry.get("file_path")
    if msg_type == "success": container.success(message)
    elif msg_type == "error": container.error(message)
    else: container.info(message)
    if file_path:
        container.code(str(file_path.resolve()), language=None)
        if container.button(f"📂 Open Containing Folder", key=f"open_log_{index}_{file_path.stem}"):
            open_file_in_explorer(file_path)
    container.divider()

def get_expander_label(step_num, title):
    if st.session_state.active_step == step_num:
        return f"➡️ STEP {step_num}: {title}"
    return f"STEP {step_num}: {title}"

# #############################################################################
# --- INITIAL SETUP & CONFIGURATION ---
# #############################################################################

st.set_page_config(page_title="Medical Book Processing Pipeline", layout="wide")
st.title("👨‍⚕️ Dr. M. Hassan's Medical Book Processing Pipeline")

if 'logging_configured' not in st.session_state:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
    st.session_state.logging_configured = True

if 'active_step' not in st.session_state: st.session_state.active_step = 1
if 'activity_log' not in st.session_state: st.session_state.activity_log = []

def reset_workflow():
    st.session_state.active_step = 1
    st.session_state.activity_log = []

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
    except FileNotFoundError:
        st.error(f"Could not load project '{selected_project}'."); st.stop()

    with st.expander(get_expander_label(1, "Upload PDF"), expanded=st.session_state.active_step == 1):
        # ... (code for step 1 is unchanged)
        pass
    with st.expander(get_expander_label(2, "PDF to Text"), expanded=st.session_state.active_step == 2):
        # ... (code for step 2 is unchanged)
        pass
    with st.expander(get_expander_label(3, "Parse to JSON"), expanded=st.session_state.active_step == 3):
        # ... (code for step 3 is unchanged)
        pass

    with st.expander(get_expander_label(4, "Process with AI"), expanded=st.session_state.active_step == 4):
        # ... (code for step 4 is unchanged)
        pass

    with st.expander(get_expander_label(5, "Find Semantic Clusters"), expanded=st.session_state.active_step == 5):
        st.info("Group questions by topic similarity without needing a query.")
        
        processed_files = sorted(list(paths.PROCESSED_DIR.glob("*_processed.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        selected_processed_json = st.selectbox("Select Processed JSON to Cluster:", processed_files, format_func=lambda p: p.name, key=f"cluster_select_{selected_project}")
        
        if selected_processed_json:
            search_key = st.selectbox(
                "Select text field to analyze:",
                ("updated_correct_choice_text", "updated_description", "updated_reasoning"),
                index=0,
                key=f"cluster_key_{selected_project}",
                help="Select the field to compare for similarity. 'updated_correct_choice_text' is great for grouping questions by their final answer."
            )
            similarity_threshold = st.slider(
                "Similarity Threshold:",
                min_value=0.50, max_value=1.0, value=0.80, step=0.05,
                help="Higher values mean items must be more similar to be grouped. 0.8 is a good starting point."
            )

            if st.button("Find Clusters", key="cluster_s5"):
                output_path = paths.PROCESSED_DIR / f"{selected_processed_json.stem}_clustered.json"
                with st.spinner(f"Clustering '{selected_processed_json.name}'..."):
                    cluster_json_by_semantic_similarity(
                        input_path=selected_processed_json,
                        output_path=output_path,
                        search_key=search_key,
                        threshold=similarity_threshold,
                        min_cluster_size=2
                    )
                
                st.session_state.activity_log.insert(0, {"type": "success", "message": f"**Step 5 Complete!** Clustering results saved.", "file_path": output_path})
                st.session_state.active_step = 6
                st.rerun()

    # --- MODIFIED: The final step is now fully compatible with clustered files ---
    with st.expander(get_expander_label(6, "Create Word Document"), expanded=st.session_state.active_step == 6):
        # The selector now correctly includes the new flat clustered files
        json_files = sorted(list(paths.PROCESSED_DIR.glob("*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        selected_json = st.selectbox("Select JSON for DOCX:", json_files, format_func=lambda p: p.name, key=f"docx_select_{selected_project}", label_visibility="collapsed")
        
        if selected_json:
            # --- REMOVED THE WARNING ---
            # The new flat list format from the clustering function is now
            # fully compatible with the DOCX conversion function.

            dest_path = paths.OUTPUT_DIR / f"{selected_json.stem}.docx"
            if dest_path.exists():
                st.warning(f"`{dest_path.name}` exists."); c1, c2 = st.columns(2)
                if c1.button("Overwrite", key="overwrite_s6"):
                    convert_json_to_docx(selected_json, dest_path)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": f"**Step 6 Complete!** Overwritten DOCX file:", "file_path": dest_path})
                    st.rerun()
                if c2.button("Save as New", key="save_new_s6"):
                    new_path = get_next_filename(dest_path)
                    convert_json_to_docx(selected_json, new_path)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": f"**Step 6 Complete!** Saved new DOCX file:", "file_path": new_path})
                    st.rerun()
            else:
                if st.button("Create DOCX", key="create_docx_s6"):
                    convert_json_to_docx(selected_json, dest_path)
                    st.session_state.activity_log.insert(0, {"type": "success", "message": f"**Step 6 Complete!** Created DOCX file:", "file_path": dest_path})
                    st.rerun()

# #############################################################################
# --- COLUMN 2: ACTIVITY LOG & DYNAMIC OUTPUT ---
# #############################################################################
with live_run_column:
    st.header("Activity Log")
    log_container = st.container(height=800, border=True)
    if not st.session_state.activity_log:
        log_container.info("Results from your actions will appear here.")
    else:
        for i, entry in enumerate(st.session_state.activity_log):
            display_log_entry(log_container, entry, i)

# --- END OF FILE app.py ---