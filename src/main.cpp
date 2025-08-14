#include <Arduino.h>
#include "config.h"
#include "bluetooth_a2dp.h"

BluetoothA2DP* bluetoothManager = nullptr;

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(1000);
    
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
    if (bluetoothManager) {
        bluetoothManager->loop();
    }
    
    static unsigned long lastHeartbeat = 0;
    unsigned long currentTime = millis();
    
    if (currentTime - lastHeartbeat > 30000) {
        Serial.println("[HEARTBEAT] System running normally");
        lastHeartbeat = currentTime;
    }
    
    delay(100);
}