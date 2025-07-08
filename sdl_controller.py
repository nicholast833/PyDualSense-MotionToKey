import math
import ctypes
import time
import sdl2
import sdl2.events
import global_state
import numpy as np
from madgwick_ahrs import MadgwickAHRS, quaternion_to_euler, euler_to_quaternion, rotate_point_by_quaternion, \
    quaternion_slerp


# Simple Low-Pass Filter Class to smooth accelerometer data
class LowPassFilter:
    def __init__(self, alpha):
        self.alpha = alpha
        self.last_value = None

    def update(self, new_value):
        if self.last_value is None:
            self.last_value = new_value
        else:
            self.last_value = self.alpha * new_value + (1.0 - self.alpha) * self.last_value
        return self.last_value

    def set_alpha(self, alpha):
        self.alpha = alpha


BUTTON_MAP = {
    sdl2.SDL_CONTROLLER_BUTTON_A: 'a', sdl2.SDL_CONTROLLER_BUTTON_B: 'b',
    sdl2.SDL_CONTROLLER_BUTTON_X: 'x', sdl2.SDL_CONTROLLER_BUTTON_Y: 'y',
    sdl2.SDL_CONTROLLER_BUTTON_BACK: 'back', sdl2.SDL_CONTROLLER_BUTTON_GUIDE: 'guide',
    sdl2.SDL_CONTROLLER_BUTTON_START: 'start', sdl2.SDL_CONTROLLER_BUTTON_LEFTSTICK: 'leftstick',
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSTICK: 'rightstick', sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER: 'leftshoulder',
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: 'rightshoulder', sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP: 'dpup',
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN: 'dpdown', sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT: 'dpleft',
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT: 'dpright',
    sdl2.SDL_CONTROLLER_BUTTON_MISC1: 'misc1',  # PS button on DualSense
    sdl2.SDL_CONTROLLER_BUTTON_PADDLE1: 'paddle1',
    sdl2.SDL_CONTROLLER_BUTTON_PADDLE2: 'paddle2',
    sdl2.SDL_CONTROLLER_BUTTON_PADDLE3: 'paddle3',
    sdl2.SDL_CONTROLLER_BUTTON_PADDLE4: 'paddle4',
    sdl2.SDL_CONTROLLER_BUTTON_TOUCHPAD: 'touchpad',
}


