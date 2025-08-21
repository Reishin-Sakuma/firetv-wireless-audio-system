# AudioBridge-Pi データフロー図

## システム全体データフロー概要

AudioBridge-Pi は、Bluetooth A2DP → 音声処理 → WiFi HTTP配信の一方向データフローを基本とする、リアルタイム音声ストリーミングシステムです。

## 1. 高レベルシステムフロー

### 音声データフロー全体像
```mermaid
flowchart TD
    subgraph Android["Android デバイス"]
        A1[Spotify/音楽アプリ]
        A2[Bluetooth A2DP Stack]
    end
    
    subgraph RaspberryPi["Raspberry Pi Zero 2W"]
        subgraph BluetoothLayer["Bluetooth 層"]
            B1[BlueZ A2DP Sink]
            B2[BluetoothManager]
        end
        
        subgraph AudioLayer["音声処理層"]
            C1[PulseAudio Monitor]
            C2[AudioPipeline]
            C3[GStreamer Pipeline]
            C4[MP3 Encoder]
        end
        
        subgraph NetworkLayer["ネットワーク層"]
            D1[WiFi Access Point]
            D2[WiFiManager]
        end
        
        subgraph ApplicationLayer["アプリケーション層"]
            E1[HTTPStreamingServer]
            E2[Flask Web Server]
            E3[AudioBridge Main]
        end
    end
    
    subgraph FireTV["Fire TV Stick"]
        F1[VLC Media Player]
        F2[WiFi Client]
    end
    
    A1 --> A2
    A2 -.Bluetooth A2DP.-> B1
    B1 --> C1
    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> E1
    E1 --> E2
    E2 -.HTTP Stream.-> F2
    F2 --> F1
    
    B2 -.管理.-> B1
    D2 -.管理.-> D1
    E3 -.統合制御.-> B2
    E3 -.統合制御.-> C2
    E3 -.統合制御.-> D2
    E3 -.統合制御.-> E1
```

### システム状態遷移フロー
```mermaid
stateDiagram-v2
    [*] --> 初期化中
    初期化中 --> Bluetooth待機: Bluetooth初期化成功
    初期化中 --> エラー状態: 初期化失敗
    
    Bluetooth待機 --> ペアリング中: Android接続要求
    ペアリング中 --> A2DP接続中: ペアリング成功
    ペアリング中 --> Bluetooth待機: ペアリング失敗
    
    A2DP接続中 --> 音声受信中: 音声データ受信開始
    音声受信中 --> 音声配信中: HTTPクライアント接続
    音声配信中 --> 音声受信中: HTTPクライアント切断
    音声受信中 --> A2DP接続中: 音声データ停止
    A2DP接続中 --> Bluetooth待機: A2DP切断
    
    音声配信中 --> 復旧中: 障害検知
    復旧中 --> 音声配信中: 復旧成功
    復旧中 --> エラー状態: 復旧失敗
    
    エラー状態 --> 初期化中: 再起動・再初期化
```

## 2. 音声データパイプライン詳細

### リアルタイム音声処理フロー
```mermaid
flowchart LR
    subgraph Input["音声入力"]
        I1[Android Audio Output]
        I2[Bluetooth A2DP Transport]
        I3[SBC Decode]
    end
    
    subgraph BlueZStack["BlueZ処理"]
        B1[A2DP Sink Profile]
        B2[Audio Routing]
        B3[PulseAudio Bridge]
    end
    
    subgraph PulseAudio["PulseAudio層"]
        P1[bluez_sink Device]
        P2[Monitor Source]
        P3[Audio Buffer]
    end
    
    subgraph GStreamer["GStreamer パイプライン"]
        G1[pulsesrc Element]
        G2[audioconvert]
        G3[audioresample]
        G4[lamemp3enc]
        G5[fdsink]
    end
    
    subgraph Output["HTTP出力"]
        O1[Flask Response]
        O2[Chunked Transfer]
        O3[Fire TV VLC]
    end
    
    I1 --> I2 --> I3 --> B1
    B1 --> B2 --> B3 --> P1
    P1 --> P2 --> P3 --> G1
    G1 --> G2 --> G3 --> G4 --> G5
    G5 --> O1 --> O2 --> O3
```

