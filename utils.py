# utils.py
import time
from pynput.keyboard import Key

# Formats a pynput key object into a readable string like 'Ctrl' or 'A'.
def format_key(key):
    if isinstance(key, Key):
        return key.name.capitalize().replace('_l', ' (L)').replace('_r', ' (R)')
    return str(key).strip("'")

# Creates a readable string summary of a recorded action sequence.
def format_action_sequence(sequence):
    if not sequence:
        return "None"
    
    # Handle the new hotkey format (a set of keys)
    if isinstance(sequence, set):
        return " + ".join(sorted([format_key(k) for k in sequence]))

    # Handle the old action format (a list of dicts)
    if len(sequence) == 1 and sequence[0]['type'] == 'click':
        return f"Click: {format_key(sequence[0]['button'])}"

    # Keyboard action
    modifiers = [format_key(e['key']) for e in sequence if isinstance(e.get('key'), Key) and 'shift' in e['key'].name]
    main_key = [format_key(e['key']) for e in sequence if 'key' in e and not isinstance(e.get('key'), Key) or (isinstance(e.get('key'), Key) and 'shift' not in e['key'].name)]
    
    parts = sorted(list(set(modifiers)))
    if main_key:
        parts.append(main_key[0])

    return " + ".join(parts) if parts else "Unknown Key"

def format_time(seconds):
    """Formats seconds into HH:MM:SS format."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"