import tkinter as tk
from tkinter import ttk
import tkinter.messagebox
import global_state


# --- Generic function to create numeric slider/entry controls ---
def create_numeric_slider_control(parent_frame, label_text, tk_var, slider_from, slider_to, slider_command,
                                  default_error_val, is_float=True):
    control_frame = tk.Frame(parent_frame)
    control_frame.pack(fill="x", padx=5, pady=5)

    if label_text:
        tk.Label(control_frame, text=label_text).pack(side="top", anchor="w")

    slider = ttk.Scale(control_frame, from_=slider_from, to=slider_to, orient="horizontal",
                       command=slider_command, variable=tk_var)
    slider.pack(fill="x", padx=5, pady=2)

    entry = ttk.Entry(control_frame, textvariable=tk_var, width=15, justify='center', font=("Segoe UI", 9))
    entry.pack(pady=2)

    def on_entry_return(event):
        try:
            val_str = entry.get()
            if is_float:
                new_val = float(val_str)
            else:
                new_val = int(val_str)

            if not (slider_from <= new_val <= slider_to):
                raise ValueError("Out of range")

            if is_float:
                tk_var.set(round(new_val, 3))
            else:
                tk_var.set(new_val)

            slider_command(tk_var.get())

        except (ValueError, TypeError):
            tk_var.set(default_error_val)
            slider_command(tk_var.get())
            tkinter.messagebox.showerror("Invalid Input",
                                         f"Please enter a valid number within {slider_from}-{slider_to}. Reset to {default_error_val}.")

        slider.set(tk_var.get())

    entry.bind("<Return>", on_entry_return)
    return slider, entry


# --- GUI Highlight Update Function (Runs on Main Thread via root.after) ---
def update_highlight_on_gui(matched_index):
    for i, label in enumerate(global_state.saved_position_labels):
        if not label.winfo_exists():
            continue
        try:
            if i == matched_index:
                label.config(bg="lightgreen", fg="black")
            elif i == global_state.selected_position_index:
                label.config(bg="lightblue", fg="black")
            else:
                label.config(bg="SystemButtonFace", fg="black")
        except tk.TclError:
            print(f"Tkinter error: Label at index {i} was destroyed during highlight update. Skipping.")