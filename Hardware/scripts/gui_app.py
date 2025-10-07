# gui_app.py

import dearpygui.dearpygui as dpg
from pathlib import Path
import os
import sys
from datetime import datetime 
import subprocess 
import io 
import re 
import zipfile 
import tempfile 

# Import Tkinter for the native file dialog
import tkinter as tk
from tkinter import filedialog as fd

# --- Import and Configuration ---
try:
    from library_manager import INPUT_ZIP_FOLDER 
    CLI_SCRIPT_PATH = Path(__file__).parent / "cli_main.py"
    def get_existing_main_symbols(): return set() 

except ImportError:
    print("Warning: library_manager not found. Using dummy paths and folder.")
    INPUT_ZIP_FOLDER = Path.cwd() 
    CLI_SCRIPT_PATH = Path.cwd() / "cli_main_dummy.py"
    def get_existing_main_symbols(): return set()
    
# Function to execute the CLI script (MODIFIED FOR UNICODE SAFETY)
def execute_library_action(paths, is_purge):
    """
    Executes the external CLI script and handles output encoding safely.
    """
    python_exe = sys.executable 
    
    action = "process"
    if is_purge:
        action = "purge"
        
    cmd = [python_exe, str(CLI_SCRIPT_PATH), action] + [str(p) for p in paths]
    
    # LOG COMMAND WITHOUT TIMESTAMP
    #log_message(None, None, f"Executing: {' '.join(cmd)}", add_timestamp=False)
    
    # --- Execute and Capture Output Safely ---
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True, 
            encoding='utf-8', 
            errors='ignore' 
        )
        
        output = result.stdout + result.stderr

        if result.returncode == 0:
            return True, output
        else:
            # Handle the error case and format the output
            error_output = f"--- CLI ERROR START ---\n"
            error_output += f"CLI failed with exit code {result.returncode}\n"
            error_output += output
            error_output += f"--- CLI ERROR END ---"
            return False, error_output

    except FileNotFoundError:
        return False, "ERROR: Python interpreter or CLI script not found."
    except Exception as e:
        return False, f"CRITICAL ERROR during CLI execution: {e}"


# --- Constants ---
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 600
CURRENT_PATH_TAG = "current_path_text" 
FILE_COUNT_TAG = "file_count_text" 
FILE_CHECKBOXES_CONTAINER = "file_checkboxes_container" 
SCROLL_FLAG_TAG = "scroll_flag_int" 
ACTION_SECTION_TAG = "action_section_group"
LOG_TEXT_TAG = "log_text_container" 
LOG_WINDOW_CHILD_TAG = "log_window_child" 

# --- State Management ---
all_selected_paths = [] 

# ===================================================
# --- DPG UTILITIES ---
# ===================================================

def log_message(sender, app_data, user_data: str, add_timestamp: bool = True, is_cli_output: bool = False):
    """
    Dynamically adds a text widget to the log container, optionally with a timestamp and color.
    
    Args:
        user_data (str): The message content.
        add_timestamp (bool): If True, prepends a timestamp. Defaults to True.
        is_cli_output (bool): If True, uses the darker CLI output theme. Defaults to False.
    """
    
    # 1. Format the log entry
    if not user_data:
        # If user_data is empty, treat it as a newline and stop (to avoid empty text widgets)
        dpg.add_text(" ", parent=LOG_TEXT_TAG, tag=dpg.generate_uuid())
        return

    log_entry = user_data
    if add_timestamp:
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        log_entry = f"{timestamp} {user_data}"
    
    # 2. Determine theme based on content
    theme_tag = "default_log_theme"
    user_data_upper = log_entry.upper()
    
    if is_cli_output:
        # Apply the dedicated theme for raw CLI output
        theme_tag = "cli_output_theme"
    elif "[FAIL]" in user_data_upper or "[ERROR]" in user_data_upper or "CRITICAL ERROR" in user_data_upper:
        theme_tag = "error_log_theme"
    elif "[OK]" in user_data_upper or "[SUCCESS]" in user_data_upper:
        theme_tag = "success_log_theme"
    
    # 3. Add the new message as a separate text item to the container
    new_text_item = dpg.add_text(log_entry, parent=LOG_TEXT_TAG, wrap=0, tag=dpg.generate_uuid())
    dpg.bind_item_theme(new_text_item, theme_tag)

    # 4. Trigger and apply scroll to bottom
    current_scroll_value = dpg.get_value(SCROLL_FLAG_TAG)
    dpg.set_value(SCROLL_FLAG_TAG, current_scroll_value + 1)
    
    if dpg.does_item_exist(LOG_WINDOW_CHILD_TAG):
        dpg.set_y_scroll(LOG_WINDOW_CHILD_TAG, -1.0) 


