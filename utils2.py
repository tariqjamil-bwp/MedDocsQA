# --- START OF FILE utils2.py ---

import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Union

# Attempt to import pypandoc. If it's not installed, document conversion will fail gracefully.
try:
    import pypandoc
except ImportError:
    pypandoc = None

# Get a logger for this module. The root logger is configured in main.py.
logger = logging.getLogger(__name__)

# #############################################################################
# --- 1. Markdown and DOCX Conversion ---
# #############################################################################

# This template defines the structure for each question in the final output files.
OUTPUT_TEMPLATE = """
## Question #: {{question_num}}

**CLINICAL SCENARIO:**
{{question_desc}}

**QUESTION LINE:**
{{question_line}}

**OPTIONS:**
{{options}}

**CORRECT CHOICE:**
{{correct_choice}}

**REASONING:**
{{reasoning}}

---

**> DESCRIPTION:**
{{updated_description}}

**> OPTIONS:**
{{updated_options}}

**> CORRECT CHOICE:**
{{updated_correct_choice}}   ({{updated_correct_choice_text}}}

**> REFINED REASONING:**
{{updated_reasoning}}


"""

# #############################################################################

def render_question_md(question: dict) -> str:
    """
    Renders a single question dictionary into a Markdown string using the template.
    It safely handles missing keys by defaulting to an empty string.
    """
    # Create a copy to avoid modifying the original dictionary
    q = question.copy()
    
    # Ensure all expected keys are present, defaulting to a placeholder if not
    keys = [
        "question_num", "question_desc", "question_line", "options",
        "correct_choice", "reasoning", "updated_description",
        "updated_options", "updated_correct_choice",
        "updated_correct_choice_text", "updated_reasoning"
    ]
    for key in keys:
        q.setdefault(key, "[N/A]")

    # Replace placeholders in the template
    # Using a loop makes it more maintainable than a long chain of .replace()
    md_string = OUTPUT_TEMPLATE
    for key, value in q.items():
        if "option" in key:
            md_string = md_string.replace(f"{{{{{key}}}}}", str(value.replace('\n', '\n\n')))
        else:
            md_string = md_string.replace(f"{{{{{key}}}}}", str(value))
        
    return md_string

# #############################################################################

