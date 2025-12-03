# api.py

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
from io import BytesIO

from image_ocr import extract_text_from_pil_image
from mrz_extractor import extract_mrz_from_ocr_text, parse_mrz

app = FastAPI(title="Passport MRZ Extraction API")


@app.post("/extract_mrz_from_image")
async def extract_mrz_from_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    try:
        contents = await file.read()
        img = Image.open(BytesIO(contents))

        raw_text = extract_text_from_pil_image(img)
        mrz_lines = extract_mrz_from_ocr_text(raw_text)
        parsed = parse_mrz(mrz_lines)

        return JSONResponse(content=parsed)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
