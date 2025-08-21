# AudioBridge-Pi API エンドポイント仕様

## API概要

AudioBridge-Pi HTTP API は、システムの状態監視、制御、および音声ストリーミング機能を提供するRESTful APIです。
Fire TV Stick等のクライアントによる音声受信と、管理システムによる監視・制御の両方をサポートします。

**ベースURL**: `http://{raspberry-pi-ip}:8080`
**デフォルトIP**: `http://192.168.4.1:8080`
**APIバージョン**: v1
**認証**: 管理API（オプション）、ストリーミング API（なし）

## レスポンス形式

### 標準レスポンス構造
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2025-08-21T10:30:00Z"
}
```

### エラーレスポンス構造
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message"
  },
  "timestamp": "2025-08-21T10:30:00Z"
}
```

---

## 🎵 音声ストリーミング API

### GET /audio.mp3
**メイン音声ストリーミングエンドポイント**

Bluetooth A2DPから受信した音声をリアルタイムMP3ストリームとして配信します。VLC等のメディアプレイヤーで直接再生可能です。

**レスポンス**:
- **Content-Type**: `audio/mpeg`
- **Transfer-Encoding**: `chunked`
- **Cache-Control**: `no-cache`

**実装例（VLC）**:
```
http://192.168.4.1:8080/audio.mp3
```

**実装例（curl）**:
```bash
curl -v http://192.168.4.1:8080/audio.mp3 > audio_stream.mp3
```

**音声仕様**:
- **フォーマット**: MPEG-1 Audio Layer III (MP3)
- **ビットレート**: 128-320 kbps（設定・適応制御による）
- **サンプリングレート**: 44.1kHz
- **チャンネル**: ステレオ
- **遅延**: 200-400ms（エンドツーエンド）

---

## 📊 システム状態監視 API

### GET /status
**システム全体の状態情報取得**

現在のシステム状態、接続情報、パフォーマンスメトリクスを取得します。

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "system": {
      "uptime_seconds": 3600,
      "timestamp": "2025-08-21T10:30:00Z",
      "version": "1.0.0",
      "environment": "production"
    },
    "services": {
      "bluetooth": {
        "state": "running",
        "connection": {
          "device": {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "name": "Galaxy S21",
            "device_type": "smartphone"
          },
          "state": "connected",
          "codec": "sbc",
          "connected_at": "2025-08-21T10:15:30Z",
          "audio_active": true
        }
      },
      "wifi": {
        "state": "running",
        "clients": [
          {
            "mac_address": "50:F5:DA:11:22:33",
            "name": "Fire TV",
            "ip_address": "192.168.4.101",
            "connected_at": "2025-08-21T10:20:15Z"
          }
        ]
      },
      "audio": {
        "state": "running",
        "metrics": {
          "sample_rate": 44100,
          "bit_rate": 128,
          "latency_ms": 180.5,
          "buffer_level_percent": 65.2
        }
      },
      "http": {
        "state": "running",
        "active_streams": 1,
        "clients": [
          {
            "client_id": "192.168.4.101_1692614400",
            "ip_address": "192.168.4.101",
            "start_time": "2025-08-21T10:20:00Z",
            "bytes_sent": 1048576
          }
        ]
      }
    },
    "resources": {
      "cpu_usage_percent": 25.3,
      "memory_usage_mb": 65,
      "memory_total_mb": 512,
      "cpu_temperature_c": 52.1
    }
  }
}
```

### GET /health
**簡易ヘルスチェック**

システムの基本的な生存確認用エンドポイント。外部監視システム用。

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "healthy": true,
    "services": {
      "bluetooth": "running",
      "wifi": "running", 
      "audio": "running",
      "http": "running"
    },
    "timestamp": "2025-08-21T10:30:00Z"
  }
}
```

---

## 📈 メトリクス・監視 API

### GET /metrics
**詳細パフォーマンスメトリクス**

