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