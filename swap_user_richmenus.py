import os
import psycopg2

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
)


USER_1 = "U6a5da72f3d53671b335562c0e6085dad"
USER_2 = "Ud5f97b6a8e337eea33a6f556c0ac19f2"


def get_db_connection():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
    )


def get_user_rich_menu(cursor, line_user_id):
    cursor.execute(
        """
        SELECT
            u.line_user_id,
            u.display_name,
            r.code AS role,
            u.current_rich_menu_id
        FROM app_users u
        JOIN roles r
            ON r.id = u.role_id
        WHERE u.line_user_id = %s
        """,
        (line_user_id,),
    )

    return cursor.fetchone()


def main():
    access_token = os.getenv("CHANNEL_ACCESS_TOKEN")

    if not access_token:
        raise RuntimeError("找不到 CHANNEL_ACCESS_TOKEN")

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            user_1 = get_user_rich_menu(cursor, USER_1)
            user_2 = get_user_rich_menu(cursor, USER_2)

        if not user_1:
            raise RuntimeError(f"資料庫找不到使用者：{USER_1}")

        if not user_2:
            raise RuntimeError(f"資料庫找不到使用者：{USER_2}")

        print("===== 資料庫目前資料 =====")
        print(
            f"{user_1[1]} | {user_1[0]} | "
            f"身份={user_1[2]} | Rich Menu={user_1[3]}"
        )
        print(
            f"{user_2[1]} | {user_2[0]} | "
            f"身份={user_2[2]} | Rich Menu={user_2[3]}"
        )

        if not user_1[3]:
            raise RuntimeError(f"{USER_1} 的 current_rich_menu_id 是空的")

        if not user_2[3]:
            raise RuntimeError(f"{USER_2} 的 current_rich_menu_id 是空的")

        configuration = Configuration(access_token=access_token)

        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)

            # 先解除原本的個人 Rich Menu
            for line_user_id in (USER_1, USER_2):
                try:
                    messaging_api.unlink_rich_menu_id_from_user(line_user_id)
                    print(f"已解除舊 Rich Menu：{line_user_id}")
                except Exception as error:
                    print(
                        f"解除 Rich Menu 時收到訊息，繼續重新綁定："
                        f"{line_user_id}｜{error}"
                    )

            # 依照資料庫交換後的 current_rich_menu_id 重新綁定
            messaging_api.link_rich_menu_id_to_user(
                USER_1,
                user_1[3],
            )
            print(f"綁定完成：{USER_1} → {user_1[3]}")

            messaging_api.link_rich_menu_id_to_user(
                USER_2,
                user_2[3],
            )
            print(f"綁定完成：{USER_2} → {user_2[3]}")

        print("\nLINE Rich Menu 已依照資料庫目前身份重新綁定。")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
