#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

// ===== Camera Pin Definitions (ESP32-CAM board example) =====
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM     21
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       19
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM        5
#define Y2_GPIO_NUM        4
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ===== WiFi & Server Settings =====
<<<<<<< HEAD
//const char* ssid = "testSKY";
//const char* password = "1234abcd@";
//const char* serverUrl = "http://10.206.92.118:5000/upload";

=======
>>>>>>> 88c29a20bb1f4f1a3fc7cb5055903e32f67de20a
const char* ssid = "Eray";
const char* password = "12345678";
const char* serverUrl = "http://10.206.41.172:5000/upload";

<<<<<<< HEAD

=======
>>>>>>> 88c29a20bb1f4f1a3fc7cb5055903e32f67de20a
// ===== Chunk Settings =====
const unsigned long CHUNK_DURATION_MS = 1000; // 1-second chunks

// ===== ImageChunker Class =====
// Manages the chunk state (chunk ID and start timestamp)
class ImageChunker {
public:
    uint32_t chunkId;
    double chunkStartTimestamp; // epoch seconds with fraction (e.g., 1707429012.456)
    unsigned long chunkStartMillis; // local millis() at chunk start

    ImageChunker() : chunkId(0), chunkStartTimestamp(0), chunkStartMillis(0) {}

    // Returns the current time as a double (epoch seconds plus milliseconds fraction)
    double getCurrentTimestamp() {
        time_t now;
        time(&now);
        // Use the remainder of millis() to add fractional seconds
        double fraction = (millis() % 1000) / 1000.0;
        return now + fraction;
    }

    // Starts a new chunk by incrementing the chunk ID and capturing the current time
    void startNewChunk() {
        chunkId++;
        chunkStartMillis = millis();
        chunkStartTimestamp = getCurrentTimestamp();
        Serial.printf("Starting new chunk: %u, timestamp: %.3f\n", chunkId, chunkStartTimestamp);
    }
};

ImageChunker chunker;

// ===== Helper Functions =====

// Connect to WiFi
void initWiFi() {
    Serial.print("Connecting to WiFi");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi connected");
}

// Synchronize time using NTP
void initTime() {
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
    Serial.print("Waiting for time synchronization");
    time_t now = time(nullptr);
    while (now < 100000) { // wait until time is set (adjust threshold as needed)
        delay(500);
        Serial.print(".");
        now = time(nullptr);
    }
    Serial.println("\nTime synchronized");
}

// Initialize the camera (configured for ~480p capture)
void initCamera() {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    
    // Use VGA (640x480) for approximately 480p resolution
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 10;  // Adjust quality as needed for FPS/memory
    config.fb_count = 1;
    
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x", err);
        return;
    }
    
    // Optionally configure sensor parameters
    sensor_t * s = esp_camera_sensor_get();
    if (s) {
        s->set_brightness(s, 0);
        s->set_contrast(s, 0);
        s->set_saturation(s, 0);
        s->set_special_effect(s, 0);
        s->set_whitebal(s, 1);
        s->set_awb_gain(s, 1);
        s->set_wb_mode(s, 0);
        s->set_exposure_ctrl(s, 1);
        s->set_aec2(s, 0);
        s->set_gain_ctrl(s, 1);
        s->set_agc_gain(s, 0);
        s->set_gainceiling(s, (gainceiling_t)0);
        s->set_bpc(s, 0);
        s->set_wpc(s, 1);
        s->set_raw_gma(s, 1);
        s->set_lenc(s, 1);
        s->set_hmirror(s, 0);
        s->set_vflip(s, 0);
        s->set_dcw(s, 1);
    }
}

// Capture an image and send it to the server along with chunk metadata.
void captureAndSendImage(uint32_t chunkId, double chunkStartTimestamp) {
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("Camera capture failed");
        return;
    }
    
    HTTPClient http;
    // Construct the URL with query parameters for chunk metadata.
    String url = String(serverUrl) + "?chunk_id=" + String(chunkId) + "&chunk_start=" + String(chunkStartTimestamp, 3);
    http.begin(url);
    http.addHeader("Content-Type", "image/jpeg");
    
    int httpResponseCode = http.POST(fb->buf, fb->len);
    
    if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.printf("Image sent (chunk %u) successfully, response: %s\n", chunkId, response.c_str());
    } else {
        Serial.printf("Error sending image (chunk %u): %d\n", chunkId, httpResponseCode);
    }
    
    http.end();
    esp_camera_fb_return(fb);
}

// ===== Main Setup and Loop =====
void setup() {
    Serial.begin(115200);
    initWiFi();
    initTime();
    initCamera();
    chunker.startNewChunk();  // Start the very first chunk
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        unsigned long currentMillis = millis();
        // If the current chunk has exceeded CHUNK_DURATION_MS, start a new one.
        if (currentMillis - chunker.chunkStartMillis >= CHUNK_DURATION_MS) {
            chunker.startNewChunk();
        }
        // Capture and send an image along with the current chunk metadata.
        captureAndSendImage(chunker.chunkId, chunker.chunkStartTimestamp);
        // A small delay can help yield to background tasks; adjust based on your FPS goals.
        delay(10);
    } else {
        Serial.println("WiFi not connected");
        delay(1000);
    }
}
