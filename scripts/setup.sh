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

# Python 3.11+ 対応：仮想環境またはシステムパッケージを使用
if python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
    log_info "Python 3.11+ 検出 - システムパッケージ経由でインストール"
    
    # システムパッケージでインストール可能な依存関係
    apt install -y \
        python3-flask \
        python3-dbus \
        python3-gi \
        python3-gi-cairo \
        python3-psutil \
        python3-yaml \
        python3-pip \
        python3-venv
    
    # pip専用パッケージは仮想環境で対処
    log_info "pip専用パッケージをインストール中..."
    
    # システム用仮想環境作成
    python3 -m venv /opt/audio-bridge-venv --system-site-packages
    /opt/audio-bridge-venv/bin/pip install pulsectl netifaces
    
    # pip警告を回避（最終手段として--break-system-packagesも併用）
    pip3 install --break-system-packages --quiet pulsectl netifaces 2>/dev/null || true
    
else
    log_info "Python 3.10以下 - pip経由でインストール"
    pip3 install -r requirements.txt
fi

# Bluetoothサービス設定
log_step "Bluetooth設定中..."
systemctl enable bluetooth
systemctl start bluetooth

# オーディオグループに現在のユーザー追加
log_step "オーディオ権限設定中..."

# 現在のユーザー名を取得（sudo実行時の元ユーザー）
if [ -n "$SUDO_USER" ]; then
    AUDIO_USER="$SUDO_USER"
elif [ -n "$USER" ]; then
    AUDIO_USER="$USER"
else
    # フォールバック：最初の1000番台UID取得
    AUDIO_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 2000 { print $1; exit }')
fi

if [ -z "$AUDIO_USER" ]; then
    log_warn "適切なユーザーが見つかりません。手動で権限設定してください"
    AUDIO_USER="$USER"
fi

log_info "ユーザー '$AUDIO_USER' にオーディオ権限を付与中..."

# ユーザー存在確認
if id "$AUDIO_USER" >/dev/null 2>&1; then
    usermod -a -G audio "$AUDIO_USER"
    usermod -a -G bluetooth "$AUDIO_USER"
    log_info "ユーザー '$AUDIO_USER' を audio, bluetooth グループに追加しました"
else
    log_error "ユーザー '$AUDIO_USER' が存在しません"
    log_info "利用可能なユーザー: $(getent passwd | awk -F: '$3 >= 1000 { print $1 }' | tr '\n' ' ')"
    exit 1
fi

# 設定ファイルコピー
log_step "設定ファイルをコピー中..."

# Bluetooth設定
cp config/bluetooth/main.conf /etc/bluetooth/
systemctl restart bluetooth

# PulseAudio設定
mkdir -p "/home/$AUDIO_USER/.pulse"
cp config/pulseaudio/default.pa /etc/pulse/
cp config/pulseaudio/daemon.conf /etc/pulse/
chown -R "$AUDIO_USER:$AUDIO_USER" "/home/$AUDIO_USER/.pulse"

# hostapd設定
cp config/hostapd/hostapd.conf /etc/hostapd/
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd

# hostapd マスク解除（設定時点で実行）
systemctl unmask hostapd 2>/dev/null || true

# dnsmasq設定
cp config/dnsmasq/dnsmasq.conf /etc/dnsmasq.d/audiobridge.conf

# systemd サービス設定
cp config/systemd/audio-bridge.service /etc/systemd/system/

# ユーザー名をサービスファイルに設定
sed -i "s/User=%i/User=$AUDIO_USER/" /etc/systemd/system/audio-bridge.service

systemctl daemon-reload

# wpa_supplicant無効化（AP Mode用）
log_step "WiFi設定中..."
systemctl disable wpa_supplicant
systemctl stop wpa_supplicant

# WiFiデバイスのブロック解除
log_info "WiFiデバイスのブロック状態を確認中..."
rfkill unblock wlan 2>/dev/null || log_warn "rfkill unblock failed - continuing"
rfkill unblock wifi 2>/dev/null || log_warn "rfkill wifi unblock failed - continuing"

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

# hostapd のマスク解除（Raspberry Pi OS対応）
log_info "hostapd サービスのマスクを解除中..."
systemctl unmask hostapd
systemctl enable hostapd

# dnsmasq有効化
systemctl enable dnsmasq

# audio-bridge サービス有効化
systemctl enable audio-bridge

log_info "全サービスが有効化されました"

# アプリケーションインストール
log_step "アプリケーションをインストール中..."

# アプリケーション用ディレクトリ作成
mkdir -p /opt/audio-bridge-pi
cp -r audio_bridge /opt/audio-bridge-pi/
cp -r config /opt/audio-bridge-pi/
cp requirements.txt /opt/audio-bridge-pi/
cp setup.py /opt/audio-bridge-pi/
chown -R "$AUDIO_USER:$AUDIO_USER" /opt/audio-bridge-pi

# 実行可能バイナリ作成
cat > /usr/local/bin/audio-bridge << EOF
#!/bin/bash
cd /opt/audio-bridge-pi
export PYTHONPATH="/opt/audio-bridge-pi:\$PYTHONPATH"

# 仮想環境があれば使用
if [ -f /opt/audio-bridge-venv/bin/python3 ]; then
    /opt/audio-bridge-venv/bin/python3 -m audio_bridge.main "\$@"
else
    python3 -m audio_bridge.main "\$@"
fi
EOF

chmod +x /usr/local/bin/audio-bridge

log_info "AudioBridge-Pi を /opt/audio-bridge-pi にインストールしました"

# ログディレクトリ作成
mkdir -p /var/log/audio-bridge
chown "$AUDIO_USER:$AUDIO_USER" /var/log/audio-bridge

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