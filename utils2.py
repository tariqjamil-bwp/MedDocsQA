# --- START OF FILE utils2.py ---

import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Union

# --- Dependency Imports ---
try:
    import pypandoc
except ImportError:
    pypandoc = None

# NEW: Import Jinja2
try:
    import jinja2
except ImportError:
    jinja2 = None

# --- Module-level Configuration ---
logger = logging.getLogger(__name__)

# #############################################################################
# --- 1. Markdown and DOCX Conversion (with Dynamic Jinja2 Templates) ---
# #############################################################################

# Import the Jinja2-compatible templates
from templates import (
    OUTPUT_TEMPLATE_FULL_JINJA,
    OUTPUT_TEMPLATE_ORIGINAL_JINJA,
    OUTPUT_TEMPLATE_UPDATED_JINJA
)

# Create a registry to map user-friendly names to the template strings
TEMPLATE_REGISTRY = {
    "FULL": OUTPUT_TEMPLATE_FULL_JINJA,
    "ORIGINAL": OUTPUT_TEMPLATE_ORIGINAL_JINJA,
    "UPDATED": OUTPUT_TEMPLATE_UPDATED_JINJA,
}

# --- NEW: Define the custom filter function to split options ---
def split_and_trim(text: str) -> List[str]:
    """A custom Jinja filter to split a string by newlines and trim whitespace."""
    if not isinstance(text, str):
        return []
    # Split by newline, filter out any empty lines
    return [line.strip() for line in text.splitlines() if line.strip()]

# Pre-compile the templates and register the custom filter
COMPILED_TEMPLATES = {}
if jinja2:
    jinja_env = jinja2.Environment(loader=jinja2.BaseLoader(), autoescape=True)
    # Register our custom function as a filter named 'splitlines'
    jinja_env.filters['splitlines'] = split_and_trim
    
    for name, template_string in TEMPLATE_REGISTRY.items():
        COMPILED_TEMPLATES[name] = jinja_env.from_string(template_string)


# --- REPLACED: This is the new, correct rendering function ---
def render_question_md(question: dict, template_choice: str) -> str:
    """
    Renders a single question dictionary using a dynamically selected Jinja2 template.
    """
    if not jinja2:
        logger.error("Jinja2 is not installed. Please run 'pip install Jinja2'.")
        return ""

    template = COMPILED_TEMPLATES.get(template_choice.upper())

    if not template:
        logger.error(f"Template '{template_choice}' not found. Defaulting to 'FULL'.")
        template = COMPILED_TEMPLATES["FULL"]
        
    # The render method uses the Jinja2 engine, not simple string replacement.
    return template.render(question)

def convert_json_to_docx(
    json_path: Union[str, Path],
    docx_path: Union[str, Path],
    template_choice: str = "FULL"
):
    _convert_json_to_docx(json_path=json_path, docx_path=docx_path, template_choice="FULL")
    _convert_json_to_docx(json_path=json_path, docx_path=docx_path, template_choice="ORIGINAL")
    _convert_json_to_docx(json_path=json_path, docx_path=docx_path, template_choice="UPDATED")

def _convert_json_to_docx(
    json_path: Union[str, Path],
    docx_path: Union[str, Path],
    template_choice: str = "FULL"
):
    """
    Converts a JSON file into a DOCX file using a specified Jinja2 template.
    """
    if pypandoc is None:
        logger.error("`pypandoc` is not installed. Cannot convert to DOCX. Please run 'pip install pypandoc'.")
        return
    json_path, docx_path = Path(json_path), Path(docx_path)
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        if not isinstance(questions, list):
            logger.error(f"Input file '{json_path.name}' must be a list of objects.")
            return
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error reading source file '{json_path.name}': {e}")
        return

    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    md_path = tmp_dir / f"{json_path.stem}_{template_choice.lower()}.md"

    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            for q in questions:
                if isinstance(q, dict):
                    # This now calls the correct Jinja2 rendering function
                    f.write(render_question_md(q, template_choice=template_choice))
                else:
                    logger.warning(f"Skipping non-dictionary item in '{json_path.name}': {q}")
        logger.info(f"Intermediate Markdown file saved to: {md_path}")
    except IOError as e:
        logger.error(f"Error writing to temporary file '{md_path}': {e}")
        return

    try:
        docx_path.parent.mkdir(parents=True, exist_ok=True)
        docx_pathT = Path(str(docx_path).replace('.docx', f"{template_choice[0]}.docx"))
        pypandoc.convert_file(str(md_path), 'docx', outputfile=str(docx_pathT))
        logger.info(f"Successfully converted '{md_path.name}' to DOCX: '{docx_pathT.name}'")
    except Exception as e:
        logger.error(f"Error converting to .docx using pypandoc: {e}")
        logger.error("Please ensure Pandoc is installed and accessible in your system's PATH.")


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

