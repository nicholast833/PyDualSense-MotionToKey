import time
from collections import deque
import global_state
import tkinter.messagebox
import tkinter as tk
from models import SavedPosition, MotionSequence, MotionSequenceStep
from gui_elements import update_highlight_on_gui
from position_manager_gui import hide_edit_position_controls, update_saved_positions_display
from motion_sequence_manager_gui import update_motion_sequences_display
from config_manager import _read_reps_from_file

# pynput imports
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

# Initialize pynput controllers globally
keyboard_controller = KeyboardController()
mouse_controller = MouseController()

# Action Cooldown Constant (in milliseconds)
ACTION_COOLDOWN_MS = 500


# --- Helper Function ---
def apply_moving_average(axis_buffer, raw_value):
    axis_buffer.append(raw_value)
    return sum(axis_buffer) / len(axis_buffer) if axis_buffer else raw_value


# --- Gyro Re-level Function ---
def relevel_gyro():
    if global_state.ds and hasattr(global_state.ds, 'connected') and global_state.ds.connected:  # Guard with hasattr
        global_state.gyro_offset[0] = global_state.ds.state.gyro.Pitch
        global_state.gyro_offset[1] = global_state.ds.state.gyro.Yaw
        global_state.gyro_offset[2] = global_state.ds.state.gyro.Roll
        print(f"Gyroscope re-leveled. New offset: {global_state.gyro_offset}")
        global_state.connection_status_var.set("Gyroscope Re-leveled!")
        global_state.root.after(2000, lambda: global_state.connection_status_var.set("Controller Connected!"))
    else:
        print("Controller not connected to re-level gyroscope.")
        tkinter.messagebox.showwarning("Re-level Error", "Controller not connected.")


# --- Position Matching Logic ---
def find_matching_position_index(current_gyro, current_accel):
    for i, saved_pos in enumerate(global_state.saved_positions):
        min_g, max_g, min_a, max_a = saved_pos.get_effective_ranges()

        is_match = True

        if saved_pos.detection_axes['Pitch']:
            if not (min_g[0] <= current_gyro[0] <= max_g[0]): is_match = False
        if is_match and saved_pos.detection_axes['Yaw']:
            if not (min_g[1] <= current_gyro[1] <= max_g[1]): is_match = False
        if is_match and saved_pos.detection_axes['Roll']:
            if not (min_g[2] <= current_gyro[2] <= max_g[2]): is_match = False

        if is_match:  # Only proceed if gyro axes (if enabled) still match
            if saved_pos.detection_axes['X']:
                if not (min_a[0] <= current_accel[0] <= max_a[0]): is_match = False
            if is_match and saved_pos.detection_axes['Y']:
                if not (min_a[1] <= current_accel[1] <= max_a[1]): is_match = False
            if is_match and saved_pos.detection_axes['Z']:
                if not (min_a[2] <= current_accel[2] <= max_a[2]): is_match = False

        any_axis_enabled = any(saved_pos.detection_axes.values())
        if is_match and any_axis_enabled:
            return i  # Found a match

    return -1  # No match find


# --- Manual Reconnect Function (called from main_app.py) ---
def manual_reconnect():
    global_state.manual_reconnect_requested = True  # Set flag for read_controller_data loop
    print("Manual reconnect requested.")
    # The read_controller_data loop will pick up this flag and attempt reconnection.


# --- Helper for reading/writing reps from file ---
import os


def _read_reps_from_file(file_path):
    if not file_path or not os.path.exists(file_path):
        return 0
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            return int(content) if content.isdigit() else 0
    except Exception as e:
        print(f"Error reading rep count from file '{file_path}': {e}")
        return 0


def _write_reps_to_file(file_path, count):
    # Prevent writes during config load or if no path
    if global_state.is_initializing_config:
        return
    if not file_path:
        print("Warning: Repetition export requested but no file path set. Cannot write.")
        global_state.root.after(0, lambda: tkinter.messagebox.showwarning("File Export Warning",
                                                                          "Repetition export enabled but file path is missing or empty."))
        return
    try:
        with open(file_path, 'w') as f:  # Open in write mode to overwrite
            f.write(str(count))
    except Exception as e:
        error_msg = f"Error writing repetition count to file '{file_path}': {e}"
        print(error_msg)
        global_state.root.after(0, lambda: tkinter.messagebox.showerror("File Write Error", error_msg))


