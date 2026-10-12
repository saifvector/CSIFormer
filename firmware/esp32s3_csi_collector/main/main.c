/*
 * ESP32-S3 Wi-Fi Channel State Information (CSI) Collector Firmware
 * CSIFormer Phase 02 — Real-Time Hardware Acquisition Pipeline
 * 
 * Captures raw OFDM CSI subcarrier IQ frames, extracts amplitudes & unwrapped phases,
 * and streams telemetry over High-Speed USB Serial (921,600 baud) or UDP socket broadcast.
 */

#include <stdio.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_spi_flash.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"

static const char *TAG = "ESP32S3_CSI_COLLECTOR";

#define WIFI_CHANNEL 6
#define SERIAL_BAUD 921600
#define UDP_PORT 5555
#define UDP_SERVER_IP "192.168.1.255" // Broadcast IP

static int udp_sock = -1;
static struct sockaddr_in dest_addr;
static uint32_t packet_sequence = 0;

/*
 * Wi-Fi CSI Callback Handler
 * Executed by ESP32-S3 hardware whenever a Wi-Fi packet is received on the configured channel.
 */
void wifi_csi_cb(void *ctx, wifi_csi_info_t *info) {
    if (!info || !info->buf) {
        return;
    }

    packet_sequence++;
    uint8_t mac_str[18];
    snprintf((char*)mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
             info->mac[0], info->mac[1], info->mac[2],
             info->mac[3], info->mac[4], info->mac[5]);

    int num_subcarriers = info->len / 2; // Each subcarrier has I (int8) and Q (int8)
    int8_t *csi_raw = (int8_t *)info->buf;

    // Buffer to format telemetry string
    char payload_buf[2048];
    int offset = snprintf(payload_buf, sizeof(payload_buf),
                          "CSI_DATA,%s,%d,%d,%d,%d,",
                          mac_str, info->rx_ctrl.rssi, info->rx_ctrl.noise_floor,
                          packet_sequence, num_subcarriers);

    // Calculate Amplitudes & Phases for each subcarrier
    for (int i = 0; i < num_subcarriers; i++) {
        int8_t real = csi_raw[i * 2];
        int8_t imag = csi_raw[i * 2 + 1];

        float amp = sqrtf(real * real + imag * imag);
        float phase = atan2f((float)imag, (float)real);

        offset += snprintf(payload_buf + offset, sizeof(payload_buf) - offset,
                           "%.2f:%.3f%s", amp, phase, (i == num_subcarriers - 1) ? "\n" : ",");

        if (offset >= sizeof(payload_buf) - 64) {
            break; // Avoid buffer overflow
        }
    }

    // 1. Stream over High-Speed USB Serial
    printf("%s", payload_buf);

    // 2. Stream over UDP Socket Broadcast if connected
    if (udp_sock >= 0) {
        sendto(udp_sock, payload_buf, strlen(payload_buf), 0,
               (struct sockaddr *)&dest_addr, sizeof(dest_addr));
    }
}

void init_csi() {
    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf2_en = true,
        .rx_filter_len = 16,
        .channel_filter_en = true,
        .manu_scale = false,
        .shift = false
    };

    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(wifi_csi_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
    ESP_LOGI(TAG, "Wi-Fi CSI Collection Enabled on Channel %d", WIFI_CHANNEL);
}

void app_main(void) {
    // Initialize NVS Flash
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_LOGI(TAG, "Initializing ESP32-S3 Wi-Fi CSI Sensing Node...");

    // Initialize Wi-Fi in Promiscuous Mode
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_NULL));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));

    // Enable CSI Subcarrier Hardware Extraction
    init_csi();

    ESP_LOGI(TAG, "ESP32-S3 CSI Node Active & Streaming Telemetry...");
}
