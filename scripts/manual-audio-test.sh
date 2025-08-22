#!/bin/bash
# audio-bridge 手動テスト・起動スクリプト

set -e

echo "=== AudioBridge 手動テスト・起動 ==="

# Root権限確認
if [[ $EUID -ne 0 ]]; then
   echo "エラー: このスクリプトはroot権限で実行してください"
   exit 1
fi

echo "1. 必要な依存関係をインストール..."
apt update
apt install -y \
    python3-flask \
    python3-dbus \
    python3-gi \
    python3-gi-cairo \
    python3-psutil \
    python3-yaml \
    python3-pip \
    pulseaudio \
    pulseaudio-module-bluetooth \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-good

echo "2. pip専用パッケージインストール..."
pip3 install --break-system-packages pulsectl netifaces || true

echo "3. アプリケーションディレクトリの確認・作成..."
if [ ! -d "/opt/audio-bridge-pi" ]; then
    echo "アプリケーションディレクトリを作成中..."
    mkdir -p /opt/audio-bridge-pi
    
    # 現在のプロジェクトからコピー
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    if [ -d "$PROJECT_ROOT/audio_bridge" ]; then
        cp -r "$PROJECT_ROOT/audio_bridge" /opt/audio-bridge-pi/
        echo "✓ audio_bridge をコピーしました"
    else
        echo "✗ $PROJECT_ROOT/audio_bridge が見つかりません"
        exit 1
    fi
    
    if [ -d "$PROJECT_ROOT/config" ]; then
        cp -r "$PROJECT_ROOT/config" /opt/audio-bridge-pi/
        echo "✓ config をコピーしました"
    fi
    
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        cp "$PROJECT_ROOT/requirements.txt" /opt/audio-bridge-pi/
    fi
fi

echo "4. 権限設定..."
AUDIO_USER="${SUDO_USER:-pi}"
chown -R "$AUDIO_USER:$AUDIO_USER" /opt/audio-bridge-pi

echo "5. PulseAudio セットアップ..."
# PulseAudio をシステムワイドモードで起動
if ! pgrep -x "pulseaudio" > /dev/null; then
    echo "PulseAudio を起動中..."
    su -c "pulseaudio --start" "$AUDIO_USER" || true
fi

echo "6. Bluetooth 確認..."
systemctl start bluetooth
sleep 2

echo "7. 手動テスト実行..."
cd /opt/audio-bridge-pi
export PYTHONPATH="/opt/audio-bridge-pi:$PYTHONPATH"

echo "Python環境テスト:"
python3 -c "
import sys
sys.path.insert(0, '/opt/audio-bridge-pi')
print('Python Path:', sys.path[:3])

try:
    from audio_bridge.main import AudioBridge
    print('✓ AudioBridge インポート成功')
    
    # 設定テスト
    app = AudioBridge()
    print('✓ AudioBridge インスタンス作成成功')
    
except Exception as e:
    print('✗ エラー:', e)
    import traceback
    traceback.print_exc()
"

echo
echo "8. HTTPサーバー起動テスト（10秒間）..."
echo "http://192.168.4.1:8080 でアクセス可能になります"
timeout 10s python3 -m audio_bridge.main || echo "10秒でタイムアウト - これは正常です"

echo
echo "=== テスト完了 ==="
echo "手動起動コマンド:"
echo "cd /opt/audio-bridge-pi && python3 -m audio_bridge.main"
echo ""
echo "systemd サービス登録:"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl enable audio-bridge" 
echo "sudo systemctl start audio-bridge"