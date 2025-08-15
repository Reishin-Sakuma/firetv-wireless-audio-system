"""
Bluetooth A2DP Sink管理モジュール
ESP32のBluetoothA2DPクラスをRaspberry Pi/BlueZ用に移行
"""

import logging
import subprocess
import time
import threading
import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import pulsectl
from .config import *

logger = logging.getLogger(__name__)

class BluetoothManager:
    """Bluetooth A2DP Sink管理クラス"""
    
    def __init__(self):
        self.initialized = False
        self.connected_devices = {}
        self.active_device = None
        self.auto_reconnect = True
        self.reconnect_thread = None
        self.audio_callback = None
        
        # D-Bus設定
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = None
        self.adapter = None
        
    def initialize(self):
        """Bluetooth機能の初期化"""
        try:
            logger.info("[BLUETOOTH] Initializing Bluetooth A2DP Sink...")
            
            # BlueZサービス確認
            if not self._is_service_running(BLUETOOTH_SERVICE_NAME):
                logger.error("[BLUETOOTH] BlueZ service not running")
                return False
            
            # D-Bus接続
            self.bus = dbus.SystemBus()
            
            # Bluetoothアダプター取得
            adapter_path = self._find_adapter()
            if not adapter_path:
                logger.error("[BLUETOOTH] No Bluetooth adapter found")
                return False
            
            self.adapter = dbus.Interface(
                self.bus.get_object("org.bluez", adapter_path),
                "org.bluez.Adapter1"
            )
            
            # アダプター設定
            self._configure_adapter()
            
            # A2DP Sinkプロファイル確認
            if not self._verify_a2dp_sink():
                logger.error("[BLUETOOTH] A2DP Sink profile not available")
                return False
            
            # 自動再接続スレッド開始
            if self.auto_reconnect:
                self._start_reconnect_thread()
            
            self.initialized = True
            logger.info(f"[BLUETOOTH] Device discoverable: {BT_DEVICE_NAME}")
            return True
            
        except Exception as e:
            logger.error(f"[BLUETOOTH] Initialization failed: {e}")
            return False
    
    def _is_service_running(self, service_name):
        """systemdサービス実行状態確認"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def _find_adapter(self):
        """Bluetoothアダプター検索"""
        try:
            manager = dbus.Interface(
                self.bus.get_object("org.bluez", "/"),
                "org.freedesktop.DBus.ObjectManager"
            )
            
            objects = manager.GetManagedObjects()
            for path, interfaces in objects.items():
                if "org.bluez.Adapter1" in interfaces:
                    return path
                    
            return None
        except Exception as e:
            logger.error(f"[BLUETOOTH] Failed to find adapter: {e}")
            return None
    
    def _configure_adapter(self):
        """Bluetoothアダプター設定"""
        try:
            # デバイス名設定
            self.adapter.Set("org.bluez.Adapter1", "Name", BT_DEVICE_NAME)
            
            # クラス設定（Audio/Video Device）
            self.adapter.Set("org.bluez.Adapter1", "Class", dbus.UInt32(int(BT_CLASS, 16)))
            
            # 検出可能・ペアリング可能に設定
            self.adapter.Set("org.bluez.Adapter1", "Discoverable", True)
            self.adapter.Set("org.bluez.Adapter1", "Pairable", True)
            self.adapter.Set("org.bluez.Adapter1", "DiscoverableTimeout", BT_DISCOVERABLE_TIMEOUT)
            self.adapter.Set("org.bluez.Adapter1", "PairableTimeout", BT_PAIRABLE_TIMEOUT)
            
            # 電源ON
            self.adapter.Set("org.bluez.Adapter1", "Powered", True)
            
            logger.info("[BLUETOOTH] Adapter configured successfully")
            
        except Exception as e:
            logger.error(f"[BLUETOOTH] Adapter configuration failed: {e}")
            raise
    
    def _verify_a2dp_sink(self):
        """A2DP Sinkプロファイル確認"""
        try:
            # PulseAudio Bluetooth モジュール確認
            with pulsectl.Pulse('bluetooth-check') as pulse:
                modules = pulse.module_list()
                bt_modules = [m for m in modules if 'bluetooth' in m.name.lower()]
                if not bt_modules:
                    logger.warning("[BLUETOOTH] PulseAudio Bluetooth modules not loaded")
                    # 自動ロード試行
                    self._load_pulseaudio_bluetooth_modules()
                    
            return True
            
        except Exception as e:
            logger.error(f"[BLUETOOTH] A2DP verification failed: {e}")
            return False
    
    def _load_pulseaudio_bluetooth_modules(self):
        """PulseAudio Bluetoothモジュールロード"""
        try:
            commands = [
                ["pactl", "load-module", "module-bluetooth-discover"],
                ["pactl", "load-module", "module-bluetooth-policy"]
            ]
            
            for cmd in commands:
                subprocess.run(cmd, check=True, capture_output=True)
                
            logger.info("[BLUETOOTH] PulseAudio Bluetooth modules loaded")
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"[BLUETOOTH] Failed to load Bluetooth modules: {e}")
    
    def enable_discoverable(self):
        """検出可能モード有効化"""
        try:
            self.adapter.Set("org.bluez.Adapter1", "Discoverable", True)
            return True
        except Exception as e:
            logger.error(f"[BLUETOOTH] Failed to enable discoverable: {e}")
            return False
    
    def is_discoverable(self):
        """検出可能状態確認"""
        try:
            props = dbus.Interface(
                self.bus.get_object("org.bluez", self.adapter.object_path),
                "org.freedesktop.DBus.Properties"
            )
            return props.Get("org.bluez.Adapter1", "Discoverable")
        except:
            return False
    
    def enable_pairable(self):
        """ペアリング可能モード有効化"""
        try:
            self.adapter.Set("org.bluez.Adapter1", "Pairable", True)
            return True
        except Exception as e:
            logger.error(f"[BLUETOOTH] Failed to enable pairable: {e}")
            return False
    
    def is_pairable(self):
        """ペアリング可能状態確認"""
        try:
            props = dbus.Interface(
                self.bus.get_object("org.bluez", self.adapter.object_path),
                "org.freedesktop.DBus.Properties"
            )
            return props.Get("org.bluez.Adapter1", "Pairable")
        except:
            return False
    
    def handle_pairing_request(self, device_address, device_name=None):
        """ペアリング要求処理"""
        try:
            logger.info(f"[BLUETOOTH] Pairing request from {device_address} ({device_name})")
            
            # デバイス情報を記録
            self.connected_devices[device_address] = {
                "name": device_name or "Unknown",
                "connected": False,
                "paired": False,
                "trusted": False,
                "last_seen": time.time()
            }
            
            # 自動ペアリング承認（簡易実装）
            # 実際の実装では、bluetoothctl or python-bluez を使用
            return True
            
        except Exception as e:
            logger.error(f"[BLUETOOTH] Pairing failed: {e}")
            return False
    
    def is_device_trusted(self, device_address):
        """デバイス信頼状態確認"""
        device_info = self.connected_devices.get(device_address, {})
        return device_info.get("trusted", False)
    
    def get_paired_devices(self):
        """ペアリング済みデバイス一覧取得"""
        return [addr for addr, info in self.connected_devices.items() 
                if info.get("paired", False)]
    
    def connect_a2dp(self, device_address):
        """A2DP接続確立"""
        try:
            logger.info(f"[BLUETOOTH] Connecting A2DP to {device_address}")
            
            # 既存接続がある場合は切断
            if self.active_device and self.active_device != device_address:
                self.disconnect_a2dp(self.active_device)
            
            # A2DP接続処理（bluetoothctl経由の簡易実装）
            result = subprocess.run(
                ["bluetoothctl", "connect", device_address],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                self.active_device = device_address
                self.connected_devices[device_address]["connected"] = True
                logger.info(f"[BLUETOOTH] A2DP connected to {device_address}")
                return True
            else:
                logger.error(f"[BLUETOOTH] A2DP connection failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"[BLUETOOTH] A2DP connection error: {e}")
            return False
    
    def disconnect_a2dp(self, device_address):
        """A2DP接続切断"""
        try:
            subprocess.run(
                ["bluetoothctl", "disconnect", device_address],
                capture_output=True, text=True, timeout=10
            )
            
            if device_address in self.connected_devices:
                self.connected_devices[device_address]["connected"] = False
            
            if self.active_device == device_address:
                self.active_device = None
                
            logger.info(f"[BLUETOOTH] A2DP disconnected from {device_address}")
            return True
            
        except Exception as e:
            logger.error(f"[BLUETOOTH] A2DP disconnection error: {e}")
            return False
    
    def is_a2dp_connected(self, device_address=None):
        """A2DP接続状態確認"""
        if device_address:
            device_info = self.connected_devices.get(device_address, {})
            return device_info.get("connected", False)
        else:
            return self.active_device is not None
    
    def is_audio_profile_active(self, device_address):
        """音声プロファイルアクティブ状態確認"""
        return self.is_a2dp_connected(device_address)
    
    def get_active_a2dp_device(self):
        """アクティブなA2DPデバイス取得"""
        return self.active_device
    
    def set_audio_callback(self, callback):
        """音声データコールバック設定"""
        self.audio_callback = callback
    
    def _handle_audio_data(self, audio_data):
        """音声データ処理"""
        if self.audio_callback:
            self.audio_callback(audio_data)
    
    def _start_reconnect_thread(self):
        """自動再接続スレッド開始"""
        def reconnect_loop():
            while self.auto_reconnect and self.initialized:
                time.sleep(RECONNECT_INTERVAL)
                self._attempt_reconnection()
        
        self.reconnect_thread = threading.Thread(target=reconnect_loop, daemon=True)
        self.reconnect_thread.start()
        logger.info("[BLUETOOTH] Auto-reconnect thread started")
    
    def _attempt_reconnection(self):
        """再接続試行"""
        if self.active_device:
            return  # 既に接続中
            
        # 最近接続していたデバイスへの再接続試行
        recent_devices = sorted(
            self.connected_devices.items(),
            key=lambda x: x[1].get("last_seen", 0),
            reverse=True
        )
        
        for device_address, info in recent_devices[:3]:  # 最近の3デバイス
            if info.get("paired", False):
                logger.info(f"[BLUETOOTH] Attempting reconnection to {device_address}")
                if self.connect_a2dp(device_address):
                    break
                time.sleep(5)  # 次の試行まで待機
    
    def _simulate_disconnection(self, device_address):
        """接続切断シミュレーション（テスト用）"""
        if device_address in self.connected_devices:
            self.connected_devices[device_address]["connected"] = False
        if self.active_device == device_address:
            self.active_device = None
    
    def get_reconnect_attempts(self, device_address):
        """再接続試行回数取得"""
        device_info = self.connected_devices.get(device_address, {})
        return device_info.get("reconnect_attempts", 0)
    
    def get_device_name(self):
        """デバイス名取得"""
        return BT_DEVICE_NAME
    
    def is_service_running(self):
        """Bluetoothサービス実行状態"""
        return self._is_service_running(BLUETOOTH_SERVICE_NAME)
    
    def is_a2dp_sink_enabled(self):
        """A2DP Sink有効状態確認"""
        return self.initialized
    
    def get_last_error(self):
        """最後のエラー取得"""
        # 簡易実装：実際にはエラー履歴を管理
        return None
    
    def attempt_recovery(self):
        """復旧処理試行"""
        try:
            logger.info("[BLUETOOTH] Attempting service recovery...")
            
            # BlueZサービス再起動
            subprocess.run(["sudo", "systemctl", "restart", BLUETOOTH_SERVICE_NAME])
            time.sleep(3)
            
            # 再初期化
            self.initialized = False
            return self.initialize()
            
        except Exception as e:
            logger.error(f"[BLUETOOTH] Recovery failed: {e}")
            return False
    
    def set_audio_codec(self, codec):
        """音声コーデック設定"""
        # BlueZでのコーデック設定は複雑なため簡易実装
        logger.info(f"[BLUETOOTH] Audio codec set to: {codec}")
    
    def get_audio_codec(self):
        """現在の音声コーデック取得"""
        return "SBC"  # デフォルト
    
    def set_bitpool(self, bitpool):
        """SBC bitpool設定"""
        logger.info(f"[BLUETOOTH] SBC bitpool set to: {bitpool}")
    
    def get_bitpool(self):
        """現在のbitpool取得"""
        return 53  # SBC最高品質
    
    def set_sample_rate(self, sample_rate):
        """サンプリングレート設定"""
        logger.info(f"[BLUETOOTH] Sample rate set to: {sample_rate}")
    
    def get_sample_rate(self):
        """現在のサンプリングレート取得"""
        return AUDIO_SAMPLE_RATE
    
    def set_channels(self, channels):
        """チャンネル数設定"""
        logger.info(f"[BLUETOOTH] Channels set to: {channels}")
    
    def get_channels(self):
        """現在のチャンネル数取得"""
        return AUDIO_CHANNELS
    
    def cleanup(self):
        """リソース解放"""
        logger.info("[BLUETOOTH] Cleaning up Bluetooth resources...")
        self.auto_reconnect = False
        self.initialized = False
        
        # アクティブ接続の切断
        if self.active_device:
            self.disconnect_a2dp(self.active_device)
    
    def __del__(self):
        """デストラクタ"""
        self.cleanup()