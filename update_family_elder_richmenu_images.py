import os
import time
import requests


# =========================================================
# LINE 設定
# =========================================================

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("缺少 CHANNEL_ACCESS_TOKEN")


# =========================================================
# GitHub Raw 圖片位置
# =========================================================

GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "zhihong122/linebot_openai/master/static"
)


# =========================================================
# Rich Menu Alias 與圖片對應
# =========================================================

RICH_MENU_GROUPS = {
    "家屬": {
        "image_base_url": f"{GITHUB_RAW_BASE}/family",
        "menus": {
            "family_main": "family_main_menu.png",
            "family_monitoring": "family_monitoring_menu.png",
            "family_management": "family_management_menu.png",
            "family_medication": "family_medication_menu.png",
            "family_calendar": "family_calendar_menu.png",
            "family_report": "family_report_menu.png",
            "family_settings": "family_settings_menu.png",
        },
    },
    "長者": {
        "image_base_url": f"{GITHUB_RAW_BASE}/paitent",
        "menus": {
            "elder_main": "elder_main_menu.png",
            "elder_today_medication": "elder_today_medication_menu.png",
            "elder_my_medication": "elder_my_medication_menu.png",
            "elder_medication_report": "elder_medication_report_menu.png",
            "elder_discomfort": "elder_discomfort_menu.png",
            "elder_calendar": "elder_calendar_menu.png",
            "elder_sos": "elder_sos_menu.png",
        },
    },
}


# =========================================================
# LINE API
# =========================================================

LINE_API_BASE = "https://api.line.me/v2/bot"
LINE_DATA_API_BASE = "https://api-data.line.me/v2/bot"

AUTH_HEADERS = {
    "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
}


# =========================================================
# 共用函式
# =========================================================

def get_rich_menu_id_by_alias(alias_id: str) -> str:
    url = f"{LINE_API_BASE}/richmenu/alias/{alias_id}"

    response = requests.get(
        url,
        headers=AUTH_HEADERS,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"取得 Alias 失敗：alias={alias_id}，"
            f"HTTP {response.status_code}，{response.text}"
        )

    data = response.json()
    rich_menu_id = data.get("richMenuId")

    if not rich_menu_id:
        raise RuntimeError(
            f"Alias {alias_id} 沒有回傳 richMenuId"
        )

    return rich_menu_id


def download_image(
    image_base_url: str,
    image_filename: str,
):
    image_url = (
        f"{image_base_url}/{image_filename}"
        f"?update={int(time.time())}"
    )

    response = requests.get(
        image_url,
        timeout=60,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"圖片下載失敗：{image_filename}，"
            f"HTTP {response.status_code}，"
            f"URL={image_url}"
        )

    image_content = response.content
    returned_content_type = response.headers.get(
        "Content-Type",
        ""
    ).split(";")[0].strip().lower()

    if image_filename.lower().endswith(".png"):
        expected_content_type = "image/png"
    elif image_filename.lower().endswith(
        (".jpg", ".jpeg")
    ):
        expected_content_type = "image/jpeg"
    else:
        raise ValueError(
            f"不支援的圖片格式：{image_filename}"
        )

    if not returned_content_type.startswith("image/"):
        raise RuntimeError(
            f"下載內容不是圖片：{image_filename}，"
            f"Content-Type={returned_content_type}"
        )

    image_size = len(image_content)

    if image_size == 0:
        raise RuntimeError(
            f"圖片內容為空：{image_filename}"
        )

    if image_size > 1024 * 1024:
        raise RuntimeError(
            f"圖片超過 LINE 1 MB 限制："
            f"{image_filename}，"
            f"{image_size / 1024 / 1024:.2f} MB"
        )

    print(
        f"圖片下載成功：{image_filename} "
        f"({image_size / 1024:.1f} KB)"
    )

    return image_content, expected_content_type


def upload_rich_menu_image(
    rich_menu_id: str,
    image_base_url: str,
    image_filename: str,
):
    image_content, content_type = download_image(
        image_base_url=image_base_url,
        image_filename=image_filename,
    )

    url = (
        f"{LINE_DATA_API_BASE}/richmenu/"
        f"{rich_menu_id}/content"
    )

    headers = {
        **AUTH_HEADERS,
        "Content-Type": content_type,
    }

    response = requests.post(
        url,
        headers=headers,
        data=image_content,
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"圖片上傳失敗："
            f"rich_menu_id={rich_menu_id}，"
            f"HTTP {response.status_code}，"
            f"{response.text}"
        )

    print(
        f"圖片更新成功："
        f"{image_filename} -> {rich_menu_id}"
    )


# =========================================================
# 更新單一身份
# =========================================================

def update_group(
    group_name: str,
    image_base_url: str,
    menus: dict,
):
    print()
    print("=" * 70)
    print(f"開始更新：{group_name}")
    print(f"圖片路徑：{image_base_url}")
    print("=" * 70)

    success_count = 0
    failed_items = []

    for alias_id, image_filename in menus.items():
        print()
        print("-" * 70)
        print(f"身份：{group_name}")
        print(f"Alias：{alias_id}")
        print(f"圖片：{image_filename}")

        try:
            rich_menu_id = get_rich_menu_id_by_alias(
                alias_id
            )

            print(
                f"目前 Rich Menu ID：{rich_menu_id}"
            )

            upload_rich_menu_image(
                rich_menu_id=rich_menu_id,
                image_base_url=image_base_url,
                image_filename=image_filename,
            )

            success_count += 1

        except Exception as error:
            failed_items.append(
                {
                    "group": group_name,
                    "alias": alias_id,
                    "image": image_filename,
                    "error": str(error),
                }
            )

            print(
                f"更新失敗：{alias_id}\n"
                f"原因：{error}"
            )

    return success_count, failed_items


# =========================================================
# 主程式
# =========================================================

def main():
    print("=" * 70)
    print("家屬＋長者 Rich Menu 圖片更新程式")
    print("不會建立新的 Rich Menu")
    print("不會更改 Alias")
    print("不會更改 Rich Menu ID")
    print("不會更改 Default 或使用者綁定")
    print("=" * 70)

    total_success = 0
    all_failed_items = []

    for group_name, group_config in RICH_MENU_GROUPS.items():
        success_count, failed_items = update_group(
            group_name=group_name,
            image_base_url=group_config["image_base_url"],
            menus=group_config["menus"],
        )

        total_success += success_count
        all_failed_items.extend(failed_items)

    print()
    print("=" * 70)
    print(
        f"全部更新完成：成功 {total_success} 個，"
        f"失敗 {len(all_failed_items)} 個"
    )

    if all_failed_items:
        print()
        print("失敗項目：")

        for item in all_failed_items:
            print(
                f"- {item['group']} / "
                f"{item['alias']} / "
                f"{item['image']}\n"
                f"  {item['error']}"
            )

        raise RuntimeError(
            "部分 Rich Menu 圖片更新失敗，"
            "請查看上方錯誤訊息。"
        )

    print("家屬與長者 Rich Menu 圖片全部更新成功。")
    print("原本的 Rich Menu ID、Alias 與綁定均保持不變。")
    print("=" * 70)


if __name__ == "__main__":
    main()
