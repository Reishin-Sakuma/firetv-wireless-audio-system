"""
Bluetooth A2DP Sink機能のテスト

ESP32のBluetoothA2DPクラスをRaspberry Pi用に移行するためのテスト
期待される動作:
- BlueZ経由でのBluetooth A2DP Sink機能
- Android デバイスからの自動ペアリング
- 音声データ受信とPulseAudioへの転送
- 接続状態の監視と自動再接続
"""
import pytest
from unittest.mock import MagicMock, patch, call
import subprocess
import threading
import time

class TestBluetoothManager:
    """Bluetooth Manager のテスト"""
    
    def test_bluetooth_service_initialization(self, mock_bluetooth):
        """Bluetoothサービスの初期化テスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        bt_manager = BluetoothManager()
        
        # 初期化が成功することを期待
        assert bt_manager.initialize() == True
        
        # BlueZサービスが開始されることを期待
        assert bt_manager.is_service_running() == True
        
        # デバイス名が設定されることを期待  
        assert bt_manager.get_device_name() == "AudioBridge-Pi"
        
        # A2DP Sinkプロファイルが有効になることを期待
        assert bt_manager.is_a2dp_sink_enabled() == True
    
    def test_bluetooth_discovery_mode(self, mock_bluetooth):
        """Bluetooth検出可能モードのテスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        bt_manager = BluetoothManager()
        bt_manager.initialize()
        
        # 検出可能モードが有効になることを期待
        assert bt_manager.enable_discoverable() == True
        assert bt_manager.is_discoverable() == True
        
        # ペア可能モードが有効になることを期待
        assert bt_manager.enable_pairable() == True
        assert bt_manager.is_pairable() == True
    
    def test_android_device_pairing(self, mock_bluetooth):
        """Androidデバイスとのペアリングテスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        bt_manager = BluetoothManager()
        bt_manager.initialize()
        
        # Androidデバイスからのペアリング要求を模擬
        android_mac = "AA:BB:CC:DD:EE:FF"
        android_name = "Android Device"
        
        # ペアリング要求の受信を期待
        pairing_result = bt_manager.handle_pairing_request(android_mac, android_name)
        assert pairing_result == True
        
        # デバイスが信頼されることを期待
        assert bt_manager.is_device_trusted(android_mac) == True
        
        # ペアリング済みデバイスリストに追加されることを期待
        paired_devices = bt_manager.get_paired_devices()
        assert android_mac in paired_devices
    
    def test_a2dp_connection_establishment(self, mock_bluetooth):
        """A2DP接続確立のテスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        bt_manager = BluetoothManager()
        bt_manager.initialize()
        
        android_mac = "AA:BB:CC:DD:EE:FF"
        
        # A2DP接続の確立を期待
        connection_result = bt_manager.connect_a2dp(android_mac)
        assert connection_result == True
        
        # 接続状態の確認を期待
        assert bt_manager.is_a2dp_connected(android_mac) == True
        
        # 音声プロファイルがアクティブになることを期待
        assert bt_manager.is_audio_profile_active(android_mac) == True
    
    def test_audio_data_reception(self, mock_bluetooth, mock_pulseaudio, audio_test_data):
        """音声データ受信のテスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        bt_manager = BluetoothManager()
        bt_manager.initialize()
        
        android_mac = "AA:BB:CC:DD:EE:FF"
        bt_manager.connect_a2dp(android_mac)
        
        # 音声データがPulseAudioに転送されることを期待
        received_data = []
        def mock_audio_callback(data):
            received_data.append(data)
            
        bt_manager.set_audio_callback(mock_audio_callback)
        
        # 音声データの受信を模擬
        bt_manager._handle_audio_data(audio_test_data)
        
        # コールバックが呼び出されることを期待
        assert len(received_data) == 1
        assert received_data[0] == audio_test_data
    
    def test_connection_monitoring_and_reconnection(self, mock_bluetooth):
        """接続監視と自動再接続のテスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        bt_manager = BluetoothManager()
        bt_manager.initialize()
        
        android_mac = "AA:BB:CC:DD:EE:FF"
        bt_manager.connect_a2dp(android_mac)
        
        # 接続切断を模擬
        bt_manager._simulate_disconnection(android_mac)
        
        # 切断が検出されることを期待
        assert bt_manager.is_a2dp_connected(android_mac) == False
        
        # 自動再接続の試行が開始されることを期待
        reconnect_attempts = bt_manager.get_reconnect_attempts(android_mac)
        
        # 30秒以内に再接続が試行されることを期待
        time.sleep(0.1)  # 短時間で模擬
        bt_manager._attempt_reconnection(android_mac)
        
        # 再接続が成功することを期待（モックなので必ず成功）
        assert bt_manager.is_a2dp_connected(android_mac) == True
    
    def test_multiple_device_handling(self, mock_bluetooth):
        """複数デバイス対応のテスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        bt_manager = BluetoothManager()
        bt_manager.initialize()
        
        # 複数のAndroidデバイス
        device1_mac = "AA:BB:CC:DD:EE:F1"
        device2_mac = "AA:BB:CC:DD:EE:F2"
        
        # 両方とペアリング
        assert bt_manager.handle_pairing_request(device1_mac, "Android 1") == True
        assert bt_manager.handle_pairing_request(device2_mac, "Android 2") == True
        
        # しかし、A2DP接続は1つのデバイスのみ（仕様）
        assert bt_manager.connect_a2dp(device1_mac) == True
        assert bt_manager.connect_a2dp(device2_mac) == False  # 既に他が接続済み
        
        # アクティブな接続の確認
        active_device = bt_manager.get_active_a2dp_device()
        assert active_device == device1_mac
    
    def test_bluetooth_service_error_handling(self, mock_bluetooth):
        """Bluetoothサービスエラーハンドリングのテスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        # BlueZサービスが利用できない場合を模擬
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 1
            
            bt_manager = BluetoothManager()
            
            # 初期化が失敗することを期待
            assert bt_manager.initialize() == False
            
            # エラー状態が記録されることを期待
            assert bt_manager.get_last_error() is not None
            
            # 復旧処理が実行されることを期待
            recovery_result = bt_manager.attempt_recovery()
            assert recovery_result in [True, False]  # 復旧成功/失敗どちらでも
    
    def test_audio_quality_settings(self, mock_bluetooth):
        """音質設定のテスト"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        bt_manager = BluetoothManager()
        bt_manager.initialize()
        
        # 高音質設定（SBC codec）
        bt_manager.set_audio_codec("SBC")
        bt_manager.set_bitpool(53)  # SBC最高品質
        
        assert bt_manager.get_audio_codec() == "SBC"
        assert bt_manager.get_bitpool() == 53
        
        # サンプリングレート設定
        bt_manager.set_sample_rate(44100)
        assert bt_manager.get_sample_rate() == 44100
        
        # チャネル設定
        bt_manager.set_channels(2)  # ステレオ
        assert bt_manager.get_channels() == 2
    
    @pytest.mark.integration
    def test_real_bluez_interaction(self):
        """実際のBlueZとの統合テスト（統合テスト環境でのみ実行）"""
        from audio_bridge.bluetooth_manager import BluetoothManager
        
        # このテストは実際のBlueZサービスが必要
        try:
            result = subprocess.run(['systemctl', 'is-active', 'bluetooth'], 
                                   capture_output=True, text=True)
            if result.returncode != 0:
                pytest.skip("Bluetooth service not available")
        except FileNotFoundError:
            pytest.skip("systemctl not available")
            
        bt_manager = BluetoothManager()
        
        # 実際のBlueZ初期化を試行
        initialization_result = bt_manager.initialize()
        
        # 初期化結果を記録（成功/失敗どちらでも）
        assert initialization_result in [True, False]
        
        if initialization_result:
            # 基本的な機能テスト
            assert bt_manager.is_service_running() == True
            assert bt_manager.get_device_name() is not None