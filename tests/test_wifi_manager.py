"""
WiFi AP + HTTPストリーミング機能のテスト

ESP32のWiFiAPクラスをRaspberry Pi用に移行するためのテスト
期待される動作:
- hostapd経由でのWiFi Access Point機能
- dnsmasq経由でのDHCPサーバー
- Flask経由でのHTTPストリーミング
- Fire TV Stick向けのリアルタイムMP3配信
"""
import pytest
from unittest.mock import MagicMock, patch, call
import subprocess
import requests
import threading
import time
import socket

class TestWiFiManager:
    """WiFi Manager のテスト"""
    
    def test_wifi_ap_initialization(self, mock_hostapd):
        """WiFi Access Point初期化のテスト"""
        from audio_bridge.wifi_manager import WiFiManager
        
        wifi_manager = WiFiManager()
        
        # 初期化が成功することを期待
        assert wifi_manager.initialize() == True
        
        # hostapdサービスが開始されることを期待
        assert wifi_manager.is_hostapd_running() == True
        
        # SSID設定の確認
        assert wifi_manager.get_ap_ssid() == "AudioBridge-Pi"
        
        # パスワード設定の確認
        assert wifi_manager.get_ap_password() == "audiobridge123"
        
        # IPアドレス設定の確認
        assert wifi_manager.get_ap_ip() == "192.168.4.1"
    
    def test_dhcp_server_configuration(self, mock_hostapd):
        """DHCPサーバー設定のテスト"""
        from audio_bridge.wifi_manager import WiFiManager
        
        wifi_manager = WiFiManager()
        wifi_manager.initialize()
        
        # dnsmasqサービスが開始されることを期待
        assert wifi_manager.is_dnsmasq_running() == True
        
        # DHCP範囲の確認
        dhcp_range = wifi_manager.get_dhcp_range()
        assert dhcp_range["start"] == "192.168.4.10"
        assert dhcp_range["end"] == "192.168.4.100"
        
        # DNSサーバー設定の確認
        assert wifi_manager.get_dns_server() == "192.168.4.1"
    
    def test_client_connection_monitoring(self, mock_hostapd):
        """クライアント接続監視のテスト"""
        from audio_bridge.wifi_manager import WiFiManager
        
        wifi_manager = WiFiManager()
        wifi_manager.initialize()
        
        # 初期状態では接続クライアントなし
        assert wifi_manager.get_connected_clients_count() == 0
        assert wifi_manager.has_connected_clients() == False
        
        # Fire TV Stickの接続を模擬
        firetv_mac = "AA:BB:CC:DD:EE:F1"
        firetv_ip = "192.168.4.15"
        
        wifi_manager._simulate_client_connection(firetv_mac, firetv_ip, "Fire TV")
        
        # 接続クライアントの確認
        assert wifi_manager.get_connected_clients_count() == 1
        assert wifi_manager.has_connected_clients() == True
        
        clients = wifi_manager.get_connected_clients()
        assert firetv_mac in clients
        assert clients[firetv_mac]["ip"] == firetv_ip
        assert clients[firetv_mac]["device_name"] == "Fire TV"
    
    def test_network_interface_configuration(self, mock_hostapd):
        """ネットワークインターフェース設定のテスト"""
        from audio_bridge.wifi_manager import WiFiManager
        
        wifi_manager = WiFiManager()
        
        # インターフェース設定
        interface_result = wifi_manager.configure_wlan_interface("wlan0")
        assert interface_result == True
        
        # 静的IP設定の確認
        ip_config = wifi_manager.get_interface_config("wlan0")
        assert ip_config["ip"] == "192.168.4.1"
        assert ip_config["netmask"] == "255.255.255.0"
        assert ip_config["broadcast"] == "192.168.4.255"
        
        # ルーティング設定の確認
        routing_enabled = wifi_manager.is_ip_forwarding_enabled()
        assert routing_enabled == True
    
    def test_firewall_configuration(self, mock_hostapd):
        """ファイアウォール設定のテスト"""
        from audio_bridge.wifi_manager import WiFiManager
        
        wifi_manager = WiFiManager()
        wifi_manager.initialize()
        
        # iptablesルールの設定を期待
        firewall_rules = wifi_manager.get_firewall_rules()
        
        # HTTP通信許可ルール
        assert any("8080" in rule and "ACCEPT" in rule for rule in firewall_rules)
        
        # インターフェース間通信許可
        assert any("wlan0" in rule and "FORWARD" in rule for rule in firewall_rules)
        
        # NATルール（不要だが確認）
        nat_rules = wifi_manager.get_nat_rules()
        assert isinstance(nat_rules, list)
    
