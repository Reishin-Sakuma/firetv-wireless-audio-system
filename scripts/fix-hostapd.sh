#!/bin/bash
# hostapd設定問題の診断・修正スクリプト

set -e

# カラー出力定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Root権限確認
if [[ $EUID -ne 0 ]]; then
   log_error "このスクリプトはroot権限で実行してください"
   exit 1
fi

log_info "hostapd設定問題の診断を開始します..."

# 1. hostapd設定ファイル確認
log_step "hostapd設定ファイル確認中..."
if [ -f /etc/hostapd/hostapd.conf ]; then
    log_info "hostapd.conf が存在します"
    echo "--- /etc/hostapd/hostapd.conf の内容 ---"
    cat /etc/hostapd/hostapd.conf
    echo "--- 設定ファイル終了 ---"
else
    log_error "hostapd.conf が存在しません"
    exit 1
fi

# 2. WiFiインターフェース確認
log_step "WiFiインターフェース確認中..."
log_info "利用可能なネットワークインターフェース:"
ip link show | grep -E "^[0-9]+:" | awk -F': ' '{print "  " $2}'

if ip link show wlan0 >/dev/null 2>&1; then
    log_info "wlan0 インターフェースが存在します"
    WLAN_STATUS=$(ip link show wlan0)
    echo "wlan0 状態: $WLAN_STATUS"
else
    log_error "wlan0 インターフェースが存在しません"
    log_info "別のWiFiインターフェースを探しています..."
    WIFI_INTERFACE=$(iw dev | awk '$1=="Interface"{print $2}' | head -1)
    if [ -n "$WIFI_INTERFACE" ]; then
        log_warn "WiFiインターフェース '$WIFI_INTERFACE' が見つかりました"
        log_info "hostapd.confを $WIFI_INTERFACE 用に更新しますか？ [y/N]"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            sed -i "s/interface=wlan0/interface=$WIFI_INTERFACE/" /etc/hostapd/hostapd.conf
            log_info "インターフェースを $WIFI_INTERFACE に変更しました"
        fi
    else
        log_error "WiFiインターフェースが見つかりません"
        exit 1
    fi
fi

# 3. rfkill状態確認
log_step "WiFi無線状態確認中..."
if command -v rfkill >/dev/null 2>&1; then
    log_info "rfkill 状態:"
    rfkill list
    
    # WiFiがブロックされている場合は解除
    if rfkill list | grep -q "Wireless LAN.*blocked: yes"; then
        log_warn "WiFiがブロックされています。解除します..."
        rfkill unblock wlan
        rfkill unblock wifi
        log_info "WiFiブロックを解除しました"
    fi
else
    log_warn "rfkill コマンドが利用できません"
fi

# 4. 競合するサービス確認・停止
log_step "競合するサービス確認中..."

# NetworkManager確認
if systemctl is-active --quiet NetworkManager; then
    log_warn "NetworkManager が実行中です。これはhostapd と競合します"
    log_info "NetworkManager を停止しますか？ [y/N]"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        systemctl stop NetworkManager
        systemctl disable NetworkManager
        log_info "NetworkManager を停止・無効化しました"
    fi
fi

# wpa_supplicant確認
if systemctl is-active --quiet wpa_supplicant; then
    log_warn "wpa_supplicant が実行中です。APモードと競合します"
    systemctl stop wpa_supplicant
    systemctl disable wpa_supplicant
    log_info "wpa_supplicant を停止・無効化しました"
fi

# 5. hostapd設定テスト
log_step "hostapd設定テスト中..."
log_info "hostapd設定の構文チェック..."

# hostapd設定テスト実行
if hostapd -t /etc/hostapd/hostapd.conf; then
    log_info "✅ hostapd設定ファイルは正常です"
else
    log_error "❌ hostapd設定ファイルにエラーがあります"
    
    log_step "設定ファイルを修正します..."
    
    # よくある問題の修正
    cp /etc/hostapd/hostapd.conf /etc/hostapd/hostapd.conf.backup
    
    # 修正版設定ファイル作成
    cat > /etc/hostapd/hostapd.conf << EOF
