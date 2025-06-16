import tkinter as tk  # Needed for tk.DISABLED state, tk.LEFT, etc.
from tkinter import ttk
import tkinter.simpledialog
import tkinter.messagebox
import global_state  # For accessing global variables like saved_positions, selected_position_index
from models import SavedPosition  # Import SavedPosition model
import threading  # For threading.Thread
import controller_interface  # To call _record_position_points (e.g., _finalize_recording uses it implicitly)
from gui_elements import create_numeric_slider_control, update_highlight_on_gui 
from motion_sequence_manager_gui import update_motion_sequences_display


# --- Position Display and Selection ---
def update_saved_positions_display():
    # Clear existing labels from the scrollable frame
    for label in global_state.saved_position_labels:
        if label.winfo_exists():
            label.destroy()
    global_state.saved_position_labels = []

    # Create new labels and pack them into the inner scrollable frame
    for i, pos in enumerate(global_state.saved_positions):
        enabled_axes = [axis for axis, enabled in pos.detection_axes.items() if enabled]
        detection_axes_str = f"({', '.join(enabled_axes) if enabled_axes else 'None'})"

        display_gyro = pos.custom_avg_gyro if pos.custom_avg_gyro is not None else pos.avg_gyro
        display_accel = pos.custom_avg_accel if pos.custom_avg_accel is not None else pos.avg_accel
        custom_indicator = "*" if (pos.custom_avg_gyro is not None or pos.custom_avg_accel is not None) else ""

        pos_text = (
            f"{pos.name}{custom_indicator} {detection_axes_str}\n"
            f"(G:{display_gyro[0]:.0f},{display_gyro[1]:.0f},{display_gyro[2]:.0f} | "
            f"A:{display_accel[0]:.1f},{display_accel[1]:.1f},{display_accel[2]:.1f})"
            f" | Pad: {pos.padding_factor:.3f}"
        )
        label = tk.Label(global_state.saved_positions_scrollable_frame, text=pos_text, anchor='w', justify=tk.LEFT,
                         padx=5, pady=2,
                         relief="groove", borderwidth=1, bg="SystemButtonFace", fg="black")
        label.pack(fill='x', expand=True, padx=5, pady=2)
        label.bind("<Button-1>", lambda event, idx=i: select_position_for_editing(idx))
        global_state.saved_position_labels.append(label)

    global_state.saved_positions_scrollable_frame.update_idletasks()
    # Ensure global_state.canvas_for_positions is correctly referenced (it's initialized in main_app.py)
    global_state.canvas_for_positions.config(scrollregion=global_state.canvas_for_positions.bbox("all"))

    # CORRECTED: Call update_highlight_on_gui directly
    update_highlight_on_gui(global_state.current_highlighted_label_index)
    if global_state.selected_position_index != -1 and global_state.selected_position_index < len(
            global_state.saved_position_labels):
        global_state.saved_position_labels[global_state.selected_position_index].config(bg="lightblue")


def select_position_for_editing(index):
    if global_state.selected_position_index == index:
        global_state.selected_position_index = -1
        hide_edit_position_controls()
    else:
        global_state.selected_position_index = index
        show_edit_position_controls()

    update_highlight_on_gui(global_state.current_highlighted_label_index)  # CORRECTED: Call directly


