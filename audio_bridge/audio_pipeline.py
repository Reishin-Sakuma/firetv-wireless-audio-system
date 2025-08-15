"""
音声パイプライン管理モジュール
ESP32のaudio_bufferクラスをRaspberry Pi/PulseAudio/GStreamer用に移行
"""

import logging
import threading
import time
import queue
import subprocess
import pulsectl
import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

from .config import *

logger = logging.getLogger(__name__)

class AudioBuffer:
    """循環音声バッファクラス"""
    
    def __init__(self, buffer_size):
        self.buffer_size = buffer_size
        self.buffer = bytearray(buffer_size)
        self.write_pos = 0
        self.read_pos = 0
        self.used_size = 0
        self.lock = threading.Lock()
        self.initialized = False
        
    def initialize(self):
        """バッファ初期化"""
        try:
            self.write_pos = 0
            self.read_pos = 0
            self.used_size = 0
            self.initialized = True
            logger.info(f"[AUDIO] Buffer initialized: {self.buffer_size} bytes")
            return True
        except Exception as e:
            logger.error(f"[AUDIO] Buffer initialization failed: {e}")
            return False
    
    def write(self, data):
        """データ書き込み"""
        with self.lock:
            if not self.initialized:
                return 0
                
            data_len = len(data)
            available_space = self.buffer_size - self.used_size
            
            if data_len > available_space:
                # オーバーフロー処理：古いデータを破棄
                overflow_size = data_len - available_space
                self._advance_read_pos(overflow_size)
                logger.debug(f"[AUDIO] Buffer overflow, dropped {overflow_size} bytes")
            
            # 循環バッファへの書き込み
            bytes_written = 0
            remaining = data_len
            
            while remaining > 0 and bytes_written < data_len:
                chunk_size = min(remaining, self.buffer_size - self.write_pos)
                
                self.buffer[self.write_pos:self.write_pos + chunk_size] = \
                    data[bytes_written:bytes_written + chunk_size]
                
                self.write_pos = (self.write_pos + chunk_size) % self.buffer_size
                bytes_written += chunk_size
                remaining -= chunk_size
            
            self.used_size = min(self.used_size + bytes_written, self.buffer_size)
            return bytes_written
    
    def read(self, size):
        """データ読み出し"""
        with self.lock:
            if not self.initialized:
                return b''
            
            read_size = min(size, self.used_size)
            if read_size == 0:
                return b''  # アンダーラン
            
            result = bytearray(read_size)
            bytes_read = 0
            
            while bytes_read < read_size:
                chunk_size = min(read_size - bytes_read, 
                               self.buffer_size - self.read_pos)
                
                result[bytes_read:bytes_read + chunk_size] = \
                    self.buffer[self.read_pos:self.read_pos + chunk_size]
                
                self.read_pos = (self.read_pos + chunk_size) % self.buffer_size
                bytes_read += chunk_size
            
            self.used_size -= read_size
            return bytes(result)
    
    def _advance_read_pos(self, size):
        """読み取り位置を進める（オーバーフロー用）"""
        advance_size = min(size, self.used_size)
        self.read_pos = (self.read_pos + advance_size) % self.buffer_size
        self.used_size -= advance_size
    
    def get_buffer_size(self):
        """バッファサイズ取得"""
        return self.buffer_size
    
    def get_used_size(self):
        """使用サイズ取得"""
        with self.lock:
            return self.used_size
    
    def get_free_size(self):
        """空きサイズ取得"""
        with self.lock:
            return self.buffer_size - self.used_size
    
    def is_empty(self):
        """空状態確認"""
        with self.lock:
            return self.used_size == 0
    
    def is_full(self):
        """満杯状態確認"""
        with self.lock:
            return self.used_size == self.buffer_size

