import json
import os
from pathlib import Path

import requests


# =========================================================
# 基本設定
# =========================================================

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

if not CHANNEL_ACCESS_TOKEN:
    raise RuntimeError("缺少環境變數 CHANNEL_ACCESS_TOKEN")

BASE_DIR = Path(__file__).resolve().parent

LINE_API_BASE = "https://api.line.me/v2/bot"
LINE_DATA_API_BASE = "https://api-data.line.me/v2/bot"

AUTH_HEADERS = {
    "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
}


# =========================================================
# Alias 與本地 JPG 圖片
# =========================================================

MENU_IMAGES = {
    # 家屬
    "family_main": BASE_DIR / "static" / "family" / "family_main_menu.jpg",
    "family_monitoring": BASE_DIR / "static" / "family" / "family_monitoring_menu.jpg",
    "family_management": BASE_DIR / "static" / "family" / "family_management_menu.jpg",
    "family_medication": BASE_DIR / "static" / "family" / "family_medication_menu.jpg",
    "family_calendar": BASE_DIR / "static" / "family" / "family_calendar_menu.jpg",
    "family_report": BASE_DIR / "static" / "family" / "family_report_menu.jpg",
    "family_settings": BASE_DIR / "static" / "family" / "family_settings_menu.jpg",

    # 長者
    "elder_main": BASE_DIR / "static" / "paitent" / "elder_main_menu.jpg",
    "elder_today_medication": BASE_DIR / "static" / "paitent" / "elder_today_medication_menu.jpg",
    "elder_my_medication": BASE_DIR / "static" / "paitent" / "elder_my_medication_menu.jpg",
    "elder_medication_report": BASE_DIR / "static" / "paitent" / "elder_medication_report_menu.jpg",
    "elder_discomfort": BASE_DIR / "static" / "paitent" / "elder_discomfort_menu.jpg",
    "elder_calendar": BASE_DIR / "static" / "paitent" / "elder_calendar_menu.jpg",
    "elder_sos": BASE_DIR / "static" / "paitent" / "elder_sos_menu.jpg",
}


# =========================================================
# HTTP 共用
# =========================================================

def require_success(response: requests.Response, action: str) -> None:
    if 200 <= response.status_code < 300:
        return

    raise RuntimeError(
        f"{action}失敗：HTTP {response.status_code}\n"
        f"{response.text}"
    )


# =========================================================
# LINE Rich Menu API
# =========================================================

def get_alias_target(alias_id: str) -> str:
    response = requests.get(
        f"{LINE_API_BASE}/richmenu/alias/{alias_id}",
        headers=AUTH_HEADERS,
        timeout=30,
    )
    require_success(response, f"取得 Alias {alias_id}")

    rich_menu_id = response.json().get("richMenuId")

    if not rich_menu_id:
        raise RuntimeError(f"Alias {alias_id} 沒有 richMenuId")

    return rich_menu_id


def get_rich_menu_object(rich_menu_id: str) -> dict:
    response = requests.get(
        f"{LINE_API_BASE}/richmenu/{rich_menu_id}",
        headers=AUTH_HEADERS,
        timeout=30,
    )
    require_success(response, f"讀取 Rich Menu {rich_menu_id}")

    data = response.json()

    # 建立 Rich Menu 時不能帶回傳專用欄位。
    allowed_fields = {
        "size",
        "selected",
        "name",
        "chatBarText",
        "areas",
    }

    create_payload = {
        key: value
        for key, value in data.items()
        if key in allowed_fields
    }

    missing = allowed_fields - create_payload.keys()

    if missing:
        raise RuntimeError(
            f"Rich Menu {rich_menu_id} 缺少必要欄位："
            f"{sorted(missing)}"
        )

    return create_payload


def create_rich_menu(payload: dict) -> str:
    response = requests.post(
        f"{LINE_API_BASE}/richmenu",
        headers={
            **AUTH_HEADERS,
            "Content-Type": "application/json",
        },
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=30,
    )
    require_success(response, "建立新 Rich Menu")

    rich_menu_id = response.json().get("richMenuId")

    if not rich_menu_id:
        raise RuntimeError("建立 Rich Menu 成功，但沒有回傳 richMenuId")

    return rich_menu_id


def validate_jpg(image_path: Path) -> None:
    if not image_path.is_file():
        raise FileNotFoundError(f"找不到圖片：{image_path}")

    if image_path.suffix.lower() not in {".jpg", ".jpeg"}:
        raise RuntimeError(f"圖片不是 JPG：{image_path}")

    size_bytes = image_path.stat().st_size

    if size_bytes == 0:
        raise RuntimeError(f"圖片是空檔案：{image_path}")

    if size_bytes > 1024 * 1024:
        raise RuntimeError(
            f"圖片超過 LINE 1 MB 限制：{image_path} "
            f"({size_bytes / 1024 / 1024:.2f} MB)"
        )

    # JPEG 檔案標頭通常為 FF D8 FF。
    with image_path.open("rb") as file:
        signature = file.read(3)

    if signature != b"\xff\xd8\xff":
        raise RuntimeError(
            f"副檔名雖然是 JPG，但內容不像 JPEG：{image_path}"
        )


