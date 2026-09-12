import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ImageOCRSniffer:
    _engine = None
    _engine_type = None

    @classmethod
    def get_engine(cls):
        if cls._engine is not None:
            return cls._engine

        # Try RapidOCR first (very fast on ONNX)
        try:
            from rapidocr_onnxruntime import RapidOCR
            cls._engine = RapidOCR()
            cls._engine_type = "rapidocr"
            logger.info("RapidOCR initialized for image CF sniping.")
            return cls._engine
        except Exception:
            pass

        # Try EasyOCR fallback
        try:
            import easyocr
            cls._engine = easyocr.Reader(['th', 'en'], gpu=False)
            cls._engine_type = "easyocr"
            logger.info("EasyOCR initialized for image CF sniping.")
            return cls._engine
        except Exception as e:
            logger.warning(f"No OCR engine available: {e}")
            return None

    @classmethod
    def extract_text_from_image(cls, image_path_or_bytes) -> str:
        engine = cls.get_engine()
        if not engine:
            return ""

        try:
            if cls._engine_type == "rapidocr":
                result, _ = engine(image_path_or_bytes)
                if result:
                    # Result format: [[box, text, score], ...]
                    extracted_lines = [item[1] for item in result]
                    return " ".join(extracted_lines)
            elif cls._engine_type == "easyocr":
                result = engine.readtext(image_path_or_bytes)
                extracted_lines = [item[1] for item in result]
                return " ".join(extracted_lines)
        except Exception as e:
            logger.error(f"OCR failed to process image: {e}")

        return ""
