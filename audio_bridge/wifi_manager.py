"""
WiFi Access Point管理モジュール
ESP32のWiFiAPクラスをRaspberry Pi/hostapd用に移行
"""

import logging
import subprocess
import time
import threading
import socket
import netifaces
from pathlib import Path
from .config import *

logger = logging.getLogger(__name__)

class WiFiManager:
    """WiFi Access Point管理クラス"""
    
    def __init__(self):
        self.initialized = False
        self.ap_started = False
        self.connected_clients = {}
        self.interface = "wlan0"
        self.monitor_thread = None
        self.monitoring = False
        
    def initialize(self):
        """WiFi AP機能の初期化"""
        try:
            logger.info("[WIFI] Initializing WiFi Access Point...")
            
            # ネットワークインターフェース確認
            if not self._check_interface_available():
                logger.error(f"[WIFI] Interface {self.interface} not available")
                return False
            
            # hostapdサービス停止（設定変更のため）
            self._stop_service(HOSTAPD_SERVICE_NAME)
            self._stop_service(DNSMASQ_SERVICE_NAME)
            
            # インターフェース設定
            if not self.configure_wlan_interface(self.interface):
                logger.error("[WIFI] Failed to configure interface")
                return False
            
            # hostapd設定
            if not self._configure_hostapd():
                logger.error("[WIFI] Failed to configure hostapd")
                return False
            
            # dnsmasq設定
            if not self._configure_dnsmasq():
                logger.error("[WIFI] Failed to configure dnsmasq")
                return False
            
            # ファイアウォール設定
            if not self._configure_firewall():
                logger.warning("[WIFI] Firewall configuration failed")
            
            # サービス開始
            if not self._start_services():
                logger.error("[WIFI] Failed to start services")
                return False
            
            # クライアント監視開始
            self._start_client_monitoring()
            
            self.initialized = True
            self.ap_started = True
            logger.info(f"[WIFI] Access Point started: {WIFI_AP_SSID}")
            logger.info(f"[WIFI] IP Address: {WIFI_AP_IP}")
            
            return True
            
        except Exception as e:
            logger.error(f"[WIFI] Initialization failed: {e}")
            return False
    
    def _check_interface_available(self):
        """ネットワークインターフェース利用可能性確認"""
        try:
            interfaces = netifaces.interfaces()
            if self.interface not in interfaces:
                logger.error(f"[WIFI] Interface {self.interface} not found")
                return False
            
            # WiFiインターフェースかチェック
            if not Path(f"/sys/class/net/{self.interface}/wireless").exists():
                logger.warning(f"[WIFI] {self.interface} may not be a wireless interface")
            
            return True
            
        except Exception as e:
            logger.error(f"[WIFI] Interface check failed: {e}")
            return False
    
    def configure_wlan_interface(self, interface):
        """ワイヤレスインターフェース設定"""
        try:
            logger.info(f"[WIFI] Configuring interface {interface}")
            
            # インターフェースダウン
            subprocess.run(["sudo", "ip", "link", "set", interface, "down"], 
                         check=True, capture_output=True)
            
            # 静的IP設定
            subprocess.run([
                "sudo", "ip", "addr", "flush", "dev", interface
            ], check=True, capture_output=True)
            
            subprocess.run([
                "sudo", "ip", "addr", "add", f"{WIFI_AP_IP}/{self._cidr_from_netmask(WIFI_AP_NETMASK)}",
                "dev", interface
            ], check=True, capture_output=True)
            
            # インターフェースアップ
            subprocess.run(["sudo", "ip", "link", "set", interface, "up"], 
                         check=True, capture_output=True)
            
            # IP forwarding有効化
            subprocess.run([
                "sudo", "sysctl", "net.ipv4.ip_forward=1"
            ], check=True, capture_output=True)
            
            logger.info(f"[WIFI] Interface {interface} configured with IP {WIFI_AP_IP}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"[WIFI] Interface configuration failed: {e}")
            return False
    
    def _cidr_from_netmask(self, netmask):
        """ネットマスクからCIDR表記に変換"""
        return sum([bin(int(x)).count('1') for x in netmask.split('.')])
    
    def get_interface_config(self, interface):
        """インターフェース設定取得"""
        try:
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                inet_info = addrs[netifaces.AF_INET][0]
                return {
                    "ip": inet_info.get("addr"),
                    "netmask": inet_info.get("netmask"),
                    "broadcast": inet_info.get("broadcast")
                }
            return {}
        except:
            return {}
    
    def _configure_hostapd(self):
        """hostapd設定ファイル作成"""
        try:
            hostapd_conf = f"""# hostapd configuration for AudioBridge-Pi
interface={self.interface}
driver=nl80211
ssid={WIFI_AP_SSID}
hw_mode=g
channel={WIFI_AP_CHANNEL}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={WIFI_AP_PASSWORD}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
            
            config_path = HOSTAPD_CONFIG_DIR / "hostapd.conf"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, "w") as f:
                f.write(hostapd_conf)
            
            # hostapdデーモン設定更新
            daemon_conf = f'DAEMON_CONF="{config_path}"\n'
            with open("/etc/default/hostapd", "w") as f:
                f.write(daemon_conf)
            
            logger.info("[WIFI] hostapd configuration created")
            return True
            
        except Exception as e:
            logger.error(f"[WIFI] hostapd configuration failed: {e}")
            return False
    
    def _configure_dnsmasq(self):
        """dnsmasq設定ファイル作成"""
        try:
            dnsmasq_conf = f"""# dnsmasq configuration for AudioBridge-Pi
interface={self.interface}
dhcp-range={WIFI_AP_DHCP_RANGE_START},{WIFI_AP_DHCP_RANGE_END},255.255.255.0,24h
domain=local
address=/gw.local/{WIFI_AP_IP}
dhcp-option=3,{WIFI_AP_IP}
dhcp-option=6,{WIFI_AP_IP}
server=8.8.8.8
log-queries
log-dhcp
listen-address={WIFI_AP_IP}
"""
            
            config_path = DNSMASQ_CONFIG_DIR / "dnsmasq.conf"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, "w") as f:
                f.write(dnsmasq_conf)
            
            # dnsmasq設定をシステムにコピー
            subprocess.run([
                "sudo", "cp", str(config_path), "/etc/dnsmasq.d/audiobridge.conf"
            ], check=True, capture_output=True)
            
            logger.info("[WIFI] dnsmasq configuration created")
            return True
            
        except Exception as e:
            logger.error(f"[WIFI] dnsmasq configuration failed: {e}")
            return False
    
    def _configure_firewall(self):
        """iptablesファイアウォール設定"""
        try:
            # 既存ルール削除
            subprocess.run([
                "sudo", "iptables", "-t", "nat", "-F", "POSTROUTING"
            ], capture_output=True)
            
            subprocess.run([
                "sudo", "iptables", "-F", "FORWARD"
            ], capture_output=True)
            
            # HTTP通信許可
            subprocess.run([
                "sudo", "iptables", "-A", "INPUT", "-p", "tcp", 
                "--dport", str(HTTP_SERVER_PORT), "-j", "ACCEPT"
            ], check=True, capture_output=True)
            
            # WiFi インターフェース間通信許可
            subprocess.run([
                "sudo", "iptables", "-A", "FORWARD", "-i", self.interface,
                "-o", self.interface, "-j", "ACCEPT"
            ], check=True, capture_output=True)
            
            # established/related接続許可
            subprocess.run([
                "sudo", "iptables", "-A", "FORWARD", "-m", "conntrack", 
                "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"
            ], check=True, capture_output=True)
            
            logger.info("[WIFI] Firewall rules configured")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"[WIFI] Firewall configuration failed: {e}")
            return False
    
    def _start_services(self):
        """WiFi AP関連サービス開始"""
        try:
            services = [HOSTAPD_SERVICE_NAME, DNSMASQ_SERVICE_NAME]
            
            for service in services:
                # サービス有効化・開始
                subprocess.run([
                    "sudo", "systemctl", "enable", service
                ], check=True, capture_output=True)
                
                subprocess.run([
                    "sudo", "systemctl", "start", service
                ], check=True, capture_output=True)
                
                # 開始確認
                time.sleep(2)
                if not self._is_service_running(service):
                    logger.error(f"[WIFI] Service {service} failed to start")
                    return False
                
                logger.info(f"[WIFI] Service {service} started successfully")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"[WIFI] Service start failed: {e}")
            return False
    
    def _stop_service(self, service_name):
        """サービス停止"""
        try:
            subprocess.run([
                "sudo", "systemctl", "stop", service_name
            ], capture_output=True)
        except:
            pass  # 停止失敗は無視
    
    def _is_service_running(self, service_name):
        """サービス実行状態確認"""
        try:
            result = subprocess.run([
                "systemctl", "is-active", service_name
            ], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def is_hostapd_running(self):
        """hostapd実行状態確認"""
        return self._is_service_running(HOSTAPD_SERVICE_NAME)
    
    def is_dnsmasq_running(self):
        """dnsmasq実行状態確認"""
        return self._is_service_running(DNSMASQ_SERVICE_NAME)
    
    def get_ap_ssid(self):
        """AP SSID取得"""
        return WIFI_AP_SSID
    
    def get_ap_password(self):
        """APパスワード取得"""
        return WIFI_AP_PASSWORD
    
    def get_ap_ip(self):
        """AP IPアドレス取得"""
        return WIFI_AP_IP
    
    def get_dhcp_range(self):
        """DHCP範囲取得"""
        return {
            "start": WIFI_AP_DHCP_RANGE_START,
            "end": WIFI_AP_DHCP_RANGE_END
        }
    
    def get_dns_server(self):
        """DNSサーバー取得"""
        return WIFI_AP_IP
    
    def _start_client_monitoring(self):
        """クライアント監視開始"""
        def monitor_clients():
            while self.monitoring and self.initialized:
                try:
                    self._update_connected_clients()
                    time.sleep(5)  # 5秒間隔で監視
                except Exception as e:
                    logger.error(f"[WIFI] Client monitoring error: {e}")
                    time.sleep(10)
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=monitor_clients, daemon=True)
        self.monitor_thread.start()
        logger.info("[WIFI] Client monitoring started")
    
    def _update_connected_clients(self):
        """接続クライアント情報更新"""
        try:
            # ARP テーブルから接続クライアント取得
            result = subprocess.run([
                "arp", "-a"
            ], capture_output=True, text=True)
            
            current_clients = {}
            
            for line in result.stdout.split('\n'):
                if WIFI_AP_IP.split('.')[0:3] == line.split()[0].strip('()').split('.')[0:3]:
                    # 同じネットワーク内のクライアント
                    parts = line.split()
                    if len(parts) >= 4:
                        ip = parts[1].strip('()')
                        mac = parts[3]
                        
                        # デバイス名推測（簡易実装）
                        device_name = self._guess_device_name(mac)
                        
                        current_clients[mac] = {
                            "ip": ip,
                            "device_name": device_name,
                            "last_seen": time.time()
                        }
            
            self.connected_clients = current_clients
            
        except Exception as e:
            logger.debug(f"[WIFI] Client update error: {e}")
    
    def _guess_device_name(self, mac_address):
        """MACアドレスからデバイス名推測"""
        # Fire TV Stick のMAC OUI例
        fire_tv_ouis = ["50:F5:DA", "CC:86:EC", "AC:63:BE"]
        
        mac_upper = mac_address.upper()
        for oui in fire_tv_ouis:
            if mac_upper.startswith(oui):
                return "Fire TV"
        
        # その他の一般的なデバイス
        if mac_upper.startswith("B8:27:EB"):
            return "Raspberry Pi"
        elif mac_upper.startswith("DC:A6:32"):
            return "Raspberry Pi"
        
        return "Unknown Device"
    
    def get_connected_clients_count(self):
        """接続クライアント数取得"""
        return len(self.connected_clients)
    
    def has_connected_clients(self):
        """接続クライアント存在確認"""
        return len(self.connected_clients) > 0
    
    def get_connected_clients(self):
        """接続クライアント一覧取得"""
        return self.connected_clients.copy()
    
    def _simulate_client_connection(self, mac, ip, device_name):
        """クライアント接続シミュレーション（テスト用）"""
        self.connected_clients[mac] = {
            "ip": ip,
            "device_name": device_name,
            "last_seen": time.time()
        }
    
    def is_ip_forwarding_enabled(self):
        """IP forwarding有効状態確認"""
        try:
            with open("/proc/sys/net/ipv4/ip_forward", "r") as f:
                return f.read().strip() == "1"
        except:
            return False
    
    def get_firewall_rules(self):
        """ファイアウォールルール取得"""
        try:
            result = subprocess.run([
                "iptables", "-L", "-n"
            ], capture_output=True, text=True)
            return result.stdout.split('\n')
        except:
            return []
    
    def get_nat_rules(self):
        """NATルール取得"""
        try:
            result = subprocess.run([
                "iptables", "-t", "nat", "-L", "-n"
            ], capture_output=True, text=True)
            return result.stdout.split('\n')
        except:
            return []
    
    def has_clients(self):
        """クライアント接続確認（互換性のため）"""
        return self.has_connected_clients()
    
    def isAPStarted(self):
        """AP開始状態確認（互換性のため）"""
        return self.ap_started
    
    def cleanup(self):
        """リソース解放"""
        logger.info("[WIFI] Cleaning up WiFi resources...")
        self.monitoring = False
        self.initialized = False
        
        # サービス停止
        services = [HOSTAPD_SERVICE_NAME, DNSMASQ_SERVICE_NAME]
        for service in services:
            self._stop_service(service)
    
    def __del__(self):
        """デストラクタ"""
        self.cleanup()