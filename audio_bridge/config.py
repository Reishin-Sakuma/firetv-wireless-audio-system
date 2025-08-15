"""
設定管理モジュール
ESP32のconfig.hに対応するPython設定
"""

import os
from pathlib import Path

# プロジェクトルートディレクトリ
PROJECT_ROOT = Path(__file__).parent.parent

# Bluetooth設定
BT_DEVICE_NAME = "AudioBridge-Pi"
BT_CLASS = "0x200414"  # Audio/Video - Loudspeaker
BT_DISCOVERABLE_TIMEOUT = 0  # 常時検出可能
BT_PAIRABLE_TIMEOUT = 0      # 常時ペアリング可能

# WiFi AP設定
WIFI_AP_SSID = "AudioBridge-Pi"
WIFI_AP_PASSWORD = "audiobridge123"
WIFI_AP_CHANNEL = 7
WIFI_AP_IP = "192.168.4.1"
WIFI_AP_NETMASK = "255.255.255.0"
WIFI_AP_DHCP_RANGE_START = "192.168.4.10"
WIFI_AP_DHCP_RANGE_END = "192.168.4.100"

# HTTP Server設定
HTTP_SERVER_HOST = "0.0.0.0"
HTTP_SERVER_PORT = 8080
HTTP_STREAM_ENDPOINT = "/audio.mp3"
HTTP_STATUS_ENDPOINT = "/status"

# 音声設定
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2
AUDIO_BITS_PER_SAMPLE = 16
AUDIO_BITRATE = 128  # kbps (可変)

# バッファ設定
AUDIO_BUFFER_SIZE = 64 * 1024  # 64KB (RasPiなので大きく)
AUDIO_CHUNK_SIZE = 4096        # 4KB chunks
AUDIO_QUEUE_SIZE = 10          # キューのサイズ

# システム設定
LOG_LEVEL = "INFO"
LOG_FILE = PROJECT_ROOT / "logs" / "audio_bridge.log"
PID_FILE = PROJECT_ROOT / "audio_bridge.pid"

# サービス設定
SYSTEMD_SERVICE_NAME = "audio-bridge"
BLUETOOTH_SERVICE_NAME = "bluetooth"
HOSTAPD_SERVICE_NAME = "hostapd"
DNSMASQ_SERVICE_NAME = "dnsmasq"

# 遅延・品質設定
TARGET_LATENCY_MS = 200        # 目標遅延200ms
MAX_LATENCY_MS = 400          # 最大許容遅延400ms
QUALITY_CHECK_INTERVAL = 5.0   # 品質チェック間隔(秒)
RECONNECT_INTERVAL = 30.0      # 再接続試行間隔(秒)

# GStreamer パイプライン設定
GST_PIPELINE_ELEMENTS = {
    "source": "pulsesrc device=bluez_sink.monitor",
    "convert": "audioconvert",
    "resample": "audioresample", 
    "encoder": f"lamemp3enc bitrate={AUDIO_BITRATE}",
    "sink": "fdsink fd=1"
}

# ファイルパス設定
CONFIG_DIR = PROJECT_ROOT / "config"
BLUETOOTH_CONFIG_DIR = CONFIG_DIR / "bluetooth"
PULSEAUDIO_CONFIG_DIR = CONFIG_DIR / "pulseaudio"
HOSTAPD_CONFIG_DIR = CONFIG_DIR / "hostapd"
DNSMASQ_CONFIG_DIR = CONFIG_DIR / "dnsmasq"
SYSTEMD_CONFIG_DIR = CONFIG_DIR / "systemd"

# 環境変数からの設定上書き
def load_env_config():
    """環境変数から設定を読み込み"""
    global AUDIO_BITRATE, HTTP_SERVER_PORT, LOG_LEVEL
    
    if "AUDIO_BITRATE" in os.environ:
        AUDIO_BITRATE = int(os.environ["AUDIO_BITRATE"])
    
    if "HTTP_PORT" in os.environ:
        HTTP_SERVER_PORT = int(os.environ["HTTP_PORT"])
    
    if "LOG_LEVEL" in os.environ:
        LOG_LEVEL = os.environ["LOG_LEVEL"]

# 初期化時に環境変数を読み込み
load_env_config()