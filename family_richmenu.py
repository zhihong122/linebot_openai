import os

from richmenu_common import create_rich_menu_set


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "static", *"family".split("/"))


MENU_DEFINITIONS = {
    "main": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "家屬主選單",
            "chatBarText": "查看更多資訊",
            "areas": [
                {
                    "bounds": {"x": 35, "y": 251, "width": 798, "height": 665},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_monitoring",
                        "data": "switch-to-family-monitoring",
                    },
                },
                {
                    "bounds": {"x": 855, "y": 251, "width": 827, "height": 671},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_management",
                        "data": "switch-to-family-management",
                    },
                },
                {
                    "bounds": {"x": 1701, "y": 254, "width": 772, "height": 665},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_medication",
                        "data": "switch-to-family-medication",
                    },
                },
                {
                    "bounds": {"x": 38, "y": 935, "width": 792, "height": 740},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_calendar",
                        "data": "switch-to-family-calendar",
                    },
                },
                {
                    "bounds": {"x": 852, "y": 941, "width": 826, "height": 741},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_report",
                        "data": "switch-to-family-report",
                    },
                },
                {
                    "bounds": {"x": 1698, "y": 935, "width": 775, "height": 744},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_settings",
                        "data": "switch-to-family-settings",
                    },
                },
            ],
        },
        "image": "family_main_menu.jpg",
        "alias": "family_main",
    },
    "monitoring": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "家屬監控中心",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1698, "y": 935, "width": 775, "height": 744},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_main",
                        "data": "switch-to-family-main",
                    },
                }
            ],
        },
        "image": "family_monitoring_menu.jpg",
        "alias": "family_monitoring",
    },
    "management": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "家屬家庭管理",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 35, "y": 251, "width": 798, "height": 665},
                    "action": {
                        "type": "postback",
                        "label": "新增長者",
                        "data": "action=family_add_elder",
                        "displayText": "新增長者",
                    },
                },
                {
                    "bounds": {"x": 855, "y": 251, "width": 827, "height": 671},
                    "action": {
                        "type": "postback",
                        "label": "管理長者",
                        "data": "action=family_manage_elder",
                        "displayText": "管理長者",
                    },
                },
                {
                    "bounds": {"x": 1701, "y": 254, "width": 772, "height": 665},
                    "action": {
                        "type": "postback",
                        "label": "新增看護",
                        "data": "action=family_add_caregiver",
                        "displayText": "新增看護",
                    },
                },
                {
                    "bounds": {"x": 38, "y": 935, "width": 792, "height": 740},
                    "action": {
                        "type": "postback",
                        "label": "指派看護",
                        "data": "action=family_assign_caregiver",
                        "displayText": "指派看護",
                    },
                },
                {
                    "bounds": {"x": 852, "y": 941, "width": 826, "height": 741},
                    "action": {
                        "type": "postback",
                        "label": "家庭群組 ID",
                        "data": "action=family_bind_group",
                        "displayText": "家庭群組 ID",
                    },
                },
                {
                    "bounds": {"x": 1698, "y": 935, "width": 775, "height": 744},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_main",
                        "data": "switch-to-family-main",
                    },
                },
            ],
        },
        "image": "family_management_menu.jpg",
        "alias": "family_management",
    },
    "medication": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "家屬藥物管理",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1698, "y": 935, "width": 775, "height": 744},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_main",
                        "data": "switch-to-family-main",
                    },
                }
            ],
        },
        "image": "family_medication_menu.jpg",
        "alias": "family_medication",
    },
    "calendar": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "家屬行事曆",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1698, "y": 935, "width": 775, "height": 744},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_main",
                        "data": "switch-to-family-main",
                    },
                }
            ],
        },
        "image": "family_calendar_menu.jpg",
        "alias": "family_calendar",
    },
    "report": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "家屬報告紀錄",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1698, "y": 935, "width": 775, "height": 744},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_main",
                        "data": "switch-to-family-main",
                    },
                }
            ],
        },
        "image": "family_report_menu.jpg",
        "alias": "family_report",
    },
    "settings": {
        "menu": {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "家屬系統設定",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {"x": 1698, "y": 935, "width": 775, "height": 744},
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "family_main",
                        "data": "switch-to-family-main",
                    },
                }
            ],
        },
        "image": "family_settings_menu.jpg",
        "alias": "family_settings",
    },
}


def create_family_richmenus():
    menu_ids = create_rich_menu_set(
        role_name="family",
        image_dir=IMAGE_DIR,
        menu_definitions=MENU_DEFINITIONS,
    )

    return {
        "role": "family",
        "home_rich_menu_id": menu_ids["main"],
        "menus": menu_ids,
        "aliases": {
            key: value["alias"]
            for key, value in MENU_DEFINITIONS.items()
        },
    }


if __name__ == "__main__":
    result = create_family_richmenus()
    print(result)
