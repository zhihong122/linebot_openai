import os

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
)


channel_access_token = os.getenv("CHANNEL_ACCESS_TOKEN")

if not channel_access_token:
    raise RuntimeError(
        "找不到 CHANNEL_ACCESS_TOKEN，請確認 Render Environment 已設定"
    )


configuration = Configuration(
    access_token=channel_access_token
)


with ApiClient(configuration) as api_client:
    api = MessagingApi(api_client)

    print("\n===== Rich Menu 清單 =====")

    menus = api.get_rich_menu_list()

    if not menus.richmenus:
        print("目前沒有 Rich Menu")
    else:
        for menu in menus.richmenus:
            print(
                f"{menu.rich_menu_id} | "
                f"{menu.name} | "
                f"{menu.chat_bar_text}"
            )

    print("\n===== Rich Menu Alias 清單 =====")

    aliases = api.get_rich_menu_alias_list()

    if not aliases.aliases:
        print("目前沒有 Rich Menu Alias")
    else:
        for alias in aliases.aliases:
            print(
                f"{alias.rich_menu_alias_id} "
                f"-> {alias.rich_menu_id}"
            )
