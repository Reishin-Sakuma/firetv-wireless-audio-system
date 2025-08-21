"""
AudioBridge-Pi システムインターフェース定義
Python型ヒント・データクラス・プロトコルによる設計契約
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Union, Callable, Protocol, Any, AsyncIterator
from datetime import datetime
import threading

# =============================================================================
# 基本データ型・列挙型
# =============================================================================

class ConnectionState(Enum):
    """接続状態"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting" 
    CONNECTED = "connected"
    FAILED = "failed"
    RECOVERING = "recovering"

class ServiceState(Enum):
    """サービス状態"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    RECOVERING = "recovering"

class AudioCodec(Enum):
    """音声コーデック"""
    SBC = "sbc"
    AAC = "aac"
    APTX = "aptx"
    LDAC = "ldac"

class AudioQuality(Enum):
    """音質レベル"""
    LOW = auto()      # 64-96kbps
    MEDIUM = auto()   # 128-192kbps  
    HIGH = auto()     # 256-320kbps
    ADAPTIVE = auto() # 動的調整

class LogLevel(Enum):
    """ログレベル"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

# =============================================================================
# デバイス・接続情報
# =============================================================================

@dataclass
class DeviceInfo:
    """デバイス情報"""
    mac_address: str
    name: str = "Unknown Device"
    device_type: str = "generic"
    manufacturer: str = ""
    last_seen: datetime = field(default_factory=datetime.now)
    trusted: bool = False
    paired: bool = False
    
    def is_fire_tv(self) -> bool:
        """Fire TV Stickか判定"""
        fire_tv_ouis = ["50:F5:DA", "CC:86:EC", "AC:63:BE"]
        return any(self.mac_address.upper().startswith(oui) for oui in fire_tv_ouis)
    
    def is_raspberry_pi(self) -> bool:
        """Raspberry Piか判定"""
        rpi_ouis = ["B8:27:EB", "DC:A6:32"]
        return any(self.mac_address.upper().startswith(oui) for oui in rpi_ouis)

@dataclass
class BluetoothConnectionInfo:
    """Bluetooth接続情報"""
    device: DeviceInfo
    state: ConnectionState
    codec: AudioCodec = AudioCodec.SBC
    bitpool: int = 53
    connected_at: Optional[datetime] = None
    reconnect_attempts: int = 0
    last_error: Optional[str] = None
    audio_active: bool = False

@dataclass 
class WiFiClientInfo:
    """WiFiクライアント情報"""
    device: DeviceInfo
    ip_address: str
    state: ConnectionState
    connected_at: datetime = field(default_factory=datetime.now)
    bytes_sent: int = 0
    bytes_received: int = 0

# =============================================================================
# 音声・メディア情報
# =============================================================================

@dataclass
class AudioBuffer:
    """音声バッファ情報"""
    buffer_size: int
    used_size: int
    write_position: int
    read_position: int
    overflow_count: int = 0
    underrun_count: int = 0
    
    @property
    def usage_percent(self) -> float:
        """使用率（%）"""
        return (self.used_size / self.buffer_size) * 100 if self.buffer_size > 0 else 0.0
    
    @property
    def free_size(self) -> int:
        """空きサイズ"""
        return self.buffer_size - self.used_size
    
    def is_full(self) -> bool:
        """満杯状態"""
        return self.used_size >= self.buffer_size
    
    def is_empty(self) -> bool:
        """空状態"""
        return self.used_size == 0

@dataclass
class AudioQualityMetrics:
    """音声品質メトリクス"""
    sample_rate: int = 44100
    channels: int = 2
    bit_rate: int = 128
    latency_ms: float = 0.0
    buffer_level_percent: float = 0.0
    codec: AudioCodec = AudioCodec.SBC
    quality_level: AudioQuality = AudioQuality.MEDIUM
    
    # 統計情報
    packets_sent: int = 0
    packets_lost: int = 0
    jitter_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def loss_rate_percent(self) -> float:
        """パケットロス率"""
        total = self.packets_sent + self.packets_lost
        return (self.packets_lost / total) * 100 if total > 0 else 0.0

@dataclass
class StreamingClientInfo:
    """ストリーミングクライアント情報"""
    client_id: str
    ip_address: str
    user_agent: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    bytes_sent: int = 0
    is_active: bool = True
    last_activity: datetime = field(default_factory=datetime.now)

# =============================================================================
# システム・パフォーマンス情報  
# =============================================================================

