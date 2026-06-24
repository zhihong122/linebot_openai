from flask import Flask, request, abort
import os
import json
import requests

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    RichMenuSize,
    RichMenuRequest,
    RichMenuArea,
    RichMenuBounds,
    MessageAction,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent


app = Flask(__name__)

# ===== LINE 設定 =====
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== Rich Menu ID 暫存 =====
RICH_MENU_IDS = {}


# ===== 3x2 選單區域 =====
def areas_3x2(actions):
    return [
        RichMenuArea(bounds=RichMenuBounds(x=0, y=0, width=833, height=843),
                     action=MessageAction(text=actions[0])),
        RichMenuArea(bounds=RichMenuBounds(x=834, y=0, width=833, height=843),
                     action=MessageAction(text=actions[1])),
        RichMenuArea(bounds=RichMenuBounds(x=1667, y=0, width=833, height=843),
                     action=MessageAction(text=actions[2])),
        RichMenuArea(bounds=RichMenuBounds(x=0, y=843, width=833, height=843),
                     action=MessageAction(text=actions[3])),
        RichMenuArea(bounds=RichMenuBounds(x=834, y=843, width=833, height=843),
                     action=MessageAction(text=actions[4])),
        RichMenuArea(bounds=RichMenuBounds(x=1667, y=843, width=833, height=843),
                     action=MessageAction(text=actions[5])),
    ]


# ===== 3格橫向選單 =====
def areas_3cols(actions):
    return [
        RichMenuArea(bounds=RichMenuBounds(x=0, y=0, width=833, height=1686),
                     action=MessageAction(text=actions[0])),
        RichMenuArea(bounds=RichMenuBounds(x=834, y=0, width=833, height=1686),
                     action=MessageAction(text=actions[1])),
        RichMenuArea(bounds=RichMenuBounds(x=1667, y=0, width=833, height=1686),
                     action=MessageAction(text=actions[2])),
    ]


# ===== 2x2 選單區域 =====
def areas_2x2(actions):
    return [
        RichMenuArea(bounds=RichMenuBounds(x=0, y=0, width=1250, height=843),
                     action=MessageAction(text=actions[0])),
        RichMenuArea(bounds=RichMenuBounds(x=1250, y=0, width=1250, height=843),
                     action=MessageAction(text=actions[1])),
        RichMenuArea(bounds=RichMenuBounds(x=0, y=843, width=1250, height=843),
                     action=MessageAction(text=actions[2])),
        RichMenuArea(bounds=RichMenuBounds(x=1250, y=843, width=1250, height=843),
                     action=MessageAction(text=actions[3])),
    ]


# ===== 建立單一 Rich Menu =====
def create_rich_menu(key, name, image_path, areas, chat_bar_text="選單"):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_blob_api = MessagingApiBlob(api_client)

        rich_menu = RichMenuRequest(
            size=RichMenuSize(width=2500, height=1686),
            selected=True,
            name=name,
            chat_bar_text=chat_bar_text,
            areas=areas
        )

        rich_menu_id = line_bot_api.create_rich_menu(
            rich_menu_request=rich_menu
        ).rich_menu_id

        full_path = os.path.join(BASE_DIR, image_path)

        with open(full_path, "rb") as image:
            line_bot_blob_api.set_rich_menu_image(
                rich_menu_id=rich_menu_id,
                body=bytearray(image.read()),
                _headers={"Content-Type": "image/png"}
            )

        RICH_MENU_IDS[key] = rich_menu_id
        print(f"{key} = {rich_menu_id}")


