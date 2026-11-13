#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} == 0 ]]; then
    echo "Voer bash install.sh uit als je gewone desktopgebruiker."
    exit 1
fi

mode=""
case "${1:-}" in
    "") ;;
    --beam) mode=" --beam" ;;
    *) echo "Gebruik: bash install.sh [--beam]"; exit 1 ;;
esac

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$HOME/.local/share/toutbien"
autostart_dir="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

sudo apt-get update
sudo apt-get install -y mpv python3-pygame python3-gpiozero python3-lgpio wireplumber xdg-user-dirs

install -d "$app_dir/audio" "$app_dir/video" "$autostart_dir" "$applications_dir"
video_copy=""
trap 'rm -f -- "$video_copy"' EXIT
for video in productvideo.mp4 productvideoPortrait.mp4; do
    video_copy="$(mktemp "$app_dir/video/.productvideo.XXXXXX")"
    install -m 644 "$project_dir/video/$video" "$video_copy"
    mv -f -- "$video_copy" "$app_dir/video/$video"
done

install -m 644 "$project_dir/player.py" "$app_dir/player.py"
install -m 644 "$project_dir/controls.lua" "$app_dir/controls.lua"
install -m 644 "$project_dir/audio/standbysound.wav" "$app_dir/audio/standbysound.wav"

cat > "$app_dir/start.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
state_dir="\${XDG_STATE_HOME:-\$HOME/.local/state}/toutbien"
mkdir -p "\$state_dir"
exec /usr/bin/python3 "\$(dirname -- "\${BASH_SOURCE[0]}")/player.py"$mode >> "\$state_dir/player.log" 2>&1
EOF
chmod 755 "$app_dir/start.sh"

launcher="$applications_dir/toutbien.desktop"
cat > "$launcher" <<EOF
[Desktop Entry]
Type=Application
Name=Toutbien expo-speler
Icon=applications-multimedia
Categories=AudioVideo;Player;
Exec="$app_dir/start.sh"
Terminal=false
EOF

install -m 644 "$launcher" "$autostart_dir/toutbien.desktop"

desktop_dir="$(xdg-user-dir DESKTOP)"
if [[ -n "$desktop_dir" && "$desktop_dir" != "$HOME" && -d "$desktop_dir" ]]; then
    install -m 755 "$launcher" "$desktop_dir/Toutbien.desktop"
fi

echo "Open Toutbien expo-speler via het bureaublad of het toepassingenmenu."
echo "Geïnstalleerd. De speler start automatisch bij de volgende desktoplogin."
echo 'Direct starten vanuit een terminal op het Pi-bureaublad: bash ~/.local/share/toutbien/start.sh'
