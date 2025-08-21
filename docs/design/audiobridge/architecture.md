# AudioBridge-Pi アーキテクチャ設計

## システム概要

AudioBridge-Pi は、Raspberry Pi Zero 2Wベースの組み込みLinuxシステムとして設計された、車載・家庭用ワイヤレス音楽ストリーミングブリッジです。Bluetooth A2DP経由で受信したAndroidデバイスからの音声を、WiFi Access Point経由でFire TV Stick等にHTTPストリーミング配信します。

**設計目標**:
- 車載環境での長期安定動作（30分〜24時間連続）
- 低遅延音声転送（200-400ms以内）
- 完全自動セットアップ・運用
- 堅牢な自動復旧機能

## アーキテクチャパターン

### 選択パターン: **レイヤードアーキテクチャ + パイプライン処理**

**理由**:
- **レイヤー分離**: Bluetooth・音声処理・ネットワーク・HTTP各層の独立性
- **パイプライン処理**: リアルタイム音声データフローの効率的処理
- **組み込みシステム適合性**: リソース制約下での最適な構造
- **保守性**: 各コンポーネントの独立したテスト・修正が可能

### アーキテクチャの層構造

```
┌─────────────────────────────────────┐
│ Presentation Layer (HTTP API)      │  ← Flask HTTPサーバー
├─────────────────────────────────────┤
│ Application Layer (統合制御)        │  ← main.py AudioBridge
├─────────────────────────────────────┤
│ Domain Layer (音声処理・機器制御)   │  ← 各種Manager
├─────────────────────────────────────┤
│ Infrastructure Layer (OS・HW)      │  ← Linux・systemd
└─────────────────────────────────────┘
```

## コンポーネント構成

### アプリケーション層 (Python)
- **フレームワーク**: Python 3.9+ with Flask
- **統合制御**: `main.py` - AudioBridge統合アプリケーション
- **状態管理**: 各Managerクラスでの分散状態管理
- **並行処理**: threading（ハートビート・監視・自動復旧）
- **設定管理**: `config.py` - 中央集権的設定

### ドメイン層 (コア機能)

#### Bluetooth管理
- **実装**: `bluetooth_manager.py` - BluetoothManager
- **技術**: BlueZ D-Bus API / python-dbus
- **責務**: A2DP Sink・ペアリング・接続管理・自動復旧

#### 音声処理パイプライン
- **実装**: `audio_pipeline.py` - AudioPipeline
- **技術**: GStreamer 1.0 / PulseAudio / pulsectl
- **責務**: 音声バッファリング・MP3エンコード・品質管理

#### WiFi Access Point
- **実装**: `wifi_manager.py` - WiFiManager  
- **技術**: hostapd / dnsmasq / netifaces
- **責務**: AP構築・DHCP・クライアント管理・ファイアウォール

#### HTTP音声配信
- **実装**: `http_server.py` - HTTPStreamingServer
- **技術**: Flask / Werkzeug
- **責務**: リアルタイムMP3配信・クライアント管理・状態API

### インフラ層 (システム・ハードウェア)

#### OS・システムサービス
- **OS**: Raspberry Pi OS Lite (Debian-based)
- **サービス管理**: systemd
- **プロセス管理**: systemctl / journald
- **自動起動**: multi-user.target統合

#### ハードウェア抽象化
- **Bluetooth**: Raspberry Pi内蔵Bluetoothアダプター
- **WiFi**: Raspberry Pi内蔵WiFiアダプター (wlan0)
- **音声処理**: CPUソフトウェア処理（専用DSPなし）

## 技術スタック詳細

### フロントエンド（クライアント側）
- **Android**: 標準Bluetooth A2DPクライアント
- **Fire TV**: VLCアプリ (HTTP音声ストリーミング受信)
- **管理UI**: HTTP API経由での状態監視（将来拡張）

### バックエンド（Raspberry Pi）
- **言語**: Python 3.9+
- **Webフレームワーク**: Flask 2.0+
- **非同期処理**: threading (GIL制約内での並行処理)
- **音声処理**: GStreamer 1.0 + PulseAudio
- **Bluetooth**: BlueZ 5.0+ / python-dbus
- **ネットワーク**: hostapd + dnsmasq + iptables

### データ・設定管理
- **設定ファイル**: INI形式 (hostapd/dnsmasq) + Python config
- **ログ管理**: Python logging + systemd journal
- **状態管理**: メモリ内状態 + ファイル永続化
- **監視**: 内蔵ヘルスチェック + systemd watchdog

## システム境界・外部インターフェース

### 外部システム接続点

#### 入力側 (Android → Raspberry Pi)
```
Android Bluetooth Stack → BlueZ A2DP Sink → PulseAudio Monitor → GStreamer
```

#### 出力側 (Raspberry Pi → Fire TV)
```
GStreamer MP3 Encoder → Flask HTTP Server → WiFi AP → Fire TV VLC
```

#### 管理・監視
```
systemd → AudioBridge Application → HTTP Status API → 外部監視システム
```

