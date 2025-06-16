# In global_state.py
import tkinter as tk # Keep this import if other parts need tk constants, but the TkVars themselves will be None
from collections import deque
import threading
from pydualsense import pydualsense

# --- Global Controller/Application State ---
ds = None
running = False
is_initializing_config = False


# --- Tkinter StringVars for GUI updates (Reverted to None - Initialized in main_app.py) ---
connection_status_var = None
gyro_text_var = None
accel_text_var = None

# --- Global Variables for Position Saving and Smoothing ---
saved_positions = []
saved_position_labels = []
initial_range_padding = 0.5
initial_padding_value_var = None # Reverted

smoothing_window_size = 10
smoothing_value_var = None # Reverted

gyro_buffers = {
    'Pitch': deque(maxlen=smoothing_window_size),
    'Yaw': deque(maxlen=smoothing_window_size),
    'Roll': deque(maxlen=smoothing_window_size)
}
accel_buffers = {
    'X': deque(maxlen=smoothing_window_size),
    'Y': deque(maxlen=smoothing_window_size),
    'Z': deque(maxlen=smoothing_window_size)
}
data_buffers_lock = threading.Lock()

# --- Gyroscope Re-leveling Offset ---
gyro_offset = [0.0, 0.0, 0.0]

# --- NEW: Reconnect Related Globals ---
# auto_reconnect_enabled is now directly read from auto_reconnect_enabled_var.get()
auto_reconnect_enabled_var = None # Reverted
manual_reconnect_requested = False
RECONNECT_DELAY_SECONDS = 3
last_disconnect_attempt_time = 0

# --- NEW: Input Delay Display ---
input_delay_ms_var = None # Reverted
last_read_timestamp = None

# --- Global Variables for Multi-Point Recording Settings (Reverted to None) ---
num_points_to_record_var = None
record_duration_ms_var = None
is_recording = False

# --- Global for tracking current highlight state and selected position ---
current_highlighted_label_index = -1
selected_position_index = -1

# --- Tkinter vars for per-position editing controls (Reverted to None) ---
per_position_padding_var = None
per_position_name_var = None
per_position_use_pitch_var = None
per_position_use_yaw_var = None
per_position_use_roll_var = None
per_position_use_accel_x_var = None
per_position_use_accel_y_var = None
per_position_use_accel_z_var = None

# --- Tkinter variables for editing individual axis values (Reverted to None) ---
edit_avg_pitch_var = None
edit_avg_yaw_var = None
edit_avg_roll_var = None
edit_avg_accel_x_var = None
edit_avg_accel_y_var = None
edit_avg_accel_z_var = None

# --- UI Element References (for global access, assigned in main_app.py) ---
root = None
edit_position_controls_frame = None
saved_positions_scrollable_frame = None
canvas_window_item_id = None
combine_button = None
save_button = None
motions_frame = None
controller_thread = None

# --- Motion Sequence Globals ---
saved_motion_sequences = []
saved_motion_sequence_labels = []
selected_motion_sequence_index = -1

# Tkinter vars for Motion Sequence editing (Reverted to None)
motion_sequence_name_var = None
motion_sequence_time_window_var = None
motion_sequence_repetition_count_var = None
motion_sequence_action_var = None
motion_sequence_reset_grace_var = None

edit_motion_controls_frame = None
motion_sequence_export_file_var = None
motion_sequence_export_reps_var = None