def convert_json_to_docx(json_path: Union[str, Path], docx_path: Union[str, Path]):
    """
    Converts a JSON file (containing a list of question objects) into a DOCX file
    by first creating an intermediate Markdown file in the 'tmp' directory.

    Args:
        json_path (Union[str, Path]): Path to the source JSON file.
        docx_path (Union[str, Path]): Path where the final DOCX file will be saved.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1a. Pre-flight Checks ---
    # Check if pypandoc is available.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    if pypandoc is None:
        logger.error("`pypandoc` is not installed. Cannot convert to DOCX. Please run 'pip install pypandoc'.")
        return
        
    json_path = Path(json_path)
    docx_path = Path(docx_path)

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1b. Read and Validate Source JSON ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        if not isinstance(questions, list):
            logger.error(f"Input file '{json_path.name}' must contain a list of question objects.")
            return
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error reading source file '{json_path.name}': {e}")
        return

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1c. Create Intermediate Markdown File ---
    # This file is created in the 'tmp' directory.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # Using Path.name is robust and works on all operating systems.
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    md_path = tmp_dir / f"{json_path.stem}.md"

    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            for q in questions:
                if isinstance(q, dict):
                    f.write(render_question_md(q))
                else:
                    logger.warning(f"Skipping non-dictionary item in '{json_path.name}': {q}")
        logger.info(f"Intermediate Markdown file saved to: {md_path}")
    except IOError as e:
        logger.error(f"Error writing to temporary file '{md_path}': {e}")
        return

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 1d. Convert Markdown to DOCX ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        docx_path.parent.mkdir(parents=True, exist_ok=True)
        pypandoc.convert_file(md_path, 'docx', outputfile=str(docx_path))
        logger.info(f"Successfully converted to DOCX: '{docx_path.name}'")
    except Exception as e:
        logger.error(f"Error converting to .docx using pypandoc: {e}")
        logger.error("Please ensure Pandoc is installed and accessible in your system's PATH.")
        
# #############################################################################
# --- 2. JSON Sorting Utility ---
# #############################################################################

# #############################################################################
# --- 2. JSON Sorting Utility (Corrected Version) ---
# #############################################################################

def sort_json_file(input_path: Path, output_path: Path, sort_key: str, reverse: bool = False):
    """
    Reads a JSON file (list of objects), sorts it by a specified key,
    and writes the result to a new file. It uses a special "natural sort"
    for the 'question_num' key and treats all other values as strings for
    robust, universal sorting.

    Args:
        input_path (Path): Path to the input JSON file.
        output_path (Path): Path where the sorted JSON file will be saved.
        sort_key (str): The dictionary key to sort by (e.g., "question_num").
        reverse (bool): If True, sorts in descending order.
    """
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2a. Read and Validate Input JSON (No Changes Here) ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    logger.info(f"Attempting to sort '{input_path.name}' by key '{sort_key}'...")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise TypeError("JSON content is not a list of objects.")
    except FileNotFoundError:
        logger.error(f"Sort error: Input file not found at {input_path}")
        return
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Sort error: Could not read or parse JSON file '{input_path.name}': {e}")
        return

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2b. Define Smart Sort Key (NEW SIMPLIFIED LOGIC) ---
    # This key uses a hierarchy to separate the special 'question_num' sort
    # from a universal string-based sort for all other keys.
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    def smart_sort_key(item: Dict[str, Any]):
        # Hierarchy Level 2: Handle items with missing keys first.
        # They will always be placed at the very end of the list.
        if sort_key not in item:
            return (2, None)

        value = item[sort_key]

        # Hierarchy Level 0: High-priority logic ONLY for 'question_num'.
        # This provides the "natural sort" order (e.g., 9, 10, 10a).
        if sort_key == "question_num" and isinstance(value, str):
            match = re.match(r'(\d+)([a-zA-Z]*)', value)
            if match:
                return (0, int(match.group(1)), match.group(2))

        # Hierarchy Level 1: Fallback for ALL other cases.
        # This applies to:
        #   - Any key that is NOT 'question_num'.
        #   - A 'question_num' value that is not a string or doesn't match the regex.
        # It safely converts the value to a lowercase string for sorting.
        return (1, str(value).lower())

    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # --- 2c. Sort and Save Data (No Changes Here) ---
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    try:
        sorted_data = sorted(data, key=smart_sort_key, reverse=reverse)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, indent=4)
        logger.info(f"Successfully sorted data and saved to '{output_path.name}'.")
    except TypeError as e:
        logger.error(f"Sort error: Key '{sort_key}' has mixed, un-sortable data types. Details: {e}")
    except IOError as e:
        logger.error(f"Sort error: Could not write to output file '{output_path}': {e}")
 
 # --- START OF FILE: run_full_clustering_flat_output.py ---

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# --- Dependency Imports ---
try:
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import community_detection
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# --- Module-level Configuration ---
logger = logging.getLogger(__name__)
model_cache = {}


# #############################################################################
# --- 1. The Semantic Similarity Clustering Function (New Output Format) ---
# #############################################################################

def cluster_json_by_semantic_similarity(
    input_path: Path,
    output_path: Path,
    search_key: str,
    threshold: float = 0.95,
    min_cluster_size: int = 2,
    model_name: str = 'all-MiniLM-L6-v2'
):
    """
    Analyzes a JSON file, groups items into clusters, and outputs a single,
    flat list with a 'cluster_id' key added to each item.
    """
    # --- Pre-flight Check ---
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        logger.error("Clustering requires 'sentence-transformers'. Please run 'pip install sentence-transformers'.")
        return

    # --- Load Data and Model ---
    logger.info(f"Starting semantic clustering of '{input_path.name}' on key '{search_key}'.")
    try:
        with open(input_path, 'r', encoding='utf-8') as f: data = json.load(f)
        if not isinstance(data, list): raise TypeError("JSON content is not a list of objects.")
    except Exception as e:
        logger.error(f"Clustering error: Could not read file '{input_path.name}': {e}"); return

    try:
        if model_name in model_cache: model = model_cache[model_name]
        else:
            logger.info(f"Loading sentence-transformer model: '{model_name}'...")
            model = SentenceTransformer(model_name)
            model_cache[model_name] = model
    except Exception as e:
        logger.error(f"Failed to load model '{model_name}'. Error: {e}"); return

    # --- Generate Embeddings and Perform Clustering ---
    try:
        texts_to_compare = [str(item.get(search_key, '')) for item in data]
        logger.info(f"Generating embeddings for {len(texts_to_compare)} items...")
        corpus_embeddings = model.encode(texts_to_compare, convert_to_tensor=True, show_progress_bar=True)

        logger.info("Performing community detection...")
        clusters = community_detection(
            corpus_embeddings, min_community_size=min_cluster_size, threshold=threshold
        )

        # --- MODIFIED: Restructure the output to a flat list ---
        final_list = []
        all_clustered_indices = set()

        # 1. Process and tag all clustered items
        cluster_id_counter = 1
        for cluster_indices in clusters:
            all_clustered_indices.update(cluster_indices)
            for idx in cluster_indices:
                item = data[idx]
                item['cluster_id'] = cluster_id_counter
                final_list.append(item)
            cluster_id_counter += 1

        # 2. Process and tag all unclustered items
        for i in range(len(data)):
            if i not in all_clustered_indices:
                item = data[i]
                item['cluster_id'] = None  # Use None for unclustered items
                final_list.append(item)
        
        # 3. Sort the final list to group clustered items together visually
        # This sort is for human readability in the final JSON file.
        final_list.sort(key=lambda x: (x['cluster_id'] is None, x['cluster_id']))

    except Exception as e:
        logger.error(f"An error occurred during clustering: {e}", exc_info=True); return

    # --- Save the Flat List Output ---
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, indent=4)
        logger.info(f"Successfully clustered data and saved to '{output_path.name}'.")
    except IOError as e:
        logger.error(f"Could not write to output file '{output_path}': {e}")

