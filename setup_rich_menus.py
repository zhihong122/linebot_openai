"""
建立家屬、看護、長者三套 LINE Rich Menu，並上傳圖片。

使用方式：
1. 在專案建立：
   static/richmenu/family.png
   static/richmenu/caregiver.png
   static/richmenu/elderly.png

2. 設定環境變數 CHANNEL_ACCESS_TOKEN。

3. 執行：
   python setup_rich_menus.py

4. 執行完成後，把 richmenu_ids.env 中的三個 ID
   貼到 Render 的 Environment。
"""

import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import requests
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "richmenu_config.json"
OUTPUT_JSON_PATH = BASE_DIR / "richmenu_ids.json"
OUTPUT_ENV_PATH = BASE_DIR / "richmenu_ids.env"

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

API_BASE = "https://api.line.me"
DATA_API_BASE = "https://api-data.line.me"

ALLOWED_IMAGE_SIZES = {
    (2500, 1686),
    (2500, 843),
    (1200, 810),
    (1200, 405),
    (800, 540),
    (800, 270),
}


def fail(message: str) -> None:
    print(f"\n[錯誤] {message}\n", file=sys.stderr)
    raise SystemExit(1)


def auth_headers(content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        fail(f"找不到設定檔：{CONFIG_PATH}")

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except json.JSONDecodeError as error:
        fail(f"richmenu_config.json 格式錯誤：{error}")

    menus = config.get("menus")

    if not isinstance(menus, list) or not menus:
        fail("richmenu_config.json 必須包含 menus 陣列")

    return config


def resolve_image_path(raw_path: str) -> Path:
    image_path = Path(raw_path)

    if not image_path.is_absolute():
        image_path = BASE_DIR / image_path

    return image_path.resolve()


def inspect_image(image_path: Path) -> tuple[int, int, str]:
    if not image_path.exists():
        fail(f"找不到 Rich Menu 圖片：{image_path}")

    try:
        with Image.open(image_path) as image:
            width, height = image.size
            image_format = (image.format or "").upper()
    except Exception as error:
        fail(f"無法讀取圖片 {image_path}：{error}")

    if (width, height) not in ALLOWED_IMAGE_SIZES:
        allowed_text = "、".join(
            f"{w}x{h}" for w, h in sorted(ALLOWED_IMAGE_SIZES)
        )
        fail(
            f"{image_path.name} 尺寸為 {width}x{height}，"
            f"請改成 LINE Rich Menu 支援尺寸：{allowed_text}"
        )

    if image_format not in {"PNG", "JPEG", "JPG"}:
        fail(f"{image_path.name} 必須是 PNG 或 JPEG")

    content_type = mimetypes.guess_type(image_path.name)[0]

    if image_format == "PNG":
        content_type = "image/png"
    else:
        content_type = "image/jpeg"

    return width, height, content_type


def validate_area(area: dict[str, Any], width: int, height: int) -> None:
    bounds = area.get("bounds")
    action = area.get("action")

    if not isinstance(bounds, dict):
        fail("每個 area 都必須包含 bounds")

    required = ("x", "y", "width", "height")

    for key in required:
        if not isinstance(bounds.get(key), int):
            fail(f"area.bounds.{key} 必須是整數")

    x = bounds["x"]
    y = bounds["y"]
    area_width = bounds["width"]
    area_height = bounds["height"]

    if x < 0 or y < 0 or area_width <= 0 or area_height <= 0:
        fail("area 邊界不可為負數，width/height 必須大於 0")

    if x + area_width > width or y + area_height > height:
        fail(
            "area 超出圖片範圍："
            f"圖片={width}x{height}, bounds={bounds}"
        )

    if not isinstance(action, dict):
        fail("每個 area 都必須包含 action")

    action_type = action.get("type")

    if action_type not in {
        "message",
        "postback",
        "uri",
        "datetimepicker",
        "richmenuswitch",
    }:
        fail(f"不支援的 action.type：{action_type}")


def build_payload(menu: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    areas = menu.get("areas", [])

    if not isinstance(areas, list) or not areas:
        fail(f"{menu.get('name', '未命名選單')} 沒有設定 areas")

    for area in areas:
        validate_area(area, width, height)

    return {
        "size": {
            "width": width,
            "height": height,
        },
        "selected": bool(menu.get("selected", True)),
        "name": str(menu.get("name", "Rich Menu"))[:300],
        "chatBarText": str(menu.get("chatBarText", "開啟選單"))[:14],
        "areas": areas,
    }


def create_rich_menu(payload: dict[str, Any]) -> str:
    response = requests.post(
        f"{API_BASE}/v2/bot/richmenu",
        headers=auth_headers("application/json"),
        json=payload,
        timeout=30,
    )

    if response.status_code != 200:
        fail(
            "建立 Rich Menu 失敗："
            f"HTTP {response.status_code}\n{response.text}"
        )

    rich_menu_id = response.json().get("richMenuId")

    if not rich_menu_id:
        fail(f"LINE 回應沒有 richMenuId：{response.text}")

    return rich_menu_id


def upload_rich_menu_image(
    rich_menu_id: str,
    image_path: Path,
    content_type: str,
) -> None:
    with image_path.open("rb") as image_file:
        response = requests.post(
            (
                f"{DATA_API_BASE}/v2/bot/richmenu/"
                f"{rich_menu_id}/content"
            ),
            headers=auth_headers(content_type),
            data=image_file,
            timeout=60,
        )

    if response.status_code != 200:
        fail(
            f"上傳圖片失敗（{rich_menu_id}）："
            f"HTTP {response.status_code}\n{response.text}"
        )


def delete_rich_menu(rich_menu_id: str) -> None:
    response = requests.delete(
        f"{API_BASE}/v2/bot/richmenu/{rich_menu_id}",
        headers=auth_headers(),
        timeout=30,
    )

    if response.status_code not in {200, 404}:
        print(
            f"[警告] 清理失敗 {rich_menu_id}："
            f"HTTP {response.status_code} {response.text}"
        )


def write_results(results: dict[str, str]) -> None:
    with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    env_lines = [
        f"FAMILY_RICH_MENU_ID={results.get('family', '')}",
        f"CAREGIVER_RICH_MENU_ID={results.get('caregiver', '')}",
        f"ELDERLY_RICH_MENU_ID={results.get('elderly', '')}",
    ]

    OUTPUT_ENV_PATH.write_text(
        "\n".join(env_lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if not CHANNEL_ACCESS_TOKEN:
        fail("缺少環境變數 CHANNEL_ACCESS_TOKEN")

    config = load_config()
    results: dict[str, str] = {}
    created_ids: list[str] = []

    try:
        for menu in config["menus"]:
            role = menu.get("role")

            if role not in {"family", "caregiver", "elderly"}:
                fail(f"role 必須是 family/caregiver/elderly：{role}")

            image_path = resolve_image_path(menu.get("image", ""))
            width, height, content_type = inspect_image(image_path)
            payload = build_payload(menu, width, height)

            print(f"\n建立：{menu['name']}")
            print(f"圖片：{image_path}")
            print(f"尺寸：{width}x{height}")

            rich_menu_id = create_rich_menu(payload)
            created_ids.append(rich_menu_id)

            print(f"Rich Menu ID：{rich_menu_id}")
            print("上傳圖片中……")

            upload_rich_menu_image(
                rich_menu_id,
                image_path,
                content_type,
            )

            results[role] = rich_menu_id
            print("完成。")

        write_results(results)

    except BaseException:
        # 避免建立到一半留下沒有圖片的選單
        if created_ids:
            print("\n正在清理由本次執行建立的 Rich Menu……")
            for rich_menu_id in created_ids:
                delete_rich_menu(rich_menu_id)
        raise

    print("\n========================================")
    print("三套 Rich Menu 已建立並上傳完成")
    print("========================================")
    print(OUTPUT_ENV_PATH.read_text(encoding="utf-8"))
    print(f"環境變數檔：{OUTPUT_ENV_PATH}")
    print(f"JSON 結果檔：{OUTPUT_JSON_PATH}")
    print("\n請把以上三個值貼到 Render Environment，然後重新部署主程式。")


if __name__ == "__main__":
    main()