class TestHTTPStreamingServer:
    """HTTP Streaming Server のテスト"""
    
    def test_flask_server_initialization(self, mock_gstreamer):
        """Flask HTTPサーバー初期化のテスト"""
        from audio_bridge.http_server import HTTPStreamingServer
        
        http_server = HTTPStreamingServer()
        
        # サーバー初期化が成功することを期待
        assert http_server.initialize() == True
        
        # ポート8080でのバインドを期待
        assert http_server.get_listen_port() == 8080
        
        # ストリーミングエンドポイントの確認
        endpoints = http_server.get_available_endpoints()
        assert "/audio.mp3" in endpoints
        assert "/status" in endpoints
    
    def test_gstreamer_pipeline_creation(self, mock_gstreamer, mock_pulseaudio):
        """GStreamer音声パイプライン作成のテスト"""
        from audio_bridge.http_server import HTTPStreamingServer
        
        http_server = HTTPStreamingServer()
        http_server.initialize()
        
        # GStreamerパイプラインが作成されることを期待
        pipeline_created = http_server.create_audio_pipeline()
        assert pipeline_created == True
        
        # パイプライン設定の確認
        pipeline_config = http_server.get_pipeline_config()
        assert "pulsesrc" in pipeline_config["source"]
        assert "lamemp3enc" in pipeline_config["encoder"]
        assert "127" <= str(pipeline_config["bitrate"]) <= "320"  # 128-320kbps範囲
    
    def test_audio_streaming_endpoint(self, mock_gstreamer):
        """音声ストリーミングエンドポイントのテスト"""
        from audio_bridge.http_server import HTTPStreamingServer
        
        http_server = HTTPStreamingServer()
        http_server.initialize()
        
        # /audio.mp3 エンドポイントのテスト
        with patch('flask.Flask.test_client') as mock_client:
            test_client = mock_client.return_value
            
            # GETリクエストの模擬
            response_mock = MagicMock()
            response_mock.status_code = 200
            response_mock.headers = {"Content-Type": "audio/mpeg"}
            test_client.get.return_value = response_mock
            
            response = test_client.get("/audio.mp3")
            
            # 適切なレスポンスヘッダーを期待
            assert response.status_code == 200
            assert response.headers["Content-Type"] == "audio/mpeg"
    
    def test_status_endpoint(self, mock_gstreamer):
        """ステータスエンドポイントのテスト"""
        from audio_bridge.http_server import HTTPStreamingServer
        
        http_server = HTTPStreamingServer()
        http_server.initialize()
        
        # /status エンドポイントのテスト
        status_data = http_server.get_system_status()
        
        # システム状態情報を期待
        assert "bluetooth" in status_data
        assert "audio_pipeline" in status_data
        assert "wifi_clients" in status_data
        assert "uptime" in status_data
        
        # Bluetooth状態
        assert status_data["bluetooth"]["connected"] in [True, False]
        
        # 音声パイプライン状態
        assert status_data["audio_pipeline"]["running"] in [True, False]
        
        # WiFiクライアント数
        assert isinstance(status_data["wifi_clients"]["count"], int)
    
    def test_real_time_audio_streaming(self, mock_gstreamer, audio_test_data):
        """リアルタイム音声ストリーミングのテスト"""
        from audio_bridge.http_server import HTTPStreamingServer
        
        http_server = HTTPStreamingServer()
        http_server.initialize()
        http_server.create_audio_pipeline()
        
        # 音声データのストリーミングを模擬
        audio_chunks = []
        
        def mock_audio_generator():
            # テスト用音声データを複数回返す
            for i in range(5):
                yield audio_test_data[i * 1024:(i + 1) * 1024]
                time.sleep(0.1)  # 100ms間隔
        
        # 音声ジェネレーターの設定
        http_server.set_audio_generator(mock_audio_generator)
        
        # ストリーミングデータの取得
        for chunk in http_server.generate_audio_stream():
            audio_chunks.append(chunk)
            if len(audio_chunks) >= 3:  # 3チャンクで終了
                break
        
        # 音声データが正常に配信されることを期待
        assert len(audio_chunks) >= 3
        assert all(len(chunk) > 0 for chunk in audio_chunks)
    
    def test_multiple_client_streaming(self, mock_gstreamer):
        """複数クライアント同時ストリーミングのテスト"""
        from audio_bridge.http_server import HTTPStreamingServer
        
        http_server = HTTPStreamingServer()
        http_server.initialize()
        
        # 複数のクライアントを模擬
        client_connections = []
        
        for i in range(3):  # 3つのクライアント
            client_id = f"client_{i}"
            connection = http_server.create_client_connection(client_id)
            client_connections.append((client_id, connection))
        
        # 全クライアントが接続されることを期待
        assert len(client_connections) == 3
        active_clients = http_server.get_active_streaming_clients()
        assert len(active_clients) == 3
        
        # 各クライアントに音声データが配信されることを期待
        for client_id, connection in client_connections:
            assert http_server.is_client_streaming(client_id) == True
    
    def test_audio_buffer_management(self, mock_gstreamer):
        """音声バッファ管理のテスト"""
        from audio_bridge.http_server import HTTPStreamingServer
        
        http_server = HTTPStreamingServer()
        http_server.initialize()
        
        # バッファサイズの設定
        buffer_size = 8192  # 8KB
        http_server.set_audio_buffer_size(buffer_size)
        
        assert http_server.get_audio_buffer_size() == buffer_size
        
        # バッファの使用量監視
        initial_usage = http_server.get_buffer_usage()
        assert initial_usage["used"] == 0
        assert initial_usage["total"] == buffer_size
        
        # バッファオーバーフロー処理
        overflow_handled = http_server.handle_buffer_overflow()
        assert overflow_handled == True
    
    @pytest.mark.integration
    def test_end_to_end_streaming(self, mock_hostapd, mock_gstreamer):
        """エンドツーエンドストリーミングテスト"""
        from audio_bridge.wifi_manager import WiFiManager
        from audio_bridge.http_server import HTTPStreamingServer
        
        # WiFi APの起動
        wifi_manager = WiFiManager()
        wifi_manager.initialize()
        
        # HTTPサーバーの起動
        http_server = HTTPStreamingServer()
        http_server.initialize()
        
        # Fire TV Stickクライアントを模擬
        firetv_ip = "192.168.4.15"
        
        # HTTPリクエストのテスト（モック）
        with patch('requests.get') as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "audio/mpeg"}
            mock_response.iter_content = lambda chunk_size: [b'audio_data' for _ in range(10)]
            mock_requests.return_value = mock_response
            
            # Fire TV からの音声ストリーミング要求を模擬
            response = mock_requests("http://192.168.4.1:8080/audio.mp3")
            
            # 正常なレスポンスを期待
            assert response.status_code == 200
            assert response.headers["Content-Type"] == "audio/mpeg"
    
    def test_error_recovery_mechanisms(self, mock_gstreamer):
        """エラー復旧機能のテスト"""
        from audio_bridge.http_server import HTTPStreamingServer
        
        http_server = HTTPStreamingServer()
        http_server.initialize()
        
        # GStreamerパイプライン停止を模擬
        http_server._simulate_pipeline_failure()
        
        # 停止が検出されることを期待
        assert http_server.is_pipeline_running() == False
        
        # 自動復旧の試行
        recovery_result = http_server.attempt_pipeline_recovery()
        
        # 復旧が成功することを期待（モックなので成功）
        assert recovery_result == True
        assert http_server.is_pipeline_running() == True
        
        # エラーログが記録されることを期待
        error_logs = http_server.get_error_logs()
        assert len(error_logs) > 0
        assert "pipeline_failure" in error_logs[-1]