def clear_log(sender, app_data):
    """Clears the log text area by deleting all child items in the container."""
    # Delete all items inside the LOG_TEXT_TAG group
    dpg.delete_item(LOG_TEXT_TAG, children_only=True) 
    
    log_message(None, None, "Log cleared.", add_timestamp=True)
    log_message(None, None, "Ready.", add_timestamp=True)


def build_file_list_ui(zip_paths):
    """Dynamically creates a list of checkboxes for the selected files."""
    global all_selected_paths
    
    dpg.delete_item(FILE_CHECKBOXES_CONTAINER, children_only=True)
    
    dpg.set_value(FILE_COUNT_TAG, f"Total files found: {len(zip_paths)}")
    
    if not zip_paths:
        with dpg.group(parent=FILE_CHECKBOXES_CONTAINER):
            dpg.add_text("No ZIP files loaded. Select a folder to begin.", color=[255, 165, 0])
        all_selected_paths = []
        return
    
    all_selected_paths = zip_paths
    
    with dpg.group(parent=FILE_CHECKBOXES_CONTAINER):
        for i, p in enumerate(zip_paths):
            tag = f"checkbox_{i}" 
            dpg.add_checkbox(label=p.name, default_value=True, tag=tag)

def toggle_all_checkboxes(sender, app_data, value):
    """Sets all file checkboxes to the given value (True or False)."""
    global all_selected_paths
    for i in range(len(all_selected_paths)):
        tag = f"checkbox_{i}"
        if dpg.does_item_exist(tag):
            dpg.set_value(tag, value)

# ===================================================
# --- CORE LOGIC ---
# ===================================================

def get_active_files_for_processing():
    """Scans the UI checkboxes to return a list of Path objects for active files."""
    global all_selected_paths
    active_paths = []
    
    for i, p in enumerate(all_selected_paths):
        tag = f"checkbox_{i}"
        if dpg.does_item_exist(tag):
            if dpg.get_value(tag):
                active_paths.append(p)
                
    return active_paths

def process_action(sender, app_data, is_purge):
    """Triggers the CLI script with the selected action, using ONLY active files."""
    
    active_files = get_active_files_for_processing()
    
    if not active_files:
        log_message(None, None, "ERROR: No active ZIP files selected for action.")
        return

    action_name = "PURGE" if is_purge else "PROCESS"
    log_message(None, None, f"--- Initiating {action_name} for {len(active_files)} active file(s) ---")
    
    success, output = execute_library_action(active_files, is_purge=is_purge)
    
    # Log the CLI output line-by-line using the new is_cli_output=True flag
    for line in output.splitlines():
        log_message(None, None, line, add_timestamp=False, is_cli_output=True) 
    
    # Log final status with a timestamp
    if success:
        log_message(None, None, f"[OK] {action_name} SUCCESSFUL.")
    else:
        log_message(None, None, f"[FAIL] {action_name} FAILED. See output above.")
    
    # Log a separator line and a newline without timestamps
    log_message(None, None, "------------------------------------------------------", add_timestamp=False)
    log_message(None, None, "", add_timestamp=False)


# --- TKINTER DIALOG HELPERS (Unchanged) ---

def _init_tkinter_root():
    root = tk.Tk()
    root.withdraw()
    return root

