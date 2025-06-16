import tkinter as tk
from collections import deque
from tkinter import ttk
import threading
import global_state  # Import global state
from controller_interface import read_controller_data, relevel_gyro, manual_reconnect
from config_manager import export_config, import_config
from gui_elements import create_numeric_slider_control, update_highlight_on_gui
from position_manager_gui import (
    update_saved_positions_display, select_position_for_editing,
    show_edit_position_controls, hide_edit_position_controls,
    update_per_position_padding, update_per_position_axis_detection,
    update_edited_avg_axis_value, reset_edited_avg_values,
    rename_selected_position, delete_selected_position, open_combine_dialog,
    start_recording_thread
)
from motion_sequence_manager_gui import (
    update_motion_sequences_display, select_motion_sequence_for_editing,
    show_edit_motion_controls, hide_edit_motion_controls,
    update_motion_time_window, rename_selected_motion, delete_selected_motion,
    edit_motion_positions, create_new_motion_sequence
)


# --- Global Functions for Sliders (moved from original script for clarity) ---
# These functions modify global_state and are passed as commands to sliders
def update_initial_range_padding(val):
    global_state.initial_range_padding = round(float(val), 3)
    global_state.initial_padding_value_var.set(global_state.initial_range_padding)


def update_smoothing_window(val):
    global_state.smoothing_window_size = int(float(val))
    global_state.smoothing_value_var.set(global_state.smoothing_window_size)
    if global_state.smoothing_window_size < 1:
        global_state.smoothing_window_size = 1
    with global_state.data_buffers_lock:
        for key in global_state.gyro_buffers:
            global_state.gyro_buffers[key] = deque(list(global_state.gyro_buffers[key]),
                                                   maxlen=global_state.smoothing_window_size)
        for key in global_state.accel_buffers:
            global_state.accel_buffers[key] = deque(list(global_state.accel_buffers[key]),
                                                    maxlen=global_state.smoothing_window_size)


def update_num_points_to_record(val):
    global_state.num_points_to_record_var.set(int(float(val)))


def update_record_duration(val):
    global_state.record_duration_ms_var.set(int(float(val)))


# Helper function to update auto_reconnect_enabled flag
def _update_auto_reconnect_setting(val):
    # The controller_interface now directly reads global_state.auto_reconnect_enabled_var.get()
    print(f"Auto-Reconnect Enabled: {val}")


# --- GUI Close Handler ---
def on_closing():
    global_state.running = False

    # Attempt to join the controller thread gracefully
    # INCREASED TIMEOUT FOR MORE ROBUST SHUTDOWN
    if global_state.controller_thread and global_state.controller_thread.is_alive():
        print("Attempting to join controller thread...")
        global_state.controller_thread.join(timeout=5)  # <--- INCREASED TIMEOUT TO 5 SECONDS
        if global_state.controller_thread.is_alive():
            print("Warning: Controller thread did not terminate cleanly within timeout.")

    global_state.root.destroy()
    print("Application closed.")


# NEW: Deferred thread start function
def _start_controller_thread_deferred():
    global_state.controller_thread = threading.Thread(target=read_controller_data, daemon=True)
    global_state.controller_thread.start()