# --- Main Controller Data Reading Function (runs in a separate thread) ---
def read_controller_data():
    global_state.ds = global_state.pydualsense()

    is_initially_connected = False
    try:
        global_state.ds.init()
        if hasattr(global_state.ds, 'connected') and global_state.ds.connected:
            is_initially_connected = True
        else:
            global_state.connection_status_var.set("Controller Not Found!")
            global_state.last_read_timestamp = None
    except Exception as e:
        global_state.connection_status_var.set(f"Error Init: {e}")
        global_state.last_read_timestamp = None

    global_state.running = is_initially_connected or global_state.auto_reconnect_enabled_var.get()

    if not global_state.running and not global_state.auto_reconnect_enabled_var.get():
        global_state.connection_status_var.set("Controller Disconnected!")
        return

    with global_state.data_buffers_lock:
        for key in global_state.gyro_buffers:
            global_state.gyro_buffers[key] = deque(list(global_state.gyro_buffers[key]),
                                                   maxlen=global_state.smoothing_window_size)
        for key in global_state.accel_buffers:
            global_state.accel_buffers[key] = deque(list(global_state.accel_buffers[key]),
                                                    maxlen=global_state.smoothing_window_size)

    last_disconnect_attempt_time = 0

    try:
        while global_state.running:
            current_connection_status = hasattr(global_state.ds, 'connected') and global_state.ds.connected

            if current_connection_status:
                current_read_time = time.monotonic() * 1000
                if global_state.last_read_timestamp is not None:
                    latency = current_read_time - global_state.last_read_timestamp
                    global_state.root.after(0,
                                            lambda: global_state.input_delay_ms_var.set(f"Latency: {latency:.2f} ms"))
                global_state.last_read_timestamp = current_read_time

                raw_gyro_pitch = global_state.ds.state.gyro.Pitch
                raw_gyro_yaw = global_state.ds.state.gyro.Yaw
                raw_gyro_roll = global_state.ds.state.gyro.Roll
                raw_accel_x = global_state.ds.state.accelerometer.X
                raw_accel_y = global_state.ds.state.accelerometer.Y
                raw_accel_z = global_state.ds.state.accelerometer.Z

                adjusted_gyro_pitch = raw_gyro_pitch - global_state.gyro_offset[0]
                adjusted_gyro_yaw = raw_gyro_yaw - global_state.gyro_offset[1]
                adjusted_gyro_roll = raw_gyro_roll - global_state.gyro_offset[2]

                with global_state.data_buffers_lock:
                    smoothed_gyro_pitch = apply_moving_average(global_state.gyro_buffers['Pitch'], adjusted_gyro_pitch)
                    smoothed_gyro_yaw = apply_moving_average(global_state.gyro_buffers['Yaw'], adjusted_gyro_yaw)
                    smoothed_gyro_roll = apply_moving_average(global_state.gyro_buffers['Roll'], adjusted_gyro_roll)
                    smoothed_accel_x = apply_moving_average(global_state.accel_buffers['X'], raw_accel_x)
                    smoothed_accel_y = apply_moving_average(global_state.accel_buffers['Y'], raw_accel_y)
                    smoothed_accel_z = apply_moving_average(global_state.accel_buffers['Z'], raw_accel_z)

                current_gyro_smoothed = (smoothed_gyro_pitch, smoothed_gyro_yaw, smoothed_gyro_roll)
                current_accel_smoothed = (smoothed_accel_x, smoothed_accel_y, smoothed_accel_z)

                global_state.gyro_text_var.set(
                    f"Pitch: {current_gyro_smoothed[0]:.2f} \u00b0/s\nYaw:   {current_gyro_smoothed[1]:.2f} \u00b0/s\nRoll:  {current_gyro_smoothed[2]:.2f} \u00b0/s"
                )
                global_state.accel_text_var.set(
                    f"X: {current_accel_smoothed[0]:.2f} G\nY: {current_accel_smoothed[1]:.2f} G\nZ: {current_accel_smoothed[2]:.2f} G"
                )

                matched_index = find_matching_position_index(current_gyro_smoothed, current_accel_smoothed)
                if matched_index != global_state.current_highlighted_label_index:
                    global_state.current_highlighted_label_index = matched_index
                    global_state.root.after(0, lambda: update_highlight_on_gui(matched_index))

                for seq in global_state.saved_motion_sequences:
                    seq.is_completed_this_frame = False

                    if not seq.steps:
                        continue

                    if seq.current_position_index < len(seq.steps):
                        current_step = seq.steps[seq.current_position_index]
                        target_pos_for_seq = next(
                            (p for p in global_state.saved_positions if p.id == current_step.position_id), None)

                        if target_pos_for_seq is None:
                            seq.current_position_index = 0
                            seq.last_match_time = None
                            seq.non_match_start_time = None
                            continue

                        min_g, max_g, min_a, max_a = target_pos_for_seq.get_effective_ranges()
                        spatial_match = True

                        if target_pos_for_seq.detection_axes['Pitch']:
                            if not (min_g[0] <= current_gyro_smoothed[0] <= max_g[0]): spatial_match = False
                        if spatial_match and target_pos_for_seq.detection_axes['Yaw']:
                            if not (min_g[1] <= current_gyro_smoothed[1] <= max_g[1]): spatial_match = False
                        if spatial_match and target_pos_for_seq.detection_axes['Roll']:
                            if not (min_g[2] <= current_gyro_smoothed[2] <= max_g[2]): spatial_match = False
                        if spatial_match:
                            if target_pos_for_seq.detection_axes['X']:
                                if not (min_a[0] <= current_accel_smoothed[0] <= max_a[0]): spatial_match = False
                            if spatial_match and target_pos_for_seq.detection_axes['Y']:
                                if not (min_a[1] <= current_accel_smoothed[1] <= max_a[1]): spatial_match = False
                            if spatial_match and target_pos_for_seq.detection_axes['Z']:
                                if not (min_a[2] <= current_accel_smoothed[2] <= max_a[2]): spatial_match = False

                        is_spatial_match = spatial_match and any(target_pos_for_seq.detection_axes.values())
                        current_time = time.monotonic() * 1000

                        if is_spatial_match:
                            if seq.current_position_index == 0 or (
                                    current_time - seq.last_match_time <= seq.time_window_ms):
                                seq.last_match_time = current_time
                                seq.non_match_start_time = None

                                # *** Improved Debugging Log ***
                                print(
                                    f"DEBUG: Motion '{seq.name}' - Step {seq.current_position_index} ('{target_pos_for_seq.name}') matched. Advancing.")
                                seq.current_position_index += 1

                                if seq.current_position_index >= len(seq.steps):
                                    if not seq.is_completed_this_frame and (seq.last_action_trigger_time is None or (
                                            current_time - seq.last_action_trigger_time > ACTION_COOLDOWN_MS)):
                                        if seq.export_reps_to_file and seq.export_file_path:
                                            try:
                                                current_file_reps = _read_reps_from_file(seq.export_file_path)
                                                seq.repetition_count = current_file_reps + 1
                                                _write_reps_to_file(seq.export_file_path, seq.repetition_count)
                                            except Exception as file_sync_e:
                                                print(f"Error syncing rep count with file: {file_sync_e}")
                                        else:
                                            seq.repetition_count += 1

                                        if seq.action_binding:
                                            try:
                                                action_str = seq.action_binding.lower()
                                                if action_str == 'left_click':
                                                    mouse_controller.click(Button.left)
                                                elif action_str == 'right_click':
                                                    mouse_controller.click(Button.right)
                                                elif action_str == 'middle_click':
                                                    mouse_controller.click(Button.middle)
                                                elif hasattr(Key, action_str.upper()):
                                                    special_key = getattr(Key, action_str.upper())
                                                    keyboard_controller.press(special_key)
                                                    keyboard_controller.release(special_key)
                                                else:
                                                    keyboard_controller.press(action_str)
                                                    keyboard_controller.release(action_str)
                                                print(
                                                    f"Action '{seq.action_binding}' triggered for motion '{seq.name}'!")
                                                seq.last_action_trigger_time = current_time
                                            except Exception as action_e:
                                                print(f"Error triggering action '{seq.action_binding}': {action_e}")

                                        global_state.root.after(0, update_motion_sequences_display)
                                        print(f"Motion '{seq.name}' completed! Repetitions: {seq.repetition_count}")

                                    seq.current_position_index = 0
                                    seq.last_match_time = None
                                    seq.is_completed_this_frame = True
                            else:
                                # *** Improved Debugging Log ***
                                print(
                                    f"DEBUG: Motion '{seq.name}' - Timed out waiting for step {seq.current_position_index}. Resetting.")
                                seq.current_position_index = 0
                                seq.last_match_time = None
                                seq.non_match_start_time = None
                        else:
                            if seq.current_position_index > 0:
                                if seq.non_match_start_time is None:
                                    seq.non_match_start_time = current_time
                                elif (current_time - seq.non_match_start_time) > seq.reset_grace_period_ms:
                                    # *** Improved Debugging Log ***
                                    print(
                                        f"DEBUG: Motion '{seq.name}' - No match for step {seq.current_position_index} ('{target_pos_for_seq.name}'). Resetting due to grace period.")
                                    seq.current_position_index = 0
                                    seq.last_match_time = None
                                    seq.non_match_start_time = None
            else:  # Controller is disconnected
                # ... (rest of the file is unchanged)
                current_time_ms = time.monotonic() * 1000

                if global_state.ds and hasattr(global_state.ds, 'close'):
                    try:
                        global_state.ds.close()
                    except AttributeError as e:
                        print(f"Warning: Attempted to close a pydualsense object but it had no report_thread: {e}")
                    except Exception as e:
                        print(f"Error during pydualsense.close(): {e}")

                time_since_last_attempt = current_time_ms - last_disconnect_attempt_time
                should_attempt_reconnect = False

                if global_state.auto_reconnect_enabled_var.get():
                    if time_since_last_attempt > global_state.RECONNECT_DELAY_SECONDS * 1000:
                        should_attempt_reconnect = True
                        print("Auto-reconnect enabled: Attempting reconnect...")

                if global_state.manual_reconnect_requested:
                    should_attempt_reconnect = True
                    global_state.manual_reconnect_requested = False
                    print("Manual reconnect requested: Attempting reconnect...")

                if should_attempt_reconnect:
                    last_disconnect_attempt_time = current_time_ms
                    global_state.connection_status_var.set("Attempting reconnect...")

                    try:
                        global_state.ds.init()
                        if hasattr(global_state.ds, 'connected') and global_state.ds.connected:
                            global_state.connection_status_var.set("Controller Connected!")
                            global_state.last_read_timestamp = time.monotonic() * 1000
                            print("Reconnected!")
                            for seq in global_state.saved_motion_sequences:
                                seq.current_position_index = 0
                                seq.last_match_time = None
                                seq.non_match_start_time = None
                        else:
                            global_state.connection_status_var.set("Reconnect failed. Disconnected.")
                            print("Reconnect attempt failed.")
                            time.sleep(global_state.RECONNECT_DELAY_SECONDS)
                    except Exception as reconnect_e:
                        global_state.connection_status_var.set(f"Reconnect Error: {reconnect_e}")
                        print(f"Error during reconnect attempt: {reconnect_e}")
                        time.sleep(global_state.RECONNECT_DELAY_SECONDS)
                else:
                    if not global_state.auto_reconnect_enabled_var.get():
                        global_state.connection_status_var.set("Controller Disconnected!")
                        print("Controller disconnected. Stopping data read thread.")
                        global_state.running = False
                    time.sleep(0.5)

    except Exception as e:
        global_state.connection_status_var.set(f"Error Reading: {e}")
        print(f"An error occurred in controller data thread: {e}")
    finally:
        if global_state.ds and hasattr(global_state.ds, 'close'):
            try:
                global_state.ds.close()
                print("Controller connection closed.")
            except AttributeError as e:
                print(f"Warning: Controller object could not be fully closed (no report_thread) in finally block: {e}")
            except Exception as e:
                print(f"Error during pydualsense.close() in finally block: {e}")
        print("Controller data thread stopped.")


