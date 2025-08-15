"""
音声バッファ・パイプラインシステムのテスト

ESP32のaudio_bufferクラスをRaspberry Pi用に移行するためのテスト
期待される動作:
- PulseAudio経由でのBluetooth音声受信
- GStreamer経由での音声変換・エンコード
- リアルタイムMP3ストリーミング配信
- 音声遅延の最小化とバッファ管理
"""
import pytest
from unittest.mock import MagicMock, patch, call
import threading
import time
import queue
import subprocess

class TestAudioBuffer:
    """Audio Buffer システムのテスト"""
    
    def test_audio_buffer_initialization(self):
        """音声バッファ初期化のテスト"""
        from audio_bridge.audio_pipeline import AudioBuffer
        
        # 32KB バッファサイズで初期化
        buffer_size = 32 * 1024
        audio_buffer = AudioBuffer(buffer_size)
        
        # 初期化が成功することを期待
        assert audio_buffer.initialize() == True
        
        # バッファサイズの確認
        assert audio_buffer.get_buffer_size() == buffer_size
        
        # 空の状態の確認
        assert audio_buffer.get_used_size() == 0
        assert audio_buffer.get_free_size() == buffer_size
        assert audio_buffer.is_empty() == True
        assert audio_buffer.is_full() == False
    
    def test_audio_buffer_write_read_operations(self, audio_test_data):
        """音声バッファ読み書き操作のテスト"""
        from audio_bridge.audio_pipeline import AudioBuffer
        
        buffer_size = 8192  # 8KB
        audio_buffer = AudioBuffer(buffer_size)
        audio_buffer.initialize()
        
        # データ書き込み
        test_chunk = audio_test_data[:1024]  # 1KB
        bytes_written = audio_buffer.write(test_chunk)
        
        # 書き込み成功を期待
        assert bytes_written == 1024
        assert audio_buffer.get_used_size() == 1024
        assert audio_buffer.is_empty() == False
        
        # データ読み出し
        read_chunk = audio_buffer.read(1024)
        
        # 読み出し成功を期待
        assert len(read_chunk) == 1024
        assert read_chunk == test_chunk
        assert audio_buffer.get_used_size() == 0
        assert audio_buffer.is_empty() == True
    
    def test_circular_buffer_wraparound(self, audio_test_data):
        """循環バッファのラップアラウンドテスト"""
        from audio_bridge.audio_pipeline import AudioBuffer
        
        buffer_size = 2048  # 2KB
        audio_buffer = AudioBuffer(buffer_size)
        audio_buffer.initialize()
        
        # バッファをほぼ満杯にする
        chunk_size = 512
        for i in range(3):  # 1.5KB 書き込み
            chunk = audio_test_data[i * chunk_size:(i + 1) * chunk_size]
            audio_buffer.write(chunk)
        
        # 一部読み出し
        audio_buffer.read(1024)  # 1KB 読み出し
        
        # さらに書き込み（ラップアラウンドが発生）
        new_chunk = audio_test_data[1536:2048]  # 512B
        bytes_written = audio_buffer.write(new_chunk)
        
        # ラップアラウンド後の書き込み成功を期待
        assert bytes_written == 512
        
        # データ整合性の確認
        remaining_data = audio_buffer.read(1024)
        assert len(remaining_data) == 1024
    
    def test_buffer_overflow_handling(self, audio_test_data):
        """バッファオーバーフロー処理のテスト"""
        from audio_bridge.audio_pipeline import AudioBuffer
        
        buffer_size = 1024  # 1KB
        audio_buffer = AudioBuffer(buffer_size)
        audio_buffer.initialize()
        
        # バッファを満杯にする
        audio_buffer.write(audio_test_data[:1024])
        assert audio_buffer.is_full() == True
        
        # オーバーフロー書き込み試行
        overflow_data = audio_test_data[1024:1536]  # 追加512B
        bytes_written = audio_buffer.write(overflow_data)
        
        # オーバーフロー処理を期待（書き込み拒否または古いデータ破棄）
        assert bytes_written <= 512  # 全部または一部拒否
        
        # バッファの状態確認
        assert audio_buffer.get_used_size() <= buffer_size
    
    def test_buffer_underrun_handling(self):
        """バッファアンダーラン処理のテスト"""
        from audio_bridge.audio_pipeline import AudioBuffer
        
        buffer_size = 1024  # 1KB
        audio_buffer = AudioBuffer(buffer_size)
        audio_buffer.initialize()
        
        # 空のバッファから読み出し試行
        read_data = audio_buffer.read(512)
        
        # アンダーラン処理を期待（無音データまたは空データ）
        assert len(read_data) <= 512
        
        # 無音データの場合の確認
        if len(read_data) > 0:
            # 無音データ（ゼロまたは特定パターン）であることを期待
            assert all(b == 0 for b in read_data) or len(set(read_data)) == 1

