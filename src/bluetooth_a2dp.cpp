#include "bluetooth_a2dp.h"
#include "BluetoothA2DPSink.h"

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
    
    a2dp_sink.set_pin_code(BT_PIN_CODE);
    a2dp_sink.set_stream_reader(audioDataCallback, false);
    a2dp_sink.set_on_connection_state_changed(connectionStateCallback);
    
    if (a2dp_sink.start(BT_DEVICE_NAME)) {
        initialized = true;
        Serial.print("[BLUETOOTH] Device discoverable: ");
        Serial.println(BT_DEVICE_NAME);
        Serial.println("[BLUETOOTH] Waiting for connection...");
        return true;
    } else {
        Serial.println("[BLUETOOTH] ERROR: Failed to initialize A2DP sink");
        return false;
    }
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
    
    static unsigned long lastStatusLog = 0;
    unsigned long currentTime = millis();
    
    if (currentTime - lastStatusLog > 10000) {
        logStatus();
        lastStatusLog = currentTime;
    }
    
    if (!isConnected() && (currentTime - lastConnectionAttempt > RECONNECT_INTERVAL)) {
        attemptReconnection();
        lastConnectionAttempt = currentTime;
    }
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
            Serial.print("[BLUETOOTH] Device connected: ");
            Serial.println(a2dp_sink.get_connected_source_name());
            break;
        case ESP_A2D_CONNECTION_STATE_DISCONNECTING:
            Serial.println("[BLUETOOTH] Device disconnecting...");
            break;
    }
}

void BluetoothA2DP::handleAudioData(const uint8_t* data, uint32_t len) {
    static unsigned long totalBytes = 0;
    static unsigned long lastReport = 0;
    
    totalBytes += len;
    unsigned long currentTime = millis();
    
    if (currentTime - lastReport > 5000) {
        Serial.print("[AUDIO] Data received: ");
        Serial.print(len);
        Serial.print(" bytes, Total: ");
        Serial.print(totalBytes);
        Serial.print(" bytes, Rate: ");
        Serial.print((totalBytes * 8) / ((currentTime - lastReport) / 1000.0), 0);
        Serial.println(" bps");
        
        Serial.print("[AUDIO] Sample rate: ");
        Serial.print(SAMPLE_RATE);
        Serial.print("Hz, Channels: ");
        Serial.println(CHANNELS);
        
        lastReport = currentTime;
        totalBytes = 0;
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