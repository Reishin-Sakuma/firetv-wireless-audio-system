#ifndef AUDIO_BUFFER_H
#define AUDIO_BUFFER_H

#include "config.h"
#include <Arduino.h>

class AudioBuffer {
private:
    uint8_t* buffer;
    size_t bufferSize;
    volatile size_t writeIndex;
    volatile size_t readIndex;
    volatile size_t availableBytes;
    SemaphoreHandle_t mutex;
    
public:
    AudioBuffer(size_t size);
    ~AudioBuffer();
    
    bool init();
    void cleanup();
    
    // 書き込み (Bluetooth側で使用)
    size_t write(const uint8_t* data, size_t len);
    
    // 読み出し (HTTP側で使用)
    size_t read(uint8_t* data, size_t len);
    
    // 状態確認
    size_t available();
    size_t freeSpace(); // free()から名前変更
    bool isEmpty();
    bool isFull();
    
    // 統計情報
    void getStats(size_t& totalWrite, size_t& totalRead, size_t& currentLevel);
    
private:
    size_t totalWritten;
    size_t totalRead;
};

extern AudioBuffer* audioBuffer;

#endif