システムの詳細なパフォーマンスデータを取得します。

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "audio": {
      "quality_metrics": {
        "sample_rate": 44100,
        "channels": 2,
        "bit_rate": 128,
        "latency_ms": 180.5,
        "buffer_level_percent": 65.2,
        "packets_sent": 15420,
        "packets_lost": 2,
        "loss_rate_percent": 0.013,
        "jitter_ms": 2.1
      },
      "pipeline_status": {
        "gstreamer_state": "playing",
        "pulseaudio_running": true,
        "bluetooth_sink_active": true
      }
    },
    "network": {
      "wifi": {
        "interface": "wlan0",
        "bytes_sent": 52428800,
        "bytes_received": 1048576,
        "connected_clients": 1,
        "signal_strength": -45
      }
    },
    "system": {
      "cpu": {
        "usage_percent": 25.3,
        "temperature_c": 52.1,
        "frequency_mhz": 1000,
        "load_average": [0.25, 0.30, 0.28]
      },
      "memory": {
        "usage_mb": 65,
        "total_mb": 512,
        "available_mb": 447,
        "usage_percent": 12.7
      },
      "disk": {
        "usage_percent": 45.2,
        "free_gb": 8.7
      }
    },
    "timestamp": "2025-08-21T10:30:00Z"
  }
}
```

### GET /logs
**システムログ取得**

最近のシステムログエントリを取得します。

**クエリパラメータ**:
- `lines`: ログ行数（デフォルト: 100、最大: 1000）
- `level`: ログレベルフィルタ（DEBUG、INFO、WARNING、ERROR、CRITICAL）
- `component`: コンポーネントフィルタ（bluetooth、wifi、audio、http、system）

**リクエスト例**:
```
GET /logs?lines=50&level=WARNING&component=bluetooth
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "timestamp": "2025-08-21T10:29:45Z",
        "level": "WARNING",
        "component": "bluetooth",
        "message": "[BLUETOOTH] Device AA:BB:CC:DD:EE:FF connection unstable"
      },
      {
        "timestamp": "2025-08-21T10:28:12Z", 
        "level": "INFO",
        "component": "audio",
        "message": "[AUDIO] Audio quality metrics updated: 128kbps, 180ms latency"
      }
    ],
    "total_lines": 2,
    "filtered": true
  }
}
```

---

## 🎛️ システム制御 API

### POST /control/bluetooth/scan
**Bluetoothデバイススキャン開始**

近くのBluetoothデバイスをスキャンします。

**リクエスト**:
```json
{
  "duration": 30
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "scan_started": true,
    "duration_seconds": 30,
    "scan_id": "scan_1692614400"
  }
}
```

### GET /control/bluetooth/devices
**検出されたBluetoothデバイス一覧**

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "devices": [
      {
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "name": "Galaxy S21",
        "device_type": "smartphone",
        "rssi": -45,
        "paired": true,
        "trusted": false,
        "last_seen": "2025-08-21T10:25:30Z"
      }
    ]
  }
}
```

### POST /control/bluetooth/connect
**特定デバイスへのBluetooth接続**

**リクエスト**:
```json
{
  "mac_address": "AA:BB:CC:DD:EE:FF"
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "connection_initiated": true,
    "device": {
      "mac_address": "AA:BB:CC:DD:EE:FF",
      "name": "Galaxy S21"
    }
  }
}
```

### POST /control/bluetooth/disconnect
**Bluetooth接続切断**

**リクエスト**:
```json
{
  "mac_address": "AA:BB:CC:DD:EE:FF"
}
```

### POST /control/audio/quality
**音質設定変更**

**リクエスト**:
```json
{
  "bitrate": 192,
  "quality_level": "high",
  "adaptive_quality": true
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "settings_applied": true,
    "current_settings": {
      "bitrate": 192,
      "quality_level": "high",
      "adaptive_quality": true
    }
  }
}
```

