import pretty_midi
from collect_midis import gather_midi_paths

all_midis = gather_midi_paths()
sample = all_midis[10000]
pm = pretty_midi.PrettyMIDI(sample[0])

print(sample[0])
print(pm.instruments)