# In global_state.py

import threading
import tkinter as tk

# --- Constants ---
# UPDATED: Default values rounded as requested
DEFAULT_HOME_ORIENTATION = [0.75, 0.65, 0.0, 0.0]

# --- Application State ---
running = True
controller_thread = None

# --- Controller State ---
controller_lock = threading.Lock()
is_controller_connected = False
is_calibrated = False
connection_status_text = "Searching for controller..."
orientation_quaternion = list(DEFAULT_HOME_ORIENTATION)
log_message = ""
home_position = {
    "name": "Home",
    "orientation": list(DEFAULT_HOME_ORIENTATION)
}

# --- Motion Data & Controls ---
gyro_rotation = [0.0, 0.0, 0.0]
accel_data = [0.0, 0.0, 0.0]
raw_gyro = [0.0, 0.0, 0.0]
raw_accel = [0.0, 0.0, 0.0]
controller_tip_position = [0.0, 0.0, 0.0]

recenter_event = threading.Event()
go_to_home_event = threading.Event()
home_button_map = 'a'
home_button_event = threading.Event()
is_mapping_home_button = False

# --- Reference Points & Groups ---
reference_points = []
reference_point_groups = {}
triggered_groups = set()
group_grace_period = 2.0

hit_tolerance = 0.15
distance_offset = 0.5
show_ref_point_labels = True

# --- Filter Settings ---
# UPDATED: Default beta gain
beta_gain = 0.1
drift_correction_gain = 0.05
accelerometer_smoothing = 0.5
correct_drift_when_still_enabled = True

# --- Dimensions ---
object_dimensions = [1.6, 0.8, 0.4]

# --- Camera Controls ---
camera_orbit_x = -165.0
camera_orbit_y = 0.0
camera_zoom = -6.0
camera_roll = 0.0

# --- Thread-safe settings bridge ---
debug_mode_enabled = False
debug_axis_to_test = 0
pause_sensor_updates_enabled = False
verbose_logging_enabled = False
log_to_console_enabled = False
play_action_sound = True
action_sound_path = None # ADDED: Path to custom WAV file

# --- Tkinter Variables (for GUI only) ---
dimension_w_var, dimension_h_var, dimension_d_var = None, None, None
gyro_x_var, gyro_y_var, gyro_z_var = None, None, None
accel_x_var, accel_y_var, accel_z_var = None, None, None
camera_orbit_x_var, camera_orbit_y_var, camera_zoom_var, camera_roll_var = None, None, None, None
pause_sensor_updates_var = None
home_button_map_var = None
mapping_status_var = None
show_visualization_var = None
debug_mode_var = None
debug_axis_var = None
raw_gyro_var = None
raw_accel_var = None
verbose_logging_var = None
beta_gain_var = None
drift_correction_gain_var = None
ref_x_var, ref_y_var, ref_z_var = None, None, None
hit_tolerance_var = None
distance_offset_var = None
show_ref_point_labels_var = None
edit_id_var, edit_x_var, edit_y_var, edit_z_var = None, None, None, None
log_message_var = None
accelerometer_smoothing_var = None
log_to_console_var = None
correct_drift_when_still_var = None
home_name_var, home_q_w_var, home_q_x_var, home_q_y_var, home_q_z_var = None, None, None, None, None
edit_point_group_var = None
group_action_type_var = None
group_action_detail_var = None
group_name_var = None
play_action_sound_var = None
group_grace_period_var = None
save_filename_var = None