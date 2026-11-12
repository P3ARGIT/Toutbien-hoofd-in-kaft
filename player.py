#!/usr/bin/env python3
import argparse
import array
from contextlib import ExitStack
import fcntl
import json
import math
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
PIR_WARMUP_SECONDS = 60
READ_SECONDS = 3
BLACK_SECONDS = 3


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


class PlayerClosed(Exception):
    pass


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
                    "--fullscreen", "--no-osc", "--osd-level=0", "--volume=100",
                    "--input-default-bindings=no", "--cursor-autohide=always",
                    "--keep-open=yes", "--keep-open-pause=no", "--image-display-duration=inf",
                    "--stop-screensaver=yes", "--input-terminal=no",
                    f"--script={ROOT / 'controls.lua'}",
                    "--msg-level=all=warn", f"--input-ipc-client=fd://{fd}",
                ],
                pass_fds=(fd,),
            )
        resources.callback(self.close)
        self.replies = resources.enter_context(self.socket.makefile("rb"))
        self.playback_failed = False

    def close(self):
        self.socket.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def command(self, *args):
        request = json.dumps({"command": args, "request_id": 1}) + "\n"
        try:
            self.socket.sendall(request.encode())
            for line in self.replies:
                message = json.loads(line)
                if message.get("event") == "end-file" and message.get("reason") == "error":
                    print(f"mpv kon het bestand niet afspelen: {message.get('file_error', message)}", flush=True)
                    self.playback_failed = True
                if message.get("request_id") == 1:
                    if args == ("get_property", "eof-reached") and message["error"] == "property unavailable":
                        return False
                    if message["error"] != "success":
                        raise RuntimeError(f"mpv {args[0]}: {message['error']}")
                    return message.get("data")
        except (BrokenPipeError, ConnectionResetError):
            pass

        code = self.process.wait(timeout=3)
        if code == 0:
            raise PlayerClosed
        raise RuntimeError(f"mpv heeft de verbinding gesloten (exitcode {code}).")


def open_sensor(resources, beam):
    from gpiozero import DigitalInputDevice
    from gpiozero.pins.lgpio import LGPIOFactory

    # Raspberry Pi 5 kernels expose RP1 as gpiochip4 or gpiochip0.
    chip = 4 if Path("/dev/gpiochip4").exists() else 0
    factory = LGPIOFactory(chip=chip)
    resources.callback(factory.close)
    return resources.enter_context(
        DigitalInputDevice(17, pull_up=beam, pin_factory=factory)
    )


def monitor_sensor(beam):
    with ExitStack() as resources:
        sensor = open_sensor(resources, beam)
        print("GPIO17 (fysieke pin 11). Stop met Ctrl+C.", flush=True)
        if not beam:
            print("Wacht na inschakelen 60 seconden en beweeg dan voor de sensor.", flush=True)
        previous = None
        while True:
            level = int(sensor.pin.state)
            if level != previous:
                print(f"GPIO17 = {level} ({'HOOG' if level else 'LAAG'})", flush=True)
                previous = level
            time.sleep(0.025)


