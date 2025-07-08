# In main_app.py
import os
import sys
import threading
import tkinter as tk
import uuid
from tkinter import ttk, messagebox, filedialog
from action_executor import ActionExecutor
import numpy as np
from OpenGL import GLUT
import time
import global_state
from config_manager import save_config, load_config, log_error
from sdl_controller import poll_controller_data
from visualization import VisFrame
from madgwick_ahrs import MadgwickAHRS, quaternion_to_euler


def quaternion_multiply(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
    return np.array([w, x, y, z])


def quaternion_inverse(q):
    w, x, y, z = q
    return np.array([w, -x, -y, -z])


def rotate_point_by_quaternion(point, q):
    q_point = np.array([0, point[0], point[1], point[2]])
    q_conj = quaternion_inverse(q)
    q_rotated = quaternion_multiply(quaternion_multiply(q, q_point), q_conj)
    return q_rotated[1:]


def euler_to_quaternion(pitch, yaw, roll):
    """
    Converts Euler angles (in degrees) to a quaternion.
    Assumes a ZYX rotation order, which matches the OpenGL glRotatef sequence.
    """
    pitch_rad = np.deg2rad(pitch)  # X
    yaw_rad = np.deg2rad(yaw)  # Y
    roll_rad = np.deg2rad(roll)  # Z

    cy = np.cos(yaw_rad * 0.5)
    sy = np.sin(yaw_rad * 0.5)
    cp = np.cos(pitch_rad * 0.5)
    sp = np.sin(pitch_rad * 0.5)
    cr = np.cos(roll_rad * 0.5)
    sr = np.sin(roll_rad * 0.5)

    w = cy * cp * cr + sy * sp * sr
    x = cy * sp * cr - sy * cp * sr
    y = sy * cp * cr + cy * sp * sr
    z = cy * cp * sr - sy * sp * cr

    return np.array([w, x, y, z])


class CollapsibleFrame(ttk.Frame):
    def __init__(self, parent, text="", collapsed=True, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.columnconfigure(0, weight=1)
        self._collapsed = tk.BooleanVar(value=collapsed)
        self.title_frame = ttk.Frame(self)
        self.title_frame.grid(row=0, column=0, sticky="ew")
        s = ttk.Style();
        s.configure("Bold.TLabel", font=("TkDefaultFont", 10, "bold"))
        self.toggle_button = ttk.Label(self.title_frame, text="▶" if collapsed else "▼")
        self.toggle_button.pack(side="left")
        self.title_label = ttk.Label(self.title_frame, text=text, style="Bold.TLabel")
        self.title_label.pack(side="left", fill="x", expand=True)
        self.content_frame = ttk.Frame(self)
        self.toggle_button.bind("<Button-1>", self.toggle);
        self.title_label.bind("<Button-1>", self.toggle)
        if not collapsed:
            self.content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(2, 5))
            self.toggle_button.config(text="▼")

    def toggle(self, event=None):
        if self._collapsed.get():
            self.content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(2, 5));
            self.toggle_button.config(text="▼");
            self._collapsed.set(False)
        else:
            self.content_frame.grid_forget();
            self.toggle_button.config(text="▶");
            self._collapsed.set(True)

        self.master.update_idletasks()
        self.master.event_generate("<Configure>")

    def is_collapsed(self):
        return self._collapsed.get()


def update_home_position_ui():
    """Helper to sync the home position data to the UI with 2-decimal formatting."""
    home_pos = global_state.home_position
    if home_pos:
        global_state.home_name_var.set(home_pos.get('name', 'Home'))
        q = home_pos.get('orientation', [1.0, 0.0, 0.0, 0.0])
        global_state.home_q_w_var.set(f"{q[0]:.2f}")
        global_state.home_q_x_var.set(f"{q[1]:.2f}")
        global_state.home_q_y_var.set(f"{q[2]:.2f}")
        global_state.home_q_z_var.set(f"{q[3]:.2f}")
    else:
        for var in [global_state.home_name_var, global_state.home_q_w_var, global_state.home_q_x_var,
                    global_state.home_q_y_var, global_state.home_q_z_var]:
            if var: var.set("")


def sync_settings_to_global_state():
    if not global_state.running: return
    with global_state.controller_lock:
        try:
            global_state.log_to_console_enabled = global_state.log_to_console_var.get()
            global_state.play_action_sound = global_state.play_action_sound_var.get()
            global_state.group_grace_period = global_state.group_grace_period_var.get()
            global_state.beta_gain = global_state.beta_gain_var.get()
            global_state.drift_correction_gain = global_state.drift_correction_gain_var.get()
            global_state.correct_drift_when_still_enabled = global_state.correct_drift_when_still_var.get()
            global_state.accelerometer_smoothing = global_state.accelerometer_smoothing_var.get()
            global_state.pause_sensor_updates_enabled = global_state.pause_sensor_updates_var.get()
            global_state.hit_tolerance = global_state.hit_tolerance_var.get()
            global_state.distance_offset = global_state.distance_offset_var.get()
            global_state.track_pitch = global_state.track_pitch_var.get()
            global_state.track_yaw = global_state.track_yaw_var.get()
            global_state.track_roll = global_state.track_roll_var.get()
            global_state.action_interval = global_state.action_interval_var.get() / 1000.0
            global_state.stockpile_mode_enabled = global_state.stockpile_mode_var.get()
            global_state.action_count_file_path = global_state.action_count_file_path_var.get()
            new_total_actions = global_state.total_actions_completed_var.get()
            if new_total_actions != global_state.total_actions_completed:
                global_state.total_actions_completed = new_total_actions
                write_action_count_to_file()

            global_state.log_tip_position_enabled = global_state.log_tip_position_var.get()
            global_state.console_log_interval = global_state.console_log_interval_var.get()

            global_state.lock_pitch_to = global_state.lock_pitch_to_var.get()
            global_state.lock_yaw_to = global_state.lock_yaw_to_var.get()
            global_state.lock_roll_to = global_state.lock_roll_to_var.get()
            global_state.axis_lock_strength = global_state.axis_lock_strength_var.get()

        except (AttributeError, tk.TclError, ValueError):
            pass


def update_camera_settings(*args):
    try:
        with global_state.controller_lock:
            global_state.camera_orbit_x = global_state.camera_orbit_x_var.get()
            global_state.camera_orbit_y = global_state.camera_orbit_y_var.get()
            global_state.camera_zoom = global_state.camera_zoom_var.get()
            global_state.camera_roll = global_state.camera_roll_var.get()
    except (ValueError, tk.TclError):
        pass


def update_object_dimensions(*args):
    with global_state.controller_lock:
        try:
            w = global_state.dimension_w_var.get()
            h = global_state.dimension_h_var.get()
            d = global_state.dimension_d_var.get()
            global_state.object_dimensions = [w, h, d]
        except (ValueError, tk.TclError):
            pass


def toggle_point_labels():
    with global_state.controller_lock:
        global_state.show_ref_point_labels = global_state.show_ref_point_labels_var.get()


def load_config_and_update_gui(root, ref_tree, group_tree, collapsible_frames, filepath=None, initial_load=False):
    if load_config(root, ref_tree, group_tree, collapsible_frames, filepath, initial_load):
        update_camera_settings()
        update_object_dimensions()
        update_home_position_ui()
        if not initial_load:
            zero_orientation()


