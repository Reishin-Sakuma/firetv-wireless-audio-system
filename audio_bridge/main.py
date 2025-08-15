"""
AudioBridge-Pi メインアプリケーション
ESP32のmain.cppをRaspberry Pi用に移行
"""

import logging
import signal
import sys
import time
import threading
from pathlib import Path

from .config import *
from .bluetooth_manager import BluetoothManager
from .wifi_manager import WiFiManager
from .audio_pipeline import AudioPipeline
from .http_server import HTTPStreamingServer

# ログ設定
def setup_logging():
    """ログ設定初期化"""
    log_dir = LOG_FILE.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)

class AudioBridge:
    """メインアプリケーションクラス"""
    
    def __init__(self):
        self.bluetooth_manager = None
        self.wifi_manager = None
        self.audio_pipeline = None
        self.http_server = None
        
        self.running = False
        self.heartbeat_thread = None
        self.status_monitor_thread = None
        
        # シグナルハンドラー設定
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def initialize(self):
        """アプリケーション初期化"""
        try:
            logger.info("========================================")
            logger.info("AudioBridge-Pi Bluetooth-WiFi Audio Bridge")
            logger.info("Raspberry Pi Zero 2W - Phase 1 Complete")
            logger.info("========================================")
            
            # システム情報表示
            self._show_system_info()
            
            # 音声パイプライン初期化
            logger.info("[SYSTEM] Initializing audio pipeline...")
            self.audio_pipeline = AudioPipeline()
            if not self.audio_pipeline.initialize():
                logger.error("[SYSTEM] Failed to initialize audio pipeline")
                return False
            
            # WiFi Access Point初期化
            logger.info("[SYSTEM] Initializing WiFi Access Point...")
            self.wifi_manager = WiFiManager()
            if not self.wifi_manager.initialize():
                logger.error("[SYSTEM] Failed to initialize WiFi Access Point")
                return False
            
            # HTTP ストリーミングサーバー初期化
            logger.info("[SYSTEM] Initializing HTTP streaming server...")
            self.http_server = HTTPStreamingServer(self.audio_pipeline)
            if not self.http_server.initialize():
                logger.error("[SYSTEM] Failed to initialize HTTP server")
                return False
            
            # Bluetooth A2DP Sink初期化
            logger.info("[SYSTEM] Initializing Bluetooth A2DP Sink...")
            self.bluetooth_manager = BluetoothManager()
            if not self.bluetooth_manager.initialize():
                logger.error("[SYSTEM] Failed to initialize Bluetooth A2DP")
                return False
            
            # 音声フロー開始
            if not self.audio_pipeline.start_audio_flow():
                logger.warning("[SYSTEM] Audio flow start failed - continuing anyway")
            
            # HTTPサーバー開始
            self.http_server.start_server()
            
            logger.info("[SYSTEM] All components initialized successfully")
            logger.info("[INFO] Ready for Android device pairing")
            logger.info(f"[INFO] Bluetooth name: {BT_DEVICE_NAME}")
            logger.info(f"[INFO] WiFi AP: {WIFI_AP_SSID} (password: {WIFI_AP_PASSWORD})")
            logger.info(f"[INFO] Audio stream: http://{WIFI_AP_IP}:{HTTP_SERVER_PORT}/audio.mp3")
            logger.info("========================================")
            
            return True
            
        except Exception as e:
            logger.error(f"[SYSTEM] Initialization failed: {e}")
            return False
    
    def _show_system_info(self):
        """システム情報表示"""
        try:
            import psutil
            
            # CPU・メモリ情報
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            logger.info(f"[SYSTEM] CPU Usage: {cpu_percent}%")
            logger.info(f"[SYSTEM] Memory: {memory.used // 1024 // 1024}MB / {memory.total // 1024 // 1024}MB")
            
            # ディスク情報
            disk = psutil.disk_usage('/')
            logger.info(f"[SYSTEM] Disk: {disk.used // 1024 // 1024 // 1024}GB / {disk.total // 1024 // 1024 // 1024}GB")
            
        except ImportError:
            logger.info("[SYSTEM] System monitoring not available (psutil not installed)")
        except Exception as e:
            logger.debug(f"[SYSTEM] System info error: {e}")
    
    def run(self):
        """メインループ実行"""
        try:
            if not self.initialize():
                logger.error("[SYSTEM] Initialization failed - exiting")
                return 1
            
            self.running = True
            
            # バックグラウンドタスク開始
            self._start_background_tasks()
            
            # メインループ
            logger.info("[SYSTEM] Entering main loop...")
            while self.running:
                try:
                    time.sleep(1.0)  # 1秒間隔で待機
                    
                except KeyboardInterrupt:
                    logger.info("[SYSTEM] Keyboard interrupt received")
                    break
                except Exception as e:
                    logger.error(f"[SYSTEM] Main loop error: {e}")
                    time.sleep(5)
            
            return 0
            
        except Exception as e:
            logger.error(f"[SYSTEM] Run error: {e}")
            return 1
        finally:
            self.cleanup()
    
    def _start_background_tasks(self):
        """バックグラウンドタスク開始"""
        # ハートビートスレッド
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        # ステータス監視スレッド
        self.status_monitor_thread = threading.Thread(target=self._status_monitor_loop, daemon=True)
        self.status_monitor_thread.start()
        
        logger.info("[SYSTEM] Background tasks started")
    
    def _heartbeat_loop(self):
        """ハートビートループ"""
        while self.running:
            try:
                logger.info("[HEARTBEAT] System running normally")
                
                # システム状態表示
                self._log_system_status()
                
                time.sleep(60.0)  # 60秒間隔
                
            except Exception as e:
                logger.error(f"[HEARTBEAT] Error: {e}")
                time.sleep(30.0)
    
    def _status_monitor_loop(self):
        """ステータス監視ループ"""
        while self.running:
            try:
                # 各コンポーネントの健全性チェック
                bluetooth_ok = self.bluetooth_manager and self.bluetooth_manager.is_service_running()
                wifi_ok = self.wifi_manager and self.wifi_manager.is_hostapd_running()
                audio_ok = self.audio_pipeline and self.audio_pipeline.is_healthy()
                http_ok = self.http_server and self.http_server.running
                
                # 問題があるコンポーネントの復旧試行
                if not bluetooth_ok and self.bluetooth_manager:
                    logger.warning("[MONITOR] Bluetooth service issue - attempting recovery")
                    self.bluetooth_manager.attempt_recovery()
                
                if not audio_ok and self.audio_pipeline:
                    logger.warning("[MONITOR] Audio pipeline issue - attempting recovery")
                    self.audio_pipeline.attempt_recovery()
                
                # 全体的な健全性ログ
                overall_health = bluetooth_ok and wifi_ok and audio_ok and http_ok
                if not overall_health:
                    logger.warning("[MONITOR] System health degraded")
                
                time.sleep(30.0)  # 30秒間隔
                
            except Exception as e:
                logger.error(f"[MONITOR] Status monitor error: {e}")
                time.sleep(60.0)
    
    def _log_system_status(self):
        """システム状態ログ"""
        try:
            status_info = []
            
            # Bluetooth状態
            if self.bluetooth_manager:
                if self.bluetooth_manager.is_a2dp_connected():
                    active_device = self.bluetooth_manager.get_active_a2dp_device()
                    status_info.append(f"Bluetooth: Connected ({active_device})")
                else:
                    status_info.append("Bluetooth: Waiting")
            
            # WiFi クライアント状態
            if self.wifi_manager:
                client_count = self.wifi_manager.get_connected_clients_count()
                status_info.append(f"WiFi Clients: {client_count}")
            
            # HTTPストリーミング状態
            if self.http_server:
                active_streams = len(self.http_server.streaming_clients)
                status_info.append(f"Active Streams: {active_streams}")
            
            # 音声品質状態
            if self.audio_pipeline:
                try:
                    metrics = self.audio_pipeline.get_audio_quality_metrics()
                    latency = metrics.get("latency_ms", 0)
                    bitrate = metrics.get("bit_rate", 0)
                    status_info.append(f"Audio: {bitrate}kbps, {latency:.0f}ms latency")
                except:
                    status_info.append("Audio: Status unavailable")
            
            logger.info(f"[STATUS] {' | '.join(status_info)}")
            
        except Exception as e:
            logger.debug(f"[STATUS] Status logging error: {e}")
    
    def _signal_handler(self, signum, frame):
        """シグナルハンドラー"""
        signal_names = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}
        signal_name = signal_names.get(signum, f"Signal {signum}")
        
        logger.info(f"[SYSTEM] {signal_name} received - initiating shutdown")
        self.running = False
    
    def cleanup(self):
        """リソース解放"""
        logger.info("[SYSTEM] Cleaning up resources...")
        
        self.running = False
        
        # 各コンポーネントのクリーンアップ
        if self.http_server:
            self.http_server.cleanup()
        
        if self.audio_pipeline:
            self.audio_pipeline.cleanup()
        
        if self.bluetooth_manager:
            self.bluetooth_manager.cleanup()
        
        if self.wifi_manager:
            self.wifi_manager.cleanup()
        
        logger.info("[SYSTEM] Cleanup completed")

def main():
    """メイン関数"""
    setup_logging()
    
    # PIDファイル作成
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.warning(f"[SYSTEM] PID file creation failed: {e}")
    
    # アプリケーション実行
    app = AudioBridge()
    exit_code = app.run()
    
    # PIDファイル削除
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception as e:
        logger.debug(f"[SYSTEM] PID file cleanup error: {e}")
    
    logger.info(f"[SYSTEM] AudioBridge-Pi exited with code {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    import os
    main()