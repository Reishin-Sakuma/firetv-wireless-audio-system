#include <Arduino.h>
#include "config.h"
#include "bluetooth_a2dp.h"
#include "wifi_ap.h"
#include "audio_buffer.h"
#include "esp_task_wdt.h"

BluetoothA2DP* bluetoothManager = nullptr;
WiFiAP* wifiManager = nullptr;

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(1000);
    
    // ウォッチドッグタイマー設定を緩和
    esp_task_wdt_init(60, true);  // 60秒に延長
    esp_task_wdt_add(NULL);       // 現在のタスクを監視対象に追加
    
    Serial.println("========================================");
    Serial.println("ESP32 Bluetooth-WiFi Audio Bridge");
    Serial.println("Phase 2: Bluetooth A2DP + WiFi AP + HTTP Streaming");
    Serial.println("========================================");
    
    Serial.print("[SYSTEM] Free heap at startup: ");
    Serial.print(ESP.getFreeHeap());
    Serial.println(" bytes");
    
    // 音声バッファ初期化（メモリ使用量表示）
    Serial.print("[SYSTEM] Attempting to allocate audio buffer: ");
    Serial.print(AUDIO_BUFFER_SIZE * BUFFER_COUNT);
    Serial.println(" bytes");
    audioBuffer = new AudioBuffer(AUDIO_BUFFER_SIZE * BUFFER_COUNT);
    if (!audioBuffer || !audioBuffer->init()) {
        Serial.println("[ERROR] Failed to initialize audio buffer - continuing without audio");
        if (audioBuffer) {
            delete audioBuffer;
            audioBuffer = nullptr;
        }
    } else {
        Serial.println("[SYSTEM] Audio buffer initialized successfully");
    }
    
    // WiFi AP初期化 (Core 0で実行)
    wifiManager = new WiFiAP();
    if (wifiManager->init()) {
        Serial.println("[SYSTEM] WiFi Access Point initialized successfully");
    } else {
        Serial.println("[ERROR] Failed to initialize WiFi Access Point");
    }
    
    // Bluetooth A2DP初期化 (Core 1で実行)
    bluetoothManager = new BluetoothA2DP();
    if (bluetoothManager->init()) {
        Serial.println("[SYSTEM] Bluetooth A2DP initialized successfully");
        Serial.println("[INFO] Ready for Android device pairing");
        Serial.println("[INFO] Bluetooth name: " BT_DEVICE_NAME);
        Serial.println("[INFO] WiFi AP: " WIFI_AP_SSID " (password: " WIFI_AP_PASSWORD ")");
    } else {
        Serial.println("[ERROR] Failed to initialize Bluetooth A2DP");
        Serial.println("[ERROR] System will continue but Bluetooth won't work");
    }
    
    Serial.println("========================================");
}

void loop() {
    // より頻繁なウォッチドッグタイマーリセット
    esp_task_wdt_reset();
    
    // WiFi AP + HTTP Server処理 (Core 0)
    if (wifiManager) {
        wifiManager->loop();
        esp_task_wdt_reset();
    }
    
    // Bluetooth A2DP処理 (Core 1)
    if (bluetoothManager) {
        bluetoothManager->loop();
        esp_task_wdt_reset();
    }
    
    static unsigned long lastHeartbeat = 0;
    unsigned long currentTime = millis();
    
    if (currentTime - lastHeartbeat > 60000) { // 60秒間隔
        Serial.println("[HEARTBEAT] System running normally");
        Serial.print("[SYSTEM] Free heap: ");
        Serial.print(ESP.getFreeHeap());
        Serial.println(" bytes");
        
        // システム状態表示
        if (wifiManager && bluetoothManager) {
            Serial.print("[STATUS] WiFi Clients: ");
            Serial.print(wifiManager->hasClients() ? "Connected" : "None");
            Serial.print(", Bluetooth: ");
            Serial.println(bluetoothManager->isConnected() ? "Connected" : "Waiting");
        }
        
        lastHeartbeat = currentTime;
        esp_task_wdt_reset(); // ハートビート後にもリセット
    }
    
    // CPU負荷分散とより長いdelay
    delay(200); // 100ms→200msに延長
    
    // 明示的にタスクをyield
    yield();
    esp_task_wdt_reset(); // loop終了前にもリセット
}