def load_action_sound():
    def open_dialog():
        root.update_idletasks()
        try:
            filepath = filedialog.askopenfilename(
                parent=root,
                title="Load Action Sound",
                filetypes=[("Audio Files", "*.wav *.mp3"), ("All Files", "*.*")]
            )
            if filepath and os.path.exists(filepath):
                global_state.action_sound_path = filepath
                print(f"Action sound set to: {filepath}")
        except Exception as e:
            messagebox.showerror("Load Sound Error", f"Could not open file dialog or load sound.\n\nError: {e}")

    root.after_idle(open_dialog)


def zero_orientation():
    with global_state.controller_lock:
        if global_state.home_position:
            global_state.go_to_home_event.set()
            print("Resetting to saved home position.")
        else:
            global_state.recenter_event.set()
            print("Resetting to default zero orientation.")


def start_mapping(target_button):
    with global_state.controller_lock:
        if global_state.mapping_target == target_button:
            global_state.mapping_target = None
        else:
            global_state.mapping_target = target_button
    update_mapping_ui()


def update_mapping_ui():
    with global_state.controller_lock:
        current_target = global_state.mapping_target
        home_status = "Listening..." if current_target == 'home' else f"({global_state.home_button_map})"
        if global_state.mapping_home_status_var:
            global_state.mapping_home_status_var.set(home_status)
        stockpile_status = "Listening..." if current_target == 'stockpile' else f"({global_state.execute_stockpiled_action_button or 'None'})"
        if global_state.mapping_stockpile_status_var:
            global_state.mapping_stockpile_status_var.set(stockpile_status)


def toggle_visualization(root, vis_container, controls_container):
    if global_state.show_visualization_var.get():
        vis_container.pack(side="left", fill="both", expand=True)
        try:
            root.minsize(*root.previous_minsize);
            root.geometry(root.previous_geometry)
        except AttributeError:
            root.minsize(800, 600);
            root.geometry("650x750")
    else:
        if not hasattr(root, 'previous_geometry'):
            root.previous_geometry = root.geometry();
            root.previous_minsize = root.minsize()
        vis_container.pack_forget()
        controls_width = 380
        window_height = root.winfo_height()
        if window_height < 100: window_height = 750
        new_width = controls_width + 40
        root.minsize(new_width, 0);
        root.geometry(f"{new_width}x{window_height}")


def _on_mousewheel(event, canvas):
    """Cross-platform mouse wheel event handler."""
    if sys.platform.startswith('linux'):
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
    else:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


def bind_mousewheel_recursively(widget, canvas):
    """Binds the mousewheel event to a widget and all of its children."""
    widget.bind('<MouseWheel>', lambda e: _on_mousewheel(e, canvas))
    for child in widget.winfo_children():
        bind_mousewheel_recursively(child, canvas)


def on_closing():
    global_state.running = False
    if global_state.controller_thread and global_state.controller_thread.is_alive():
        print("Joining controller thread...")
        global_state.controller_thread.join(timeout=2)
    print("Closing application window.")
    root.destroy()


def add_reference_point(tree, position=None):
    with global_state.controller_lock:
        if position is None:
            position = global_state.controller_tip_position
        point_id = str(uuid.uuid4().hex[:6])
        new_point = {'id': point_id, 'position': list(position), 'hit': False, 'is_active': True, 'chain_parent': None}
        global_state.reference_points.append(new_point)
        tree.insert('', 'end', iid=point_id,
                    values=(point_id, f"{position[0]:.2f}", f"{position[1]:.2f}", f"{position[2]:.2f}"))
    refresh_edit_dropdowns(ref_tree, group_combo, chain_combo)


def add_manual_reference_point(tree):
    try:
        x = float(global_state.ref_x_var.get());
        y = float(global_state.ref_y_var.get());
        z = float(global_state.ref_z_var.get())
        add_reference_point(tree, position=[x, y, z])
    except ValueError:
        messagebox.showerror("Invalid Input", "Please enter valid numbers for X, Y, and Z.")


def delete_reference_point(tree):
    selected_items = tree.selection()
    if not selected_items:
        messagebox.showinfo("No Selection", "Please select a point to delete.")
        return

    with global_state.controller_lock:
        for item_id in selected_items:
            global_state.reference_points = [p for p in global_state.reference_points if p['id'] != item_id]
            for p in global_state.reference_points:
                if p.get('chain_parent') == item_id:
                    p['chain_parent'] = None
            if item_id in global_state.point_hit_history:
                del global_state.point_hit_history[item_id]
            for group_id, group_data in global_state.reference_point_groups.items():
                if item_id in group_data.get('point_ids', set()):
                    group_data['point_ids'].remove(item_id)
            tree.delete(item_id)
    print(f"Deleted point(s): {', '.join(selected_items)}")
    refresh_edit_dropdowns(ref_tree, group_combo, chain_combo)


def refresh_edit_dropdowns(point_tree, group_combo, chain_combo):
    """Refreshes the values in the group and chain dropdowns based on current state."""
    selected_iid = point_tree.selection()

    with global_state.controller_lock:
        group_names = ['None'] + [g['name'] for g in global_state.reference_point_groups.values()]
        group_ids = ['None'] + list(global_state.reference_point_groups.keys())
        group_combo.name_to_id_map = dict(zip(group_names, group_ids))
        group_combo['values'] = group_names

        point_ids_for_chain = ['None']
        if selected_iid:
            point_ids_for_chain.extend([p['id'] for p in global_state.reference_points if p['id'] != selected_iid[0]])
        else:
            point_ids_for_chain.extend([p['id'] for p in global_state.reference_points])

        chain_combo['values'] = point_ids_for_chain

    if selected_iid:
        with global_state.controller_lock:
            point = next((p for p in global_state.reference_points if p['id'] == selected_iid[0]), None)
            if point:
                current_group_name = 'None'
                for group_id, group_data in global_state.reference_point_groups.items():
                    if selected_iid[0] in group_data.get('point_ids', set()):
                        current_group_name = group_data.get('name', 'Unnamed Group')
                        break
                global_state.edit_point_group_var.set(current_group_name)
                chain_parent_id = point.get('chain_parent')
                global_state.edit_point_chain_var.set(chain_parent_id if chain_parent_id else 'None')


def on_point_select(event, tree, edit_frame, group_combo, chain_combo):
    """Handles populating the edit form when a point is selected."""
    selected_iid = tree.selection()

    if not selected_iid:
        for child in edit_frame.winfo_children():
            child.configure(state='disabled')
        global_state.edit_point_group_var.set('None')
        global_state.edit_point_chain_var.set('None')
        return

    selected_iid = selected_iid[0]
    with global_state.controller_lock:
        point = next((p for p in global_state.reference_points if p['id'] == selected_iid), None)
        if point:
            global_state.edit_id_var.set(point['id'])
            global_state.edit_x_var.set(f"{point['position'][0]:.2f}")
            global_state.edit_y_var.set(f"{point['position'][1]:.2f}")
            global_state.edit_z_var.set(f"{point['position'][2]:.2f}")
            for child in edit_frame.winfo_children():
                child.configure(state='normal')

    refresh_edit_dropdowns(tree, group_combo, chain_combo)