---

## 🔧 設定管理 API

### GET /config
**現在の設定取得**

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "system": {
      "name": "AudioBridge-Pi",
      "version": "1.0.0",
      "environment": "production"
    },
    "bluetooth": {
      "device_name": "AudioBridge-Pi",
      "discoverable_timeout": 0,
      "auto_connect": true
    },
    "wifi": {
      "ssid": "AudioBridge-Pi",
      "channel": 7,
      "max_clients": 5,
      "ip_address": "192.168.4.1"
    },
    "audio": {
      "sample_rate": 44100,
      "channels": 2,
      "default_bitrate": 128,
      "quality_level": "medium"
    },
    "http": {
      "host": "0.0.0.0",
      "port": 8080,
      "max_clients": 3
    }
  }
}
```

### POST /config
**設定更新**

**リクエスト**:
```json
{
  "bluetooth": {
    "device_name": "My-AudioBridge"
  },
  "wifi": {
    "ssid": "MyCarAudio",
    "password": "newpassword123"
  },
  "audio": {
    "default_bitrate": 192
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "updated": true,
    "restart_required": true,
    "affected_services": ["bluetooth", "wifi"]
  }
}
```

---

## 🔄 システム操作 API

### POST /control/system/restart
**システム再起動**

**リクエスト**:
```json
{
  "component": "all"  // または "bluetooth", "wifi", "audio", "http"
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "restart_initiated": true,
    "component": "all",
    "estimated_downtime_seconds": 30
  }
}
```

### POST /control/system/recovery
**自動復旧実行**

**リクエスト**:
```json
{
  "component": "bluetooth"  // 特定コンポーネントまたは "all"
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "recovery_started": true,
    "component": "bluetooth",
    "recovery_id": "recovery_1692614400"
  }
}
```

---

## 🐛 デバッグ・診断 API

### GET /debug
**包括的デバッグ情報**

システム診断用の詳細情報を提供します。

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "system_info": {
      "os_release": "Raspberry Pi OS Lite",
      "kernel": "6.1.0-rpi4-rpi-v8",
      "architecture": "aarch64",
      "python_version": "3.9.2"
    },
    "hardware": {
      "model": "Raspberry Pi Zero 2 W Rev 1.0",
      "cpu_cores": 4,
      "memory_total": 512,
      "temperature": 52.1
    },
    "services_status": {
      "systemd_services": {
        "bluetooth": "active",
        "hostapd": "active", 
        "dnsmasq": "active",
        "audio-bridge": "active"
      },
      "processes": {
        "bluetoothd": true,
        "hostapd": true,
        "dnsmasq": true,
        "pulseaudio": true
      }
    },
    "network": {
      "interfaces": {
        "wlan0": {
          "status": "UP",
          "ip": "192.168.4.1",
          "mac": "B8:27:EB:XX:XX:XX"
        }
      },
      "routing_table": [...],
      "iptables_rules": [...]
    },
    "audio": {
      "gstreamer_version": "1.18.4",
      "available_elements": ["pulsesrc", "lamemp3enc", "fdsink"],
      "pulseaudio_info": {
        "version": "14.2",
        "sources": ["bluez_sink.monitor"],
        "sinks": ["bluez_sink"]
      }
    },
    "bluetooth": {
      "bluez_version": "5.55",
      "hci_devices": ["hci0"],
      "paired_devices": [...]
    }
  }
}
```

### GET /debug/test-pipeline
**音声パイプライン テスト**

