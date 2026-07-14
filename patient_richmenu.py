import os

from richmenu_common import create_rich_menu_set


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def find_patient_image_dir():
    target_image = "elder_main_menu.jpg"
    matched_dirs = []

    if not os.path.isdir(STATIC_DIR):
        raise FileNotFoundError(
            f"找不到 static 資料夾：{STATIC_DIR}"
        )

    for current_dir, _, filenames in os.walk(STATIC_DIR):
        if target_image in filenames:
            matched_dirs.append(current_dir)

    if not matched_dirs:
        raise FileNotFoundError(
            "在 static 資料夾內找不到 "
            f"{target_image}。\n"
            "請確認長者圖片已提交到 GitHub，"
            "並且 Render 已重新部署最新版本。"
        )

    if len(matched_dirs) > 1:
        raise RuntimeError(
            "找到多個長者圖片資料夾，無法判斷應使用哪一個：\n- "
            + "\n- ".join(matched_dirs)
        )

    selected_dir = matched_dirs[0]

    required_images = [
        "elder_main_menu.jpg",
        "elder_today_medication_menu.jpg",
        "elder_my_medication_menu.jpg",
        "elder_medication_report_menu.jpg",
        "elder_discomfort_menu.jpg",
        "elder_calendar_menu.jpg",
        "elder_sos_menu.jpg",
    ]

    missing_images = [
        filename
        for filename in required_images
        if not os.path.isfile(
            os.path.join(selected_dir, filename)
        )
    ]

    if missing_images:
        raise FileNotFoundError(
            f"長者圖片資料夾：{selected_dir}\n"
            "但缺少以下圖片：\n- "
            + "\n- ".join(missing_images)
        )

    print(f"[elderly] 使用圖片資料夾：{selected_dir}")
    return selected_dir


IMAGE_DIR = find_patient_image_dir()


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
