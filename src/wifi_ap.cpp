#include "wifi_ap.h"
#include "audio_buffer.h"
#include "esp_task_wdt.h"

WiFiAP::WiFiAP() : server(nullptr), initialized(false), apStarted(false), lastStatusLog(0) {
}

WiFiAP::~WiFiAP() {
    cleanup();
}

bool WiFiAP::init() {
    Serial.println("[WIFI] Initializing Access Point...");
    
    // WiFi APモード設定
    setupAccessPoint();
    
    // Webサーバー設定
    setupWebServer();
    
    initialized = true;
    Serial.println("[WIFI] Access Point initialized successfully");
    return true;
}

void WiFiAP::setupAccessPoint() {
    // WiFiモードをAP+STAに設定（Bluetooth共存のため）
    WiFi.mode(WIFI_AP);
    
    // アクセスポイント設定
    WiFi.softAPConfig(WIFI_AP_IP_GATEWAY, WIFI_AP_IP_GATEWAY, WIFI_AP_IP_SUBNET);
    
    // アクセスポイント開始
    if (WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASSWORD, WIFI_AP_CHANNEL, WIFI_AP_HIDDEN, WIFI_AP_MAX_CONNECTION)) {
        apStarted = true;
        Serial.println("[WIFI] Access Point started successfully");
        Serial.print("[WIFI] SSID: ");
        Serial.println(WIFI_AP_SSID);
        Serial.print("[WIFI] IP Address: ");
        Serial.println(WiFi.softAPIP());
        Serial.print("[WIFI] Password: ");
        Serial.println(WIFI_AP_PASSWORD);
    } else {
        Serial.println("[WIFI] ERROR: Failed to start Access Point");
        apStarted = false;
    }
    
    esp_task_wdt_reset();
}

void WiFiAP::setupWebServer() {
    server = new WebServer(HTTP_SERVER_PORT);
    
    // ルートページ
    server->on("/", [this]() { handleRoot(); });
    
    // ストリーミングエンドポイント
    server->on(HTTP_STREAM_PATH, HTTP_GET, [this]() { handleStreamRequest(); });
    
    // 404ハンドラー
    server->onNotFound([this]() { handleNotFound(); });
    
    server->begin();
    Serial.print("[HTTP] Server started on port ");
    Serial.println(HTTP_SERVER_PORT);
    Serial.print("[HTTP] Stream URL: http://");
    Serial.print(WiFi.softAPIP());
    Serial.print(":");
    Serial.print(HTTP_SERVER_PORT);
    Serial.println(HTTP_STREAM_PATH);
}

void WiFiAP::handleRoot() {
    // 軽量化されたHTMLレスポンス
    String html = "<html><head><title>ESP32 Audio Bridge</title></head><body>";
    html += "<h1>ESP32 Audio Bridge</h1>";
    html += "<p>Stream: <a href='/stream'>http://" + WiFi.softAPIP().toString() + ":8080/stream</a></p>";
    html += "<p>1. Connect Bluetooth: ESP32-AudioBridge</p>";
    html += "<p>2. Play music on phone</p>";
    html += "<p>3. Open stream URL in VLC</p>";
    html += "<p>Status: " + String(hasClients() ? "Connected" : "No clients") + "</p>";
    html += "</body></html>";
    
    server->send(200, "text/html", html);
}

void WiFiAP::handleStreamRequest() {
    Serial.println("[HTTP] Stream request received - starting audio stream");
    
    // WAVヘッダー作成 (44.1kHz, 16bit, Stereo)
    uint8_t wavHeader[44] = {
        'R','I','F','F', 0xFF,0xFF,0xFF,0x7F, 'W','A','V','E', // RIFF header
        'f','m','t',' ', 16,0,0,0, 1,0, 2,0,                  // fmt chunk
        0x44,0xAC,0,0, 0x10,0xB1,0x02,0, 4,0, 16,0,          // 44100Hz, stereo, 16bit
        'd','a','t','a', 0xFF,0xFF,0xFF,0x7F                  // data chunk
    };
    
    // HTTP レスポンスヘッダー送信
    server->setContentLength(CONTENT_LENGTH_UNKNOWN);
    server->send(200, "audio/wav", "");
    
    // WAVヘッダー送信
    server->sendContent((char*)wavHeader, 44);
    
    // ストリーミング開始
    streamAudioData();
}

