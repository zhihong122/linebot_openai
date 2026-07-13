import json
import os

from family_richmenu import create_family_richmenus
from patient_richmenu import create_patient_richmenus
from caregiver_richmenu import create_caregiver_richmenus


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RICHMENU_ID_FILE = os.path.join(
    BASE_DIR,
    "richmenu_ids.json",
)


def create_all_richmenus():
    results = {
        "family": create_family_richmenus(),
        "elderly": create_patient_richmenus(),
        "caregiver": create_caregiver_richmenus(),
    }

    with open(
        RICHMENU_ID_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return results


def load_richmenu_ids():
    if not os.path.exists(RICHMENU_ID_FILE):
        return {}

    with open(
        RICHMENU_ID_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_home_rich_menu_id(role):
    data = load_richmenu_ids()
    role_data = data.get(role, {})
    return role_data.get("home_rich_menu_id")


if __name__ == "__main__":
    result = create_all_richmenus()
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
