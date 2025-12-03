# client.py

from image_ocr import extract_text_from_image
from mrz_extractor import extract_mrz_from_ocr_text, parse_mrz
import json

raw_text = extract_text_from_image("fr-1.jpg")
mrz = extract_mrz_from_ocr_text(raw_text)
parsed = parse_mrz(mrz)

print(json.dumps(parsed, indent=2))
