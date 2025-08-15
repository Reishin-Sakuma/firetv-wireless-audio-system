#ifndef WIFI_AP_H
#define WIFI_AP_H

#include "config.h"
#include <WiFi.h>
#include <WebServer.h>

class WiFiAP {
private:
    WebServer* server;
    bool initialized;
    bool apStarted;
    unsigned long lastStatusLog;
    
public:
    WiFiAP();
    ~WiFiAP();
    
    bool init();
    void cleanup();
    bool isAPStarted();
    bool hasClients();
    void loop();
    void handleStreamRequest();
    void streamAudioData();
    void logStatus();
    
private:
    void setupAccessPoint();
    void setupWebServer();
    void handleRoot();
    void handleNotFound();
};

#endif