# --- Main GUI Setup ---
if __name__ == "__main__":
    global_state.root = tk.Tk()  # Assign root to global_state

    # --- CRITICAL: Initialize all Tkinter variables *after* global_state.root is created ---
    global_state.connection_status_var = tk.StringVar(value="Initializing controller...")
    global_state.gyro_text_var = tk.StringVar(value="Pitch: --\nYaw:   --\nRoll:  --")
    global_state.accel_text_var = tk.StringVar(value="X: --\nY: --\nZ: --")

    # ADDED: Initialize auto_reconnect_enabled_var
    global_state.auto_reconnect_enabled_var = tk.BooleanVar(value=True) # Default to True as per checkbox state in GUI

    global_state.input_delay_ms_var = tk.StringVar(value="Latency: -- ms")

    global_state.initial_padding_value_var = tk.DoubleVar(value=global_state.initial_range_padding)
    global_state.smoothing_value_var = tk.IntVar(value=global_state.smoothing_window_size)

    global_state.num_points_to_record_var = tk.IntVar(value=5)
    global_state.record_duration_ms_var = tk.IntVar(value=200)

    global_state.per_position_padding_var = tk.DoubleVar(value=global_state.initial_range_padding)
    global_state.per_position_name_var = tk.StringVar(value="No position selected")
    global_state.per_position_use_pitch_var = tk.BooleanVar(value=True)
    global_state.per_position_use_yaw_var = tk.BooleanVar(value=True)
    global_state.per_position_use_roll_var = tk.BooleanVar(value=True)
    global_state.per_position_use_accel_x_var = tk.BooleanVar(value=True)
    global_state.per_position_use_accel_y_var = tk.BooleanVar(value=True)
    global_state.per_position_use_accel_z_var = tk.BooleanVar(value=True)

    global_state.edit_avg_pitch_var = tk.DoubleVar(value=0.0)
    global_state.edit_avg_yaw_var = tk.DoubleVar(value=0.0)
    global_state.edit_avg_roll_var = tk.DoubleVar(value=0.0)
    global_state.edit_avg_accel_x_var = tk.DoubleVar(value=0.0)
    global_state.edit_avg_accel_y_var = tk.DoubleVar(value=0.0)
    global_state.edit_avg_accel_z_var = tk.DoubleVar(value=0.0)

    global_state.motion_sequence_name_var = tk.StringVar(value="No motion selected")
    global_state.motion_sequence_time_window_var = tk.IntVar(value=1000)
    global_state.motion_sequence_repetition_count_var = tk.IntVar(value=0)
    global_state.motion_sequence_action_var = tk.StringVar(value="")
    global_state.motion_sequence_reset_grace_var = tk.IntVar(value=100)
    global_state.motion_sequence_export_reps_var = tk.BooleanVar(value=False)
    global_state.motion_sequence_export_file_var = tk.StringVar(value="")
    # --- END CRITICAL INITIALIZATION ---

    global_state.root.title("DualSense Motion Data & Position Saver")
    global_state.root.geometry("1000x750")
    global_state.root.resizable(False, False)

    notebook = ttk.Notebook(global_state.root)
    notebook.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    # --- Main Data Tab ---
    main_data_tab_frame = ttk.Frame(notebook)
    notebook.add(main_data_tab_frame, text="Main Data")

    status_label = tk.Label(main_data_tab_frame, textvariable=global_state.connection_status_var,
                            font=("Segoe UI", 12, "bold"), pady=5)
    status_label.pack(fill="x")

    gyro_frame = tk.LabelFrame(main_data_tab_frame, text="Gyroscope (Angular Velocity)", padx=15, pady=15)
    gyro_frame.pack(padx=5, pady=5, fill="x", expand=True)

    gyro_label = tk.Label(gyro_frame, textvariable=global_state.gyro_text_var, justify=tk.LEFT,
                          font=("Consolas", 14), foreground="blue")
    gyro_label.pack(fill="both", expand=True)

    accel_frame = tk.LabelFrame(main_data_tab_frame, text="Accelerometer (Linear Acceleration)", padx=15, pady=15)
    accel_frame.pack(padx=5, pady=5, fill="x", expand=True)

    accel_label = tk.Label(accel_frame, textvariable=global_state.accel_text_var, justify=tk.LEFT,
                           font=("Consolas", 14), foreground="green")
    accel_label.pack(fill="both", expand=True)

    global_state.save_button = tk.Button(main_data_tab_frame, text="Save Current Position (Multi-Point)",
                                         command=start_recording_thread,
                                         font=("Segoe UI", 12), bg="lightblue", activebackground="darkblue",
                                         activeforeground="white")
    global_state.save_button.pack(pady=10)

    tk.Label(main_data_tab_frame, text="Note: This always creates a NEW saved position.", font=("Segoe UI", 8),
             fg="gray").pack()

    input_delay_label = tk.Label(main_data_tab_frame, textvariable=global_state.input_delay_ms_var,
                                 font=("Segoe UI", 10), anchor="w", padx=5)
    input_delay_label.pack(fill="x")

    # --- Controls Tab ---
    controls_tab_frame = ttk.Frame(notebook)
    notebook.add(controls_tab_frame, text="Controls")

    relevel_button = tk.Button(controls_tab_frame, text="Re-level Gyroscope", command=relevel_gyro,
                               font=("Segoe UI", 10), bg="#FFD700", activebackground="#DAA520")
    relevel_button.pack(pady=5)

    export_button = tk.Button(controls_tab_frame, text="Export Config", command=export_config,
                              font=("Segoe UI", 10), bg="#ADD8E6", activebackground="#87CEEB")
    export_button.pack(pady=5)
    import_button = tk.Button(controls_tab_frame, text="Import Config", command=import_config,
                              font=("Segoe UI", 10), bg="#90EE90", activebackground="#66CDAA")
    import_button.pack(pady=5)

    manual_reconnect_button = tk.Button(controls_tab_frame, text="Manual Reconnect", command=manual_reconnect,
                                        font=("Segoe UI", 10), bg="#FFC0CB", activebackground="#FF69B4")
    manual_reconnect_button.pack(pady=5)

    auto_reconnect_checkbox = ttk.Checkbutton(controls_tab_frame, text="Enable Auto-Reconnect",
                                              variable=global_state.auto_reconnect_enabled_var,
                                              command=lambda: _update_auto_reconnect_setting(
                                                  global_state.auto_reconnect_enabled_var.get()))
    auto_reconnect_checkbox.pack(pady=5, anchor='w')

    recording_settings_frame = tk.LabelFrame(controls_tab_frame, text="Position Recording Settings", padx=5, pady=5)
    recording_settings_frame.pack(padx=5, pady=10, fill="x")

    # Number of Points to Record control
    create_numeric_slider_control(
        parent_frame=recording_settings_frame,
        label_text="Number of Points to Record:",
        tk_var=global_state.num_points_to_record_var,
        slider_from=1,
        slider_to=30,
        slider_command=update_num_points_to_record,
        default_error_val=5,
        is_float=False
    )

    # Recording Duration control
    create_numeric_slider_control(
        parent_frame=recording_settings_frame,
        label_text="Recording Duration (ms):",
        tk_var=global_state.record_duration_ms_var,
        slider_from=50,
        slider_to=1000,
        slider_command=update_record_duration,
        default_error_val=200,
        is_float=False
    )

    # Initial Range Padding control
    initial_padding_frame = tk.LabelFrame(controls_tab_frame, text="Initial Range Padding for New Positions", padx=5,
                                          pady=5)
    initial_padding_frame.pack(padx=5, pady=10, fill="x")
    create_numeric_slider_control(
        parent_frame=initial_padding_frame,
        label_text="",
        tk_var=global_state.initial_padding_value_var,
        slider_from=0.0,
        slider_to=100.0,
        slider_command=update_initial_range_padding,
        default_error_val=0.5,
        is_float=True
    )

    smoothing_frame = tk.LabelFrame(controls_tab_frame, text="Motion Smoothing (Higher = More Stable Data)", padx=5,
                                    pady=5)
    smoothing_frame.pack(padx=5, pady=10, fill="x")
    create_numeric_slider_control(
        parent_frame=smoothing_frame,
        label_text="",
        tk_var=global_state.smoothing_value_var,
        slider_from=1,
        slider_to=100,
        slider_command=update_smoothing_window,
        default_error_val=10,
        is_float=False
    )

    # --- New Motions Tab ---
    motions_tab_frame = ttk.Frame(notebook)
    notebook.add(motions_tab_frame, text="Motions")
    create_motion_button = tk.Button(motions_tab_frame, text="Create New Motion Sequence",
                                     command=create_new_motion_sequence,
                                     font=("Segoe UI", 12), bg="lightblue", activebackground="darkblue",
                                     activeforeground="white")
    create_motion_button.pack(pady=10)
    global_state.motions_frame = tk.LabelFrame(motions_tab_frame, text="Saved Motion Sequences", padx=5, pady=5)
    global_state.motions_frame.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Sidebar for Saved Positions ---
    global_state.saved_positions_frame = tk.LabelFrame(global_state.root, text="Saved Positions", padx=5, pady=5)
    global_state.saved_positions_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    global_state.canvas_for_positions = tk.Canvas(global_state.saved_positions_frame)
    global_state.scrollbar_for_positions = ttk.Scrollbar(global_state.saved_positions_frame, orient="vertical",
                                                         command=global_state.canvas_for_positions.yview)

    global_state.saved_positions_scrollable_frame = tk.Frame(global_state.canvas_for_positions)

    global_state.canvas_window_item_id = global_state.canvas_for_positions.create_window((0, 0),
                                                                                         window=global_state.saved_positions_scrollable_frame,
                                                                                         anchor="nw")


    def _on_canvas_configure(event):
        if global_state.saved_positions_scrollable_frame.winfo_exists():
            global_state.canvas_for_positions.itemconfigure(global_state.canvas_window_item_id, width=event.width + 1)
            global_state.saved_positions_scrollable_frame.update_idletasks()
            global_state.canvas_for_positions.config(scrollregion=global_state.canvas_for_positions.bbox("all"))


    global_state.canvas_for_positions.bind("<Configure>", _on_canvas_configure)

    global_state.canvas_for_positions.configure(yscrollcommand=global_state.scrollbar_for_positions.set)

    global_state.canvas_for_positions.pack(side="top", fill="both", expand=True)
    global_state.scrollbar_for_positions.pack(side="right", fill="y")

    update_saved_positions_display()

    global_state.combine_button = tk.Button(global_state.saved_positions_frame, text="Combine Selected Positions",
                                            command=open_combine_dialog)

    # --- Start Controller Thread (DEFERRED) ---
    # Schedule the thread to start after the Tkinter event loop has processed initial events
    global_state.root.after_idle(_start_controller_thread_deferred)

    # --- Handle Window Closing Event ---
    global_state.root.protocol("WM_DELETE_WINDOW", on_closing)

    # --- Start Tkinter Event Loop ---
    global_state.root.mainloop()
    print("Application closed.")