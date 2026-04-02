import re
line = "7.2 유지관리 항목"
print(any(p.match(line.strip()) for p in HEADING_PATTERNS))


import json

with open(r"C:\Users\kwater\Downloads\진천군수도정비기본계획보고서(2021).chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"총 chunk 수: {len(chunks)}\n")
for c in chunks:
    print(f"[{c['chunk_id']}]")
    print(f"  heading_path: {c['heading_path']}")
    print(f"  pages: {c['pages']}")
    print(f"  content 길이: {len(c['content'])}자")
    print()