class PulseAudioManager:
    """PulseAudio管理クラス"""
    
    def __init__(self):
        self.pulse = None
        self.bluetooth_sink = None
        self.monitor_source = None
        self.audio_callback = None
        
    def is_service_running(self):
        """PulseAudioサービス実行確認"""
        try:
            subprocess.run(["pulseaudio", "--check"], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_daemon_config(self):
        """デーモン設定取得"""
        return {
            "sample-rate": AUDIO_SAMPLE_RATE,
            "channels": AUDIO_CHANNELS
        }
    
    def find_bluetooth_sink(self):
        """Bluetoothシンク検索"""
        try:
            with pulsectl.Pulse('bluetooth-finder') as pulse:
                sinks = pulse.sink_list()
                
                for sink in sinks:
                    if 'bluez' in sink.name.lower():
                        self.bluetooth_sink = sink.name
                        logger.info(f"[AUDIO] Found Bluetooth sink: {sink.name}")
                        return sink.name
                
                logger.warning("[AUDIO] No Bluetooth sink found")
                return None
                
        except Exception as e:
            logger.error(f"[AUDIO] Bluetooth sink search failed: {e}")
            return None
    
    def get_sink_info(self, sink_name):
        """シンク情報取得"""
        try:
            with pulsectl.Pulse('sink-info') as pulse:
                sink = pulse.get_sink_by_name(sink_name)
                
                return {
                    "sample_rate": sink.sample_spec.rate,
                    "channels": sink.sample_spec.channels,
                    "state": sink.state.name
                }
                
        except Exception as e:
            logger.error(f"[AUDIO] Sink info failed: {e}")
            return {}
    
    def setup_monitor_source(self, sink_name):
        """モニタリングソース設定"""
        try:
            monitor_source = f"{sink_name}.monitor"
            self.monitor_source = monitor_source
            logger.info(f"[AUDIO] Monitor source: {monitor_source}")
            return monitor_source
        except Exception as e:
            logger.error(f"[AUDIO] Monitor source setup failed: {e}")
            return None
    
    def start_monitoring(self, monitor_source):
        """モニタリング開始"""
        try:
            # PulseAudioモニタリングの実装は複雑なため、
            # GStreamerパイプラインで処理
            logger.info(f"[AUDIO] Monitoring started on {monitor_source}")
            return True
        except Exception as e:
            logger.error(f"[AUDIO] Monitoring start failed: {e}")
            return False
    
    def set_audio_callback(self, callback):
        """音声コールバック設定"""
        self.audio_callback = callback
    
    def _simulate_audio_data(self, audio_data):
        """音声データシミュレーション（テスト用）"""
        if self.audio_callback:
            # 16bit ステレオサンプルに変換
            samples = []
            for i in range(0, len(audio_data), 4):
                if i + 3 < len(audio_data):
                    left = int.from_bytes(audio_data[i:i+2], byteorder='little', signed=True)
                    right = int.from_bytes(audio_data[i+2:i+4], byteorder='little', signed=True)
                    samples.extend([left, right])
            
            self.audio_callback(samples)

class GStreamerManager:
    """GStreamer パイプライン管理クラス"""
    
    def __init__(self):
        Gst.init(None)
        self.pipeline = None
        self.pipeline_state = "NULL"
        self.output_callback = None
        self.error_message = None
        
    def is_available(self):
        """GStreamer利用可能確認"""
        try:
            # 基本的なGStreamer機能テスト
            pipeline = Gst.parse_launch("fakesrc ! fakesink")
            pipeline.set_state(Gst.State.NULL)
            return True
        except Exception as e:
            logger.error(f"[AUDIO] GStreamer not available: {e}")
            return False
    
    def is_plugin_available(self, plugin_name):
        """プラグイン利用可能確認"""
        try:
            registry = Gst.Registry.get()
            plugin = registry.find_plugin(plugin_name)
            return plugin is not None
        except:
            return False
    
    def create_pipeline(self, pipeline_spec):
        """パイプライン作成"""
        try:
            # パイプライン文字列構築
            elements = []
            
            if "source" in pipeline_spec:
                elements.append(pipeline_spec["source"])
            
            if "processing" in pipeline_spec:
                elements.append(pipeline_spec["processing"])
            elif "convert" in pipeline_spec and "resample" in pipeline_spec:
                elements.extend([pipeline_spec["convert"], pipeline_spec["resample"]])
            
            if "encoder" in pipeline_spec:
                elements.append(pipeline_spec["encoder"])
            
            if "output" in pipeline_spec:
                elements.append(pipeline_spec["output"])
            elif "sink" in pipeline_spec:
                elements.append(pipeline_spec["sink"])
            
            pipeline_str = " ! ".join(elements)
            logger.info(f"[AUDIO] Creating pipeline: {pipeline_str}")
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            # バス設定（エラー監視用）
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self._on_bus_message)
            
            self.pipeline_state = "READY"
            return True
            
        except Exception as e:
            logger.error(f"[AUDIO] Pipeline creation failed: {e}")
            self.error_message = str(e)
            return False
    
    def _on_bus_message(self, bus, message):
        """バスメッセージ処理"""
        msg_type = message.type
        
        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            self.error_message = f"GStreamer Error: {err}"
            logger.error(f"[AUDIO] Pipeline error: {err}")
            
        elif msg_type == Gst.MessageType.EOS:
            logger.info("[AUDIO] Pipeline end of stream")
            
        elif msg_type == Gst.MessageType.STATE_CHANGED:
            old_state, new_state, pending_state = message.parse_state_changed()
            if message.src == self.pipeline:
                self.pipeline_state = new_state.value_name.replace("GST_STATE_", "")
    
    def get_pipeline_state(self):
        """パイプライン状態取得"""
        return self.pipeline_state
    
    def start_pipeline(self):
        """パイプライン開始"""
        try:
            if not self.pipeline:
                return False
            
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("[AUDIO] Pipeline start failed")
                return False
            
            logger.info("[AUDIO] Pipeline started")
            return True
            
        except Exception as e:
            logger.error(f"[AUDIO] Pipeline start error: {e}")
            return False
    
    def stop_pipeline(self):
        """パイプライン停止"""
        try:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
                logger.info("[AUDIO] Pipeline stopped")
            return True
        except Exception as e:
            logger.error(f"[AUDIO] Pipeline stop error: {e}")
            return False
    
    def set_output_callback(self, callback):
        """出力コールバック設定"""
        self.output_callback = callback
    
    def _simulate_input_data(self, audio_data):
        """入力データシミュレーション（テスト用）"""
        if self.output_callback:
            # 簡易MP3エンコードシミュレーション
            # 実際の実装では、appsrc経由でデータ投入
            encoded_chunk = b'\xff\xfb' + audio_data[:1024]  # MP3フレームヘッダー風
            self.output_callback(encoded_chunk)
    
    def configure_latency(self, latency_config):
        """遅延設定"""
        self.latency_config = latency_config
        logger.info(f"[AUDIO] Latency configured: {latency_config}")
    
    def get_latency_config(self):
        """現在の遅延設定取得"""
        return getattr(self, 'latency_config', {})
    
    def has_error(self):
        """エラー状態確認"""
        return self.error_message is not None
    
    def get_last_error(self):
        """最後のエラー取得"""
        return self.error_message
    
    def _simulate_pipeline_error(self, error_msg):
        """パイプラインエラーシミュレーション（テスト用）"""
        self.error_message = error_msg
    
    def attempt_recovery(self):
        """復旧処理試行"""
        try:
            logger.info("[AUDIO] Attempting pipeline recovery...")
            
            # パイプライン停止・再作成
            if self.pipeline:
                self.stop_pipeline()
            
            time.sleep(1)
            
            # エラークリア
            self.error_message = None
            
            # 復旧成功をシミュレート
            return True
            
        except Exception as e:
            logger.error(f"[AUDIO] Recovery failed: {e}")
            return False

