#!/bin/bash
# AudioBridge-Pi 診断スクリプト

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

log_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

echo "========================================="
echo "AudioBridge-Pi システム診断"
echo "========================================="

# システム基本情報
log_check "システム情報"
echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '"')"
echo "Kernel: $(uname -r)"
echo "Hardware: $(cat /proc/device-tree/model 2>/dev/null || echo 'Unknown')"
echo ""

# WiFi診断
log_check "WiFi インターフェース状態"
if ip link show wlan0 >/dev/null 2>&1; then
    echo "✅ wlan0 interface found"
    ip addr show wlan0 | grep -E "(inet |UP|DOWN)"
else
    log_error "❌ wlan0 interface not found"
fi

echo ""
log_check "rfkill状態"
rfkill list

echo ""
log_check "hostapd サービス状態"
echo "Enabled: $(systemctl is-enabled hostapd 2>/dev/null || echo 'unknown')"
echo "Active: $(systemctl is-active hostapd 2>/dev/null || echo 'unknown')"

if systemctl status hostapd --no-pager -l; then
    echo "✅ hostapd status OK"
else
    log_error "❌ hostapd has issues"
fi

echo ""
log_check "hostapd 設定確認"
if [ -f /etc/hostapd/hostapd.conf ]; then
    echo "✅ hostapd.conf exists"
    echo "SSID: $(grep '^ssid=' /etc/hostapd/hostapd.conf | cut -d= -f2)"
    echo "Interface: $(grep '^interface=' /etc/hostapd/hostapd.conf | cut -d= -f2)"
    echo "Channel: $(grep '^channel=' /etc/hostapd/hostapd.conf | cut -d= -f2)"
else
    log_error "❌ /etc/hostapd/hostapd.conf not found"
fi

echo ""
log_check "dnsmasq サービス状態"
echo "Enabled: $(systemctl is-enabled dnsmasq 2>/dev/null || echo 'unknown')"
echo "Active: $(systemctl is-active dnsmasq 2>/dev/null || echo 'unknown')"
systemctl status dnsmasq --no-pager -l

echo ""
log_check "Bluetooth診断"
echo "Bluetooth service enabled: $(systemctl is-enabled bluetooth 2>/dev/null || echo 'unknown')"
echo "Bluetooth service active: $(systemctl is-active bluetooth 2>/dev/null || echo 'unknown')"

if command -v bluetoothctl >/dev/null; then
    echo "✅ bluetoothctl available"
    
    # Bluetooth power状態
    timeout 5 bluetoothctl show | grep -E "(Powered|Discoverable|Pairable)" || log_warn "bluetoothctl timeout"
else
    log_error "❌ bluetoothctl not found"
fi

echo ""
log_check "Audio-Bridge アプリケーション"
echo "Service enabled: $(systemctl is-enabled audio-bridge 2>/dev/null || echo 'unknown')"  
echo "Service active: $(systemctl is-active audio-bridge 2>/dev/null || echo 'unknown')"

if [ -f /usr/local/bin/audio-bridge ]; then
    echo "✅ audio-bridge executable exists"
else
    log_error "❌ /usr/local/bin/audio-bridge not found"
fi

if [ -d /opt/audio-bridge-pi ]; then
    echo "✅ application directory exists"
    ls -la /opt/audio-bridge-pi/
else
    log_error "❌ /opt/audio-bridge-pi directory not found"
fi

echo ""
log_check "ネットワーク設定"
if [ -f /etc/dhcpcd.conf ]; then
    echo "dhcpcd.conf wlan0 static IP:"
    grep -A3 "interface wlan0" /etc/dhcpcd.conf || log_warn "No wlan0 static config found"
else
    log_warn "/etc/dhcpcd.conf not found"
fi

echo ""
log_check "プロセス確認"
echo "hostapd process:"
pgrep -f hostapd || log_warn "hostapd process not running"

echo "dnsmasq process:"  
pgrep -f dnsmasq || log_warn "dnsmasq process not running"

echo "audio-bridge process:"
pgrep -f audio-bridge || log_warn "audio-bridge process not running"

echo ""
log_check "ポート確認"
echo "Port 8080 (HTTP server):"
if netstat -tlnp | grep :8080; then
    echo "✅ Port 8080 is listening"
else
    log_warn "❌ Port 8080 not listening"
fi

echo ""
log_check "最新ログ (last 20 lines)"
echo "--- hostapd logs ---"
journalctl -u hostapd --no-pager -n 10 2>/dev/null || log_warn "No hostapd logs"

echo "--- audio-bridge logs ---"
journalctl -u audio-bridge --no-pager -n 10 2>/dev/null || log_warn "No audio-bridge logs"

echo ""
log_info "診断完了。問題がある場合は上記の❌項目を確認してください。"