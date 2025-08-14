#ifndef BLUETOOTH_A2DP_H
#define BLUETOOTH_A2DP_H

#include "config.h"

class BluetoothA2DP {
private:
    bool initialized;
    bool connected;
    unsigned long lastConnectionAttempt;
    static const unsigned long RECONNECT_INTERVAL = 30000; // 30秒

public:
    BluetoothA2DP();
    ~BluetoothA2DP();
    
    bool init();
    void cleanup();
    bool isConnected();
    void loop();
    
    static void connectionStateCallback(esp_a2d_connection_state_t state, void* ptr);
    static void audioDataCallback(const uint8_t* data, uint32_t len);
    
private:
    void handleConnectionState(esp_a2d_connection_state_t state);
    void handleAudioData(const uint8_t* data, uint32_t len);
    void attemptReconnection();
    void logStatus();
};

#endif