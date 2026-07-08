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
    base_url = "https://raw.githubusercontent.com/zhihong122/linebot_openai/master/static/patient"

    # ============================== 長者主選單 ==============================
    rich_menu_main_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "長者主選單",
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
                    "richMenuAliasId": "elder_today_medication",
                    "data": "switch-to-elder-today-medication"
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
                    "richMenuAliasId": "elder_my_medication",
                    "data": "switch-to-elder-my-medication"
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
                    "richMenuAliasId": "elder_medication_report",
                    "data": "switch-to-elder-medication-report"
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
                    "richMenuAliasId": "elder_discomfort",
                    "data": "switch-to-elder-discomfort"
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
                    "richMenuAliasId": "elder_calendar",
                    "data": "switch-to-elder-calendar"
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
                    "richMenuAliasId": "elder_sos",
                    "data": "switch-to-elder-sos"
                }
            }
        ]
    }"""

    rich_menu_main_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_main_str)
    ).rich_menu_id

    print(f"elder_main_id: {rich_menu_main_id}")

    response = requests.get(f"{base_url}/elder_main_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_main_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="elder_main",
            rich_menu_id=rich_menu_main_id
        )
    )

    # ============================== 今日用藥 ==============================
    rich_menu_today_medication_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "長者今日用藥",
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
                    "richMenuAliasId": "elder_main",
                    "data": "switch-to-elder-main"
                }
            }
        ]
    }"""

    rich_menu_today_medication_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_today_medication_str)
    ).rich_menu_id

    print(f"elder_today_medication_id: {rich_menu_today_medication_id}")

    response = requests.get(f"{base_url}/elder_today_medication_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_today_medication_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="elder_today_medication",
            rich_menu_id=rich_menu_today_medication_id
        )
    )

    # ============================== 我的藥物 ==============================
    rich_menu_my_medication_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "長者我的藥物",
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
                    "richMenuAliasId": "elder_main",
                    "data": "switch-to-elder-main"
                }
            }
        ]
    }"""

    rich_menu_my_medication_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_my_medication_str)
    ).rich_menu_id

    print(f"elder_my_medication_id: {rich_menu_my_medication_id}")

    response = requests.get(f"{base_url}/elder_my_medication_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_my_medication_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="elder_my_medication",
            rich_menu_id=rich_menu_my_medication_id
        )
    )

    # ============================== 用藥回報 ==============================
    rich_menu_medication_report_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "長者用藥回報",
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
                    "richMenuAliasId": "elder_main",
                    "data": "switch-to-elder-main"
                }
            }
        ]
    }"""

    rich_menu_medication_report_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_medication_report_str)
    ).rich_menu_id

    print(f"elder_medication_report_id: {rich_menu_medication_report_id}")

    response = requests.get(f"{base_url}/elder_medication_report_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_medication_report_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="elder_medication_report",
            rich_menu_id=rich_menu_medication_report_id
        )
    )

    # ============================== 身體不適 ==============================
    rich_menu_discomfort_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "長者身體不適",
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
                    "richMenuAliasId": "elder_main",
                    "data": "switch-to-elder-main"
                }
            }
        ]
    }"""

    rich_menu_discomfort_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_discomfort_str)
    ).rich_menu_id

    print(f"elder_discomfort_id: {rich_menu_discomfort_id}")

    response = requests.get(f"{base_url}/elder_discomfort_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_discomfort_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="elder_discomfort",
            rich_menu_id=rich_menu_discomfort_id
        )
    )

    # ============================== 行事曆 ==============================
    rich_menu_calendar_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "長者行事曆",
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
                    "richMenuAliasId": "elder_main",
                    "data": "switch-to-elder-main"
                }
            }
        ]
    }"""

    rich_menu_calendar_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_calendar_str)
    ).rich_menu_id

    print(f"elder_calendar_id: {rich_menu_calendar_id}")

    response = requests.get(f"{base_url}/elder_calendar_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_calendar_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="elder_calendar",
            rich_menu_id=rich_menu_calendar_id
        )
    )

    # ============================== SOS ==============================
    rich_menu_sos_str = """{
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": true,
        "name": "長者SOS",
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
                    "richMenuAliasId": "elder_main",
                    "data": "switch-to-elder-main"
                }
            }
        ]
    }"""

    rich_menu_sos_id = line_bot_api.create_rich_menu(
        rich_menu_request=RichMenuRequest.from_json(rich_menu_sos_str)
    ).rich_menu_id

    print(f"elder_sos_id: {rich_menu_sos_id}")

    response = requests.get(f"{base_url}/elder_sos_menu.png")
    line_bot_blob_api.set_rich_menu_image(
        rich_menu_id=rich_menu_sos_id,
        body=response.content,
        _headers={'Content-Type': 'image/png'}
    )

    line_bot_api.create_rich_menu_alias(
        CreateRichMenuAliasRequest(
            rich_menu_alias_id="elder_sos",
            rich_menu_id=rich_menu_sos_id
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

    print("長者 Rich Menu 建立完成")
    print(f"elder_main_id: {rich_menu_main_id}")
