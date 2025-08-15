"""
pytest設定とフィクスチャ定義
"""
import pytest
import sys
import os
from unittest.mock import MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def mock_bluetooth():
    """BlueZモックオブジェクト"""
    mock = MagicMock()
    mock.is_connected.return_value = False
    mock.connect.return_value = True
    mock.disconnect.return_value = True
    return mock

@pytest.fixture  
def mock_pulseaudio():
    """PulseAudioモックオブジェクト"""
    mock = MagicMock()
    mock.is_running.return_value = True
    mock.get_default_sink.return_value = "bluez_sink"
    return mock

@pytest.fixture
def mock_gstreamer():
    """GStreamerモックオブジェクト"""
    mock = MagicMock()
    mock.create_pipeline.return_value = True
    mock.start_pipeline.return_value = True
    mock.stop_pipeline.return_value = True
    return mock

@pytest.fixture
def mock_hostapd():
    """hostapdモックオブジェクト"""
    mock = MagicMock()
    mock.start_ap.return_value = True
    mock.stop_ap.return_value = True
    mock.is_running.return_value = True
    return mock

@pytest.fixture
def audio_test_data():
    """テスト用音声データ"""
    return b'\x00' * 4096  # 4KB のサイレント音声データ