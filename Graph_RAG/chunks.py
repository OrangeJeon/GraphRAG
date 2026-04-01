"""
pdf 문서 청킹 스크립트
-이미지, 텍스트, 표 추출
"""

import json
import re
from pathlib import Path
import pdfplumber
import fitz

#pdf 처리
def extract_from_pdf(pdf_path:str) -> list[dict]:
    chunks = []
    doc_name = Path(pdf_path).stem
    img_dir = Path(pdf_path).parent / f"{doc_name}_images"
    img_dir.mkdir(exist_ok=True)

    fitz_doc = fitz.open(pdf_path)
    page_image = {}

    for page_num in range(len(fitz_doc)):
        page = fitz_doc[page_num]
        image_list = page.get_images(full=True)
        page_image[page_num+1] = []

        for img_idx, img_info, in enumerate(image_list):
            xref = img_info[0]
            base_image = fitz_doc.extract_image(xref)
            img_bytes = base_image["image"]
            img_ext = base_image["ext"]
            img_path = img_dir/f"p{page_num+1}_img{img_idx+1}.{img_ext}"

            with open(img_path, "wb") as f:
                f.write(img_bytes)
            page_image[page_num+1].append(str(img_path))

    fitz_doc.close()

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start = 1):
            tables = page.find_tables()
            table_bboxes = [t.bbox for t in tables]
            extract_tables = page.extract_tables()

            for i, table_data in enumerate(extract_tables):
                if not table_data:
                    continue
                rows = []

                for row in table_data:
                    cleaned = [cell.strip() if cell else "" for cell in row]
                    rows.append(" | ".join(cleaned))

                chunks.append({
                    "type":"table",
                    "source": doc_name,
                    "page": page_num,
                    "table_index": i,
                    "content": "\n".join(rows)
                    "metadata": {
                        "bbox": table_bboxes[i] if i < len(table_bboxes) else None
                    }
                })

            if table_bboxes:
                words = page.extract_words()
                filtered_words = []

                for word in words:
                    in_table = False
                    for bbox in table_bboxes:
                        wx =(word["x0"] + word["x1"]) /2
                        wy =(word["top"] + word["bottom"]) / 2
                        if bbox[0]<= wx <= bbox[2] and bbox[1] <= wy <= bbox[3]:
                            in_table = True
                            break
                    if not in_table:
                        filtered_words.append(word["text"])
                text = " ".join(filtered_words).strip()
            else:
                text = (page.extract_text() or "").strip()
            
            if text:
                chunks.append({
                    "type": "text",
                    "source":doc_name,
                    "page":page_num,
                    "content":text,
                    "metadata":{}
                })

            for ing_idx, img_path in enumerate(page_image.get(page_num, [])):
                chunks.append({
                    "type":"image",
                    "source":doc_name,
                    "page":page_num,
                    "image_index":img_idx,
                    "content":f"[이미지:{Path(img_path).name}]",
                    "metadata":{"image_path": img_path}
                })
    print(f"[PDF] {doc_name} -> 청크 {len(chunks)}개 추출 완료")
    return chunks


