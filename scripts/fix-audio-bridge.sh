#!/bin/bash
# audio-bridge サービス診断・修正スクリプト

set -e

echo "=== AudioBridge サービス診断・修正スクリプト ==="

# Root権限確認
if [[ $EUID -ne 0 ]]; then
   echo "エラー: このスクリプトはroot権限で実行してください"
   exit 1
fi

echo "1. 現在のサービス状態確認..."
systemctl status audio-bridge --no-pager || true

echo
echo "2. エラーログ確認..."
journalctl -u audio-bridge --no-pager -n 20 || true

echo
echo "3. Python環境確認..."
which python3
python3 --version
pip3 --version || echo "pip3が利用できません"

echo
echo "4. audio_bridge モジュール確認..."
if [ -d "/opt/audio-bridge-pi/audio_bridge" ]; then
    echo "✓ /opt/audio-bridge-pi/audio_bridge ディレクトリ存在"
    ls -la /opt/audio-bridge-pi/audio_bridge/
else
    echo "✗ /opt/audio-bridge-pi/audio_bridge ディレクトリなし"
    echo "セットアップが未完了の可能性があります"
fi

echo
echo "5. Python パス確認..."
export PYTHONPATH="/opt/audio-bridge-pi:$PYTHONPATH"
python3 -c "import sys; print('Python path:'); [print(p) for p in sys.path]"

echo
echo "6. 依存関係確認..."
python3 -c "
try:
    import flask
    print('✓ Flask: OK')
except ImportError as e:
    print('✗ Flask: MISSING -', e)

try:
    import dbus
    print('✓ D-Bus: OK') 
except ImportError as e:
    print('✗ D-Bus: MISSING -', e)

try:
    import gi
    print('✓ GObject: OK')
except ImportError as e:
    print('✗ GObject: MISSING -', e)

try:
    import psutil
    print('✓ psutil: OK')
except ImportError as e:
    print('✗ psutil: MISSING -', e)
"

echo
echo "7. audio_bridge モジュールインポートテスト..."
cd /opt/audio-bridge-pi || exit 1
export PYTHONPATH="/opt/audio-bridge-pi:$PYTHONPATH"

python3 -c "
try:
    from audio_bridge.main import AudioBridge
    print('✓ audio_bridge.main: インポート成功')
except ImportError as e:
    print('✗ audio_bridge.main: インポート失敗 -', e)
    import traceback
    traceback.print_exc()
except Exception as e:
    print('✗ audio_bridge.main: 実行時エラー -', e)
    import traceback
    traceback.print_exc()
"

echo
echo "8. systemd サービス設定確認..."
if [ -f "/etc/systemd/system/audio-bridge.service" ]; then
    echo "✓ systemdサービスファイル存在"
    cat /etc/systemd/system/audio-bridge.service
else
    echo "✗ systemdサービスファイルなし"
    echo "セットアップ未完了です"
fi

echo
echo "9. 権限確認..."
if [ -d "/opt/audio-bridge-pi" ]; then
    ls -la /opt/audio-bridge-pi/
    echo "ユーザー権限:"
    ls -la /opt/audio-bridge-pi/audio_bridge/ | head -5
fi

echo
echo "=== 診断完了 ==="
echo "問題が見つかった場合の修正案:"
echo "1. 依存関係インストール: sudo apt install -y python3-flask python3-dbus python3-gi python3-psutil"
echo "2. セットアップ再実行: sudo ./scripts/setup-safe.sh (段階4)"
echo "3. 手動起動テスト: cd /opt/audio-bridge-pi && python3 -m audio_bridge.main"
echo "4. サービス再起動: sudo systemctl restart audio-bridge"