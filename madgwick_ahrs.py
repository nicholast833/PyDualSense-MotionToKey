# In madgwick_ahrs.py
import numpy as np
import global_state


# --- Quaternion & Euler Math Utilities ---

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
    Assumes a ZYX rotation order.
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


def quaternion_to_euler(q):
    """
    Converts a quaternion into Euler angles (pitch, yaw, roll) in degrees.
    This corresponds to rotations around the X, Y, and Z axes respectively.
    """
    w, x, y, z = q

    # Pitch (X-axis rotation)
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    pitch_x = np.degrees(np.arctan2(t0, t1))

    # Yaw (Y-axis rotation)
    t2 = +2.0 * (w * y - z * x)
    t2 = np.clip(t2, -1.0, 1.0)  # Clamp the value to avoid domain error with arcsin
    yaw_y = np.degrees(np.arcsin(t2))

    # Roll (Z-axis rotation)
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    roll_z = np.degrees(np.arctan2(t3, t4))

    return pitch_x, yaw_y, roll_z


# NEW FUNCTION
def quaternion_slerp(q1, q2, t):
    """
    Spherical linear interpolation between two quaternions.
    Smoothly transitions from q1 to q2 based on t (0.0 to 1.0).
    """
    q1 = np.array(q1, dtype=np.float64)
    q2 = np.array(q2, dtype=np.float64)

    # Normalize inputs to be safe
    norm1 = np.linalg.norm(q1)
    if norm1 > 0: q1 /= norm1

    norm2 = np.linalg.norm(q2)
    if norm2 > 0: q2 /= norm2

    dot = np.dot(q1, q2)

    # If the dot product is negative, slerp won't take the shortest path.
    # We can invert one quaternion to get the shorter path.
    if dot < 0.0:
        q2 = -q2
        dot = -dot

    # Threshold for when to use linear interpolation (if quaternions are very close)
    DOT_THRESHOLD = 0.9995
    if dot > DOT_THRESHOLD:
        result = q1 + t * (q2 - q1)
        return result / np.linalg.norm(result)

    # Standard slerp calculation
    theta_0 = np.arccos(dot)  # Angle between input quaternions
    theta = theta_0 * t  # Angle for interpolation
    sin_theta = np.sin(theta)
    sin_theta_0 = np.sin(theta_0)

    s0 = np.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0

    return (s0 * q1) + (s1 * q2)


# --- Madgwick Filter Class ---
class MadgwickAHRS:
    def __init__(self, sample_period=1 / 200, beta=0.1, zeta=0.0):
        self.sample_period = sample_period
        self.beta = beta
        self.zeta = zeta
        self.quaternion = np.array(global_state.DEFAULT_HOME_ORIENTATION, dtype=float)
        self.gyro_bias = np.array([0.0, 0.0, 0.0], dtype=float)

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

        if self.zeta > 0:
            is_stationary = abs(accel_magnitude - 1.0) < 0.1
            apply_correction = not global_state.correct_drift_when_still_enabled or is_stationary

            if apply_correction:
                error = np.cross(est_grav, accel_norm)
                self.gyro_bias += error * self.zeta * self.sample_period

        gyro = gyro - self.gyro_bias

        step = j.T.dot(f)
        if np.linalg.norm(step) > 0:
            step = step / np.linalg.norm(step)

        q_dot = 0.5 * quaternion_multiply(q, [0, gyro[0], gyro[1], gyro[2]])
        q_dot -= self.beta * step

        self.quaternion += q_dot * self.sample_period
        self.quaternion = self.quaternion / np.linalg.norm(self.quaternion)
