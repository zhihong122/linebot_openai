from richmenu_common import create_rich_menu_set


BASE_URL = (
    "https://raw.githubusercontent.com/"
    "zhihong122/linebot_openai/master/static/caregiver"
)


MENU_DEFINITIONS = {
    "main": {
        "menu": {
            "size": {
                "width": 2500,
                "height": 1686,
            },
            "selected": True,
            "name": "看護患者選擇",
            "chatBarText": "查看更多資訊",
            "areas": [
                {
                    "bounds": {
                        "x": 0,
                        "y": 0,
                        "width": 833,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "caregiver_patient1_main",
                        "data": "switch-to-caregiver-patient1-main",
                    },
                },
                {
                    "bounds": {
                        "x": 1663,
                        "y": 0,
                        "width": 837,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "caregiver_sos_contact",
                        "data": "switch-to-caregiver-sos-contact",
                    },
                },
            ],
        },
        "image": "caregiver_patient_selector_menu.jpg",
        "alias": "caregiver_main",
    },

    "patient1_main": {
        "menu": {
            "size": {
                "width": 2500,
                "height": 1686,
            },
            "selected": True,
            "name": "看護患者1主選單",
            "chatBarText": "查看更多資訊",
            "areas": [
                {
                    "bounds": {
                        "x": 0,
                        "y": 0,
                        "width": 833,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": (
                            "caregiver_patient1_today_tasks"
                        ),
                        "data": (
                            "switch-to-caregiver-patient1-today-tasks"
                        ),
                    },
                },
                {
                    "bounds": {
                        "x": 834,
                        "y": 0,
                        "width": 833,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": (
                            "caregiver_patient1_checklist"
                        ),
                        "data": (
                            "switch-to-caregiver-patient1-checklist"
                        ),
                    },
                },
                {
                    "bounds": {
                        "x": 834,
                        "y": 843,
                        "width": 833,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": (
                            "caregiver_patient1_report_issue"
                        ),
                        "data": (
                            "switch-to-caregiver-patient1-report-issue"
                        ),
                    },
                },
                {
                    "bounds": {
                        "x": 1663,
                        "y": 843,
                        "width": 837,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "caregiver_main",
                        "data": "switch-to-caregiver-main",
                    },
                },
            ],
        },
        "image": "caregiver_patient1_main_menu.jpg",
        "alias": "caregiver_patient1_main",
    },

    "patient1_today_tasks": {
        "menu": {
            "size": {
                "width": 2500,
                "height": 1686,
            },
            "selected": True,
            "name": "看護患者1今日任務",
            "chatBarText": "返回患者1",
            "areas": [
                {
                    "bounds": {
                        "x": 1663,
                        "y": 843,
                        "width": 837,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "caregiver_patient1_main",
                        "data": "switch-to-caregiver-patient1-main",
                    },
                },
            ],
        },
        "image": "caregiver_patient1_today_tasks_menu.jpg",
        "alias": "caregiver_patient1_today_tasks",
    },

    "patient1_checklist": {
        "menu": {
            "size": {
                "width": 2500,
                "height": 1686,
            },
            "selected": True,
            "name": "看護患者1 Checklist",
            "chatBarText": "返回患者1",
            "areas": [
                {
                    "bounds": {
                        "x": 1663,
                        "y": 843,
                        "width": 837,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "caregiver_patient1_main",
                        "data": "switch-to-caregiver-patient1-main",
                    },
                },
            ],
        },
        "image": "caregiver_patient1_checklist_menu.jpg",
        "alias": "caregiver_patient1_checklist",
    },

    "patient1_report_issue": {
        "menu": {
            "size": {
                "width": 2500,
                "height": 1686,
            },
            "selected": True,
            "name": "看護患者1異常回報",
            "chatBarText": "返回患者1",
            "areas": [
                {
                    "bounds": {
                        "x": 1663,
                        "y": 843,
                        "width": 837,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "caregiver_patient1_main",
                        "data": "switch-to-caregiver-patient1-main",
                    },
                },
            ],
        },
        "image": "caregiver_patient1_report_issue_menu.jpg",
        "alias": "caregiver_patient1_report_issue",
    },

    "sos_contact": {
        "menu": {
            "size": {
                "width": 2500,
                "height": 1686,
            },
            "selected": True,
            "name": "看護SOS聯絡",
            "chatBarText": "返回主選單",
            "areas": [
                {
                    "bounds": {
                        "x": 1663,
                        "y": 843,
                        "width": 837,
                        "height": 843,
                    },
                    "action": {
                        "type": "richmenuswitch",
                        "richMenuAliasId": "caregiver_main",
                        "data": "switch-to-caregiver-main",
                    },
                },
            ],
        },
        "image": "caregiver_sos_contact_menu.jpg",
        "alias": "caregiver_sos_contact",
    },
}


def create_caregiver_richmenus():
    menu_ids = create_rich_menu_set(
        role_name="caregiver",
        base_url=BASE_URL,
        menu_definitions=MENU_DEFINITIONS,
    )

    return {
        "role": "caregiver",
        "home_rich_menu_id": menu_ids["main"],
        "menus": menu_ids,
        "aliases": {
            key: value["alias"]
            for key, value in MENU_DEFINITIONS.items()
        },
    }


if __name__ == "__main__":
    result = create_caregiver_richmenus()
    print(result)
