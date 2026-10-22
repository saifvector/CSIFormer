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
#if __has_include("esp_spi_flash.h")
#include "esp_spi_flash.h"
#endif
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"

static const char *TAG = "ESP32S3_CSI_COLLECTOR";

#define WIFI_CHANNEL 7
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
                          "CSI_DATA,%s,%d,%d,%lu,%d,",
                          mac_str, (int)info->rx_ctrl.rssi, (int)info->rx_ctrl.noise_floor,
                          (unsigned long)packet_sequence, num_subcarriers);

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

static esp_err_t init_csi(void) {
    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = true,
        .manu_scale = false,
        .shift = 0,
        .dump_ack_en = false
    };

    esp_err_t ret = esp_wifi_set_csi_config(&csi_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_set_csi_config failed: %s (0x%x)", esp_err_to_name(ret), ret);
        return ret;
    }

    ret = esp_wifi_set_csi_rx_cb(wifi_csi_cb, NULL);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_set_csi_rx_cb failed: %s (0x%x)", esp_err_to_name(ret), ret);
        return ret;
    }

    ret = esp_wifi_set_csi(true);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_set_csi failed: %s (0x%x)", esp_err_to_name(ret), ret);
        return ret;
    }

    ESP_LOGI(TAG, "Wi-Fi CSI Collection Enabled on Channel %d", WIFI_CHANNEL);
    return ESP_OK;
}

void app_main(void) {
    // Initialize NVS Flash
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS flash initialization failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    ESP_LOGI(TAG, "Initializing ESP32-S3 Wi-Fi CSI Sensing Node...");

    // Initialize Network Interface and System Event Loop
    ret = esp_netif_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_netif_init failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    ret = esp_event_loop_create_default();
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(TAG, "esp_event_loop_create_default failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    esp_netif_create_default_wifi_sta();

    // Initialize Wi-Fi in Station / Promiscuous Mode
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    cfg.csi_enable = 1; // Explicitly ensure CSI driver buffer allocation in MAC layer
    ret = esp_wifi_init(&cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_init failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    ret = esp_wifi_set_storage(WIFI_STORAGE_RAM);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_set_storage failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    ret = esp_wifi_set_mode(WIFI_MODE_STA);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_set_mode(STA) failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    ret = esp_wifi_start();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_start failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    ret = esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_set_channel failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    ret = esp_wifi_set_promiscuous(true);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_set_promiscuous failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    // Enable CSI Subcarrier Hardware Extraction
    ret = init_csi();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "CSI initialization failed: %s (0x%x)", esp_err_to_name(ret), ret);
        goto fail_halt;
    }

    ESP_LOGI(TAG, "ESP32-S3 CSI Node Active & Streaming Telemetry on Channel %d...", WIFI_CHANNEL);
    return;

fail_halt:
    ESP_LOGE(TAG, "FATAL: Wi-Fi CSI initialization encountered a fatal error. Entering diagnostic halt.");
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