class TestPulseAudioIntegration:
    """PulseAudio統合のテスト"""
    
    def test_pulseaudio_service_detection(self, mock_pulseaudio):
        """PulseAudioサービス検出のテスト"""
        from audio_bridge.audio_pipeline import PulseAudioManager
        
        pulse_manager = PulseAudioManager()
        
        # PulseAudioが実行中であることを期待
        assert pulse_manager.is_service_running() == True
        
        # デーモン設定の確認
        daemon_config = pulse_manager.get_daemon_config()
        assert "sample-rate" in daemon_config
        assert "channels" in daemon_config
    
    def test_bluetooth_sink_detection(self, mock_pulseaudio, mock_bluetooth):
        """Bluetoothシンク検出のテスト"""
        from audio_bridge.audio_pipeline import PulseAudioManager
        
        pulse_manager = PulseAudioManager()
        
        # Bluetoothシンクが利用可能になることを期待
        bluetooth_sink = pulse_manager.find_bluetooth_sink()
        assert bluetooth_sink is not None
        assert "bluez_sink" in bluetooth_sink
        
        # シンクの詳細情報
        sink_info = pulse_manager.get_sink_info(bluetooth_sink)
        assert sink_info["sample_rate"] == 44100
        assert sink_info["channels"] == 2
        assert sink_info["state"] == "RUNNING"
    
    def test_audio_monitoring_setup(self, mock_pulseaudio):
        """音声モニタリング設定のテスト"""
        from audio_bridge.audio_pipeline import PulseAudioManager
        
        pulse_manager = PulseAudioManager()
        
        # モニタリングソースの設定
        monitor_source = pulse_manager.setup_monitor_source("bluez_sink")
        assert monitor_source is not None
        assert ".monitor" in monitor_source
        
        # モニタリング開始
        monitoring_started = pulse_manager.start_monitoring(monitor_source)
        assert monitoring_started == True
        
        # 音声データコールバックの設定
        received_samples = []
        def audio_callback(samples):
            received_samples.extend(samples)
        
        pulse_manager.set_audio_callback(audio_callback)
        
        # 音声データ受信の模擬
        pulse_manager._simulate_audio_data(b'\x00\x00' * 1024)  # 1024サンプル
        
        # コールバックが呼び出されることを期待
        assert len(received_samples) > 0

class TestGStreamerPipeline:
    """GStreamer パイプラインのテスト"""
    
    def test_gstreamer_installation_check(self, mock_gstreamer):
        """GStreamerインストール確認のテスト"""
        from audio_bridge.audio_pipeline import GStreamerManager
        
        gst_manager = GStreamerManager()
        
        # GStreamerが利用可能であることを期待
        assert gst_manager.is_available() == True
        
        # 必要なプラグインの確認
        required_plugins = ["pulsesrc", "audioconvert", "audioresample", "lamemp3enc"]
        for plugin in required_plugins:
            assert gst_manager.is_plugin_available(plugin) == True
    
    def test_audio_encoding_pipeline_creation(self, mock_gstreamer):
        """音声エンコードパイプライン作成のテスト"""
        from audio_bridge.audio_pipeline import GStreamerManager
        
        gst_manager = GStreamerManager()
        
        # パイプライン仕様の定義
        pipeline_spec = {
            "source": "pulsesrc device=bluez_sink.monitor",
            "processing": "audioconvert ! audioresample",
            "encoder": "lamemp3enc bitrate=128",
            "output": "fdsink fd=1"
        }
        
        # パイプライン作成
        pipeline_created = gst_manager.create_pipeline(pipeline_spec)
        assert pipeline_created == True
        
        # パイプライン状態の確認
        assert gst_manager.get_pipeline_state() == "READY"
    
    def test_real_time_audio_encoding(self, mock_gstreamer, audio_test_data):
        """リアルタイム音声エンコードのテスト"""
        from audio_bridge.audio_pipeline import GStreamerManager
        
        gst_manager = GStreamerManager()
        gst_manager.create_pipeline({
            "source": "pulsesrc device=bluez_sink.monitor",
            "encoder": "lamemp3enc bitrate=128",
            "output": "fdsink fd=1"
        })
        
        # パイプライン開始
        start_result = gst_manager.start_pipeline()
        assert start_result == True
        assert gst_manager.get_pipeline_state() == "PLAYING"
        
        # エンコードされたデータの取得を模擬
        encoded_chunks = []
        def data_callback(chunk):
            encoded_chunks.append(chunk)
        
        gst_manager.set_output_callback(data_callback)
        
        # 入力音声データの送信を模擬
        gst_manager._simulate_input_data(audio_test_data)
        
        # エンコードされたデータが出力されることを期待
        time.sleep(0.1)  # エンコード処理待機
        assert len(encoded_chunks) > 0
        
        # MP3データの確認（魔法数字）
        if encoded_chunks:
            first_chunk = encoded_chunks[0]
            assert len(first_chunk) > 0
            # MP3の場合、フレーム同期コードをチェック可能
    
    def test_pipeline_latency_optimization(self, mock_gstreamer):
        """パイプライン遅延最適化のテスト"""
        from audio_bridge.audio_pipeline import GStreamerManager
        
        gst_manager = GStreamerManager()
        
        # 低遅延設定の適用
        latency_config = {
            "buffer-time": 100000,  # 100ms
            "latency-time": 10000,  # 10ms
            "provide-clock": False
        }
        
        gst_manager.configure_latency(latency_config)
        
        # 設定が適用されることを期待
        current_config = gst_manager.get_latency_config()
        assert current_config["buffer-time"] == 100000
        assert current_config["latency-time"] == 10000
    
    def test_pipeline_error_handling(self, mock_gstreamer):
        """パイプラインエラーハンドリングのテスト"""
        from audio_bridge.audio_pipeline import GStreamerManager
        
        gst_manager = GStreamerManager()
        gst_manager.create_pipeline({"source": "pulsesrc", "encoder": "lamemp3enc"})
        
        # パイプラインエラーを模擬
        gst_manager._simulate_pipeline_error("Source element not found")
        
        # エラーが検出されることを期待
        assert gst_manager.has_error() == True
        error_message = gst_manager.get_last_error()
        assert "Source element not found" in error_message
        
        # 復旧処理の試行
        recovery_result = gst_manager.attempt_recovery()
        assert recovery_result in [True, False]