def create_group(tree):
    with global_state.controller_lock:
        base_name = "New Group"
        new_name = base_name
        counter = 2
        existing_names = {g['name'] for g in global_state.reference_point_groups.values()}
        while new_name in existing_names:
            new_name = f"{base_name} ({counter})"
            counter += 1

        group_id = f"group_{uuid.uuid4().hex[:6]}"
        new_group = {"name": new_name, "point_ids": set(), "hit_timestamps": {},
                     "action": {"type": "Key Press", "detail": ""}}
        global_state.reference_point_groups[group_id] = new_group

    tree.insert('', 'end', iid=group_id, values=(new_group['name'],))
    tree.selection_set(group_id)
    refresh_edit_dropdowns(ref_tree, group_combo, chain_combo)


def delete_group(tree):
    selected_id = tree.selection()
    if not selected_id:
        messagebox.showinfo("No Selection", "Please select a group to delete.");
        return
    selected_id = selected_id[0]

    if messagebox.askyesno("Confirm Delete",
                           f"Are you sure you want to delete group '{global_state.reference_point_groups[selected_id]['name']}'?"):
        with global_state.controller_lock:
            del global_state.reference_point_groups[selected_id]
        tree.delete(selected_id)
    refresh_edit_dropdowns(ref_tree, group_combo, chain_combo)


def on_group_select(event, tree, details_frame, member_list_tree):
    member_list_tree.delete(*member_list_tree.get_children())
    selected_id = tree.selection()

    def set_child_widgets_state(parent, state):
        for child in parent.winfo_children():
            if isinstance(child, (ttk.LabelFrame, ttk.Frame)): set_child_widgets_state(child, state)
            try:
                child.configure(state=state)
            except tk.TclError:
                pass

    if not selected_id:
        set_child_widgets_state(details_frame, 'disabled');
        return

    selected_id = selected_id[0]
    set_child_widgets_state(details_frame, 'normal')

    with global_state.controller_lock:
        group_data = global_state.reference_point_groups.get(selected_id)
        if group_data:
            action = group_data.get('action', {})
            global_state.group_name_var.set(group_data.get('name', ''))
            global_state.group_action_type_var.set(action.get('type', 'Key Press'))
            global_state.group_action_detail_var.set(action.get('detail', ''))
            for point_id in group_data.get('point_ids', set()):
                point = next((p for p in global_state.reference_points if p['id'] == point_id), None)
                if point: member_list_tree.insert('', 'end', iid=f"member_{point_id}", values=(point_id,))


def update_group_details(tree):
    selected_id = tree.selection()
    if not selected_id: messagebox.showinfo("No Selection", "Please select a group to update."); return
    selected_id = selected_id[0]

    with global_state.controller_lock:
        group_data = global_state.reference_point_groups.get(selected_id)
        if group_data:
            group_data['name'] = global_state.group_name_var.get()
            group_data['action'] = {'type': global_state.group_action_type_var.get(),
                                    'detail': global_state.group_action_detail_var.get()}
            tree.item(selected_id, values=(group_data['name'],))
            print(f"Updated group {selected_id}")


def update_selected_point(tree, edit_frame, group_combo):
    selected_iid = tree.selection()
    if not selected_iid: messagebox.showinfo("No Selection", "Please select a point to edit."); return
    original_iid = selected_iid[0]

    try:
        new_id = global_state.edit_id_var.get()
        new_x = float(global_state.edit_x_var.get())
        new_y = float(global_state.edit_y_var.get())
        new_z = float(global_state.edit_z_var.get())
        new_chain_parent = global_state.edit_point_chain_var.get()
        if new_chain_parent == 'None': new_chain_parent = None

        new_values = (new_id, f"{new_x:.2f}", f"{new_y:.2f}", f"{new_z:.2f}")

        with global_state.controller_lock:
            for g_id, g_data in list(global_state.reference_point_groups.items()):
                if original_iid in g_data.get('point_ids', set()):
                    g_data['point_ids'].remove(original_iid)

            group_name = group_combo.get()
            group_id = group_combo.name_to_id_map.get(group_name)

            if group_id and group_id != 'None':
                if group_id in global_state.reference_point_groups:
                    global_state.reference_point_groups[group_id]['point_ids'].add(new_id)
                    print(f"Assigned point {new_id} to group '{group_name}'")

            point_to_update = next((p for p in global_state.reference_points if p['id'] == original_iid), None)
            if point_to_update:
                point_to_update['id'] = new_id
                point_to_update['position'] = [new_x, new_y, new_z]
                point_to_update['chain_parent'] = new_chain_parent

        if original_iid != new_id:
            index = tree.index(original_iid)
            tree.delete(original_iid)
            tree.insert('', index, iid=new_id, values=new_values)
        else:
            tree.item(original_iid, values=new_values)

        tree.selection_remove(tree.selection())
        for child in edit_frame.winfo_children(): child.configure(state='disabled')

    except (ValueError, TypeError) as e:
        messagebox.showerror("Invalid Input", f"Please enter valid data for all fields.\n{e}")


def set_home_position():
    with global_state.controller_lock:
        global_state.home_position = {'name': 'Home', 'orientation': list(global_state.orientation_quaternion)}
    update_home_position_ui()
    print("Home position set.")


def set_home_and_update_points(ref_tree):
    with global_state.controller_lock:
        if not global_state.home_position or 'orientation' not in global_state.home_position:
            messagebox.showinfo("No Home Set", "Please set a home position first.");
            return

        q_old = np.array(global_state.home_position['orientation'])
        q_new = np.array(global_state.orientation_quaternion)
        q_old_inv = quaternion_inverse(q_old)
        q_delta = quaternion_multiply(q_new, q_old_inv)

        for point in global_state.reference_points:
            p_old = np.array(point['position'])
            p_new = rotate_point_by_quaternion(p_old, q_delta)
            point['position'] = list(p_new)
            point_id = point['id']
            new_values = (point_id, f"{p_new[0]:.2f}", f"{p_new[1]:.2f}", f"{p_new[2]:.2f}")
            if ref_tree.exists(point_id): ref_tree.item(point_id, values=new_values)

        d_pitch, d_yaw, d_roll = quaternion_to_euler(q_delta)
        global_state.camera_orbit_x -= d_pitch
        global_state.camera_orbit_y -= d_yaw
        global_state.camera_roll -= d_roll

        try:
            global_state.camera_orbit_x_var.set(global_state.camera_orbit_x)
            global_state.camera_orbit_y_var.set(global_state.camera_orbit_y)
            global_state.camera_roll_var.set(global_state.camera_roll)
        except tk.TclError:
            pass

        global_state.home_position = {'name': global_state.home_position.get('name', 'Home'),
                                      'orientation': list(q_new)}

    update_home_position_ui()
    print("Home position updated, all reference points and camera transformed.")


def go_to_home():
    if not global_state.home_position: messagebox.showinfo("No Home Set", "Please set a home position first."); return
    global_state.go_to_home_event.set()


def update_home_from_ui():
    if not global_state.home_position: messagebox.showinfo("No Home Set", "Please set a home position first."); return
    try:
        new_q = [float(global_state.home_q_w_var.get()), float(global_state.home_q_x_var.get()),
                 float(global_state.home_q_y_var.get()), float(global_state.home_q_z_var.get())]
        new_q_norm = np.linalg.norm(new_q)
        if new_q_norm == 0: messagebox.showerror("Invalid Input", "Quaternion cannot be all zeros."); return
        new_q = new_q / new_q_norm
        with global_state.controller_lock:
            global_state.home_position['name'] = global_state.home_name_var.get()
            global_state.home_position['orientation'] = list(new_q)
        update_home_position_ui()
        print("Home position updated.")
    except (ValueError, tk.TclError):
        messagebox.showerror("Invalid Input", "Please enter valid numbers for all quaternion fields.")


