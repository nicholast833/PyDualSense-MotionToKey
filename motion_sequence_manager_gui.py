import tkinter as tk
from tkinter import ttk
import tkinter.simpledialog
import tkinter.messagebox
import global_state
from models import MotionSequence, MotionSequenceStep
from gui_elements import create_numeric_slider_control, \
    update_highlight_on_gui  # CORRECTED: Ensure update_highlight_on_gui is imported


def update_motion_sequences_display():
    for label in global_state.saved_motion_sequence_labels:
        if label.winfo_exists():
            label.destroy()
    global_state.saved_motion_sequence_labels = []
    for i, seq in enumerate(global_state.saved_motion_sequences):
        export_status = "Export: On" if seq.export_reps_to_file else "Export: Off"
        seq_text = (
            f"{seq.name} | Steps: {len(seq.steps)} | Time: {seq.time_window_ms}ms "
            f"| Grace: {seq.reset_grace_period_ms}ms | Reps: {seq.repetition_count}"
            f" | Action: {seq.action_binding if seq.action_binding else 'None'}"
            f" | {export_status}"
        )
        label = tk.Label(global_state.motions_frame, text=seq_text, anchor='w', justify='left', padx=5, pady=2,
                         relief="groove", borderwidth=1, bg="SystemButtonFace", fg="black")
        label.pack(fill='x', expand=True, padx=5, pady=2)
        label.bind("<Button-1>", lambda event, idx=i: select_motion_sequence_for_editing(idx))
        global_state.saved_motion_sequence_labels.append(label)
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequence_labels):
        global_state.saved_motion_sequence_labels[global_state.selected_motion_sequence_index].config(bg="lightblue")


def select_motion_sequence_for_editing(index):
    if global_state.selected_motion_sequence_index == index:
        global_state.selected_motion_sequence_index = -1
        hide_edit_motion_controls()
    else:
        global_state.selected_position_index = -1  # Unselect any position being edited
        global_state.selected_motion_sequence_index = index
        show_edit_motion_controls()

    if global_state.selected_motion_sequence_index != -1:
        selected_seq = global_state.saved_motion_sequences[global_state.selected_motion_sequence_index]
        global_state.motion_sequence_repetition_count_var.set(selected_seq.repetition_count)
        global_state.motion_sequence_action_var.set(selected_seq.action_binding if selected_seq.action_binding else "")
        global_state.motion_sequence_export_reps_var.set(selected_seq.export_reps_to_file)
        global_state.motion_sequence_export_file_var.set(
            selected_seq.export_file_path if selected_seq.export_file_path else "")
    else:
        global_state.motion_sequence_repetition_count_var.set(0)
        global_state.motion_sequence_action_var.set("")
        global_state.motion_sequence_export_reps_var.set(False)
        global_state.motion_sequence_export_file_var.set("")

    # CORRECTED: Call update_highlight_on_gui directly
    update_highlight_on_gui(global_state.current_highlighted_label_index)
    update_motion_sequences_display()


