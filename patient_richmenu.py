import os

from richmenu_common import create_rich_menu_set


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "static", "paitent")


MENU_DEFINITIONS = {
    "main": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者主選單",
            "chatBarText": "查看更多資訊",
            "areas": [
                {
                    "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_today_medication",
                        "data": "switch-to-elder-today-medication",
                    },
                },
                {
                    "bounds": {"x": 834, "y": 0, "width": 833, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_my_medication",
                        "data": "switch-to-elder-my-medication",
                    },
                },
                {
                    "bounds": {"x": 1663, "y": 0, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_medication_report",
                        "data": "switch-to-elder-medication-report",
                    },
                },
                {
                    "bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_discomfort",
                        "data": "switch-to-elder-discomfort",
                    },
                },
                {
                    "bounds": {"x": 834, "y": 843, "width": 833, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_calendar",
                        "data": "switch-to-elder-calendar",
                    },
                },
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_sos",
                        "data": "switch-to-elder-sos",
                    },
                },
            ],
        },
        "image": "elder_main_menu.jpg",
        "alias": "elder_main",
    },
    "today_medication": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者今日用藥",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_main",
                        "data": "switch-to-elder-main",
                    },
                }
            ],
        },
        "image": "elder_today_medication_menu.jpg",
        "alias": "elder_today_medication",
    },
    "my_medication": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者我的藥物",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_main",
                        "data": "switch-to-elder-main",
                    },
                }
            ],
        },
        "image": "elder_my_medication_menu.jpg",
        "alias": "elder_my_medication",
    },
    "medication_report": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者用藥回報",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_main",
                        "data": "switch-to-elder-main",
                    },
                }
            ],
        },
        "image": "elder_medication_report_menu.jpg",
        "alias": "elder_medication_report",
    },
    "discomfort": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者身體不適",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_main",
                        "data": "switch-to-elder-main",
                    },
                }
            ],
        },
        "image": "elder_discomfort_menu.jpg",
        "alias": "elder_discomfort",
    },
    "calendar": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者行事曆",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_main",
                        "data": "switch-to-elder-main",
                    },
                }
            ],
        },
        "image": "elder_calendar_menu.jpg",
        "alias": "elder_calendar",
    },
    "sos": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者SOS",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_main",
                        "data": "switch-to-elder-main",
                    },
                }
            ],
        },
        "image": "elder_sos_menu.jpg",
        "alias": "elder_sos",
    },
}


def create_patient_richmenus():
    menu_ids = create_rich_menu_set(
        role_name="elderly",
        image_dir=IMAGE_DIR,
        menu_definitions=MENU_DEFINITIONS,
    )

    return {
        "role": "elderly",
        "home_rich_menu_id": menu_ids["main"],
        "menus": menu_ids,
        "aliases": {
            key: value["alias"]
            for key, value in MENU_DEFINITIONS.items()
        },
    }


if __name__ == "__main__":
    result = create_patient_richmenus()
    print(result)
