#include "esp_log.h"
#include "nvs_flash.h"
#include "icm42670.h"
#include "console/console.h"
#include "nimble/ble.h"
#include "host/ble_hs.h"
#include "host/ble_uuid.h"
#include "services/gap/ble_svc_gap.h"
#include "blecsc_sens.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include <stdio.h>
#define I2C_MASTER_NUM I2C_NUM_0

static const char *TAG = "BLE_IMU";
static const char *tag = "NimBLE_BLE_IMU";

static uint16_t conn_handle;
static uint8_t ble_addr_type;
static struct ble_csc_measurement_state csc_measurement_state;
static bool notify_state = false;
static uint16_t imu_characteristic_handle;
static const char *device_name = "ESP32C3_IMU";

/* Measurement and notification timer */
static struct ble_npl_callout blecsc_measure_timer;
static int ble_imu_gap_event(struct ble_gap_event *event, void *arg);

icm42670_handle_t imu;
icm42670_value_t accel;
icm42670_value_t gyro;

//Initialize I2C
static i2c_master_bus_handle_t i2c_handle = NULL;

static void i2c_bus_init(void) {
    const i2c_master_bus_config_t bus_config = {
        .i2c_port = I2C_MASTER_NUM,
        .sda_io_num = GPIO_NUM_10,
        .scl_io_num = GPIO_NUM_8,
        .clk_source = I2C_CLK_SRC_DEFAULT,
    };

    esp_err_t ret = i2c_new_master_bus(&bus_config, &i2c_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize I2C master bus: %s", esp_err_to_name(ret));
        return;
    }
    ESP_LOGI(TAG, "I2C bus initialized successfully.");
}

//Initialize IMU
static void imu_init(void) {
    esp_err_t ret;

    i2c_bus_init();

    ret = icm42670_create(i2c_handle, ICM42670_I2C_ADDRESS, &imu);
    if (ret != ESP_OK || imu == NULL) {
        ESP_LOGE(TAG, "Failed to initialize ICM42670: %s", esp_err_to_name(ret));
        return;
    }

    const icm42670_cfg_t imu_cfg = {
        .acce_fs = ACCE_FS_2G,
        .acce_odr = ACCE_ODR_400HZ,
        .gyro_fs = GYRO_FS_2000DPS,
        .gyro_odr = GYRO_ODR_400HZ,
    };

    ret = icm42670_config(imu, &imu_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure ICM42670: %s", esp_err_to_name(ret));
        return;
    }

    ret = icm42670_acce_set_pwr(imu, ACCE_PWR_LOWNOISE);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set accelerometer power: %s", esp_err_to_name(ret));
        return;
    }

    ret = icm42670_gyro_set_pwr(imu, GYRO_PWR_LOWNOISE);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set gyroscope power: %s", esp_err_to_name(ret));
        return;
    }

    ESP_LOGI(TAG, "ICM42670 sensor initialized and configured.");
}

// Notify IMU data
static void notify_imu_data(void) {
    if (!notify_state) {
        ESP_LOGI(TAG, "Notify state is false, not sending IMU data");
        return;
    }

    if (!imu) {
        ESP_LOGE(TAG, "IMU handle is null; skipping data notification.");
        return;
    }

    int rc = gatt_svr_chr_notify_csc_measurement(conn_handle);
    if (rc != 0) {
        ESP_LOGE(TAG, "Failed to send IMU notification: %d", rc);
    }
}

// Measurement Timer Callback
static void measurement_timer_cb(struct ble_npl_event *ev) {
    esp_err_t ret_accel = icm42670_get_acce_value(imu, &accel);
    esp_err_t ret_gyro = icm42670_get_gyro_value(imu, &gyro);

    if (ret_accel == ESP_OK && ret_gyro == ESP_OK) {
        notify_imu_data();  // Pass fresh data to the notify function
    } else {
        ESP_LOGE(TAG, "Failed to read IMU data during timer callback.");
    }
    ble_npl_callout_reset(&blecsc_measure_timer, pdMS_TO_TICKS(100));
}

//Advertise
static void ble_advertise(void) {
    struct ble_gap_adv_params adv_params;
    struct ble_hs_adv_fields fields;
    memset(&fields, 0, sizeof(fields));

    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    fields.tx_pwr_lvl_is_present = 1;
    fields.tx_pwr_lvl = BLE_HS_ADV_TX_PWR_LVL_AUTO;
    fields.name = (uint8_t *)device_name;
    fields.name_len = strlen(device_name);
    fields.name_is_complete = 1;

    int rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
        ESP_LOGE(TAG, "Error setting advertisement data; rc=%d", rc);
        return;
    }

    memset(&adv_params, 0, sizeof(adv_params));
    adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;

    rc = ble_gap_adv_start(ble_addr_type, NULL, BLE_HS_FOREVER, &adv_params,
                           ble_imu_gap_event, NULL);
    if (rc != 0) {
        ESP_LOGE(TAG, "Error starting advertisement; rc=%d", rc);
        return;
    }
}

// GAP Event Callback
static int ble_imu_gap_event(struct ble_gap_event *event, void *arg) {
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        if (event->connect.status == 0) {
            conn_handle = event->connect.conn_handle;
        } else {
            ble_advertise();
        }
        break;

    case BLE_GAP_EVENT_DISCONNECT:
        ble_advertise();
        conn_handle = 0;
        break;

    case BLE_GAP_EVENT_SUBSCRIBE:
        if (event->subscribe.attr_handle == csc_measurement_handle) {
            notify_state = event->subscribe.cur_notify;
            ESP_LOGI(TAG, "Notify state changed: %d", notify_state);
        }
        break;

    case BLE_GAP_EVENT_MTU:
        break;
    }
    return 0;
}

// Host Sync Callback
static void ble_on_sync(void) {
    int rc = ble_hs_id_infer_auto(0, &ble_addr_type);
    if (rc == 0) {
        ble_advertise();
    }
}

void ble_host_task(void *param) {
    nimble_port_run();
    nimble_port_freertos_deinit();
}

//Main code
int app_main(void) {
    if (imu) {
        icm42670_delete(imu);
        imu = NULL;
        ESP_LOGI(TAG, "IMU handle deleted for reinitialization.");
    }
    
    imu_init();

    esp_log_level_set("*", ESP_LOG_INFO);

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ret = nimble_port_init();
    if (ret != ESP_OK) {
        ESP_LOGE(tag, "Failed to init nimble %d", ret);
        return -1;
    }

    ble_hs_cfg.sync_cb = ble_on_sync;

    int rc = gatt_svr_init(&csc_measurement_state);
    ble_npl_callout_init(&blecsc_measure_timer, nimble_port_get_dflt_eventq(),
                         measurement_timer_cb, NULL);
    ble_npl_callout_reset(&blecsc_measure_timer, pdMS_TO_TICKS(100));

    rc = ble_svc_gap_device_name_set(device_name);
    if (rc == 0) {
        nimble_port_freertos_init(ble_host_task);
    }
    return 0;
}

