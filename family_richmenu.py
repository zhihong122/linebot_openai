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

    # GitHub 圖片 raw 路徑
    base_url = "https://raw.githubusercontent.com/zhihong122/linebot_openai/master/static/family/"

    # ============================== 家屬主選單 ==============================
    rich_menu_main_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "家屬主選單",
        "chatBarText": "查看更多資訊",
        "areas": [
            {
                "bounds": {
                    "x": 0,
                    "y": 0,
                    "width": 833,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_monitoring",
                    "data": "switch-to-family-monitoring"
                }
            },
            {
                "bounds": {
                    "x": 834,
                    "y": 0,
                    "width": 833,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_management",
                    "data": "switch-to-family-management"
                }
            },
            {
                "bounds": {
                    "x": 1663,
                    "y": 0,
                    "width": 837,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_medication",
                    "data": "switch-to-family-medication"
                }
            },
            {
                "bounds": {
                    "x": 0,
                    "y": 843,
                    "width": 833,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_calendar",
                    "data": "switch-to-family-calendar"
                }
            },
            {
                "bounds": {
                    "x": 834,
                    "y": 843,
                    "width": 833,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_report",
                    "data": "switch-to-family-report"
                }
            },
            {
                "bounds": {
                    "x": 1663,
                    "y": 843,
                    "width": 837,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_settings",
                    "data": "switch-to-family-settings"
                }
            }
        ]
    }"""

    rich_menu_main_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_main_str)
    ).rich_menu_id

    print(f"family_main_id: {rich_menu_main_id}")

    response = requests.get(f"{base_url}/family_main_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_main_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="family_main",
            rich_menu_id=rich_menu_main_id
        )
    )

    # ============================== 監控中心 ==============================
    rich_menu_monitoring_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "家屬監控中心",
        "chatBarText": "返回主選單",
        "areas": [
            {
                "bounds": {
                    "x": 1663,
                    "y": 843,
                    "width": 837,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_main",
                    "data": "switch-to-family-main"
                }
            }
        ]
    }"""

    rich_menu_monitoring_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_monitoring_str)
    ).rich_menu_id

    print(f"family_monitoring_id: {rich_menu_monitoring_id}")

    response = requests.get(f"{base_url}/family_monitoring_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_monitoring_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="family_monitoring",
            rich_menu_id=rich_menu_monitoring_id
        )
    )

    # ============================== 家庭管理 ==============================
    rich_menu_management_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "家屬家庭管理",
        "chatBarText": "返回主選單",
        "areas": [
            {
                "bounds": {
                    "x": 1663,
                    "y": 843,
                    "width": 837,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_main",
                    "data": "switch-to-family-main"
                }
            }
        ]
    }"""

    rich_menu_management_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_management_str)
    ).rich_menu_id

    print(f"family_management_id: {rich_menu_management_id}")

    response = requests.get(f"{base_url}/family_management_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_management_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="family_management",
            rich_menu_id=rich_menu_management_id
        )
    )

    # ============================== 藥物管理 ==============================
    rich_menu_medication_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "家屬藥物管理",
        "chatBarText": "返回主選單",
        "areas": [
            {
                "bounds": {
                    "x": 1663,
                    "y": 843,
                    "width": 837,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_main",
                    "data": "switch-to-family-main"
                }
            }
        ]
    }"""

    rich_menu_medication_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_medication_str)
    ).rich_menu_id

    print(f"family_medication_id: {rich_menu_medication_id}")

    response = requests.get(f"{base_url}/family_medication_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_medication_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="family_medication",
            rich_menu_id=rich_menu_medication_id
        )
    )

    # ============================== 行事曆 ==============================
    rich_menu_calendar_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "家屬行事曆",
        "chatBarText": "返回主選單",
        "areas": [
            {
                "bounds": {
                    "x": 1663,
                    "y": 843,
                    "width": 837,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_main",
                    "data": "switch-to-family-main"
                }
            }
        ]
    }"""

    rich_menu_calendar_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_calendar_str)
    ).rich_menu_id

    print(f"family_calendar_id: {rich_menu_calendar_id}")

    response = requests.get(f"{base_url}/family_calendar_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_calendar_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="family_calendar",
            rich_menu_id=rich_menu_calendar_id
        )
    )

    # ============================== 報告紀錄 ==============================
    rich_menu_report_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "家屬報告紀錄",
        "chatBarText": "返回主選單",
        "areas": [
            {
                "bounds": {
                    "x": 1663,
                    "y": 843,
                    "width": 837,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_main",
                    "data": "switch-to-family-main"
                }
            }
        ]
    }"""

    rich_menu_report_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_report_str)
    ).rich_menu_id

    print(f"family_report_id: {rich_menu_report_id}")

    response = requests.get(f"{base_url}/family_report_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_report_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="family_report",
            rich_menu_id=rich_menu_report_id
        )
    )

    # ============================== 系統設定 ==============================
    rich_menu_settings_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "家屬系統設定",
        "chatBarText": "返回主選單",
        "areas": [
            {
                "bounds": {
                    "x": 1663,
                    "y": 843,
                    "width": 837,
                    "height": 843
                },
                "action": {
                    "type": "richmenuswitch",
                    "richMenuAliasId": "family_main",
                    "data": "switch-to-family-main"
                }
            }
        ]
    }"""

    rich_menu_settings_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_settings_str)
    ).rich_menu_id

    print(f"family_settings_id: {rich_menu_settings_id}")

    response = requests.get(f"{base_url}/family_settings_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_settings_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="family_settings",
            rich_menu_id=rich_menu_settings_id
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

    print("家屬 Rich Menu 建立完成")
    print(f"family_main_id: {rich_menu_main_id}")
