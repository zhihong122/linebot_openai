import json
from flask import request, jsonify


# =========================================================
# Apple Health Adapter
# =========================================================


class AppleHealthError(Exception):
    """Apple Health Adapter 專用錯誤。"""
    pass


# =========================================================
# 資料格式標準化
# =========================================================

METRIC_CONFIG = {
    "heart_rate": {
        "unit": "bpm",
    },
    "resting_heart_rate": {
        "unit": "bpm",
    },
    "hrv_sdnn": {
        "unit": "ms",
    },
    "spo2": {
        "unit": "%",
    },
    "respiratory_rate": {
        "unit": "breaths/min",
    },
    "wrist_temperature": {
        "unit": "°C",
    },
    "steps": {
        "unit": "count",
    },
}


METRIC_ALIASES = {
    # Heart Rate
    "heart_rate": "heart_rate",
    "heartrate": "heart_rate",
    "HKQuantityTypeIdentifierHeartRate": "heart_rate",

    # Resting Heart Rate
    "resting_heart_rate": "resting_heart_rate",
    "restingheartrate": "resting_heart_rate",
    "HKQuantityTypeIdentifierRestingHeartRate":
        "resting_heart_rate",

    # HRV
    "hrv": "hrv_sdnn",
    "hrv_sdnn": "hrv_sdnn",
    "heart_rate_variability": "hrv_sdnn",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":
        "hrv_sdnn",

    # SpO2
    "spo2": "spo2",
    "oxygen_saturation": "spo2",
    "HKQuantityTypeIdentifierOxygenSaturation":
        "spo2",

    # Respiratory Rate
    "respiratory_rate": "respiratory_rate",
    "HKQuantityTypeIdentifierRespiratoryRate":
        "respiratory_rate",

    # Wrist Temperature
    "wrist_temperature": "wrist_temperature",
    "HKQuantityTypeIdentifierAppleSleepingWristTemperature":
        "wrist_temperature",

    # Steps
    "steps": "steps",
    "step_count": "steps",
    "HKQuantityTypeIdentifierStepCount":
        "steps",
}


def normalize_metric(metric):
    """
    將 Apple HealthKit metric 名稱
    轉成系統統一使用的名稱。
    """

    if not metric:
        return None

    metric_text = str(metric).strip()

    if metric_text in METRIC_ALIASES:
        return METRIC_ALIASES[metric_text]

    lower_metric = metric_text.lower()

    if lower_metric in METRIC_ALIASES:
        return METRIC_ALIASES[lower_metric]

    return lower_metric


def normalize_health_record(
    patient_id,
    data,
):
    """
    將 iPhone HealthWear App 傳來的資料，
    轉成後端統一格式。
    """

    metric = normalize_metric(
        data.get("metric")
    )

    if not metric:
        raise AppleHealthError(
            "缺少 metric"
        )

    if data.get("value") is None:
        raise AppleHealthError(
            "缺少 value"
        )

    measured_at = (
        data.get("measured_at")
        or data.get("timestamp")
    )

    if not measured_at:
        raise AppleHealthError(
            "缺少 measured_at"
        )

    device = data.get("device") or {}

    default_unit = (
        METRIC_CONFIG
        .get(metric, {})
        .get("unit")
    )

    return {
        "patient_id": str(patient_id),

        "source": "apple_healthkit",

        "metric": metric,

        "value": data.get("value"),

        "unit": (
            data.get("unit")
            or default_unit
        ),

        "measured_at": measured_at,

        "device": {
            "manufacturer": (
                device.get("manufacturer")
                or "Apple"
            ),

            "model": (
                device.get("model")
                or "Apple Watch"
            ),

            "name": device.get("name"),

            "hardware_version":
                device.get(
                    "hardware_version"
                ),

            "software_version":
                device.get(
                    "software_version"
                ),
        },

        "source_info": {
            "source_name":
                data.get("source_name"),

            "bundle_identifier":
                data.get(
                    "bundle_identifier"
                ),
        },

        "raw_data": data,
    }


# =========================================================
# Flask Adapter
# =========================================================

