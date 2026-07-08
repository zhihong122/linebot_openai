from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    RichMenuRequest,
    CreateRichMenuAliasRequest,
    RichMenuBulkLinkRequest,
    RichMenuBulkUnlinkRequest,
    RichMenuBatchUnlinkAllOperation,
    RichMenuBatchRequest,
    RichMenuBatchOperation,
    RichMenuBatchLinkOperation,
    RichMenuBatchUnlinkOperation
)
import requests
import os

configuration = Configuration(access_token=os.getenv('CHANNEL_ACCESS_TOKEN'))

with ApiClient(configuration) as api_client:
    line_bot_api = MessagingApi(api_client)
    line_bot_blob_api = MessagingApiBlob(api_client)

    base_url = "https://raw.githubusercontent.com/zhihong122/linebot_openai/master/static/caregiver"

    # ============================== 看護主選單：患者選擇 ==============================
    rich_menu_main_str = """{
        "size": {"width": 2500, "height": 1686},
        "selected": true,
        "name": "看護患者選擇",
        "chatBarText": "查看更多資訊",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_patient1_main",
                    "data": "switch-to-caregiver-patient1-main"
                }
            },
            {
                "bounds": {"x": 1663, "y": 0, "width": 837, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_sos_contact",
                    "data": "switch-to-caregiver-sos-contact"
                }
            }
        ]
    }"""

    rich_menu_main_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_main_str)
    ).rich_menu_id

    print(f"caregiver_main_id: {rich_menu_main_id}")

    response = requests.get(f"{base_url}/caregiver_patient_selector_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_main_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="caregiver_main",
            rich_menu_id=rich_menu_main_id
        )
    )

    # ============================== 患者1主選單 ==============================
    rich_menu_patient1_main_str = """{
        "size": {"width": 2500, "height": 1686},
        "selected": true,
        "name": "看護患者1主選單",
        "chatBarText": "查看更多資訊",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_patient1_today_tasks",
                    "data": "switch-to-caregiver-patient1-today-tasks"
                }
            },
            {
                "bounds": {"x": 834, "y": 0, "width": 833, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_patient1_checklist",
                    "data": "switch-to-caregiver-patient1-checklist"
                }
            },
            {
                "bounds": {"x": 834, "y": 843, "width": 833, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_patient1_report_issue",
                    "data": "switch-to-caregiver-patient1-report-issue"
                }
            },
            {
                "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_main",
                    "data": "switch-to-caregiver-main"
                }
            }
        ]
    }"""

    rich_menu_patient1_main_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_patient1_main_str)
    ).rich_menu_id

    print(f"caregiver_patient1_main_id: {rich_menu_patient1_main_id}")

    response = requests.get(f"{base_url}/caregiver_patient1_main_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_patient1_main_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="caregiver_patient1_main",
            rich_menu_id=rich_menu_patient1_main_id
        )
    )

    # ============================== 患者1：今日任務 ==============================
    rich_menu_today_tasks_str = """{
        "size": {"width": 2500, "height": 1686},
        "selected": true,
        "name": "看護患者1今日任務",
        "chatBarText": "返回患者1",
        "areas": [
            {
                "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_patient1_main",
                    "data": "switch-to-caregiver-patient1-main"
                }
            }
        ]
    }"""

    rich_menu_today_tasks_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_today_tasks_str)
    ).rich_menu_id

    print(f"caregiver_patient1_today_tasks_id: {rich_menu_today_tasks_id}")

    response = requests.get(f"{base_url}/caregiver_patient1_today_tasks_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_today_tasks_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="caregiver_patient1_today_tasks",
            rich_menu_id=rich_menu_today_tasks_id
        )
    )

    # ============================== 患者1：Checklist ==============================
    rich_menu_checklist_str = """{
        "size": {"width": 2500, "height": 1686},
        "selected": true,
        "name": "看護患者1 Checklist",
        "chatBarText": "返回患者1",
        "areas": [
            {
                "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_patient1_main",
                    "data": "switch-to-caregiver-patient1-main"
                }
            }
        ]
    }"""

    rich_menu_checklist_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_checklist_str)
    ).rich_menu_id

    print(f"caregiver_patient1_checklist_id: {rich_menu_checklist_id}")

    response = requests.get(f"{base_url}/caregiver_patient1_checklist_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_checklist_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="caregiver_patient1_checklist",
            rich_menu_id=rich_menu_checklist_id
        )
    )

    # ============================== 患者1：異常回報 ==============================
    rich_menu_report_issue_str = """{
        "size": {"width": 2500, "height": 1686},
        "selected": true,
        "name": "看護患者1異常回報",
        "chatBarText": "返回患者1",
        "areas": [
            {
                "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_patient1_main",
                    "data": "switch-to-caregiver-patient1-main"
                }
            }
        ]
    }"""

    rich_menu_report_issue_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_report_issue_str)
    ).rich_menu_id

    print(f"caregiver_patient1_report_issue_id: {rich_menu_report_issue_id}")

    response = requests.get(f"{base_url}/caregiver_patient1_report_issue_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_report_issue_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="caregiver_patient1_report_issue",
            rich_menu_id=rich_menu_report_issue_id
        )
    )

    # ============================== SOS 聯絡 ==============================
    rich_menu_sos_contact_str = """{
        "size": {"width": 2500, "height": 1686},
        "selected": true,
        "name": "看護SOS聯絡",
        "chatBarText": "返回主選單",
        "areas": [
            {
                "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "caregiver_main",
                    "data": "switch-to-caregiver-main"
                }
            }
        ]
    }"""

    rich_menu_sos_contact_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_sos_contact_str)
    ).rich_menu_id

    print(f"caregiver_sos_contact_id: {rich_menu_sos_contact_id}")

    response = requests.get(f"{base_url}/caregiver_sos_contact_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_sos_contact_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="caregiver_sos_contact",
            rich_menu_id=rich_menu_sos_contact_id
        )
    )

    # Step 4. 連結圖文選單到使用者
    # user_ids = ["Uxxxxxxx"]
    # line_bot_api.link_rich_menu_id_to_user(userId, rich_menu_main_id)
    # line_bot_api.link_rich_menu_id_to_users(
    #     RichMenuBulkLinkRequest(
    #         rich_menu_id=rich_menu_main_id,
    #         user_ids=user_ids
    #     )
    # )

    # 取消圖文選單連結使用者
    # line_bot_api.unlink_rich_menu_id_from_user("Uxxxxxxx")
    # line_bot_api.unlink_rich_menu_id_from_users(
    #     RichMenuBulkUnlinkRequest(
    #         user_ids=user_ids
    #     )
    # )

    # 取得使用者的圖文選單ID
    # rich_menu_id = line_bot_api.get_rich_menu_id_of_user("Uxxxxxxx")

    # 批次替換或取消連結圖文選單
    # line_bot_api.rich_menu_batch(
    #     RichMenuBatchRequest(
    #         operations=[
    #             # RichMenuBatchLinkOperation(
    #             #     var_from="richmenu-xxxxxxx",
    #             #     to=rich_menu_main_id
    #             # ),
    #             # RichMenuBatchUnlinkOperation(
    #             #     var_from="richmenu-xxxxxxx"
    #             # ),
    #             RichMenuBatchUnlinkAllOperation(),
    #         ]
    #     )
    # )

    print("看護 Rich Menu 建立完成")
    print(f"caregiver_main_id: {rich_menu_main_id}")