@dataclass
class SystemResources:
    """システムリソース情報"""
    cpu_usage_percent: float
    memory_usage_mb: int
    memory_total_mb: int
    cpu_temperature_c: float = 0.0
    disk_usage_percent: float = 0.0
    uptime_seconds: int = 0
    load_average: List[float] = field(default_factory=list)
    
    @property
    def memory_usage_percent(self) -> float:
        """メモリ使用率"""
        return (self.memory_usage_mb / self.memory_total_mb) * 100 if self.memory_total_mb > 0 else 0.0

@dataclass
class NetworkMetrics:
    """ネットワークメトリクス"""
    interface: str
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    errors_in: int = 0
    errors_out: int = 0
    dropped_in: int = 0
    dropped_out: int = 0

@dataclass
class SystemStatus:
    """システム全体の状態"""
    # サービス状態
    bluetooth_state: ServiceState
    wifi_state: ServiceState
    audio_state: ServiceState
    http_state: ServiceState
    
    # 接続情報
    bluetooth_connection: Optional[BluetoothConnectionInfo] = None
    wifi_clients: List[WiFiClientInfo] = field(default_factory=list)
    streaming_clients: List[StreamingClientInfo] = field(default_factory=list)
    
    # システム情報
    resources: Optional[SystemResources] = None
    audio_metrics: Optional[AudioQualityMetrics] = None
    
    # 統計
    uptime_seconds: int = 0
    total_connections: int = 0
    error_count: int = 0
    restart_count: int = 0
    
    def is_healthy(self) -> bool:
        """システム健全性判定"""
        critical_services = [
            self.bluetooth_state,
            self.wifi_state,
            self.audio_state,
            self.http_state
        ]
        return all(state == ServiceState.RUNNING for state in critical_services)

# =============================================================================
# 設定情報
# =============================================================================

@dataclass
class BluetoothConfig:
    """Bluetooth設定"""
    device_name: str = "AudioBridge-Pi"
    device_class: str = "0x200414"  # Audio/Video Device
    discoverable_timeout: int = 0   # 常時検出可能
    pairable_timeout: int = 0       # 常時ペアリング可能
    auto_connect: bool = True
    reconnect_interval: int = 30    # 秒

@dataclass
class WiFiConfig:
    """WiFi設定"""
    ssid: str = "AudioBridge-Pi"
    password: str = "audiobridge123"
    channel: int = 7
    ip_address: str = "192.168.4.1"
    netmask: str = "255.255.255.0"
    dhcp_start: str = "192.168.4.100"
    dhcp_end: str = "192.168.4.200"
    max_clients: int = 5

@dataclass
class AudioConfig:
    """音声設定"""
    sample_rate: int = 44100
    channels: int = 2
    buffer_size: int = 4096
    bitrate: int = 128
    quality_level: AudioQuality = AudioQuality.MEDIUM
    max_latency_ms: int = 400
    adaptive_quality: bool = True

@dataclass
class HTTPConfig:
    """HTTP設定"""
    host: str = "0.0.0.0"
    port: int = 8080
    max_clients: int = 3
    chunk_size: int = 4096
    timeout_seconds: int = 30

@dataclass
class LoggingConfig:
    """ログ設定"""
    level: LogLevel = LogLevel.INFO
    file_path: str = "/var/log/audio-bridge/audio-bridge.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    console_output: bool = True

