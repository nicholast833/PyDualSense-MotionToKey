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
from config_manager import save_config, load_config, update_home_position_ui
from sdl_controller import poll_controller_data
from visualization import VisFrame

def rotate_point_by_quaternion(point, q):
    q_point = np.array([0, point[0], point[1], point[2]])
    q_conj = np.array([q[0], -q[1], -q[2], -q[3]])
    q_rotated = quaternion_multiply(quaternion_multiply(q, q_point), q_conj)
    return q_rotated[1:]

def quaternion_multiply(q1, q2):
    w1, x1, y1, z1 = q1;
    w2, x2, y2, z2 = q2
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
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

    def is_collapsed(self):
        return self._collapsed.get()

def sync_settings_to_global_state():
    if not global_state.running: return
    with global_state.controller_lock:
        try:
            global_state.debug_mode_enabled = global_state.debug_mode_var.get()
            global_state.debug_axis_to_test = global_state.debug_axis_var.get()
            global_state.verbose_logging_enabled = global_state.verbose_logging_var.get()
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
        except (AttributeError, tk.TclError):
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
    print("DEBUG: load_config_and_update_gui called.")
    if load_config(root, ref_tree, group_tree, collapsible_frames, filepath, initial_load):
        print("DEBUG: load_config returned True. Applying post-load actions.")
        update_camera_settings()
        update_object_dimensions()
        # Only zero on manual load, not initial load
        if not initial_load:
            zero_orientation()

def load_action_sound():
    """Opens a file dialog to select an audio file for action notifications."""
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

def zero_orientation():
    """
    Called by the 'Zero Orientation' button or a mapped controller button.
    Prioritizes resetting to the saved home position if it exists,
    otherwise performs a standard zero reset.
    """
    with global_state.controller_lock:
        if global_state.home_position:  # Check if a home position is set
            global_state.go_to_home_event.set()
            print("Resetting to saved home position.")
        else:
            global_state.recenter_event.set()
            print("Resetting to default zero orientation.")

def start_button_mapping():
    with global_state.controller_lock:
        global_state.is_mapping_home_button = not global_state.is_mapping_home_button
        status = "Listening..." if global_state.is_mapping_home_button else ""
        global_state.mapping_status_var.set(status)

def toggle_visualization(root, vis_container, controls_container):
    if global_state.show_visualization_var.get():
        vis_container.pack(side="left", fill="both", expand=True)
        try:
            root.minsize(*root.previous_minsize);
            root.geometry(root.previous_geometry)
        except AttributeError:
            root.minsize(600, 600);
            root.geometry("600x750")
    else:
        if not hasattr(root, 'previous_geometry'):
            root.previous_geometry = root.geometry();
            root.previous_minsize = root.minsize()
        # vis_container.pack_forget() # FIX: This line causes the visualizer error
        controls_width = 320
        window_height = root.winfo_height()
        if window_height < 100: window_height = 750
        new_width = controls_width + 40
        root.minsize(new_width, 0);
        root.geometry(f"{new_width}x{window_height}")

def _on_mousewheel(event, canvas):
    direction = -1 if (event.num == 4 or event.delta > 0) else 1
    canvas.yview_scroll(direction, "units")

def on_closing():
    global_state.running = False
    if global_state.controller_thread and global_state.controller_thread.is_alive():
        print("Joining controller thread...")
        global_state.controller_thread.join(timeout=2)

    # The shutdown call is no longer needed for the simplified ActionExecutor
    # if 'action_executor' in locals() or 'action_executor' in globals():
    #     action_executor.shutdown()

    print("Closing application window.")
    root.destroy()

def add_reference_point(tree, position=None):
    with global_state.controller_lock:
        if position is None:
            # FIX: Use the live controller tip position directly
            position = global_state.controller_tip_position
        point_id = str(uuid.uuid4().hex[:6])
        new_point = {'id': point_id, 'position': list(position), 'hit': False}
        global_state.reference_points.append(new_point)
        tree.insert('', 'end', iid=point_id,
                    values=(point_id, f"{position[0]:.2f}", f"{position[1]:.2f}", f"{position[2]:.2f}"))

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
            # Remove the point from the main list
            global_state.reference_points = [p for p in global_state.reference_points if p['id'] != item_id]

            # Remove the point from any group that contains it
            for group_id, group_data in global_state.reference_point_groups.items():
                if item_id in group_data['point_ids']:
                    group_data['point_ids'].remove(item_id)

            tree.delete(item_id)
    print(f"Deleted point(s): {', '.join(selected_items)}")

