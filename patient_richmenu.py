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
                    "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "早餐藥物",
                        "data": "action=elder_today_breakfast",
                        "displayText": "早餐藥物",
                    },
                },
                {
                    "bounds": {"x": 834, "y": 0, "width": 833, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "午餐藥物",
                        "data": "action=elder_today_lunch",
                        "displayText": "午餐藥物",
                    },
                },
                {
                    "bounds": {"x": 1663, "y": 0, "width": 837, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "晚餐藥物",
                        "data": "action=elder_today_dinner",
                        "displayText": "晚餐藥物",
                    },
                },
                {
                    "bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "睡前藥物",
                        "data": "action=elder_today_bedtime",
                        "displayText": "睡前藥物",
                    },
                },
                {
                    "bounds": {"x": 834, "y": 843, "width": 833, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "今日全部",
                        "data": "action=elder_today_all",
                        "displayText": "今日全部",
                    },
                },
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_main",
                        "data": "switch-to-elder-main",
                    },
                },
            ],
        },
        "image": "elder_today_medication_menu.jpg",
        "alias": "elder_today_medication",
    },
    "my_medication": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者我已服藥",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "早餐已服",
                        "data": "action=elder_taken_breakfast",
                        "displayText": "早餐已服",
                    },
                },
                {
                    "bounds": {"x": 834, "y": 0, "width": 833, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "午餐已服",
                        "data": "action=elder_taken_lunch",
                        "displayText": "午餐已服",
                    },
                },
                {
                    "bounds": {"x": 1663, "y": 0, "width": 837, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "晚餐已服",
                        "data": "action=elder_taken_dinner",
                        "displayText": "晚餐已服",
                    },
                },
                {
                    "bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "睡前已服",
                        "data": "action=elder_taken_bedtime",
                        "displayText": "睡前已服",
                    },
                },
                {
                    "bounds": {"x": 834, "y": 843, "width": 833, "height": 843},
                    "action": {
                        "type": "postback",
                        "label": "今日紀錄",
                        "data": "action=elder_taken_today",
                        "displayText": "今日紀錄",
                    },
                },
                {
                    "bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "elder_main",
                        "data": "switch-to-elder-main",
                    },
                },
            ],
        },
        "image": "elder_my_medication_menu.jpg",
        "alias": "elder_my_medication",
    },
    "medication_report": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "長者我的藥物",
            "chatBarText": "返回主選單",
            "areas": [
                {"bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "開藥清單",
                            "data": "action=elder_medicine_list",
                            "displayText": "開藥清單"}},
                {"bounds": {"x": 834, "y": 0, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "藥物說明",
                            "data": "action=elder_medicine_info",
                            "displayText": "藥物說明"}},
                {"bounds": {"x": 1663, "y": 0, "width": 837, "height": 843},
                 "action": {"type": "postback", "label": "藥量剩餘",
                            "data": "action=elder_medicine_remaining",
                            "displayText": "藥量剩餘"}},
                {"bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "拍攝藥單",
                            "data": "action=elder_medicine_capture",
                            "displayText": "拍攝藥單"}},
                {"bounds": {"x": 834, "y": 843, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "停用藥物",
                            "data": "action=elder_medicine_stop",
                            "displayText": "停用藥物"}},
                {"bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                 "action": {"type": "richmenuswitch",
                            "richMenuAliasId": "elder_main",
                            "data": "switch-to-elder-main"}},
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
                {"bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "頭暈",
                            "data": "action=elder_discomfort_dizziness",
                            "displayText": "頭暈"}},
                {"bounds": {"x": 834, "y": 0, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "頭痛",
                            "data": "action=elder_discomfort_headache",
                            "displayText": "頭痛"}},
                {"bounds": {"x": 1663, "y": 0, "width": 837, "height": 843},
                 "action": {"type": "postback", "label": "想吐",
                            "data": "action=elder_discomfort_nausea",
                            "displayText": "想吐"}},
                {"bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "睡不好",
                            "data": "action=elder_discomfort_sleep",
                            "displayText": "睡不好"}},
                {"bounds": {"x": 834, "y": 843, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "其他問題",
                            "data": "action=elder_discomfort_other",
                            "displayText": "其他問題"}},
                {"bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                 "action": {"type": "richmenuswitch",
                            "richMenuAliasId": "elder_main",
                            "data": "switch-to-elder-main"}},
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
                {"bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "查看行事曆",
                            "data": "action=elder_calendar_view",
                            "displayText": "查看行事曆"}},
                {"bounds": {"x": 834, "y": 0, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "新增行程",
                            "data": "action=elder_calendar_add",
                            "displayText": "新增行程"}},
                {"bounds": {"x": 1663, "y": 0, "width": 837, "height": 843},
                 "action": {"type": "postback", "label": "修改行程",
                            "data": "action=elder_calendar_edit",
                            "displayText": "修改行程"}},
                {"bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "刪除行程",
                            "data": "action=elder_calendar_delete",
                            "displayText": "刪除行程"}},
                {"bounds": {"x": 834, "y": 843, "width": 833, "height": 843},
                 "action": {"type": "postback", "label": "回診提醒",
                            "data": "action=elder_calendar_reminder",
                            "displayText": "回診提醒"}},
                {"bounds": {"x": 1663, "y": 843, "width": 837, "height": 843},
                 "action": {"type": "richmenuswitch",
                            "richMenuAliasId": "elder_main",
                            "data": "switch-to-elder-main"}},
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
                {"bounds": {"x": 0, "y": 0, "width": 1250, "height": 843},
                 "action": {"type": "postback", "label": "緊急聯絡人1",
                            "data": "action=elder_sos_contact1",
                            "displayText": "緊急聯絡人1"}},
                {"bounds": {"x": 1250, "y": 0, "width": 1250, "height": 843},
                 "action": {"type": "postback", "label": "緊急聯絡人2",
                            "data": "action=elder_sos_contact2",
                            "displayText": "緊急聯絡人2"}},
                {"bounds": {"x": 0, "y": 843, "width": 1250, "height": 843},
                 "action": {"type": "postback", "label": "通知全部",
                            "data": "action=elder_sos_notify_all",
                            "displayText": "通知全部"}},
                {"bounds": {"x": 1250, "y": 843, "width": 1250, "height": 843},
                 "action": {"type": "richmenuswitch",
                            "richMenuAliasId": "elder_main",
                            "data": "switch-to-elder-main"}},
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
