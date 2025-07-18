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


# #############################################################################
# --- 2. Main Execution Block ---
# #############################################################################

def main():
    """
    Main function to orchestrate the semantic clustering process on a specific file.
    """
    # --- Configuration: Set your parameters here ---
    SEARCH_KEY = 'updated_description'
    SIMILARITY_THRESHOLD = 0.80 # Using a reasonable threshold for topic matching
    MIN_CLUSTER_SIZE = 2

    # --- Path Setup ---
    try:
        project_root = Path(__file__).resolve().parent
        input_file = project_root / "Projects" / "DRHASSAN" / "2Parsed" / "TestGastroenterology.json"
        output_file = input_file.with_name(f"{input_file.stem}__clustered_flat.json") # New suffix
    except Exception as e:
        logger.error(f"Error resolving file paths: {e}"); return

    if not input_file.exists():
        logger.error(f"FATAL: Input file not found at the expected path: {input_file}"); return

    logging.info("="*60)
    logging.info("--- Starting Semantic Clustering Process (Flat Output) ---")
    logging.info(f"Input file:  {input_file}")
    logging.info(f"Output file: {output_file}")
    logging.info(f"Search key:  '{SEARCH_KEY}'")
    logging.info(f"Threshold:   {SIMILARITY_THRESHOLD}")
    logging.info("="*60)

    # --- Execution ---
    cluster_json_by_semantic_similarity(
        input_path=input_file,
        output_path=output_file,
        search_key=SEARCH_KEY,
        threshold=SIMILARITY_THRESHOLD,
        min_cluster_size=MIN_CLUSTER_SIZE
    )

    # --- Verification and Reporting ---
    if output_file.exists():
        logging.info("\n--- Process Finished. Verifying output... ---")
        with open(output_file, 'r', encoding='utf-8') as f:
            results = json.load(f)

        cluster_ids = {item.get('cluster_id') for item in results if item.get('cluster_id') is not None}
        unclustered_count = sum(1 for item in results if item.get('cluster_id') is None)

        print(f"\n✅ Success! Clustered results saved to {output_file.name}")
        print(f"   Found {len(cluster_ids)} cluster(s) and {unclustered_count} unclustered item(s).")
        print("\n--- Summary of Clusters ---")
        if cluster_ids:
            for cid in sorted(list(cluster_ids)):
                items_in_cluster = [item['question_num'] for item in results if item.get('cluster_id') == cid]
                print(f"  Cluster #{cid}: Contains questions {items_in_cluster}")
        else:
            print("  No clusters were formed that met the criteria.")
        print("-" * 29)
    else:
        logging.error("Clustering process may have failed, as the output file was not created.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main()

# --- END OF FILE: run_full_clustering_flat_output.py ---