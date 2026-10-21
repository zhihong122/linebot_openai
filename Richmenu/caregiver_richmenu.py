import os

from richmenu_common import create_rich_menu_set


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "static", "caregiver", "en")
SIZE = {"width": 2500, "height": 1686}
TOP = [{"x": 45, "y": 210, "width": 788, "height": 543}, {"x": 858, "y": 216, "width": 814, "height": 535}, {"x": 1688, "y": 215, "width": 798, "height": 535}]
BOTTOM = [{"x": 38, "y": 776, "width": 795, "height": 620}, {"x": 855, "y": 782, "width": 820, "height": 614}, {"x": 1707, "y": 792, "width": 757, "height": 600}]
SIX = TOP + BOTTOM
SWITCH_PATIENT = {"x": 1265, "y": 19, "width": 1227, "height": 172}
SELECTOR = [{"x": 45, "y": 210, "width": 788, "height": 1196}, {"x": 858, "y": 216, "width": 814, "height": 1180}, {"x": 1688, "y": 219, "width": 798, "height": 1164}]
ONLY_ONE_PATIENT = [{"x": 38, "y": 255, "width": 1221, "height": 1417}, {"x": 1268, "y": 264, "width": 1205, "height": 1401}]


def postback(data, label):
    return {"type": "postback", "data": data, "displayText": label}


def switch(alias, data):
    return {"type": "richmenuswitch", "richMenuAliasId": alias, "data": data}


def area(bounds, action):
    return {"bounds": bounds, "action": action}


def six_menu(name, actions, image, alias, chat_bar="Back"):
    return {"menu": {"size": SIZE, "selected": True, "name": name, "chatBarText": chat_bar, "areas": [area(bounds, action) for bounds, action in zip(SIX, actions)]}, "image": image, "alias": alias}


