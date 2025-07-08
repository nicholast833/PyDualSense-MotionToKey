from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
import global_state
import os
import threading
import time
import random
import sys

# Conditionally import winsound for Windows-specific sound playback
if sys.platform == "win32":
    import winsound

class ActionExecutor:
    def __init__(self):
        """
        Initializes the ActionExecutor.
        Controllers for keyboard and mouse are initialized lazily on first use
        to prevent any startup delay.
        """
        self.keyboard = None
        self.mouse = None
        # Maps string representations to pynput's special Key objects
        self.special_keys = {
            'alt': Key.alt, 'alt_l': Key.alt_l, 'alt_r': Key.alt_r,
            'backspace': Key.backspace, 'caps_lock': Key.caps_lock,
            'cmd': Key.cmd, 'cmd_l': Key.cmd_l, 'cmd_r': Key.cmd_r,
            'ctrl': Key.ctrl, 'ctrl_l': Key.ctrl_l, 'ctrl_r': Key.ctrl_r,
            'delete': Key.delete, 'down': Key.down, 'end': Key.end,
            'enter': Key.enter, 'esc': Key.esc, 'f1': Key.f1, 'f2': Key.f2,
            'f3': Key.f3, 'f4': Key.f4, 'f5': Key.f5, 'f6': Key.f6,
            'f7': Key.f7, 'f8': Key.f8, 'f9': Key.f9, 'f10': Key.f10,
            'f11': Key.f11, 'f12': Key.f12, 'home': Key.home,
            'insert': Key.insert, 'left': Key.left, 'media_next': Key.media_next,
            'media_play_pause': Key.media_play_pause, 'media_previous': Key.media_previous,
            'media_volume_down': Key.media_volume_down, 'media_volume_mute': Key.media_volume_mute,
            'media_volume_up': Key.media_volume_up, 'menu': Key.menu,
            'num_lock': Key.num_lock, 'page_down': Key.page_down, 'page_up': Key.page_up,
            'pause': Key.pause, 'print_screen': Key.print_screen, 'right': Key.right,
            'scroll_lock': Key.scroll_lock, 'shift': Key.shift, 'shift_l': Key.shift_l,
            'shift_r': Key.shift_r, 'space': Key.space, 'tab': Key.tab, 'up': Key.up
        }

    def _lazy_init_controllers(self):
        """Initializes pynput controllers if they haven't been already."""
        if self.keyboard is None:
            self.keyboard = KeyboardController()
        if self.mouse is None:
            self.mouse = MouseController()

    def execute(self, action):
        """Executes a given key or mouse action."""
        self._lazy_init_controllers()

        action_type = action.get('type')
        detail = action.get('detail')

        # Play a sound notification in a background thread to avoid blocking
        if global_state.play_action_sound and global_state.action_sound_path:
            if os.path.exists(global_state.action_sound_path):
                # Use winsound on Windows for better compatibility; it's built-in.
                if sys.platform == "win32":
                    sound_thread = threading.Thread(target=lambda: winsound.PlaySound(global_state.action_sound_path, winsound.SND_FILENAME), daemon=True)
                    sound_thread.start()
                else:
                    # Provide a message for non-Windows users as playsound is removed.
                    print(f"Warning: Sound playback is currently only supported on Windows.")
            else:
                print(f"Warning: Sound file not found at '{global_state.action_sound_path}'")

        if not detail:
            return

        try:
            if action_type == 'Key Press':
                key_to_press = self.special_keys.get(detail.lower(), detail)

                # Press the key
                self.keyboard.press(key_to_press)

                # **MODIFICATION**: Wait for a short, random interval to simulate a real key press
                time.sleep(random.uniform(0.04, 0.09))  # 40ms to 90ms

                # Release the key
                self.keyboard.release(key_to_press)

                print(f"Action Executed: Pressed key '{detail}' with simulated duration.")

            elif action_type == 'Mouse Click':
                if detail.lower() == 'left':
                    self.mouse.press(Button.left)
                    self.mouse.release(Button.left)
                elif detail.lower() == 'right':
                    self.mouse.press(Button.right)
                    self.mouse.release(Button.right)
                print(f"Action Executed: {detail} mouse click")

        except Exception as e:
            print(f"Error during action execution: {e}")