def on_point_select(event, tree, edit_frame, group_combo):
    """Handles populating the edit form when a point is selected."""
    # First, dynamically update the list of available groups in the dropdown
    group_names = ['None'] + [g['name'] for g in global_state.reference_point_groups.values()]
    group_ids = ['None'] + list(global_state.reference_point_groups.keys())
    # Create a mapping from displayed name to actual ID
    group_combo.name_to_id_map = dict(zip(group_names, group_ids))
    group_combo['values'] = group_names

    selected_iid = tree.selection()
    if not selected_iid:
        for child in edit_frame.winfo_children():
            child.configure(state='disabled')
        global_state.edit_point_group_var.set('None')  # Clear group selection
        return

    selected_iid = selected_iid[0]
    with global_state.controller_lock:
        point = next((p for p in global_state.reference_points if p['id'] == selected_iid), None)
        if point:
            global_state.edit_id_var.set(point['id'])
            global_state.edit_x_var.set(f"{point['position'][0]:.2f}")
            global_state.edit_y_var.set(f"{point['position'][1]:.2f}")
            global_state.edit_z_var.set(f"{point['position'][2]:.2f}")

            # Find which group the point belongs to and set the dropdown
            current_group_name = 'None'
            for group_id, group_data in global_state.reference_point_groups.items():
                if selected_iid in group_data['point_ids']:
                    current_group_name = group_data.get('name', 'Unnamed Group')
                    break
            global_state.edit_point_group_var.set(current_group_name)

            for child in edit_frame.winfo_children():
                child.configure(state='normal')

def create_group(tree):
    """Creates a new, empty point group with a unique default name."""
    with global_state.controller_lock:
        base_name = "New Group"
        new_name = base_name
        counter = 2
        existing_names = {g['name'] for g in global_state.reference_point_groups.values()}
        while new_name in existing_names:
            new_name = f"{base_name} ({counter})"
            counter += 1

        group_id = f"group_{uuid.uuid4().hex[:6]}"
        new_group = {
            "name": new_name,
            "point_ids": set(),
            "hit_timestamps": {},  # ADDED: For grace period tracking
            "action": {"type": "Key Press", "detail": ""}
        }
        global_state.reference_point_groups[group_id] = new_group

    tree.insert('', 'end', iid=group_id, values=(new_group['name'],))
    tree.selection_set(group_id)

def delete_group(tree):
    """Deletes the selected group."""
    selected_id = tree.selection()
    if not selected_id:
        messagebox.showinfo("No Selection", "Please select a group to delete.")
        return
    selected_id = selected_id[0]

    if messagebox.askyesno("Confirm Delete",
                           f"Are you sure you want to delete group '{global_state.reference_point_groups[selected_id]['name']}'?"):
        with global_state.controller_lock:
            del global_state.reference_point_groups[selected_id]
        tree.delete(selected_id)

def assign_point_to_group(point_tree, group_combo):
    """Assigns the selected point to the selected group."""
    point_id = point_tree.selection()
    if not point_id:
        messagebox.showinfo("No Selection", "Please select a reference point first.")
        return
    point_id = point_id[0]

    # Get the group name from the dropdown and map it back to its ID
    group_name = group_combo.get()
    group_id = group_combo.name_to_id_map.get(group_name)

    with global_state.controller_lock:
        # First, remove the point from any group it might already be in
        for g_id, g_data in global_state.reference_point_groups.items():
            if point_id in g_data['point_ids']:
                g_data['point_ids'].remove(point_id)

        # Then, add it to the new group (if not 'None')
        if group_id and group_id != 'None':
            global_state.reference_point_groups[group_id]['point_ids'].add(point_id)
            print(f"Assigned point {point_id} to group '{group_name}'")