### バッファリング戦略
```mermaid
sequenceDiagram
    participant Android
    participant BlueZ as BlueZ Stack
    participant PA as PulseAudio
    participant Buffer as AudioBuffer
    participant GStreamer
    participant HTTP as HTTP Client
    
    Android->>BlueZ: A2DP Audio Packets
    BlueZ->>PA: PCM Audio Samples
    PA->>Buffer: Buffered Audio (4096 bytes)
    
    loop Real-time Processing
        Buffer->>GStreamer: Audio Chunk (1024 bytes)
        GStreamer->>GStreamer: MP3 Encode
        GStreamer->>HTTP: MP3 Frame
        HTTP-->>GStreamer: Backpressure (if slow)
    end
    
    Note over Buffer: Overflow Protection
    Buffer->>Buffer: Drop Old Data if Full
    
    Note over GStreamer: Quality Adaptation  
    GStreamer->>GStreamer: Bitrate Adjustment
```

## 3. ネットワーク通信フロー

### WiFi Access Point セットアップフロー
```mermaid
sequenceDiagram
    participant System as System Boot
    participant WiFiMgr as WiFiManager
    participant hostapd
    participant dnsmasq
    participant iptables
    participant FireTV as Fire TV
    
    System->>WiFiMgr: initialize()
    WiFiMgr->>hostapd: Configure AP (AudioBridge-Pi)
    WiFiMgr->>dnsmasq: Configure DHCP (192.168.4.1/24)
    WiFiMgr->>iptables: Configure Firewall
    
    hostapd-->>WiFiMgr: AP Started
    dnsmasq-->>WiFiMgr: DHCP Started
    
    FireTV->>hostapd: WiFi Association Request
    hostapd-->>FireTV: Authentication Success
    FireTV->>dnsmasq: DHCP Request
    dnsmasq-->>FireTV: IP Assignment (192.168.4.x)
    
    WiFiMgr->>WiFiMgr: Monitor Client Connection
```

### HTTP音声ストリーミングフロー
```mermaid
sequenceDiagram
    participant FireTV as Fire TV VLC
    participant Flask as Flask Server
    participant GStreamer
    participant AudioPipeline as Audio Pipeline
    
    FireTV->>Flask: GET /audio.mp3
    Flask->>Flask: Create Streaming Response
    Flask->>GStreamer: Start Audio Pipeline
    GStreamer->>AudioPipeline: Request Audio Data
    
    loop Streaming Loop
        AudioPipeline-->>GStreamer: Audio Chunk
        GStreamer->>GStreamer: MP3 Encode
        GStreamer-->>Flask: MP3 Frame
        Flask-->>FireTV: HTTP Chunk
        FireTV->>FireTV: Buffer & Play
    end
    
    alt Connection Lost
        FireTV-xFlask: Connection Closed
        Flask->>GStreamer: Stop Pipeline
        Flask->>Flask: Cleanup Client
    end
```

## 4. システム管理・監視フロー

### 統合システム制御フロー
```mermaid
flowchart TD
    subgraph MainApp["AudioBridge メインアプリケーション"]
        M1[System Initialize]
        M2[Component Manager]
        M3[Health Monitor]
        M4[Recovery Controller]
    end
    
    subgraph Components["システムコンポーネント"]
        C1[BluetoothManager]
        C2[WiFiManager] 
        C3[AudioPipeline]
        C4[HTTPServer]
    end
    
    subgraph Monitoring["監視・復旧"]
        Mo1[Heartbeat Thread]
        Mo2[Status Monitor Thread]
        Mo3[Auto Recovery Thread]
    end
    
    subgraph External["外部システム"]
        E1[systemd Service]
        E2[System Logs]
        E3[Performance Metrics]
    end
    
    M1 --> M2
    M2 --> C1 & C2 & C3 & C4
    M2 --> M3
    M3 --> Mo1 & Mo2 & Mo3
    Mo2 --> M4
    M4 --> C1 & C2 & C3 & C4
    
    Mo1 --> E2
    Mo2 --> E3
    M2 --> E1
    E1 --> M1
```

