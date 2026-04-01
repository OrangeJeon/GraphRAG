import pdfplumber
import re

HEADING_PATTERNS = [
    re.compile(r"^\s*\d+\.\d+\s+.{2,}"),
    re.compile(r"^\s*\d+\.\s+.{2,}"),
    re.compile(r"^제\s*\d+\s*장\s+.+"),
    re.compile(r"^제\s*\d+\s*절\s+.+"),
    re.compile(r"^제\s*\d+\s*조\s*[(\（].+"),
]

with pdfplumber.open(r"C:\Users\kwater\Downloads\진천군수도정비기본계획보고서(2021).pdf") as pdf:
    for page_num in [592, 593, 594, 595, 600, 605]:
        text = pdf.pages[page_num - 1].extract_text() or ""
        for line in text.splitlines():
            stripped = line.strip()
            if any(p.match(stripped) for p in HEADING_PATTERNS):
                print(f"[p{page_num}] 헤딩: {repr(stripped)}")