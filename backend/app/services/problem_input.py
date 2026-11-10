from pathlib import Path
from io import BytesIO


class ProblemInputError(ValueError):
    pass


def extract_problem_text(filename: str, content_type: str, data: bytes) -> tuple[str, str]:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".txt" or content_type == "text/plain":
        try:
            text = data.decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise ProblemInputError("TXT 文件编码无法识别，请使用 UTF-8 编码。") from exc
        source_type = "txt"
    elif suffix == ".pdf" or content_type == "application/pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as exc:
            raise ProblemInputError("PDF 解析失败，请确认文件未损坏且未加密。") from exc
        source_type = "pdf"
        if not text:
            raise ProblemInputError("这个 PDF 没有可提取的文字，可能是扫描件；扫描件 OCR 将在下一阶段接入。")
    elif suffix in {".png", ".jpg", ".jpeg", ".webp"} or content_type.startswith("image/"):
        try:
            from PIL import Image
            import pytesseract
            image = Image.open(BytesIO(data))
            text = pytesseract.image_to_string(image, lang="chi_sim+eng").strip()
        except ImportError as exc:
            raise ProblemInputError("图片 OCR 依赖尚未安装。请安装 Pillow、pytesseract 和系统 Tesseract（含 chi_sim 语言包）。") from exc
        except Exception as exc:
            raise ProblemInputError("图片识别失败，请上传清晰的 JPG 或 PNG 题目图片。") from exc
        source_type = "image"
        if not text:
            raise ProblemInputError("未能从图片中识别出题目文字，请尝试更清晰、无遮挡的图片。")
    else:
        raise ProblemInputError("仅支持 TXT、可复制文字的 PDF、PNG、JPG、WEBP 文件。")
    if len(text) > 12000:
        raise ProblemInputError("题目内容过长，请控制在 12000 字以内。")
    if len(text.strip()) < 3:
        raise ProblemInputError("没有识别到有效题目内容。")
    return text, source_type