def select_zip_folder():
    """Opens native dialog for selecting a folder and finds all Zips within."""
    root = _init_tkinter_root()
    try:
        folder_path_str = fd.askdirectory(
            title="Select Folder Containing ZIP Archives",
            initialdir=str(INPUT_ZIP_FOLDER.resolve())
        )
        
        if not folder_path_str:
            return []
            
        folder_path = Path(folder_path_str)
        zip_files = list(folder_path.glob("*.zip"))
        
        return zip_files
    finally:
        root.destroy()


# ===================================================
# --- DPG INTERFACE CALLBACKS ---
# ===================================================

def clear_view_state():
    """Internal function to clear the UI/state when selection is dropped."""
    global all_selected_paths
    
    all_selected_paths.clear()
    build_file_list_ui([])
    
    if dpg.does_item_exist(ACTION_SECTION_TAG):
        dpg.hide_item(ACTION_SECTION_TAG)
        
    log_message(None, None, "Selection cleared.")

def show_native_folder_dialog(sender, app_data):
    """Opens dialog, processes ZIPs, and reloads the UI."""
    
    paths = select_zip_folder()
    
    if not paths:
        log_message(None, None, "Folder selection cancelled or no ZIP files found.")
        dpg.hide_item(ACTION_SECTION_TAG)
        build_file_list_ui([])
        dpg.set_value(CURRENT_PATH_TAG, "Current Folder: (None Selected)")
        return
    
    selected_folder_str = str(paths[0].parent.resolve())
    log_message(None, None, f"Found {len(paths)} ZIP file(s).")
    reload_folder_from_path(selected_folder_str)


# ===================================================
# --- GUI Layout and Initialization ---
# ===================================================

def reload_folder_from_path(folder_path_str):
    """Helper to reload the UI based on a known path string."""
    folder_path = Path(folder_path_str).resolve()
    
    if not folder_path.exists() or not folder_path.is_dir():
        log_message(None, None, f"ERROR: Folder not found at '{folder_path}'.")
        build_file_list_ui([])
        return
        
    try:
        paths = list(folder_path.glob("*.zip"))
        valid_paths = [p for p in paths if p.exists()]
        
        dpg.set_value(CURRENT_PATH_TAG, f"Current Folder: {folder_path.resolve()}")

        if valid_paths:
            dpg.show_item(ACTION_SECTION_TAG)
        else:
            dpg.hide_item(ACTION_SECTION_TAG)
            
        build_file_list_ui(valid_paths)
        
    except Exception as e:
        log_message(None, None, f"ERROR scanning folder: {e}")
        build_file_list_ui([])


def initial_load():
    """Scans the default INPUT_ZIP_FOLDER path on startup and updates the GUI."""
    
    target_folder = INPUT_ZIP_FOLDER.resolve()
    
    dpg.set_value(CURRENT_PATH_TAG, f"Current Folder: {target_folder}")
    
    if not target_folder.exists() or not target_folder.is_dir():
        log_message(None, None, f"ERROR: Input folder not found at '{target_folder}'. Skipping initial load.")
        dpg.set_value(CURRENT_PATH_TAG, "Current Folder: (Path Error)")
        return
    
    log_message(None, None, f"Checking default folder: '{target_folder}'")
    
    try:
        paths = list(target_folder.glob("*.zip"))
        valid_paths = [p for p in paths if p.exists()]
    except Exception as e:
        log_message(None, None, f"ERROR scanning folder: {e}")
        valid_paths = []
        
    if valid_paths:
        log_message(None, None, f"Successfully loaded {len(valid_paths)} ZIP file(s) from default path.")
        dpg.show_item(ACTION_SECTION_TAG)
    else:
        log_message(None, None, "No ZIP files found in the default folder.")
        
    build_file_list_ui(valid_paths)


