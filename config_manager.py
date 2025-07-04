import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import traceback
import global_state


def log_error(exc):
    """Logs exceptions to a file for easier debugging."""
    with open("error.log", "a") as f:
        f.write(f"--- {traceback.format_exc()} ---\n")
    print(f"An error occurred. Details have been logged to error.log")


def save_config(root, collapsible_frames, filepath=None):
    """Saves the current application state to the specified filepath."""
    if not filepath:
        messagebox.showerror("Save Error", "No filename provided.")
        return

    if not filepath.lower().endswith('.json'):
        filepath += '.json'

    config_data = {
        'ui_settings': {}, 'reference_points': [], 'frame_states': {},
        'home_position': {}, 'reference_point_groups': {}, 'action_sound_path': None
    }

    with global_state.controller_lock:
        # FIX: Explicitly cast the 'hit' value to a standard bool for JSON serialization.
        points_to_save = []
        for p in global_state.reference_points:
            point_copy = p.copy()
            point_copy['hit'] = bool(p['hit'])
            points_to_save.append(point_copy)
        config_data['reference_points'] = points_to_save

        config_data['home_position'] = global_state.home_position
        config_data['reference_point_groups'] = {
            gid: {**gdata, 'point_ids': list(gdata.get('point_ids', []))}
            for gid, gdata in global_state.reference_point_groups.items()
        }
        config_data['action_sound_path'] = global_state.action_sound_path

    for key, var in vars(global_state).items():
        if isinstance(var, (tk.BooleanVar, tk.DoubleVar, tk.StringVar)) and key.endswith('_var'):
            try:
                value = var.get()
                if isinstance(var, tk.BooleanVar):
                    config_data['ui_settings'][key] = bool(value)
                else:
                    config_data['ui_settings'][key] = value
            except (tk.TclError, AttributeError):
                pass

    for name, frame in collapsible_frames.items():
        config_data['frame_states'][name] = frame.is_collapsed()

    try:
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=4)
        messagebox.showinfo("Save Success", f"Configuration saved to {filepath}")
        print(f"Configuration saved to {filepath}")
    except Exception as e:
        log_error(e)
        messagebox.showerror("Save Error", f"Failed to save configuration file. See error.log for details.")


def load_config(root, ref_tree, group_tree, collapsible_frames, filepath=None, initial_load=False):
    """Loads application state from the specified filepath."""
    if not filepath or not os.path.exists(filepath):
        if not initial_load:
            messagebox.showwarning("Load Warning", f"File not found: {filepath}")
        return False

    try:
        with open(filepath, 'r') as f:
            config_data = json.load(f)
    except Exception as e:
        log_error(e)
        if not initial_load:
            messagebox.showerror("Load Error",
                                 f"Failed to load or parse configuration file. See error.log for details.")
        return False

    with global_state.controller_lock:
        global_state.reference_points = config_data.get('reference_points', [])
        global_state.home_position = config_data.get('home_position', {})
        global_state.action_sound_path = config_data.get('action_sound_path', None)
        loaded_groups = config_data.get('reference_point_groups', {})
        global_state.reference_point_groups = {}
        for gid, gdata in loaded_groups.items():
            gdata['point_ids'] = set(gdata.get('point_ids', []))
            gdata['hit_timestamps'] = {}
            global_state.reference_point_groups[gid] = gdata

    ref_tree.delete(*ref_tree.get_children())
    for point in global_state.reference_points:
        values = (
            point.get('id', ''), f"{point.get('position', [0, 0, 0])[0]:.2f}",
            f"{point.get('position', [0, 0, 0])[1]:.2f}",
            f"{point.get('position', [0, 0, 0])[2]:.2f}")
        ref_tree.insert('', 'end', iid=point.get('id'), values=values)

    group_tree.delete(*group_tree.get_children())
    for group_id, group_data in global_state.reference_point_groups.items():
        group_tree.insert('', 'end', iid=group_id, values=(group_data.get('name', 'Unnamed Group'),))

    update_home_position_ui()

    ui_settings = config_data.get('ui_settings', {})
    for key, value in ui_settings.items():
        if hasattr(global_state, key):
            try:
                if not key.startswith('home_q_') and key != 'home_name_var':
                    getattr(global_state, key).set(value)
            except (tk.TclError, AttributeError):
                pass

    frame_states = config_data.get('frame_states', {})
    for name, frame in collapsible_frames.items():
        is_collapsed_in_config = frame_states.get(name, True)
        if is_collapsed_in_config != frame.is_collapsed():
            frame.toggle()

    print(f"Configuration loaded from {filepath}")
    return True


def update_home_position_ui():
    """Helper to sync the home position data to the UI."""
    home_pos = global_state.home_position
    if home_pos:
        global_state.home_name_var.set(home_pos.get('name', 'Home'))
        q = home_pos.get('orientation', [1.0, 0.0, 0.0, 0.0])
        global_state.home_q_w_var.set(f"{q[0]:.3f}")
        global_state.home_q_x_var.set(f"{q[1]:.3f}")
        global_state.home_q_y_var.set(f"{q[2]:.3f}")
        global_state.home_q_z_var.set(f"{q[3]:.3f}")
    else:
        for var in [global_state.home_name_var, global_state.home_q_w_var, global_state.home_q_x_var,
                    global_state.home_q_y_var, global_state.home_q_z_var]:
            if var: var.set("")