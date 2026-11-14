#!/usr/bin/env python3
import argparse
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

from microphone import DEMO_THRESHOLD, TARGET_SPL, Microphone, monitor

ROOT = Path(__file__).resolve().parent
VIDEO = ROOT / "video" / "productvideo.mp4"
PORTRAIT_VIDEO = VIDEO.with_name("productvideoPortrait.mp4")
PORTRAIT_STILL = PORTRAIT_VIDEO.with_suffix(".png")
TITLE = "sorry voor het ongemak sebiet"
STANDBY_BACKGROUND = (243, 234, 220)
STANDBY_TEXT = (214, 19, 33)
RESET_SECONDS = 20
PIR_WARMUP_SECONDS = 60
READ_SECONDS = 3
BLACK_SECONDS = 3
MIC_PAUSE_SECONDS = 23.5
MIC_TIMEOUT_SECONDS = 30
SENSOR_DEBOUNCE_SECONDS = 0.12
PIR_REARM_SECONDS = 5
PIR_TRIGGER_SECONDS = 0.5
MIC_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "toutbien-mic-offset"


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
                    "--video-rotate=90",
                    "--loop-file=no", "--loop-playlist=no",
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
                    if args[0] == "get_property" and message["error"] == "property unavailable":
                        return None
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
        subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "60%"], check=True, timeout=3)
        subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], check=True, timeout=3)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Kon het systeemvolume niet instellen: {error}", flush=True)


