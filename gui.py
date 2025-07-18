# gui.py
import customtkinter as ctk
import threading
import time
from pynput import mouse, keyboard

from backend import ActionExecutor
from recorder import ActionRecorder
from utils import format_key, format_action_sequence, format_time

class HotkeyListener(threading.Thread):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.pressed_keys = set()
        self.listener = None
        self.daemon = True

    def run(self):
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            self.listener = listener
            listener.join()

    def on_press(self, key):
        self.pressed_keys.add(key)
        # Use sorted lists of strings for reliable comparison of key sets
        if sorted(list(map(str, self.pressed_keys))) == sorted(list(map(str, self.app.hotkey_action))):
            self.app.toggle_action()
    
    def on_release(self, key):
        try:
            self.pressed_keys.remove(key)
        except KeyError:
            pass
    
    def stop(self):
        if self.listener:
            self.listener.stop()

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(self.tooltip_window, text=self.text, corner_radius=5,
                             fg_color="#2B2B2B", justify="left")
        label.pack(ipadx=5, ipady=5)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # --- State ---
        self.app_state = "Idle"
        self.start_time = time.time()
        self.total_actions = 0
        self.hotkey_action = {keyboard.Key.f6}
        self.custom_key_action = [{'type': 'press', 'key': 'e'}, {'type': 'release', 'key': 'e'}]
        self.active_thread = None
        self.active_recorder = None
        self.picked_pos = None

        # --- Window Setup ---
        self.title("Python AutoClicker")
        self.geometry("680x610")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        ctk.set_appearance_mode("Dark")
        self.grid_columnconfigure(0, weight=1)

        self._create_widgets()
        self.hotkey_listener = HotkeyListener(self)
        self.hotkey_listener.start()
        self.update_stats_display()
        self.on_timing_mode_change()
        self.on_target_change()

    def _create_widgets(self):
        # -- Status Bar Frame (Sharp) --
        self.status_bar_frame = ctk.CTkFrame(self, corner_radius=0)
        self.status_bar_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        
        self.status_label = ctk.CTkLabel(self.status_bar_frame, text="Status: Idle", font=("Arial", 16, "bold"), text_color="red")
        self.status_label.pack(side="left", padx=10, pady=5)
        
        self.stats_label = ctk.CTkLabel(self.status_bar_frame, text="Uptime: 00:00:00 | Total Clicks: 0")
        self.stats_label.pack(side="right", padx=10, pady=5)

        # -- Main Frames (Sharp Corners) --
        self.action_frame = ctk.CTkFrame(self, corner_radius=0)
        self.type_frame = ctk.CTkFrame(self, corner_radius=0)
        self.cursor_frame = ctk.CTkFrame(self, corner_radius=0)
        self.controls_frame = ctk.CTkFrame(self, corner_radius=0)

        self.action_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.type_frame.grid(row=2, column=0, padx=10, pady=0, sticky="ew")
        self.cursor_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        self.controls_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")

        # -- 1. Click Action Frame --
        self.action_frame.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self.action_frame, text="Click Action", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        self.target_var = ctk.StringVar(value="Left")
        
        ctk.CTkRadioButton(self.action_frame, text="Left Click", variable=self.target_var, value="Left", command=self.on_target_change).grid(row=1, column=0, pady=5)
        ctk.CTkRadioButton(self.action_frame, text="Middle Click", variable=self.target_var, value="Middle", command=self.on_target_change).grid(row=1, column=1, pady=5)
        ctk.CTkRadioButton(self.action_frame, text="Right Click", variable=self.target_var, value="Right", command=self.on_target_change).grid(row=2, column=0, pady=5)
        
        custom_key_frame = ctk.CTkFrame(self.action_frame, fg_color="transparent")
        custom_key_frame.grid(row=2, column=1, pady=5)
        ctk.CTkRadioButton(custom_key_frame, text="Custom Key", variable=self.target_var, value="Key", command=self.on_target_change).pack(side="left")
        self.custom_key_button = ctk.CTkButton(custom_key_frame, text=f"Set Key ( {format_action_sequence(self.custom_key_action)} )", command=self.set_custom_key)
        self.custom_key_button.pack(side="left", padx=5)

        # -- 2. Click Type Frame --
        self.type_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.type_frame, text="Click Type", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=(10,0))
        
        self.timing_mode_var = ctk.StringVar(value="CPS")
        timing_radio_frame = ctk.CTkFrame(self.type_frame, fg_color="transparent")
        timing_radio_frame.grid(row=1, column=0, columnspan=2, pady=5)
        ctk.CTkRadioButton(timing_radio_frame, text="Clicks Per Second", variable=self.timing_mode_var, value="CPS", command=self.on_timing_mode_change).pack(side="left", padx=20)
        ctk.CTkRadioButton(timing_radio_frame, text="Click Interval", variable=self.timing_mode_var, value="Interval", command=self.on_timing_mode_change).pack(side="left", padx=20)

        # CPS widgets
        self.cps_frame = ctk.CTkFrame(self.type_frame, fg_color="transparent")
        self.cps_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10)
        self.cps_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.cps_frame, text="Clicks Per Second:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.cps_entry = ctk.CTkEntry(self.cps_frame, placeholder_text="e.g., 10")
        self.cps_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.cps_entry.insert(0, "10")
        
        # Interval widgets
        self.interval_frame = ctk.CTkFrame(self.type_frame, fg_color="transparent")
        self.interval_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10)
        self.interval_frame.grid_columnconfigure(0, weight=1)
        
        interval_entries_frame = ctk.CTkFrame(self.interval_frame, fg_color="transparent")
        interval_entries_frame.grid(row=0, column=0, sticky="ew")
        self.interval_entries = {}
        labels = ["Hours", "Mins", "Secs", "Ms"]
        for i, label_text in enumerate(labels):
            interval_entries_frame.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(interval_entries_frame, text=label_text).grid(row=0, column=i)
            entry = ctk.CTkEntry(interval_entries_frame)
            entry.grid(row=1, column=i, padx=5, sticky="ew")
            entry.insert(0, "0")
            self.interval_entries[label_text.lower()] = entry
        
        # Randomizer (New)
        ctk.CTkLabel(self.type_frame, text="Random Delay (+/- ms):").grid(row=3, column=0, padx=20, pady=5, sticky="w")
        self.random_entry = ctk.CTkEntry(self.type_frame)
        self.random_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")
        self.random_entry.insert(0, "0")

        # Stop After (Moved down)
        ctk.CTkLabel(self.type_frame, text="Stop After (clicks):").grid(row=4, column=0, padx=20, pady=10, sticky="w")
        self.stop_at_entry = ctk.CTkEntry(self.type_frame)
        self.stop_at_entry.grid(row=4, column=1, padx=10, pady=10, sticky="ew")
        self.stop_at_entry.insert(0, "0")
        
        # -- 3. Cursor Position Frame --
        self.cursor_frame.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self.cursor_frame, text="Cursor Position", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        self.cursor_var = ctk.StringVar(value="Current")
        ctk.CTkRadioButton(self.cursor_frame, text="At Current Position", variable=self.cursor_var, value="Current").grid(row=1, column=0)
        
        self.custom_loc_frame = ctk.CTkFrame(self.cursor_frame, fg_color="transparent")
        self.custom_loc_frame.grid(row=1, column=1)
        self.radio_picked = ctk.CTkRadioButton(self.custom_loc_frame, text="At Custom Location", variable=self.cursor_var, value="Picked")
        self.radio_picked.pack()
        self.pick_button = ctk.CTkButton(self.custom_loc_frame, text="Pick Location", command=self.pick_location)
        self.pick_button.pack(pady=5)
        self.picked_pos_label = ctk.CTkLabel(self.custom_loc_frame, text="X: None, Y: None")
        self.picked_pos_label.pack()

        # -- 4. Controls Frame --
        self.controls_frame.grid_columnconfigure(0, weight=1)
        self.hotkey_button = ctk.CTkButton(self.controls_frame, text=f"Start/Stop Hotkey: {format_action_sequence(self.hotkey_action)}", command=self.set_hotkey)
        
        self.theme_switch = ctk.CTkSwitch(self.controls_frame, text="Light Mode", command=self.toggle_theme)
        
        help_text = (
            "--- AutoClicker Help ---\n"
            "Hotkey: Records a key combination (e.g., Ctrl+Shift+F).\n\n"
            "Click Action: Choose what to automate.\n"
            "- Set Key: Records a specific key press or mouse click.\n\n"
            "Click Type: Set clicks/sec or a fixed interval.\n"
            "- Random Delay: Adds a random +/- variance to the timing.\n\n"
            "Cursor Position: Choose where mouse clicks happen."
        )
        self.help_button = ctk.CTkButton(self.controls_frame, text="?", width=28)
        Tooltip(self.help_button, help_text)
        
        self.help_button.pack(side="right", padx=10, pady=10)
        self.theme_switch.pack(side="right", padx=0, pady=10)
        self.hotkey_button.pack(side="left", fill="x", expand=True, padx=10, pady=10)

    def toggle_theme(self):
        mode = "light" if self.theme_switch.get() else "dark"
        ctk.set_appearance_mode(mode)

    def update_status(self, text, color):
        self.status_label.configure(text=f"Status: {text}", text_color=color)
        self.app_state = text

    def update_stats_display(self):
        uptime_str = format_time(time.time() - self.start_time)
        
        current_run_actions = 0
        if self.active_thread and self.active_thread.is_alive():
            current_run_actions = self.active_thread.actions_done

        display_actions = self.total_actions + current_run_actions
        self.stats_label.configure(text=f"Uptime: {uptime_str} | Total Clicks: {display_actions}")
        
        self.after(1000, self.update_stats_display)

    def on_timing_mode_change(self):
        if self.timing_mode_var.get() == "CPS":
            self.cps_frame.grid()
            self.interval_frame.grid_remove()
        else:
            self.cps_frame.grid_remove()
            self.interval_frame.grid()

    def on_target_change(self):
        is_mouse_action = self.target_var.get() in ["Left", "Middle", "Right"]
        state = "normal" if is_mouse_action else "disabled"

        def set_state_recursive(widget):
            try:
                if 'state' in widget.configure():
                    widget.configure(state=state)
            except Exception:
                pass
            
            for child in widget.winfo_children():
                set_state_recursive(child)
        
        set_state_recursive(self.cursor_frame)

    def set_hotkey(self):
        if self.active_recorder: return
        self.hotkey_button.configure(text="Recording new hotkey...")
        self.active_recorder = ActionRecorder(callback=self.on_hotkey_recorded, hotkey_mode=True)
        self.active_recorder.start()

    def on_hotkey_recorded(self, key_combination):
        if key_combination: self.hotkey_action = key_combination
        self.hotkey_button.configure(text=f"Start/Stop Hotkey: {format_action_sequence(self.hotkey_action)}")
        self.active_recorder = None

    def set_custom_key(self):
        if self.active_recorder: return
        self.custom_key_button.configure(text="Recording...")
        self.active_recorder = ActionRecorder(callback=self.on_custom_key_recorded, restrict_mouse=True)
        self.active_recorder.start()

    def on_custom_key_recorded(self, event_sequence):
        if event_sequence: self.custom_key_action = event_sequence
        self.custom_key_button.configure(text=f"Set Key ( {format_action_sequence(self.custom_key_action)} )")
        self.active_recorder = None
    
    def toggle_action(self):
        if self.app_state == "Active":
            self.stop_action()
        elif self.app_state == "Idle":
            self.start_action()

    def start_action(self):
        if self.app_state != "Idle": return
        
        self.update_status("Active", "green")
        try:
            stop_count = int(self.stop_at_entry.get())
            random_ms = int(self.random_entry.get())
            
            if self.timing_mode_var.get() == "CPS":
                cps = int(self.cps_entry.get())
                delay = 1.0 / (cps if cps > 0 else 1)
            else:
                h = int(self.interval_entries['hours'].get())
                m = int(self.interval_entries['mins'].get())
                s = int(self.interval_entries['secs'].get())
                ms = int(self.interval_entries['ms'].get())
                delay = (h * 3600) + (m * 60) + s + (ms / 1000)
            
            target_selection = self.target_var.get()
            action_sequence = []
            if target_selection == "Left":
                action_sequence = [{'type': 'click', 'button': mouse.Button.left}]
            elif target_selection == "Middle":
                action_sequence = [{'type': 'click', 'button': mouse.Button.middle}]
            elif target_selection == "Right":
                action_sequence = [{'type': 'click', 'button': mouse.Button.right}]
            else:
                action_sequence = self.custom_key_action

            pos = self.picked_pos if self.cursor_var.get() == "Picked" else None

            self.active_thread = ActionExecutor(delay, stop_count, action_sequence, pos, random_ms)
            self.active_thread.start()

        except ValueError:
            self.update_status("Idle", "red")

    def stop_action(self):
        if self.active_thread:
            self.active_thread.stop()
            self.active_thread.join(timeout=0.1) 
            self.total_actions += self.active_thread.actions_done
            self.active_thread = None
        self.update_status("Idle", "red")
    
    def pick_location(self):
        self.update_status("Picking...", "blue")
        def on_click(x, y, button, pressed):
            if pressed:
                self.picked_pos = (x, y)
                self.picked_pos_label.configure(text=f"X: {x}, Y: {y}")
                self.update_status("Idle", "red")
                return False 
        mouse_listener = mouse.Listener(on_click=on_click)
        mouse_listener.start()

    def on_closing(self):
        self.stop_action()
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        self.destroy()