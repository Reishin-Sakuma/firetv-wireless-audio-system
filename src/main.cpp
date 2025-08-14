#include <Arduino.h>
#include "config.h"
#include "bluetooth_a2dp.h"
#include "esp_task_wdt.h"

BluetoothA2DP* bluetoothManager = nullptr;

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(1000);
    
    // ウォッチドッグタイマー設定を緩和
    esp_task_wdt_init(60, true);  // 60秒に延長
    esp_task_wdt_add(NULL);       // 現在のタスクを監視対象に追加
    
    Serial.println("========================================");
    Serial.println("ESP32 Bluetooth-WiFi Audio Bridge");
    Serial.println("Phase 1: Bluetooth A2DP Sink");
    Serial.println("========================================");
    
    Serial.print("[SYSTEM] Free heap at startup: ");
    Serial.print(ESP.getFreeHeap());
    Serial.println(" bytes");
    
    bluetoothManager = new BluetoothA2DP();
    
    if (bluetoothManager->init()) {
        Serial.println("[SYSTEM] Bluetooth A2DP initialized successfully");
        Serial.println("[INFO] Ready for Android device pairing");
        Serial.println("[INFO] Device name: " BT_DEVICE_NAME);
        Serial.println("[INFO] PIN code: " BT_PIN_CODE);
    } else {
        Serial.println("[ERROR] Failed to initialize Bluetooth A2DP");
        Serial.println("[ERROR] System will continue but Bluetooth won't work");
    }
    
    Serial.println("========================================");
}

void loop() {
    // より頻繁なウォッチドッグタイマーリセット
    esp_task_wdt_reset();
    
    if (bluetoothManager) {
        bluetoothManager->loop();
        // Bluetooth処理後にもリセット
        esp_task_wdt_reset();
    }
    
    static unsigned long lastHeartbeat = 0;
    unsigned long currentTime = millis();
    
    if (currentTime - lastHeartbeat > 60000) { // 60秒間隔
        Serial.println("[HEARTBEAT] System running normally");
        Serial.print("[SYSTEM] Free heap: ");
        Serial.print(ESP.getFreeHeap());
        Serial.println(" bytes");
        lastHeartbeat = currentTime;
        esp_task_wdt_reset(); // ハートビート後にもリセット
    }
    
    // CPU負荷分散とより長いdelay
    delay(200); // 100ms→200msに延長
    
    // 明示的にタスクをyield
    yield();
    esp_task_wdt_reset(); // loop終了前にもリセット
}