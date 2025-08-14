# ESP32 Bluetooth-WiFi オーディオブリッジ

ESP32を使用してBluetooth A2DPで受信した音声をWiFi経由でFire TV Stickにストリーミングするプロジェクトです。

## Phase 1: Bluetooth A2DP Sink 実装

現在はPhase 1として、AndroidデバイスからBluetooth A2DPで音声を受信する基本機能を実装しています。

## ハードウェア要件

- **ESP32 Dev Module** (esp32dev)
- **メモリ**: 520KB SRAM
- **USB-Cケーブル** (ESP32書き込み・電源用)

## セットアップ手順

### 1. PlatformIOのインストール

```bash
# VS Codeの場合
# PlatformIO IDE拡張機能をインストール

# コマンドラインの場合
pip install platformio
```

### 2. プロジェクトのビルド

```bash
# 依存関係インストール & ビルド
pio run

# ESP32への書き込み
pio run --target upload

# シリアル監視
pio device monitor
```

## Android接続方法

### 初回接続（手動ペアリング）

1. ESP32を起動
2. Androidの**設定** → **Bluetooth**を開く
3. **ESP32-AudioBridge**を検索
4. ペアリングを実行（PINコード: 0000）

### 2回目以降（自動接続）

1. ESP32を起動
2. 自動的にAndroidデバイスを検索（30秒間）
3. 自動接続が失敗した場合は手動で接続

### 音声再生テスト

1. Spotify、YouTube Music等の音楽アプリを開く
2. 音声出力デバイスとして**ESP32-AudioBridge**を選択
3. 音楽を再生開始
4. シリアル監視でデータ受信ログを確認

## シリアル出力例

```
========================================
ESP32 Bluetooth-WiFi Audio Bridge
Phase 1: Bluetooth A2DP Sink
========================================
[SYSTEM] Free heap at startup: 298472 bytes
[BLUETOOTH] Initializing A2DP Sink...
[BLUETOOTH] Device discoverable: ESP32-AudioBridge
[BLUETOOTH] Waiting for connection...
[BLUETOOTH] Device connected: Galaxy S21 (Android Device)
[AUDIO] Data received: 1024 bytes, Total: 40960 bytes, Rate: 320000 bps
[AUDIO] Sample rate: 44100Hz, Channels: 2
[SYSTEM] Free heap: 234567 bytes
```

## トラブルシューティング

### Bluetooth接続できない

- ESP32を再起動してください
- Android側でBluetooth設定をリセット
- ペアリング済みデバイスから削除後、再ペアリング

### コンパイルエラー

```bash
# クリーンビルド
pio run --target clean
pio run
```

### シリアル監視が表示されない

- USBケーブルを確認
- ポート設定確認: `pio device monitor --port COM3` (Windowsの場合)

### 音声データが受信されない

- Android側で音声出力デバイスを確認
- Spotify等のアプリで音楽が再生されているか確認
- ESP32のヒープメモリ不足の可能性（再起動で解決）

## 設定変更

`include/config.h`で以下の設定を変更できます：

```cpp
#define BT_DEVICE_NAME "ESP32-AudioBridge"  // Bluetoothデバイス名
#define BT_PIN_CODE "0000"                  // ペアリングPINコード
#define SERIAL_BAUD 115200                  // シリアル通信速度
```

## Phase 2 以降の予定

- **WiFi AP機能**: ESP32をアクセスポイントとして動作
- **HTTP音声ストリーミング**: 受信した音声をHTTPでストリーミング配信
- **Fire TV Stick対応**: VLCアプリでHTTPストリームを再生
- **音質最適化**: 320kbps対応、遅延最小化

## 成功判定基準

- [ ] ESP32がAndroidから検出される
- [ ] ペアリングが正常完了する
- [ ] A2DP接続が確立される
- [ ] Spotify音声データが受信される（ログ確認）
- [ ] 接続切断が正常処理される
- [ ] 30分間の安定動作

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。