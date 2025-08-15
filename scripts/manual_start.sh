#!/bin/bash
# AudioBridge-Pi 手動起動スクリプト

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

log_info "AudioBridge-Pi サービス手動起動を開始..."

# WiFi設定
log_step "WiFi AP設定中..."

# wlan0インターフェースの強制UP
ip link set wlan0 up
sleep 2

# 静的IP強制設定
ip addr flush dev wlan0
ip addr add 192.168.4.1/24 dev wlan0
ip link set wlan0 up

log_info "wlan0 IP address: $(ip addr show wlan0 | grep 'inet ' | awk '{print $2}')"

# rfkill解除
log_step "WiFiブロック解除..."
rfkill unblock wlan
rfkill unblock wifi
rfkill list

# hostapd手動起動
log_step "hostapd 手動起動..."
systemctl stop hostapd
sleep 2

if [ -f /etc/hostapd/hostapd.conf ]; then
    log_info "hostapd設定ファイル確認 OK"
    
    # バックグラウンドでhostapd起動
    hostapd /etc/hostapd/hostapd.conf &
    HOSTAPD_PID=$!
    log_info "hostapd started with PID: $HOSTAPD_PID"
    
    # 起動待機
    sleep 5
    
    # プロセス確認
    if kill -0 $HOSTAPD_PID 2>/dev/null; then
        log_info "✅ hostapd is running"
    else
        log_error "❌ hostapd failed to start"
    fi
else
    log_error "/etc/hostapd/hostapd.conf not found"
fi

# dnsmasq起動
log_step "dnsmasq 起動..."
systemctl start dnsmasq
sleep 2
systemctl status dnsmasq --no-pager -l

# Bluetooth設定
log_step "Bluetooth設定中..."

# Bluetoothサービス確認
systemctl start bluetooth
sleep 2

# bluetoothctl自動設定
log_info "Bluetooth自動設定中..."
bluetoothctl <<EOF
power on
discoverable on
pairable on
agent NoInputNoOutput
default-agent
EOF

log_info "Bluetooth設定完了"

# Bluetooth状態確認
log_step "Bluetooth状態確認..."
timeout 5 bluetoothctl show || log_warn "bluetoothctl show timeout"

# Audio-Bridge起動
log_step "Audio-Bridge アプリケーション起動..."

if [ -f /usr/local/bin/audio-bridge ]; then
    # バックグラウンドで起動
    log_info "Starting audio-bridge application..."
    /usr/local/bin/audio-bridge &
    AUDIO_PID=$!
    log_info "audio-bridge started with PID: $AUDIO_PID"
    
    sleep 3
    
    # プロセス確認
    if kill -0 $AUDIO_PID 2>/dev/null; then
        log_info "✅ audio-bridge is running"
    else
        log_warn "❌ audio-bridge may have failed to start"
    fi
else
    log_error "/usr/local/bin/audio-bridge not found"
fi

# 最終状態確認
log_step "最終状態確認..."

echo ""
log_info "=== サービス状態 ==="
echo "hostapd PID: $(pgrep -f hostapd || echo 'Not running')"
echo "dnsmasq: $(systemctl is-active dnsmasq)"
echo "bluetooth: $(systemctl is-active bluetooth)"
echo "audio-bridge PID: $(pgrep -f audio-bridge || echo 'Not running')"

echo ""
log_info "=== ネットワーク状態 ==="
echo "wlan0 IP: $(ip addr show wlan0 | grep 'inet ' | awk '{print $2}' || echo 'No IP')"
echo "WiFi clients: $(iw dev wlan0 station dump | grep Station | wc -l)"

echo ""
log_info "=== Bluetooth状態 ==="
bluetoothctl show | head -10

echo ""
log_info "手動起動完了！"
log_info ""
log_info "Android接続テスト:"
log_info "1. WiFi: 'AudioBridge-Pi' (password: audiobridge123)"  
log_info "2. Bluetooth: 'AudioBridge-Pi' でペアリング"
log_info "3. HTTP: http://192.168.4.1:8080/audio.mp3"
log_info ""
log_info "停止する場合:"
log_info "sudo pkill hostapd"
log_info "sudo pkill audio-bridge"