# --- Per-Position Editing Controls ---
def show_edit_position_controls():
    hide_edit_position_controls()
    if global_state.selected_position_index == -1:
        return
    selected_pos = global_state.saved_positions[global_state.selected_position_index]

    global_state.edit_position_controls_frame = tk.LabelFrame(global_state.saved_positions_frame,
                                                              text="Edit Selected Position", padx=5, pady=5)
    global_state.edit_position_controls_frame.pack(fill='x', padx=5, pady=10)

    global_state.per_position_name_var.set(f"Editing: {selected_pos.name}")
    tk.Label(global_state.edit_position_controls_frame, textvariable=global_state.per_position_name_var,
             font=("Segoe UI", 10, "bold")).pack(pady=5)

    # Use create_numeric_slider_control directly
    create_numeric_slider_control(
        parent_frame=global_state.edit_position_controls_frame,
        label_text="Position-Specific Range Padding:",
        tk_var=global_state.per_position_padding_var,
        slider_from=0.0,
        slider_to=2500.0,
        slider_command=update_per_position_padding,
        default_error_val=50.0,
        is_float=True
    )
    global_state.per_position_padding_var.set(selected_pos.padding_factor)

    tk.Label(global_state.edit_position_controls_frame, text="Detection Axes:").pack(side="top", anchor="w", padx=5,
                                                                                     pady=(5, 0))

    gyro_axes_frame = tk.Frame(global_state.edit_position_controls_frame)
    gyro_axes_frame.pack(side="top", anchor="w", padx=10)
    tk.Label(gyro_axes_frame, text="Gyro:").pack(side="left")
    global_state.per_position_use_pitch_var.set(selected_pos.detection_axes['Pitch'])
    ttk.Checkbutton(gyro_axes_frame, text="Pitch", variable=global_state.per_position_use_pitch_var,
                    command=update_per_position_axis_detection).pack(side="left", padx=2)
    global_state.per_position_use_yaw_var.set(selected_pos.detection_axes['Yaw'])
    ttk.Checkbutton(gyro_axes_frame, text="Yaw", variable=global_state.per_position_use_yaw_var,
                    command=update_per_position_axis_detection).pack(side="left", padx=2)
    global_state.per_position_use_roll_var.set(selected_pos.detection_axes['Roll'])
    ttk.Checkbutton(gyro_axes_frame, text="Roll", variable=global_state.per_position_use_roll_var,
                    command=update_per_position_axis_detection).pack(side="left", padx=2)

    accel_axes_frame = tk.Frame(global_state.edit_position_controls_frame)
    accel_axes_frame.pack(side="top", anchor="w", padx=10)
    tk.Label(accel_axes_frame, text="Accel:").pack(side="left")
    global_state.per_position_use_accel_x_var.set(selected_pos.detection_axes['X'])
    ttk.Checkbutton(accel_axes_frame, text="X", variable=global_state.per_position_use_accel_x_var,
                    command=update_per_position_axis_detection).pack(side="left", padx=2)
    global_state.per_position_use_accel_y_var.set(selected_pos.detection_axes['Y'])
    ttk.Checkbutton(accel_axes_frame, text="Y", variable=global_state.per_position_use_accel_y_var,
                    command=update_per_position_axis_detection).pack(side="left", padx=2)
    global_state.per_position_use_accel_z_var.set(selected_pos.detection_axes['Z'])
    ttk.Checkbutton(accel_axes_frame, text="Z", variable=global_state.per_position_use_accel_z_var,
                    command=update_per_position_axis_detection).pack(side="left", padx=2)

    tk.Label(global_state.edit_position_controls_frame, text="Override Recorded Averages:").pack(side="top", anchor="w",
                                                                                                 padx=5, pady=(10, 0))

    gyro_avg_frame = tk.Frame(global_state.edit_position_controls_frame)
    gyro_avg_frame.pack(fill='x', padx=10, pady=2)
    tk.Label(gyro_avg_frame, text="G:").pack(side="left")

    global_state.edit_avg_pitch_var.set(
        selected_pos.avg_gyro[0] if selected_pos.custom_avg_gyro is None else selected_pos.custom_avg_gyro[0])
    ttk.Entry(gyro_avg_frame, textvariable=global_state.edit_avg_pitch_var, width=8, justify='center',
              font=("Segoe UI", 9)).pack(side="left", padx=2)
    tk.Label(gyro_avg_frame, text="P").pack(side="left")

    global_state.edit_avg_yaw_var.set(
        selected_pos.avg_gyro[1] if selected_pos.custom_avg_gyro is None else selected_pos.custom_avg_gyro[1])
    ttk.Entry(gyro_avg_frame, textvariable=global_state.edit_avg_yaw_var, width=8, justify='center',
              font=("Segoe UI", 9)).pack(side="left", padx=2)
    tk.Label(gyro_avg_frame, text="Y").pack(side="left")

    global_state.edit_avg_roll_var.set(
        selected_pos.avg_gyro[2] if selected_pos.custom_avg_gyro is None else selected_pos.custom_avg_gyro[2])
    ttk.Entry(gyro_avg_frame, textvariable=global_state.edit_avg_roll_var, width=8, justify='center',
              font=("Segoe UI", 9)).pack(side="left", padx=2)
    tk.Label(gyro_avg_frame, text="R").pack(side="left")

    accel_avg_frame = tk.Frame(global_state.edit_position_controls_frame)
    accel_avg_frame.pack(fill='x', padx=10, pady=2)
    tk.Label(accel_avg_frame, text="A:").pack(side="left")

    global_state.edit_avg_accel_x_var.set(
        selected_pos.avg_accel[0] if selected_pos.custom_avg_accel is None else selected_pos.custom_avg_accel[0])
    ttk.Entry(accel_avg_frame, textvariable=global_state.edit_avg_accel_x_var, width=8, justify='center',
              font=("Segoe UI", 9)).pack(side="left", padx=2)
    tk.Label(accel_avg_frame, text="X").pack(side="left")

    global_state.edit_avg_accel_y_var.set(
        selected_pos.avg_accel[1] if selected_pos.custom_avg_accel is None else selected_pos.custom_avg_accel[1])
    ttk.Entry(accel_avg_frame, textvariable=global_state.edit_avg_accel_y_var, width=8, justify='center',
              font=("Segoe UI", 9)).pack(side="left", padx=2)
    tk.Label(accel_avg_frame, text="Y").pack(side="left")

    global_state.edit_avg_accel_z_var.set(
        selected_pos.avg_accel[2] if selected_pos.custom_avg_accel is None else selected_pos.custom_avg_accel[2])
    ttk.Entry(accel_avg_frame, textvariable=global_state.edit_avg_accel_z_var, width=8, justify='center',
              font=("Segoe UI", 9)).pack(side="left", padx=2)
    tk.Label(accel_avg_frame, text="Z").pack(side="left")

    set_averages_button = tk.Button(global_state.edit_position_controls_frame, text="Set Overridden Averages",
                                    command=update_edited_avg_axis_value, font=("Segoe UI", 9))
    set_averages_button.pack(pady=5)

    reset_overrides_button = tk.Button(global_state.edit_position_controls_frame, text="Reset Overrides",
                                       command=reset_edited_avg_values, font=("Segoe UI", 9), bg="orange",
                                       activebackground="darkorange")
    reset_overrides_button.pack(pady=5)

    rename_button = tk.Button(global_state.edit_position_controls_frame, text="Rename",
                              command=rename_selected_position)
    rename_button.pack(pady=5)

    delete_button = tk.Button(global_state.edit_position_controls_frame, text="Delete Position",
                              command=delete_selected_position, bg="red", fg="white")
    delete_button.pack(pady=5)

    global_state.combine_button.pack(pady=10)  # Access combine_button via global_state


