#!/bin/bash
# WiFi AP問題修正スクリプト

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

log_info "WiFi AP問題を修正します..."

# 現在のWiFi状態確認
log_step "現在のWiFi状態確認"
echo "Current wlan0 config:"
ip addr show wlan0 | grep inet

# wpa_supplicant完全停止
log_step "wpa_supplicant完全停止"
systemctl stop wpa_supplicant
systemctl disable wpa_supplicant
pkill wpa_supplicant || true

# dhcpcd設定修正（APモード強制）
log_step "dhcpcd設定をAPモード専用に修正"
cat > /etc/dhcpcd.conf << 'EOF'
# AudioBridge-Pi WiFi AP configuration
# 通常のクライアント接続を無効化

# インターフェース設定
interface wlan0
static ip_address=192.168.4.1/24
nohook wpa_supplicant

# DHCPクライアント機能無効化
nodhcp

# IPv6無効化  
noipv6

# デフォルトゲートウェイ無効化
nogateway
EOF

# NetworkManager無効化（存在する場合）
if systemctl is-active NetworkManager >/dev/null 2>&1; then
    log_step "NetworkManager停止・無効化"
    systemctl stop NetworkManager
    systemctl disable NetworkManager
fi

# wlan0インターフェース強制リセット
log_step "wlan0インターフェース強制リセット"
ip link set wlan0 down
sleep 2
ip addr flush dev wlan0
ip link set wlan0 up
sleep 2

# 静的IP手動設定
log_step "静的IP手動設定"
ip addr add 192.168.4.1/24 dev wlan0
ip route add 192.168.4.0/24 dev wlan0 || true

log_info "New wlan0 config:"
ip addr show wlan0 | grep inet

# hostapd設定確認・修正
log_step "hostapd設定確認"
if [ ! -f /etc/hostapd/hostapd.conf ]; then
    log_error "hostapd.conf not found"
    exit 1
fi

# hostapd再起動
log_step "hostapd再起動"
systemctl stop hostapd
sleep 2

# hostapd設定テスト
log_info "hostapd設定テスト中..."
if hostapd -t /etc/hostapd/hostapd.conf; then
    log_info "✅ hostapd configuration is valid"
else
    log_error "❌ hostapd configuration error"
    exit 1
fi

systemctl start hostapd
sleep 3

# hostapd状態確認
if systemctl is-active hostapd >/dev/null; then
    log_info "✅ hostapd is running"
else
    log_error "❌ hostapd failed to start"
    systemctl status hostapd --no-pager -l
fi

# dnsmasq再起動
log_step "dnsmasq再起動"
systemctl restart dnsmasq
sleep 2

if systemctl is-active dnsmasq >/dev/null; then
    log_info "✅ dnsmasq is running"
else
    log_error "❌ dnsmasq failed to start"
fi

# APモード確認
log_step "APモード動作確認"
echo ""
echo "=== WiFi AP状態 ==="
echo "Interface: $(ip addr show wlan0 | grep 'inet ' | awk '{print $2}')"
echo "hostapd: $(systemctl is-active hostapd)"
echo "dnsmasq: $(systemctl is-active dnsmasq)"

# iwconfig確認（APモード表示）
if command -v iwconfig >/dev/null; then
    echo ""
    echo "=== iwconfig wlan0 ==="
    iwconfig wlan0 | grep -E "(Mode|ESSID|Frequency)"
fi

# 接続可能デバイス確認
echo ""
echo "=== 接続可能WiFiネットワーク一覧（近くのAndroidで確認） ==="
echo "SSID: AudioBridge-Pi"
echo "Password: audiobridge123"
echo "IP Range: 192.168.4.10-192.168.4.100"

log_info "WiFi AP修正完了！"
log_info "AndroidでWiFi設定を開いて 'AudioBridge-Pi' が表示されるか確認してください"