**クエリパラメータ**:
- `duration`: テスト継続時間（秒、デフォルト: 10）
- `frequency`: テストトーン周波数（Hz、デフォルト: 440）

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "test_started": true,
    "test_type": "audio_pipeline",
    "parameters": {
      "duration": 10,
      "frequency": 440
    },
    "expected_output": "Test tone should be audible via HTTP stream"
  }
}
```

---

## 📱 WebSocket API （将来拡張）

### WS /ws/events
**リアルタイムイベントストリーム**

システムイベントをリアルタイムで配信するWebSocketエンドポイントです。

**接続例**:
```javascript
const ws = new WebSocket('ws://192.168.4.1:8080/ws/events');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Event:', data.event_type, data.message);
};
```

**イベント形式**:
```json
{
  "event_type": "bluetooth_connected",
  "timestamp": "2025-08-21T10:30:00Z",
  "source_component": "bluetooth",
  "data": {
    "device": {
      "mac_address": "AA:BB:CC:DD:EE:FF",
      "name": "Galaxy S21"
    }
  },
  "message": "Device Galaxy S21 connected successfully"
}
```

---

## 🔐 認証・セキュリティ

### 認証方式
管理API（`/control/*`、`/config`）については、以下の認証方式をサポートします：

#### API Key認証
```bash
curl -H "X-API-Key: your-api-key" http://192.168.4.1:8080/control/system/status
```

#### Basic認証
```bash
curl -u "admin:password" http://192.168.4.1:8080/config
```

### セキュリティヘッダー
すべてのレスポンスに以下のセキュリティヘッダーが含まれます：

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## ⚠️ エラーコード一覧

### システムエラー
- `SYSTEM_INIT_ERROR`: システム初期化失敗
- `SERVICE_UNAVAILABLE`: サービス利用不可
- `RESOURCE_EXHAUSTED`: リソース不足

### Bluetooth エラー
- `BT_SERVICE_NOT_RUNNING`: Bluetoothサービス停止中
- `BT_DEVICE_NOT_FOUND`: 指定デバイスが見つからない
- `BT_CONNECTION_FAILED`: 接続失敗
- `BT_PAIRING_FAILED`: ペアリング失敗

### WiFi エラー
- `WIFI_AP_START_FAILED`: Access Point開始失敗
- `WIFI_INTERFACE_ERROR`: インターフェースエラー
- `DHCP_SERVER_ERROR`: DHCPサーバーエラー

### 音声エラー
- `AUDIO_PIPELINE_ERROR`: 音声パイプラインエラー
- `GSTREAMER_INIT_FAILED`: GStreamer初期化失敗
- `PULSEAUDIO_ERROR`: PulseAudioエラー
- `CODEC_NOT_SUPPORTED`: 非対応コーデック

### HTTP エラー
- `MAX_CLIENTS_REACHED`: 最大クライアント数到達
- `STREAM_ERROR`: ストリーミングエラー
- `INVALID_REQUEST`: 不正なリクエスト

---

## 📋 使用例・統合ガイド

### Fire TV Stick VLC統合
```
1. Fire TV StickでVLCアプリを起動
2. "ネットワークストリーム"を選択
3. URL: http://192.168.4.1:8080/audio.mp3 を入力
4. 再生開始
```

### 外部監視システム統合
```bash
#!/bin/bash
# ヘルスチェックスクリプト
HEALTH=$(curl -s http://192.168.4.1:8080/health | jq -r '.data.healthy')
if [ "$HEALTH" != "true" ]; then
    echo "AudioBridge-Pi health check failed"
    exit 1
fi
echo "AudioBridge-Pi is healthy"
```

### Home Assistant統合
```yaml
# configuration.yaml
sensor:
  - platform: rest
    resource: http://192.168.4.1:8080/status
    name: "AudioBridge Status"
    json_attributes_path: "$.data"
    json_attributes:
      - system
      - services
      - resources
    value_template: "{{ value_json.success }}"
```

---

**API設計確認事項**:
- ✅ RESTful API設計原則の遵守
- ✅ 音声ストリーミング・状態監視の両対応
- ✅ Fire TV Stick VLC完全対応
- ✅ 包括的なエラーハンドリング
- ✅ セキュリティ・認証機能
- ✅ 外部システム統合対応