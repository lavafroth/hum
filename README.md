# Hum

Convert hummed melody into MIDI.

## Getting Started

```sh
nix develop
python main.py
```

### Baseline

For the first time, you need to hum a single note at a frequency you're comfortable in. Press _q_ to confirm the baseline.

### Melody

For the second round, hum the melody, pressing the space bar at the start of each note. This should feel natural as humans have an incredible sense of rhythm.

Finally, press q to stop recording.

### Replay

You can play the output midi file with a command line tool like _timidity_

```sh
timidity --volume=150 output.mid
```

or open them in a DAW like _Ardour_.