def on_group_select(event, tree, details_frame, member_list_tree):
    """Handles populating the group details UI when a group is selected."""
    member_list_tree.delete(*member_list_tree.get_children())

    selected_id = tree.selection()

    def set_child_widgets_state(parent, state):
        for child in parent.winfo_children():
            if isinstance(child, (ttk.LabelFrame, ttk.Frame)):
                set_child_widgets_state(child, state)
            try:
                child.configure(state=state)
            except tk.TclError:
                pass

    if not selected_id:
        set_child_widgets_state(details_frame, 'disabled')
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
                if point:
                    member_list_tree.insert('', 'end', iid=f"member_{point_id}", values=(point_id,))

def update_group_details(tree):
    """Saves changes made to the selected group's name or action."""
    selected_id = tree.selection()
    if not selected_id:
        messagebox.showinfo("No Selection", "Please select a group to update.")
        return
    selected_id = selected_id[0]

    with global_state.controller_lock:
        group_data = global_state.reference_point_groups.get(selected_id)
        if group_data:
            group_data['name'] = global_state.group_name_var.get()
            group_data['action'] = {
                'type': global_state.group_action_type_var.get(),
                'detail': global_state.group_action_detail_var.get()
            }
            tree.item(selected_id, values=(group_data['name'],))
            print(f"Updated group {selected_id}")

def update_selected_point(tree, edit_frame):
    selected_iid = tree.selection()
    if not selected_iid: messagebox.showinfo("No Selection", "Please select a point to edit."); return
    original_iid = selected_iid[0]
    try:
        new_id = global_state.edit_id_var.get()
        new_x = float(global_state.edit_x_var.get());
        new_y = float(global_state.edit_y_var.get());
        new_z = float(global_state.edit_z_var.get())
        new_values = (new_id, f"{new_x:.2f}", f"{new_y:.2f}", f"{new_z:.2f}")
        with global_state.controller_lock:
            point_to_update = next((p for p in global_state.reference_points if p['id'] == original_iid), None)
            if point_to_update:
                point_to_update['id'] = new_id;
                point_to_update['position'] = [new_x, new_y, new_z]
        if original_iid != new_id:
            index = tree.index(original_iid);
            tree.delete(original_iid)
            tree.insert('', index, iid=new_id, values=new_values)
        else:
            tree.item(original_iid, values=new_values)
        tree.selection_remove(tree.selection())
        for child in edit_frame.winfo_children(): child.configure(state='disabled')
    except (ValueError, TypeError):
        messagebox.showerror("Invalid Input", "Please enter valid data for all fields.")

def update_action_details_ui(action_type, detail_entry, detail_combo):
    """Shows/hides the correct detail widget based on action type."""
    if action_type == "Controller Press":
        detail_entry.grid_remove()
        detail_combo.grid()
    else: # Key Press or Mouse Click
        detail_combo.grid_remove()
        detail_entry.grid()

def set_home_position():
    """Sets the current controller orientation as the home position."""
    with global_state.controller_lock:
        global_state.home_position = {
            'name': 'Home',
            'orientation': list(global_state.orientation_quaternion)
        }
    update_home_position_ui()
    print("Home position set.")

def go_to_home():
    """Triggers the event to reset the orientation to the home position."""
    if not global_state.home_position:
        messagebox.showinfo("No Home Set", "Please set a home position first.")
        return
    global_state.go_to_home_event.set()

def update_home_from_ui():
    """Saves the manually edited home position data from the UI."""
    if not global_state.home_position:
        messagebox.showinfo("No Home Set", "Please set a home position first.")
        return
    try:
        new_q = [
            float(global_state.home_q_w_var.get()),
            float(global_state.home_q_x_var.get()),
            float(global_state.home_q_y_var.get()),
            float(global_state.home_q_z_var.get())
        ]
        # Normalize the new quaternion to ensure it's a valid rotation
        new_q_norm = np.linalg.norm(new_q)
        if new_q_norm == 0:
            messagebox.showerror("Invalid Input", "Quaternion cannot be all zeros.")
            return
        new_q = new_q / new_q_norm

        with global_state.controller_lock:
            global_state.home_position['name'] = global_state.home_name_var.get()
            global_state.home_position['orientation'] = list(new_q)

        update_home_position_ui()  # Refresh UI to show normalized values
        print("Home position updated.")
    except (ValueError, tk.TclError):
        messagebox.showerror("Invalid Input", "Please enter valid numbers for all quaternion fields.")

def delete_home_position():
    """Deletes the currently saved home position."""
    if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the home position?"):
        with global_state.controller_lock:
            global_state.home_position = {}
        update_home_position_ui()
        print("Home position deleted.")