def delete_home_position():
    if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the home position?"):
        with global_state.controller_lock: global_state.home_position = {}
        update_home_position_ui()
        print("Home position deleted.")


def write_action_count_to_file():
    if global_state.action_count_file_path:
        try:
            with open(global_state.action_count_file_path, 'w') as f:
                f.write(str(global_state.total_actions_completed))
        except Exception as e:
            print(f"Error writing to action count file: {e}");
            log_error(e)


def reset_action_count():
    if messagebox.askyesno("Confirm Reset", "Are you sure you want to reset the total action count to 0?"):
        with global_state.controller_lock:
            global_state.total_actions_completed = 0
            global_state.total_actions_completed_var.set(0)
            write_action_count_to_file()
        print("Total action count has been reset.")


def browse_for_action_count_file():
    def open_dialog():
        root.update_idletasks()
        try:
            filepath = filedialog.asksaveasfilename(parent=root, title="Select File for Action Count",
                                                    filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                                                    defaultextension=".txt")
            if filepath:
                global_state.action_count_file_path_var.set(filepath)
                with global_state.controller_lock:
                    global_state.action_count_file_path = filepath
                    write_action_count_to_file()
        except tk.TclError as e:
            messagebox.showerror("File Dialog Error",
                                 f"Could not open the file dialog.\nThis can sometimes be a temporary issue.\nPlease try again.\n\nError: {e}")
        except Exception as e:
            log_error(e)
            messagebox.showerror("File Save Error",
                                 f"An unexpected error occurred while saving the file.\nSee error.log for details.")

    root.after_idle(open_dialog)


def handle_action_completion(group_data, action_executor):
    with global_state.controller_lock:
        global_state.total_actions_completed += 1
        global_state.session_actions_completed += 1
        if global_state.total_actions_completed_var: global_state.total_actions_completed_var.set(
            global_state.total_actions_completed)
        if global_state.actions_completed_this_session_var: global_state.actions_completed_this_session_var.set(
            global_state.session_actions_completed)
        write_action_count_to_file()

        if global_state.stockpile_mode_enabled:
            global_state.stockpiled_actions.append(group_data['action'])
            if global_state.stockpiled_actions_count_var: global_state.stockpiled_actions_count_var.set(
                f"({len(global_state.stockpiled_actions)})")
            print(f"Action stockpiled. Total stockpiled: {len(global_state.stockpiled_actions)}")
        else:
            action_executor.execute(group_data['action'])


