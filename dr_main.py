# --- START OF FILE dr_main.py ---

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Import the main functions from the pipeline modules
from a_converter import main as run_converter
from b_parser import main as run_parser
from c_processor import main as run_processor
from utils import get_paths, ProjectPaths
from utils2 import convert_json_to_docx, sort_json_file

# #############################################################################
# --- CLI Application Setup ---
# #############################################################################

# --- Configuration ---
# This is the single source of truth for the project name.
# You can change this to work on a different project.
PROJECT_NAME = "DRHASSAN"

# Initialize Typer for the CLI app and Rich for beautiful terminal output
app = typer.Typer(
    name="dr-qa-pipe",
    help="A command-line tool to process medical QA documents through a multi-step pipeline.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

# #############################################################################
# --- Helper Functions ---
# #############################################################################

def create_hyperlink(path: Path) -> str:
    """Creates a clickable hyperlink for supported terminals."""
    # .as_uri() creates the 'file://...' link
    uri = path.resolve().as_uri()
    return f"[link={uri}]{path.name}[/link]"

def _setup_logging_and_paths(ctx: typer.Context):
    """
    A callback function that runs before any command. It sets up logging
    and project paths, storing them in the context for other commands to use.
    """
    code_dir = Path(__file__).resolve().parent

    # Configure logging
    log_dir = code_dir / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f'{PROJECT_NAME}_cli.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file, mode='a'), logging.StreamHandler()]
    )
    
    # Get project paths and attach them to the context object
    try:
        paths = get_paths(code_dir, PROJECT_NAME)
        ctx.obj = paths
    except FileNotFoundError as e:
        console.print(f"[bold red]ERROR:[/bold red] Project '{PROJECT_NAME}' not found. {e}")
        raise typer.Exit(code=1)

# #############################################################################
# --- CLI Commands ---
# #############################################################################

@app.command(name="convert", help="Step 1: Convert a PDF from '0Source' to a text file in '1Texted'.")
def convert_command(
    ctx: typer.Context,
    subject_file: Path = typer.Argument(..., help="The PDF filename (e.g., 'Cardiology.pdf').")
):
    """Converts a single PDF to a text file."""
    paths: ProjectPaths = ctx.obj
    console.print(f"\n[bold blue]--- Running: PDF to Text Conversion ---[/bold blue]")
    
    source_path = paths.SRCFILE_DIR / subject_file
    if not source_path.exists():
        console.print(f"[bold red]ERROR:[/bold red] Source file not found: {source_path}")
        raise typer.Exit(code=1)

    output_path = run_converter(paths, subject_file, overwrite=True)
    
    if output_path:
        console.print(f"[bold green]SUCCESS:[/bold green] Converted to text file: {create_hyperlink(output_path)}")
    else:
        console.print("[bold red]FAILURE:[/bold red] Conversion step failed.")
        raise typer.Exit(code=1)

# #############################################################################

@app.command(name="parse", help="Step 2: Parse a text file from '1Texted' to a JSON in '2Parsed'.")
def parse_command(
    ctx: typer.Context,
    subject_file: Path = typer.Argument(..., help="The text filename (e.g., 'Cardiology.txt').")
):
    """Parses a single text file into a structured JSON."""
    paths: ProjectPaths = ctx.obj
    console.print(f"\n[bold blue]--- Running: Text to JSON Parsing ---[/bold blue]")
    
    source_path = paths.TEXTED_DIR / subject_file
    if not source_path.exists():
        console.print(f"[bold red]ERROR:[/bold red] Source file not found: {source_path}")
        raise typer.Exit(code=1)
        
    output_path = run_parser(paths, subject_file, overwrite=True)
    
    if output_path:
        console.print(f"[bold green]SUCCESS:[/bold green] Parsed to JSON file: {create_hyperlink(output_path)}")
    else:
        console.print("[bold red]FAILURE:[/bold red] Parsing step failed.")
        raise typer.Exit(code=1)

# #############################################################################