@dataclass
class SystemConfig:
    """システム全体設定"""
    bluetooth: BluetoothConfig = field(default_factory=BluetoothConfig)
    wifi: WiFiConfig = field(default_factory=WiFiConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    http: HTTPConfig = field(default_factory=HTTPConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # 監視・復旧設定
    health_check_interval: int = 30  # 秒
    heartbeat_interval: int = 60     # 秒
    auto_recovery: bool = True
    max_recovery_attempts: int = 3

# =============================================================================
# プロトコル・インターフェース
# =============================================================================

class ComponentManager(Protocol):
    """コンポーネント管理の共通インターフェース"""
    
    def initialize(self) -> bool:
        """初期化処理"""
        ...
    
    def cleanup(self) -> None:
        """リソース解放"""
        ...
    
    def is_healthy(self) -> bool:
        """健全性チェック"""
        ...
    
    def attempt_recovery(self) -> bool:
        """復旧処理試行"""
        ...
    
    def get_status(self) -> Dict[str, Any]:
        """状態情報取得"""
        ...

class BluetoothManagerProtocol(ComponentManager, Protocol):
    """Bluetooth管理インターフェース"""
    
    def is_service_running(self) -> bool:
        """Bluetoothサービス実行確認"""
        ...
    
    def enable_discoverable(self) -> bool:
        """検出可能モード有効化"""
        ...
    
    def is_a2dp_connected(self, device_address: Optional[str] = None) -> bool:
        """A2DP接続状態確認"""
        ...
    
    def connect_a2dp(self, device_address: str) -> bool:
        """A2DP接続確立"""
        ...
    
    def disconnect_a2dp(self, device_address: str) -> bool:
        """A2DP接続切断"""
        ...
    
    def get_active_a2dp_device(self) -> Optional[str]:
        """アクティブなA2DPデバイス取得"""
        ...
    
    def get_paired_devices(self) -> List[str]:
        """ペアリング済みデバイス一覧"""
        ...

class AudioPipelineProtocol(ComponentManager, Protocol):
    """音声パイプライン管理インターフェース"""
    
    def start_audio_flow(self) -> bool:
        """音声フロー開始"""
        ...
    
    def stop_audio_flow(self) -> bool:
        """音声フロー停止"""
        ...
    
    def get_audio_quality_metrics(self) -> AudioQualityMetrics:
        """音声品質メトリクス取得"""
        ...
    
    def set_target_bitrate(self, bitrate: int) -> bool:
        """目標ビットレート設定"""
        ...
    
    def get_current_bitrate(self) -> int:
        """現在のビットレート取得"""
        ...
    
    def is_bluetooth_connected(self) -> bool:
        """Bluetooth接続状態"""
        ...

class WiFiManagerProtocol(ComponentManager, Protocol):
    """WiFi管理インターフェース"""
    
    def configure_wlan_interface(self, interface: str) -> bool:
        """ワイヤレスインターフェース設定"""
        ...
    
    def is_hostapd_running(self) -> bool:
        """hostapd実行状態確認"""
        ...
    
    def is_dnsmasq_running(self) -> bool:
        """dnsmasq実行状態確認"""
        ...
    
    def get_connected_clients_count(self) -> int:
        """接続クライアント数取得"""
        ...
    
    def get_connected_clients(self) -> Dict[str, WiFiClientInfo]:
        """接続クライアント一覧取得"""
        ...
    
    def has_connected_clients(self) -> bool:
        """接続クライアント存在確認"""
        ...

class HTTPStreamingProtocol(ComponentManager, Protocol):
    """HTTPストリーミング管理インターフェース"""
    
    def start_server(self) -> bool:
        """サーバー開始"""
        ...
    
    def stop_server(self) -> bool:
        """サーバー停止"""
        ...
    
    def get_streaming_clients(self) -> Dict[str, StreamingClientInfo]:
        """ストリーミングクライアント一覧"""
        ...
    
    def get_active_streams_count(self) -> int:
        """アクティブストリーム数"""
        ...

# =============================================================================
# 高レベルアプリケーションインターフェース
# =============================================================================

class SystemMonitorProtocol(Protocol):
    """システム監視インターフェース"""
    
    def get_system_resources(self) -> SystemResources:
        """システムリソース取得"""
        ...
    
    def get_network_metrics(self, interface: str) -> NetworkMetrics:
        """ネットワークメトリクス取得"""
        ...
    
    def check_component_health(self) -> Dict[str, bool]:
        """各コンポーネントの健全性チェック"""
        ...

class RecoveryControllerProtocol(Protocol):
    """復旧制御インターフェース"""
    
    def trigger_component_recovery(self, component: str) -> bool:
        """特定コンポーネントの復旧実行"""
        ...
    
    def trigger_system_recovery(self) -> bool:
        """システム全体の復旧実行"""
        ...
    
    def get_recovery_history(self) -> List[Dict[str, Any]]:
        """復旧履歴取得"""
        ...

class AudioBridgeMainProtocol(Protocol):
    """メインアプリケーションインターフェース"""
    
    def initialize(self) -> bool:
        """アプリケーション初期化"""
        ...
    
    def run(self) -> int:
        """メインループ実行"""
        ...
    
    def shutdown(self) -> None:
        """システム終了処理"""
        ...
    
    def get_system_status(self) -> SystemStatus:
        """システム全体状態取得"""
        ...

# =============================================================================
# イベント・コールバック
# =============================================================================

class EventType(Enum):
    """イベント種別"""
    BLUETOOTH_CONNECTED = "bluetooth_connected"
    BLUETOOTH_DISCONNECTED = "bluetooth_disconnected"  
    WIFI_CLIENT_CONNECTED = "wifi_client_connected"
    WIFI_CLIENT_DISCONNECTED = "wifi_client_disconnected"
    AUDIO_STREAM_STARTED = "audio_stream_started"
    AUDIO_STREAM_STOPPED = "audio_stream_stopped"
    HTTP_CLIENT_CONNECTED = "http_client_connected" 
    HTTP_CLIENT_DISCONNECTED = "http_client_disconnected"
    SYSTEM_ERROR = "system_error"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"

@dataclass
class SystemEvent:
    """システムイベント"""
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    source_component: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

# コールバック型定義
EventCallback = Callable[[SystemEvent], None]
AudioDataCallback = Callable[[bytes], None]
StatusChangeCallback = Callable[[str, Any], None]

class EventManagerProtocol(Protocol):
    """イベント管理インターフェース"""
    
    def register_callback(self, event_type: EventType, callback: EventCallback) -> None:
        """イベントコールバック登録"""
        ...
    
    def unregister_callback(self, event_type: EventType, callback: EventCallback) -> None:
        """イベントコールバック解除"""
        ...
    
    def emit_event(self, event: SystemEvent) -> None:
        """イベント発火"""
        ...

# =============================================================================
# API レスポンス型
# =============================================================================

@dataclass
class APIResponse:
    """API共通レスポンス形式"""
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, str]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def success_response(cls, data: Any = None) -> 'APIResponse':
        """成功レスポンス生成"""
        return cls(success=True, data=data)
    
    @classmethod
    def error_response(cls, code: str, message: str) -> 'APIResponse':
        """エラーレスポンス生成"""
        return cls(
            success=False,
            error={"code": code, "message": message}
        )

@dataclass
class StatusAPIResponse(APIResponse):
    """ステータスAPI専用レスポンス"""
    data: Optional[SystemStatus] = None

@dataclass
class MetricsAPIResponse(APIResponse):
    """メトリクスAPI専用レスポンス"""
    data: Optional[Dict[str, Any]] = None

# =============================================================================
# ユーティリティ・検証
# =============================================================================

def validate_mac_address(mac: str) -> bool:
    """MACアドレス形式検証"""
    import re
    pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
    return bool(re.match(pattern, mac))

def validate_ip_address(ip: str) -> bool:
    """IPアドレス形式検証"""
    import ipaddress
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def validate_audio_bitrate(bitrate: int) -> bool:
    """音声ビットレート検証"""
    valid_bitrates = [64, 96, 128, 160, 192, 256, 320]
    return bitrate in valid_bitrates

def validate_wifi_channel(channel: int) -> bool:
    """WiFiチャンネル検証（2.4GHz）"""
    return 1 <= channel <= 13

# =============================================================================
# 定数・制約
# =============================================================================

class AudioBridgeConstants:
    """システム定数"""
    
    # システム制約
    MAX_WIFI_CLIENTS = 5
    MAX_HTTP_STREAMS = 3
    MAX_AUDIO_LATENCY_MS = 400
    MIN_CPU_FREQUENCY = 600  # MHz
    MAX_CPU_TEMPERATURE = 75  # Celsius
    
    # バッファサイズ
    AUDIO_BUFFER_SIZE = 4096
    HTTP_CHUNK_SIZE = 4096
    
    # タイムアウト
    BLUETOOTH_CONNECT_TIMEOUT = 30  # seconds
    HTTP_STREAM_TIMEOUT = 30        # seconds
    HEALTH_CHECK_INTERVAL = 30      # seconds
    RECONNECT_INTERVAL = 30         # seconds
    
    # ファイルパス
    LOG_DIR = "/var/log/audio-bridge"
    CONFIG_DIR = "/etc/audio-bridge"
    PID_FILE = "/var/run/audio-bridge.pid"
    
    # ネットワーク
    DEFAULT_WIFI_IP = "192.168.4.1"
    DEFAULT_HTTP_PORT = 8080
    
    # Bluetooth
    BT_DEVICE_CLASS = "0x200414"  # Audio/Video Device
    BT_DEFAULT_NAME = "AudioBridge-Pi"

# =============================================================================
# 型エイリアス
# =============================================================================

# システム型
ComponentName = str
MACAddress = str
IPAddress = str
AudioSample = bytes

# 辞書型
DeviceDict = Dict[MACAddress, DeviceInfo]
ClientDict = Dict[str, Union[WiFiClientInfo, StreamingClientInfo]]
StatusDict = Dict[str, Any]
ConfigDict = Dict[str, Any]
MetricsDict = Dict[str, Union[int, float, str]]

# =============================================================================
# 互換性・レガシー対応
# =============================================================================

# ESP32からの移行互換性のためのエイリアス
A2DPSink = BluetoothManagerProtocol
WiFiAP = WiFiManagerProtocol

# バージョン情報
__version__ = "1.0.0"
__api_version__ = "v1"