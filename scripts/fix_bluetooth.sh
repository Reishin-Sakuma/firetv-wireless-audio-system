#!/bin/bash
# Bluetooth問題修正スクリプト

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

log_info "Bluetooth問題を修正します..."

# Bluetoothサービス再起動
log_step "Bluetoothサービス再起動"
systemctl restart bluetooth
sleep 3

if systemctl is-active bluetooth >/dev/null; then
    log_info "✅ Bluetooth service is running"
else
    log_error "❌ Bluetooth service failed to start"
    exit 1
fi

# BlueZ設定適用
log_step "BlueZ設定確認・適用"
if [ -f /etc/bluetooth/main.conf ]; then
    log_info "BlueZ main.conf found"
    
    # 設定内容確認
    echo "Device Name: $(grep '^Name' /etc/bluetooth/main.conf | cut -d= -f2 | tr -d ' ')"
    echo "Class: $(grep '^Class' /etc/bluetooth/main.conf | cut -d= -f2 | tr -d ' ')"
    echo "Discoverable: $(grep '^Discoverable' /etc/bluetooth/main.conf | cut -d= -f2 | tr -d ' ')"
else
    log_error "/etc/bluetooth/main.conf not found"
fi

# bluetoothctl自動設定
log_step "bluetoothctl自動設定実行"

# bluetoothctl対話セッション
timeout 30 bluetoothctl <<EOF
power on
discoverable on
pairable on
agent NoInputNoOutput
default-agent
quit
EOF

sleep 2

# 設定確認
log_step "Bluetooth設定確認"
echo ""
echo "=== Bluetooth Controller Status ==="
timeout 10 bluetoothctl show | head -15

# hciconfig確認（より詳細）
if command -v hciconfig >/dev/null; then
    echo ""
    echo "=== hciconfig ==="
    hciconfig hci0 | grep -E "(UP|RUNNING|PSCAN|ISCAN)"
    
    # 強制的にDiscoverable有効化
    log_step "hciconfig経由でDiscoverable強制有効化"
    hciconfig hci0 up
    hciconfig hci0 piscan  # Page scan + Inquiry scan
    
    sleep 2
    echo "After hciconfig piscan:"
    hciconfig hci0 | grep -E "(UP|RUNNING|PSCAN|ISCAN)"
fi

# D-Bus経由での設定（念のため）
log_step "D-Bus経由でのBluetooth設定"
if command -v dbus-send >/dev/null; then
    # Powered On
    dbus-send --system --dest=org.bluez --type=method_call /org/bluez/hci0 org.freedesktop.DBus.Properties.Set string:"org.bluez.Adapter1" string:"Powered" variant:boolean:true 2>/dev/null || log_warn "D-Bus Powered failed"
    
    # Discoverable On
    dbus-send --system --dest=org.bluez --type=method_call /org/bluez/hci0 org.freedesktop.DBus.Properties.Set string:"org.bluez.Adapter1" string:"Discoverable" variant:boolean:true 2>/dev/null || log_warn "D-Bus Discoverable failed"
    
    # Pairable On
    dbus-send --system --dest=org.bluez --type=method_call /org/bluez/hci0 org.freedesktop.DBus.Properties.Set string:"org.bluez.Adapter1" string:"Pairable" variant:boolean:true 2>/dev/null || log_warn "D-Bus Pairable failed"
    
    sleep 2
fi

# 最終確認
log_step "最終Bluetooth状態確認"
echo ""
echo "=== Final Bluetooth Status ==="
timeout 10 bluetoothctl show | grep -E "(Powered|Discoverable|Pairable|Name)"

# Bluetoothスキャン可能状態テスト
echo ""
echo "=== Bluetooth Visibility Test ==="
if timeout 5 hcitool scan >/dev/null 2>&1; then
    log_info "✅ Bluetooth scanning works"
else
    log_warn "❌ Bluetooth scanning may not work"
fi

log_info "Bluetooth修正完了！"
log_info ""
log_info "AndroidでBluetooth設定を開いて 'AudioBridge-Pi' が表示されるか確認してください"
log_info "表示されない場合は、Android側でBluetoothをOFF→ONしてから再度スキャンしてください"