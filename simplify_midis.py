import pretty_midi
import os
from collect_midis import gather_midi_paths

def analyze_midi(path):
    """Returns the bass, melody, and chord instruments of a MIDI file."""
    pm = pretty_midi.PrettyMIDI(path)
    instruments = [inst for inst in pm.instruments if not inst.is_drum]

    if len(instruments) == 1:
        return { "melody": instruments[0] }

    # 1) First pass: gather raw stats per instrument
    stats = []
    for inst in instruments:
        num_notes = len(inst.notes)
        if num_notes == 0:
            continue

        total_pitch = 0
        concurrent_notes = 0
        prev_end = 0
        total_length = 0

        for note in inst.notes:
            pitch = note.pitch
            total_pitch += pitch
            if note.start < prev_end:
                concurrent_notes += 1
            prev_end = note.end
            total_length += (note.end - note.start)

        avg_pitch = total_pitch / num_notes
        avg_length = total_length / num_notes

        stats.append({
            "instrument": inst,
            "program": inst.program,
            "num_notes": num_notes,
            "avg_pitch": avg_pitch,
            "concurrency": concurrent_notes,
            "avg_length": avg_length
        })

    # 2) Compute normalization constants
    max_num_notes = max(s["num_notes"] for s in stats)
    max_concurrency = max(s["concurrency"] for s in stats) or 1   # avoid division by zero
    max_avg_length = max(s["avg_length"] for s in stats) or 1.0

    # 3) Assign scores
    results = []
    for s in stats:
        prog = s["program"]
        num_notes = s["num_notes"]
        avg_pitch = s["avg_pitch"]
        concurrency = s["concurrency"]
        avg_length = s["avg_length"]

        # Normalize note count
        norm_note_count = num_notes / max_num_notes

        # Normalize concurrency and avg length
        norm_concurrency = concurrency / max_concurrency
        norm_avg_length = avg_length / max_avg_length

        # Bass score:
        is_bass_prog = 1 if 33 <= prog <= 40 else 0
        low_pitch_score = (127 - avg_pitch) / 127
        bass_score = (
                0.5 * is_bass_prog +
                0.5 * low_pitch_score
        )

        # Chord score:
        high_concurrency_score = norm_concurrency
        long_length_score = norm_avg_length
        chord_score = (
                0.5 * high_concurrency_score +
                0.4 * long_length_score +
                0.1 * norm_note_count
        )

        # Melody score:
        high_pitch_score = avg_pitch / 127
        low_concurrency_score = (max_concurrency - concurrency) / max_concurrency
        melody_score = (
                0.45 * high_pitch_score +
                0.45 * low_concurrency_score +
                0.1 * norm_note_count
        )

        results.append({
            "instrument": s["instrument"],
            "bass_score": bass_score,
            "chord_score": chord_score,
            "melody_score": melody_score,
            "avg_pitch": avg_pitch,
            "concurrency": concurrency,
            "avg_length": avg_length,
            "num_notes": num_notes
        })

    # 4) (Optional) Print out scores for inspection
    # for r in results:
    #     inst = r["instrument"]
    #     name = inst.name or f"Program {inst.program}"
    #     print(f"Track: {name}")
    #     print(f"  Bass score:   {r['bass_score']:.3f}")
    #     print(f"  Chord score:  {r['chord_score']:.3f}")
    #     print(f"  Melody score: {r['melody_score']:.3f}")
    #     print(f"    Avg pitch: {r['avg_pitch']:.1f}, Concurrency: {r['concurrency']}, "
    #           f"Avg length: {r['avg_length']:.3f}, Notes: {r['num_notes']}\n")

    # 5) Select top instruments for each role, handling fewer than 3 results
    n = len(results)

    # If there's only one instrument with notes, return it as melody
    if n == 1:
        return { "melody": results[0]["instrument"] }

    # If there are exactly two instruments, pick the two highest-scoring roles across both
    if n == 2:
        # Build a flattened list of (instrument, role, score)
        flattened = []
        for r in results:
            inst = r["instrument"]
            flattened.append((inst, "bass",   r["bass_score"]))
            flattened.append((inst, "melody", r["melody_score"]))
            flattened.append((inst, "chords", r["chord_score"]))

        # Sort by descending score
        flattened.sort(key=lambda x: x[2], reverse=True)

        assigned = {}
        used_insts = set()
        used_roles = set()

        # Assign top two non-conflicting (instrument, role) pairs
        for inst, role, score in flattened:
            if inst not in used_insts and role not in used_roles:
                assigned[role] = inst
                used_insts.add(inst)
                used_roles.add(role)
                if len(assigned) == 2:
                    break

        return assigned

    # Otherwise (3 or more), follow the original fixed-order logic:
    #  - pick the highest-scoring bass
    #  - then highest-scoring melody among the remaining
    #  - then highest-scoring chord among the remaining
    sorted_for_bass = sorted(results, key=lambda x: x["bass_score"], reverse=True)
    bass_inst = sorted_for_bass[0]["instrument"]

    remaining = [r for r in results if r["instrument"] != bass_inst]

    sorted_for_melody = sorted(remaining, key=lambda x: x["melody_score"], reverse=True)
    melody_inst = sorted_for_melody[0]["instrument"]

    remaining = [r for r in remaining if r["instrument"] != melody_inst]

    sorted_for_chord = sorted(remaining, key=lambda x: x["chord_score"], reverse=True)
    chord_inst = sorted_for_chord[0]["instrument"]

    return {
        "bass": bass_inst,
        "melody": melody_inst,
        "chords": chord_inst,
    }


def simplify_midis():
    all_midis = gather_midi_paths()
    for path, _ in all_midis:
        try:
            results = analyze_midi(path)
        except Exception as e:
            print(f"Error processing MIDI file '{path}': {e}")
            continue

        # Create a new MIDI file using the instruments
        new_midi = pretty_midi.PrettyMIDI()

        # Add the bass, melody, and chord instruments to the new MIDI file
        bass_inst = results.get('bass')
        if bass_inst:
            bass_inst.program = 33
            bass_inst.name = 'Bass'
            new_midi.instruments.append(bass_inst)

        melody_inst = results.get('melody')
        if melody_inst:
            melody_inst.program = 1
            melody_inst.name = 'Melody'
            new_midi.instruments.append(melody_inst)


        chord_inst = results.get('chords')
        if chord_inst:
            chord_inst.program = 0
            chord_inst.name = 'Chords'
            new_midi.instruments.append(chord_inst)

        # Write the new MIDI file to disk
        # Get the genre (first directory after /MIDIs/) and filename
        path_parts = path.split(os.sep)
        genre = path_parts[1]
        filename = path_parts[-1]

        # Create the new output path
        output_dir = os.path.join("simplified_MIDIs", genre)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        new_midi.write(output_path)

        print(f"New MIDI file created and saved as '{output_path}'")

simplify_midis()