### 障害検知・復旧フロー
```mermaid
flowchart TD
    A[Health Check] --> B{Component Status}
    
    B -->|Bluetooth OK| C1[Continue]
    B -->|Bluetooth Failed| D1[Bluetooth Recovery]
    
    B -->|Audio OK| C2[Continue]
    B -->|Audio Failed| D2[Audio Recovery]
    
    B -->|WiFi OK| C3[Continue]
    B -->|WiFi Failed| D3[WiFi Recovery]
    
    B -->|HTTP OK| C4[Continue]
    B -->|HTTP Failed| D4[HTTP Recovery]
    
    D1 --> E1{Recovery Success?}
    D2 --> E2{Recovery Success?}
    D3 --> E3{Recovery Success?}
    D4 --> E4{Recovery Success?}
    
    E1 -->|Yes| F1[Log Success]
    E1 -->|No| G1[Escalate Error]
    
    E2 -->|Yes| F2[Log Success]
    E2 -->|No| G2[Escalate Error]
    
    E3 -->|Yes| F3[Log Success]
    E3 -->|No| G3[Escalate Error]
    
    E4 -->|Yes| F4[Log Success]
    E4 -->|No| G4[Escalate Error]
    
    G1 & G2 & G3 & G4 --> H[System Restart]
    F1 & F2 & F3 & F4 --> I[Wait Next Check]
    H --> A
    I --> A
```

## 5. 起動・初期化シーケンス

### システム起動フロー
```mermaid
sequenceDiagram
    participant systemd
    participant MainApp as AudioBridge Main
    participant AudioMgr as AudioPipeline
    participant WiFiMgr as WiFiManager
    participant BTMgr as BluetoothManager
    participant HTTPSrv as HTTPServer
    
    systemd->>MainApp: Start Service
    MainApp->>MainApp: Setup Logging
    MainApp->>MainApp: Load Configuration
    
    MainApp->>AudioMgr: initialize()
    AudioMgr->>AudioMgr: Check PulseAudio
    AudioMgr->>AudioMgr: Setup GStreamer
    AudioMgr-->>MainApp: Success/Failure
    
    MainApp->>WiFiMgr: initialize()
    WiFiMgr->>WiFiMgr: Configure wlan0
    WiFiMgr->>WiFiMgr: Start hostapd/dnsmasq
    WiFiMgr-->>MainApp: Success/Failure
    
    MainApp->>HTTPSrv: initialize()
    HTTPSrv->>HTTPSrv: Setup Flask App
    HTTPSrv->>HTTPSrv: Bind Port 8080
    HTTPSrv-->>MainApp: Success/Failure
    
    MainApp->>BTMgr: initialize()
    BTMgr->>BTMgr: Configure BlueZ
    BTMgr->>BTMgr: Enable Discoverable
    BTMgr-->>MainApp: Success/Failure
    
    MainApp->>MainApp: Start Background Threads
    MainApp->>systemd: Ready Signal
```

### 接続確立フロー
```mermaid
sequenceDiagram
    participant Android
    participant BTMgr as BluetoothManager
    participant AudioPipe as AudioPipeline
    participant HTTPSrv as HTTPServer
    participant FireTV
    
    Android->>BTMgr: Bluetooth Scan
    BTMgr-->>Android: AudioBridge-Pi Found
    Android->>BTMgr: Pairing Request
    BTMgr->>BTMgr: Auto Accept Pairing
    BTMgr-->>Android: Pairing Success
    
    Android->>BTMgr: A2DP Connection
    BTMgr->>AudioPipe: Start Audio Flow
    AudioPipe->>AudioPipe: Enable Audio Processing
    
    FireTV->>HTTPSrv: WiFi Connection
    HTTPSrv-->>FireTV: IP Assignment
    FireTV->>HTTPSrv: GET /audio.mp3
    HTTPSrv->>AudioPipe: Request Audio Stream
    AudioPipe-->>HTTPSrv: MP3 Stream
    HTTPSrv-->>FireTV: HTTP Audio Stream
```

