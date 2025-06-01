import os

def gather_midi_paths(root_dir="MIDIs"):
    """Returns list of (midi_path, genre) tuples."""
    examples = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn.lower().endswith(".mid"):
                full_path = os.path.join(dirpath, fn)
                # Assumes structure: MIDIs/Genre/(OptionalSubgenre/)/Artist/song.mid
                parts = full_path.split(os.sep)
                # parts = ["MIDIs", "Genre", ... , "song.mid"]
                if len(parts) < 3:
                    continue
                genre = parts[1]  # the folder immediately under MIDIs
                examples.append((full_path, genre))
    return examples