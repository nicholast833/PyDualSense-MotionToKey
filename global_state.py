# In global_state.py

import threading
import tkinter as tk

# --- Constants ---
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
home_button_event = threading.Event()

mapping_target = None
home_button_map = 'b'
execute_stockpiled_action_button = ''


# --- Stats and Stockpiling ---
total_actions_completed = 0
session_actions_completed = 0
action_count_file_path = ""
stockpile_mode_enabled = False
stockpiled_actions = []
execute_stockpiled_event = threading.Event()


# --- Reference Points & Groups ---
reference_points = []
reference_point_groups = {}
point_hit_history = {}
last_hit_details = {} # MODIFIED: Added missing variable
triggered_groups = set()
previously_completed_groups = set()
group_grace_period = 2.0

hit_tolerance = 0.15
distance_offset = 0.5
show_ref_point_labels = True

# --- Filter Settings ---
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
pause_sensor_updates_enabled = False
log_to_console_enabled = False
play_action_sound = True
action_sound_path = None
track_pitch = True
track_yaw = True
track_roll = True
last_good_pitch = 0.0
last_good_yaw = 0.0
last_good_roll = 0.0
action_interval = 1.0
group_last_triggered = {}
log_tip_position_enabled = False
console_log_interval = 15.0 # ms
last_console_log_time = 0.0

# MODIFIED - Axis locking and debug state
lock_pitch_to = 0.0
lock_yaw_to = 0.0
lock_roll_to = 0.0
axis_lock_strength = 0.1  # How quickly the orientation snaps to the locked position.
unintended_movement_detected = False


# --- Tkinter Variables (for GUI only) ---
dimension_w_var, dimension_h_var, dimension_d_var = None, None, None
camera_orbit_x_var, camera_orbit_y_var, camera_zoom_var, camera_roll_var = None, None, None, None
pause_sensor_updates_var = None
show_visualization_var = None
beta_gain_var = None
drift_correction_gain_var = None
ref_x_var, ref_y_var, ref_z_var = None, None, None
hit_tolerance_var = None
distance_offset_var = None
show_ref_point_labels_var = None
edit_id_var, edit_x_var, edit_y_var, edit_z_var = None, None, None, None
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
load_filename_var = None
track_pitch_var, track_yaw_var, track_roll_var = None, None, None
action_interval_var = None
edit_point_chain_var = None

total_actions_completed_var = None
actions_completed_this_session_var = None
action_count_file_path_var = None
stockpile_mode_var = None
stockpiled_actions_count_var = None
mapping_home_status_var = None
mapping_stockpile_status_var = None
log_tip_position_var = None
console_log_interval_var = None

# MODIFIED - Tkinter variables for axis locking
lock_pitch_to_var = None
lock_yaw_to_var = None
lock_roll_to_var = None
axis_lock_strength_var = None
unintended_movement_status_var = None