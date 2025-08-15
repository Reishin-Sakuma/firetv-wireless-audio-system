# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Claude Code: Raspberry Pi Zero 2 W Bluetooth-WiFi音楽ブリッジ開発

## 🎯 プロジェクト目標

**車載環境で Android（Spotify）→ Raspberry Pi → Fire TV Stick の音楽ストリーミング環境を構築**

```
Android (Spotify) → [Bluetooth A2DP] → Raspberry Pi Zero 2W → [WiFi AP + HTTP Stream] → Fire TV Stick (VLC)
```

## 📋 技術仕様

### ハードウェア
- **Raspberry Pi Zero 2 W**: クアッドコア1GHz、512MB RAM
- **OS**: Raspberry Pi OS Lite (Headless)
- **ストレージ**: microSDカード 16GB以上
- **音質**: Spotify最高音質 320kbps対応
- **遅延**: 200-400ms（実用的）

### ソフトウェアアーキテクチャ
```
┌─────────────────────────────────────┐
│ Raspberry Pi Zero 2 W (Linux)      │
├─────────────────────────────────────┤
│ BlueZ Stack (Bluetooth A2DP Sink)  │
├─────────────────────────────────────┤
│ PulseAudio (音声パイプライン)       │
├─────────────────────────────────────┤
│ GStreamer (リアルタイム音声変換)    │
├─────────────────────────────────────┤
│ Python Flask (HTTPストリーミング)   │
├─────────────────────────────────────┤
│ hostapd + dnsmasq (WiFi AP)        │
└─────────────────────────────────────┘
```

## 🎯 Phase 1 実装要求

**今回の目標: Bluetooth A2DP Sinkの基本動作 + WiFi AP + HTTPストリーミング**

### 必須実装機能

#### 1. **システム基盤構築**
- Raspberry Pi OS Lite セットアップスクリプト
- 必要パッケージの自動インストール
- SSH有効化・基本設定

#### 2. **Bluetooth A2DP Sink実装**
- BlueZ設定・自動ペアリング
- A2DP Sink プロファイル有効化
- 自動接続・再接続機能
- 接続状態監視

#### 3. **音声パイプライン構築**
- PulseAudio設定・音声ルーティング
- GStreamer パイプライン（Bluetooth → HTTP変換）
- 音声バッファリング最適化
- 音質・遅延調整

#### 4. **WiFi Access Point**
- hostapd設定（AP モード）
- dnsmasq設定（DHCP・DNS）
- 固定IP設定（192.168.4.1）
- ファイアウォール設定

#### 5. **HTTPストリーミングサーバー**
- Python Flask ベースの音声配信
- リアルタイムMP3ストリーミング
- Fire TV Stick VLC対応
- 複数クライアント対応

#### 6. **システム自動化**
- systemd サービス設定
- 起動時自動開始
- プロセス監視・自動復旧
- ログ管理

### ファイル構成要求
```
audio-bridge/
├── setup.sh                   # 初期セットアップスクリプト
├── install_packages.sh        # パッケージインストール
├── config/
│   ├── bluetooth/
│   │   ├── main.conf          # BlueZ設定
│   │   └── audio.conf         # A2DP設定
│   ├── pulseaudio/
│   │   ├── default.pa         # PulseAudio設定
│   │   └── daemon.conf        # デーモン設定
│   ├── hostapd/
│   │   └── hostapd.conf       # WiFi AP設定
│   ├── dnsmasq/
│   │   └── dnsmasq.conf       # DHCP設定
│   └── systemd/
│       ├── audio-bridge.service
│       ├── bluetooth-agent.service
│       └── wifi-ap.service
├── src/
│   ├── audio_bridge.py        # メインアプリケーション
│   ├── bluetooth_manager.py   # Bluetooth制御
│   ├── audio_pipeline.py      # 音声処理
│   ├── http_server.py         # HTTPストリーミング
│   ├── wifi_manager.py        # WiFi AP制御
│   └── system_monitor.py      # システム監視
├── scripts/
│   ├── start_services.sh      # サービス起動
│   ├── stop_services.sh       # サービス停止
│   ├── bluetooth_pair.sh      # ペアリング支援
│   └── status_check.sh        # 状態確認
├── logs/                      # ログディレクトリ
├── README.md                  # セットアップ・使用方法
└── requirements.txt           # Python依存関係
```

## 🔧 技術的実装要求

### Bluetooth A2DP設定
```bash
# /etc/bluetooth/main.conf
[General]
Class = 0x200414
DiscoverableTimeout = 0
PairableTimeout = 0
AutoEnable = true

[A2DP]
Enable = Sink
AutoConnect = true
```

### PulseAudio設定
```bash
# /etc/pulse/default.pa
load-module module-bluetooth-discover
load-module module-bluetooth-policy
set-default-sink bluez_sink
```

### GStreamer音声パイプライン
```python
# 基本パイプライン
pipeline = "pulsesrc device=bluez_sink.monitor ! audioconvert ! audioresample ! lamemp3enc bitrate=128 ! shout2send"
```

### WiFi AP設定
```bash
# /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=AudioBridge-Pi
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=audiobridge123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
```

