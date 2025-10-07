# cli_main.py - FIXED Argument Parsing

import sys
from pathlib import Path
import argparse 
import os 
import io 
import locale

# =========================================================
# ⚠️ UNICODE FIX: Force standard output to use UTF-8 encoding
# (Kept from previous fix to ensure Unicode compatibility)
# =========================================================
if sys.platform.startswith('win'):
    if locale.getpreferredencoding(False) not in ['UTF-8', 'utf8']:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass
# =========================================================

# Import the core logic from the separate file
from library_manager import (
    INPUT_ZIP_FOLDER, 
    PROJECT_SYMBOL_LIB, 
    list_symbols_simple, 
    process_zip, 
    purge_zip_contents
)


def parse_arguments():
    """
    Parses command-line arguments to determine action and files, and includes help documentation.
    """
    parser = argparse.ArgumentParser(
        description="KiCad Library Manager CLI: Tool for processing or purging symbols, footprints, and 3D files from ZIP archives into a project library.",
        formatter_class=argparse.RawTextHelpFormatter 
    ) 
    
    # 💥 FIX 1: Add a mandatory positional argument for the action mode
    # This consumes the 'process' or 'purge' argument sent by the GUI.
    parser.add_argument(
        'action',
        choices=['process', 'purge'],
        help='The action to perform: "process" (import) or "purge" (delete).'
    )
    
    # Argument to override the INPUT_ZIP_FOLDER
    parser.add_argument(
        '--input_folder',
        type=str,
        help=f"Override the source folder containing ZIP files.\n(DEFAULT: '{INPUT_ZIP_FOLDER}')"
    )

    # Positional arguments for specific ZIP files
    parser.add_argument(
        'zip_files',
        nargs='*', 
        type=str,
        default=[],
        help="One or more specific ZIP file paths to process or purge.\n"
             "If provided, only these files are acted upon.\n"
             "If omitted, ALL ZIP files in the --input_folder are used."
    )

    # NOTE: The original --purge flag is no longer needed since 'action' covers it.
    
    return parser.parse_args()


def main():
    """
    Main function to determine mode (process or purge) and iterate over zip files.
    """
    args = parse_arguments()
    
    # --- Determine Source Folder ---
    source_folder = Path(args.input_folder) if args.input_folder else INPUT_ZIP_FOLDER

    # Determine the list of ZIP files to process
    zip_paths = []
    
    if args.zip_files:
        # Use only the ZIP files specified in the command line (now correctly shifted)
        zip_paths = [Path(f) for f in args.zip_files]
    else:
        # Fallback: process all ZIP files in the source_folder
        zip_paths = list(source_folder.glob("*.zip"))
        
    # Determine action and mode name based on the consumed positional argument
    is_purge = args.action == 'purge'
    action_func = purge_zip_contents if is_purge else process_zip
    mode_name = "PURGE" if is_purge else "PROCESSING"
    
    # 💥 FIX 2: Correct the display source when using the default/env path
    # The CLI output shows "Source: generate" but the GUI output showed the full path.
    # Using source_folder.resolve() ensures consistency if needed, but for now, 
    # we'll stick to printing the current path value.
    # print(f"\n*** {mode_name} MODE ACTIVATED (Source: {source_folder.resolve()}) ***")
    
    if not zip_paths:
        print(f"Warning: No ZIP files found in '{source_folder}' to process/purge.")
        # Print final symbol list (which is the same as initial)
        print("\n--- Final List of Main Symbols ---")
        list_symbols_simple(PROJECT_SYMBOL_LIB, print_list=True)
        return

    # --- Start Processing/Purging ---
    for zip_file in zip_paths:
        print(f"\n--- {mode_name} {zip_file.name} ---")
        # Now zip_file is a Path object to the ZIP file, not the string 'process'
        action_func(zip_file) 
        
    # Print final symbol list
    print("\n--- Final List of Main Symbols ---")
    list_symbols_simple(PROJECT_SYMBOL_LIB, print_list=True)

if __name__ == "__main__": 
    # print("--- Starting Part Localization Script ---")
    # Printouts moved here to keep library_manager clean
    # print("Source ZIP folder (from .env):", INPUT_ZIP_FOLDER.resolve())
    # print("Project Symbols Library:", PROJECT_SYMBOL_LIB.resolve())
    # Run the main processing function
    main()