import os

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
)


LINE_USER_ID = "U6a5da72f3d53671b335562c0e6085dad"
FAMILY_RICH_MENU_ID = "richmenu-175e929a4b422f3b83fe15b7faeba406"


def main():
    access_token = os.getenv("CHANNEL_ACCESS_TOKEN")

    if not access_token:
        raise RuntimeError("找不到 CHANNEL_ACCESS_TOKEN")

    configuration = Configuration(access_token=access_token)

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)

        # 直接綁定家屬 Rich Menu
        # 不需要先 unlink，新的綁定會直接取代舊的
        messaging_api.link_rich_menu_id_to_user(
            LINE_USER_ID,
            FAMILY_RICH_MENU_ID,
        )

        print(
            "家屬 Rich Menu 綁定完成："
            f"{LINE_USER_ID} → {FAMILY_RICH_MENU_ID}"
        )


if __name__ == "__main__":
    main()
