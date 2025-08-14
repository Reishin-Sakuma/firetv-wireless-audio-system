# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# ESP32 Bluetooth-WiFi オーディオブリッジ開発プロジェクト

## 🎯 プロジェクト目標

**車載環境で Android（Spotify）→ ESP32 → Fire TV Stick の音楽ストリーミング環境を構築**

```
Android (Spotify) → [Bluetooth A2DP] → ESP32 → [WiFi AP + HTTP Stream] → Fire TV Stick (VLC)
```

## 📋 技術仕様

### ハードウェア
- **ESP32**: ESP32 Dev Module (esp32dev)
- **メモリ**: 520KB SRAM (PSRAM拡張なし)
- **音質**: Spotify最高音質 320kbps = 40KB/秒
- **バッファ**: 160KB (4秒分の音声バッファ確保可能)

### ソフトウェアアーキテクチャ
- **Core 0**: WiFi AP + HTTPストリーミングサーバー専用
- **Core 1**: Bluetooth A2DP Sink + メイン制御
- **フレームワーク**: Arduino for ESP32
- **開発環境**: PlatformIO

## 🚀 Phase 1 実装要求

**今回の目標: Bluetooth A2DP Sinkの基本動作確認**

### 必須実装機能
1. **PlatformIOプロジェクト作成**
   - プロジェクト名: `esp32-audio-bridge`
   - ESP32 Dev Module対応
   - 必要ライブラリの自動インストール設定

2. **Bluetooth A2DP Sink実装**
   - Androidデバイス検出・ペアリング
   - A2DP接続確立（初回手動、2回目以降自動接続対応）
   - 音声データ受信（ログ出力で確認）
   - 接続状態監視
   - **自動再接続機能**（接続切断時の復旧処理）

3. **基本デバッグ機能**
   - シリアル監視出力
   - 接続ステータス表示
   - 受信データ量表示
   - エラー処理

### ファイル構成要求
```
esp32-audio-bridge/
├── platformio.ini          # ESP32設定・ライブラリ依存関係
├── src/
│   ├── main.cpp            # メインループ・初期化
│   ├── bluetooth_a2dp.cpp  # A2DP Sink実装
│   ├── bluetooth_a2dp.h    # A2DPヘッダー
│   └── config.h            # 設定定数
├── include/
└── README.md               # セットアップ・使用方法
```

### platformio.ini 仕様
```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
lib_deps = 
    ESP32-A2DP
build_flags = 
    -DCORE_DEBUG_LEVEL=4
    -DCONFIG_BT_ENABLED=1
    -DCONFIG_BLUEDROID_ENABLED=1
```

### 実装技術要求

#### Bluetooth A2DP実装
```cpp
// 必須機能
- esp_a2dp_sink_init() による初期化
- デバイス検出可能モード設定（常時接続可能）
- ペアリング要求処理
- A2DP接続コールバック実装
- 音声データ受信コールバック実装
- 接続切断処理
- 自動再接続ロジック（定期的な接続試行）
- ペアリング済みデバイス記憶機能
```

#### 接続方式
```cpp
// 初回接続（手動ペアリング必要）
1. ESP32起動 → 検出可能モード
2. Android: 設定 → Bluetooth → ESP32-AudioBridge検索
3. ペアリング実行・登録

// 2回目以降（自動接続期待、保証なし）
1. ESP32起動 → 既知デバイス自動検索
2. Android側からの接続待機（10-30秒）
3. 自動接続失敗時 → 手動接続ガイド表示
```

#### デバッグ出力例
```
[BLUETOOTH] Initializing A2DP Sink...
[BLUETOOTH] Device discoverable: ESP32-AudioBridge
[BLUETOOTH] Waiting for connection...
[BLUETOOTH] Device connected: XX:XX:XX:XX:XX:XX (Device Name)
[AUDIO] Data received: 1024 bytes
[AUDIO] Sample rate: 44100Hz, Channels: 2
[SYSTEM] Free heap: 234KB
```

## 🔧 開発環境・コマンド

### PlatformIOコマンド（よく使用）

