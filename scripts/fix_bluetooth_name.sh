#!/bin/bash
# Bluetoothデバイス名修正スクリプト

# カラー出力定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Root権限確認
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[ERROR]${NC} このスクリプトはroot権限で実行してください: sudo $0"
   exit 1
fi

log_info "Bluetoothデバイス名を 'AudioBridge-Pi' に変更します..."

# 現在のBluetoothデバイス名確認
log_step "現在のBluetoothデバイス名確認"
echo "Current name: $(timeout 5 bluetoothctl show | grep 'Name:' | cut -d: -f2 | xargs)"

# /etc/bluetooth/main.conf 修正
log_step "BlueZ設定ファイル修正"
if [ -f /etc/bluetooth/main.conf ]; then
    # バックアップ作成
    cp /etc/bluetooth/main.conf /etc/bluetooth/main.conf.backup
    
    # Name設定を確実に追加/修正
    if grep -q "^Name" /etc/bluetooth/main.conf; then
        sed -i 's/^Name.*/Name = AudioBridge-Pi/' /etc/bluetooth/main.conf
        log_info "既存のName設定を更新しました"
    else
        # [General]セクションの後にName追加
        sed -i '/^\[General\]/a Name = AudioBridge-Pi' /etc/bluetooth/main.conf
        log_info "Name設定を追加しました"
    fi
    
    echo "Updated main.conf Name setting:"
    grep "^Name" /etc/bluetooth/main.conf || echo "Name setting not found"
else
    log_info "main.conf not found, creating basic configuration..."
    cat > /etc/bluetooth/main.conf << 'EOF'
[General]
Name = AudioBridge-Pi
Class = 0x200414
DiscoverableTimeout = 0
PairableTimeout = 0
Discoverable = true
Pairable = true
AutoEnable = true

[Policy]
AutoConnect = true
EOF
fi

# ホスト名も確認・修正（影響する場合）
log_step "ホスト名確認"
current_hostname=$(hostname)
echo "Current hostname: $current_hostname"

if [ "$current_hostname" != "audiobridge-pi" ]; then
    log_info "ホスト名も変更しますか？ (Y/n)"
    read -r -t 10 response || response="n"
    
    if [[ $response =~ ^[Yy]$ ]]; then
        echo "audiobridge-pi" > /etc/hostname
        sed -i "s/127.0.1.1.*/127.0.1.1\taudiobridge-pi/" /etc/hosts
        log_info "ホスト名を audiobridge-pi に変更しました（再起動後有効）"
    fi
fi

# Bluetoothサービス再起動
log_step "Bluetoothサービス再起動"
systemctl restart bluetooth
sleep 3

# bluetoothctl経由でデバイス名設定
log_step "bluetoothctl経由でデバイス名設定"
timeout 15 bluetoothctl <<EOF
power off
power on
system-alias AudioBridge-Pi
discoverable on
pairable on
quit
EOF

sleep 2

# hciconfig経由でデバイス名設定（追加確認）
if command -v hciconfig >/dev/null; then
    log_step "hciconfig経由でデバイス名確認"
    hciconfig hci0 name "AudioBridge-Pi" 2>/dev/null || log_info "hciconfig name setting may not be supported"
fi

# 設定確認
log_step "設定確認"
echo ""
echo "=== Updated Bluetooth Configuration ==="
timeout 10 bluetoothctl show | grep -E "(Name|Alias|Powered|Discoverable)"

echo ""
echo "=== BlueZ Configuration File ==="
grep -E "(^Name|^Class|^Discoverable)" /etc/bluetooth/main.conf 2>/dev/null || echo "Settings not found in config file"

log_info "Bluetoothデバイス名修正完了！"
log_info ""
log_info "確認方法:"
log_info "1. Android Bluetooth設定で古いデバイス('rei-raspi')を削除"
log_info "2. Bluetoothデバイススキャンを実行"
log_info "3. 'AudioBridge-Pi' として表示されることを確認"
log_info ""
log_info "変更が反映されない場合は再起動してください: sudo reboot"