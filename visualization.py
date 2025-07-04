# In visualization.py
import tkinter as tk
from pyopengltk import OpenGLFrame
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL import GLUT
import global_state
import numpy as np


def draw_text_3d(x, y, z, text, is_hit):
    """Renders a 3D text label at a given position."""
    glPushMatrix()
    try:
        glDisable(GL_LIGHTING)
        if is_hit:
            glColor3f(1.0, 1.0, 0.0)
        else:
            glColor3f(1.0, 1.0, 1.0)

        glRasterPos3f(x, y + 0.15, z)
        for char in text:
            GLUT.glutBitmapCharacter(GLUT.GLUT_BITMAP_HELVETICA_18, ord(char))
    finally:
        glEnable(GL_LIGHTING)
        glPopMatrix()


class VisFrame(OpenGLFrame):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.quadric = None

    def initgl(self):
        # FIX #1: Prevent division-by-zero if the frame has no height yet.
        if self.height <= 0:
            return

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (self.width / self.height), 0.1, 50.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION, [0, 1, 1, 0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def redraw(self):
        """Redraw the scene with defensive state management."""
        self.tkMakeCurrent()
        if self.quadric is None:
            self.quadric = gluNewQuadric()

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        with global_state.controller_lock:
            cam_orbit_x, cam_orbit_y = global_state.camera_orbit_x, global_state.camera_orbit_y
            cam_roll, cam_zoom = global_state.camera_roll, global_state.camera_zoom
            gyro_pitch, gyro_yaw, gyro_roll = global_state.gyro_rotation
            dimensions = global_state.object_dimensions
            ref_points = list(global_state.reference_points)
            tip_pos = global_state.controller_tip_position
            show_labels = global_state.show_ref_point_labels

        glPushMatrix()
        try:
            glTranslatef(0, 0, cam_zoom)
            glRotatef(cam_orbit_x, 1, 0, 0)
            glRotatef(cam_orbit_y, 0, 1, 0)
            glRotatef(cam_roll, 0, 0, 1)

            self.draw_reference_points(ref_points, show_labels)
            self.draw_controller_tip(tip_pos)

            glPushMatrix()
            try:
                glRotatef(gyro_pitch, 1, 0, 0)
                glRotatef(gyro_yaw, 0, 1, 0)
                glRotatef(gyro_roll, 0, 0, 1)
                self.draw_object(dimensions)
            finally:
                glPopMatrix()

        finally:
            glPopMatrix()

        self.tkSwapBuffers()

    def draw_object(self, dimensions):
        w, h, d = dimensions
        w /= 2.0
        h /= 2.0
        d /= 2.0

        def draw_prism(vertices, faces, outline_color=(0.8, 0.8, 0.8)):
            # FIX #2: Use try/finally to guarantee glEnd is called.
            try:
                for face_indices, color in faces:
                    try:
                        glBegin(GL_QUADS)
                        glColor3fv(color)
                        glNormal3fv([0, 0, 1])
                        for index in face_indices:
                            glVertex3fv(vertices[index])
                    finally:
                        glEnd()
                glLineWidth(1.5)
                for face_indices, color in faces:
                    try:
                        glBegin(GL_LINE_LOOP)
                        glColor3fv(outline_color)
                        for index in face_indices:
                            glVertex3fv(vertices[index])
                    finally:
                        glEnd()
            except Exception as e:
                print(f"Error drawing prism: {e}")


        body_w, body_h, body_d = w, h * 0.5, d
        body_vertices = np.array([[-body_w, -body_h, -body_d], [body_w, -body_h, -body_d], [body_w, -body_h, body_d], [-body_w, -body_h, body_d],
                                  [-body_w, body_h, -body_d], [body_w, body_h, -body_d], [body_w, body_h, body_d], [-body_w, body_h, body_d]])
        body_faces = [([4, 7, 6, 5], [0.8, 0.8, 0.8]), ([0, 1, 2, 3], [0.8, 0.8, 0.8]), ([0, 1, 5, 4], [0.9, 0.9, 0.9]),
                      ([3, 2, 6, 7], [0.7, 0.7, 0.7]), ([1, 2, 6, 5], [0.9, 0.9, 0.9]), ([0, 3, 7, 4], [0.7, 0.7, 0.7])]
        draw_prism(body_vertices, body_faces)

        h_w, h_h, h_d = w * 0.24, h * 0.49, d * 1.83
        lx_off, ly_off, lz_off = -w * 0.75, h * 0, d * -0.7
        left_handle_vertices = np.array(
            [[-h_w + lx_off, -h_h + ly_off, -h_d + lz_off], [h_w + lx_off, -h_h + ly_off, -h_d + lz_off],
             [h_w + lx_off, -h_h + ly_off, h_d + lz_off], [-h_w + lx_off, -h_h + ly_off, h_d + lz_off],
             [-h_w + lx_off, h_h + ly_off, -h_d + lz_off], [h_w + lx_off, h_h + ly_off, -h_d + lz_off],
             [h_w + lx_off, h_h + ly_off, h_d + lz_off], [-h_w + lx_off, h_h + ly_off, h_d + lz_off]])
        handle_color = [0.2, 0.2, 0.2]
        handle_faces = [([4, 7, 6, 5], handle_color), ([0, 1, 2, 3], handle_color), ([0, 1, 5, 4], handle_color),
                        ([3, 2, 6, 7], handle_color), ([1, 2, 6, 5], handle_color), ([0, 3, 7, 4], handle_color)]
        draw_prism(left_handle_vertices, handle_faces)

        rx_off = w * 0.75
        right_handle_vertices = np.array(
            [[-h_w + rx_off, -h_h + ly_off, -h_d + lz_off], [h_w + rx_off, -h_h + ly_off, -h_d + lz_off],
             [h_w + rx_off, -h_h + ly_off, h_d + lz_off], [-h_w + rx_off, -h_h + ly_off, h_d + lz_off],
             [-h_w + rx_off, h_h + ly_off, -h_d + lz_off], [h_w + rx_off, h_h + ly_off, -h_d + lz_off],
             [h_w + rx_off, h_h + ly_off, h_d + lz_off], [-h_w + rx_off, h_h + ly_off, h_d + lz_off]])
        draw_prism(right_handle_vertices, handle_faces)

    def draw_reference_points(self, points, show_labels):
        # FIX #2: Use try/finally to guarantee glPopMatrix is called.
        for point in points:
            glPushMatrix()
            try:
                x, y, z = point['position']
                glTranslatef(x, y, z)
                if point['hit']:
                    glColor3f(1.0, 1.0, 0.0)
                else:
                    glColor3f(0.0, 0.8, 0.8)
                gluSphere(self.quadric, 0.05, 32, 32)
                if show_labels:
                    draw_text_3d(x, y, z, point['id'], point['hit'])
            finally:
                glPopMatrix()

    def draw_controller_tip(self, position):
        # FIX #2: Use try/finally to guarantee glPopMatrix and glEnd are called.
        glPushMatrix()
        try:
            glTranslatef(position[0], position[1], position[2])
            glDisable(GL_LIGHTING)
            glLineWidth(2.0)
            try:
                glBegin(GL_LINES)
                glColor3f(1, 0, 0)
                glVertex3f(-0.03, 0, 0)
                glVertex3f(0.03, 0, 0)
                glColor3f(0, 1, 0)
                glVertex3f(0, -0.03, 0)
                glVertex3f(0, 0.03, 0)
                glColor3f(0, 0, 1)
                glVertex3f(0, 0, -0.03)
                glVertex3f(0, 0, 0.03)
            finally:
                glEnd()
            glEnable(GL_LIGHTING)
        finally:
            glPopMatrix()