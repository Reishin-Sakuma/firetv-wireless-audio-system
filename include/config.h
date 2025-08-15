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

// WiFi設定 (Phase 2)
#define WIFI_AP_SSID "ESP32-Audio-Bridge"
#define WIFI_AP_PASSWORD "audio2024"
#define WIFI_AP_CHANNEL 1
#define WIFI_AP_HIDDEN false
#define WIFI_AP_MAX_CONNECTION 4
#define WIFI_AP_IP_GATEWAY IPAddress(192,168,4,1)
#define WIFI_AP_IP_SUBNET IPAddress(255,255,255,0)

// HTTP Server設定
#define HTTP_SERVER_PORT 8080
#define HTTP_STREAM_PATH "/stream"

// バッファ設定（メモリ制限により縮小）
#define AUDIO_BUFFER_SIZE (16 * 1024)  // 16KB に縮小
#define BUFFER_COUNT 2                 // 2個に削減 = 計32KB
#define CHUNK_SIZE 1024                // 1KB チャンク

// デュアルコア設定
#define CORE_BLUETOOTH 1    // Bluetooth処理用コア
#define CORE_WIFI_HTTP 0    // WiFi + HTTP処理用コア

#endif