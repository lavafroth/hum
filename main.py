from keypress import keypress
from player import play_frequencies, handle_input_event
import asyncio
from numpy.typing import NDArray
import librosa
import mido
import numpy as np
import sounddevice as sd
import time
from dataclasses import dataclass
from scipy.stats import mode

samplerate = 22050
channels = 1  # mono


@dataclass
class Note:
    frequency: float
    start: float
    end: float


async def record_audio(event):
    chunks = []

    def callback(indata, _frames, _time, _status):
        chunks.append(indata.copy())

    stream = sd.InputStream(samplerate=samplerate, channels=channels, callback=callback)

    with stream:
        await event.wait()

    if chunks:
        return np.concatenate(chunks, axis=0).squeeze().astype(np.float32)


def loudest_frequency(chunk: NDArray, bins: NDArray) -> float:
    peak_frequencies = np.argmax(chunk, axis=0)
    peak_frequency_energy = np.max(chunk, axis=0)

    valid_frames = peak_frequency_energy > -15
    if np.sum(valid_frames) == 0:
        return np.nan

    stable_center_row = mode(peak_frequencies[valid_frames]).mode
    return bins[stable_center_row]


def align(hum, timings: list[float]) -> list[float]:
    if len(timings) == 0:
        raise Exception("Error: No note boundaries set.")

    y, sr = hum, samplerate

    fmin = librosa.note_to_hz("C2").item()
    n_bins = 40
    bins_per_octave = 12

    C = librosa.cqt(
        y=y, sr=sr, fmin=fmin, n_bins=n_bins, bins_per_octave=bins_per_octave
    )
    C_db = librosa.amplitude_to_db(np.abs(C), ref=np.max)
    true_frequencies = librosa.cqt_frequencies(
        fmin=fmin, n_bins=n_bins, bins_per_octave=bins_per_octave
    )

    notes: list[float] = [
        0.0,
    ]

    timings.append(librosa.get_duration(y=y, sr=sr))
    frames = librosa.time_to_frames(timings, sr=sr)

    for frame_start, frame_end in zip(frames, frames[1:]):
        if frame_end - frame_start < 3:
            continue

        freq = loudest_frequency(C_db[:, frame_start:frame_end], true_frequencies)

        if np.isnan(freq) or freq < 85:
            continue

        notes.append(freq)
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


async def record_audio_times(event):
    humming_timestamps = []
    start_session = time.perf_counter()


    while not await asyncio.to_thread(keypress, "q"):
        current_time = time.perf_counter() - start_session
        humming_timestamps.append(current_time)
        print(f"\rnote boundary at: {current_time:.3f}s", end="", flush=True)

    event.set()
    print()
    return humming_timestamps


async def main():
    event = asyncio.Event()

    print("hum your melody slowly, one note at a time: press 'q' to stop recording")
    print("anything else to mark a note boundary")
    
    results = await asyncio.gather(record_audio(event), record_audio_times(event))

    print("playing notes back to you")
    print("press 'q' to stop capturing rhythm")
    print("keep pressing any other key at the correct rhythm until all notes are exhausted")
    print("ready whenever you are")

    freqs = align(*results)
    event = asyncio.Event()
    _, timestamps = await asyncio.gather(
        play_frequencies(event, freqs),
        handle_input_event(event, freqs),
    )

    notes = [
        Note(freq, start, end)
        for freq, start, end in zip(freqs[1:], timestamps[1:], timestamps[2:])
    ]
    save(notes, "output.mid")


asyncio.run(main())
