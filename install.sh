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

sudo apt-get update
sudo apt-get install -y mpv python3-pygame python3-gpiozero python3-lgpio

install -d "$app_dir/audio" "$app_dir/video" "$autostart_dir"
install -m 644 "$project_dir/player.py" "$app_dir/player.py"
install -m 644 "$project_dir/fade.lua" "$app_dir/fade.lua"
install -m 644 "$project_dir/audio/standbysound.wav" "$app_dir/audio/standbysound.wav"
install -m 644 "$project_dir/video/productvideo.mp4" "$app_dir/video/productvideo.mp4"

cat > "$app_dir/start.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
state_dir="\${XDG_STATE_HOME:-\$HOME/.local/state}/toutbien"
mkdir -p "\$state_dir"
exec /usr/bin/python3 "\$(dirname -- "\${BASH_SOURCE[0]}")/player.py"$mode >> "\$state_dir/player.log" 2>&1
EOF
chmod 755 "$app_dir/start.sh"

cat > "$autostart_dir/toutbien.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Toutbien expo-speler
Exec="$app_dir/start.sh"
Terminal=false
EOF

echo "Geïnstalleerd. De speler start automatisch bij de volgende desktoplogin."
echo 'Direct starten vanuit een terminal op het Pi-bureaublad: bash ~/.local/share/toutbien/start.sh'
