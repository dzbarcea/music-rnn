import os
import pretty_midi
import torch
from collect_midis import gather_midi_paths

## Converts MIDI files to token sequences, then stores them in midi_token_dataset.pt as pairs of (token_sequence, genre_id)
## Stores genre->integer map in genre2idx.pt

# Step 1: define event vocabulary to map MIDI events to an integer ID:
TIME_STEP = 0.03

def quantize_time(t):
    """Round a float time t (in seconds) to the nearest TIME_STEP grid index."""
    return int(round(t / TIME_STEP))

MAX_PITCH = 127
MAX_SHIFT = 100

token2event = {}
event2token = {}

# NOTE_ON tokens: 0...127
for pitch in range(MAX_PITCH + 1):
    token = f"NOTE_ON_{pitch}"
    idx = pitch
    token2event[idx] = token
    event2token[token] = idx

# TIME_SHIFT tokens: 128...128+MAX_SHIFT-1
base = MAX_PITCH + 1
for shift in range(1, MAX_SHIFT + 1):
    token = f"TIME_SHIFT_{shift}"
    idx = base + shift - 1
    token2event[idx] = token
    event2token[token] = idx

VOCAB_SIZE = MAX_PITCH + 1 + MAX_SHIFT


# Step 2: define function for converting MIDI events to token sequence
def midi_to_token_sequence(midi_path):
    # Validate the MIDI file before processing
    if not os.path.isfile(midi_path):
        raise FileNotFoundError(f"The file '{midi_path}' does not exist or is not accessible.")

    if os.path.getsize(midi_path) == 0:
        raise ValueError(f"The file '{midi_path}' is empty and cannot be processed.")

    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
    except Exception as e:
        # Handle corrupted or non-MIDI files gracefully
        raise ValueError(f"Failed to parse MIDI file '{midi_path}'. Error: {e}")

    # 1) Gather all note-on events for each instrument
    note_events = []
    for inst in pm.instruments:
        for note in inst.notes:
            start_bin = quantize_time(note.start)
            note_events.append((start_bin, note.pitch))

    if not note_events:
        return []

    # 2) Sort by time_bin, then by pitch
    note_events.sort(key=lambda x: (x[0], x[1]))

    # 3) Walk through each event, emitting NOTE_ON and TIME_SHIFT
    i = 0
    tokens = []
    prev_bin = note_events[0][0]
    while i < len(note_events) and note_events[i][0] == prev_bin:
        pitch = note_events[i][1]
        tokens.append(event2token[f"NOTE_ON_{pitch}"])
        i += 1

    while i < len(note_events):
        curr_bin, pitch = note_events[i]

        delta = curr_bin - prev_bin
        # 3a) If delta > 0, break it into TIME_SHIFT tokens
        while delta > 0:
            shift_amount = min(delta, MAX_SHIFT)
            tokens.append(event2token[f"TIME_SHIFT_{shift_amount}"])
            delta -= shift_amount

        # 3b) Emit all NOTE_ON events at this new time bin
        same_bin = curr_bin
        while i < len(note_events) and note_events[i][0] == same_bin:
            pitch = note_events[i][1]
            tokens.append(event2token[f"NOTE_ON_{pitch}"])
            i += 1

        prev_bin = same_bin

    return tokens


# Step 3: Build a dataset of (tokens, genre) pairs
# 3.1: Run collect_midis to get a List of (midi_path, genre) tuples
midi_list = gather_midi_paths()

# 3.2: Create a genre->integer map
genres = sorted({g for _, g in midi_list})
genre2idx = {g: i for i, g in enumerate(genres)}
print("Genre mapping:", genre2idx)

# 3.3: Convert every file and store (token_seq, genre_id)
dataset = []
failed = []
for path, genre in midi_list:
    try:
        seq = midi_to_token_sequence(path)
        if len(seq) < 10:
            # Skip extremely short files
            failed.append((path, "Sequence too short"))
            continue
        print(f"Converted {path} to {len(seq)} tokens.")
        dataset.append((seq, genre2idx[genre]))
    except Exception as e:
        # Log the error and skip the problematic file
        failed.append((path, str(e)))

print(f"Converted {len(dataset)} files, skipped {len(failed)} files.")


# Step 4: Save (token_sequence, genre_id) pairs as .pt
print(f"Saving dataset...")
torch.save(dataset, "midi_token_dataset.pt")
print(f"Saved dataset to midi_token_dataset.pt.")
print(f"Saving genre2idx...")
torch.save(genre2idx, "genre2idx.pt")
print(f"Saved genre2idx to genre2idx.pt.")