## 6. エラーハンドリング・フォールバックフロー

### 音声パイプライン障害対応
```mermaid
flowchart TD
    A[Audio Pipeline Start] --> B{GStreamer Available?}
    
    B -->|Yes| C[Try Primary Pipeline]
    B -->|No| X[Log Error & Exit]
    
    C --> D{Pipeline Success?}
    D -->|Yes| E[Normal Operation]
    D -->|No| F[Try Secondary Pipeline]
    
    F --> G{Secondary Success?}
    G -->|Yes| E
    G -->|No| H[Try Fallback Pipeline]
    
    H --> I{Fallback Success?}
    I -->|Yes| J[Degraded Operation]
    I -->|No| K[Generate Static MP3]
    
    E --> L[Monitor Quality]
    J --> L
    K --> M[Silent Stream Mode]
    
    L --> N{Quality OK?}
    N -->|Yes| L
    N -->|No| O[Adjust Bitrate]
    O --> L
    
    M --> P[Wait for Recovery]
    P --> A
```

### ネットワーク障害復旧フロー
```mermaid
flowchart TD
    A[Network Health Check] --> B{WiFi AP Status}
    
    B -->|Running| C{DHCP Status}
    B -->|Failed| D[Restart hostapd]
    
    C -->|Running| E{Client Count}
    C -->|Failed| F[Restart dnsmasq]
    
    E -->|Normal| G[Continue Monitoring]
    E -->|Zero for 5min| H[Check Interface]
    
    D --> I{Restart Success?}
    F --> I
    H --> I
    
    I -->|Yes| J[Service Restored]
    I -->|No| K[Interface Reset]
    
    K --> L{Reset Success?}
    L -->|Yes| J
    L -->|No| M[System Recovery]
    
    J --> N[Update Status]
    M --> N
    
    N --> O[Wait Next Check]
    O --> A
```

## 7. パフォーマンス・品質監視フロー

### 音声品質監視
```mermaid
sequenceDiagram
    participant Monitor as Quality Monitor
    participant Pipeline as Audio Pipeline
    participant Metrics as Performance Metrics
    participant Controller as Adaptive Controller
    
    loop Every 10 seconds
        Monitor->>Pipeline: Get Audio Metrics
        Pipeline-->>Monitor: Latency, Bitrate, Buffer Level
        
        Monitor->>Metrics: Store Metrics
        Monitor->>Monitor: Analyze Trends
        
        alt High Latency Detected
            Monitor->>Controller: Trigger Latency Reduction
            Controller->>Pipeline: Reduce Buffer Size
            Controller->>Pipeline: Lower Bitrate
        else Buffer Underrun
            Monitor->>Controller: Trigger Quality Recovery
            Controller->>Pipeline: Increase Buffer Size
            Controller->>Pipeline: Stable Bitrate
        end
    end
```

### システムリソース監視
```mermaid
flowchart LR
    subgraph Monitoring["システム監視"]
        M1[CPU Monitor]
        M2[Memory Monitor]
        M3[Temperature Monitor]
        M4[Network Monitor]
    end
    
    subgraph Metrics["メトリクス収集"]
        ME1[CPU Usage %]
        ME2[Memory Usage MB]
        ME3[CPU Temperature °C]
        ME4[Network Throughput]
    end
    
    subgraph Actions["適応制御"]
        A1[Quality Adjustment]
        A2[Buffer Optimization]
        A3[Thermal Throttling]
        A4[Connection Management]
    end
    
    M1 --> ME1 --> A1
    M2 --> ME2 --> A2
    M3 --> ME3 --> A3
    M4 --> ME4 --> A4
    
    A1 & A2 & A3 & A4 --> L[Log Actions]
```

---

**データフロー設計確認事項**:
- ✅ リアルタイム音声処理の低遅延パイプライン
- ✅ 堅牢な障害検知・自動復旧機構
- ✅ 適応的品質制御による安定配信
- ✅ システムリソース制約下での最適化
- ✅ エンドツーエンドでの統合データフロー