def show_edit_motion_controls():
    hide_edit_motion_controls()
    if global_state.selected_motion_sequence_index == -1:
        return
    selected_seq = global_state.saved_motion_sequences[global_state.selected_motion_sequence_index]
    global_state.edit_motion_controls_frame = tk.LabelFrame(global_state.motions_frame, text="Edit Selected Motion",
                                                            padx=5, pady=5)
    global_state.edit_motion_controls_frame.pack(fill='x', padx=5, pady=10)
    global_state.motion_sequence_name_var.set(f"Editing: {selected_seq.name}")
    tk.Label(global_state.edit_motion_controls_frame, textvariable=global_state.motion_sequence_name_var,
             font=("Segoe UI", 10, "bold")).pack(pady=5)

    create_numeric_slider_control(
        parent_frame=global_state.edit_motion_controls_frame,
        label_text="Time Window Between Positions (ms):",
        tk_var=global_state.motion_sequence_time_window_var,
        slider_from=50,
        slider_to=20000,
        slider_command=update_motion_time_window,
        default_error_val=1000,
        is_float=False
    )
    global_state.motion_sequence_time_window_var.set(selected_seq.time_window_ms)

    create_numeric_slider_control(
        parent_frame=global_state.edit_motion_controls_frame,
        label_text="Reset Grace Period (ms):",
        tk_var=global_state.motion_sequence_reset_grace_var,
        slider_from=0,
        slider_to=1000,
        slider_command=_update_motion_reset_grace,
        default_error_val=100,
        is_float=False
    )
    global_state.motion_sequence_reset_grace_var.set(selected_seq.reset_grace_period_ms)

    tk.Label(global_state.edit_motion_controls_frame, textvariable=global_state.motion_sequence_repetition_count_var,
             font=("Segoe UI", 10, "bold")).pack(side="top", anchor="w", padx=5, pady=5)
    global_state.motion_sequence_repetition_count_var.set(selected_seq.repetition_count)

    action_binding_frame = tk.Frame(global_state.edit_motion_controls_frame)
    action_binding_frame.pack(fill='x', padx=5, pady=5)
    tk.Label(action_binding_frame, text="Action Binding (Key/Click):").pack(side="left", anchor="w")
    action_entry = ttk.Entry(action_binding_frame, textvariable=global_state.motion_sequence_action_var, width=15,
                             font=("Segoe UI", 9))
    action_entry.pack(side="left", padx=2, fill='x', expand=True)
    global_state.motion_sequence_action_var.set(selected_seq.action_binding if selected_seq.action_binding else "")
    action_entry.bind("<Return>", lambda event: _update_motion_action_binding())

    set_action_button = tk.Button(action_binding_frame, text="Set Action", command=_update_motion_action_binding,
                                  font=("Segoe UI", 8))
    set_action_button.pack(side="left", padx=2)

    export_reps_frame = tk.LabelFrame(global_state.edit_motion_controls_frame, text="Repetition Export Settings",
                                      padx=5, pady=5)
    export_reps_frame.pack(fill='x', padx=5, pady=10)

    global_state.motion_sequence_export_reps_var.set(selected_seq.export_reps_to_file)
    export_toggle_checkbox = ttk.Checkbutton(export_reps_frame, text="Enable Export Repetitions to File",
                                             variable=global_state.motion_sequence_export_reps_var,
                                             command=_update_motion_export_reps_setting)
    export_toggle_checkbox.pack(anchor='w', pady=2)

    file_path_frame = tk.Frame(export_reps_frame)
    file_path_frame.pack(fill='x', pady=2)
    tk.Label(file_path_frame, text="Export File Path:").pack(side="left")
    file_path_entry = ttk.Entry(file_path_frame,
                                textvariable=global_state.motion_sequence_export_file_var)  # Corrected ttk.Entry constructor
    file_path_entry.pack(side="left", padx=2, fill='x', expand=True)
    global_state.motion_sequence_export_file_var.set(
        selected_seq.export_file_path if selected_seq.export_file_path else "")
    browse_button = tk.Button(file_path_frame, text="Browse", command=_browse_export_file, font=("Segoe UI", 8))
    browse_button.pack(side="left", padx=2)
    file_path_entry.bind("<Return>", lambda event: _update_motion_export_file_path())

    reset_file_button = tk.Button(export_reps_frame, text="Reset File Counter",
                                  command=_reset_motion_export_file_counter, font=("Segoe UI", 9), bg="lightblue")
    reset_file_button.pack(pady=5)

    rename_button = tk.Button(global_state.edit_motion_controls_frame, text="Rename", command=rename_selected_motion)
    rename_button.pack(pady=5)
    delete_button = tk.Button(global_state.edit_motion_controls_frame, text="Delete Motion",
                              command=delete_selected_motion,
                              bg="red", fg="white")
    delete_button.pack(pady=5)
    edit_positions_button = tk.Button(global_state.edit_motion_controls_frame, text="Edit Positions",
                                      command=edit_motion_positions)
    edit_positions_button.pack(pady=5)


def hide_edit_motion_controls():
    if global_state.edit_motion_controls_frame and global_state.edit_motion_controls_frame.winfo_exists():
        global_state.edit_motion_controls_frame.destroy()
    global_state.edit_motion_controls_frame = None


def update_motion_time_window(val):
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        global_state.saved_motion_sequences[global_state.selected_motion_sequence_index].time_window_ms = int(
            float(val))
        update_motion_sequences_display()


def _update_motion_reset_grace(val):
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        global_state.saved_motion_sequences[global_state.selected_motion_sequence_index].reset_grace_period_ms = int(
            float(val))
        update_motion_sequences_display()


def _update_motion_action_binding(event=None):
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        selected_seq = global_state.saved_motion_sequences[global_state.selected_motion_sequence_index]
        action_text = global_state.motion_sequence_action_var.get().strip()
        selected_seq.action_binding = action_text if action_text else None
        update_motion_sequences_display()
        print(f"Action for '{selected_seq.name}' set to: '{selected_seq.action_binding}'")


def _update_motion_export_reps_setting():
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        selected_seq = global_state.saved_motion_sequences[global_state.selected_motion_sequence_index]
        selected_seq.export_reps_to_file = global_state.motion_sequence_export_reps_var.get()
        update_motion_sequences_display()


def _update_motion_export_file_path(event=None):
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        selected_seq = global_state.saved_motion_sequences[global_state.selected_motion_sequence_index]
        file_path = global_state.motion_sequence_export_file_var.get().strip()
        selected_seq.export_file_path = file_path if file_path else None
        update_motion_sequences_display()


def _browse_export_file():
    if global_state.selected_motion_sequence_index != -1:
        file_path = tkinter.filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Select Repetition Export File"
        )
        if file_path:
            global_state.motion_sequence_export_file_var.set(file_path)
            _update_motion_export_file_path()


