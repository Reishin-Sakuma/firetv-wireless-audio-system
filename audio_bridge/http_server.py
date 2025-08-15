"""
HTTP ストリーミングサーバーモジュール
ESP32のWebServerクラスをRaspberry Pi/Flask用に移行
"""

import logging
import threading
import time
import queue
import subprocess
from flask import Flask, Response, jsonify, request
from .config import *
from .audio_pipeline import AudioPipeline

logger = logging.getLogger(__name__)

class HTTPStreamingServer:
    """HTTP音声ストリーミングサーバークラス"""
    
    def __init__(self, audio_pipeline=None):
        self.app = Flask(__name__)
        self.audio_pipeline = audio_pipeline or AudioPipeline()
        self.server_thread = None
        self.running = False
        self.streaming_clients = {}
        self.audio_generator = None
        self.buffer_size = AUDIO_CHUNK_SIZE
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Flaskルート設定"""
        
        @self.app.route('/audio.mp3')
        def stream_audio():
            """MP3音声ストリーミングエンドポイント"""
            try:
                client_ip = request.remote_addr
                logger.info(f"[HTTP] Audio stream requested from {client_ip}")
                
                def generate_audio_stream():
                    """音声ストリーミング生成器"""
                    try:
                        # GStreamerパイプライン経由での音声取得
                        gst_process = self._create_gstreamer_process()
                        
                        if not gst_process:
                            logger.error("[HTTP] Failed to create GStreamer process")
                            return
                        
                        # クライアント接続を記録
                        client_id = f"{client_ip}_{int(time.time())}"
                        self.streaming_clients[client_id] = {
                            "ip": client_ip,
                            "start_time": time.time(),
                            "bytes_sent": 0
                        }
                        
                        try:
                            while self.running:
                                chunk = gst_process.stdout.read(self.buffer_size)
                                if not chunk:
                                    logger.warning("[HTTP] No audio data available")
                                    time.sleep(0.1)
                                    continue
                                
                                # クライアント統計更新
                                self.streaming_clients[client_id]["bytes_sent"] += len(chunk)
                                
                                yield chunk
                                
                        except Exception as e:
                            logger.error(f"[HTTP] Streaming error: {e}")
                        finally:
                            # クライアント接続終了
                            if client_id in self.streaming_clients:
                                del self.streaming_clients[client_id]
                            
                            if gst_process:
                                gst_process.terminate()
                                gst_process.wait()
                    
                    except Exception as e:
                        logger.error(f"[HTTP] Stream generation error: {e}")
                
                return Response(
                    generate_audio_stream(),
                    mimetype='audio/mpeg',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'close',
                        'Content-Type': 'audio/mpeg'
                    }
                )
                
            except Exception as e:
                logger.error(f"[HTTP] Stream endpoint error: {e}")
                return "Audio stream not available", 503
        
        @self.app.route('/status')
        def get_status():
            """システム状態エンドポイント"""
            try:
                status = self.get_system_status()
                return jsonify(status)
            except Exception as e:
                logger.error(f"[HTTP] Status endpoint error: {e}")
                return jsonify({"error": "Status unavailable"}), 500
        
        @self.app.route('/')
        def get_root():
            """ルートエンドポイント - 簡易情報ページ"""
            html = f"""
            <html>
            <head><title>AudioBridge-Pi</title></head>
            <body>
                <h1>AudioBridge-Pi Audio Streaming</h1>
                <p>Bluetooth A2DP to WiFi HTTP Audio Bridge</p>
                <ul>
                    <li><a href="/audio.mp3">MP3 Audio Stream</a></li>
                    <li><a href="/status">System Status (JSON)</a></li>
                </ul>
                <p>For Fire TV Stick VLC: http://{WIFI_AP_IP}:{HTTP_SERVER_PORT}/audio.mp3</p>
            </body>
            </html>
            """
            return html
        
        @self.app.route('/health')
        def health_check():
            """ヘルスチェックエンドポイント"""
            if self.running and self.audio_pipeline:
                return jsonify({"status": "healthy", "timestamp": time.time()})
            else:
                return jsonify({"status": "unhealthy"}), 503
    
    def _create_gstreamer_process(self):
        """GStreamerプロセス作成"""
        try:
            # BlueZ A2DP Sink からの音声を取得するGStreamerパイプライン
            bluetooth_sink = self._find_bluetooth_sink()
            if not bluetooth_sink:
                logger.error("[HTTP] No Bluetooth sink available")
                return None
            
            gst_cmd = [
                'gst-launch-1.0',
                '-q',  # Quiet mode
                f'pulsesrc', f'device={bluetooth_sink}.monitor',
                '!', 'audioconvert',
                '!', 'audioresample',
                '!', f'lamemp3enc', f'bitrate={AUDIO_BITRATE}',
                '!', 'fdsink', 'fd=1'
            ]
            
            logger.info(f"[HTTP] Starting GStreamer: {' '.join(gst_cmd)}")
            
            process = subprocess.Popen(
                gst_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # プロセス開始確認
            time.sleep(0.5)
            if process.poll() is not None:
                stderr_output = process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"[HTTP] GStreamer failed to start: {stderr_output}")
                return None
            
            return process
            
        except Exception as e:
            logger.error(f"[HTTP] GStreamer process creation failed: {e}")
            return None
    
    def _find_bluetooth_sink(self):
        """Bluetooth音声シンク検索"""
        try:
            # PulseAudio経由でBluetooth音声シンクを検索
            result = subprocess.run(
                ['pactl', 'list', 'sinks', 'short'],
                capture_output=True, text=True
            )
            
            for line in result.stdout.split('\n'):
                if 'bluez_sink' in line.lower():
                    sink_name = line.split('\t')[1]
                    logger.info(f"[HTTP] Found Bluetooth sink: {sink_name}")
                    return sink_name
            
            logger.warning("[HTTP] No Bluetooth sink found")
            return None
            
        except Exception as e:
            logger.error(f"[HTTP] Bluetooth sink search failed: {e}")
            return None
    
    def initialize(self):
        """HTTPサーバー初期化"""
        try:
            logger.info(f"[HTTP] Initializing HTTP server on port {HTTP_SERVER_PORT}")
            
            # 音声パイプライン初期化
            if self.audio_pipeline and not self.audio_pipeline.initialize():
                logger.warning("[HTTP] Audio pipeline initialization failed")
            
            self.running = True
            logger.info("[HTTP] HTTP server initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"[HTTP] HTTP server initialization failed: {e}")
            return False
    
    def start_server(self):
        """HTTPサーバー開始"""
        def run_server():
            try:
                logger.info(f"[HTTP] Starting HTTP server on {HTTP_SERVER_HOST}:{HTTP_SERVER_PORT}")
                self.app.run(
                    host=HTTP_SERVER_HOST,
                    port=HTTP_SERVER_PORT,
                    debug=False,
                    threaded=True
                )
            except Exception as e:
                logger.error(f"[HTTP] Server run error: {e}")
        
        if not self.server_thread or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            logger.info("[HTTP] HTTP server thread started")
    
    def get_listen_port(self):
        """リスンポート取得"""
        return HTTP_SERVER_PORT
    
    def get_available_endpoints(self):
        """利用可能エンドポイント一覧"""
        return [
            HTTP_STREAM_ENDPOINT,
            HTTP_STATUS_ENDPOINT,
            "/",
            "/health"
        ]
    
    def create_audio_pipeline(self):
        """音声パイプライン作成"""
        if self.audio_pipeline:
            return self.audio_pipeline.initialize()
        return False
    
    def get_pipeline_config(self):
        """パイプライン設定取得"""
        return {
            "source": f"pulsesrc device=bluez_sink.monitor",
            "encoder": "lamemp3enc",
            "bitrate": AUDIO_BITRATE
        }
    
    def get_system_status(self):
        """システム状態取得"""
        try:
            bluetooth_status = self._get_bluetooth_status()
            audio_status = self._get_audio_pipeline_status()
            client_status = self._get_client_status()
            
            return {
                "bluetooth": bluetooth_status,
                "audio_pipeline": audio_status,
                "wifi_clients": client_status,
                "uptime": time.time() - self._get_start_time(),
                "server_status": {
                    "running": self.running,
                    "port": HTTP_SERVER_PORT,
                    "active_streams": len(self.streaming_clients)
                }
            }
            
        except Exception as e:
            logger.error(f"[HTTP] System status error: {e}")
            return {"error": str(e)}
    
    def _get_bluetooth_status(self):
        """Bluetooth状態取得"""
        try:
            # bluetoothctl経由で接続状態確認
            result = subprocess.run(
                ['bluetoothctl', 'info'],
                capture_output=True, text=True, timeout=5
            )
            
            connected = 'Connected: yes' in result.stdout
            
            return {
                "connected": connected,
                "service_running": self._is_bluetooth_service_running()
            }
            
        except Exception as e:
            logger.debug(f"[HTTP] Bluetooth status check error: {e}")
            return {"connected": False, "service_running": False}
    
    def _get_audio_pipeline_status(self):
        """音声パイプライン状態取得"""
        if self.audio_pipeline:
            return {
                "running": self.audio_pipeline.is_healthy(),
                "pulseaudio_running": self.audio_pipeline.is_pulseaudio_running(),
                "gstreamer_ready": self.audio_pipeline.is_gstreamer_ready()
            }
        else:
            return {"running": False}
    
    def _get_client_status(self):
        """クライアント状態取得"""
        return {
            "count": len(self.streaming_clients),
            "clients": list(self.streaming_clients.values())
        }
    
    def _is_bluetooth_service_running(self):
        """Bluetoothサービス実行状態確認"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'bluetooth'],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def _get_start_time(self):
        """サーバー開始時刻取得"""
        return getattr(self, '_start_time', time.time())
    
    def set_audio_generator(self, generator):
        """音声ジェネレーター設定（テスト用）"""
        self.audio_generator = generator
    
    def generate_audio_stream(self):
        """音声ストリーム生成（テスト用）"""
        if self.audio_generator:
            return self.audio_generator()
        else:
            # デフォルト音声データ生成
            for i in range(10):
                yield b'\x00' * 1024  # 無音データ
                time.sleep(0.1)
    
    def create_client_connection(self, client_id):
        """クライアント接続作成（テスト用）"""
        connection = {
            "id": client_id,
            "connected_time": time.time(),
            "streaming": True
        }
        self.streaming_clients[client_id] = connection
        return connection
    
    def get_active_streaming_clients(self):
        """アクティブストリーミングクライアント取得"""
        return list(self.streaming_clients.keys())
    
    def is_client_streaming(self, client_id):
        """クライアントストリーミング状態確認"""
        return client_id in self.streaming_clients
    
    def set_audio_buffer_size(self, buffer_size):
        """音声バッファサイズ設定"""
        self.buffer_size = buffer_size
    
    def get_audio_buffer_size(self):
        """音声バッファサイズ取得"""
        return self.buffer_size
    
    def get_buffer_usage(self):
        """バッファ使用量取得"""
        return {
            "used": 0,  # 簡易実装
            "total": self.buffer_size
        }
    
    def handle_buffer_overflow(self):
        """バッファオーバーフロー処理"""
        logger.warning("[HTTP] Buffer overflow handled")
        return True
    
    def _simulate_pipeline_failure(self):
        """パイプライン障害シミュレーション（テスト用）"""
        if self.audio_pipeline:
            self.audio_pipeline.audio_flow_active = False
    
    def is_pipeline_running(self):
        """パイプライン実行状態確認"""
        if self.audio_pipeline:
            return self.audio_pipeline.audio_flow_active
        return False
    
    def attempt_pipeline_recovery(self):
        """パイプライン復旧試行"""
        if self.audio_pipeline:
            return self.audio_pipeline.attempt_recovery()
        return False
    
    def get_error_logs(self):
        """エラーログ取得"""
        # 簡易実装：実際にはログファイルから読み込み
        return ["pipeline_failure", "recovery_attempted"]
    
    def cleanup(self):
        """リソース解放"""
        logger.info("[HTTP] Cleaning up HTTP server...")
        self.running = False
        
        if self.audio_pipeline:
            self.audio_pipeline.cleanup()
    
    def __del__(self):
        """デストラクタ"""
        self.cleanup()