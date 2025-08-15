#!/bin/bash
# 音声パイプライン問題修正スクリプト

# カラー出力定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Root権限確認
if [[ $EUID -ne 0 ]]; then
   log_error "このスクリプトはroot権限で実行してください: sudo $0"
   exit 1
fi

# ユーザー確認
AUDIO_USER="${SUDO_USER:-pi}"

log_info "音声パイプライン問題を修正します..."
log_info "対象ユーザー: $AUDIO_USER"

# 1. Raspberry Pi Zero 2W 音声出力無効化
log_step "Raspberry Pi 内蔵音声出力を無効化（ノイズ対策）"

# /boot/config.txt で音声出力無効化
if [ -f /boot/config.txt ]; then
    # 既存の音声設定をコメントアウト
    sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' /boot/config.txt
    
    # 音声無効化設定追加
    if ! grep -q "dtparam=audio=off" /boot/config.txt; then
        echo "# AudioBridge-Pi: 内蔵音声無効化" >> /boot/config.txt
        echo "dtparam=audio=off" >> /boot/config.txt
        log_info "内蔵音声出力を無効化しました"
    fi
fi

# /boot/firmware/config.txt も確認（新しいRaspberry Pi OS）
if [ -f /boot/firmware/config.txt ]; then
    sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' /boot/firmware/config.txt
    
    if ! grep -q "dtparam=audio=off" /boot/firmware/config.txt; then
        echo "# AudioBridge-Pi: 内蔵音声無効化" >> /boot/firmware/config.txt
        echo "dtparam=audio=off" >> /boot/firmware/config.txt
        log_info "内蔵音声出力を無効化しました（firmware）"
    fi
fi

# 2. PulseAudio設定修正
log_step "PulseAudio設定修正"

# システム用PulseAudio設定
cat > /etc/pulse/system.pa << 'EOF'
#!/usr/bin/pulseaudio -nF
# AudioBridge-Pi システム用PulseAudio設定

# 基本モジュール
load-module module-device-restore
load-module module-stream-restore
load-module module-card-restore

# Bluetooth専用設定
load-module module-bluetooth-discover
load-module module-bluetooth-policy

# Unix socket
load-module module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulse-socket

# TCP（ローカルのみ）
load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1;192.168.4.0/24

# 内蔵オーディオ無効化
# load-module module-alsa-sink
# load-module module-alsa-source

# デフォルトシンクなし（Bluetoothのみ使用）
# set-default-sink 
EOF

# ユーザー用PulseAudio設定
mkdir -p "/home/$AUDIO_USER/.config/pulse"
cat > "/home/$AUDIO_USER/.config/pulse/default.pa" << 'EOF'
#!/usr/bin/pulseaudio -nF
# AudioBridge-Pi ユーザー用PulseAudio設定

# 基本モジュール  
load-module module-device-restore
load-module module-stream-restore
load-module module-card-restore

# Bluetooth専用
load-module module-bluetooth-discover
load-module module-bluetooth-policy

# Unix protocol
load-module module-native-protocol-unix

# 内蔵オーディオ明示的に無効化
# load-module module-alsa-sink
# load-module module-alsa-source

# Bluetoothデバイス自動接続
load-module module-switch-on-port-available
EOF

# daemon.conf
cat > "/home/$AUDIO_USER/.config/pulse/daemon.conf" << 'EOF'
# AudioBridge-Pi PulseAudio daemon設定

# システム設定
daemonize = no
fail = yes
high-priority = yes
nice-level = -11
realtime-scheduling = yes
realtime-priority = 5

# 音声品質（Bluetooth専用）
default-sample-format = s16le
default-sample-rate = 44100
alternate-sample-rate = 48000
default-sample-channels = 2

# レイテンシ設定
default-fragments = 4
default-fragment-size-msec = 25

# ログ
log-target = syslog
log-level = notice

# 自動終了無効化（常駐）
exit-idle-time = -1
EOF

chown -R "$AUDIO_USER:$AUDIO_USER" "/home/$AUDIO_USER/.config"

