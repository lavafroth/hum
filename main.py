from numpy.typing import NDArray
import librosa
import mido
import numpy as np
import queue
import sounddevice as sd
import sys
import threading
import time
from dataclasses import dataclass
from scipy.stats import mode

samplerate = 22050
channels = 1  # mono

audio_queue = queue.Queue()
recording = True
recorded_raw = np.empty((0, channels), dtype=np.float32)
recorded_squeezed = np.empty(0, dtype=np.float32)


@dataclass
class Note:
    frequency: float
    start: float
    end: float


def keypress(character: str):
    if sys.platform.startswith("win"):  # weeee microslop
        import msvcrt

        return msvcrt.getch().decode("utf-8", errors="ignore")
    else:
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch == character


def callback(indata, _frames, _time, status):
    if status:
        print(status, file=sys.stderr, flush=True)
    if recording:
        audio_queue.put(indata.copy())


def record_audio():
    global recorded_raw, recorded_squeezed
    chunks = []

    stream = sd.InputStream(samplerate=samplerate, channels=channels, callback=callback)

    with stream:
        while recording:
            try:
                data = audio_queue.get(timeout=0.1)
                chunks.append(data)
            except queue.Empty:
                continue

        stream.stop()
        stream.close()

    while not audio_queue.empty():
        chunks.append(audio_queue.get())

    if chunks:
        recorded_raw = np.concatenate(chunks, axis=0)
        recorded_squeezed = recorded_raw.squeeze().astype(np.float32)


def chunk_stable_frequency(chunk: NDArray, bins: NDArray) -> float:
    peak_frequencies = np.argmax(chunk, axis=0)
    peak_frequency_energy = np.max(chunk, axis=0)

    valid_frames = peak_frequency_energy > -15
    if np.sum(valid_frames) == 0:
        return np.nan

    stable_center_row = mode(peak_frequencies[valid_frames]).mode
    return bins[stable_center_row]


def align(baseline_end_time: float, hum: list[float]):
    if len(hum) == 0:
        raise Exception("Error: No note boundaries set.")

    y, sr = recorded_squeezed, samplerate

    fmin = librosa.note_to_hz("C2").item()
    cqt_args = dict(fmin=fmin, n_bins=40, bins_per_octave=12)

    C = librosa.cqt(y=y, sr=sr, **cqt_args)
    C_db = librosa.amplitude_to_db(np.abs(C), ref=np.max)
    true_frequencies = librosa.cqt_frequencies(**cqt_args)

    notes = []

    frame_end = librosa.time_to_frames(baseline_end_time, sr=sr)

    if frame_end < 3:
        raise Exception("The baseline hum was too short. Try humming a bit longer.")

    baseline = chunk_stable_frequency(C_db[:, :frame_end], true_frequencies)
    if np.isnan(baseline) or baseline < 85:
        raise Exception(
            "No frequency in the baseline hum was in the human humming range. Did you even hum?"
        )

    baselines = [
        np.argmin(np.abs(true_frequencies - baseline * (2 ** (n / 12))))
        for n in range(-4, 24)
    ]

    hum.append(librosa.get_duration(y=y, sr=sr))
    frames = librosa.time_to_frames(hum, sr=sr)

    for t_start, t_end, frame_start, frame_end in zip(hum, hum[1:], frames, frames[1:]):
        if frame_end - frame_start < 3:
            continue

        freq = chunk_stable_frequency(
            C_db[baselines, frame_start:frame_end], true_frequencies[baselines]
        )

        if np.isnan(freq):
            continue

        n = (12 * np.log2(freq / baseline)).round()
        freq = baseline * (2 ** (n / 12))

        notes.append(Note(freq, t_start, t_end))
    return notes


def save(notes: list[Note], to: str):
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))

    seconds_per_tick = 60.0 / (120 * mid.ticks_per_beat)
    last_ticks = 0

    for note in notes:
        pitch = int(np.round(librosa.hz_to_midi(note.frequency)))

        for time_seconds, note_state, velocity in (
            (note.start, "note_on", 100),
            (note.end, "note_off", 0),
        ):
            curr_ticks = int(np.round(time_seconds / seconds_per_tick))
            delta = max(0, curr_ticks - last_ticks)
            last_ticks = curr_ticks

            track.append(
                mido.Message(note_state, note=pitch, velocity=velocity, time=delta)
            )
    mid.save(to)


# main

thread = threading.Thread(target=record_audio)
thread.start()

print("hum a single note: press 'q' to stop recording and calibrate")

baseline = None  # mut
humming_timestamps = []  # mut

start_session = time.perf_counter()

while not keypress("q"):
    continue

current_time = time.perf_counter() - start_session
baseline = current_time

print("hum your melody: press 'q' to stop recording")
print("anything else to mark a note boundary")

while not keypress("q"):
    current_time = time.perf_counter() - start_session
    humming_timestamps.append(current_time)
    print(f"\rnote boundary at: {current_time:.3f}s", end="", flush=True)

print()

recording = False
thread.join()

notes = align(baseline, humming_timestamps)
save(notes, "output.mid")
