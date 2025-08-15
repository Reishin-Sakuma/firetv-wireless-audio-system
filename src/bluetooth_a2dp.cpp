#include "bluetooth_a2dp.h"
#include "BluetoothA2DPSink.h"
#include "esp_a2dp_api.h"
#include "audio_buffer.h"
#include <Arduino.h>
#include <ESP.h>
#include "esp_task_wdt.h"

BluetoothA2DPSink a2dp_sink;
BluetoothA2DP* instancePtr = nullptr;

BluetoothA2DP::BluetoothA2DP() : initialized(false), connected(false), lastConnectionAttempt(0) {
    instancePtr = this;
}

BluetoothA2DP::~BluetoothA2DP() {
    cleanup();
    instancePtr = nullptr;
}

bool BluetoothA2DP::init() {
    Serial.println("[BLUETOOTH] Initializing A2DP Sink...");
    
    // CPU負荷軽減: 音声コールバックを無効設定で初期化
    a2dp_sink.set_stream_reader(audioDataCallback, false);
    a2dp_sink.set_on_connection_state_changed(connectionStateCallback);
    
    // CPU分散のためdelay追加
    delay(100);
    esp_task_wdt_reset();
    
    a2dp_sink.start(BT_DEVICE_NAME);
    initialized = true;
    Serial.print("[BLUETOOTH] Device discoverable: ");
    Serial.println(BT_DEVICE_NAME);
    Serial.println("[BLUETOOTH] Waiting for connection...");
    
    // 初期化後のCPU負荷軽減
    delay(500);
    esp_task_wdt_reset();
    
    return true;
}

void BluetoothA2DP::cleanup() {
    if (initialized) {
        a2dp_sink.end();
        initialized = false;
        connected = false;
        Serial.println("[BLUETOOTH] A2DP sink cleaned up");
    }
}

bool BluetoothA2DP::isConnected() {
    return connected && a2dp_sink.is_connected();
}

void BluetoothA2DP::loop() {
    if (!initialized) return;
    
    // ウォッチドッグリセット
    esp_task_wdt_reset();
    
    static unsigned long lastStatusLog = 0;
    unsigned long currentTime = millis();
    
    if (currentTime - lastStatusLog > 10000) {
        logStatus();
        lastStatusLog = currentTime;
        esp_task_wdt_reset(); // ログ後にリセット
    }
    
    if (!isConnected() && (currentTime - lastConnectionAttempt > RECONNECT_INTERVAL)) {
        attemptReconnection();
        lastConnectionAttempt = currentTime;
        esp_task_wdt_reset(); // 再接続処理後にリセット
    }
    
    // CPU負荷軽減のためのyield
    yield();
}

void BluetoothA2DP::connectionStateCallback(esp_a2d_connection_state_t state, void* ptr) {
    if (instancePtr) {
        instancePtr->handleConnectionState(state);
    }
}

void BluetoothA2DP::audioDataCallback(const uint8_t* data, uint32_t len) {
    if (instancePtr) {
        instancePtr->handleAudioData(data, len);
    }
}

void BluetoothA2DP::handleConnectionState(esp_a2d_connection_state_t state) {
    switch (state) {
        case ESP_A2D_CONNECTION_STATE_DISCONNECTED:
            connected = false;
            Serial.println("[BLUETOOTH] Device disconnected");
            break;
        case ESP_A2D_CONNECTION_STATE_CONNECTING:
            Serial.println("[BLUETOOTH] Device connecting...");
            break;
        case ESP_A2D_CONNECTION_STATE_CONNECTED:
            connected = true;
            Serial.println("[BLUETOOTH] Device connected");
            break;
        case ESP_A2D_CONNECTION_STATE_DISCONNECTING:
            Serial.println("[BLUETOOTH] Device disconnecting...");
            break;
    }
}

void BluetoothA2DP::handleAudioData(const uint8_t* data, uint32_t len) {
    // 音声データをバッファに書き込み
    if (audioBuffer && data && len > 0) {
        size_t written = audioBuffer->write(data, len);
        
        // バッファログ (5秒間隔)
        static unsigned long lastLog = 0;
        unsigned long currentTime = millis();
        
        if (currentTime - lastLog > 5000) {
            size_t totalWrite, totalRead, currentLevel;
            audioBuffer->getStats(totalWrite, totalRead, currentLevel);
            
            Serial.print("[AUDIO] Buffer: ");
            Serial.print(currentLevel);
            Serial.print("/");
            Serial.print(AUDIO_BUFFER_SIZE * BUFFER_COUNT);
            Serial.print(" bytes, Written: ");
            Serial.print(totalWrite);
            Serial.print(", Read: ");
            Serial.println(totalRead);
            
            lastLog = currentTime;
        }
        
        // バッファがフルの場合の警告
        if (written < len) {
            static unsigned long lastFullWarning = 0;
            if (currentTime - lastFullWarning > 10000) {
                Serial.print("[AUDIO] WARNING: Buffer full, dropped ");
                Serial.print(len - written);
                Serial.println(" bytes");
                lastFullWarning = currentTime;
            }
        }
    }
}

void BluetoothA2DP::attemptReconnection() {
    if (!connected) {
        Serial.println("[BLUETOOTH] Attempting reconnection...");
    }
}

void BluetoothA2DP::logStatus() {
    Serial.print("[SYSTEM] Free heap: ");
    Serial.print(ESP.getFreeHeap());
    Serial.println(" bytes");
    
    if (connected) {
        Serial.println("[BLUETOOTH] Status: Connected");
    } else {
        Serial.println("[BLUETOOTH] Status: Waiting for connection");
    }
}