# 3. PulseAudioサービス設定
log_step "PulseAudioサービス設定"

# システムモードでPulseAudio起動
systemctl --global disable pulseaudio.service pulseaudio.socket 2>/dev/null || true

# システム用PulseAudio service作成
cat > /etc/systemd/system/pulseaudio-system.service << EOF
[Unit]
Description=PulseAudio Sound System (System Mode)
Documentation=man:pulseaudio(1)
After=bluetooth.service
Wants=bluetooth.service

[Service]
Type=notify
ExecStart=/usr/bin/pulseaudio --system --realtime --disallow-exit --no-cpu-limit --file=/etc/pulse/system.pa
Restart=on-failure
RestartSec=5
User=pulse
Group=audio

[Install]
WantedBy=multi-user.target
EOF

# pulseユーザーをaudioグループに追加
usermod -a -G audio pulse
usermod -a -G bluetooth pulse

# 4. GStreamer設定確認・修正
log_step "GStreamer設定確認"

# GStreamerプラグイン確認
log_info "GStreamer プラグイン確認中..."
missing_plugins=()

for plugin in pulsesrc audioconvert audioresample lamemp3enc; do
    if ! gst-inspect-1.0 $plugin >/dev/null 2>&1; then
        missing_plugins+=($plugin)
        log_warn "Missing plugin: $plugin"
    else
        log_info "✅ Plugin available: $plugin"
    fi
done

if [ ${#missing_plugins[@]} -gt 0 ]; then
    log_error "Missing GStreamer plugins: ${missing_plugins[*]}"
    log_info "Installing additional GStreamer plugins..."
    
    apt install -y \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-libav \
        gstreamer1.0-pulseaudio
fi

# 5. ALSA設定（内蔵音声無効化）
log_step "ALSA設定（内蔵音声無効化）"

cat > /etc/asound.conf << 'EOF'
# AudioBridge-Pi ALSA設定
# 内蔵音声無効化、Bluetooth専用

# デフォルトカード無効化
# pcm.!default {
#     type pulse
# }
# ctl.!default {
#     type pulse
# }

# Bluetooth専用設定
defaults.bluealsa.interface "hci0"
defaults.bluealsa.device "00:00:00:00:00:00"
defaults.bluealsa.profile "a2dp"
EOF

# 6. サービス再起動
log_step "音声関連サービス再起動"

# PulseAudio停止・再起動
systemctl stop pulseaudio-system 2>/dev/null || true
killall pulseaudio 2>/dev/null || true
sleep 2

# システムPulseAudio有効化・起動
systemctl enable pulseaudio-system
systemctl start pulseaudio-system

sleep 3

# Bluetooth再起動
systemctl restart bluetooth
sleep 2

# 7. 動作確認
log_step "音声システム動作確認"

echo ""
echo "=== PulseAudio Status ==="
if systemctl is-active pulseaudio-system >/dev/null; then
    log_info "✅ PulseAudio system service running"
else
    log_error "❌ PulseAudio system service not running"
fi

echo ""
echo "=== Available Audio Sources ==="
timeout 10 sudo -u pulse pactl list sources short 2>/dev/null || log_warn "pactl sources check failed"

echo ""
echo "=== GStreamer Pipeline Test ==="
log_info "Testing basic GStreamer pipeline..."

# 基本パイプラインテスト
timeout 5 gst-launch-1.0 audiotestsrc freq=440 ! audioconvert ! fakesink 2>/dev/null
if [ $? -eq 0 ]; then
    log_info "✅ Basic GStreamer pipeline works"
else
    log_warn "⚠️ Basic GStreamer pipeline may have issues"
fi

echo ""
log_info "音声パイプライン修正完了！"
log_info ""
log_info "次のステップ:"
log_info "1. sudo reboot でシステム再起動"
log_info "2. Android Bluetooth接続"
log_info "3. 修正版音声ストリーミングテスト"
log_info ""
log_info "Raspberry Piからノイズが出なくなり、"
log_info "GStreamerパイプラインが正常動作するはずです。"