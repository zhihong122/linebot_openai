"""Medication-bag image analysis and real QR decoding for the LINE bot."""

from __future__ import annotations

import base64
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


ANALYSIS_PROMPT = """你是一個專門辨識臺灣醫療院所藥袋、處方箋與用藥標示的圖片分析助手。

任務：忠實擷取圖片上實際可見的資訊，依固定格式輸出。不得根據一般醫學知識、藥名、網站或常見用法補充、推測、修正或改寫圖片未標示的內容。

必要規則：
1. 欄位完全沒有標示時填「未標示」；有標示但因模糊、反光、遮擋、皺褶、裁切或解析度不足無法確認時填「看不清楚」。
2. 不得自行補充副作用、警語、危險警訊、注意事項、禁忌、疾病建議、藥理作用、用藥時間表、停藥方式、劑量調整或任何一般醫學知識。
3. 「每次量」只放單次量；「一天幾次／每幾小時」只放頻率或間隔；「與餐關係」只放餐前後資訊；「早／中／晚／睡前」只放圖片實際標示的時段。
4. 「用藥方式」可以整合圖片上已有內容成一句，但不得自行安排時間。
5. PRN 必須擷取圖片實際標示的使用條件、單次量、最短間隔與每日上限；個別項目沒寫就寫未標示。完全沒有 PRN 就寫未標示。
6. 療程與總量只照圖片輸出，不得加入「剛好吃完」等說明。
7. 臨床用途只能擷取藥袋上實際寫出的用途，不得由藥名推測。
8. 副作用、警語、危險警訊若有原始編號或符號，必須保留；一條一行，不得合併或自行分類嚴重程度。
9. QR Code 已由後端解碼器實際處理。你必須逐字使用使用者訊息提供的 QR 結果與狀態，不得從圖片猜測、修改或補齊網址，也不得聲稱使用 Code Interpreter。
10. 使用繁體中文及臺灣常用醫療用語；不要輸出前言、結語、Python 程式碼、Markdown 粗體或「照抄藥袋」等註解。

固定輸出格式（每個欄位都必須保留）：
・藥名＋含量：
・每次量：
・用藥方式（Administration）：
・一天幾次／每幾小時：
・與餐關係：
・早／中／晚／睡前：
・PRN：
・療程天數／總量：
・臨床用途（藥袋標示）：
・可能副作用：
・警語：
・危險警訊：
・QR Code（掃描後連結）：

QR Code 解碼狀態：
・是否偵測到：
・是否完整：
・實際執行方法：
・成功方法：
・失敗原因：
"""


@dataclass
class QRResult:
    value: Optional[str]
    detected: bool
    complete: Optional[bool]
    attempted_methods: list[str]
    successful_method: Optional[str]
    failure_reasons: list[str]

    @property
    def field_value(self) -> str:
        if self.value and re.match(r"^https?://", self.value, re.I):
            return self.value
        if self.value:
            return "解碼內容不是連結"
        if self.detected and self.complete is False:
            reason = "／".join(self.failure_reasons[:3]) or "邊緣不完整"
            return f"QR Code 不完整：{reason}"
        if not self.detected:
            return "未偵測到 QR Code"
        return "無法掃描出連結"

    def prompt_context(self) -> str:
        complete = "是" if self.complete is True else "否" if self.complete is False else "無法確認"
        return (
            f"QR Code（掃描後連結）：{self.field_value}\n"
            f"是否偵測到：{'是' if self.detected else '否'}\n"
            f"是否完整：{complete}\n"
            f"實際執行方法：{'、'.join(self.attempted_methods) or '未執行'}\n"
            f"成功方法：{self.successful_method or '無'}\n"
            f"失敗原因：{'、'.join(self.failure_reasons[:3]) or '無'}"
        )