def hide_edit_position_controls():
    if global_state.edit_position_controls_frame and global_state.edit_position_controls_frame.winfo_exists():
        global_state.edit_position_controls_frame.destroy()
    global_state.edit_position_controls_frame = None

    if global_state.combine_button and global_state.combine_button.winfo_exists():
        global_state.combine_button.pack_forget()


def update_per_position_padding(val):
    if global_state.selected_position_index != -1 and global_state.selected_position_index < len(
            global_state.saved_positions):
        global_state.saved_positions[global_state.selected_position_index].padding_factor = round(float(val), 3)
        update_saved_positions_display()


# Function to update edited average axis values - Called by new "Set" button
def update_edited_avg_axis_value(event=None):
    if global_state.selected_position_index == -1 or global_state.selected_position_index >= len(
            global_state.saved_positions):
        return

    selected_pos = global_state.saved_positions[global_state.selected_position_index]

    new_gyro = [0.0, 0.0, 0.0]
    new_accel = [0.0, 0.0, 0.0]

    valid_input = True

    try:
        new_gyro[0] = round(float(global_state.edit_avg_pitch_var.get()), 3)
        new_gyro[1] = round(float(global_state.edit_avg_yaw_var.get()), 3)
        new_gyro[2] = round(float(global_state.edit_avg_roll_var.get()), 3)

        new_accel[0] = round(float(global_state.edit_avg_accel_x_var.get()), 3)
        new_accel[1] = round(float(global_state.edit_avg_accel_y_var.get()), 3)
        new_accel[2] = round(float(global_state.edit_avg_accel_z_var.get()), 3)

        selected_pos.custom_avg_gyro = tuple(new_gyro)
        selected_pos.custom_avg_accel = tuple(new_accel)

    except ValueError:
        valid_input = False
        selected_pos.custom_avg_gyro = None
        selected_pos.custom_avg_accel = None
        tkinter.messagebox.showerror("Invalid Input",
                                     "One or more average axis values are invalid. Reverting to original calculated averages.")

    # Reset Tkinter vars to reflect current state of selected_pos (either updated custom or reverted to calculated)
    global_state.edit_avg_pitch_var.set(
        selected_pos.avg_gyro[0] if selected_pos.custom_avg_gyro is None else selected_pos.custom_avg_gyro[0])
    global_state.edit_avg_yaw_var.set(
        selected_pos.avg_gyro[1] if selected_pos.custom_avg_gyro is None else selected_pos.custom_avg_gyro[1])
    global_state.edit_avg_roll_var.set(
        selected_pos.avg_gyro[2] if selected_pos.custom_avg_gyro is None else selected_pos.custom_avg_gyro[2])
    global_state.edit_avg_accel_x_var.set(
        selected_pos.avg_accel[0] if selected_pos.custom_avg_accel is None else selected_pos.custom_avg_accel[0])
    global_state.edit_avg_accel_y_var.set(
        selected_pos.avg_accel[1] if selected_pos.custom_avg_accel is None else selected_pos.custom_avg_accel[
            1])  # Corrected typo: selected_pos.avg_accem
    global_state.edit_avg_accel_z_var.set(
        selected_pos.avg_accel[2] if selected_pos.custom_avg_accel is None else selected_pos.custom_avg_accel[2])

    if valid_input:
        print(
            f"Updated {selected_pos.name} custom averages to: Gyro={selected_pos.custom_avg_gyro}, Accel={selected_pos.custom_avg_accel}")

    update_saved_positions_display()


