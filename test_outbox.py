import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure we're using the mock/provided text
ocr_text = "This is a letter to the Honorable Minister requesting funds for a local hospital in Belagavi."

from modules.letterbox import process_letterbox_ocr

result = process_letterbox_ocr(ocr_text, direction="outbox", tenant_id=1)
print("Result:")
print(result)