class TestAudioPipelineIntegration:
    """音声パイプライン統合のテスト"""
    
    def test_end_to_end_audio_flow(self, mock_bluetooth, mock_pulseaudio, mock_gstreamer):
        """エンドツーエンド音声フローのテスト"""
        from audio_bridge.audio_pipeline import AudioPipeline
        
        pipeline = AudioPipeline()
        
        # 全体初期化
        initialization_result = pipeline.initialize()
        assert initialization_result == True
        
        # コンポーネント状態の確認
        assert pipeline.is_bluetooth_connected() == False  # 初期状態
        assert pipeline.is_pulseaudio_running() == True
        assert pipeline.is_gstreamer_ready() == True
        
        # Bluetooth接続の模擬
        pipeline._simulate_bluetooth_connection("AA:BB:CC:DD:EE:FF")
        assert pipeline.is_bluetooth_connected() == True
        
        # 音声フロー開始
        flow_started = pipeline.start_audio_flow()
        assert flow_started == True
    
    def test_audio_quality_monitoring(self, mock_gstreamer):
        """音声品質監視のテスト"""
        from audio_bridge.audio_pipeline import AudioPipeline
        
        pipeline = AudioPipeline()
        pipeline.initialize()
        pipeline.start_audio_flow()
        
        # 品質メトリクスの取得
        quality_metrics = pipeline.get_audio_quality_metrics()
        
        # 期待されるメトリクス
        assert "sample_rate" in quality_metrics
        assert "bit_rate" in quality_metrics
        assert "latency_ms" in quality_metrics
        assert "buffer_level" in quality_metrics
        
        # 値の妥当性チェック
        assert quality_metrics["sample_rate"] in [44100, 48000]
        assert 64 <= quality_metrics["bit_rate"] <= 320  # kbps
        assert quality_metrics["latency_ms"] < 1000  # 1秒未満
        assert 0 <= quality_metrics["buffer_level"] <= 100  # パーセント
    
    def test_adaptive_bitrate_control(self, mock_gstreamer):
        """適応ビットレート制御のテスト"""
        from audio_bridge.audio_pipeline import AudioPipeline
        
        pipeline = AudioPipeline()
        pipeline.initialize()
        
        # 初期ビットレート設定
        initial_bitrate = 128  # kbps
        pipeline.set_target_bitrate(initial_bitrate)
        assert pipeline.get_current_bitrate() == initial_bitrate
        
        # ネットワーク負荷の模擬
        pipeline._simulate_network_congestion(high_load=True)
        
        # ビットレートが自動的に下がることを期待
        time.sleep(0.1)  # 調整処理待機
        adjusted_bitrate = pipeline.get_current_bitrate()
        assert adjusted_bitrate <= initial_bitrate
        
        # 負荷軽減後のビットレート復旧
        pipeline._simulate_network_congestion(high_load=False)
        time.sleep(0.1)
        recovered_bitrate = pipeline.get_current_bitrate()
        assert recovered_bitrate >= adjusted_bitrate
    
    @pytest.mark.slow
    def test_long_running_stability(self, mock_bluetooth, mock_pulseaudio, mock_gstreamer):
        """長時間動作安定性のテスト"""
        from audio_bridge.audio_pipeline import AudioPipeline
        
        pipeline = AudioPipeline()
        pipeline.initialize()
        pipeline.start_audio_flow()
        
        # 5秒間の連続動作を模擬
        start_time = time.time()
        error_count = 0
        
        while time.time() - start_time < 5.0:
            # システム状態の監視
            if not pipeline.is_healthy():
                error_count += 1
                pipeline.attempt_recovery()
            
            time.sleep(0.1)  # 100ms間隔でチェック
        
        # 安定動作を期待（エラー率5%以下）
        total_checks = int(5.0 / 0.1)
        error_rate = error_count / total_checks
        assert error_rate < 0.05  # 5%未満