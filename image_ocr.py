# image_ocr.py

import pytesseract
from PIL import Image

# If Tesseract is not in PATH, set the full path:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_image(image_path: str) -> str:
    """
    Runs OCR using Tesseract on an image path.
    Returns raw OCR text.
    """
    img = Image.open(image_path)
    return pytesseract.image_to_string(img)


def extract_text_from_pil_image(img: Image.Image) -> str:
    """
    Runs OCR using Tesseract on a PIL image object.
    Useful for FastAPI uploads.
    """
    return pytesseract.image_to_string(img)


if __name__ == "__main__":
    text = extract_text_from_image("passport_sample.jpg")
    print("----- OCR OUTPUT -----")
    print(text)
