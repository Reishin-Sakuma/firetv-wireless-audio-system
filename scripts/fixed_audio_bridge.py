#!/usr/bin/env python3
"""
修正版 音声ストリーミングサーバー
PulseAudio設定修正後のGStreamerパイプライン対応
"""

import logging
import sys
import time
import subprocess
import threading
import signal
import os
from pathlib import Path
from flask import Flask, Response, jsonify, request

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class FixedAudioBridge:
    """修正版音声ストリーミングサーバー"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.running = False
        self.streaming_clients = {}
        self.setup_routes()
        
        # シグナルハンドラー
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_routes(self):
        """Flaskルート設定"""
        
        @self.app.route('/')
        def root():
            return """
            <html>
            <head><title>AudioBridge-Pi Fixed</title></head>
            <body>
                <h1>AudioBridge-Pi Fixed Audio Streaming</h1>
                <h2>Available Endpoints:</h2>
                <ul>
                    <li><a href="/status">System Status</a></li>
                    <li><a href="/audio.mp3">MP3 Audio Stream</a> (for VLC)</li>
                    <li><a href="/test-pipeline">Test GStreamer Pipeline</a></li>
                    <li><a href="/debug">Debug Information</a></li>
                </ul>
                <h2>Usage:</h2>
                <p>1. Connect Android via Bluetooth to 'AudioBridge-Pi'</p>
                <p>2. Play music on Android (Spotify, etc.)</p>
                <p>3. Open VLC and play: <strong>http://192.168.4.1:8080/audio.mp3</strong></p>
                <hr>
                <p><strong>Fixed Issues:</strong></p>
                <ul>
                    <li>✅ Raspberry Pi internal audio disabled (no noise)</li>
                    <li>✅ PulseAudio Bluetooth-only configuration</li>
                    <li>✅ Improved GStreamer pipeline</li>
                    <li>✅ Better error handling</li>
                </ul>
            </body>
            </html>
            """
        
        @self.app.route('/test-pipeline')
        def test_pipeline():
            """GStreamerパイプラインテスト"""
            result = self.test_gstreamer_pipeline()
            return jsonify(result)
        
        @self.app.route('/debug')
        def debug_info():
            """デバッグ情報"""
            debug_data = self.get_debug_info()
            return jsonify(debug_data)
        
        @self.app.route('/status')
        def status():
            return jsonify(self.get_system_status())
        
        @self.app.route('/audio.mp3')
        def stream_audio():
            """修正版音声ストリーミング"""
            client_ip = request.remote_addr
            client_id = f"{client_ip}_{int(time.time())}"
            
            logger.info(f"Audio stream requested from {client_ip}")
            
            def generate_audio():
                # クライアント登録
                self.streaming_clients[client_id] = {
                    'ip': client_ip,
                    'start_time': time.time(),
                    'bytes_sent': 0
                }
                
                try:
                    # 修正版GStreamerパイプライン作成
                    gst_process = self.create_fixed_gstreamer_pipeline()
                    
                    if not gst_process:
                        logger.error("Failed to create fixed GStreamer pipeline")
                        # エラー時はサイレント音声を返す
                        for _ in range(100):
                            yield b'\xff\xfb\x90\x00' + b'\x00' * 1020  # MP3 silence frame
                            time.sleep(0.1)
                        return
                    
                    logger.info(f"Fixed GStreamer pipeline started for client {client_ip}")
                    
                    # 音声データストリーミング
                    while self.running and gst_process.poll() is None:
                        try:
                            chunk = gst_process.stdout.read(4096)
                            if not chunk:
                                logger.warning("No audio data from GStreamer")
                                break
                            
                            self.streaming_clients[client_id]['bytes_sent'] += len(chunk)
                            yield chunk
                            
                        except Exception as e:
                            logger.error(f"Audio streaming error: {e}")
                            break
                    
                    # クリーンアップ
                    if gst_process and gst_process.poll() is None:
                        gst_process.terminate()
                        try:
                            gst_process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            gst_process.kill()
                        
                except Exception as e:
                    logger.error(f"Audio generation error: {e}")
                    # エラー時はHTTPエラーではなく無音を返す
                    yield b'# Audio stream error, playing silence\n'
                finally:
                    # クライアント登録解除
                    if client_id in self.streaming_clients:
                        del self.streaming_clients[client_id]
                    logger.info(f"Client {client_ip} disconnected")
            
            return Response(
                generate_audio(),
                mimetype='audio/mpeg',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'close',
                    'Content-Type': 'audio/mpeg',
                    'Transfer-Encoding': 'chunked'
                }
            )
    
    def find_bluetooth_audio_source(self):
        """Bluetooth音声ソース検索（修正版）"""
        try:
            logger.info("Searching for Bluetooth audio sources...")
            
            # PulseAudio ソース一覧取得（システムモード）
            env = os.environ.copy()
            env['PULSE_RUNTIME_PATH'] = '/var/run/pulse'
            
            result = subprocess.run(
                ['sudo', '-u', 'pulse', 'pactl', 'list', 'sources', 'short'],
                capture_output=True, text=True, timeout=10, env=env
            )
            
            bluetooth_sources = []
            all_sources = []
            
            for line in result.stdout.split('\n'):
                if '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        source_name = parts[1]
                        all_sources.append(source_name)
                        
                        # Bluetooth関連ソース検索
                        if any(keyword in source_name.lower() for keyword in ['bluez', 'bluetooth', 'a2dp']):
                            bluetooth_sources.append(source_name)
                            logger.info(f"Found Bluetooth source: {source_name}")
            
            logger.info(f"All sources: {all_sources}")
            logger.info(f"Bluetooth sources: {bluetooth_sources}")
            
            # Bluetooth音声ソース選択
            if bluetooth_sources:
                # monitor付きソースを優先
                monitor_sources = [s for s in bluetooth_sources if 'monitor' in s]
                if monitor_sources:
                    selected = monitor_sources[0]
                    logger.info(f"Selected monitor source: {selected}")
                    return selected
                else:
                    selected = bluetooth_sources[0]
                    logger.info(f"Selected Bluetooth source: {selected}")
                    return selected
            
            # フォールバック
            logger.warning("No Bluetooth sources found, trying alternatives...")
            
            # デフォルトソース確認
            if all_sources:
                for source in all_sources:
                    if 'monitor' in source and 'alsa' not in source.lower():
                        logger.info(f"Using fallback monitor source: {source}")
                        return source
            
            # 最終フォールバック
            logger.warning("Using audiotestsrc as fallback")
            return "audiotestsrc"
            
        except Exception as e:
            logger.error(f"Bluetooth source search failed: {e}")
            return "audiotestsrc"
    
    def create_fixed_gstreamer_pipeline(self):
        """修正版GStreamerパイプライン作成"""
        try:
            # Bluetooth音声ソース取得
            audio_source = self.find_bluetooth_audio_source()
            
            # パイプライン設定
            if audio_source == "audiotestsrc":
                # テスト音源使用
                gst_cmd = [
                    'gst-launch-1.0', '-q',
                    'audiotestsrc', 'freq=440', 'wave=0',
                    '!', 'audioconvert',
                    '!', 'audioresample', 'rate=44100',
                    '!', 'lamemp3enc', 'bitrate=128', 'cbr=true',
                    '!', 'fdsink', 'fd=1'
                ]
                logger.info("Using test audio source (440Hz tone)")
            else:
                # PulseAudio音声ソース使用
                gst_cmd = [
                    'gst-launch-1.0', '-q',
                    'pulsesrc', f'device={audio_source}', 'server=unix:/var/run/pulse/native',
                    '!', 'audioconvert',
                    '!', 'audioresample', 'rate=44100',
                    '!', 'lamemp3enc', 'bitrate=128', 'cbr=true',
                    '!', 'fdsink', 'fd=1'
                ]
                logger.info(f"Using PulseAudio source: {audio_source}")
            
            logger.info(f"Starting GStreamer: {' '.join(gst_cmd)}")
            
            # 環境変数設定
            env = os.environ.copy()
            env['PULSE_RUNTIME_PATH'] = '/var/run/pulse'
            env['PULSE_SERVER'] = 'unix:/var/run/pulse/native'
            
            # パイプライン起動
            process = subprocess.Popen(
                gst_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                env=env
            )
            
            # 起動確認
            time.sleep(1.0)
            if process.poll() is not None:
                stderr_output = process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"GStreamer failed: {stderr_output}")
                return None
            
            return process
            
        except Exception as e:
            logger.error(f"Fixed GStreamer pipeline creation failed: {e}")
            return None
    
    def test_gstreamer_pipeline(self):
        """GStreamerパイプラインテスト"""
        try:
            logger.info("Testing GStreamer pipeline...")
            
            # 基本テスト
            basic_test = subprocess.run([
                'gst-launch-1.0', '--version'
            ], capture_output=True, text=True, timeout=10)
            
            if basic_test.returncode != 0:
                return {'error': 'GStreamer not available', 'details': basic_test.stderr}
            
            # パイプラインテスト
            pipeline_test = subprocess.run([
                'gst-launch-1.0', '-q',
                'audiotestsrc', 'num-buffers=10',
                '!', 'audioconvert',
                '!', 'lamemp3enc', 'bitrate=128',
                '!', 'fakesink'
            ], capture_output=True, text=True, timeout=15)
            
            if pipeline_test.returncode == 0:
                return {
                    'status': 'success',
                    'message': 'GStreamer pipeline test passed',
                    'audio_source': self.find_bluetooth_audio_source()
                }
            else:
                return {
                    'status': 'error',
                    'message': 'GStreamer pipeline test failed',
                    'details': pipeline_test.stderr
                }
                
        except Exception as e:
            return {'error': str(e)}
    
    def get_debug_info(self):
        """デバッグ情報取得"""
        debug_info = {}
        
        try:
            # PulseAudio情報
            env = os.environ.copy()
            env['PULSE_RUNTIME_PATH'] = '/var/run/pulse'
            
            pulse_info = subprocess.run(
                ['sudo', '-u', 'pulse', 'pactl', 'info'],
                capture_output=True, text=True, timeout=5, env=env
            )
            debug_info['pulseaudio_info'] = pulse_info.stdout if pulse_info.returncode == 0 else pulse_info.stderr
            
            # PulseAudioソース
            pulse_sources = subprocess.run(
                ['sudo', '-u', 'pulse', 'pactl', 'list', 'sources', 'short'],
                capture_output=True, text=True, timeout=5, env=env
            )
            debug_info['pulseaudio_sources'] = pulse_sources.stdout if pulse_sources.returncode == 0 else pulse_sources.stderr
            
            # Bluetoothデバイス
            bt_devices = subprocess.run(
                ['bluetoothctl', 'devices'],
                capture_output=True, text=True, timeout=5
            )
            debug_info['bluetooth_devices'] = bt_devices.stdout if bt_devices.returncode == 0 else bt_devices.stderr
            
            # GStreamerプラグイン
            gst_plugins = subprocess.run(
                ['gst-inspect-1.0', '--print-all'],
                capture_output=True, text=True, timeout=10
            )
            debug_info['gstreamer_available'] = gst_plugins.returncode == 0
            
            # システム情報
            debug_info['system'] = {
                'audio_source': self.find_bluetooth_audio_source(),
                'streaming_clients': len(self.streaming_clients),
                'server_running': self.running
            }
            
        except Exception as e:
            debug_info['error'] = str(e)
        
        return debug_info
    
    def get_system_status(self):
        """システム状態取得"""
        try:
            return {
                'server': {
                    'running': self.running,
                    'clients': len(self.streaming_clients)
                },
                'audio': {
                    'source': self.find_bluetooth_audio_source(),
                    'pipeline_test': self.test_gstreamer_pipeline()
                },
                'bluetooth': self.get_bluetooth_status(),
                'timestamp': time.time()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_bluetooth_status(self):
        """Bluetooth状態取得"""
        try:
            result = subprocess.run(
                ['bluetoothctl', 'show'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout
                return {
                    'powered': 'Powered: yes' in output,
                    'discoverable': 'Discoverable: yes' in output,
                    'name': next((line.split(':', 1)[1].strip() for line in output.split('\n') if 'Name:' in line), 'Unknown')
                }
            else:
                return {'error': result.stderr}
                
        except Exception as e:
            return {'error': str(e)}
    
    def start(self):
        """サーバー開始"""
        self.running = True
        self.start_time = time.time()
        
        logger.info("Starting AudioBridge-Pi Fixed Audio Streaming Server...")
        logger.info("Fixed issues: Pi internal audio disabled, PulseAudio Bluetooth-only")
        logger.info("Server will be available at:")
        logger.info("  http://192.168.4.1:8080/")
        logger.info("  http://192.168.4.1:8080/audio.mp3 (for VLC)")
        logger.info("  http://192.168.4.1:8080/debug (debug info)")
        
        try:
            self.app.run(
                host='0.0.0.0',
                port=8080,
                debug=False,
                threaded=True
            )
        except Exception as e:
            logger.error(f"Server failed to start: {e}")
            return 1
        
        return 0
    
    def signal_handler(self, signum, frame):
        """シグナルハンドラー"""
        logger.info(f"Signal {signum} received, shutting down...")
        self.running = False
        sys.exit(0)

def main():
    """メイン関数"""
    logger.info("AudioBridge-Pi Fixed Audio Streaming Server")
    logger.info("=" * 60)
    
    # AudioBridge起動
    bridge = FixedAudioBridge()
    return bridge.start()

if __name__ == "__main__":
    sys.exit(main())