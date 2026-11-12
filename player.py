#!/usr/bin/env python3
import argparse
import array
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import time
import wave

ROOT = Path(__file__).resolve().parent
VIDEO = ROOT / "video" / "productvideo.mp4"
STANDBY = ROOT / "audio" / "standbysound.wav"
TITLE = "sorry voor het ongemak sebiet"
RESET_SECONDS = 20


def standby_loop(path):
    """Overlap the WAV edges once, then repeat the resulting PCM buffer."""
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate()
        channels = wav.getnchannels()
        if wav.getsampwidth() != 2 or channels not in (1, 2):
            raise ValueError("Standby vereist een 16-bit mono of stereo PCM-WAV.")
        samples = array.array("h", wav.readframes(wav.getnframes()))

    if sys.byteorder == "big":
        samples.byteswap()
    overlap = min(rate // 10, len(samples) // channels // 4)
    if overlap < 2:
        raise ValueError("Standby-WAV is te kort.")
    width = overlap * channels
    tail = len(samples) - width
    for frame in range(overlap):
        weight = frame / (overlap - 1)
        for channel in range(channels):
            index = frame * channels + channel
            samples[index] = round(
                samples[tail + index] * (1 - weight) + samples[index] * weight
            )
    del samples[tail:]
    return rate, channels, samples.tobytes()


class Player:
    def __init__(self, resources):
        self.socket, child = socket.socketpair()
        resources.enter_context(self.socket)
        self.socket.settimeout(8)
        with child:
            fd = child.fileno()
            self.process = subprocess.Popen(
                [
                    "mpv", "--no-config", "--idle=yes", "--force-window=immediate",
                    "--fullscreen", "--no-osc", "--osd-level=0",
                    "--input-default-bindings=no", "--cursor-autohide=always",
                    "--keep-open=yes", "--keep-open-pause=no", "--image-display-duration=inf",
                    "--stop-screensaver=yes", "--input-terminal=no",
                    f"--script={ROOT / 'fade.lua'}",
                    "--msg-level=all=warn", f"--input-ipc-client=fd://{fd}",
                ],
                pass_fds=(fd,),
            )
        resources.callback(self.close)
        self.replies = resources.enter_context(self.socket.makefile("rb"))

    def close(self):
        self.socket.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def command(self, *args):
        request = json.dumps({"command": args, "request_id": 1}) + "\n"
        self.socket.sendall(request.encode())
        for line in self.replies:
            message = json.loads(line)
            if message.get("request_id") == 1:
                if args == ("get_property", "eof-reached") and message["error"] == "property unavailable":
                    return False
                if message["error"] != "success":
                    raise RuntimeError(f"mpv {args[0]}: {message['error']}")
                return message.get("data")
        raise RuntimeError("mpv heeft de verbinding gesloten.")


def play(args):
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from pygame import Surface, font, image, mixer

    rate, channels, pcm = standby_loop(STANDBY)
    if not VIDEO.is_file():
        raise FileNotFoundError(VIDEO)

    with ExitStack() as resources:
        lock = resources.enter_context(
            open(Path(os.environ["XDG_RUNTIME_DIR"]) / "toutbien.lock", "a")
        )
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Toutbien draait al.", flush=True)
            return

        if not args.test:
            from gpiozero import DigitalInputDevice
            from gpiozero.pins.lgpio import LGPIOFactory

            # Raspberry Pi 5 kernels expose RP1 as gpiochip4 or gpiochip0.
            chip = 4 if Path('/dev/gpiochip4').exists() else 0
            factory = LGPIOFactory(chip=chip)
            resources.callback(factory.close)
            sensor = resources.enter_context(
                DigitalInputDevice(17, pull_up=args.beam, pin_factory=factory)
            )

        mixer.init(frequency=rate, size=-16, channels=channels, buffer=512, allowedchanges=0)
        resources.callback(mixer.quit)
        standby = mixer.Sound(buffer=pcm)
        temporary = resources.enter_context(tempfile.TemporaryDirectory())
        screen = Surface((1280, 720))
        screen.fill((0, 0, 0))
        font.init()
        resources.callback(font.quit)
        title = font.Font(None, 76).render(TITLE, True, (255, 255, 255))
        screen.blit(title, title.get_rect(center=screen.get_rect().center))
        standby_image = str(Path(temporary) / "standby.png")
        image.save(screen, standby_image)

        player = Player(resources)

        def show_standby():
            print("Standby", flush=True)
            player.command("loadfile", standby_image, "replace")
            standby.play(loops=-1)

        show_standby()

        deadline = time.monotonic() + (0 if args.beam or args.test else 60)
        triggered = video_playing = stable = candidate = simulated = False
        absent_since = None
        next_eof_check = 0
        changed_at = time.monotonic()
        if args.test:
            print("Enter = hoofd erin/eruit. Typ q en druk Enter om te stoppen.", flush=True)
        else:
            print("Standby. De PIR stabiliseert 60 seconden na start." if not args.beam else
                  "Standby. Lichtsluis actief.", flush=True)

        while player.process.poll() is None:
            if args.test:
                if select.select([sys.stdin], [], [], 0.025)[0]:
                    line = sys.stdin.readline()
                    if not line or line.strip().lower() == "q":
                        return
                    simulated = not simulated
                present = simulated
            else:
                time.sleep(0.025)
                # PIR hoog bij beweging. Lichtsluis hoog bij onderbreking:
                # met pull-up is sensor.value actief wanneer de uitgang laag is.
                present = not sensor.value if args.beam else bool(sensor.value)

            now = time.monotonic()
            if now < deadline:
                continue
            if present != candidate:
                candidate = present
                changed_at = now
            if candidate != stable and now - changed_at >= 0.12:
                stable = candidate
                if not stable:
                    absent_since = changed_at

            if absent_since is not None and now - absent_since >= RESET_SECONDS:
                triggered = False
                absent_since = None
                if video_playing:
                    show_standby()
                    video_playing = False

            if stable:
                absent_since = None
                if not triggered:
                    print("Video", flush=True)
                    standby.stop()
                    player.command("loadfile", str(VIDEO), "replace")
                    triggered = video_playing = True
                    next_eof_check = now + 0.1

            if video_playing and now >= next_eof_check:
                next_eof_check = now + 0.1
                if player.command("get_property", "eof-reached"):
                    show_standby()
                    video_playing = False

        raise RuntimeError(f"mpv is gestopt (exitcode {player.process.returncode}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Toutbien expo-speler")
    parser.add_argument("--beam", action="store_true", help="Gebruik een lichtsluis.")
    parser.add_argument("--test", action="store_true", help="Test met Enter in de terminal.")
    try:
        play(parser.parse_args())
    except KeyboardInterrupt:
        pass
