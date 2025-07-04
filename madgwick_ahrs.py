# In madgwick_ahrs.py
import numpy as np
import global_state


def quaternion_to_euler(q):
    """Converts a quaternion to Euler angles (in degrees)."""
    w, x, y, z = q
    sinp = 2 * (w * x + y * z)
    cosp = 1 - 2 * (x * x + y * y)
    pitch = np.degrees(np.arctan2(sinp, cosp))
    siny_cosp = 2 * (w * y - z * x)
    if np.abs(siny_cosp) >= 1:
        yaw = np.degrees(np.copysign(np.pi / 2, siny_cosp))
    else:
        yaw = np.degrees(np.arcsin(siny_cosp))
    sinr_cosp = 2 * (w * z + x * y)
    cosr_cosp = 1 - 2 * (y * y + z * z)
    roll = np.degrees(np.arctan2(sinr_cosp, cosr_cosp))
    return pitch, yaw, roll


class MadgwickAHRS:
    def __init__(self, sample_period=1 / 200, beta=0.1, zeta=0.0):
        self.sample_period = sample_period
        self.beta = beta
        self.zeta = zeta  # Gyro bias correction gain
        self.quaternion = np.array(global_state.DEFAULT_HOME_ORIENTATION)
        self.gyro_bias = np.array([0.0, 0.0, 0.0])

    def update_imu(self, gyro, accel):
        """
        Update the filter with new gyroscope and accelerometer data.
        :param gyro: A 3-element numpy array of gyroscope data (rad/s)
        :param accel: A 3-element numpy array of accelerometer data (g)
        """
        q = self.quaternion

        accel_magnitude = np.linalg.norm(accel)
        if accel_magnitude == 0:
            return

        # Normalize accelerometer measurement
        accel_norm = accel / accel_magnitude

        # Estimated direction of gravity
        est_grav = np.array([
            2 * (q[1] * q[3] - q[0] * q[2]),
            2 * (q[0] * q[1] + q[2] * q[3]),
            q[0] ** 2 - q[1] ** 2 - q[2] ** 2 + q[3] ** 2
        ])

        # Objective function (error between estimated and measured gravity)
        f = est_grav - accel_norm

        # Jacobian
        j = np.array([
            [-2 * q[2], 2 * q[3], -2 * q[0], 2 * q[1]],
            [2 * q[1], 2 * q[0], 2 * q[3], 2 * q[2]],
            [0, -4 * q[1], -4 * q[2], 0]
        ])

        # Gyroscope bias correction
        if self.zeta > 0:
            # Check if smart correction is enabled
            is_stationary = abs(accel_magnitude - 1.0) < 0.1  # Threshold for 1g
            apply_correction = not global_state.correct_drift_when_still_enabled or is_stationary

            if apply_correction:
                error = np.cross(est_grav, accel_norm)
                self.gyro_bias += error * self.zeta * self.sample_period

        # Subtract the estimated gyro bias
        gyro = gyro - self.gyro_bias

        # Compute rate of change of quaternion
        step = j.T.dot(f)
        if np.linalg.norm(step) > 0:
            step = step / np.linalg.norm(step)

        q_dot = 0.5 * self.quaternion_multiply(q, [0, gyro[0], gyro[1], gyro[2]])
        q_dot -= self.beta * step

        # Integrate to yield quaternion
        self.quaternion += q_dot * self.sample_period
        self.quaternion = self.quaternion / np.linalg.norm(self.quaternion)

    @staticmethod
    def quaternion_multiply(q1, q2):
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        return np.array([w, x, y, z])