# AudioBridge-Pi hostapd 修正版設定
interface=wlan0
driver=nl80211
ssid=AudioBridge-Pi
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=audiobridge123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF
    
    log_info "修正版設定ファイルを作成しました"
    
    # 再テスト
    if hostapd -t /etc/hostapd/hostapd.conf; then
        log_info "✅ 修正後の設定ファイルは正常です"
    else
        log_error "❌ 修正後も設定ファイルにエラーがあります"
        
        # さらに基本的な設定に変更
        cat > /etc/hostapd/hostapd.conf << EOF
interface=wlan0
driver=nl80211
ssid=AudioBridge-Pi
hw_mode=g
channel=7
auth_algs=1
wpa=2
wpa_passphrase=audiobridge123
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF
        
        if hostapd -t /etc/hostapd/hostapd.conf; then
            log_info "✅ 最小構成での設定ファイルは正常です"
        else
            log_error "❌ 基本設定でもエラーが発生します。手動確認が必要です"
        fi
    fi
fi

# 6. dhcpcd設定確認
log_step "dhcpcd設定確認中..."
if [ -f /etc/dhcpcd.conf ]; then
    log_info "dhcpcd.conf の内容確認:"
    grep -A 5 -B 5 "interface wlan0\|static ip_address" /etc/dhcpcd.conf || true
    
    # 設定に問題がある場合の修正
    if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
        log_warn "dhcpcd.conf にwlan0設定がありません。追加します"
        cat >> /etc/dhcpcd.conf << EOF

# AudioBridge-Pi WiFi AP configuration
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
        log_info "dhcpcd.conf にwlan0設定を追加しました"
    fi
fi

# 7. デーモン設定確認
log_step "hostapd デーモン設定確認中..."
if [ -f /etc/default/hostapd ]; then
    log_info "/etc/default/hostapd の内容:"
    cat /etc/default/hostapd
else
    log_warn "/etc/default/hostapd が存在しません。作成します"
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
    log_info "hostapd デーモン設定を作成しました"
fi

# 8. サービス状態確認
log_step "サービス状態確認中..."
log_info "hostapd サービス状態:"
systemctl status hostapd --no-pager || true

log_info "dnsmasq サービス状態:"
systemctl status dnsmasq --no-pager || true

# 9. hostapd手動起動テスト
log_step "hostapd 手動起動テスト..."
log_warn "hostapd を手動で起動してテストします（Ctrl+Cで停止）"
log_info "テストを実行しますか？ [y/N]"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    log_info "hostapd を手動で起動中... (10秒後に自動停止)"
    timeout 10 hostapd -d /etc/hostapd/hostapd.conf || true
    log_info "手動テスト完了"
fi

# 10. 修復アクション
log_step "修復アクションの提案..."
log_info "以下の修復アクションを実行しますか？"
echo "1. hostapd サービスの再起動"
echo "2. dnsmasq サービスの再起動" 
echo "3. dhcpcd サービスの再起動"
echo "4. wlan0 インターフェースの再起動"
read -p "[y/N]: " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "修復アクションを実行中..."
    
    # サービス再起動
    systemctl restart dhcpcd || log_warn "dhcpcd再起動失敗"
    sleep 2
    
    systemctl restart hostapd || log_warn "hostapd再起動失敗"
    sleep 2
    
    systemctl restart dnsmasq || log_warn "dnsmasq再起動失敗"
    sleep 2
    
    # インターフェース状態確認
    ip addr show wlan0 || log_warn "wlan0状態確認失敗"
    
    log_info "修復アクション完了"
    
    # 最終状態確認
    log_info "最終状態確認:"
    systemctl is-active hostapd && log_info "✅ hostapd: 実行中" || log_error "❌ hostapd: 停止中"
    systemctl is-active dnsmasq && log_info "✅ dnsmasq: 実行中" || log_error "❌ dnsmasq: 停止中"
    
    # WiFi AP確認
    if ip addr show wlan0 | grep -q "192.168.4.1"; then
        log_info "✅ wlan0に192.168.4.1が設定されています"
    else
        log_warn "❌ wlan0のIP設定に問題があります"
    fi
    
    log_info "AndroidデバイスでWiFiスキャンを実行して'AudioBridge-Pi'が見つかるか確認してください"
fi

log_info "hostapd診断・修正スクリプト完了"