if __name__ == "__main__":
    GLUT.glutInit(sys.argv)
    root = tk.Tk()
    root.title("SDL Gyro Visualizer")
    root.geometry("650x750")

    # Initialize all Tkinter variables
    global_state.show_visualization_var = tk.BooleanVar(value=False)
    global_state.pause_sensor_updates_var = tk.BooleanVar(value=False)
    global_state.debug_mode_var = tk.BooleanVar(value=False)
    global_state.verbose_logging_var = tk.BooleanVar(value=False)
    global_state.show_ref_point_labels_var = tk.BooleanVar(value=True)
    global_state.play_action_sound_var = tk.BooleanVar(value=True)
    global_state.home_button_map_var, global_state.mapping_status_var = tk.StringVar(), tk.StringVar()
    global_state.save_filename_var = tk.StringVar(value="config.json")
    global_state.load_filename_var = tk.StringVar()
    global_state.raw_gyro_var, global_state.raw_accel_var = tk.StringVar(), tk.StringVar()
    global_state.ref_x_var, global_state.ref_y_var, global_state.ref_z_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    global_state.edit_id_var, global_state.edit_x_var, global_state.edit_y_var, global_state.edit_z_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
    global_state.dimension_w_var, global_state.dimension_h_var, global_state.dimension_d_var = tk.DoubleVar(
        value=global_state.object_dimensions[0]), tk.DoubleVar(
        value=global_state.object_dimensions[1]), tk.DoubleVar(
        value=global_state.object_dimensions[2])
    global_state.camera_orbit_x_var, global_state.camera_orbit_y_var, global_state.camera_zoom_var, global_state.camera_roll_var = tk.DoubleVar(
        value=global_state.camera_orbit_x), tk.DoubleVar(value=global_state.camera_orbit_y), tk.DoubleVar(
        value=global_state.camera_zoom), tk.DoubleVar(value=global_state.camera_roll)
    global_state.beta_gain_var, global_state.hit_tolerance_var, global_state.distance_offset_var = tk.DoubleVar(
        value=global_state.beta_gain), tk.DoubleVar(value=global_state.hit_tolerance), tk.DoubleVar(
        value=global_state.distance_offset)
    global_state.drift_correction_gain_var = tk.DoubleVar(value=global_state.drift_correction_gain)
    global_state.group_grace_period_var = tk.DoubleVar(value=global_state.group_grace_period)
    global_state.debug_axis_var = tk.IntVar(value=0)
    global_state.log_message = ""
    global_state.log_message_var = tk.StringVar()
    global_state.log_to_console_var = tk.BooleanVar(value=False)
    global_state.correct_drift_when_still_var = tk.BooleanVar(
        value=global_state.correct_drift_when_still_enabled)
    global_state.accelerometer_smoothing_var = tk.DoubleVar(value=global_state.accelerometer_smoothing)
    global_state.home_name_var = tk.StringVar()
    global_state.home_q_w_var = tk.StringVar()
    global_state.home_q_x_var = tk.StringVar()
    global_state.home_q_y_var = tk.StringVar()
    global_state.home_q_z_var = tk.StringVar()
    global_state.group_name_var = tk.StringVar()
    global_state.group_action_type_var = tk.StringVar(value="Key Press")
    global_state.group_action_detail_var = tk.StringVar()
    global_state.edit_point_group_var = tk.StringVar()

    main_frame = ttk.Frame(root)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    controls_container = ttk.Frame(main_frame, width=320)
    controls_container.pack(side="right", fill="y", padx=(10, 0))
    controls_container.pack_propagate(False)
    canvas = tk.Canvas(controls_container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(controls_container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")


    def _bound_on_mousewheel(event):
        _on_mousewheel(event, canvas)


    canvas.bind_all("<MouseWheel>", _bound_on_mousewheel)
    vis_container = ttk.Frame(main_frame)
    vis_container.pack(side="left", fill="both", expand=True)
    vis_frame = VisFrame(vis_container)
    vis_frame.pack(fill="both", expand=True)


    def create_slider_entry(parent, text, var, fr, to, r, digits=2, cmd=None):
        ttk.Label(parent, text=text).grid(row=r, column=0, sticky='w', padx=5, pady=2)
        s = ttk.Scale(parent, from_=fr, to=to, orient="horizontal", variable=var)
        if cmd: s.config(command=cmd)
        s.grid(row=r, column=1, sticky='we', padx=(5, 0))
        e = ttk.Entry(parent, width=5)
        e.grid(row=r, column=2, padx=(5, 5))

        def from_var(*a):
            e.delete(0, 'end');
            e.insert(0, f"{var.get():.{digits}f}")

        def from_entry(*a):
            try:
                var.set(float(e.get()))
            except:
                pass

        var.trace_add('write', from_var)
        e.bind("<Return>", from_entry)
        from_var()
        parent.columnconfigure(1, weight=1)


    collapsible_frames = {}
    view_cf = CollapsibleFrame(scrollable_frame, "View Options", True)
    view_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['view'] = view_cf
    controller_cf = CollapsibleFrame(scrollable_frame, "Controller Actions", False)
    controller_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['controller'] = controller_cf
    group_cf = CollapsibleFrame(scrollable_frame, "Point Groups & Actions", False)
    group_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['groups'] = group_cf
    ref_points_cf = CollapsibleFrame(scrollable_frame, "Reference Points", True)
    ref_points_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['ref_points'] = ref_points_cf
    edit_cf = CollapsibleFrame(scrollable_frame, "Edit Selected Point", True)
    edit_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['edit'] = edit_cf
    ref_settings_cf = CollapsibleFrame(scrollable_frame, "Reference Point Settings", True)
    ref_settings_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['ref_settings'] = ref_settings_cf
    filter_cf = CollapsibleFrame(scrollable_frame, "Filter Settings", True)
    filter_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['filter'] = filter_cf
    camera_cf = CollapsibleFrame(scrollable_frame, "Camera Controls", True)
    camera_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['camera'] = camera_cf
    dim_cf = CollapsibleFrame(scrollable_frame, "Object Dimensions", True)
    dim_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['dim'] = dim_cf
    debug_cf = CollapsibleFrame(scrollable_frame, "Debug Tools", True)
    debug_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['debug'] = debug_cf
    config_cf = CollapsibleFrame(scrollable_frame, "Configuration", True)
    config_cf.pack(fill='x', padx=5, pady=5)
    collapsible_frames['config'] = config_cf

    ttk.Checkbutton(view_cf.content_frame, text="Show Visualization",
                    variable=global_state.show_visualization_var,
                    command=lambda: toggle_visualization(root, vis_container, controls_container)).pack(
        anchor='w',
        padx=5)
    ttk.Checkbutton(view_cf.content_frame, text="Pause Sensor Updates",
                    variable=global_state.pause_sensor_updates_var).pack(anchor='w', padx=5)

    ttk.Button(controller_cf.content_frame, text="Zero Orientation", command=zero_orientation).pack(fill='x',
                                                                                                    padx=5,
                                                                                                    pady=2)
    ttk.Separator(controller_cf.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

    home_frame = ttk.Frame(controller_cf.content_frame)
    home_frame.pack(fill='x', expand=True)
    home_buttons_frame = ttk.Frame(home_frame)
    home_buttons_frame.pack(fill='x')
    ttk.Button(home_buttons_frame, text="Set Current as Home", command=set_home_position).pack(side='left',
                                                                                               fill='x',
                                                                                               expand=True,
                                                                                               padx=5, pady=2)
    ttk.Button(home_buttons_frame, text="Go Home", command=go_to_home).pack(side='left', fill='x', expand=True,
                                                                            padx=5, pady=2)
    home_details_frame = ttk.LabelFrame(home_frame, text="Home Position Details")
    home_details_frame.pack(fill='x', padx=5, pady=5)
    ttk.Label(home_details_frame, text="Name:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
    ttk.Entry(home_details_frame, textvariable=global_state.home_name_var).grid(row=0, column=1, columnspan=4,
                                                                                sticky='ew', padx=5, pady=2)
    for i, (label, var) in enumerate([("W:", global_state.home_q_w_var), ("X:", global_state.home_q_x_var),
                                      ("Y:", global_state.home_q_y_var), ("Z:", global_state.home_q_z_var)]):
        ttk.Label(home_details_frame, text=label).grid(row=1, column=i, sticky='w', padx=(5, 0))
        ttk.Entry(home_details_frame, textvariable=var, width=8).grid(row=2, column=i, sticky='w', padx=5)
    home_edit_buttons_frame = ttk.Frame(home_frame)
    home_edit_buttons_frame.pack(fill='x')
    ttk.Button(home_edit_buttons_frame, text="Update Home", command=update_home_from_ui).pack(side='left',
                                                                                              fill='x',
                                                                                              expand=True,
                                                                                              padx=5, pady=2)
    ttk.Button(home_edit_buttons_frame, text="Delete Home", command=delete_home_position).pack(side='left',
                                                                                               fill='x',
                                                                                               expand=True,
                                                                                               padx=5, pady=2)

    group_list_frame = ttk.Frame(group_cf.content_frame)
    group_list_frame.pack(fill='x', expand=True, padx=5, pady=5)

    group_tree = ttk.Treeview(group_list_frame, columns=('Name',), show='headings', height=4)
    group_tree.pack(side='left', fill='x', expand=True)
    group_tree.heading('Name', text='Group Name')
    group_tree.column('Name', anchor='w')

    group_buttons_frame = ttk.Frame(group_list_frame)
    group_buttons_frame.pack(side='left', fill='y', padx=(5, 0))
    ttk.Button(group_buttons_frame, text="New", command=lambda: create_group(group_tree)).pack()
    ttk.Button(group_buttons_frame, text="Delete", command=lambda: delete_group(group_tree)).pack()

    group_details_frame = ttk.LabelFrame(group_cf.content_frame, text="Selected Group Details")
    group_details_frame.pack(fill='x', padx=5, pady=5)

    create_slider_entry(group_details_frame, "Grace Period (s):", global_state.group_grace_period_var, 0.0, 10.0, 0,
                        digits=2)

    ttk.Label(group_details_frame, text="Name:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
    ttk.Entry(group_details_frame, textvariable=global_state.group_name_var).grid(row=1, column=1, sticky='ew', padx=5,
                                                                                  pady=2)

    ttk.Label(group_details_frame, text="Action Type:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
    action_types = ["Key Press", "Mouse Click"]
    action_type_combo = ttk.Combobox(group_details_frame, textvariable=global_state.group_action_type_var,
                                     values=action_types, state="readonly")
    action_type_combo.grid(row=2, column=1, sticky='ew', padx=5, pady=2)

    ttk.Label(group_details_frame, text="Action Detail:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
    ttk.Entry(group_details_frame, textvariable=global_state.group_action_detail_var).grid(row=3, column=1, sticky='ew',
                                                                                           padx=5, pady=2)

    ttk.Button(group_details_frame, text="Update Group Details", command=lambda: update_group_details(group_tree)).grid(
        row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=5)

    member_frame = ttk.LabelFrame(group_details_frame, text="Points in Group")
    member_frame.grid(row=5, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
    member_list_tree = ttk.Treeview(member_frame, columns=('ID',), show='headings', height=3)
    member_list_tree.pack(side='left', fill='x', expand=True)
    member_list_tree.heading('ID', text='Point ID')
    member_list_tree.column('ID', anchor='w')

    group_details_frame.columnconfigure(1, weight=1)
    group_tree.bind('<<TreeviewSelect>>',
                    lambda e: on_group_select(e, group_tree, group_details_frame, member_list_tree))

    ref_content = ref_points_cf.content_frame
    ttk.Button(ref_content, text="Record Current Tip Position",
               command=lambda: add_reference_point(ref_tree)).pack(
        fill='x', padx=5, pady=2)
    manual_frame = ttk.Frame(ref_content)
    manual_frame.pack(fill='x', padx=5, pady=5)
    for i, (label, var) in enumerate(
            [("X:", global_state.ref_x_var), ("Y:", global_state.ref_y_var), ("Z:", global_state.ref_z_var)]):
        ttk.Label(manual_frame, text=label).pack(side='left')
        ttk.Entry(manual_frame, width=5, textvariable=var).pack(side='left')
    ttk.Button(manual_frame, text="Add", command=lambda: add_manual_reference_point(ref_tree)).pack(side='left',
                                                                                                    padx=(5, 0))
    tree_frame = ttk.Frame(ref_content)
    tree_frame.pack(fill='x', expand=True, padx=5, pady=5)
    ref_tree = ttk.Treeview(tree_frame, columns=('ID', 'X', 'Y', 'Z'), show='headings', height=4)
    ref_tree.pack(side='left', fill='x', expand=True)
    for col, w in [('ID', 50), ('X', 70), ('Y', 70), ('Z', 70)]: ref_tree.heading(col,
                                                                                  text=col); ref_tree.column(
        col,
        width=w,
        anchor='center')
    ttk.Button(ref_content, text="Delete Selected", command=lambda: delete_reference_point(ref_tree)).pack(
        fill='x',
        padx=5,
        pady=2)

    edit_content = edit_cf.content_frame
    for i, (label, var) in enumerate(
            [("ID:", global_state.edit_id_var), ("X:", global_state.edit_x_var),
             ("Y:", global_state.edit_y_var),
             ("Z:", global_state.edit_z_var)]):
        ttk.Label(edit_content, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(edit_content, textvariable=var, state='disabled').grid(row=i, column=1, sticky='ew', padx=5,
                                                                         pady=2)
    ttk.Button(edit_content, text="Update Point", command=lambda: update_selected_point(ref_tree, edit_content),
               state='disabled').grid(row=4, columnspan=2, sticky='ew', padx=5, pady=5)

    ttk.Label(edit_content, text="Assign to Group:").grid(row=5, column=0, sticky='w', padx=5, pady=2)
    group_combo = ttk.Combobox(edit_content, textvariable=global_state.edit_point_group_var, values=['None'],
                               state='readonly')
    group_combo.grid(row=5, column=1, sticky='ew', padx=5, pady=2)
    ttk.Button(edit_content, text="Assign Point", command=lambda: assign_point_to_group(ref_tree, group_combo)).grid(
        row=6, columnspan=2, sticky='ew', padx=5, pady=5)

    ref_tree.bind('<<TreeviewSelect>>', lambda e: on_point_select(e, ref_tree, edit_content, group_combo))

    create_slider_entry(ref_settings_cf.content_frame, "Hit Tolerance:", global_state.hit_tolerance_var, 0.01,
                        1.0, 0,
                        digits=2)
    create_slider_entry(ref_settings_cf.content_frame, "Distance Offset:", global_state.distance_offset_var,
                        0.0, 2.0,
                        1, digits=2)
    ttk.Checkbutton(ref_settings_cf.content_frame, text="Show Point Labels",
                    variable=global_state.show_ref_point_labels_var, command=toggle_point_labels).grid(row=2,
                                                                                                       columnspan=3,
                                                                                                       sticky='w',
                                                                                                       padx=5)

    create_slider_entry(filter_cf.content_frame, "Filter Beta Gain:", global_state.beta_gain_var, 0.01, 1.0, 0,
                        digits=2)
    create_slider_entry(filter_cf.content_frame, "Drift Correction (Zeta):",
                        global_state.drift_correction_gain_var,
                        0.0, 0.5, 1, digits=3)
    create_slider_entry(filter_cf.content_frame, "Accel Smoothing:", global_state.accelerometer_smoothing_var,
                        0.01, 1.0, 2, digits=2)
    ttk.Checkbutton(filter_cf.content_frame, text="Drift-Correct Only When Still",
                    variable=global_state.correct_drift_when_still_var).grid(row=3, columnspan=3, sticky='w',
                                                                             padx=5)

    create_slider_entry(camera_cf.content_frame, "Orbit X:", global_state.camera_orbit_x_var, -180, 180, 0,
                        digits=0,
                        cmd=update_camera_settings)
    create_slider_entry(camera_cf.content_frame, "Orbit Y:", global_state.camera_orbit_y_var, -180, 180, 1,
                        digits=0,
                        cmd=update_camera_settings)

    create_slider_entry(dim_cf.content_frame, "Width:", global_state.dimension_w_var, 0.1, 5.0, 0, digits=1,
                        cmd=update_object_dimensions)
    create_slider_entry(dim_cf.content_frame, "Height:", global_state.dimension_h_var, 0.1, 5.0, 1, digits=1,
                        cmd=update_object_dimensions)
    create_slider_entry(dim_cf.content_frame, "Depth:", global_state.dimension_d_var, 0.1, 5.0, 2, digits=1,
                        cmd=update_object_dimensions)

    ttk.Checkbutton(debug_cf.content_frame, text="Log to UI", variable=global_state.verbose_logging_var).pack(
        anchor='w', padx=5)
    ttk.Checkbutton(debug_cf.content_frame, text="Log to Console",
                    variable=global_state.log_to_console_var).pack(anchor='w', padx=5)
    ttk.Checkbutton(debug_cf.content_frame, text="Play Sound on Action",
                    variable=global_state.play_action_sound_var).pack(anchor='w', padx=5)
    log_label = ttk.Label(debug_cf.content_frame, textvariable=global_state.log_message_var,
                          font=("Courier", 9), wraplength=300, justify='left')
    log_label.pack(anchor='w', padx=5, pady=2, fill='x')

    config_content = config_cf.content_frame
    save_frame = ttk.LabelFrame(config_content, text="Save Configuration")
    save_frame.pack(fill='x', padx=5, pady=5)
    ttk.Label(save_frame, text="Filename:").pack(side='left', padx=(5, 2))
    ttk.Entry(save_frame, textvariable=global_state.save_filename_var).pack(side='left', fill='x', expand=True, padx=2)
    ttk.Button(save_frame, text="Save", width=8,
               command=lambda: save_config(root, collapsible_frames, global_state.save_filename_var.get())).pack(
        side='left', padx=(2, 5))
    load_frame = ttk.LabelFrame(config_content, text="Load Configuration")
    load_frame.pack(fill='x', padx=5, pady=5)


    def refresh_load_list():
        json_files = [f for f in os.listdir('.') if f.endswith('.json')]
        load_combo['values'] = json_files
        if json_files:
            global_state.load_filename_var.set(json_files[0])


    ttk.Label(load_frame, text="Load File:").pack(side='left', padx=(5, 2))
    load_combo = ttk.Combobox(load_frame, textvariable=global_state.load_filename_var, state='readonly')
    load_combo.pack(side='left', fill='x', expand=True, padx=2)
    refresh_button = ttk.Button(load_frame, text="🔄", width=3, command=refresh_load_list)
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
        if global_state.home_button_event.is_set(): zero_orientation(); global_state.home_button_event.clear()

        with global_state.controller_lock:
            if hasattr(global_state, 'log_message_var'):
                global_state.log_message_var.set(global_state.log_message)

            q = global_state.orientation_quaternion
            offset = global_state.distance_offset
            tip_pos = rotate_point_by_quaternion(np.array([0, 0, offset]), q)
            global_state.controller_tip_position = tip_pos

            currently_hit_points = set()
            for point in global_state.reference_points:
                is_hit = np.linalg.norm(tip_pos - np.array(point['position'])) < global_state.hit_tolerance
                point['hit'] = is_hit
                if is_hit:
                    currently_hit_points.add(point['id'])

            current_time = time.monotonic()
            grace_period = global_state.group_grace_period

            completed_in_current_frame = set()

            for group_id, group_data in global_state.reference_point_groups.items():
                for point_id in group_data['point_ids']:
                    if point_id in currently_hit_points:
                        group_data.setdefault('hit_timestamps', {})[point_id] = current_time

                expired_points = [
                    pid for pid, hit_time in group_data.get('hit_timestamps', {}).items()
                    if current_time - hit_time > grace_period
                ]
                for pid in expired_points:
                    del group_data['hit_timestamps'][pid]

                if group_data['point_ids'] and len(group_data.get('hit_timestamps', {})) == len(
                        group_data['point_ids']):
                    completed_in_current_frame.add(group_id)
                    if group_id not in global_state.previously_completed_groups:
                        action_executor.execute(group_data['action'])
                        group_data['hit_timestamps'].clear()

            global_state.previously_completed_groups = completed_in_current_frame

        if global_state.show_visualization_var.get() and global_state.is_calibrated:
            vis_frame.redraw()

        root.after(16, update_gui)


    # --- Final Startup Sequence ---
    root.protocol("WM_DELETE_WINDOW", on_closing)

    load_config_and_update_gui(root, ref_tree, group_tree, collapsible_frames,
                               filepath=os.path.join(os.getcwd(), "config.json"),
                               initial_load=True)

    root.update_idletasks()
    toggle_visualization(root, vis_container, controls_container)

    root.after(2500, zero_orientation)
    root.after(150, update_gui)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nCtrl+C detected, shutting down.")
        on_closing()