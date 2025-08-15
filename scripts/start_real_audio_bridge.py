#!/usr/bin/env python3
"""
実際の音声ストリーミング機能付きAudio-Bridge
GStreamer + PulseAudio + Flask統合版
"""

import logging
import sys
import time
import subprocess
import threading
import signal
from pathlib import Path
from flask import Flask, Response, jsonify, request

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class RealAudioBridge:
    """実際の音声ストリーミング機能付きAudio-Bridge"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.running = False
        self.gstreamer_process = None
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
            <head><title>AudioBridge-Pi</title></head>
            <body>
                <h1>AudioBridge-Pi Real Audio Streaming</h1>
                <h2>Available Endpoints:</h2>
                <ul>
                    <li><a href="/status">System Status</a></li>
                    <li><a href="/audio.mp3">MP3 Audio Stream</a> (for VLC)</li>
                    <li><a href="/test">Test Endpoint</a></li>
                </ul>
                <h2>Usage:</h2>
                <p>1. Connect Android via Bluetooth to 'AudioBridge-Pi'</p>
                <p>2. Play music on Android (Spotify, etc.)</p>
                <p>3. Open VLC and play: <strong>http://192.168.4.1:8080/audio.mp3</strong></p>
            </body>
            </html>
            """
        
        @self.app.route('/test')
        def test():
            return jsonify({
                'status': 'ok',
                'message': 'AudioBridge-Pi real streaming server',
                'timestamp': time.time(),
                'active_clients': len(self.streaming_clients)
            })
        
        @self.app.route('/status')
        def status():
            return jsonify(self.get_system_status())
        
        @self.app.route('/audio.mp3')
        def stream_audio():
            """実際の音声ストリーミング"""
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
                    # GStreamerパイプライン作成
                    gst_process = self.create_gstreamer_pipeline()
                    
                    if not gst_process:
                        logger.error("Failed to create GStreamer pipeline")
                        yield b"# Audio stream not available\n"
                        return
                    
                    logger.info(f"GStreamer pipeline started for client {client_ip}")
                    
                    # 音声データストリーミング
                    while self.running:
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
                    if gst_process:
                        gst_process.terminate()
                        gst_process.wait()
                        
                except Exception as e:
                    logger.error(f"Audio generation error: {e}")
                    yield b"# Audio stream error\n"
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
    
    def create_gstreamer_pipeline(self):
        """GStreamerパイプライン作成"""
        try:
            # Bluetooth音声ソース検索
            bluetooth_source = self.find_bluetooth_audio_source()
            
            if not bluetooth_source:
                logger.warning("No Bluetooth audio source found, using default")
                bluetooth_source = "default"
            
            # GStreamerコマンド構築
            gst_cmd = [
                'gst-launch-1.0', '-q',
                'pulsesrc', f'device={bluetooth_source}',
                '!', 'audioconvert',
                '!', 'audioresample', 'rate=44100',
                '!', 'lamemp3enc', 'bitrate=128', 'cbr=true',
                '!', 'fdsink', 'fd=1'
            ]
            
            logger.info(f"Starting GStreamer: {' '.join(gst_cmd)}")
            
            # パイプライン起動
            process = subprocess.Popen(
                gst_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # 起動確認
            time.sleep(0.5)
            if process.poll() is not None:
                stderr_output = process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"GStreamer failed: {stderr_output}")
                return None
            
            return process
            
        except Exception as e:
            logger.error(f"GStreamer pipeline creation failed: {e}")
            return None
    
    def find_bluetooth_audio_source(self):
        """Bluetooth音声ソース検索"""
        try:
            # pactl list sources経由でBluetooth音声ソース検索
            result = subprocess.run(
                ['pactl', 'list', 'sources', 'short'],
                capture_output=True, text=True, timeout=10
            )
            
            for line in result.stdout.split('\n'):
                if 'bluez' in line.lower() and 'monitor' in line.lower():
                    source_name = line.split('\t')[1]
                    logger.info(f"Found Bluetooth audio source: {source_name}")
                    return source_name
            
            # フォールバック: default.monitor
            logger.info("Using default audio monitor source")
            return "default.monitor"
            
        except Exception as e:
            logger.error(f"Bluetooth source search failed: {e}")
            return "default.monitor"
    
    def get_system_status(self):
        """システム状態取得"""
        try:
            # Bluetooth状態
            bt_status = self.get_bluetooth_status()
            
            # Audio状態
            audio_status = self.get_audio_status()
            
            # ネットワーク状態
            network_status = self.get_network_status()
            
            return {
                'bluetooth': bt_status,
                'audio': audio_status,
                'network': network_status,
                'streaming': {
                    'active_clients': len(self.streaming_clients),
                    'clients': list(self.streaming_clients.values())
                },
                'server': {
                    'running': self.running,
                    'uptime': time.time() - getattr(self, 'start_time', time.time())
                }
            }
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {'error': str(e)}
    
    def get_bluetooth_status(self):
        """Bluetooth状態取得"""
        try:
            result = subprocess.run(
                ['bluetoothctl', 'show'],
                capture_output=True, text=True, timeout=5
            )
            
            status = {
                'service_active': False,
                'powered': False,
                'discoverable': False,
                'connected_devices': []
            }
            
            if result.returncode == 0:
                status['service_active'] = True
                output = result.stdout
                
                status['powered'] = 'Powered: yes' in output
                status['discoverable'] = 'Discoverable: yes' in output
            
            return status
            
        except Exception as e:
            logger.error(f"Bluetooth status check failed: {e}")
            return {'error': str(e)}
    
    def get_audio_status(self):
        """Audio状態取得"""
        try:
            # PulseAudio状態
            pa_result = subprocess.run(['pulseaudio', '--check'], capture_output=True)
            pa_running = pa_result.returncode == 0
            
            # Audio sources
            sources = []
            if pa_running:
                try:
                    sources_result = subprocess.run(
                        ['pactl', 'list', 'sources', 'short'],
                        capture_output=True, text=True, timeout=5
                    )
                    sources = [line.split('\t')[1] for line in sources_result.stdout.split('\n') if '\t' in line]
                except:
                    pass
            
            return {
                'pulseaudio_running': pa_running,
                'available_sources': sources,
                'bluetooth_sources': [s for s in sources if 'bluez' in s.lower()]
            }
            
        except Exception as e:
            logger.error(f"Audio status check failed: {e}")
            return {'error': str(e)}
    
    def get_network_status(self):
        """ネットワーク状態取得"""
        try:
            # wlan0 IP確認
            ip_result = subprocess.run(
                ['ip', 'addr', 'show', 'wlan0'],
                capture_output=True, text=True
            )
            
            ip_address = None
            for line in ip_result.stdout.split('\n'):
                if 'inet ' in line and '192.168.4.1' in line:
                    ip_address = line.split()[1]
                    break
            
            return {
                'wifi_ap_ip': ip_address,
                'interface_up': 'UP' in ip_result.stdout
            }
            
        except Exception as e:
            logger.error(f"Network status check failed: {e}")
            return {'error': str(e)}
    
    def start(self):
        """サーバー開始"""
        self.running = True
        self.start_time = time.time()
        
        logger.info("Starting AudioBridge-Pi Real Audio Streaming Server...")
        logger.info("Server will be available at:")
        logger.info("  http://192.168.4.1:8080/")
        logger.info("  http://192.168.4.1:8080/audio.mp3 (for VLC)")
        
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
        
        # GStreamerプロセス終了
        if self.gstreamer_process:
            self.gstreamer_process.terminate()
        
        sys.exit(0)

def main():
    """メイン関数"""
    logger.info("AudioBridge-Pi Real Audio Streaming Server")
    logger.info("=" * 60)
    
    # 依存関係確認
    try:
        import flask
        logger.info("✅ Flask available")
    except ImportError:
        logger.error("❌ Flask not available")
        return 1
    
    # GStreamer確認
    try:
        result = subprocess.run(['gst-launch-1.0', '--version'], capture_output=True)
        if result.returncode == 0:
            logger.info("✅ GStreamer available")
        else:
            logger.error("❌ GStreamer not available")
            return 1
    except FileNotFoundError:
        logger.error("❌ GStreamer not installed")
        return 1
    
    # AudioBridge起動
    bridge = RealAudioBridge()
    return bridge.start()

if __name__ == "__main__":
    sys.exit(main())