def _url_or_text(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _qr_is_complete(points, width: int, height: int) -> Optional[bool]:
    """Conservative completeness check based on detected corner locations."""
    if points is None:
        return None
    try:
        pts = points.reshape(-1, 2)
        if len(pts) < 4:
            return None
        margin = max(2, int(min(width, height) * 0.002))
        return bool(
            (pts[:, 0] >= margin).all()
            and (pts[:, 0] <= width - 1 - margin).all()
            and (pts[:, 1] >= margin).all()
            and (pts[:, 1] <= height - 1 - margin).all()
        )
    except Exception:
        return None


def decode_qr(image_path: str) -> QRResult:
    """Decode QR codes with independent decoders and multiple real transforms."""
    attempted: list[str] = []
    failures: list[str] = []
    detected = False
    complete: Optional[bool] = None
    detected_points = None

    try:
        import cv2
        import numpy as np
    except ImportError:
        return QRResult(None, False, None, [], None, ["QR 解碼套件未安裝"])

    image = cv2.imread(str(image_path))
    if image is None:
        return QRResult(None, False, None, [], None, ["圖片無法讀取"])

    height, width = image.shape[:2]

    # Decoder 1: ZXing-C++ is packaged as a wheel and does not require libzbar.
    try:
        import zxingcpp

        transforms = [
            ("ZXing 原圖", image),
            ("ZXing 灰階放大 2 倍", cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)),
            ("ZXing 自適應二值化", cv2.adaptiveThreshold(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 7)),
            ("ZXing 反色", cv2.bitwise_not(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))),
        ]
        for method, candidate in transforms:
            attempted.append(method)
            results = zxingcpp.read_barcodes(candidate)
            if results:
                for result in results:
                    if "qrcode" not in str(getattr(result, "format", "")).lower():
                        continue
                    detected = True
                    value = _url_or_text(getattr(result, "text", None))
                    if value:
                        return QRResult(value, True, True, attempted, method, [])
    except ImportError:
        failures.append("ZXing 套件不可用")
    except Exception:
        failures.append("ZXing 無法解碼")

    # Decoder 2: OpenCV, including threshold and sharpening strategies.
    detector = cv2.QRCodeDetector()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpened = cv2.filter2D(
        gray,
        -1,
        np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32),
    )
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates = [
        ("OpenCV 原圖", image),
        ("OpenCV 灰階放大 3 倍", cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)),
        ("OpenCV 銳化", sharpened),
        ("OpenCV 全域二值化", otsu),
    ]

    for method, candidate in candidates:
        attempted.append(method)
        try:
            value, points, _ = detector.detectAndDecode(candidate)
            if points is not None:
                detected = True
                detected_points = points
            value = _url_or_text(value)
            if value:
                scaled_height, scaled_width = candidate.shape[:2]
                complete = _qr_is_complete(points, scaled_width, scaled_height)
                return QRResult(value, True, complete, attempted, method, [])
        except Exception:
            continue

    # Try four rotations after the independent strategies above.
    for degrees, candidate in (
        (90, cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)),
        (180, cv2.rotate(image, cv2.ROTATE_180)),
        (270, cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)),
    ):
        method = f"OpenCV 旋轉 {degrees} 度"
        attempted.append(method)
        try:
            value, points, _ = detector.detectAndDecode(candidate)
            if points is not None:
                detected = True
            value = _url_or_text(value)
            if value:
                return QRResult(value, True, _qr_is_complete(points, candidate.shape[1], candidate.shape[0]), attempted, method, [])
        except Exception:
            continue

    if detected_points is not None:
        complete = _qr_is_complete(detected_points, width, height)
    if detected:
        failures.append("多種解碼策略仍無內容")
        if complete is False:
            failures.insert(0, "裁切或邊緣不完整")
    else:
        failures.append("未偵測到 QR Code")

    return QRResult(None, detected, complete, attempted, None, failures[:3])


def _image_data_url(image_path: str) -> str:
    suffix = Path(image_path).suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def analyze_medication_image(client, image_path: str, model: str = "gpt-4.1") -> dict:
    """Run real QR decoding, then ask GPT-4.1 to transcribe the medication bag."""
    qr = decode_qr(image_path)
    response = client.responses.create(
        model=model,
        instructions=ANALYSIS_PROMPT,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "請分析這張藥袋圖片。QR Code 已由後端程式實際解碼；"
                            "請逐字使用以下結果，不得從圖片猜測網址：\n\n"
                            + qr.prompt_context()
                        ),
                    },
                    {"type": "input_image", "image_url": _image_data_url(image_path)},
                ],
            }
        ],
        temperature=0.1,
        max_output_tokens=3000,
        top_p=1,
        store=False,
    )
    display_text = (getattr(response, "output_text", "") or "").strip()
    if not display_text:
        raise RuntimeError("OpenAI 沒有返回藥袋辨識內容")
    return {
        "display_text": display_text,
        "model": model,
        "qr": asdict(qr),
    }