void WiFiAP::streamAudioData() {
    const size_t chunkSize = CHUNK_SIZE; // 設定ファイルから取得
    uint8_t audioChunk[chunkSize];
    unsigned long lastActivity = millis();
    unsigned long streamStart = millis();
    size_t totalSent = 0;
    
    Serial.println("[HTTP] Starting audio streaming...");
    
    while (server->client().connected()) {
        esp_task_wdt_reset();
        
        size_t bytesRead = 0;
        
        // オーディオバッファからデータ読み取り（安全チェック付き）
        if (audioBuffer != nullptr) {
            if (!audioBuffer->isEmpty()) {
                bytesRead = audioBuffer->read(audioChunk, chunkSize);
                lastActivity = millis();
            }
        } else {
            // バッファが初期化されていない場合の処理
            Serial.println("[HTTP] WARNING: Audio buffer not initialized");
        }
        
        // データがない場合は無音を送信
        if (bytesRead == 0) {
            // 無音データ (ゼロ) を生成
            memset(audioChunk, 0, chunkSize);
            bytesRead = chunkSize;
            
            // 10秒間データがない場合は接続終了
            if (millis() - lastActivity > 10000) {
                Serial.println("[HTTP] No audio data for 10s, ending stream");
                break;
            }
        }
        
        // クライアントにデータ送信
        if (bytesRead > 0) {
            if (!server->client().write(audioChunk, bytesRead)) {
                Serial.println("[HTTP] Client disconnected during streaming");
                break;
            }
            totalSent += bytesRead;
        }
        
        // ストリーミング統計 (30秒毎)
        if (millis() - streamStart > 30000 && totalSent > 0) {
            float duration = (millis() - streamStart) / 1000.0;
            float avgKbps = (totalSent * 8) / (duration * 1024);
            Serial.print("[HTTP] Streaming: ");
            Serial.print(duration);
            Serial.print("s, ");
            Serial.print(totalSent);
            Serial.print(" bytes, ");
            Serial.print(avgKbps);
            Serial.println(" Kbps");
            streamStart = millis();
            totalSent = 0;
        }
        
        delay(10); // CPU負荷軽減
    }
    
    Serial.println("[HTTP] Audio streaming ended");
}

void WiFiAP::handleNotFound() {
    server->send(404, "text/plain", "404: Not Found");
}

bool WiFiAP::isAPStarted() {
    return apStarted && WiFi.getMode() == WIFI_AP;
}

bool WiFiAP::hasClients() {
    return WiFi.softAPgetStationNum() > 0;
}

void WiFiAP::loop() {
    if (!initialized || !server) return;
    
    esp_task_wdt_reset();
    
    // Webサーバー処理
    server->handleClient();
    
    // ステータスログ（20秒間隔）
    unsigned long currentTime = millis();
    if (currentTime - lastStatusLog > 20000) {
        logStatus();
        lastStatusLog = currentTime;
    }
    
    yield();
}

void WiFiAP::logStatus() {
    Serial.print("[WIFI] AP Status: ");
    Serial.print(isAPStarted() ? "Active" : "Inactive");
    Serial.print(", Connected Clients: ");
    Serial.println(WiFi.softAPgetStationNum());
    
    if (hasClients()) {
        Serial.print("[WIFI] Client IP: ");
        // TODO: クライアントIP表示機能
    }
}

void WiFiAP::cleanup() {
    if (server) {
        server->stop();
        delete server;
        server = nullptr;
    }
    
    if (apStarted) {
        WiFi.softAPdisconnect(true);
        apStarted = false;
    }
    
    initialized = false;
    Serial.println("[WIFI] Access Point cleaned up");
}