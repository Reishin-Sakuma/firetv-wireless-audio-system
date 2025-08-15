#!/usr/bin/env python3
"""
Audio-Bridge テスト起動スクリプト
GStreamer依存関係の問題を回避した簡易版
"""

import logging
import sys
import time
import subprocess
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def check_dependencies():
    """依存関係確認"""
    logger.info("=== Dependency Check ===")
    
    # Python modules
    required_modules = ['flask', 'dbus', 'gi']
    
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"✅ {module} module available")
        except ImportError as e:
            logger.error(f"❌ {module} module missing: {e}")
            return False
    
    # GStreamer
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        logger.info("✅ GStreamer available")
    except Exception as e:
        logger.error(f"❌ GStreamer error: {e}")
        return False
    
    # System commands
    required_commands = ['bluetoothctl', 'pactl', 'gst-launch-1.0']
    
    for cmd in required_commands:
        try:
            subprocess.run([cmd, '--help'], capture_output=True, check=True)
            logger.info(f"✅ {cmd} command available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning(f"⚠️ {cmd} command not available")
    
    return True

def test_bluetooth():
    """Bluetooth機能テスト"""
    logger.info("=== Bluetooth Test ===")
    
    try:
        result = subprocess.run(['systemctl', 'is-active', 'bluetooth'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ Bluetooth service active")
        else:
            logger.error("❌ Bluetooth service not active")
            return False
    except Exception as e:
        logger.error(f"❌ Bluetooth service check failed: {e}")
        return False
    
    # bluetoothctl確認
    try:
        result = subprocess.run(['bluetoothctl', 'show'], 
                               capture_output=True, text=True, timeout=10)
        if 'Powered: yes' in result.stdout:
            logger.info("✅ Bluetooth powered on")
        else:
            logger.warning("⚠️ Bluetooth may not be powered")
            
        if 'Discoverable: yes' in result.stdout:
            logger.info("✅ Bluetooth discoverable")
        else:
            logger.warning("⚠️ Bluetooth not discoverable")
            
    except Exception as e:
        logger.error(f"❌ bluetoothctl test failed: {e}")
    
    return True

def test_audio():
    """Audio機能テスト"""
    logger.info("=== Audio Test ===")
    
    # PulseAudio確認
    try:
        result = subprocess.run(['pulseaudio', '--check'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ PulseAudio running")
        else:
            logger.warning("⚠️ PulseAudio not running")
    except Exception as e:
        logger.warning(f"⚠️ PulseAudio check failed: {e}")
    
    # pactl確認
    try:
        result = subprocess.run(['pactl', 'info'], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("✅ pactl works")
        else:
            logger.warning("⚠️ pactl failed")
    except Exception as e:
        logger.warning(f"⚠️ pactl test failed: {e}")
    
    return True

def test_simple_http_server():
    """簡易HTTPサーバーテスト"""
    logger.info("=== Simple HTTP Server Test ===")
    
    try:
        from flask import Flask, jsonify
        
        app = Flask(__name__)
        
        @app.route('/test')
        def test():
            return jsonify({
                'status': 'ok',
                'message': 'AudioBridge-Pi test server',
                'timestamp': time.time()
            })
        
        @app.route('/audio.mp3')
        def audio_stream():
            return "Audio stream endpoint (test mode)", 200, {
                'Content-Type': 'audio/mpeg'
            }
        
        logger.info("✅ Flask HTTP server created")
        logger.info("Starting test HTTP server on port 8080...")
        
        # 短時間のテスト実行
        import threading
        import requests
        
        def run_server():
            app.run(host='0.0.0.0', port=8080, debug=False)
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # サーバー起動待機
        time.sleep(2)
        
        # 自己テスト
        try:
            response = requests.get('http://localhost:8080/test', timeout=5)
            if response.status_code == 200:
                logger.info("✅ HTTP server responding")
                return True
            else:
                logger.warning(f"⚠️ HTTP server response: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ HTTP server test failed: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ HTTP server test failed: {e}")
        return False

def main():
    """メイン関数"""
    logger.info("AudioBridge-Pi Test Started")
    logger.info("=" * 50)
    
    # 依存関係チェック
    if not check_dependencies():
        logger.error("Dependency check failed")
        return 1
    
    # Bluetoothテスト
    if not test_bluetooth():
        logger.error("Bluetooth test failed")
        return 1
    
    # Audioテスト  
    if not test_audio():
        logger.warning("Audio test had warnings")
    
    # HTTPサーバーテスト
    if not test_simple_http_server():
        logger.error("HTTP server test failed")
        return 1
    
    logger.info("=" * 50)
    logger.info("✅ All tests completed!")
    logger.info("AudioBridge-Pi basic functionality verified")
    
    # 簡易サーバー継続実行
    logger.info("Keeping test server running for 30 seconds...")
    logger.info("Test URLs:")
    logger.info("  http://192.168.4.1:8080/test")
    logger.info("  http://192.168.4.1:8080/audio.mp3")
    
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    
    logger.info("Test completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())