if __name__ == "__main__":
    GLUT.glutInit(sys.argv)
    root = tk.Tk()
    root.title("PyDualM2K")
    root.geometry("650x750")
    root.minsize(800, 600)

    # --- Initialize Global State Tkinter Variables ---
    global_state.show_visualization_var = tk.BooleanVar(value=True)
    global_state.pause_sensor_updates_var = tk.BooleanVar(value=False)
    global_state.show_ref_point_labels_var = tk.BooleanVar(value=True)
    global_state.play_action_sound_var = tk.BooleanVar(value=True)
    global_state.save_filename_var = tk.StringVar(value="config.json")
    global_state.load_filename_var = tk.StringVar()
    global_state.ref_x_var, global_state.ref_y_var, global_state.ref_z_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    global_state.edit_id_var, global_state.edit_x_var, global_state.edit_y_var, global_state.edit_z_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
    global_state.dimension_w_var, global_state.dimension_h_var, global_state.dimension_d_var = tk.DoubleVar(
        value=global_state.object_dimensions[0]), tk.DoubleVar(value=global_state.object_dimensions[1]), tk.DoubleVar(
        value=global_state.object_dimensions[2])
    global_state.camera_orbit_x_var, global_state.camera_orbit_y_var, global_state.camera_zoom_var, global_state.camera_roll_var = tk.DoubleVar(
        value=global_state.camera_orbit_x), tk.DoubleVar(value=global_state.camera_orbit_y), tk.DoubleVar(
        value=global_state.camera_zoom), tk.DoubleVar(value=global_state.camera_roll)
    global_state.beta_gain_var, global_state.hit_tolerance_var, global_state.distance_offset_var = tk.DoubleVar(
        value=global_state.beta_gain), tk.DoubleVar(value=global_state.hit_tolerance), tk.DoubleVar(
        value=global_state.distance_offset)
    global_state.drift_correction_gain_var = tk.DoubleVar(value=global_state.drift_correction_gain)
    global_state.group_grace_period_var = tk.DoubleVar(value=global_state.group_grace_period)
    global_state.log_to_console_var = tk.BooleanVar(value=False)
    global_state.correct_drift_when_still_var = tk.BooleanVar(value=global_state.correct_drift_when_still_enabled)
    global_state.accelerometer_smoothing_var = tk.DoubleVar(value=global_state.accelerometer_smoothing)
    global_state.home_name_var, global_state.home_q_w_var, global_state.home_q_x_var, global_state.home_q_y_var, global_state.home_q_z_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
    global_state.group_name_var, global_state.group_action_type_var, global_state.group_action_detail_var = tk.StringVar(), tk.StringVar(
        value="Key Press"), tk.StringVar()
    global_state.edit_point_group_var, global_state.edit_point_chain_var = tk.StringVar(), tk.StringVar()
    global_state.track_pitch_var, global_state.track_yaw_var, global_state.track_roll_var = tk.BooleanVar(
        value=True), tk.BooleanVar(value=True), tk.BooleanVar(value=True)
    global_state.action_interval_var = tk.DoubleVar(value=1000.0)
    global_state.total_actions_completed_var = tk.IntVar(value=0)
    global_state.actions_completed_this_session_var = tk.IntVar(value=0)
    global_state.action_count_file_path_var = tk.StringVar(value="")
    global_state.stockpile_mode_var = tk.BooleanVar(value=False)
    global_state.stockpiled_actions_count_var = tk.StringVar(value="(0)")
    global_state.mapping_home_status_var = tk.StringVar()
    global_state.mapping_stockpile_status_var = tk.StringVar()
    global_state.log_tip_position_var = tk.BooleanVar(value=False)
    global_state.console_log_interval_var = tk.DoubleVar(value=15.0)
    global_state.lock_pitch_to_var = tk.DoubleVar(value=0.0)
    global_state.lock_yaw_to_var = tk.DoubleVar(value=0.0)
    global_state.lock_roll_to_var = tk.DoubleVar(value=0.0)
    global_state.axis_lock_strength_var = tk.DoubleVar(value=0.1)
    global_state.unintended_movement_status_var = tk.StringVar(value="")

    main_frame = ttk.Frame(root);
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    controls_container = ttk.Frame(main_frame, width=380);
    controls_container.pack(side="right", fill="y", padx=(10, 0));
    controls_container.pack_propagate(False)
    canvas = tk.Canvas(controls_container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(controls_container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    scrollable_frame_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")


    def fit_frame_to_canvas(event):
        canvas_width = event.width
        canvas.itemconfig(scrollable_frame_window, width=canvas_width)


    canvas.bind("<Configure>", fit_frame_to_canvas)

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True);
    scrollbar.pack(side="right", fill="y")

    vis_container = ttk.Frame(main_frame);
    vis_container.pack(side="left", fill="both", expand=True)
    vis_frame = VisFrame(vis_container);
    vis_frame.pack(fill="both", expand=True)


    def create_slider_entry(parent, text, double_var, fr, to, r, digits=2, cmd=None):
        ttk.Label(parent, text=text).grid(row=r, column=0, sticky='w', padx=5, pady=2)

        string_var = tk.StringVar()

        def _update_string_from_double(*args):
            if hasattr(double_var, '_trace_lock'): return
            try:
                string_var.set(f"{double_var.get():.{digits}f}")
            except (tk.TclError, ValueError):
                pass

        def _update_double_from_string(*args):
            if hasattr(string_var, '_trace_lock'): return
            try:
                val = float(string_var.get())
                if double_var.get() != val:
                    setattr(double_var, '_trace_lock', True)
                    double_var.set(val)
                    delattr(double_var, '_trace_lock')
            except (ValueError, tk.TclError):
                setattr(string_var, '_trace_lock', True)
                _update_string_from_double()
                delattr(string_var, '_trace_lock')

        double_var.trace_add('write', _update_string_from_double)
        string_var.trace_add('write', _update_double_from_string)

        _update_string_from_double()

        def on_scale_move(value_str):
            val = float(value_str)
            double_var.set(val)
            if cmd:
                cmd(val)

        s = ttk.Scale(parent, from_=fr, to=to, orient="horizontal", variable=double_var, command=on_scale_move)
        s.grid(row=r, column=1, sticky='ew', padx=(5, 0))

        e = ttk.Entry(parent, width=8, textvariable=string_var)
        e.grid(row=r, column=2, padx=(5, 5))

        parent.columnconfigure(1, weight=1)


    collapsible_frames = {}
    view_cf = CollapsibleFrame(scrollable_frame, "View Options", True);
    view_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['view'] = view_cf
    controller_cf = CollapsibleFrame(scrollable_frame, "Controller Actions", False);
    controller_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['controller'] = controller_cf
    stats_cf = CollapsibleFrame(scrollable_frame, "Stats & Stockpile", False);
    stats_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['stats'] = stats_cf
    group_cf = CollapsibleFrame(scrollable_frame, "Point Groups & Actions", True);
    group_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['groups'] = group_cf
    ref_points_cf = CollapsibleFrame(scrollable_frame, "Reference Points", True);
    ref_points_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['ref_points'] = ref_points_cf
    edit_cf = CollapsibleFrame(scrollable_frame, "Edit Selected Point", True);
    edit_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['edit'] = edit_cf
    ref_settings_cf = CollapsibleFrame(scrollable_frame, "Reference Point Settings", True);
    ref_settings_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['ref_settings'] = ref_settings_cf
    filter_cf = CollapsibleFrame(scrollable_frame, "Filter Settings", True);
    filter_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['filter'] = filter_cf
    camera_cf = CollapsibleFrame(scrollable_frame, "Camera Controls", True);
    camera_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['camera'] = camera_cf
    dim_cf = CollapsibleFrame(scrollable_frame, "Object Dimensions", True);
    dim_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['dim'] = dim_cf
    debug_cf = CollapsibleFrame(scrollable_frame, "Debug Tools", True);
    debug_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['debug'] = debug_cf
    config_cf = CollapsibleFrame(scrollable_frame, "Configuration", True);
    config_cf.pack(fill='x', expand=True, padx=5, pady=5);
    collapsible_frames['config'] = config_cf

    ttk.Checkbutton(view_cf.content_frame, text="Show Visualization", variable=global_state.show_visualization_var,
                    command=lambda: toggle_visualization(root, vis_container, controls_container)).pack(anchor='w',
                                                                                                        padx=5)
    ttk.Checkbutton(view_cf.content_frame, text="Pause Sensor Updates",
                    variable=global_state.pause_sensor_updates_var).pack(anchor='w', padx=5)

    controller_actions_frame = ttk.Frame(controller_cf.content_frame)
    controller_actions_frame.pack(fill='x', padx=5, pady=2)
    go_home_btn = ttk.Button(controller_actions_frame, text="Go to Home Position", command=go_to_home)
    go_home_btn.pack(side='left', expand=True, fill='x', padx=(0, 5))
    map_home_btn = ttk.Button(controller_actions_frame, text="Map Home", command=lambda: start_mapping('home'))
    map_home_btn.pack(side='left')
    ttk.Label(controller_actions_frame, textvariable=global_state.mapping_home_status_var, foreground="blue").pack(
        side='left', padx=5)

    ttk.Separator(controller_cf.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

    home_frame = ttk.Frame(controller_cf.content_frame);
    home_frame.pack(fill='x', expand=True)
    home_buttons_frame = ttk.Frame(home_frame);
    home_buttons_frame.pack(fill='x')
    ttk.Button(home_buttons_frame, text="Set Home Here", command=set_home_position).pack(side='left', fill='x',
                                                                                         expand=True, padx=5, pady=2)
    ttk.Button(home_buttons_frame, text="Set & Update Points",
               command=lambda: set_home_and_update_points(ref_tree)).pack(side='left', fill='x', expand=True, padx=5,
                                                                          pady=2)
    home_details_frame = ttk.LabelFrame(home_frame, text="Home Position Details");
    home_details_frame.pack(fill='x', padx=5, pady=5)
    ttk.Label(home_details_frame, text="Name:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
    ttk.Entry(home_details_frame, textvariable=global_state.home_name_var).grid(row=0, column=1, columnspan=4,
                                                                                sticky='ew', padx=5, pady=2)
    for i, (label, var) in enumerate(
            [("W:", global_state.home_q_w_var), ("X:", global_state.home_q_x_var), ("Y:", global_state.home_q_y_var),
             ("Z:", global_state.home_q_z_var)]):
        ttk.Label(home_details_frame, text=label).grid(row=1, column=i, sticky='w', padx=(5, 0))
        ttk.Entry(home_details_frame, textvariable=var, width=8).grid(row=2, column=i, sticky='w', padx=5)
    home_edit_buttons_frame = ttk.Frame(home_frame);
    home_edit_buttons_frame.pack(fill='x')
    ttk.Button(home_edit_buttons_frame, text="Update From Fields", command=update_home_from_ui).pack(side='left',
                                                                                                     fill='x',
                                                                                                     expand=True,
                                                                                                     padx=5, pady=2)
    ttk.Button(home_edit_buttons_frame, text="Delete Home", command=delete_home_position).pack(side='left', fill='x',
                                                                                               expand=True, padx=5,
                                                                                               pady=2)

    stats_content = stats_cf.content_frame
    stockpile_lf = ttk.LabelFrame(stats_content, text="Stockpile Settings");
    stockpile_lf.pack(fill='x', padx=5, pady=5);
    stockpile_lf.columnconfigure(1, weight=1)
    ttk.Checkbutton(stockpile_lf, text="Enable Stockpile Mode", variable=global_state.stockpile_mode_var).grid(row=0,
                                                                                                               column=0,
                                                                                                               columnspan=2,
                                                                                                               sticky='w',
                                                                                                               padx=5)
    stockpile_map_frame = ttk.Frame(stockpile_lf);
    stockpile_map_frame.grid(row=1, column=0, columnspan=3, sticky='ew')
    ttk.Button(stockpile_map_frame, text="Map Execute Button", command=lambda: start_mapping('stockpile')).pack(
        side='left', padx=5, pady=2)
    ttk.Label(stockpile_map_frame, textvariable=global_state.mapping_stockpile_status_var, foreground="blue").pack(
        side='left', padx=5)

    stats_lf = ttk.LabelFrame(stats_content, text="Action Counter");
    stats_lf.pack(fill='x', padx=5, pady=5);
    stats_lf.columnconfigure(1, weight=1)
    ttk.Label(stats_lf, text="Actions This Session:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
    ttk.Entry(stats_lf, textvariable=global_state.actions_completed_this_session_var, width=10, state='readonly').grid(
        row=0, column=1, sticky='w', padx=5)
    ttk.Label(stats_lf, text="Total Actions Completed:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
    ttk.Entry(stats_lf, textvariable=global_state.total_actions_completed_var, width=10).grid(row=1, column=1,
                                                                                              sticky='w', padx=5)
    ttk.Button(stats_lf, text="Reset Total", command=reset_action_count).grid(row=1, column=2, sticky='e', padx=5)
    ttk.Label(stats_lf, text="Counter File Path (for OBS):").grid(row=2, column=0, columnspan=3, sticky='w', padx=5,
                                                                  pady=(5, 0))
    count_file_frame = ttk.Frame(stats_lf);
    count_file_frame.grid(row=3, column=0, columnspan=3, sticky='ew');
    count_file_frame.columnconfigure(0, weight=1)
    ttk.Entry(count_file_frame, textvariable=global_state.action_count_file_path_var).grid(row=0, column=0, sticky='ew',
                                                                                           padx=5)
    ttk.Button(count_file_frame, text="Browse...", command=browse_for_action_count_file).grid(row=0, column=1, padx=5)

    group_list_frame = ttk.Frame(group_cf.content_frame);
    group_list_frame.pack(fill='x', expand=True, padx=5, pady=5)
    group_tree = ttk.Treeview(group_list_frame, columns=('Name',), show='headings', height=4);
    group_tree.pack(side='left', fill='x', expand=True)
    group_tree.heading('Name', text='Group Name');
    group_tree.column('Name', anchor='w')
    group_buttons_frame = ttk.Frame(group_list_frame);
    group_buttons_frame.pack(side='left', fill='y', padx=(5, 0))
    ttk.Button(group_buttons_frame, text="New", command=lambda: create_group(group_tree)).pack()
    ttk.Button(group_buttons_frame, text="Delete", command=lambda: delete_group(group_tree)).pack()
    group_details_frame = ttk.LabelFrame(group_cf.content_frame, text="Selected Group Details");
    group_details_frame.pack(fill='x', padx=5, pady=5)
    create_slider_entry(group_details_frame, "Grace Period (s):", global_state.group_grace_period_var, 0.0, 10.0, 0,
                        digits=2)
    create_slider_entry(group_details_frame, "Action Cooldown (ms):", global_state.action_interval_var, 5.0, 3000.0, 1,
                        digits=0)
    ttk.Label(group_details_frame, text="Name:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
    ttk.Entry(group_details_frame, textvariable=global_state.group_name_var).grid(row=2, column=1, sticky='ew', padx=5,
                                                                                  pady=2)
    ttk.Label(group_details_frame, text="Action Type:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
    action_type_combo = ttk.Combobox(group_details_frame, textvariable=global_state.group_action_type_var,
                                     values=["Key Press", "Mouse Click"], state="readonly");
    action_type_combo.grid(row=3, column=1, sticky='ew', padx=5, pady=2)
    ttk.Label(group_details_frame, text="Action Detail:").grid(row=4, column=0, sticky='w', padx=5, pady=2)
    ttk.Entry(group_details_frame, textvariable=global_state.group_action_detail_var).grid(row=4, column=1, sticky='ew',
                                                                                           padx=5, pady=2)
    ttk.Button(group_details_frame, text="Update Group Details", command=lambda: update_group_details(group_tree)).grid(
        row=5, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
    member_frame = ttk.LabelFrame(group_details_frame, text="Points in Group");
    member_frame.grid(row=6, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
    member_list_tree = ttk.Treeview(member_frame, columns=('ID',), show='headings', height=3);
    member_list_tree.pack(side='left', fill='x', expand=True)
    member_list_tree.heading('ID', text='Point ID');
    member_list_tree.column('ID', anchor='w')
    group_details_frame.columnconfigure(1, weight=1)
    group_tree.bind('<<TreeviewSelect>>',
                    lambda e: on_group_select(e, group_tree, group_details_frame, member_list_tree))

    ref_content = ref_points_cf.content_frame
    ttk.Button(ref_content, text="Record Current Tip Position", command=lambda: add_reference_point(ref_tree)).pack(
        fill='x', padx=5, pady=2)
    manual_frame = ttk.Frame(ref_content);
    manual_frame.pack(fill='x', padx=5, pady=5)
    for i, (label, var) in enumerate(
            [("X:", global_state.ref_x_var), ("Y:", global_state.ref_y_var), ("Z:", global_state.ref_z_var)]):
        ttk.Label(manual_frame, text=label).pack(side='left')
        ttk.Entry(manual_frame, width=5, textvariable=var).pack(side='left')
    ttk.Button(manual_frame, text="Add", command=lambda: add_manual_reference_point(ref_tree)).pack(side='left',
                                                                                                    padx=(5, 0))
    tree_frame = ttk.Frame(ref_content);
    tree_frame.pack(fill='x', expand=True, padx=5, pady=5)
    ref_tree = ttk.Treeview(tree_frame, columns=('ID', 'X', 'Y', 'Z'), show='headings', height=4);
    ref_tree.pack(side='left', fill='x', expand=True)
    for col, w in [('ID', 50), ('X', 70), ('Y', 70), ('Z', 70)]: ref_tree.heading(col, text=col); ref_tree.column(col,
                                                                                                                  width=w,
                                                                                                                  anchor='center')
    ttk.Button(ref_content, text="Delete Selected", command=lambda: delete_reference_point(ref_tree)).pack(fill='x',
                                                                                                           padx=5,
                                                                                                           pady=2)

    edit_content = edit_cf.content_frame
    for i, (label, var) in enumerate(
            [("ID:", global_state.edit_id_var), ("X:", global_state.edit_x_var), ("Y:", global_state.edit_y_var),
             ("Z:", global_state.edit_z_var)]):
        ttk.Label(edit_content, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(edit_content, textvariable=var, state='disabled').grid(row=i, column=1, sticky='ew', padx=5, pady=2)
    ttk.Label(edit_content, text="Assign to Group:").grid(row=4, column=0, sticky='w', padx=5, pady=2)
    group_combo = ttk.Combobox(edit_content, textvariable=global_state.edit_point_group_var, values=['None'],
                               state='readonly');
    group_combo.grid(row=4, column=1, sticky='ew', padx=5, pady=2)
    ttk.Label(edit_content, text="Chain After Point:").grid(row=5, column=0, sticky='w', padx=5, pady=2)
    chain_combo = ttk.Combobox(edit_content, textvariable=global_state.edit_point_chain_var, values=['None'],
                               state='readonly');
    chain_combo.grid(row=5, column=1, sticky='ew', padx=5, pady=2)
    ttk.Button(edit_content, text="Update Point",
               command=lambda: update_selected_point(ref_tree, edit_content, group_combo), state='disabled').grid(row=6,
                                                                                                                  columnspan=2,
                                                                                                                  sticky='ew',
                                                                                                                  padx=5,
                                                                                                                  pady=5)
    ref_tree.bind('<<TreeviewSelect>>', lambda e: on_point_select(e, ref_tree, edit_content, group_combo, chain_combo))

    create_slider_entry(ref_settings_cf.content_frame, "Hit Tolerance:", global_state.hit_tolerance_var, 0.01, 1.0, 0,
                        digits=2)
    create_slider_entry(ref_settings_cf.content_frame, "Distance Offset:", global_state.distance_offset_var, 0.0, 2.0,
                        1, digits=2)
    ttk.Checkbutton(ref_settings_cf.content_frame, text="Show Point Labels",
                    variable=global_state.show_ref_point_labels_var, command=toggle_point_labels).grid(row=2,
                                                                                                       columnspan=3,
                                                                                                       sticky='w',
                                                                                                       padx=5)

    create_slider_entry(filter_cf.content_frame, "Filter Beta Gain:", global_state.beta_gain_var, 0.01, 1.0, 0,
                        digits=2)
    create_slider_entry(filter_cf.content_frame, "Drift Correction (Zeta):", global_state.drift_correction_gain_var,
                        0.0, 0.5, 1, digits=2)
    create_slider_entry(filter_cf.content_frame, "Accel Smoothing:", global_state.accelerometer_smoothing_var, 0.01,
                        1.0, 2, digits=2)
    ttk.Checkbutton(filter_cf.content_frame, text="Drift-Correct Only When Still",
                    variable=global_state.correct_drift_when_still_var).grid(row=3, columnspan=3, sticky='w', padx=5)

    create_slider_entry(camera_cf.content_frame, "Orbit X (Pitch):", global_state.camera_orbit_x_var, -180, 180, 0,
                        digits=2, cmd=update_camera_settings)
    create_slider_entry(camera_cf.content_frame, "Orbit Y (Yaw):", global_state.camera_orbit_y_var, -180, 180, 1,
                        digits=2, cmd=update_camera_settings)
    create_slider_entry(camera_cf.content_frame, "Orbit Z (Roll):", global_state.camera_roll_var, -180, 180, 2,
                        digits=2, cmd=update_camera_settings)
    create_slider_entry(camera_cf.content_frame, "Zoom:", global_state.camera_zoom_var, -20, -1, 3, digits=2,
                        cmd=update_camera_settings)

    create_slider_entry(dim_cf.content_frame, "Width:", global_state.dimension_w_var, 0.1, 5.0, 0, digits=2,
                        cmd=update_object_dimensions)
    create_slider_entry(dim_cf.content_frame, "Height:", global_state.dimension_h_var, 0.1, 5.0, 1, digits=2,
                        cmd=update_object_dimensions)
    create_slider_entry(dim_cf.content_frame, "Depth:", global_state.dimension_d_var, 0.1, 5.0, 2, digits=2,
                        cmd=update_object_dimensions)

    debug_content = debug_cf.content_frame
    ttk.Checkbutton(debug_content, text="Play Sound on Action", variable=global_state.play_action_sound_var).pack(
        anchor='w', padx=5)
    ttk.Separator(debug_content, orient='horizontal').pack(fill='x', pady=5, padx=5)

    axis_track_frame = ttk.Frame(debug_content)
    axis_track_frame.pack(fill='x', padx=5, pady=2)
    ttk.Checkbutton(axis_track_frame, text="Track Pitch", variable=global_state.track_pitch_var).pack(side='left',
                                                                                                      expand=True,
                                                                                                      padx=2)
    ttk.Checkbutton(axis_track_frame, text="Track Yaw", variable=global_state.track_yaw_var).pack(side='left',
                                                                                                  expand=True, padx=2)
    ttk.Checkbutton(axis_track_frame, text="Track Roll", variable=global_state.track_roll_var).pack(side='left',
                                                                                                    expand=True, padx=2)

    lock_pos_frame = ttk.LabelFrame(debug_content, text="Lock-to Positions (°)")
    lock_pos_frame.pack(fill='x', padx=5, pady=5)
    for i, (text, var) in enumerate([("Pitch:", global_state.lock_pitch_to_var), ("Yaw:", global_state.lock_yaw_to_var),
                                     ("Roll:", global_state.lock_roll_to_var)]):
        ttk.Label(lock_pos_frame, text=text).grid(row=0, column=i * 2, padx=(5, 2), pady=2)
        ttk.Entry(lock_pos_frame, textvariable=var, width=6).grid(row=0, column=i * 2 + 1, padx=(0, 10), pady=2)

    create_slider_entry(lock_pos_frame, "Lock Strength:", global_state.axis_lock_strength_var, 0.01, 1.0, r=1, digits=2)
    lock_pos_frame.grid_columnconfigure(1, weight=1)

    ttk.Label(lock_pos_frame, textvariable=global_state.unintended_movement_status_var, foreground="red").grid(row=2,
                                                                                                               column=0,
                                                                                                               columnspan=6,
                                                                                                               sticky='w',
                                                                                                               padx=5,
                                                                                                               pady=2)

    log_frame = ttk.LabelFrame(debug_content, text="Console Logging")
    log_frame.pack(fill='x', padx=5, pady=5)
    log_frame.columnconfigure(1, weight=1)
    ttk.Checkbutton(log_frame, text="Log Controller Position", variable=global_state.log_to_console_var).grid(row=0,
                                                                                                              column=0,
                                                                                                              columnspan=3,
                                                                                                              sticky='w',
                                                                                                              padx=5)
    ttk.Checkbutton(log_frame, text="Log Tip Position", variable=global_state.log_tip_position_var).grid(row=1,
                                                                                                         column=0,
                                                                                                         columnspan=3,
                                                                                                         sticky='w',
                                                                                                         padx=5)
    create_slider_entry(log_frame, "Log Interval (ms):", global_state.console_log_interval_var, 5, 1000, 2, digits=0)

    config_content = config_cf.content_frame
    save_frame = ttk.LabelFrame(config_content, text="Save Configuration");
    save_frame.pack(fill='x', padx=5, pady=5)
    ttk.Label(save_frame, text="Filename:").pack(side='left', padx=(5, 2))
    ttk.Entry(save_frame, textvariable=global_state.save_filename_var).pack(side='left', fill='x', expand=True, padx=2)
    ttk.Button(save_frame, text="Save", width=8,
               command=lambda: save_config(root, collapsible_frames, global_state.save_filename_var.get())).pack(
        side='left', padx=(2, 5))
    load_frame = ttk.LabelFrame(config_content, text="Load Configuration");
    load_frame.pack(fill='x', padx=5, pady=5)


    def refresh_load_list():
        try:
            json_files = [f for f in os.listdir('.') if f.endswith('.json')]
        except FileNotFoundError:
            json_files = []
        load_combo['values'] = json_files
        if json_files and not global_state.load_filename_var.get(): global_state.load_filename_var.set(json_files[0])


    ttk.Label(load_frame, text="Load File:").pack(side='left', padx=(5, 2))
    load_combo = ttk.Combobox(load_frame, textvariable=global_state.load_filename_var, state='readonly');
    load_combo.pack(side='left', fill='x', expand=True, padx=2)
    refresh_button = ttk.Button(load_frame, text="🔄", width=3, command=refresh_load_list);
    refresh_button.pack(side='left', padx=2)
    ttk.Button(load_frame, text="Load", width=8,
               command=lambda: load_config_and_update_gui(root, ref_tree, group_tree, collapsible_frames,
                                                          filepath=global_state.load_filename_var.get())).pack(
        side='left', padx=(2, 5))
    refresh_load_list()
    ttk.Button(config_content, text="Load Action Sound (.wav, .mp3)",
               command=lambda: root.after_idle(load_action_sound)).pack(fill='x', padx=5, pady=(10, 5))

    status_label = ttk.Label(root, textvariable=global_state.connection_status_text, anchor='w')
    status_label.pack(side="bottom", fill="x", padx=10, pady=2)

    action_executor = ActionExecutor()
    global_state.controller_thread = threading.Thread(target=poll_controller_data, daemon=True)
    global_state.controller_thread.start()


    def update_gui():
        if not global_state.running: return
        sync_settings_to_global_state()
        update_mapping_ui()

        if global_state.home_button_event.is_set():
            zero_orientation();
            global_state.home_button_event.clear()

        if global_state.execute_stockpiled_event.is_set():
            with global_state.controller_lock:
                if global_state.stockpiled_actions:
                    action_to_execute = global_state.stockpiled_actions.pop(0)
                    action_executor.execute(action_to_execute)
                    if global_state.stockpiled_actions_count_var: global_state.stockpiled_actions_count_var.set(
                        f"({len(global_state.stockpiled_actions)})")
            global_state.execute_stockpiled_event.clear()

        triggered_groups_to_process = []

        with global_state.controller_lock:
            if global_state.unintended_movement_detected:
                global_state.unintended_movement_status_var.set("WARNING: Locked axis moved!")
            else:
                global_state.unintended_movement_status_var.set("")

            now = time.monotonic()
            if (now - global_state.last_console_log_time) * 1000 >= global_state.console_log_interval:
                if global_state.log_to_console_enabled or global_state.log_tip_position_enabled:
                    global_state.last_console_log_time = now

                    log_msg = ""
                    if global_state.log_to_console_enabled:
                        p, y, r = global_state.gyro_rotation
                        log_msg += f"Controller -> Pitch: {p:>6.2f}, Yaw: {y:>6.2f}, Roll: {r:>6.2f}"

                    if global_state.log_tip_position_enabled:
                        tx, ty, tz = global_state.controller_tip_position
                        if log_msg: log_msg += " | "
                        log_msg += f"Tip -> X: {tx:>6.2f}, Y: {ty:>6.2f}, Z: {tz:>6.2f}"

                    if log_msg:
                        print(log_msg)

            # --- START: HIT DETECTION LOGIC ---
            current_time = time.monotonic()
            grace_period = global_state.group_grace_period

            # Expire old hits from the global history
            expired_ids = [pid for pid, hit_time in global_state.point_hit_history.items() if
                           current_time - hit_time > grace_period]
            if expired_ids:
                for pid in expired_ids:
                    if pid in global_state.point_hit_history:
                        del global_state.point_hit_history[pid]

            # Register new hits
            newly_hit_points = set()
            for point in global_state.reference_points:
                parent_id = point.get('chain_parent')
                point['is_active'] = not parent_id or parent_id in global_state.point_hit_history

                is_within_distance = np.linalg.norm(
                    global_state.controller_tip_position - np.array(point['position'])) < global_state.hit_tolerance

                point['hit'] = point['is_active'] and is_within_distance

                if point['hit']:
                    if point['id'] not in global_state.point_hit_history:
                        newly_hit_points.add(point['id'])
                        global_state.point_hit_history[point['id']] = current_time
                        print(f"DEBUG: New hit for point '{point['id']}' at time {current_time:.2f}")

            points_to_clear_from_history = set()
            # Check for group completion only if there was a new hit
            if newly_hit_points:
                all_point_ids_in_world = {p['id'] for p in global_state.reference_points}

                for group_id, group_data in global_state.reference_point_groups.items():
                    required_points_from_config = group_data.get('point_ids', set())

                    # Filter for points that actually exist in the world
                    valid_required_points = required_points_from_config.intersection(all_point_ids_in_world)

                    if not valid_required_points or not newly_hit_points.intersection(valid_required_points):
                        continue

                    group_name = group_data.get('name', 'Unnamed')
                    hit_history_keys = set(global_state.point_hit_history.keys())

                    if valid_required_points.issubset(hit_history_keys):
                        hit_times = [global_state.point_hit_history[pid] for pid in valid_required_points]
                        if not hit_times: continue

                        time_span = max(hit_times) - min(hit_times)
                        is_within_grace = time_span <= grace_period

                        print(f"\n--- Group Check: '{group_name}' ---")
                        print(f"  Required (from config): {required_points_from_config}")
                        print(f"  Required (and valid):   {valid_required_points}")
                        print(f"  Current Hit History:    {hit_history_keys}")
                        print(
                            f"  Time Span of hits: {time_span:.2f}s <= Grace Period: {grace_period:.2f}s? -> {is_within_grace}")

                        if is_within_grace:
                            cooldown = global_state.action_interval
                            last_triggered = global_state.group_last_triggered.get(group_id, 0)
                            time_since_last_trigger = current_time - last_triggered
                            has_cooldown_passed = time_since_last_trigger > cooldown

                            print(
                                f"  Cooldown check: {cooldown:.2f}s < Time Since Last: {time_since_last_trigger:.2f}s? -> {has_cooldown_passed}")

                            if has_cooldown_passed:
                                print(f"  >>> SUCCESS: Group '{group_name}' queued for action!")
                                triggered_groups_to_process.append(group_data.copy())
                                global_state.group_last_triggered[group_id] = current_time
                                points_to_clear_from_history.update(valid_required_points)

            # After checking all groups, clear the points from all triggered groups
            if points_to_clear_from_history:
                print(f"DEBUG: Clearing triggered points from history: {points_to_clear_from_history}")
                for pid in points_to_clear_from_history:
                    if pid in global_state.point_hit_history:
                        del global_state.point_hit_history[pid]
            # --- END: HIT DETECTION LOGIC ---

        # Process queued actions outside of the main controller lock to prevent deadlocks
        if triggered_groups_to_process:
            for group_data in triggered_groups_to_process:
                handle_action_completion(group_data, action_executor)

        if global_state.show_visualization_var.get():
            vis_frame.redraw()

        root.after(16, update_gui)


    root.protocol("WM_DELETE_WINDOW", on_closing)
    load_config_and_update_gui(root, ref_tree, group_tree, collapsible_frames,
                               filepath=os.path.join(os.getcwd(), "config.json"), initial_load=True)
    root.update_idletasks()

    bind_mousewheel_recursively(scrollable_frame, canvas)
    canvas.bind('<MouseWheel>', lambda e: _on_mousewheel(e, canvas))

    toggle_visualization(root, vis_container, controls_container)
    update_mapping_ui()
    root.after(2500, zero_orientation)
    root.after(150, update_gui)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nCtrl+C detected, shutting down.")
        on_closing()
