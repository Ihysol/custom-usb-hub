# cli_main.py

import sys
from pathlib import Path

# Import the core logic from the separate file
from library_manager import (
    INPUT_ZIP_FOLDER, 
    PROJECT_SYMBOL_LIB, 
    list_symbols_simple, 
    process_zip, 
    purge_zip_contents
)

def main():
    """
    Main function to determine mode (process or purge) and iterate over zip files.
    """
    
    # Check for the --purge command line argument
    if len(sys.argv) > 1 and sys.argv[1].lower() == '--purge':
        print("\n*** PURGE MODE ACTIVATED ***")
        for zip_file in INPUT_ZIP_FOLDER.glob("*.zip"):
            purge_zip_contents(zip_file)
    else:
        for zip_file in INPUT_ZIP_FOLDER.glob("*.zip"):
            print(f"\n--- Processing {zip_file.name} ---")
            process_zip(zip_file)

if __name__ == "__main__": 
    print("--- Starting Part Localization Script ---")
    # Printouts moved here to keep library_manager clean
    print("Source ZIP folder:", INPUT_ZIP_FOLDER)
    print("Project Symbols Library:", PROJECT_SYMBOL_LIB)
    # Run the main processing function
    main()
    