def register_apple_health(
    app,
    get_db_connection,
):
    """
    將 Apple Health API Routes
    註冊到目前 Flask App。

    使用方式：

    apple_health = register_apple_health(
        app,
        get_db_connection,
    )
    """

    # =====================================================
    # API Key -> Patient
    # =====================================================

    def get_patient_from_api_key(
        api_key,
    ):
        """
        利用 HealthWear App 傳來的 API Key
        找出資料屬於哪一位 patient。
        """

        if not api_key:
            return None

        connection = get_db_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    p.id,
                    p.full_name,
                    p.linked_user_id,
                    u.line_user_id
                FROM patients p
                JOIN app_users u
                  ON u.id = p.linked_user_id
                WHERE
                    p.health_api_key = %s
                    AND p.is_active = TRUE
                    AND u.is_active = TRUE
                LIMIT 1
                """,
                (api_key,),
            )

            row = cursor.fetchone()

            if not row:
                return None

            return {
                "patient_id": row[0],
                "patient_name": row[1],
                "app_user_id": row[2],
                "line_user_id": row[3],
            }

        finally:
            connection.close()


    # =====================================================
    # Save Health Measurement
    # =====================================================

    def save_health_measurement(
        record,
    ):
        """
        寫入 PostgreSQL。
        """

        connection = get_db_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO health_measurements (
                    patient_id,
                    source,
                    device_manufacturer,
                    device_model,
                    metric,
                    value,
                    unit,
                    measured_at,
                    raw_data
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s::jsonb
                )
                RETURNING id
                """,
                (
                    record["patient_id"],

                    record["source"],

                    record["device"].get(
                        "manufacturer"
                    ),

                    record["device"].get(
                        "model"
                    ),

                    record["metric"],

                    record["value"],

                    record["unit"],

                    record["measured_at"],

                    json.dumps(
                        record["raw_data"],
                        ensure_ascii=False,
                    ),
                ),
            )

            measurement_id = (
                cursor.fetchone()[0]
            )

            connection.commit()

            return measurement_id

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()


    # =====================================================
    # POST /api/health/apple
    # =====================================================

    @app.route(
        "/api/health/apple",
        methods=["POST"],
    )
    def receive_apple_health():

        try:
            # ---------------------------------------------
            # 1. 驗證裝置 / 使用者
            # ---------------------------------------------

            api_key = request.headers.get(
                "X-Health-API-Key"
            )

            if not api_key:
                return jsonify({
                    "success": False,
                    "error": (
                        "缺少 X-Health-API-Key"
                    ),
                }), 401

            patient = (
                get_patient_from_api_key(
                    api_key
                )
            )

            if not patient:
                return jsonify({
                    "success": False,
                    "error": (
                        "Health API Key 無效"
                    ),
                }), 401

            # ---------------------------------------------
            # 2. 讀取 JSON
            # ---------------------------------------------

            data = request.get_json(
                silent=True
            )

            if not data:
                return jsonify({
                    "success": False,
                    "error": (
                        "沒有收到 JSON 資料"
                    ),
                }), 400

            # ---------------------------------------------
            # 3. Normalize
            # ---------------------------------------------

            record = (
                normalize_health_record(
                    patient_id=patient[
                        "patient_id"
                    ],
                    data=data,
                )
            )

            # ---------------------------------------------
            # 4. 寫 PostgreSQL
            # ---------------------------------------------

            measurement_id = (
                save_health_measurement(
                    record
                )
            )

            app.logger.info(
                (
                    "Apple Health received: "
                    "patient=%s "
                    "metric=%s "
                    "value=%s "
                    "unit=%s"
                ),
                patient["patient_id"],
                record["metric"],
                record["value"],
                record["unit"],
            )

            # ---------------------------------------------
            # 5. 回應 iPhone
            # ---------------------------------------------

            return jsonify({
                "success": True,

                "measurement_id":
                    str(measurement_id),

                "patient_id":
                    str(
                        patient[
                            "patient_id"
                        ]
                    ),

                "metric":
                    record["metric"],

                "value":
                    record["value"],

                "unit":
                    record["unit"],

                "measured_at":
                    record[
                        "measured_at"
                    ],
            }), 200

        except AppleHealthError as error:

            return jsonify({
                "success": False,
                "error": str(error),
            }), 400

        except Exception as error:

            app.logger.exception(
                "Apple Health 接收資料失敗"
            )

            return jsonify({
                "success": False,
                "error": (
                    "Apple Health "
                    "資料處理失敗"
                ),
                "detail": str(error),
            }), 500


    # =====================================================
    # POST /api/health/apple/batch
    # =====================================================

    @app.route(
        "/api/health/apple/batch",
        methods=["POST"],
    )
    def receive_apple_health_batch():
        """
        iPhone 一次上傳多筆 HealthKit 資料。

        {
            "records": [
                {...},
                {...}
            ]
        }
        """

        try:
            api_key = request.headers.get(
                "X-Health-API-Key"
            )

            if not api_key:
                return jsonify({
                    "success": False,
                    "error": (
                        "缺少 X-Health-API-Key"
                    ),
                }), 401

            patient = (
                get_patient_from_api_key(
                    api_key
                )
            )

            if not patient:
                return jsonify({
                    "success": False,
                    "error": (
                        "Health API Key 無效"
                    ),
                }), 401

            payload = request.get_json(
                silent=True
            ) or {}

            records = payload.get(
                "records"
            )

            if not isinstance(
                records,
                list,
            ):
                return jsonify({
                    "success": False,
                    "error": (
                        "records 必須為陣列"
                    ),
                }), 400

            if len(records) > 500:
                return jsonify({
                    "success": False,
                    "error": (
                        "單次最多上傳 "
                        "500 筆資料"
                    ),
                }), 400

            saved = []
            failed = []

            for index, data in enumerate(
                records
            ):
                try:
                    record = (
                        normalize_health_record(
                            patient_id=
                                patient[
                                    "patient_id"
                                ],
                            data=data,
                        )
                    )

                    measurement_id = (
                        save_health_measurement(
                            record
                        )
                    )

                    saved.append({
                        "index": index,
                        "measurement_id":
                            str(
                                measurement_id
                            ),
                        "metric":
                            record[
                                "metric"
                            ],
                    })

                except Exception as error:
                    failed.append({
                        "index": index,
                        "error": str(error),
                    })

            return jsonify({
                "success": True,
                "received":
                    len(records),
                "saved":
                    len(saved),
                "failed":
                    len(failed),
                "saved_records":
                    saved,
                "failed_records":
                    failed,
            }), 200

        except Exception as error:

            app.logger.exception(
                (
                    "Apple Health Batch "
                    "處理失敗"
                )
            )

            return jsonify({
                "success": False,
                "error": str(error),
            }), 500


    # =====================================================
    # GET /api/health/apple/status
    # =====================================================

    @app.route(
        "/api/health/apple/status",
        methods=["GET"],
    )
    def apple_health_status():

        return jsonify({
            "success": True,
            "service":
                "apple_health_adapter",
            "status": "running",
        }), 200


    return {
        "enabled": True,
        "name": "apple_health",
    }
