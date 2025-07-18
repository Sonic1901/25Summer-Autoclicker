# backend.py
import threading
import time
import random
from pynput import mouse, keyboard

class ActionExecutor(threading.Thread):
    def __init__(self, delay_seconds, stop_count, action_sequence, click_pos=None, random_delay_ms=0):
        super().__init__()
        self.base_delay = delay_seconds
        self.random_delay_s = random_delay_ms / 1000.0
        self.stop_count = stop_count
        self.action_sequence = action_sequence
        self.click_pos = click_pos
        self.running = False
        self.actions_done = 0
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        self.daemon = True

    def run(self):
        self.running = True
        while self.running:
            if self.stop_count > 0 and self.actions_done >= self.stop_count:
                break
            
            for event in self.action_sequence:
                if event['type'] == 'click':
                    if self.click_pos:
                        self.mouse.position = self.click_pos
                    self.mouse.click(event['button'])
                elif event['type'] == 'press':
                    self.keyboard.press(event['key'])
                elif event['type'] == 'release':
                    self.keyboard.release(event['key'])
            
            self.actions_done += 1
            
            # Calculate final delay with randomization
            random_offset = random.uniform(-self.random_delay_s, self.random_delay_s)
            final_delay = max(0, self.base_delay + random_offset)
            time.sleep(final_delay)
            
        self.running = False

    def stop(self):
        self.running = False