def patient_menu_definitions(slot):
    """產生 Patient 1/2 各自獨立的圖片、Rich Menu 與 Alias。"""
    prefix = f"cg_p{slot}"
    key = f"patient{slot}"
    back_main = switch(f"{prefix}_main", f"switch-to-caregiver-patient{slot}-main")
    back_selector = postback("action=caregiver_back_selector", "Switch Patient")
    images = ({
        "main": "caregiver_patient1_main_menu.jpg", "tasks": "caregiver_patient1_today_tasks_menu.jpg",
        "records": "caregiver_patient1_medication_records_menu.jpg", "calendar": "caregiver_patient1_calendar_menu.jpg",
        "rx": "caregiver_patient1_prescription_medication_menu.jpg", "plan": "caregiver_patient1_medication_plan_menu.jpg",
        "report": "caregiver_patient1_report_issue_menu.jpg", "sos": "caregiver_patient1_sos_menu.jpg",
    } if slot == 1 else {
        "main": "2mainmenu.jpg", "tasks": "2today_task.jpg", "records": "2medecation_record.jpg",
        "calendar": "2calendar.jpg", "rx": "2photograph.jpg", "plan": "2medecation_plan.jpg",
        "report": "2report.jpg", "sos": "2sos.jpg",
    })

    result = {
        f"{key}_main": {
            "menu": {"size": SIZE, "selected": True, "name": f"Caregiver - Patient {slot}", "chatBarText": "Patient Menu", "areas": [
                area(TOP[0], switch(f"{prefix}_tasks", "switch-to-caregiver-today-tasks")),
                area(TOP[1], switch(f"{prefix}_records", "switch-to-caregiver-medication-records")),
                area(TOP[2], switch(f"{prefix}_calendar", "switch-to-caregiver-calendar")),
                area(BOTTOM[0], switch(f"{prefix}_rx", "switch-to-caregiver-prescription")),
                area(BOTTOM[1], switch(f"{prefix}_report", "switch-to-caregiver-report-issue")),
                area(BOTTOM[2], switch(f"{prefix}_sos", "switch-to-caregiver-sos")),
                area(SWITCH_PATIENT, back_selector),
            ]}, "image": images["main"], "alias": f"{prefix}_main",
        },
        f"{key}_tasks": six_menu(f"Caregiver - Patient {slot} Tasks", [
            postback("action=caregiver_tasks&slot=breakfast", "Morning Tasks"), postback("action=caregiver_tasks&slot=lunch", "Afternoon Tasks"),
            postback("action=caregiver_tasks&slot=dinner", "Evening Tasks"), postback("action=caregiver_tasks&slot=bedtime", "Before Bed Tasks"),
            postback("action=caregiver_medication_schedule", "Medication Schedule"), back_main,
        ], images["tasks"], f"{prefix}_tasks"),
        f"{key}_records": six_menu(f"Caregiver - Patient {slot} Medication Records", [
            postback("action=caregiver_medication_records&period=today", "Today's Records"), postback("action=caregiver_medication_records&period=7days", "Last 7 Days"),
            postback("action=caregiver_medication_summary", "Medication Summary"), postback("action=caregiver_medication_records&period=late", "Late Records"),
            postback("action=caregiver_medication_records&period=missed", "Missed Records"), back_main,
        ], images["records"], f"{prefix}_records"),
        f"{key}_calendar": six_menu(f"Caregiver - Patient {slot} Calendar", [
            postback("action=caregiver_calendar&type=hospital_visit", "Return Visit"), postback("action=caregiver_calendar&type=medication_pickup", "Medication Pickup"),
            postback("action=caregiver_calendar&type=other", "Other"), postback("action=caregiver_calendar&type=temporary", "Temporary Appointment"),
            postback("action=caregiver_calendar&type=reminders", "Upcoming Reminders"), back_main,
        ], images["calendar"], f"{prefix}_calendar"),
        f"{key}_rx": six_menu(f"Caregiver - Patient {slot} Prescription", [
            {"type": "camera", "label": "Photograph Rx"}, switch(f"{prefix}_plan", "switch-to-caregiver-medication-plan"),
            postback("action=caregiver_prescription_details", "Prescription Details"), postback("action=caregiver_recognition_result", "Recognition Result"),
            postback("action=caregiver_medication_warnings", "Medication Warnings"), back_main,
        ], images["rx"], f"{prefix}_rx"),
        f"{key}_plan": six_menu(f"Caregiver - Patient {slot} Medication Plan", [
            postback("action=caregiver_medication_plan&slot=breakfast", "Morning Medication"), postback("action=caregiver_medication_plan&slot=lunch", "Noon Medication"),
            postback("action=caregiver_medication_plan&slot=dinner", "Evening Medication"), postback("action=caregiver_medication_plan&slot=bedtime", "Bedtime Medication"),
            postback("action=caregiver_medication_plan&slot=prn", "PRN Medication"), switch(f"{prefix}_rx", "back-to-caregiver-prescription"),
        ], images["plan"], f"{prefix}_plan"),
        f"{key}_report": six_menu(f"Caregiver - Patient {slot} Report Issue", [
            postback("action=caregiver_report_issue&type=refuse_service", "Refuse Service"), postback("action=caregiver_report_issue&type=body_discomfort", "Body Discomfort"),
            postback("action=caregiver_report_issue&type=vomiting", "Vomiting"), postback("action=caregiver_report_issue&type=missing_medication", "Missing Medication"),
            postback("action=caregiver_report_issue&type=other", "Other Issue"), back_main,
        ], images["report"], f"{prefix}_report"),
        f"{key}_sos": {"menu": {"size": SIZE, "selected": True, "name": f"Caregiver - Patient {slot} SOS", "chatBarText": "SOS", "areas": [
            area({"x": 45, "y": 210, "width": 788, "height": 543}, postback("action=caregiver_sos_contact&contact=1", "Contact 1")),
            area({"x": 858, "y": 216, "width": 1628, "height": 535}, postback("action=caregiver_sos_contact&contact=2", "Contact 2")),
            area({"x": 38, "y": 776, "width": 1637, "height": 620}, postback("action=caregiver_sos_notify_all", "Notify All")),
            area({"x": 1707, "y": 792, "width": 757, "height": 600}, back_main),
        ]}, "image": images["sos"], "alias": f"{prefix}_sos"},
    }
    return result


MENU_DEFINITIONS = {
    "main": {"menu": {"size": SIZE, "selected": True, "name": "Caregiver - Select Patient", "chatBarText": "Select Patient", "areas": [
        area(SELECTOR[0], postback("action=caregiver_select_patient&slot=1", "Patient 1")),
        area(SELECTOR[1], postback("action=caregiver_select_patient&slot=2", "Patient 2")),
        area(SELECTOR[2], postback("action=caregiver_emergency", "Emergency")),
    ]}, "image": "caregiver_patient_selector_menu.jpg", "alias": "caregiver_main"},
    "single_patient_main": {"menu": {"size": SIZE, "selected": True, "name": "Caregiver - One Patient", "chatBarText": "Patient / SOS", "areas": [
        area(ONLY_ONE_PATIENT[0], postback("action=caregiver_select_patient&slot=1", "Patient 1")),
        area(ONLY_ONE_PATIENT[1], postback("action=caregiver_emergency", "Emergency")),
    ]}, "image": "onrly1patient.jpg", "alias": "caregiver_single_main"},
}
MENU_DEFINITIONS.update(patient_menu_definitions(1))
MENU_DEFINITIONS.update(patient_menu_definitions(2))


def create_caregiver_richmenus():
    menu_ids = create_rich_menu_set(role_name="caregiver", image_dir=IMAGE_DIR, menu_definitions=MENU_DEFINITIONS)
    return {"role": "caregiver", "home_rich_menu_id": menu_ids["main"], "single_patient_home_rich_menu_id": menu_ids["single_patient_main"], "menus": menu_ids, "aliases": {key: value["alias"] for key, value in MENU_DEFINITIONS.items()}}


if __name__ == "__main__":
    print(create_caregiver_richmenus())
