import re
import json
import sys
from pathlib import Path
import pdfplumber
import fitz


def is_useful_image(base_image):
    w = base_image.get("width", 0)
    h = base_image.get("height", 0)
    size = len(base_image["image"])

    if w < 200 or h < 200:
        return False
    if h <= 210 and w > 500:
        return False
    if h > 0 and w / h > 4 and size < 30000:
        return False
    if size < 15000:
        return False
    return True


def extract_images(pdf_path: str) -> dict:
    doc_name = Path(pdf_path).stem
    save_dir = Path(pdf_path).parent / f"{doc_name}_images"
    save_dir.mkdir(exist_ok=True)

    page_images = {}
    fitz_doc = fitz.open(pdf_path)

    for page_idx in range(len(fitz_doc)):
        page_num = page_idx + 1
        page_images[page_num] = []
        for img_idx, img_info in enumerate(fitz_doc[page_idx].get_images(full=True)):
            xref = img_info[0]
            base_image = fitz_doc.extract_image(xref)
            if not is_useful_image(base_image):
                continue

            img_path = save_dir / f"p{page_num}_img{img_idx+1}.jpg"
            pix = fitz.Pixmap(fitz_doc, xref)
            pix = fitz.Pixmap(fitz.csRGB, pix)
            pix = fitz.Pixmap(pix, 0)
            pix.save(str(img_path))
            page_images[page_num].append(str(img_path))

    fitz_doc.close()
    return page_images


def is_toc_line(line: str) -> bool:
    stripped = line.strip()
    if re.search(r"\s+\d+-\d+\s*$", stripped): return True
    if re.search(r"[·﹒．]{3,}", stripped): return True
    if re.search(r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\s*-\s*\d+", stripped): return True
    return False


def extract_page_content(pdf_path: str) -> list:
    pages_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            table_bboxes = [t.bbox for t in tables]
            raw_tables = page.extract_tables()

            md_tables = []
            for table_data in raw_tables:
                if not table_data:
                    continue
                rows = []
                for i, row in enumerate(table_data):
                    cleaned = [str(c).strip().replace("\n", " ") if c else "" for c in row]
                    rows.append("| " + " | ".join(cleaned) + " |")
                    if i == 0:
                        rows.append("| " + " | ".join(["---"] * len(cleaned)) + " |")
                md_tables.append("\n".join(rows))

            if table_bboxes:
                words = page.extract_words()
                filtered = []
                for word in words:
                    wx = (word["x0"] + word["x1"]) / 2
                    wy = (word["top"] + word["bottom"]) / 2
                    in_table = any(
                        b[0] <= wx <= b[2] and b[1] <= wy <= b[3]
                        for b in table_bboxes
                    )
                    if not in_table:
                        filtered.append(word["text"])
                text = " ".join(filtered).strip()
            else:
                text = (page.extract_text() or "").strip()

            cleaned_lines = [l for l in text.splitlines() if not is_toc_line(l)]
            text = "\n".join(cleaned_lines)

            pages_data.append({
                "page": page_num,
                "text": text,
                "tables": md_tables,
            })

    return pages_data


HEADING_PATTERNS = [
    re.compile(r"^\s*\d+\.\d+\s+.{2,}"),
    re.compile(r"^\s*\d+\.\s+.{2,}"),
    re.compile(r"^제\s*\d+\s*장\s+.+"),
    re.compile(r"^제\s*\d+\s*절\s+.+"),
    re.compile(r"^제\s*\d+\s*조\s*[(\（].+"),
]

def is_heading(line: str) -> bool:
    stripped = line.strip()
    if is_toc_line(stripped):
        return False
    if re.match(r"^\d{4}\.", stripped):
        return False
    if re.match(r"^\d+\.\s+[「『\"(（]", stripped):
        return False
    m = re.match(r"^\d+\.\s+(.+)", stripped)
    if m and not re.match(r"^\d+\.\d", stripped) and len(m.group(1)) > 20:
        return False
    return any(p.match(stripped) for p in HEADING_PATTERNS)

def update_heading_stack(stack: list, new_heading: str) -> list:
    if re.match(r"^제\s*\d+\s*장", new_heading):
        return [new_heading]
    elif re.match(r"^제\s*\d+\s*절", new_heading):
        return [s for s in stack if re.match(r"^제\s*\d+\s*장", s)] + [new_heading]
    elif re.match(r"^\s*\d+\.\d+", new_heading):
        base = [s for s in stack if not re.match(r"^\s*\d+\.\d+", s)]
        return base + [new_heading]
    elif re.match(r"^\s*\d+\.", new_heading):
        base = [s for s in stack if re.match(r"^제\s*\d+\s*[장절]", s)]
        return base + [new_heading]
    else:
        return stack + [new_heading]


def split_into_articles(pages_data: list, page_images: dict, doc_name: str, toc_end_page: int = None) -> list:
    articles = []
    chunk_count = 0
    heading_stack = [doc_name]
    current_heading = doc_name
    current_heading_path = doc_name
    current_lines = []
    current_tables = []
    current_pages = []

    if toc_end_page is None:
        toc_end_page = max(5, len(pages_data) // 50)

    def flush():
        nonlocal chunk_count
        text_part = "\n".join(current_lines).strip()
        table_part = "\n\n".join(current_tables)
        content = "\n\n".join(filter(None, [text_part, table_part]))
        if not content:
            return
        images = []
        for p in current_pages:
            images.extend(page_images.get(p, []))
        chunk_count += 1
        articles.append({
            "chunk_id": f"{doc_name}__chunk{chunk_count:04d}__001",
            "source": doc_name,
            "heading": current_heading,
            "heading_path": current_heading_path,
            "content": content,
            "pages": list(dict.fromkeys(current_pages)),
            "image_paths": images,
        })

    for page_data in pages_data:
        current_tables.extend(page_data["tables"])
        if page_data["page"] not in current_pages:
            current_pages.append(page_data["page"])

        for line in page_data["text"].splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if is_heading(stripped):
                if page_data["page"] <= toc_end_page:
                    continue
                flush()
                current_lines = []
                current_tables = list(page_data["tables"])
                current_pages = [page_data["page"]]
                current_heading = stripped
                heading_stack = update_heading_stack(heading_stack, stripped)
                current_heading_path = " > ".join(heading_stack)
            else:
                current_lines.append(stripped)

    flush()
    return articles


def process_pdf(pdf_path: str) -> list:
    doc_name = Path(pdf_path).stem
    print(f"\n처리 시작: {doc_name}")

    print("[1] 이미지 추출 중...")
    page_images = extract_images(pdf_path)
    print(f"    -> {sum(len(v) for v in page_images.values())}개")

    print("[2] 텍스트/표 추출 중...")
    pages_data = extract_page_content(pdf_path)
    print(f"    -> {len(pages_data)}페이지")

    print("[3] 청킹 중...")
    chunks = split_into_articles(pages_data, page_images, doc_name, toc_end_page=7)
    print(f"    -> {len(chunks)}개 chunk")

    json_path = Path(pdf_path).with_suffix(".chunks.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"\n완료: {json_path}")

    return chunks


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python chunks.py <pdf_path>")
        sys.exit(1)
    process_pdf(sys.argv[1])