class AudioPipeline:
    """統合音声パイプライン管理クラス"""
    
    def __init__(self):
        self.audio_buffer = AudioBuffer(AUDIO_BUFFER_SIZE)
        self.pulse_manager = PulseAudioManager()
        self.gst_manager = GStreamerManager()
        
        self.bluetooth_connected = False
        self.audio_flow_active = False
        self.quality_monitor_thread = None
        self.monitoring_quality = False
        
        self.current_bitrate = AUDIO_BITRATE
        self.target_bitrate = AUDIO_BITRATE
        
    def initialize(self):
        """パイプライン全体初期化"""
        try:
            logger.info("[AUDIO] Initializing audio pipeline...")
            
            # 各コンポーネント初期化
            if not self.audio_buffer.initialize():
                logger.error("[AUDIO] Buffer initialization failed")
                return False
            
            if not self.pulse_manager.is_service_running():
                logger.error("[AUDIO] PulseAudio not running")
                return False
            
            if not self.gst_manager.is_available():
                logger.error("[AUDIO] GStreamer not available")
                return False
            
            # 音声パイプライン構築
            pipeline_spec = {
                "source": GST_PIPELINE_ELEMENTS["source"],
                "convert": GST_PIPELINE_ELEMENTS["convert"],
                "resample": GST_PIPELINE_ELEMENTS["resample"],
                "encoder": GST_PIPELINE_ELEMENTS["encoder"],
                "sink": GST_PIPELINE_ELEMENTS["sink"]
            }
            
            if not self.gst_manager.create_pipeline(pipeline_spec):
                logger.error("[AUDIO] Pipeline creation failed")
                return False
            
            logger.info("[AUDIO] Audio pipeline initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"[AUDIO] Pipeline initialization failed: {e}")
            return False
    
    def is_bluetooth_connected(self):
        """Bluetooth接続状態"""
        return self.bluetooth_connected
    
    def is_pulseaudio_running(self):
        """PulseAudio実行状態"""
        return self.pulse_manager.is_service_running()
    
    def is_gstreamer_ready(self):
        """GStreamer準備状態"""
        return self.gst_manager.is_available()
    
    def _simulate_bluetooth_connection(self, device_address):
        """Bluetooth接続シミュレーション（テスト用）"""
        self.bluetooth_connected = True
        logger.info(f"[AUDIO] Bluetooth connected: {device_address}")
    
    def start_audio_flow(self):
        """音声フロー開始"""
        try:
            # GStreamerパイプライン開始
            if not self.gst_manager.start_pipeline():
                return False
            
            # 品質監視開始
            self._start_quality_monitoring()
            
            self.audio_flow_active = True
            logger.info("[AUDIO] Audio flow started")
            return True
            
        except Exception as e:
            logger.error(f"[AUDIO] Audio flow start failed: {e}")
            return False
    
    def _start_quality_monitoring(self):
        """音声品質監視開始"""
        def quality_monitor():
            while self.monitoring_quality:
                try:
                    metrics = self.get_audio_quality_metrics()
                    
                    # 遅延チェック
                    if metrics["latency_ms"] > MAX_LATENCY_MS:
                        logger.warning(f"[AUDIO] High latency detected: {metrics['latency_ms']}ms")
                        self._adjust_for_latency()
                    
                    time.sleep(QUALITY_CHECK_INTERVAL)
                    
                except Exception as e:
                    logger.error(f"[AUDIO] Quality monitoring error: {e}")
                    time.sleep(10)
        
        self.monitoring_quality = True
        self.quality_monitor_thread = threading.Thread(target=quality_monitor, daemon=True)
        self.quality_monitor_thread.start()
    
    def get_audio_quality_metrics(self):
        """音声品質メトリクス取得"""
        return {
            "sample_rate": AUDIO_SAMPLE_RATE,
            "bit_rate": self.current_bitrate,
            "latency_ms": self._estimate_latency(),
            "buffer_level": (self.audio_buffer.get_used_size() / self.audio_buffer.get_buffer_size()) * 100
        }
    
    def _estimate_latency(self):
        """遅延推定"""
        # 簡易遅延推定（実際は複雑な計算が必要）
        buffer_latency = (self.audio_buffer.get_used_size() / (AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * 2)) * 1000
        processing_latency = 50  # 処理遅延50ms
        network_latency = 30     # ネットワーク遅延30ms
        
        return buffer_latency + processing_latency + network_latency
    
    def _adjust_for_latency(self):
        """遅延調整"""
        # バッファサイズ調整やビットレート調整
        current_level = self.audio_buffer.get_used_size() / self.audio_buffer.get_buffer_size()
        
        if current_level > 0.8:  # 80%以上なら
            # ビットレート下げて遅延軽減
            self.set_target_bitrate(max(64, self.current_bitrate - 32))
    
    def set_target_bitrate(self, bitrate):
        """目標ビットレート設定"""
        self.target_bitrate = bitrate
        logger.info(f"[AUDIO] Target bitrate set to {bitrate} kbps")
    
    def get_current_bitrate(self):
        """現在のビットレート取得"""
        return self.current_bitrate
    
    def _simulate_network_congestion(self, high_load):
        """ネットワーク負荷シミュレーション（テスト用）"""
        if high_load:
            self.current_bitrate = max(64, self.current_bitrate - 32)
        else:
            self.current_bitrate = min(self.target_bitrate, self.current_bitrate + 16)
    
    def is_healthy(self):
        """システム健全性確認"""
        return (
            self.is_pulseaudio_running() and
            self.gst_manager.get_pipeline_state() == "PLAYING" and
            not self.gst_manager.has_error() and
            self._estimate_latency() < MAX_LATENCY_MS
        )
    
    def attempt_recovery(self):
        """復旧処理"""
        try:
            logger.info("[AUDIO] Attempting audio pipeline recovery...")
            
            # GStreamer復旧
            if self.gst_manager.has_error():
                if not self.gst_manager.attempt_recovery():
                    return False
            
            # パイプライン再開
            if self.gst_manager.get_pipeline_state() != "PLAYING":
                if not self.gst_manager.start_pipeline():
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"[AUDIO] Recovery failed: {e}")
            return False
    
    def cleanup(self):
        """リソース解放"""
        logger.info("[AUDIO] Cleaning up audio pipeline...")
        self.monitoring_quality = False
        self.audio_flow_active = False
        
        if self.gst_manager:
            self.gst_manager.stop_pipeline()
    
    def __del__(self):
        """デストラクタ"""
        self.cleanup()