def upload_jpg(rich_menu_id: str, image_path: Path) -> None:
    validate_jpg(image_path)

    with image_path.open("rb") as image_file:
        response = requests.post(
            f"{LINE_DATA_API_BASE}/richmenu/{rich_menu_id}/content",
            headers={
                **AUTH_HEADERS,
                "Content-Type": "image/jpeg",
            },
            data=image_file,
            timeout=60,
        )

    require_success(
        response,
        f"上傳圖片 {image_path.name} 到 {rich_menu_id}",
    )


def update_alias(alias_id: str, new_rich_menu_id: str) -> None:
    response = requests.post(
        f"{LINE_API_BASE}/richmenu/alias/{alias_id}",
        headers={
            **AUTH_HEADERS,
            "Content-Type": "application/json",
        },
        json={
            "richMenuId": new_rich_menu_id,
        },
        timeout=30,
    )
    require_success(response, f"更新 Alias {alias_id}")


def delete_rich_menu(rich_menu_id: str) -> None:
    response = requests.delete(
        f"{LINE_API_BASE}/richmenu/{rich_menu_id}",
        headers=AUTH_HEADERS,
        timeout=30,
    )
    require_success(response, f"刪除 Rich Menu {rich_menu_id}")


# =========================================================
# 更新流程
# =========================================================

def replace_one_menu(alias_id: str, image_path: Path) -> dict:
    old_rich_menu_id = get_alias_target(alias_id)
    old_payload = get_rich_menu_object(old_rich_menu_id)

    new_rich_menu_id = None

    try:
        new_rich_menu_id = create_rich_menu(old_payload)
        upload_jpg(new_rich_menu_id, image_path)
        update_alias(alias_id, new_rich_menu_id)

    except Exception:
        # 如果 Alias 尚未更新，但新選單建立到一半，清除不完整的新選單。
        if new_rich_menu_id:
            try:
                delete_rich_menu(new_rich_menu_id)
            except Exception as cleanup_error:
                print(
                    f"警告：清除未完成選單失敗："
                    f"{new_rich_menu_id}\n{cleanup_error}"
                )
        raise

    return {
        "alias": alias_id,
        "image": str(image_path),
        "old_rich_menu_id": old_rich_menu_id,
        "new_rich_menu_id": new_rich_menu_id,
    }


def main() -> None:
    print("=" * 72)
    print("家屬＋長者 Rich Menu JPG 更新")
    print("流程：複製舊設定 → 建立新 ID → 上傳 JPG → Alias 指向新 ID")
    print("舊 Rich Menu 暫不刪除，避免現有使用者選單突然消失")
    print("=" * 72)

    results = []
    failures = []

    for alias_id, image_path in MENU_IMAGES.items():
        print()
        print("-" * 72)
        print(f"Alias：{alias_id}")
        print(f"JPG：{image_path}")

        try:
            result = replace_one_menu(alias_id, image_path)
            results.append(result)

            print(f"舊 ID：{result['old_rich_menu_id']}")
            print(f"新 ID：{result['new_rich_menu_id']}")
            print("Alias 更新成功")

        except Exception as error:
            failures.append({
                "alias": alias_id,
                "image": str(image_path),
                "error": str(error),
            })
            print(f"更新失敗：{error}")

    print()
    print("=" * 72)
    print(f"成功：{len(results)}")
    print(f"失敗：{len(failures)}")

    result_by_alias = {
        item["alias"]: item["new_rich_menu_id"]
        for item in results
    }

    print()
    print("請更新 Render 環境變數：")

    if "family_main" in result_by_alias:
        print(
            "FAMILY_RICH_MENU_ID="
            f"{result_by_alias['family_main']}"
        )

    if "elder_main" in result_by_alias:
        print(
            "ELDERLY_RICH_MENU_ID="
            f"{result_by_alias['elder_main']}"
        )

    print()
    print("新舊 ID 對照：")

    for item in results:
        print(
            f"{item['alias']}："
            f"{item['old_rich_menu_id']} "
            f"-> {item['new_rich_menu_id']}"
        )

    if failures:
        print()
        print("失敗項目：")

        for item in failures:
            print(
                f"- {item['alias']} / {item['image']}\n"
                f"  {item['error']}"
            )

        raise RuntimeError(
            "部分選單更新失敗；成功項目的 Alias 已經更新。"
        )

    print()
    print("14 個 Alias 全部更新完成。")
    print("=" * 72)


if __name__ == "__main__":
    main()
