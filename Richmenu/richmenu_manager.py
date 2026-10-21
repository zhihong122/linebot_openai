import argparse
import json
import os

from family_richmenu import create_family_richmenus
from patient_richmenu import create_patient_richmenus
from caregiver_richmenu import create_caregiver_richmenus


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RICHMENU_ID_FILE = os.path.join(BASE_DIR, "richmenu_ids.json")

BUILDERS = {
    "family": create_family_richmenus,
    "elderly": create_patient_richmenus,
    "caregiver": create_caregiver_richmenus,
}


def load_richmenu_ids():
    if not os.path.exists(RICHMENU_ID_FILE):
        return {}

    with open(RICHMENU_ID_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_richmenu_ids(data):
    with open(RICHMENU_ID_FILE, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def create_richmenus(selected_roles):
    results = load_richmenu_ids()

    for role in selected_roles:
        print(f"\n===== 開始建立 {role} Rich Menu =====")
        role_result = BUILDERS[role]()
        results[role] = role_result

        # 每完成一個身份就立即保存，後面失敗也不會遺失前面的 ID。
        save_richmenu_ids(results)

        print(
            f"===== {role} 完成，首頁 ID："
            f"{role_result['home_rich_menu_id']} ====="
        )

    return results


def get_home_rich_menu_id(role):
    data = load_richmenu_ids()
    return data.get(role, {}).get("home_rich_menu_id")


def parse_args():
    parser = argparse.ArgumentParser(
        description="建立或更新指定身份的 LINE Rich Menu"
    )
    parser.add_argument(
        "role",
        nargs="?",
        choices=["all", "family", "elderly", "caregiver"],
        default="all",
        help=(
            "all=全部；family=家屬；"
            "elderly=長者；caregiver=看護"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    roles = (
        ["family", "elderly", "caregiver"]
        if args.role == "all"
        else [args.role]
    )

    result = create_richmenus(roles)

    print(
        "\n===== 建立結果 =====\n"
        + json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