# ===== 建立全部 Rich Menu =====
def create_all_rich_menus():

    # ===== 家屬 =====
    create_rich_menu(
        "family_main_menu",
        "family_main_menu",
        "static/family/family_main_menu.png",
        areas_3x2([
            "family_monitoring_menu",
            "family_management_menu",
            "family_medication_menu",
            "family_calendar_menu",
            "family_report_menu",
            "family_settings_menu",
        ])
    )

    create_rich_menu(
        "family_monitoring_menu",
        "family_monitoring_menu",
        "static/family/family_monitoring_menu.png",
        areas_3x2([
            "family_today_status",
            "family_missed_medication_notice",
            "family_emergency_notice",
            "family_discomfort_record",
            "family_medication_rate_stats",
            "family_main_menu",
        ])
    )

    create_rich_menu(
        "family_medication_menu",
        "family_medication_menu",
        "static/family/family_medication_menu.png",
        areas_3x2([
            "family_view_medication",
            "family_edit_medication",
            "family_remaining_medication",
            "family_medication_empty_notice",
            "family_medication_bag_record",
            "family_main_menu",
        ])
    )

    create_rich_menu(
        "family_calendar_menu",
        "family_calendar_menu",
        "static/family/family_calendar_menu.png",
        areas_3x2([
            "family_view_calendar",
            "family_add_schedule",
            "family_edit_schedule",
            "family_delete_schedule",
            "family_return_visit_reminder",
            "family_main_menu",
        ])
    )

    create_rich_menu(
        "family_report_menu",
        "family_report_menu",
        "static/family/family_report_menu.png",
        areas_3x2([
            "family_today_report",
            "family_7days_report",
            "family_30days_report",
            "family_abnormal_stats",
            "family_export_summary",
            "family_main_menu",
        ])
    )

    create_rich_menu(
        "family_settings_menu",
        "family_settings_menu",
        "static/family/family_settings_menu.png",
        areas_3x2([
            "family_notification_settings",
            "family_permission_settings",
            "family_language_settings",
            "family_help",
            "family_id",
            "family_main_menu",
        ])
    )

    # ===== 看護 印尼文 id =====
    create_rich_menu(
        "caregiver_patient_selector_menu_id",
        "caregiver_patient_selector_menu_id",
        "static/caregiver/id/caregiver_patient_selector_menu_id.png",
        areas_3cols([
            "caregiver_patient1_main_menu_id",
            "caregiver_patient2_main_menu_id",
            "caregiver_sos_contact_menu_id",
        ])
    )

    create_rich_menu(
        "caregiver_patient1_main_menu_id",
        "caregiver_patient1_main_menu_id",
        "static/caregiver/id/caregiver_patient1_main_menu_id.png",
        areas_3x2([
            "caregiver_patient1_today_tasks_menu_id",
            "caregiver_patient1_checklist_menu_id",
            "caregiver_patient1_medication_history",
            "caregiver_patient1_photo_prescription",
            "caregiver_patient1_report_issue_menu_id",
            "caregiver_patient_selector_menu_id",
        ])
    )

    create_rich_menu(
        "caregiver_patient1_today_tasks_menu_id",
        "caregiver_patient1_today_tasks_menu_id",
        "static/caregiver/id/caregiver_patient1_today_tasks_menu_id.png",
        areas_3x2([
            "caregiver_patient1_morning_tasks",
            "caregiver_patient1_afternoon_tasks",
            "caregiver_patient1_evening_tasks",
            "caregiver_patient1_before_sleep_tasks",
            "caregiver_patient1_medication_schedule",
            "caregiver_patient1_main_menu_id",
        ])
    )

    create_rich_menu(
        "caregiver_patient1_checklist_menu_id",
        "caregiver_patient1_checklist_menu_id",
        "static/caregiver/id/caregiver_patient1_checklist_menu_id.png",
        areas_3x2([
            "caregiver_patient1_morning_completed",
            "caregiver_patient1_afternoon_completed",
            "caregiver_patient1_evening_completed",
            "caregiver_patient1_before_sleep_completed",
            "caregiver_patient1_incomplete_items",
            "caregiver_patient1_main_menu_id",
        ])
    )

    create_rich_menu(
        "caregiver_patient1_report_issue_menu_id",
        "caregiver_patient1_report_issue_menu_id",
        "static/caregiver/id/caregiver_patient1_report_issue_menu_id.png",
        areas_3x2([
            "caregiver_patient1_refuse_medication",
            "caregiver_patient1_body_discomfort",
            "caregiver_patient1_vomiting",
            "caregiver_patient1_missing_medication",
            "caregiver_patient1_other_issue",
            "caregiver_patient1_main_menu_id",
        ])
    )

    create_rich_menu(
        "caregiver_sos_contact_menu_id",
        "caregiver_sos_contact_menu_id",
        "static/caregiver/id/caregiver_sos_contact_menu_id.png",
        areas_2x2([
            "caregiver_primary_contact_id",
            "caregiver_secondary_contact_id",
            "caregiver_sos_all_group_id",
            "caregiver_patient_selector_menu_id",
        ])
    )

    # ===== 長者 =====
    create_rich_menu(
        "patient_main_menu",
        "patient_main_menu",
        "static/patient/patient_main_menu.png",
        areas_3x2([
            "patient_today_medication_menu",
            "patient_my_medication_menu",
            "patient_medication_report_menu",
            "patient_discomfort_menu",
            "patient_calendar_menu",
            "patient_sos_menu",
        ])
    )

    create_rich_menu(
        "patient_today_medication_menu",
        "patient_today_medication_menu",
        "static/patient/patient_today_medication_menu.png",
        areas_3x2([
            "patient_breakfast_medication",
            "patient_lunch_medication",
            "patient_dinner_medication",
            "patient_before_sleep_medication",
            "patient_today_all_medication",
            "patient_main_menu",
        ])
    )

    create_rich_menu(
        "patient_my_medication_menu",
        "patient_my_medication_menu",
        "static/patient/patient_my_medication_menu.png",
        areas_3x2([
            "patient_medication_list",
            "patient_medication_instruction",
            "patient_remaining_medication",
            "patient_photo_prescription",
            "patient_stop_medication",
            "patient_main_menu",
        ])
    )

    create_rich_menu(
        "patient_medication_report_menu",
        "patient_medication_report_menu",
        "static/patient/patient_medication_report_menu.png",
        areas_3x2([
            "patient_breakfast_taken",
            "patient_lunch_taken",
            "patient_dinner_taken",
            "patient_before_sleep_taken",
            "patient_today_record",
            "patient_main_menu",
        ])
    )

    create_rich_menu(
        "patient_discomfort_menu",
        "patient_discomfort_menu",
        "static/patient/patient_discomfort_menu.png",
        areas_3x2([
            "patient_dizzy",
            "patient_headache",
            "patient_vomiting",
            "patient_sleep_bad",
            "patient_other_issue",
            "patient_main_menu",
        ])
    )

    create_rich_menu(
        "patient_calendar_menu",
        "patient_calendar_menu",
        "static/patient/patient_calendar_menu.png",
        areas_3x2([
            "patient_today_schedule",
            "patient_tomorrow_schedule",
            "patient_week_schedule",
            "patient_return_visit_info",
            "patient_medication_reminder",
            "patient_main_menu",
        ])
    )

    create_rich_menu(
        "patient_sos_menu",
        "patient_sos_menu",
        "static/patient/patient_sos_menu.png",
        areas_2x2([
            "patient_sos_contact1",
            "patient_sos_contact2",
            "patient_sos_all",
            "patient_main_menu",
        ])
    )


# ===== 切換 Rich Menu =====
def switch_rich_menu(user_id, menu_key):
    if menu_key in RICH_MENU_IDS:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.link_rich_menu_id_to_user(
                user_id=user_id,
                rich_menu_id=RICH_MENU_IDS[menu_key]
            )
        return True

    return False


# ===== Webhook =====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# ===== 文字事件 =====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 直接切換選單
    if switch_rich_menu(user_id, text):
        return

    # 身份入口
    if text in ["家屬", "family"]:
        switch_rich_menu(user_id, "family_main_menu")
        return

    if text in ["看護", "caregiver", "id", "indonesia"]:
        switch_rich_menu(user_id, "caregiver_patient_selector_menu_id")
        return

    if text in ["長者", "patient", "elder"]:
        switch_rich_menu(user_id, "patient_main_menu")
        return

    # 一般功能回覆
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=f"收到：{text}")
                ]
            )
        )


# ===== 啟動時建立 Rich Menu =====
if os.getenv("CREATE_RICH_MENU", "false").lower() == "true":
    create_all_rich_menus()


if __name__ == "__main__":
    app.run()
