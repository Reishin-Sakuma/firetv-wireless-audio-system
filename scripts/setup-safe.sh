#!/bin/bash
# AudioBridge-Pi 安全セットアップスクリプト
# SSH接続維持・段階的設定版

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

log_info "AudioBridge-Pi 安全セットアップを開始します..."
log_warn "このスクリプトは段階的に実行され、手動での再起動が必要です"

# 現在の接続状態確認
CURRENT_CONNECTION=$(who am i | awk '{print $2}' | head -1)
if [[ $CURRENT_CONNECTION =~ pts/* ]]; then
    log_warn "SSH接続で実行されています。設定変更により切断される可能性があります"
    log_info "設定は段階的に行い、各段階で手動確認します"
fi

# 段階選択
echo "実行する段階を選択してください："
echo "1) パッケージインストール（安全）"
echo "2) 基本サービス設定（安全）" 
echo "3) ネットワーク設定（要注意：SSH切断リスク）"
echo "4) 最終設定・サービス開始（要再起動）"
echo "5) 全段階を順次実行（非推奨）"
read -p "段階を選択 [1-5]: " STAGE

case $STAGE in
    1)
        log_step "段階1: パッケージインストール"
        ;;
    2)
        log_step "段階2: 基本サービス設定"
        ;;
    3)
        log_step "段階3: ネットワーク設定（要注意）"
        ;;
    4)
        log_step "段階4: 最終設定"
        ;;
    5)
        log_step "全段階実行（非推奨）"
        ;;
    *)
        log_error "無効な選択です"
        exit 1
        ;;
esac

# 段階1: パッケージインストール
install_packages() {
    log_step "システムアップデート..."
    apt update && apt upgrade -y

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

    log_step "Python依存関係をインストール中..."
    # Python 3.11+ 対応
    if python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
        log_info "Python 3.11+ 検出 - システムパッケージ経由でインストール"
        
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
        python3 -m venv /opt/audio-bridge-venv --system-site-packages
        /opt/audio-bridge-venv/bin/pip install pulsectl netifaces
        
        # pip警告回避
        pip3 install --break-system-packages --quiet pulsectl netifaces 2>/dev/null || true
    else
        log_info "Python 3.10以下 - pip経由でインストール"
        pip3 install -r requirements.txt
    fi
    
    log_info "段階1完了: パッケージインストール成功"
}

# 段階2: 基本サービス設定
configure_basic_services() {
    log_step "Bluetooth設定中..."
    systemctl enable bluetooth
    systemctl start bluetooth

    log_step "オーディオ権限設定中..."
    # 現在のユーザー名を取得
    if [ -n "$SUDO_USER" ]; then
        AUDIO_USER="$SUDO_USER"
    elif [ -n "$USER" ]; then
        AUDIO_USER="$USER"
    else
        AUDIO_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 2000 { print $1; exit }')
    fi

    if [ -z "$AUDIO_USER" ]; then
        log_warn "適切なユーザーが見つかりません"
        AUDIO_USER="pi"
    fi

    log_info "ユーザー '$AUDIO_USER' にオーディオ権限を付与中..."
    if id "$AUDIO_USER" >/dev/null 2>&1; then
        usermod -a -G audio "$AUDIO_USER"
        usermod -a -G bluetooth "$AUDIO_USER"
        log_info "ユーザー '$AUDIO_USER' を audio, bluetooth グループに追加しました"
    else
        log_error "ユーザー '$AUDIO_USER' が存在しません"
        exit 1
    fi

    log_step "設定ファイルをコピー中..."
    # Bluetooth設定
    cp config/bluetooth/main.conf /etc/bluetooth/
    systemctl restart bluetooth

    # PulseAudio設定
    mkdir -p "/home/$AUDIO_USER/.pulse"
    cp config/pulseaudio/default.pa /etc/pulse/
    cp config/pulseaudio/daemon.conf /etc/pulse/
    chown -R "$AUDIO_USER:$AUDIO_USER" "/home/$AUDIO_USER/.pulse"

    log_info "段階2完了: 基本サービス設定成功"
}

# 段階3: ネットワーク設定（SSH切断リスク）
configure_network() {
    log_error "⚠️  警告: この段階はSSH接続を切断する可能性があります ⚠️"
    log_warn "物理アクセスまたはシリアル接続が利用できることを確認してください"
    
    read -p "続行しますか？ NetworkManagerを停止してWiFi APモードに切り替えます [y/N]: " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "ネットワーク設定をスキップしました"
        return 0
    fi

    log_step "ネットワーク設定の準備..."
    
    # 設定ファイルのバックアップ
    cp /etc/dhcpcd.conf /etc/dhcpcd.conf.backup || true
    cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup || true

    # hostapd設定
    cp config/hostapd/hostapd.conf /etc/hostapd/
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd

    # dnsmasq設定
    cp config/dnsmasq/dnsmasq.conf /etc/dnsmasq.d/audiobridge.conf

    log_warn "NetworkManagerを無効化します（SSH切断の可能性）"
    systemctl disable NetworkManager || true
    systemctl stop NetworkManager || true

    # wpa_supplicant無効化
    systemctl disable wpa_supplicant || true
    systemctl stop wpa_supplicant || true

    # WiFiデバイスのブロック解除
    rfkill unblock wlan 2>/dev/null || true
    rfkill unblock wifi 2>/dev/null || true

    log_step "dhcpcd設定..."
    cat > /etc/dhcpcd.conf << 'EOF'
# AudioBridge-Pi network configuration
# Static IP for wlan0 interface
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant

# Keep eth0 for SSH access during setup
interface eth0
    # Use DHCP for ethernet (if connected)
EOF

    # IP Forwarding有効化
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

    log_step "ファイアウォール設定中..."
    iptables -t nat -F
    iptables -F
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
    iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
    iptables -A INPUT -p tcp --dport 22 -j ACCEPT  # SSH保持

    # iptables保存
    mkdir -p /etc/iptables
    iptables-save > /etc/iptables/rules.v4

    log_warn "段階3完了: ネットワーク設定完了"
    log_warn "WiFiインターフェースの設定変更により、WiFi SSH接続が切断される可能性があります"
    log_info "有線接続またはコンソール接続で次の段階を実行してください"
}

# 段階4: 最終設定・サービス開始
finalize_setup() {
    log_step "サービスを有効化中..."

    # hostapd のマスク解除
    log_info "hostapd サービスのマスクを解除中..."
    systemctl unmask hostapd
    systemctl enable hostapd

    # dnsmasq有効化
    systemctl enable dnsmasq

    # systemd サービス設定
    cp config/systemd/audio-bridge.service /etc/systemd/system/
    
    # ユーザー名をサービスファイルに設定
    if [ -n "$SUDO_USER" ]; then
        AUDIO_USER="$SUDO_USER"
    else
        AUDIO_USER="pi"
    fi
    sed -i "s/User=%i/User=$AUDIO_USER/" /etc/systemd/system/audio-bridge.service
    systemctl daemon-reload

    # audio-bridge サービス有効化
    systemctl enable audio-bridge

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

    # ログディレクトリ作成
    mkdir -p /var/log/audio-bridge
    chown "$AUDIO_USER:$AUDIO_USER" /var/log/audio-bridge

    log_info "段階4完了: 最終設定完了"
    
    log_info "セットアップが完了しました！"
    log_info ""
    log_warn "⚠️  重要: システム再起動が必要です"
    log_info "再起動後の使用手順："
    log_info "1. AndroidデバイスでBluetoothペアリング: AudioBridge-Pi"
    log_info "2. Fire TV StickでWiFi接続: AudioBridge-Pi (pass: audiobridge123)"
    log_info "3. VLCで再生: http://192.168.4.1:8080/audio.mp3"
    log_info ""
    log_info "サービス確認: sudo systemctl status audio-bridge"
    log_info "ログ確認: sudo journalctl -u audio-bridge -f"
}

# メイン実行部分
case $STAGE in
    1)
        install_packages
        log_info "段階1完了。次は段階2を実行してください: sudo ./scripts/setup-safe.sh"
        ;;
    2)
        configure_basic_services
        log_info "段階2完了。次は段階3を実行してください: sudo ./scripts/setup-safe.sh"
        log_warn "段階3はSSH切断リスクがあります。物理アクセスを確保してください"
        ;;
    3)
        configure_network
        log_info "段階3完了。次は段階4を実行してください: sudo ./scripts/setup-safe.sh"
        log_warn "WiFi接続が切断された場合は、有線またはコンソール接続で段階4を実行してください"
        ;;
    4)
        finalize_setup
        echo
        read -p "今すぐ再起動しますか？ [y/N]: " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "システムを再起動しています..."
            reboot
        else
            log_info "手動で再起動してください: sudo reboot"
        fi
        ;;
    5)
        log_warn "全段階実行は非推奨です。問題が発生した場合はコンソールアクセスが必要です"
        read -p "続行しますか？ [y/N]: " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_packages
            configure_basic_services
            configure_network
            finalize_setup
        else
            log_info "中断されました"
        fi
        ;;
esac