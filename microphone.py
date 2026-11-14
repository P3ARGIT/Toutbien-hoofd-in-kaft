import math
import os
import struct
import subprocess
import time

RATE = 16000
FRAME_MS = 10
FRAME_BYTES = RATE * FRAME_MS // 1000 * 2
TARGET_SPL = 80
DEMO_THRESHOLD = -16
REQUIRED_VOICED_MS = 75
REQUIRED_VOICED_FRAMES = math.ceil(REQUIRED_VOICED_MS / FRAME_MS)


def rms_dbfs(frame):
    samples = struct.unpack(f"<{len(frame) // 2}h", frame)
    mean = sum(samples) / len(samples)
    power = sum((sample - mean) ** 2 for sample in samples) / len(samples)
    return 10 * math.log10(max(power / 32768 ** 2, 1e-12))


class Microphone:
    def __init__(self):
        from webrtcvad import Vad

        self.vad = Vad(2)
        self.process = None
        self.pending = bytearray()
        self.voiced_frames = 0

    def start(self):
        self.close()
        sources = subprocess.check_output(
            ["pactl", "list", "short", "sources"], text=True, timeout=2
        )
        source = next(
            (fields[1] for line in sources.splitlines()
             if len(fields := line.split()) >= 2
             and "jbl" in fields[1].lower() and not fields[1].endswith(".monitor")),
            None,
        )
        if source is None:
            raise RuntimeError("JBL microphone not found in pactl list short sources.")
        self.process = subprocess.Popen(
            ["parec", "--device", source, "--raw", "--format=s16le",
             f"--rate={RATE}", "--channels=1", "--latency-msec=40"],
            stdout=subprocess.PIPE,
        )
        os.set_blocking(self.process.stdout.fileno(), False)

    def measure(self, threshold):
        data = self.process.stdout.read1(8192)
        if data is None:
            return None, False
        if not data:
            if self.process.poll() is not None:
                raise RuntimeError("JBL microphone capture stopped.")
            return None, False

        self.pending.extend(data)
        peak = None
        while len(self.pending) >= FRAME_BYTES:
            frame = bytes(self.pending[:FRAME_BYTES])
            del self.pending[:FRAME_BYTES]
            level = rms_dbfs(frame)
            peak = level if peak is None else max(peak, level)
            if level >= threshold and self.vad.is_speech(frame, RATE):
                self.voiced_frames += 1
                if self.voiced_frames >= REQUIRED_VOICED_FRAMES:
                    return peak, True
            else:
                self.voiced_frames = 0
        return peak, False

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process.stdout.close()
            self.process = None
        self.pending.clear()
        self.voiced_frames = 0


def monitor():
    mic = Microphone()
    try:
        mic.start()
        while True:
            levels = []
            until = time.monotonic() + 1
            while time.monotonic() < until:
                level, _ = mic.measure(math.inf)
                if level is not None:
                    levels.append(level)
                time.sleep(0.02)
            if levels:
                print(f"JBL level: {max(levels):.1f} dBFS", flush=True)
    finally:
        mic.close()