def reset_edited_avg_values():
    if global_state.selected_position_index == -1 or global_state.selected_position_index >= len(
            global_state.saved_positions):
        return

    selected_pos = global_state.saved_positions[global_state.selected_position_index]

    selected_pos.custom_avg_gyro = None
    selected_pos.custom_avg_accel = None

    tkinter.messagebox.showinfo("Overrides Reset",
                                f"Overridden averages for '{selected_pos.name}' have been reset to calculated values.")

    global_state.edit_avg_pitch_var.set(selected_pos.avg_gyro[0])
    global_state.edit_avg_yaw_var.set(selected_pos.avg_gyro[1])
    global_state.edit_avg_roll_var.set(selected_pos.avg_gyro[2])
    global_state.edit_avg_accel_x_var.set(selected_pos.avg_accel[0])
    global_state.edit_avg_accel_y_var.set(selected_pos.avg_accel[1])
    global_state.edit_avg_accel_z_var.set(selected_pos.avg_accel[2])

    update_saved_positions_display()


def rename_selected_position():
    if global_state.selected_position_index != -1 and global_state.selected_position_index < len(
            global_state.saved_positions):
        current_name = global_state.saved_positions[global_state.selected_position_index].name
        new_name = tkinter.simpledialog.askstring("Rename Position", f"Enter new name for '{current_name}':",
                                                  initialvalue=current_name)
        if new_name and new_name.strip():
            global_state.saved_positions[global_state.selected_position_index].name = new_name.strip()
            update_saved_positions_display()
            global_state.per_position_name_var.set(f"Editing: {new_name.strip()}")


def delete_selected_position():
    if global_state.selected_position_index != -1 and global_state.selected_position_index < len(
            global_state.saved_positions):
        if tkinter.messagebox.askyesno("Delete Position",
                                       f"Are you sure you want to delete '{global_state.saved_positions[global_state.selected_position_index].name}'?"):
            deleted_pos_id = global_state.saved_positions[global_state.selected_position_index].id
            for seq in global_state.saved_motion_sequences:
                # Correctly filter out the steps with the deleted position ID
                seq.steps = [step for step in seq.steps if step.position_id != deleted_pos_id]
                if seq.current_position_index >= len(seq.steps):
                    seq.current_position_index = 0
                    seq.last_match_time = None

            del global_state.saved_positions[global_state.selected_position_index]
            global_state.selected_position_index = -1
            hide_edit_position_controls()
            update_saved_positions_display()
            # This was missing and is needed to reflect the changes in the UI
            update_motion_sequences_display()


def start_recording_thread():
    if global_state.ds and global_state.ds.connected and not global_state.is_recording:
        global_state.is_recording = True
        global_state.save_button.config(state=tk.DISABLED)
        global_state.connection_status_var.set("Recording position...")

        # CORRECTED: Call the renamed function directly from controller_interface
        recording_thread = threading.Thread(target=controller_interface.record_position_points, daemon=True)
        recording_thread.start()
    elif global_state.is_recording:
        print("Already recording a position.")
    else:
        print("Controller not connected to start recording.")

def update_per_position_padding(val):
    if global_state.selected_position_index != -1 and global_state.selected_position_index < len(
            global_state.saved_positions):
        global_state.saved_positions[global_state.selected_position_index].padding_factor = round(float(val), 3)
        update_saved_positions_display()


