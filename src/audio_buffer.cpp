#include "audio_buffer.h"

AudioBuffer* audioBuffer = nullptr;

AudioBuffer::AudioBuffer(size_t size) : 
    buffer(nullptr), bufferSize(size), writeIndex(0), readIndex(0), 
    availableBytes(0), mutex(nullptr), totalWritten(0), totalRead(0) {
}

AudioBuffer::~AudioBuffer() {
    cleanup();
}

bool AudioBuffer::init() {
    // メモリ確保
    buffer = (uint8_t*)malloc(bufferSize);
    if (!buffer) {
        Serial.println("[AUDIO] ERROR: Failed to allocate audio buffer");
        return false;
    }
    
    // ミューテックス作成
    mutex = xSemaphoreCreateMutex();
    if (!mutex) {
        Serial.println("[AUDIO] ERROR: Failed to create mutex");
        ::free(buffer); // グローバルfree関数を明示的に指定
        buffer = nullptr;
        return false;
    }
    
    // 初期化
    memset(buffer, 0, bufferSize);
    writeIndex = 0;
    readIndex = 0;
    availableBytes = 0;
    totalWritten = 0;
    totalRead = 0;
    
    Serial.print("[AUDIO] Buffer initialized: ");
    Serial.print(bufferSize);
    Serial.println(" bytes");
    
    return true;
}

void AudioBuffer::cleanup() {
    if (mutex) {
        vSemaphoreDelete(mutex);
        mutex = nullptr;
    }
    
    if (buffer) {
        ::free(buffer); // グローバルfree関数を明示的に指定
        buffer = nullptr;
    }
    
    Serial.println("[AUDIO] Buffer cleaned up");
}

size_t AudioBuffer::write(const uint8_t* data, size_t len) {
    if (!buffer || !data || len == 0) return 0;
    
    if (xSemaphoreTake(mutex, pdMS_TO_TICKS(10)) != pdTRUE) {
        return 0; // タイムアウト
    }
    
    size_t freeSpace = bufferSize - availableBytes;
    size_t writeLen = (len > freeSpace) ? freeSpace : len;
    
    for (size_t i = 0; i < writeLen; i++) {
        buffer[writeIndex] = data[i];
        writeIndex = (writeIndex + 1) % bufferSize;
    }
    
    availableBytes += writeLen;
    totalWritten += writeLen;
    
    xSemaphoreGive(mutex);
    return writeLen;
}

size_t AudioBuffer::read(uint8_t* data, size_t len) {
    if (!buffer || !data || len == 0) return 0;
    
    if (xSemaphoreTake(mutex, pdMS_TO_TICKS(10)) != pdTRUE) {
        return 0; // タイムアウト
    }
    
    size_t readLen = (len > availableBytes) ? availableBytes : len;
    
    for (size_t i = 0; i < readLen; i++) {
        data[i] = buffer[readIndex];
        readIndex = (readIndex + 1) % bufferSize;
    }
    
    availableBytes -= readLen;
    totalRead += readLen;
    
    xSemaphoreGive(mutex);
    return readLen;
}

size_t AudioBuffer::available() {
    if (xSemaphoreTake(mutex, pdMS_TO_TICKS(5)) != pdTRUE) {
        return 0;
    }
    size_t result = availableBytes;
    xSemaphoreGive(mutex);
    return result;
}

size_t AudioBuffer::freeSpace() {
    if (xSemaphoreTake(mutex, pdMS_TO_TICKS(5)) != pdTRUE) {
        return 0;
    }
    size_t result = bufferSize - availableBytes;
    xSemaphoreGive(mutex);
    return result;
}

bool AudioBuffer::isEmpty() {
    return available() == 0;
}

bool AudioBuffer::isFull() {
    return freeSpace() == 0;
}

void AudioBuffer::getStats(size_t& totalWrite, size_t& totalReadOut, size_t& currentLevel) {
    if (xSemaphoreTake(mutex, pdMS_TO_TICKS(5)) != pdTRUE) {
        totalWrite = totalReadOut = currentLevel = 0;
        return;
    }
    
    totalWrite = totalWritten;
    totalReadOut = totalRead;
    currentLevel = availableBytes;
    
    xSemaphoreGive(mutex);
}