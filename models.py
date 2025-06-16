import uuid
import math


class SavedPosition:
    def __init__(self, recorded_points, name, padding_factor, detection_axes=None, _id=None,
                 custom_avg_gyro=None, custom_avg_accel=None):
        self.id = _id if _id is not None else str(uuid.uuid4())
        self.recorded_points = recorded_points
        self.name = name
        self.padding_factor = padding_factor

        if detection_axes is None:
            self.detection_axes = {'Pitch': True, 'Yaw': True, 'Roll': True,
                                   'X': True, 'Y': True, 'Z': True}
        else:
            self.detection_axes = detection_axes

        if recorded_points:
            total_gyro_pitch = sum(p[0][0] for p in recorded_points)
            total_gyro_yaw = sum(p[0][1] for p in recorded_points)
            total_gyro_roll = sum(p[0][2] for p in recorded_points)
            total_accel_x = sum(p[1][0] for p in recorded_points)
            total_accel_y = sum(p[1][1] for p in recorded_points)
            total_accel_z = sum(p[1][2] for p in recorded_points)
            num_recorded = len(recorded_points)
            self.avg_gyro = (
                total_gyro_pitch / num_recorded,
                total_gyro_yaw / num_recorded,
                total_gyro_roll / num_recorded
            )
            self.avg_accel = (
                total_accel_x / num_recorded,
                total_accel_y / num_recorded,
                total_accel_z / num_recorded
            )
            min_p = min(p[0][0] for p in recorded_points)
            max_p = max(p[0][0] for p in recorded_points)
            min_y = min(p[0][1] for p in recorded_points)
            max_y = max(p[0][1] for p in recorded_points)
            min_r = min(p[0][2] for p in recorded_points)
            max_r = max(p[0][2] for p in recorded_points)
            min_x = min(p[1][0] for p in recorded_points)
            max_x = max(p[1][0] for p in recorded_points)
            min_y_accel = min(p[1][1] for p in recorded_points)
            max_y_accel = max(p[1][1] for p in recorded_points)
            min_z = min(p[1][2] for p in recorded_points)
            max_z = max(p[1][2] for p in recorded_points)
            self.raw_min_gyro = (min_p, min_y, min_r)
            self.raw_max_gyro = (max_p, max_y, max_r)
            self.raw_min_accel = (min_x, min_y_accel, min_z)
            self.raw_max_accel = (max_x, max_y_accel, max_z)
        else:
            self.avg_gyro = (0, 0, 0)
            self.avg_accel = (0, 0, 0)
            self.raw_min_gyro = self.raw_max_gyro = (0, 0, 0)
            self.raw_min_accel = self.raw_max_accel = (0, 0, 0)

        self.custom_avg_gyro = custom_avg_gyro
        self.custom_avg_accel = custom_avg_accel

    def get_effective_ranges(self):
        center_gyro = self.custom_avg_gyro if self.custom_avg_gyro is not None else self.avg_gyro
        center_accel = self.custom_avg_accel if self.custom_avg_accel is not None else self.avg_accel

        spread_gyro_p = self.raw_max_gyro[0] - self.raw_min_gyro[0]
        spread_gyro_y = self.raw_max_gyro[1] - self.raw_min_gyro[1]
        spread_gyro_r = self.raw_max_gyro[2] - self.raw_min_gyro[2]
        spread_accel_x = self.raw_max_accel[0] - self.raw_min_accel[0]
        spread_accel_y = self.raw_max_accel[1] - self.raw_min_accel[1]
        spread_accel_z = self.raw_max_accel[2] - self.raw_min_accel[2]

        effective_min_gyro = (
            center_gyro[0] - (spread_gyro_p / 2) - self.padding_factor,
            center_gyro[1] - (spread_gyro_y / 2) - self.padding_factor,
            center_gyro[2] - (spread_gyro_r / 2) - self.padding_factor
        )
        effective_max_gyro = (
            center_gyro[0] + (spread_gyro_p / 2) + self.padding_factor,
            center_gyro[1] + (spread_gyro_y / 2) + self.padding_factor,
            center_gyro[2] + (spread_gyro_r / 2) + self.padding_factor
        )
        effective_min_accel = (
            center_accel[0] - (spread_accel_x / 2) - self.padding_factor,
            center_accel[1] - (spread_accel_y / 2) - self.padding_factor,
            center_accel[2] - (spread_accel_z / 2) - self.padding_factor
        )
        effective_max_accel = (
            center_accel[0] + (spread_accel_x / 2) + self.padding_factor,
            center_accel[1] + (spread_accel_y / 2) + self.padding_factor,
            center_accel[2] + (spread_accel_z / 2) + self.padding_factor
        )

        return effective_min_gyro, effective_max_gyro, effective_min_accel, effective_max_accel

    def __repr__(self):
        display_gyro = self.custom_avg_gyro if self.custom_avg_gyro is not None else self.avg_gyro
        display_accel = self.custom_avg_accel if self.custom_avg_accel is not None else self.avg_accel
        return (
            f"Pos: {self.name} | G:{display_gyro[0]:.0f},Y:{display_gyro[1]:.0f},R:{display_gyro[2]:.0f} "
            f"| A:{display_accel[0]:.1f},Y:{display_accel[1]:.1f},Z:{display_accel[2]:.1f}"
        )


class MotionSequenceStep:
    def __init__(self, position_id, gyro_directions=None, accel_directions=None):
        self.position_id = position_id

        if gyro_directions is None:
            self.gyro_directions = {'Pitch': 'any', 'Yaw': 'any', 'Roll': 'any'}
        else:
            self.gyro_directions = gyro_directions

        if accel_directions is None:
            self.accel_directions = {'X': 'any', 'Y': 'any', 'Z': 'any'}
        else:
            self.accel_directions = accel_directions

    def __repr__(self):
        return (f"Step(PosID:{self.position_id[:4]}..,"
                f" G:{self.gyro_directions['Pitch'][0]}{self.gyro_directions['Yaw'][0]}{self.gyro_directions['Roll'][0]},"
                f" A:{self.accel_directions['X'][0]}{self.accel_directions['Y'][0]}{self.accel_directions['Z'][0]})")


class MotionSequence:
    def __init__(self, name, steps, time_window_ms, repetition_count=0, reset_grace_period_ms=0, action_binding=None, last_action_trigger_time=None, export_reps_to_file=False, export_file_path=None):
        self.name = name
        self.steps = steps
        self.time_window_ms = time_window_ms
        self.repetition_count = repetition_count
        self.current_position_index = 0
        self.last_match_time = None
        self.reset_grace_period_ms = reset_grace_period_ms
        self.non_match_start_time = None
        self.action_binding = action_binding
        self.last_action_trigger_time = None
        self.export_reps_to_file = export_reps_to_file
        self.export_file_path = export_file_path
        self.is_completed_this_frame = False


    def __repr__(self):
        return (f"Motion: {self.name} | Steps: {len(self.steps)} | Time: {self.time_window_ms}ms "
                f"| Grace: {self.reset_grace_period_ms}ms | Reps: {self.repetition_count}")


# --- Helper Functions (can stay here or be moved to utils.py if it grows) ---
def euclidean_distance(point1, point2):
    if len(point1) != 3 or len(point2) != 3:
        raise ValueError("Points must be 3-dimensional for Euclidean distance calculation.")
    return math.sqrt(
        (point1[0] - point2[0]) ** 2 +
        (point1[1] - point2[1]) ** 2 +
        (point1[2] - point2[2]) ** 2
    )