def _reset_motion_export_file_counter():
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        selected_seq = global_state.saved_motion_sequences[global_state.selected_motion_sequence_index]
        if selected_seq.export_file_path:
            if tkinter.messagebox.askyesno("Confirm Reset",
                                           f"Are you sure you want to reset the counter in '{selected_seq.export_file_path}' to 0?"):
                try:
                    with open(selected_seq.export_file_path, 'w') as f:
                        f.write("0")
                    tkinter.messagebox.showinfo("Reset Success", "Counter in file has been reset to 0.")
                except Exception as e:
                    tkinter.messagebox.showerror("Reset Error", f"Failed to reset file counter: {e}")
        else:
            tkinter.messagebox.showwarning("No File", "No export file path is set for this motion sequence.")


def rename_selected_motion():
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        current_name = global_state.saved_motion_sequences[global_state.selected_motion_sequence_index].name
        new_name = tkinter.simpledialog.askstring("Rename Motion", f"Enter new name for '{current_name}':",
                                                  initialvalue=current_name)
        if new_name and new_name.strip():
            global_state.saved_motion_sequences[global_state.selected_motion_sequence_index].name = new_name.strip()
            update_motion_sequences_display()
            global_state.motion_sequence_name_var.set(f"Editing: {new_name.strip()}")


def delete_selected_motion():
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        if tkinter.messagebox.askyesno("Delete Motion",
                                       f"Are you sure you want to delete '{global_state.saved_motion_sequences[global_state.selected_motion_sequence_index].name}'?"):
            del global_state.saved_motion_sequences[global_state.selected_motion_sequence_index]
            global_state.selected_motion_sequence_index = -1
            hide_edit_motion_controls()
            update_motion_sequences_display()


def edit_motion_positions():
    if global_state.selected_motion_sequence_index != -1 and global_state.selected_motion_sequence_index < len(
            global_state.saved_motion_sequences):
        selected_seq = global_state.saved_motion_sequences[global_state.selected_motion_sequence_index]
        edit_window = tk.Toplevel(global_state.root)
        edit_window.title(f"Edit Positions for {selected_seq.name}")
        tk.Label(edit_window, text="Select Positions for Motion", font=("Segoe UI", 12, "bold")).pack(pady=5)

        canvas_positions_editor = tk.Canvas(edit_window)
        scrollbar_positions_editor = ttk.Scrollbar(edit_window, orient="vertical",
                                                   command=canvas_positions_editor.yview)
        scrollable_frame_positions_editor = tk.Frame(canvas_positions_editor)

        scrollable_frame_positions_editor.bind(
            "<Configure>",
            lambda e: canvas_positions_editor.configure(
                scrollregion=canvas_positions_editor.bbox("all")
            )
        )
        canvas_positions_editor.create_window((0, 0), window=scrollable_frame_positions_editor, anchor="nw", width=380)
        canvas_positions_editor.configure(yscrollcommand=scrollbar_positions_editor.set)

        canvas_positions_editor.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar_positions_editor.pack(side="right", fill="y")

        selected_position_vars = []
        for pos in global_state.saved_positions:
            is_in_sequence = any(step.position_id == pos.id for step in selected_seq.steps)
            var = tk.BooleanVar(value=is_in_sequence)
            chk = ttk.Checkbutton(scrollable_frame_positions_editor, text=pos.name, variable=var)
            chk.pack(anchor="w", padx=5, pady=2)
            selected_position_vars.append((pos, var))

        def save_positions():
            if not tkinter.messagebox.askyesno("Confirm Save",
                                               "Are you sure you want to save these changes to the motion sequence positions?"):
                return

            new_motion_sequence_steps = []

            for saved_pos_in_global_list in global_state.saved_positions:
                for pos_var_tuple in selected_position_vars:
                    pos_obj, tk_var = pos_var_tuple

                    if tk_var.get() and pos_obj.id == saved_pos_in_global_list.id:
                        new_step = MotionSequenceStep(
                            position_id=pos_obj.id,
                            gyro_directions={'Pitch': 'any', 'Yaw': 'any', 'Roll': 'any'},
                            accel_directions={'X': 'any', 'Y': 'any', 'Z': 'any'}
                        )
                        new_motion_sequence_steps.append(new_step)
                        break

            selected_seq.steps = new_motion_sequence_steps
            selected_seq.current_position_index = 0
            selected_seq.last_match_time = None
            global_state.root.after(0, update_motion_sequences_display)
            edit_window.destroy()

        tk.Button(edit_window, text="Save", command=save_positions, bg="lightblue").pack(pady=10)
        tk.Button(edit_window, text="Cancel", command=edit_window.destroy).pack(pady=5)


def create_new_motion_sequence():
    name = tkinter.simpledialog.askstring("New Motion Sequence", "Enter name for new motion sequence:",
                                          initialvalue=f"Motion {len(global_state.saved_motion_sequences) + 1}")
    if name and name.strip():
        new_seq = MotionSequence(name.strip(), [], time_window_ms=1000, repetition_count=0, reset_grace_period_ms=100,
                                 action_binding=None, export_reps_to_file=False, export_file_path=None)
        global_state.saved_motion_sequences.append(new_seq)
        global_state.selected_motion_sequence_index = len(global_state.saved_motion_sequences) - 1
        update_motion_sequences_display()
        edit_motion_positions()