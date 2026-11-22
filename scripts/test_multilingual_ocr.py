
import time
from pathlib import Path

import pytesseract
from PIL import Image
from pytesseract import Output

SOURCE_DIR = Path.home() / "Pictures" / "MobScreenshots"
TARGET = "Screenshot_20250426-125811"

matches = list(SOURCE_DIR.glob(TARGET + ".*"))

if not matches:
    raise FileNotFoundError(f"Could not find {TARGET}")

image_path = matches[0]

print("=" * 80)
print("IMAGE:", image_path.name)
print("=" * 80)

with Image.open(image_path) as img:
    image = img.convert("RGB")

# 1. Check script detection
print("\n========== OSD DETECTION ==========")

try:
    print(pytesseract.image_to_osd(image))
except Exception as error:
    print("OSD ERROR:", error)

# 2. Compare multilingual configurations
configurations = ["eng+mar", "eng+hin"]

for language in configurations:
    print(f"\n\n{'=' * 80}")
    print(f"LANGUAGE CONFIGURATION: {language}")
    print("=" * 80)

    start = time.time()

    try:
        text = pytesseract.image_to_string(
            image,
            lang=language,
            config="--psm 6"
        )

        data = pytesseract.image_to_data(
            image,
            lang=language,
            config="--psm 6",
            output_type=Output.DICT
        )

        confidences = [
            float(c)
            for c, word in zip(data["conf"], data["text"])
            if word.strip() and float(c) >= 0
        ]

        avg_confidence = (
            sum(confidences) / len(confidences)
            if confidences else 0
        )

        elapsed = time.time() - start

        print(f"Confidence: {avg_confidence:.2f}")
        print(f"Recognized words: {len(confidences)}")
        print(f"Processing time: {elapsed:.2f} seconds")
        print("\nEXTRACTED TEXT:\n")
        print(text.strip() or "[No text detected]")

    except Exception as error:
        print("ERROR:", error)

print("\n\nMultilingual test completed.")