```bash
# プロジェクト初期化
pio project init --board esp32dev

# ビルド
pio run

# ESP32への書き込み
pio run --target upload

# シリアル監視
pio device monitor

# クリーンビルド
pio run --target clean

# 依存関係更新
pio pkg update
```

## 🧪 テスト・検証要求

### 基本動作テスト
1. **コンパイル確認**
   ```bash
   pio run
   ```

2. **ESP32書き込み**
   ```bash
   pio run --target upload
   ```

3. **シリアル監視**
   ```bash
   pio device monitor
   ```

4. **Bluetooth接続テスト**
   - **初回**: Android設定 → Bluetooth → ESP32-AudioBridge検索・ペアリング
   - **2回目**: ESP32再起動 → 自動接続確認（30秒待機）
   - **手動接続**: 自動失敗時のAndroid操作確認
   - Spotify再生開始
   - シリアル出力で音声データ受信確認
   - **接続切断・再接続テスト**

### 成功判定基準
- [ ] ESP32がAndroidから検出される
- [ ] ペアリングが正常完了する
- [ ] A2DP接続が確立される
- [ ] Spotify音声データが受信される（ログ確認）
- [ ] 接続切断が正常処理される
- [ ] 30分間の安定動作

## ⚙️ 設定・定数仕様

### config.h 内容
```cpp
#ifndef CONFIG_H
#define CONFIG_H

// Bluetooth設定
#define BT_DEVICE_NAME "ESP32-AudioBridge"
#define BT_PIN_CODE "0000"

// 音声設定  
#define SAMPLE_RATE 44100
#define CHANNELS 2
#define BITS_PER_SAMPLE 16

// デバッグ設定
#define DEBUG_LEVEL 4
#define SERIAL_BAUD 115200

// バッファ設定（Phase 2用準備）
#define AUDIO_BUFFER_SIZE (40 * 1024)  // 40KB = 1秒分
#define BUFFER_COUNT 4

#endif
```

## 📝 ドキュメント要求

### README.md 必須項目
1. **ハードウェア要求**
2. **セットアップ手順**
3. **Android接続方法**
4. **トラブルシューティング**
5. **Phase 2 以降の予定**

### コード内コメント要求
- 各関数の役割説明
- 重要な処理ブロックの説明
- TODO: Phase 2で実装予定の箇所
- 潜在的な問題点の注記

## 🔧 エラーハンドリング要求

### 必須エラー処理
1. **Bluetooth初期化失敗**
2. **ペアリング失敗**
3. **A2DP接続失敗**
4. **自動接続タイムアウト**（30秒以内に接続されない）
5. **音声データ受信エラー**
6. **メモリ不足**
7. **接続切断の検出・自動復旧**

### ログレベル
- ERROR: 致命的エラー
- WARN: 警告・復旧可能エラー
- INFO: 接続状態変化
- DEBUG: 詳細デバッグ情報

## 🎯 開発指示

**Claude Code での実行手順:**

1. **プロジェクト作成**
   ```bash
   mkdir esp32-audio-bridge && cd esp32-audio-bridge
   pio project init --board esp32dev
   ```

2. **ファイル作成・実装**
   - platformio.ini 設定
   - src/main.cpp メインロジック
   - src/bluetooth_a2dp.cpp A2DP実装
   - include/config.h 設定定義
   - README.md ドキュメント

3. **ビルド・テスト**
   ```bash
   pio run
   pio run --target upload
   pio device monitor
   ```

4. **Androidテスト**
   - Bluetooth接続確認
   - Spotify再生テスト
   - ログ出力確認

**開発完了条件:**
- すべてのファイルが作成されている
- コンパイルエラーが0個
- Android接続テストが成功
- 音声データ受信ログが確認できる
- README.mdが完成している

**Phase 1完了後の次ステップ:**
Phase 2でWiFi AP + HTTPストリーミング実装に進む予定

---

**⚡ 今すぐ開始してください！ ⚡**

このプロンプトに基づき、ESP32 Bluetooth-WiFi オーディオブリッジのPhase 1を完全実装してください。まずはBluetooth A2DP Sinkの基本動作を確実に動作させることが目標です。