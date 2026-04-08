"""
(Document)-[:HAS_CHUNK]->(Chunk)
(Chunk)-[:HAS_IMAGE]->(Image)
"""

import json
from neo4j import GraphDatabase, basic_auth

driver = GraphDatabase.driver("neo4j://127.0.0.1:7687", auth=basic_auth("neo4j", "06180618"))

with open(r"C:\python\Graph_RAG\진천군수도정비기본계획보고서(2021).chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)


def insert_chunk(tx, chunk):
    # Document + Chunk 노드 생성 및 관계 연결
    tx.run("""
        MERGE (doc:Document {title: $source})
        MERGE (c:Chunk {chunk_id: $chunk_id})
        SET c.source       = $source,
            c.heading      = $heading,
            c.heading_path = $heading_path,
            c.content      = $content,
            c.pages        = $pages
        MERGE (doc)-[:HAS_CHUNK]->(c)
    """,
        source=chunk["source"],
        chunk_id=chunk["chunk_id"],
        heading=chunk["heading"],
        heading_path=chunk["heading_path"],
        content=chunk["content"],
        pages=chunk["pages"],
    )

    # 이미지 노드 생성 및 Chunk와 연결
    for img_path in chunk.get("image_paths", []):
        tx.run("""
            MATCH (c:Chunk {chunk_id: $chunk_id})
            MERGE (img:Image {image_path: $image_path})
            SET img.source = $source
            MERGE (c)-[:HAS_IMAGE]->(img)
        """,
            chunk_id=chunk["chunk_id"],
            image_path=img_path,
            source=chunk["source"],
        )


with driver.session() as session:
    for i, chunk in enumerate(chunks):
        session.execute_write(insert_chunk, chunk)
        print(f"[{i+1}/{len(chunks)}] {chunk['chunk_id']} 완료")

driver.close()
print("\n전체 업로드 완료!")