### プロトコル・インターフェース詳細

#### Bluetooth A2DP
- **プロトコル**: Advanced Audio Distribution Profile (A2DP)
- **コーデック**: SBC (Sub Band Coding) - 標準必須
- **ビットプール**: 53 (最高音質)
- **サンプリングレート**: 44.1kHz ステレオ

#### WiFi 802.11n
- **モード**: Access Point (hostapd)
- **暗号化**: WPA2-PSK (CCMP)
- **チャンネル**: 2.4GHz帯 (ch1-13選択可能)
- **DHCP**: 192.168.4.1/24 サブネット

#### HTTP音声ストリーミング
- **プロトコル**: HTTP/1.1 Chunked Transfer
- **音声形式**: MPEG-1 Audio Layer III (MP3)
- **ビットレート**: 128-320kbps 可変
- **MIME Type**: `audio/mpeg`

## パフォーマンス設計

### レイテンシ最適化
- **目標遅延**: 200-400ms エンドツーエンド
- **バッファ戦略**: 適応的サイズ調整 (1024-4096バイト)
- **処理優先度**: リアルタイム音声処理の最優先化

### リソース制約対応 (512MB RAM)
- **メモリ使用量**: 50-80MB (通常動作時)
- **CPU使用率**: 15-25% (音声処理時)
- **循環バッファ**: オーバーフロー時の古いデータ自動破棄

### 並行処理設計
- **メインスレッド**: HTTP サーバー・音声パイプライン
- **監視スレッド**: ハートビート (60秒間隔)
- **復旧スレッド**: 健全性チェック (30秒間隔)
- **再接続スレッド**: Bluetooth自動再接続 (30秒間隔)

## 可用性・復旧設計

### 自動復旧戦略
```
障害検知 → 診断実行 → 復旧試行 → 状態確認 → ログ記録
```

#### 障害パターン別復旧
- **Bluetooth切断**: 30秒間隔での自動再接続試行
- **音声パイプライン停止**: GStreamer再起動・代替パイプライン
- **WiFi AP停止**: hostapd/dnsmasq サービス再起動
- **HTTP サーバー停止**: プロセス再起動・フォールバック応答

#### システムレベル復旧
- **プロセス異常終了**: systemd自動再起動 (RestartSec=30)
- **電源断復旧**: OS起動時の全サービス自動開始
- **設定破損**: デフォルト設定での緊急起動

### 監視・診断機能
- **ハートビート**: 60秒間隔でのシステム生存確認
- **健全性チェック**: 各コンポーネントの定期診断
- **メトリクス収集**: CPU・メモリ・音声品質・接続状態
- **ログ管理**: 構造化ログによる問題追跡

## セキュリティ設計

### ネットワークセキュリティ
- **WiFi暗号化**: WPA2-PSK (パスフレーズ必須)
- **ファイアウォール**: iptables (HTTP 8080ポートのみ開放)
- **ネットワーク分離**: 専用VLAN (192.168.4.0/24)

### システムセキュリティ
- **最小権限実行**: 非rootユーザーでのアプリケーション実行
- **権限分離**: audioグループ権限のみ付与
- **設定ファイル保護**: 適切なファイル権限設定

### 運用セキュリティ
- **パスワード管理**: WiFiパスフレーズの適切な強度
- **アップデート**: セキュリティパッチの定期適用
- **ログ保護**: 機密情報のログ出力回避

## 拡張性・保守性設計

### モジュラー設計
- **疎結合**: 各Managerクラスの独立性
- **インターフェース統一**: 共通の初期化・クリーンアップパターン
- **設定外部化**: config.pyによる中央設定管理

### テスト設計
- **単体テスト**: 各Managerクラスの独立テスト
- **統合テスト**: コンポーネント間連携テスト
- **システムテスト**: エンドツーエンド動作確認

### 運用設計
- **設定管理**: バージョン管理対応の設定ファイル
- **ログ戦略**: レベル別・構造化ログ出力
- **監視統合**: systemd・外部監視システム連携

## デプロイメント設計

### 自動セットアップ
- **ワンコマンドインストール**: `sudo ./scripts/setup.sh`
- **依存関係解決**: システムパッケージ + Python仮想環境
- **設定自動生成**: テンプレートベース設定ファイル生成

### サービス統合
- **systemd統合**: マルチユーザーターゲットでの自動起動
- **依存関係管理**: network-online.target・bluetooth.service
- **プロセス管理**: 適切なタイムアウト・再起動設定

### バージョン管理
- **設定バックアップ**: アップグレード時の設定保護
- **ロールバック**: 問題発生時の前バージョン復旧
- **互換性管理**: 設定形式・API仕様の後方互換性

---

**アーキテクチャ設計承認事項**:
- ✅ レイヤードアーキテクチャによる構造化
- ✅ パイプライン処理による低遅延実現  
- ✅ 組み込みLinuxシステムとしての最適化
- ✅ 完全自動運用・復旧機能
- ✅ 車載・家庭環境両対応の堅牢性