def play(args):
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from pygame import Surface, font, image

    for path in (VIDEO, PORTRAIT_VIDEO, PORTRAIT_STILL):
        if not path.is_file():
            raise FileNotFoundError(path)

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
        temporary = resources.enter_context(tempfile.TemporaryDirectory())
        screen = Surface((1280, 720))
        screen.fill((0, 0, 0))
        black_image = str(Path(temporary) / "black.png")
        image.save(screen, black_image)
        font.init()
        resources.callback(font.quit)
        title_font = font.match_font("Obviously", bold=True)
        if title_font is None:
            title_font = font.match_font("DejaVu Sans", bold=True)
            print("Obviously ontbreekt. Standbytitel gebruikt DejaVu Sans.", flush=True)
        standby_image = str(Path(temporary) / "standby.png")
        screen.fill(STANDBY_BACKGROUND)
        size = 57
        title_face = font.Font(title_font, size)
        width = title_face.size(TITLE)[0]
        available = screen.get_width() - 96
        if width > available:
            title_face = font.Font(title_font, size * available // width)
        title = title_face.render(TITLE, True, STANDBY_TEXT)
        screen.blit(title, title.get_rect(center=screen.get_rect().center))
        image.save(screen, standby_image)

        player = Player(resources)
        mic = Microphone()
        resources.callback(mic.close)
        offset = float(MIC_CONFIG.read_text()) if MIC_CONFIG.is_file() else None
        if offset is not None and not math.isfinite(offset):
            raise ValueError("Invalid microphone calibration offset.")
        threshold = DEMO_THRESHOLD if offset is None else TARGET_SPL - offset
        waiting_for_voice = challenge_passed = False
        mic_deadline = None
        next_mic_update = 0

        def show_mic_meter(fraction):
            value = "hidden" if fraction is None else f"{fraction:.3f}"
            player.command("script-message-to", "controls", "toutbien-mic", value)

        def stop_listening():
            nonlocal waiting_for_voice, mic_deadline
            mic.close()
            waiting_for_voice = False
            mic_deadline = None
            show_mic_meter(None)

        overlay = None

        def update_standby(status, number=""):
            nonlocal overlay
            current = (status, number)
            if current != overlay:
                player.command("script-message-to", "controls", "toutbien-standby", *current)
                overlay = current

        portrait = True

        def show_standby():
            if waiting_for_voice:
                stop_listening()
            path = str(PORTRAIT_STILL) if portrait else standby_image
            player.command("stop")
            player.command("loadfile", path, "replace")
            print(f"Standby: {Path(path).name}", flush=True)

        def start_video():
            path = PORTRAIT_VIDEO if portrait else VIDEO
            print(f"Video: {path.name}", flush=True)
            update_standby("hidden")
            player.playback_failed = False
            player.command("loadfile", str(path), "replace")
            player.command("set_property", "pause", False)

        show_standby()
        update_standby("idle")

        warmup_left = 0
        if not (args.beam or args.test):
            uptime = time.clock_gettime(time.CLOCK_BOOTTIME)
            warmup_left = max(0, PIR_WARMUP_SECONDS - uptime)
        warming_up = warmup_left > 0
        deadline = time.monotonic() + warmup_left
        triggered = video_playing = stable = candidate = simulated = False
        sensor_ready = args.test
        rearm_seconds = SENSOR_DEBOUNCE_SECONDS
        trigger_seconds = SENSOR_DEBOUNCE_SECONDS if args.beam else PIR_TRIGGER_SECONDS
        absent_since = None
        next_eof_check = 0
        next_orientation_check = 0
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
            if now >= next_orientation_check:
                next_orientation_check = now + 0.1
                rotation = player.command("get_property", "video-rotate")
                if rotation in (90, 180) and portrait != (rotation == 90):
                    portrait = rotation == 90
                    if video_playing:
                        start_video()
                        challenge_passed = False
                        next_eof_check = now + 0.1
                    elif standby_at is None:
                        show_standby()

            if warming_up:
                if now < deadline:
                    continue
                warming_up = False
                candidate = present
                changed_at = now
                print(f"PIR klaar. GPIO17 = {int(present)}.", flush=True)
            if present != candidate:
                if candidate and not stable and sensor_ready and not args.test:
                    print(f"GPIO17: korte puls genegeerd ({now - changed_at:.2f} s).", flush=True)
                candidate = present
                changed_at = now
                if not sensor_ready and not args.test:
                    print(f"GPIO17 tijdens herinschakelen = {int(candidate)}.", flush=True)
            if not sensor_ready:
                if not candidate and now - changed_at >= rearm_seconds:
                    sensor_ready = True
                    stable = False
                    print(f"GPIO17 {rearm_seconds:g} s laag. Klaar voor nieuwe detectie.", flush=True)
                update_standby("motion" if candidate else "idle")
                continue

            new_detection = False
            debounce = trigger_seconds if candidate else SENSOR_DEBOUNCE_SECONDS
            if candidate != stable and now - changed_at >= debounce:
                stable = candidate
                new_detection = stable
                if not args.test:
                    print(f"GPIO17 = {int(stable)}.", flush=True)
                if not stable:
                    absent_since = changed_at
                    if challenge_passed:
                        print(f"Reset na {RESET_SECONDS} seconden laag signaal.", flush=True)

            if challenge_passed and not stable and absent_since is not None and now - absent_since >= RESET_SECONDS:
                if triggered:
                    print("Klaar voor volgende detectie.", flush=True)
                triggered = challenge_passed = False
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
                    video_at = now if portrait else now + READ_SECONDS
                    if not portrait:
                        print(f"Video start over {READ_SECONDS} seconden.", flush=True)

            if video_at is not None and now >= video_at:
                start_video()
                video_playing = True
                challenge_passed = False
                video_at = None
                next_eof_check = now + 0.1

            if video_playing and now >= next_eof_check:
                next_eof_check = now + 0.1
                if player.command("get_property", "eof-reached") or player.playback_failed:
                    if waiting_for_voice:
                        stop_listening()
                    player.command("loadfile", black_image, "replace")
                    standby_at = time.monotonic() + BLACK_SECONDS
                    video_playing = False
                    triggered = False

                elif not challenge_passed and not waiting_for_voice:
                    position = player.command("get_property", "time-pos")
                    if position is not None and position >= MIC_PAUSE_SECONDS:
                        player.command("set_property", "pause", True)
                        mic_deadline = time.monotonic() + MIC_TIMEOUT_SECONDS
                        player.command("seek", MIC_PAUSE_SECONDS, "absolute+exact")
                        waiting_for_voice = True
                        next_mic_update = now
                        show_mic_meter(0)
                        try:
                            mic.start()
                        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                            print(f"Microphone: {error}", flush=True)
                            mic.close()
                            show_mic_meter(0)

            if mic_deadline is not None and time.monotonic() >= mic_deadline:
                print("Microfoondrempel niet gehaald binnen 30 seconden.", flush=True)
                show_standby()
                video_playing = triggered = False
                sensor_ready = False
                video_at = None
                rearm_seconds = SENSOR_DEBOUNCE_SECONDS if args.beam else PIR_REARM_SECONDS
                print(f"Wacht op {rearm_seconds:g} s laag GPIO17-signaal.", flush=True)
                changed_at = time.monotonic()
                absent_since = None

            if waiting_for_voice and mic.process is not None:
                try:
                    level, passed = mic.measure(threshold)
                except (OSError, RuntimeError) as error:
                    print(f"Microphone: {error}", flush=True)
                    mic.close()
                    show_mic_meter(0)
                else:
                    if passed:
                        stop_listening()
                        challenge_passed = True
                        absent_since = None if stable else time.monotonic()
                        player.command("set_property", "pause", False)
                    elif level is not None and now >= next_mic_update:
                        next_mic_update = now + 0.04
                        fraction = min(1, max(0, (level - threshold + 35) / 35))
                        show_mic_meter(fraction)

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
    modes.add_argument("--mic-level", action="store_true", help="Toon het JBL-niveau in dBFS.")
    args = parser.parse_args()
    try:
        if args.mic_level:
            monitor()
        elif args.sensor_test:
            monitor_sensor(args.beam)
        else:
            play(args)
    except (KeyboardInterrupt, PlayerClosed):
        pass
