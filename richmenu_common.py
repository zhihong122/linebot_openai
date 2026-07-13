import json
import os
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


configuration = Configuration(
    access_token=CHANNEL_ACCESS_TOKEN
)

API_BASE = "https://api.line.me/v2/bot"


def _request(method, url, **kwargs):
    response = requests.request(
        method,
        url,
        timeout=30,
        **kwargs,
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"LINE API 請求失敗：HTTP {response.status_code} "
            f"{response.text}"
        )

    return response


def create_or_update_alias(alias_id, rich_menu_id):
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    get_response = requests.get(
        f"{API_BASE}/richmenu/alias/{alias_id}",
        headers={
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
        },
        timeout=20,
    )

    if get_response.status_code == 200:
        _request(
            "POST",
            f"{API_BASE}/richmenu/alias/{alias_id}",
            headers=headers,
            json={"richMenuId": rich_menu_id},
        )
        return "updated"

    if get_response.status_code == 404:
        _request(
            "POST",
            f"{API_BASE}/richmenu/alias",
            headers=headers,
            json={
                "richMenuAliasId": alias_id,
                "richMenuId": rich_menu_id,
            },
        )
        return "created"

    raise RuntimeError(
        "查詢 Rich Menu Alias 失敗："
        f"HTTP {get_response.status_code} {get_response.text}"
    )


def download_image(image_url):
    response = requests.get(
        image_url,
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "下載 Rich Menu 圖片失敗："
            f"HTTP {response.status_code} {response.text}"
        )

    content_type = response.headers.get(
        "Content-Type",
        "image/png",
    ).split(";")[0]

    if content_type not in (
        "image/png",
        "image/jpeg",
    ):
        content_type = "image/png"

    return response.content, content_type


def create_rich_menu_set(
    role_name,
    base_url,
    menu_definitions,
):
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

            image_bytes, content_type = download_image(
                f"{base_url}/{definition['image']}"
            )

            blob_api.set_rich_menu_image(
                rich_menu_id=rich_menu_id,
                body=image_bytes,
                _headers={
                    "Content-Type": content_type
                },
            )

            alias_status = create_or_update_alias(
                definition["alias"],
                rich_menu_id,
            )

            created_ids[menu_key] = rich_menu_id

            print(
                f"[{role_name}] {menu_key}: "
                f"{rich_menu_id} "
                f"(alias {alias_status}: "
                f"{definition['alias']})"
            )

    return created_ids
