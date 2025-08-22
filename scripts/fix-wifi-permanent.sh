#!/bin/bash
# WiFi AP永続化修正スクリプト

set -e

echo "WiFi AP 永続化設定を開始します..."

# Root権限確認
if [[ $EUID -ne 0 ]]; then
   echo "エラー: このスクリプトはroot権限で実行してください"
   exit 1
fi

echo "1. WiFi競合サービスを無効化中..."
systemctl disable wpa_supplicant || true
systemctl stop wpa_supplicant || true

echo "2. rfkillの永続化設定..."
# 起動時にWiFiのブロックを解除
cat > /etc/systemd/system/unblock-wifi.service << 'EOF'
[Unit]
Description=Unblock WiFi at boot
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock wlan
ExecStart=/usr/sbin/rfkill unblock wifi
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl enable unblock-wifi.service

echo "3. wlan0 静的IP設定..."
# dhcpcd.confに追加
if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
    cat >> /etc/dhcpcd.conf << 'EOF'

# AudioBridge-Pi WiFi AP
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
fi

echo "4. hostapdサービス強制有効化..."
systemctl unmask hostapd
systemctl enable hostapd

echo "5. dnsmasq設定確認..."
systemctl enable dnsmasq

echo "永続化設定完了！"
echo ""
echo "再起動後の確認手順："
echo "1. sudo systemctl status hostapd"
echo "2. sudo systemctl status unblock-wifi"
echo "3. ip addr show wlan0"
echo ""
echo "今すぐ再起動しますか？ [y/N]"
read -r reply
if [[ $reply =~ ^[Yy]$ ]]; then
    echo "再起動中..."
    reboot
else
    echo "手動で再起動してください: sudo reboot"
fi