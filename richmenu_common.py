import json
import os
import mimetypes
import requests

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    RichMenuRequest,
)


CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("缺少 CHANNEL_ACCESS_TOKEN")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
API_BASE = "https://api.line.me/v2/bot"
MAX_IMAGE_BYTES = 1024 * 1024


def _request(method, url, **kwargs):
    response = requests.request(
        method,
        url,
        timeout=30,
        **kwargs,
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"LINE API 請求失敗：HTTP {response.status_code} {response.text}"
        )

    return response


def create_or_update_alias(alias_id, rich_menu_id):
    auth_headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }
    json_headers = {
        **auth_headers,
        "Content-Type": "application/json",
    }

    response = requests.get(
        f"{API_BASE}/richmenu/alias/{alias_id}",
        headers=auth_headers,
        timeout=20,
    )

    if response.status_code == 200:
        _request(
            "POST",
            f"{API_BASE}/richmenu/alias/{alias_id}",
            headers=json_headers,
            json={"richMenuId": rich_menu_id},
        )
        return "updated"

    if response.status_code == 404:
        _request(
            "POST",
            f"{API_BASE}/richmenu/alias",
            headers=json_headers,
            json={
                "richMenuAliasId": alias_id,
                "richMenuId": rich_menu_id,
            },
        )
        return "created"

    raise RuntimeError(
        "查詢 Rich Menu Alias 失敗："
        f"HTTP {response.status_code} {response.text}"
    )


def validate_rich_menu_images(image_dir, menu_definitions):
    errors = []
    checked = []

    for menu_key, definition in menu_definitions.items():
        image_path = os.path.join(image_dir, definition["image"])

        if not os.path.isfile(image_path):
            errors.append(
                f"[{menu_key}] 找不到圖片：{image_path}"
            )
            continue

        image_size = os.path.getsize(image_path)
        extension = os.path.splitext(image_path)[1].lower()

        if extension not in (".jpg", ".jpeg", ".png"):
            errors.append(
                f"[{menu_key}] 圖片格式不支援：{image_path}"
            )
            continue

        if image_size > MAX_IMAGE_BYTES:
            errors.append(
                f"[{menu_key}] 圖片超過 1 MB：{image_path} "
                f"({image_size / 1024:.1f} KB)"
            )
            continue

        checked.append(
            f"[{menu_key}] {image_path} ({image_size / 1024:.1f} KB)"
        )

    if errors:
        raise RuntimeError(
            "Rich Menu 圖片預檢失敗，尚未建立任何選單：\n- "
            + "\n- ".join(errors)
        )

    return checked


def read_image(image_path):
    extension = os.path.splitext(image_path)[1].lower()

    if extension in (".jpg", ".jpeg"):
        content_type = "image/jpeg"
    elif extension == ".png":
        content_type = "image/png"
    else:
        content_type = mimetypes.guess_type(image_path)[0]

    if content_type not in ("image/jpeg", "image/png"):
        raise ValueError(f"不支援的圖片格式：{image_path}")

    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise RuntimeError(
            f"Rich Menu 圖片超過 1 MB：{image_path} "
            f"({len(image_bytes) / 1024:.1f} KB)"
        )

    return image_bytes, content_type


def create_rich_menu_set(
    role_name,
    image_dir,
    menu_definitions,
):
    checked = validate_rich_menu_images(
        image_dir=image_dir,
        menu_definitions=menu_definitions,
    )

    print(f"[{role_name}] 圖片預檢完成：")
    for item in checked:
        print(f"  {item}")

    created_ids = {}

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        blob_api = MessagingApiBlob(api_client)

        for menu_key, definition in menu_definitions.items():
            menu_request = RichMenuRequest.from_json(
                json.dumps(
                    definition["menu"],
                    ensure_ascii=False,
                )
            )

            rich_menu_id = messaging_api.create_rich_menu(
                rich_menu_request=menu_request
            ).rich_menu_id

            try:
                image_path = os.path.join(
                    image_dir,
                    definition["image"],
                )
                image_bytes, content_type = read_image(image_path)

                blob_api.set_rich_menu_image(
                    rich_menu_id=rich_menu_id,
                    body=image_bytes,
                    _headers={"Content-Type": content_type},
                )

                alias_status = create_or_update_alias(
                    definition["alias"],
                    rich_menu_id,
                )

                created_ids[menu_key] = rich_menu_id

                print(
                    f"[{role_name}] {menu_key}: {rich_menu_id} "
                    f"(alias {alias_status}: {definition['alias']})"
                )

            except Exception:
                try:
                    messaging_api.delete_rich_menu(
                        rich_menu_id=rich_menu_id
                    )
                except Exception:
                    pass
                raise

    return created_ids
