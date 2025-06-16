# In config_manager.py
import json
import tkinter.filedialog
import tkinter.messagebox
import global_state
from models import SavedPosition, MotionSequence, MotionSequenceStep
import os
from position_manager_gui import update_saved_positions_display, hide_edit_position_controls
from motion_sequence_manager_gui import update_motion_sequences_display, hide_edit_motion_controls


# --- Helper: Read Reps From File ---
# Moved here temporarily from controller_interface, as needed by import.
# Will be moved back to controller_interface when all references are cleaned up.
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


def _serialize_position(pos):
    return {
        'id': pos.id,
        'name': pos.name,
        'recorded_points': [[list(g), list(a)] for g, a in pos.recorded_points],
        'padding_factor': pos.padding_factor,
        'detection_axes': pos.detection_axes,
        'custom_avg_gyro': list(pos.custom_avg_gyro) if pos.custom_avg_gyro is not None else None,
        'custom_avg_accel': list(pos.custom_avg_accel) if pos.custom_avg_accel is not None else None
    }


def _deserialize_position(data):
    recorded_points = [(tuple(g), tuple(a)) for g, a in data['recorded_points']]
    custom_avg_gyro = tuple(data['custom_avg_gyro']) if data.get('custom_avg_gyro') is not None else None
    custom_avg_accel = tuple(data['custom_avg_accel']) if data.get('custom_avg_accel') is not None else None

    return SavedPosition(recorded_points, data['name'], data['padding_factor'],
                         data['detection_axes'], _id=data['id'],
                         custom_avg_gyro=custom_avg_gyro, custom_avg_accel=custom_avg_accel)


def _serialize_motion_sequence(seq):
    serialized_steps = []
    for step in seq.steps:
        serialized_steps.append({
            'position_id': step.position_id,
            'gyro_directions': step.gyro_directions,
            'accel_directions': step.accel_directions
        })
    return {
        'name': seq.name,
        'steps': serialized_steps,
        'time_window_ms': seq.time_window_ms,
        'repetition_count': seq.repetition_count,
        'reset_grace_period_ms': seq.reset_grace_period_ms,
        'action_binding': seq.action_binding,
        'last_action_trigger_time': seq.last_action_trigger_time,
        'export_reps_to_file': seq.export_reps_to_file,
        'export_file_path': seq.export_file_path
    }


def _deserialize_motion_sequence(data, position_map):
    deserialized_steps = []
    if 'steps' in data:
        steps_data = data['steps']
        for step_data in steps_data:
            deserialized_steps.append(MotionSequenceStep(
                position_id=step_data['position_id'],
                gyro_directions=step_data.get('gyro_directions', {'Pitch': 'any', 'Yaw': 'any', 'Roll': 'any'}),
                accel_directions=step_data.get('accel_directions', {'X': 'any', 'Y': 'any', 'Z': 'any'})
            ))
    elif 'positions' in data:
        position_ids = data['positions']
        for pid in position_ids:
            pos_obj = position_map.get(pid)
            if pos_obj:
                deserialized_steps.append(MotionSequenceStep(
                    position_id=pos_obj.id,
                    gyro_directions={'Pitch': 'any', 'Yaw': 'any', 'Roll': 'any'},
                    accel_directions={'X': 'any', 'Y': 'any', 'Z': 'any'}
                ))
            else:
                print(
                    f"Warning: Position ID {pid} not found during motion sequence deserialization (from old config). Skipping step.")

    repetition_count_from_config = data.get('repetition_count', 0)

    seq = MotionSequence(data['name'], deserialized_steps, data['time_window_ms'],
                         repetition_count=repetition_count_from_config,
                         reset_grace_period_ms=data.get('reset_grace_period_ms', 0),
                         action_binding=data.get('action_binding', None),
                         last_action_trigger_time=data.get('last_action_trigger_time', None),
                         export_reps_to_file=data.get('export_reps_to_file', False),
                         export_file_path=data.get('export_file_path', None))

    # NEW LOGIC: Read initial count from file if export is enabled for this sequence
    if seq.export_reps_to_file and seq.export_file_path:
        initial_file_count = _read_reps_from_file(seq.export_file_path)
        seq.repetition_count = initial_file_count  # Overwrite with file content
        print(f"DEBUG: Initializing '{seq.name}' rep count from file: {initial_file_count}")

    return seq


def export_config():
    filepath = tkinter.filedialog.asksaveasfilename(defaultextension=".cfg",
                                                    filetypes=[("Config Files", "*.cfg"), ("JSON Files", "*.json"),
                                                               ("All Files", "*.*")])
    if filepath:
        config_data = {
            'positions': [_serialize_position(pos) for pos in global_state.saved_positions],
            'sequences': [_serialize_motion_sequence(seq) for seq in global_state.saved_motion_sequences]
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(config_data, f, indent=4)
            print(f"Config exported to {filepath}")
            global_state.connection_status_var.set("Config Exported!")
            global_state.root.after(2000, lambda: global_state.connection_status_var.set("Controller Connected!"))
        except Exception as e:
            tkinter.messagebox.showerror("Export Error", f"Failed to export config: {e}")
            print(f"Error exporting config: {e}")


def import_config():
    filepath = tkinter.filedialog.askopenfilename(defaultextension=".cfg",
                                                  filetypes=[("Config Files", "*.cfg"), ("JSON Files", "*.json"),
                                                             ("All Files", "*.*")])
    if filepath:
        if tkinter.messagebox.askyesno("Confirm Import",
                                       "This will clear all current positions and motions. Continue?"):
            global_state.is_initializing_config = True  # Set flag during import
            try:
                with open(filepath, 'r') as f:
                    config_data = json.load(f)

                global_state.saved_positions.clear()
                global_state.saved_motion_sequences.clear()

                position_map = {}
                for pos_data in config_data.get('positions', []):
                    pos_obj = _deserialize_position(pos_data)
                    global_state.saved_positions.append(pos_obj)
                    position_map[pos_obj.id] = pos_obj

                for seq_data in config_data.get('sequences', []):
                    # Repetition count is now read from file inside deserialize_motion_sequence
                    seq_obj = _deserialize_motion_sequence(seq_data, position_map)
                    global_state.saved_motion_sequences.append(seq_obj)

                global_state.root.after(0, update_saved_positions_display)
                global_state.root.after(0, update_motion_sequences_display)
                global_state.root.after(0, hide_edit_position_controls)
                global_state.root.after(0, hide_edit_motion_controls)

                print(f"Config imported from {filepath}")
                global_state.connection_status_var.set("Config Imported!")
                global_state.root.after(2000, lambda: global_state.connection_status_var.set("Controller Connected!"))

            except Exception as e:
                tkinter.messagebox.showerror("Import Error", f"Failed to import config: {e}")
                print(f"Error importing config: {e}")
            finally:  # Ensure flag is reset even on error
                global_state.is_initializing_config = False  # Reset flag after importeee