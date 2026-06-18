import time
import asyncio
import numpy as np
import sounddevice as sd
from keypress import keypress

class FrequencyPlayer:
    def __init__(self, freq, sr):
        self.freqs = freq
        self.sr = sr
        self.phase = 0
        self.freq_ix = 0

    def __call__(self, out, frames: int, _time, _status):
        freq = self.freqs[self.freq_ix] if self.inbounds() else 0

        dt = 1 / self.sr
        phase_increment = 2 * np.pi * freq * dt

        phases = self.phase + np.arange(frames) * phase_increment

        out[:] = 0.2 * np.sin(phases).reshape(-1, 1)
        self.phase = (phases[-1] + phase_increment) % (2 * np.pi)

    def next_freq(self):
        if self.inbounds():
            self.freq_ix += 1

    def inbounds(self):
        return len(self.freqs) > self.freq_ix



async def play_frequencies(event, freqs):
    samplerate = sd.query_devices(sd.default.device, 'output')['default_samplerate']

    player = FrequencyPlayer(freqs, samplerate)
    with sd.OutputStream(samplerate, channels=1, callback=player):
        while player.inbounds():
            await event.wait()
            player.next_freq()
            event.clear()


async def handle_input_event(event, freqs) -> list[float]:
    start_session = time.perf_counter()
    timestamps = [0.0]
    for _ in freqs:
        await asyncio.to_thread(keypress, "q")
        current_time = time.perf_counter() - start_session
        timestamps.append(current_time)
        print(current_time)
        event.set()

    return timestamps