def update_per_position_axis_detection():
    if global_state.selected_position_index != -1 and global_state.selected_position_index < len(
            global_state.saved_positions):
        selected_pos = global_state.saved_positions[global_state.selected_position_index]

        current_detection_axes = {
            'Pitch': global_state.per_position_use_pitch_var.get(),
            'Yaw': global_state.per_position_use_yaw_var.get(),
            'Roll': global_state.per_position_use_roll_var.get(),
            'X': global_state.per_position_use_accel_x_var.get(),
            'Y': global_state.per_position_use_accel_y_var.get(),
            'Z': global_state.per_position_use_accel_z_var.get()
        }

        if not any(current_detection_axes.values()):
            tkinter.messagebox.showwarning("Detection Axis Error",
                                           "At least one detection axis must be enabled for this position.")
            selected_pos.detection_axes = {'Pitch': True, 'Yaw': True, 'Roll': True,
                                           'X': True, 'Y': True, 'Z': True}
            global_state.per_position_use_pitch_var.set(True)
            global_state.per_position_use_yaw_var.set(True)
            global_state.per_position_use_roll_var.set(True)
            global_state.per_position_use_accel_x_var.set(True)
            global_state.per_position_use_accel_y_var.set(True)
            global_state.per_position_use_accel_z_var.set(True)
        else:
            selected_pos.detection_axes = current_detection_axes

        update_saved_positions_display()


# --- Functions for combining positions ---
def open_combine_dialog():
    combine_window = tk.Toplevel(global_state.root)
    combine_window.title("Combine Positions")
    combine_window.geometry("450x550")

    tk.Label(combine_window, text="Select Positions to Combine", font=("Segoe UI", 12, "bold")).pack(pady=10)
    tk.Label(combine_window, text="Select at least two positions.").pack()

    canvas_combine_positions = tk.Canvas(combine_window)
    scrollbar_combine = ttk.Scrollbar(combine_window, orient="vertical", command=canvas_combine_positions.yview)
    scrollable_frame_combine = tk.Frame(canvas_combine_positions)

    scrollable_frame_combine.bind(
        "<Configure>",
        lambda e: canvas_combine_positions.configure(
            scrollregion=canvas_combine_positions.bbox("all")
        )
    )
    canvas_combine_positions.create_window((0, 0), window=scrollable_frame_combine, anchor="nw")
    canvas_combine_positions.configure(yscrollcommand=scrollbar_combine.set)

    canvas_combine_positions.pack(side="top", fill="both", expand=True, padx=10, pady=5)
    scrollbar_combine.pack(side="right", fill="y")

    selected_combine_vars = []
    for pos in global_state.saved_positions:
        var = tk.BooleanVar(value=False)
        chk = ttk.Checkbutton(scrollable_frame_combine, text=pos.name, variable=var)
        chk.pack(anchor="w", padx=5, pady=2)
        selected_combine_vars.append((pos, var))

    def perform_combine_action():
        selected_for_combine = [pos for pos, var in selected_combine_vars if var.get()]
        if len(selected_for_combine) < 2:
            tkinter.messagebox.showwarning("Combine Error", "Please select at least two positions to combine.")
            return

        _combine_positions(selected_for_combine)
        combine_window.destroy()

    tk.Button(combine_window, text="Combine Selected", command=perform_combine_action, bg="lightgreen").pack(pady=10)
    tk.Button(combine_window, text="Cancel", command=combine_window.destroy).pack(pady=5)


# --- Function to perform the combination logic ---
def _combine_positions(positions_to_combine):
    combined_recorded_points = []
    combined_name_parts = []
    for pos in positions_to_combine:
        combined_recorded_points.extend(pos.recorded_points)
        combined_name_parts.append(pos.name)

    new_name = f"Combined ({' & '.join(combined_name_parts)})"

    new_combined_pos = SavedPosition(
        recorded_points=combined_recorded_points,
        name=new_name,
        padding_factor=global_state.initial_range_padding,
        detection_axes={'Pitch': True, 'Yaw': True, 'Roll': True, 'X': True, 'Y': True, 'Z': True}
    )

    global_state.saved_positions.append(new_combined_pos)
    print(f"Created combined position: {new_combined_pos}")

    update_saved_positions_display()
    global_state.root.after(0, lambda: select_position_for_editing(
        len(global_state.saved_positions) - 1))  # Select new combined pos
