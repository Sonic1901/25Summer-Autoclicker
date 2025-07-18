# recorder.py
import threading
from pynput import mouse, keyboard

class ActionRecorder(threading.Thread):
    def __init__(self, callback, hotkey_mode=False, restrict_mouse=False):
        super().__init__()
        self.callback = callback
        self.hotkey_mode = hotkey_mode
        self.restrict_mouse = restrict_mouse
        
        self.events = []
        self.pressed_keys = set()
        
        self.mouse_listener = None
        self.keyboard_listener = None
        self.ignore_first_mouseup = True
        self.daemon = True

    def run(self):
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop_listeners(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        
        # Return the set of pressed keys for hotkey mode
        if self.hotkey_mode:
            self.callback(self.pressed_keys)
        # Return the sequence of events for custom key mode
        else:
            self.callback(self.events)

    def on_click(self, x, y, button, pressed):
        if not pressed:
            if self.ignore_first_mouseup:
                self.ignore_first_mouseup = False
                return
            
            if self.restrict_mouse and button in [mouse.Button.left, mouse.Button.right, mouse.Button.middle]:
                return

            self.events.append({'type': 'click', 'button': button, 'pos': (x, y)})
            self.stop_listeners()
            return False

    def on_press(self, key):
        self.ignore_first_mouseup = False 
        self.pressed_keys.add(key)
        if not self.hotkey_mode:
            self.events.append({'type': 'press', 'key': key})

    def on_release(self, key):
        if self.hotkey_mode:
            # In hotkey mode, the recording ends when the last key is released
            self.stop_listeners()
            return False
        
        # Standard custom key recording logic
        self.events.append({'type': 'release', 'key': key})
        is_modifier = isinstance(key, keyboard.Key) and any(mod in key.name for mod in ['shift', 'ctrl', 'alt'])
        
        has_main_key = any(
            'key' in e and not (isinstance(e.get('key'), keyboard.Key) and any(mod in e['key'].name for mod in ['shift', 'ctrl', 'alt']))
            for e in self.events if e['type'] == 'press'
        )

        if not is_modifier or (is_modifier and not has_main_key):
            self.stop_listeners()
            return False