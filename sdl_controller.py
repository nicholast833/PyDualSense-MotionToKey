import math
import ctypes
import time
import sdl2
import sdl2.events
import global_state
import numpy as np
from madgwick_ahrs import MadgwickAHRS, quaternion_to_euler


# Simple Low-Pass Filter Class to smooth accelerometer data
class LowPassFilter:
    def __init__(self, alpha):
        self.alpha = alpha
        self.last_value = None  # Initialize to None

    def update(self, new_value):
        if self.last_value is None:  # First run, prime the filter
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

    # Auto-calibration phase
    with global_state.controller_lock:
        global_state.connection_status_text = "Calibrating... Keep controller still."
    print("Calibrating gyroscope... Keep the controller still for 2 seconds.")

    num_calibration_samples = 400
    gyro_sum = np.array([0.0, 0.0, 0.0])
    for _ in range(num_calibration_samples):
        gyro_buffer = (ctypes.c_float * 3)()
        sdl2.SDL_GameControllerGetSensorData(controller, sdl2.SDL_SENSOR_GYRO, gyro_buffer, 3)

        # FIX #1: Remap axes during calibration
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
        # Set the calibrated flag to True so the visualizer can start drawing
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
                button_name = BUTTON_MAP.get(event.cbutton.button)
                with global_state.controller_lock:
                    if global_state.is_mapping_home_button:
                        global_state.home_button_map = button_name
                        global_state.is_mapping_home_button = False
                        global_state.mapping_status_var.set(f"'{button_name}' set!")
                    elif button_name == global_state.home_button_map:
                        global_state.home_button_event.set()

        accel_buffer = (ctypes.c_float * 3)()
        gyro_buffer = (ctypes.c_float * 3)()
        sdl2.SDL_GameControllerGetSensorData(controller, sdl2.SDL_SENSOR_ACCEL, accel_buffer, 3)
        sdl2.SDL_GameControllerGetSensorData(controller, sdl2.SDL_SENSOR_GYRO, gyro_buffer, 3)

        # FIX #2: Remap axes for real-time data
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
                np.array([raw_ax, raw_ay, raw_az])
            )

            global_state.accel_data = [smooth_ax, smooth_ay, smooth_az]

            global_state.orientation_quaternion = list(madgwick_filter.quaternion)
            global_state.gyro_rotation = quaternion_to_euler(madgwick_filter.quaternion)

            if global_state.verbose_logging_enabled:
                log_message = (
                    f"Pitch: {global_state.gyro_rotation[0]:>6.2f}, "
                    f"Yaw: {global_state.gyro_rotation[1]:>6.2f}, "
                    f"Roll: {global_state.gyro_rotation[2]:>6.2f} | "
                    f"Bias: [{madgwick_filter.gyro_bias[0]:>7.4f}, "
                    f"{madgwick_filter.gyro_bias[1]:>7.4f}, "
                    f"{madgwick_filter.gyro_bias[2]:>7.4f}]"
                )
                global_state.log_message = log_message
                if global_state.log_to_console_enabled:
                    print(log_message)
            else:
                global_state.log_message = ""

        time.sleep(1.0 / sample_rate)

    if controller:
        sdl2.SDL_GameControllerClose(controller)
    sdl2.SDL_Quit()