@app.command(name="process", help="Step 3: Process a JSON from '2Parsed' using AI to '3Processed'.")
def process_command(
    ctx: typer.Context,
    subject_file: Path = typer.Argument(..., help="The JSON filename (e.g., 'Cardiology.json')."),
    overwrite: bool = typer.Option(False, "--overwrite", "-o", help="Overwrite existing processed file and start fresh.")
):
    """Processes a single parsed JSON file with the AI agent."""
    paths: ProjectPaths = ctx.obj
    console.print(f"\n[bold blue]--- Running: AI Processing ---[/bold blue]")
    
    source_path = paths.PARSED_DIR / subject_file
    if not source_path.exists():
        console.print(f"[bold red]ERROR:[/bold red] Source file not found: {source_path}")
        raise typer.Exit(code=1)

    # run_processor doesn't return a path, it works on the file in-place
    run_processor(paths, subject_file, overwrite=overwrite)
    
    subject_stem = subject_file.stem
    output_path = paths.PROCESSED_DIR / f"{subject_stem}_processed.json"
    
    if output_path.exists():
        console.print(f"[bold green]SUCCESS:[/bold green] AI processing complete. Output file: {create_hyperlink(output_path)}")
    else:
        console.print("[bold red]FAILURE:[/bold red] AI Processing step failed.")
        raise typer.Exit(code=1)

# #############################################################################

@app.command(name="full-pipeline", help="Run the entire Convert -> Parse -> Process pipeline for a single PDF.")
def full_pipeline_command(
    ctx: typer.Context,
    subject_file: Path = typer.Argument(..., help="The source PDF filename (e.g., 'Cardiology.pdf')."),
    overwrite: bool = typer.Option(False, "--overwrite", "-o", help="Overwrite all steps, including the final processed file.")
):
    """Runs all steps of the pipeline in sequence."""
    paths: ProjectPaths = ctx.obj
    subject_stem = subject_file.stem
    
    # --- Step 1: Convert ---
    console.print(f"\n[bold magenta]===> STEP 1: CONVERTING <===[/bold magenta]")
    texted_path = run_converter(paths, subject_file, overwrite=overwrite)
    if not texted_path:
        console.print("[bold red]PIPELINE HALTED:[/bold red] Conversion failed."); raise typer.Exit(1)
    console.print(f"[green]Output:[/green] {create_hyperlink(texted_path)}")

    # --- Step 2: Parse ---
    console.print(f"\n[bold magenta]===> STEP 2: PARSING <===[/bold magenta]")
    parsed_path = run_parser(paths, texted_path.name, overwrite=overwrite)
    if not parsed_path:
        console.print("[bold red]PIPELINE HALTED:[/bold red] Parsing failed."); raise typer.Exit(1)
    console.print(f"[green]Output:[/green] {create_hyperlink(parsed_path)}")
    
    # --- Step 3: Process ---
    console.print(f"\n[bold magenta]===> STEP 3: PROCESSING WITH AI <===[/bold magenta]")
    run_processor(paths, parsed_path.name, overwrite=overwrite)
    processed_path = paths.PROCESSED_DIR / f"{subject_stem}_processed.json"
    if not processed_path.exists():
        console.print("[bold red]PIPELINE HALTED:[/bold red] AI Processing failed."); raise typer.Exit(1)
    console.print(f"[green]Output:[/green] {create_hyperlink(processed_path)}")

    # --- Step 4: Final Export ---
    console.print(f"\n[bold magenta]===> STEP 4: GENERATING DOCX OUTPUTS <===[/bold magenta]")
    
    # Unsorted (numeric order)
    docx_numeric_path = paths.OUTPUT_DIR / f"{subject_stem}_numeric_order.docx"
    convert_json_to_docx(processed_path, docx_numeric_path)
    console.print(f"[green]Created numerically sorted DOCX:[/green] {create_hyperlink(docx_numeric_path)}")

    # Sorted by choice text
    sorted_json_path = paths.PROCESSED_DIR / f"{subject_stem}_sorted_by_choice.json"
    sort_json_file(processed_path, sorted_json_path, sort_key="updated_correct_choice_text")
    if sorted_json_path.exists():
        docx_sorted_path = paths.OUTPUT_DIR / f"{subject_stem}_sorted_by_choice.docx"
        convert_json_to_docx(sorted_json_path, docx_sorted_path)
        console.print(f"[green]Created text-sorted DOCX:[/green] {create_hyperlink(docx_sorted_path)}")

    console.print("\n[bold green]✅✅✅ Full pipeline completed successfully! ✅✅✅[/bold green]")


# #############################################################################
# --- Script Entry Point ---
# #############################################################################

if __name__ == "__main__":
    app(callback=_setup_logging_and_paths)