def record_position_points():
    global_state.is_recording = True
    recorded_data = []
    num_points = global_state.num_points_to_record_var.get()
    duration_ms = global_state.record_duration_ms_var.get()

    if num_points <= 0 or duration_ms <= 0:
        print("Invalid recording parameters.")
        global_state.root.after(0, lambda: [
            global_state.save_button.config(state=tk.NORMAL),
            global_state.connection_status_var.set(
                "Controller Connected!" if global_state.ds and global_state.ds.connected else "Controller Not Found!")
        ])
        global_state.is_recording = False
        return

    interval_s = (duration_ms / 1000.0) / (num_points - 1) if num_points > 1 else 0
    points_captured = 0
    start_time = time.monotonic()

    while points_captured < num_points and global_state.running and global_state.ds.connected:
        try:
            raw_gyro_pitch = global_state.ds.state.gyro.Pitch
            raw_gyro_yaw = global_state.ds.state.gyro.Yaw
            raw_gyro_roll = global_state.ds.state.gyro.Roll
            raw_accel_x = global_state.ds.state.accelerometer.X
            raw_accel_y = global_state.ds.state.accelerometer.Y
            raw_accel_z = global_state.ds.state.accelerometer.Z

            adjusted_gyro_pitch = raw_gyro_pitch - global_state.gyro_offset[0]
            adjusted_gyro_yaw = raw_gyro_yaw - global_state.gyro_offset[1]
            adjusted_gyro_roll = raw_gyro_roll - global_state.gyro_offset[2]

            with global_state.data_buffers_lock:
                current_gyro_smoothed = (
                    apply_moving_average(global_state.gyro_buffers['Pitch'], adjusted_gyro_pitch),
                    apply_moving_average(global_state.gyro_buffers['Yaw'], adjusted_gyro_yaw),
                    apply_moving_average(global_state.gyro_buffers['Roll'], adjusted_gyro_roll)
                )
                current_accel_smoothed = (
                    apply_moving_average(global_state.accel_buffers['X'], raw_accel_x),
                    apply_moving_average(global_state.accel_buffers['Y'], raw_accel_y),
                    apply_moving_average(global_state.accel_buffers['Z'], raw_accel_z)
                )
            recorded_data.append((current_gyro_smoothed, current_accel_smoothed))
            points_captured += 1
            if points_captured < num_points:
                elapsed_s = time.monotonic() - start_time
                target_elapsed_s = points_captured * interval_s
                sleep_needed = target_elapsed_s - elapsed_s
                if sleep_needed > 0:
                    time.sleep(sleep_needed)
        except Exception as e:
            print(f"Error capturing point {points_captured + 1}: {e}")
            break
    global_state.root.after(0, lambda: _finalize_recording(recorded_data))


def _finalize_recording(recorded_data):
    if recorded_data:
        position_name = f"Position {len(global_state.saved_positions) + 1}"
        default_detection_axes = {'Pitch': True, 'Yaw': True, 'Roll': True,
                                  'X': True, 'Y': True, 'Z': True}
        new_saved_pos = SavedPosition(recorded_data, position_name, global_state.initial_range_padding,
                                      detection_axes=default_detection_axes,
                                      custom_avg_gyro=None, custom_avg_accel=None)
        global_state.saved_positions.append(new_saved_pos)
        print(f"Saved: {new_saved_pos} with {len(recorded_data)} points. ID: {new_saved_pos.id}")
        global_state.current_highlighted_label_index = -1
        global_state.selected_position_index = -1
        global_state.root.after(0, hide_edit_position_controls)
        global_state.root.after(0, update_saved_positions_display)
    else:
        print("No data recorded for position.")

    global_state.root.after(0, lambda: [
        global_state.save_button.config(state=tk.NORMAL),
        global_state.connection_status_var.set(
            "Controller Connected!" if global_state.ds and global_state.ds.connected else "Controller Not Found!")
    ])
    global_state.is_recording = False