### HTTPストリーミング実装
```python
from flask import Flask, Response
import subprocess
import threading

app = Flask(__name__)

@app.route('/audio.mp3')
def stream_audio():
    def generate():
        cmd = [
            'gst-launch-1.0',
            'pulsesrc', 'device=bluez_sink.monitor',
            '!', 'audioconvert',
            '!', 'audioresample',
            '!', 'lamemp3enc', 'bitrate=128',
            '!', 'fdsink', 'fd=1'
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            yield chunk
    
    return Response(generate(), 
                   mimetype='audio/mpeg',
                   headers={'Cache-Control': 'no-cache'})

@app.route('/status')
def status():
    return {
        'bluetooth': get_bluetooth_status(),
        'audio': get_audio_status(),
        'clients': get_connected_clients()
    }
```

## 🧪 テスト・検証要求

### 基本動作テスト
1. **Raspberry Pi OS セットアップ**
   ```bash
   sudo ./setup.sh
   sudo reboot
   ```

2. **Bluetooth接続テスト**
   ```bash
   sudo systemctl status bluetooth
   bluetoothctl discoverable on
   # Android側でAudioBridge-Pi検索・ペアリング
   ```

3. **音声パイプラインテスト**
   ```bash
   pulseaudio --check -v
   pactl list sources | grep bluez
   ```

4. **WiFi APテスト**
   ```bash
   sudo systemctl status hostapd
   iwconfig wlan0
   # Fire TV StickでAudioBridge-Pi WiFi接続
   ```

5. **HTTPストリーミングテスト**
   ```bash
   curl -I http://192.168.4.1:8080/audio.mp3
   # Fire TV Stick VLCで http://192.168.4.1:8080/audio.mp3 再生
   ```

### 統合テスト
1. **Android → Raspberry Pi → Fire TV Stick**
2. **Spotify音楽再生**
3. **30分連続動作テスト**
4. **接続切断・再接続テスト**

### 成功判定基準
- [ ] Android Bluetooth自動ペアリング成功
- [ ] Spotify音楽がFire TV Stickで再生される
- [ ] 音質劣化が最小限（主観評価）
- [ ] 遅延400ms以内
- [ ] 30分間の連続再生が安定
- [ ] 接続切断時の自動復旧機能

## ⚙️ 設定・最適化要求

### 音質・遅延調整
```python
# 音質優先設定
AUDIO_BITRATE = 320  # kbps
BUFFER_SIZE = 4096   # bytes
SAMPLE_RATE = 44100  # Hz

# 低遅延優先設定  
AUDIO_BITRATE = 128  # kbps
BUFFER_SIZE = 1024   # bytes
LATENCY_TARGET = 200 # ms
```

### システム最適化
```bash
# CPUガバナー設定
echo performance | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# オーディオ優先度調整
echo '@audio - rtprio 99' | sudo tee -a /etc/security/limits.conf
```

## 📝 ドキュメント要求

### README.md 必須項目
1. **ハードウェア要求・セットアップ**
2. **自動インストール手順**
3. **Android・Fire TV Stick設定方法**
4. **トラブルシューティング**
5. **音質・遅延調整方法**
6. **車載環境での設置方法**

### 操作・保守ガイド
```bash
# システム状態確認
./scripts/status_check.sh

# サービス再起動
./scripts/restart_services.sh

# ログ確認
journalctl -u audio-bridge -f

# 音質調整
sudo nano config/audio_pipeline.conf
```

## 🔧 エラーハンドリング要求

### 必須エラー処理
1. **Bluetooth接続失敗・切断**
2. **音声パイプライン中断**
3. **WiFi AP接続失敗**
4. **HTTPストリーミング中断**
5. **メモリ・CPU使用量異常**
6. **システムリソース不足**

### 自動復旧機能
```python
# プロセス監視・再起動
def monitor_processes():
    for service in ['bluetooth', 'pulseaudio', 'hostapd']:
        if not is_service_running(service):
            restart_service(service)
            log_warning(f"Restarted {service}")
```

## 🎯 開発指示

**Claude Code での実行手順:**

1. **プロジェクト構造作成**
   ```bash
   mkdir audio-bridge && cd audio-bridge
   mkdir -p config/{bluetooth,pulseaudio,hostapd,dnsmasq,systemd}
   mkdir -p src scripts logs
   ```

2. **セットアップスクリプト作成**
   - setup.sh: 全自動セットアップ
   - install_packages.sh: 必要パッケージインストール
   - 設定ファイル一式

3. **アプリケーション実装**
   - audio_bridge.py: メインアプリケーション
   - 各コンポーネント（Bluetooth、音声、WiFi、HTTP）
   - systemd サービス定義

4. **テスト・検証**
   - 仮想環境でのテスト
   - 実機でのBluetooth接続テスト
   - Fire TV Stick連携テスト

**開発完了条件:**
- すべてのファイル・スクリプトが作成されている
- setup.sh で完全自動セットアップが可能
- Android接続 → Fire TV Stick再生までの全工程が動作
- README.mdが完成している
- 30分間の安定動作を確認

**技術方針:**
- 既存のLinuxツール最大活用
- Python中心の実装
- systemd による堅牢なサービス管理
- 包括的なエラーハンドリング・ログ機能

---

**⚡ 今すぐ開始してください！ ⚡**

このプロンプトに基づき、Raspberry Pi Zero 2 W で確実に動作するBluetooth-WiFi音楽ブリッジを完全実装してください。ESP32の制約を完全に解決した、安定動作する車載音楽環境の構築が目標です。