def poll_controller_data():
    controller = None
    sample_rate = 200.0
    try:
        sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER | sdl2.SDL_INIT_SENSOR | sdl2.SDL_INIT_EVENTS)
        for i in range(sdl2.SDL_NumJoysticks()):
            if sdl2.SDL_IsGameController(i):
                controller = sdl2.SDL_GameControllerOpen(i)
                break
        if not controller:
            global_state.connection_status_text = "Controller not found."
            return
        sdl2.SDL_GameControllerSetSensorEnabled(controller, sdl2.SDL_SENSOR_GYRO, True)
        sdl2.SDL_GameControllerSetSensorEnabled(controller, sdl2.SDL_SENSOR_ACCEL, True)
    except Exception as e:
        print(f"Error initializing SDL or controller: {e}")
        return

    with global_state.controller_lock:
        global_state.connection_status_text = "Calibrating... Keep controller still."
    print("Calibrating gyroscope... Keep the controller still for 2 seconds.")

    num_calibration_samples = 400
    gyro_sum = np.array([0.0, 0.0, 0.0])
    for _ in range(num_calibration_samples):
        gyro_buffer = (ctypes.c_float * 3)()
        sdl2.SDL_GameControllerGetSensorData(controller, sdl2.SDL_SENSOR_GYRO, gyro_buffer, 3)
        gyro_sum += np.array([gyro_buffer[0], -gyro_buffer[1], -gyro_buffer[2]])
        time.sleep(1.0 / sample_rate)

    initial_bias = gyro_sum / num_calibration_samples
    print(f"Calibration complete. Initial bias set to: {initial_bias}")

    madgwick_filter = MadgwickAHRS(sample_period=(1.0 / sample_rate), beta=global_state.beta_gain,
                                   zeta=global_state.drift_correction_gain)
    madgwick_filter.gyro_bias = initial_bias

    accel_lpf_x = LowPassFilter(alpha=global_state.accelerometer_smoothing)
    accel_lpf_y = LowPassFilter(alpha=global_state.accelerometer_smoothing)
    accel_lpf_z = LowPassFilter(alpha=global_state.accelerometer_smoothing)

    with global_state.controller_lock:
        global_state.is_controller_connected = True
        global_state.connection_status_text = f"Connected: {sdl2.SDL_GameControllerName(controller).decode()}"
        global_state.is_calibrated = True

    last_time = time.monotonic()
    event = sdl2.events.SDL_Event()

    while global_state.running:
        current_time = time.monotonic()
        dt = current_time - last_time
        if dt <= 0:
            time.sleep(0.001)
            continue
        last_time = current_time
        madgwick_filter.sample_period = dt

        while sdl2.events.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
                button_name = BUTTON_MAP.get(event.cbutton.button, f"Button {event.cbutton.button}")

                with global_state.controller_lock:
                    target = global_state.mapping_target
                    if target:
                        if target == 'home':
                            global_state.home_button_map = button_name
                            if global_state.mapping_home_status_var:
                                global_state.mapping_home_status_var.set(f"Set to: '{button_name}'")
                        elif target == 'stockpile':
                            global_state.execute_stockpiled_action_button = button_name
                            if global_state.mapping_stockpile_status_var:
                                global_state.mapping_stockpile_status_var.set(f"Set to: '{button_name}'")

                        global_state.mapping_target = None
                    else:
                        if button_name and button_name == global_state.home_button_map:
                            global_state.home_button_event.set()
                        elif button_name and button_name == global_state.execute_stockpiled_action_button:
                            global_state.execute_stockpiled_event.set()

        accel_buffer = (ctypes.c_float * 3)()
        gyro_buffer = (ctypes.c_float * 3)()
        sdl2.SDL_GameControllerGetSensorData(controller, sdl2.SDL_SENSOR_ACCEL, accel_buffer, 3)
        sdl2.SDL_GameControllerGetSensorData(controller, sdl2.SDL_SENSOR_GYRO, gyro_buffer, 3)

        raw_ax, raw_ay, raw_az = accel_buffer[0], -accel_buffer[1], -accel_buffer[2]
        raw_gx, raw_gy, raw_gz = gyro_buffer[0], -gyro_buffer[1], -gyro_buffer[2]

        if global_state.recenter_event.is_set():
            madgwick_filter.quaternion = np.array(global_state.DEFAULT_HOME_ORIENTATION)
            madgwick_filter.gyro_bias = initial_bias
            global_state.recenter_event.clear()

        if global_state.go_to_home_event.is_set():
            with global_state.controller_lock:
                if global_state.home_position and 'orientation' in global_state.home_position:
                    madgwick_filter.quaternion = np.array(global_state.home_position['orientation'])
                    madgwick_filter.gyro_bias = initial_bias
            global_state.go_to_home_event.clear()

        with global_state.controller_lock:
            if global_state.pause_sensor_updates_enabled:
                time.sleep(0.01)
                continue

            madgwick_filter.beta = global_state.beta_gain
            madgwick_filter.zeta = global_state.drift_correction_gain

            smoothing_alpha = global_state.accelerometer_smoothing
            accel_lpf_x.set_alpha(smoothing_alpha)
            accel_lpf_y.set_alpha(smoothing_alpha)
            accel_lpf_z.set_alpha(smoothing_alpha)

            smooth_ax = accel_lpf_x.update(raw_ax)
            smooth_ay = accel_lpf_y.update(raw_ay)
            smooth_az = accel_lpf_z.update(raw_az)

            global_state.raw_gyro = [raw_gx, raw_gy, raw_gz]
            global_state.raw_accel = [raw_ax, raw_ay, raw_az]

            madgwick_filter.update_imu(
                np.array([raw_gx, raw_gy, raw_gz]),
                np.array([smooth_ax, smooth_ay, smooth_az])  # MODIFIED: Use smoothed accel data
            )

            # --- AXIS LOCKING LOGIC (MODIFIED) ---
            unfiltered_pitch, unfiltered_yaw, unfiltered_roll = quaternion_to_euler(madgwick_filter.quaternion)

            # Determine the target orientation based on which axes are tracked
            target_pitch = unfiltered_pitch if global_state.track_pitch else global_state.lock_pitch_to
            target_yaw = unfiltered_yaw if global_state.track_yaw else global_state.lock_yaw_to
            target_roll = unfiltered_roll if global_state.track_roll else global_state.lock_roll_to

            # Detect unintended movement on locked axes
            global_state.unintended_movement_detected = False
            if not global_state.track_pitch and abs(unfiltered_pitch - global_state.lock_pitch_to) > 1.5:
                global_state.unintended_movement_detected = True
            if not global_state.track_yaw and abs(unfiltered_yaw - global_state.lock_yaw_to) > 1.5:
                global_state.unintended_movement_detected = True
            if not global_state.track_roll and abs(unfiltered_roll - global_state.lock_roll_to) > 1.5:
                global_state.unintended_movement_detected = True

            # Convert the desired final angles back to a target quaternion
            target_q = euler_to_quaternion(target_pitch, target_yaw, target_roll)

            # Instead of a hard overwrite, smoothly interpolate towards the target quaternion.
            # This eliminates jitter caused by snapping the orientation.
            slerp_factor = global_state.axis_lock_strength
            corrected_q = quaternion_slerp(madgwick_filter.quaternion, target_q, slerp_factor)

            # Update the filter's state with the smoothly corrected orientation
            madgwick_filter.quaternion = corrected_q
            global_state.orientation_quaternion = list(corrected_q)

            # Update the last known good values and the UI display from the corrected state
            final_pitch, final_yaw, final_roll = quaternion_to_euler(corrected_q)
            global_state.gyro_rotation = [final_pitch, final_yaw, final_roll]
            global_state.last_good_pitch = final_pitch
            global_state.last_good_yaw = final_yaw
            global_state.last_good_roll = final_roll

            # Calculate tip position based on the FINAL corrected orientation
            offset = global_state.distance_offset
            tip_pos = rotate_point_by_quaternion(np.array([0, 0, offset]), corrected_q)
            global_state.controller_tip_position = tip_pos

        time.sleep(1.0 / sample_rate)

    if controller:
        sdl2.SDL_GameControllerClose(controller)
    sdl2.SDL_Quit()