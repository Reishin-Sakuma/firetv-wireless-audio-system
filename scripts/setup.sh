#!/bin/bash
# AudioBridge-Pi 自動セットアップスクリプト
# Raspberry Pi OS Lite 用

set -e

# カラー出力定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
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
   log_error "このスクリプトはroot権限で実行してください"
   exit 1
fi

# Raspberry Pi OS確認
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    log_warn "Raspberry Pi以外で実行されています"
fi

log_info "AudioBridge-Pi セットアップを開始します..."

# システムアップデート
log_step "システムアップデート..."
apt update && apt upgrade -y

# 必要パッケージのインストール
log_step "必要パッケージをインストール中..."
apt install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    bluetooth \
    bluez \
    bluez-tools \
    pulseaudio \
    pulseaudio-module-bluetooth \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    hostapd \
    dnsmasq \
    iptables-persistent \
    git

# Python依存関係インストール
log_step "Python依存関係をインストール中..."
pip3 install -r requirements.txt

# Bluetoothサービス設定
log_step "Bluetooth設定中..."
systemctl enable bluetooth
systemctl start bluetooth

# オーディオグループにpiユーザー追加
log_step "オーディオ権限設定中..."
usermod -a -G audio pi
usermod -a -G bluetooth pi

# 設定ファイルコピー
log_step "設定ファイルをコピー中..."

# Bluetooth設定
cp config/bluetooth/main.conf /etc/bluetooth/
systemctl restart bluetooth

# PulseAudio設定
mkdir -p /home/pi/.pulse
cp config/pulseaudio/default.pa /etc/pulse/
cp config/pulseaudio/daemon.conf /etc/pulse/
chown -R pi:pi /home/pi/.pulse

# hostapd設定
cp config/hostapd/hostapd.conf /etc/hostapd/
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd

# dnsmasq設定
cp config/dnsmasq/dnsmasq.conf /etc/dnsmasq.d/audiobridge.conf

# systemd サービス設定
cp config/systemd/audio-bridge.service /etc/systemd/system/
systemctl daemon-reload

# wpa_supplicant無効化（AP Mode用）
log_step "WiFi設定中..."
systemctl disable wpa_supplicant
systemctl stop wpa_supplicant

# ネットワーク設定
log_step "ネットワーク設定中..."
cat > /etc/dhcpcd.conf << 'EOF'
# AudioBridge-Pi network configuration
interface wlan0
static ip_address=192.168.4.1/24
nohook wpa_supplicant
EOF

# IP Forwarding有効化
echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

# iptables設定
log_step "ファイアウォール設定中..."
iptables -t nat -F
iptables -F
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT

# iptables保存
iptables-save > /etc/iptables/rules.v4

# サービス有効化
log_step "サービスを有効化中..."
systemctl enable hostapd
systemctl enable dnsmasq
systemctl enable audio-bridge

# アプリケーションインストール
log_step "アプリケーションをインストール中..."
python3 setup.py install

# ログディレクトリ作成
mkdir -p /var/log/audio-bridge
chown pi:pi /var/log/audio-bridge

# 完了メッセージ
log_info "セットアップが完了しました！"
log_info ""
log_info "次の手順で使用してください："
log_info "1. sudo reboot でシステム再起動"
log_info "2. AndroidデバイスでBluetoothペアリング: AudioBridge-Pi"
log_info "3. Fire TV StickでWiFi接続: AudioBridge-Pi (pass: audiobridge123)"
log_info "4. VLCで再生: http://192.168.4.1:8080/audio.mp3"
log_info ""
log_info "サービス確認: sudo systemctl status audio-bridge"
log_info "ログ確認: sudo journalctl -u audio-bridge -f"

# 再起動確認
read -p "今すぐ再起動しますか？ [y/N]: " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "システムを再起動しています..."
    reboot
else
    log_info "手動で再起動してください: sudo reboot"
fi