def set_output_volume():
    try:
        subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "100%"], check=True, timeout=3)
        subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], check=True, timeout=3)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Kon het systeemvolume niet instellen: {error}", flush=True)


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
            sensor = open_sensor(resources, args.beam)

        set_output_volume()
        mixer.init(frequency=rate, size=-16, channels=channels, buffer=512, allowedchanges=0)
        resources.callback(mixer.quit)
        standby = mixer.Sound(buffer=pcm)
        standby.set_volume(1.0)
        temporary = resources.enter_context(tempfile.TemporaryDirectory())
        screen = Surface((1280, 720))
        screen.fill((0, 0, 0))
        black_image = str(Path(temporary) / "black.png")
        image.save(screen, black_image)
        font.init()
        resources.callback(font.quit)
        title = font.Font(None, 76).render(TITLE, True, (255, 255, 255))
        screen.blit(title, title.get_rect(center=screen.get_rect().center))
        standby_image = str(Path(temporary) / "standby.png")
        image.save(screen, standby_image)

        player = Player(resources)
        overlay = None

        def update_standby(status, number=""):
            nonlocal overlay
            current = (status, number)
            if current != overlay:
                player.command("script-message-to", "controls", "toutbien-standby", *current)
                overlay = current

        def show_standby():
            print("Standby", flush=True)
            player.command("loadfile", standby_image, "replace")
            standby.play(loops=-1)

        show_standby()
        update_standby("idle")

        warmup_left = 0
        if not (args.beam or args.test):
            uptime = time.clock_gettime(time.CLOCK_BOOTTIME)
            warmup_left = max(0, PIR_WARMUP_SECONDS - uptime)
        warming_up = warmup_left > 0
        deadline = time.monotonic() + warmup_left
        triggered = video_playing = stable = candidate = simulated = False
        absent_since = None
        next_eof_check = 0
        video_at = None
        standby_at = None
        changed_at = time.monotonic()
        if args.test:
            print("Enter = hoofd erin/eruit. Typ q en druk Enter om te stoppen.", flush=True)
        elif warming_up:
            print(f"PIR warmt nog {warmup_left:.0f} seconden op.", flush=True)
        else:
            print(f"Sensor klaar. GPIO17 = {int(sensor.pin.state)}.", flush=True)

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
                # Beide sensoraansluitingen gebruiken een fysiek hoog signaal als trigger.
                present = bool(sensor.pin.state)

            now = time.monotonic()
            if warming_up:
                if now < deadline:
                    continue
                warming_up = False
                print(f"PIR klaar. GPIO17 = {int(present)}.", flush=True)
            if present != candidate:
                candidate = present
                changed_at = now
            new_detection = False
            if candidate != stable and now - changed_at >= 0.12:
                stable = candidate
                new_detection = stable
                if not args.test:
                    print(f"GPIO17 = {int(stable)}.", flush=True)
                if not stable:
                    absent_since = changed_at
                    if triggered:
                        print(f"Reset na {RESET_SECONDS} seconden laag signaal.", flush=True)

            if absent_since is not None and now - absent_since >= RESET_SECONDS:
                if triggered:
                    print("Klaar voor volgende detectie.", flush=True)
                triggered = False
                video_at = None
                absent_since = None
                if video_playing:
                    show_standby()
                    video_playing = False

            if standby_at is not None and now >= standby_at:
                show_standby()
                standby_at = None

            if stable:
                absent_since = None
                if new_detection and not triggered and standby_at is None:
                    triggered = True
                    video_at = now + READ_SECONDS
                    print(f"Video start over {READ_SECONDS} seconden.", flush=True)

            if video_at is not None and now >= video_at:
                print("Video", flush=True)
                update_standby("hidden")
                standby.stop()
                player.playback_failed = False
                player.command("loadfile", str(VIDEO), "replace")
                video_playing = True
                video_at = None
                next_eof_check = now + 0.1

            if video_playing and now >= next_eof_check:
                next_eof_check = now + 0.1
                if player.command("get_property", "eof-reached") or player.playback_failed:
                    player.command("loadfile", black_image, "replace")
                    standby_at = time.monotonic() + BLACK_SECONDS
                    video_playing = False
                    triggered = False

            if not video_playing and standby_at is None:
                number = ""
                if video_at is not None:
                    seconds_left = min(READ_SECONDS, math.ceil(video_at - now))
                    number = str(seconds_left)
                update_standby("motion" if stable else "idle", number)

        if player.process.returncode != 0:
            raise RuntimeError(f"mpv is gestopt (exitcode {player.process.returncode}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Toutbien expo-speler")
    parser.add_argument("--beam", action="store_true", help="Gebruik een lichtsluis.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--test", action="store_true", help="Test met Enter in de terminal.")
    modes.add_argument("--sensor-test", action="store_true", help="Toon het ruwe GPIO17-signaal.")
    args = parser.parse_args()
    try:
        if args.sensor_test:
            monitor_sensor(args.beam)
        else:
            play(args)
    except (KeyboardInterrupt, PlayerClosed):
        pass