def create_gui():
    dpg.create_context()
    dpg.create_viewport(title='KiCad Library Manager', width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
    dpg.setup_dearpygui()

    # --- Theme setup (Minimal to avoid errors) ---
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (25, 25, 25))
    dpg.bind_theme(global_theme)
    
    # --- Log Color Themes ---
    
    # 1. Default (Timestamped messages) - Bright/Normal Grey
    with dpg.theme(tag="default_log_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (200, 200, 200)) 
            
    # 2. CLI Output (Non-timestamped messages) - Darker Grey
    with dpg.theme(tag="cli_output_theme"):
        with dpg.theme_component(dpg.mvAll):
            # A darker grey to distinguish it from the standard log
            dpg.add_theme_color(dpg.mvThemeCol_Text, (140, 140, 140)) 
            
    # 3. Error/Fail
    with dpg.theme(tag="error_log_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 50, 50)) 
            
    # 4. Success
    with dpg.theme(tag="success_log_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (0, 255, 0)) 
    
    # --- Main Window ---
    with dpg.window(tag="main_window", label="KiCad Library Manager"):
        dpg.set_primary_window("main_window", True)
        
        # 1. Selection Section 
        dpg.add_text("1. Select Archive Folder (ZIPs will be scanned automatically):", color=[0, 255, 255])
        
        # Button and Path are now together in one horizontal group
        with dpg.group(horizontal=True):
            dpg.add_button(label="Open Folder...", callback=show_native_folder_dialog) 
            dpg.add_text("Current Folder: (Initializing...)", tag=CURRENT_PATH_TAG, wrap=0, color=[150, 150, 255])
        
        dpg.add_separator()
        
        # 2. Active Files Header and Count (Always visible for layout stability)
        dpg.add_text("2. Active ZIP Archives for Processing:", color=[255, 255, 0])
        dpg.add_text("Total files found: 0", tag=FILE_COUNT_TAG, color=[0, 255, 0])
        
        # File List Container (Always Visible)
        with dpg.child_window(tag=FILE_CHECKBOXES_CONTAINER, width=-1, height=180, border=True):
            pass 
        
        # 3. Action Buttons and Toggles (Hidden by default)
        with dpg.group(tag=ACTION_SECTION_TAG, show=False):
            
            # Global Checkbox Toggles
            with dpg.group(horizontal=True):
                dpg.add_button(label="Select All", callback=lambda s, a: toggle_all_checkboxes(s, a, True))
                dpg.add_button(label="Deselect All", callback=lambda s, a: toggle_all_checkboxes(s, a, False))

            dpg.add_separator()
            
            # Action Buttons Section
            with dpg.group(horizontal=True, horizontal_spacing=20):
                dpg.add_button(
                    label="🚀 PROCESS / IMPORT", 
                    tag="process_btn", 
                    callback=lambda s, a: process_action(s, a, False),
                    width=200
                )
                dpg.add_button(
                    label="🗑️ PURGE / DELETE", 
                    tag="purge_btn", 
                    callback=lambda s, a: process_action(s, a, True),
                    width=200
                )
                dpg.add_text("NOTE: Only checked files will be used.")

            dpg.add_separator()

        # Log Output Section (Always visible)
        with dpg.group(horizontal=True):
            dpg.add_text("CLI Output Log:")
            dpg.add_button(label="🧹 Clear Log", callback=clear_log, small=True) 
            
        # Log Text Area (Wrapped in child window for scrolling)
        with dpg.child_window(tag=LOG_WINDOW_CHILD_TAG, width=-1, height=-1, border=True):
            # This group holds the dynamically added dpg.add_text items
            dpg.add_group(tag=LOG_TEXT_TAG, width=-1)
        
        # Scroll Flag Item (Hidden)
        dpg.add_input_int(tag=SCROLL_FLAG_TAG, default_value=0, show=False)


    # --- FINAL SETUP AND INITIAL LOAD ---
    dpg.show_viewport()
    
    initial_load() 
    
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    try:
        import dearpygui.dearpygui as dpg
    except ImportError:
        print("Error: DearPyGui is not installed. Please install it: pip install dearpygui")
        sys.exit(1)
        
    try:
        import tkinter as tk
    except ImportError:
        print("Error: tkinter is required for the native file dialog but is not available.")
        sys.exit(1)
        
    create_gui()