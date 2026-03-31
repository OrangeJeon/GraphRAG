"""
(Document) -[:HAS_ARTICLE]-> (Article)
(Article) -[:BELONGS_TO_CHAPTER]-> (Chapter)
(Article) -[:BELONGS_TO_SECTION]-> (Section)
(Article) -[:NEXT_ARTICLE]-> (Article)  # 순서 관계
"""

import json
from neo4j import GraphDatabase, basic_auth

driver = GraphDatabase.driver("neo4j://127.0.0.1:7687", auth=basic_auth("neo4j", "06180618"))

with open(r"C:\Users\kwater\Desktop\k-water\txt\chunks\댐 및 수도시설 등에 관한 재산권처리기준_chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

def insert_chunk(tx, chunk):
    tx.run("""
        MERGE (doc:Document {title: $source_file})
        MERGE (art:Article {chunk_id: $chunk_id})
        SET art.article_no = $article_no,
            art.title = $article_title,
            art.content = $content,
            art.heading_path = $heading_path
        MERGE (doc)-[:HAS_ARTICLE]->(art)
    """,
    source_file=chunk["source_file"],
    chunk_id=chunk["chunk_id"],
    article_no=chunk["article_no"],
    article_title=chunk["article_title"],
    content=chunk["content"],
    heading_path=chunk["heading_path"]
    )

    # 장 관계 별도 쿼리
    if chunk.get("chapter"):
        tx.run("""
            MATCH (art:Article {chunk_id: $chunk_id})
            MERGE (ch:Chapter {name: $chapter, document: $source_file})
            MERGE (art)-[:BELONGS_TO_CHAPTER]->(ch)
        """, chunk_id=chunk["chunk_id"], chapter=chunk["chapter"], source_file=chunk["source_file"])

    # 절 관계 별도 쿼리
    if chunk.get("section"):
        tx.run("""
            MATCH (art:Article {chunk_id: $chunk_id})
            MERGE (sec:Section {name: $section, document: $source_file})
            MERGE (art)-[:BELONGS_TO_SECTION]->(sec)
        """, chunk_id=chunk["chunk_id"], section=chunk["section"], source_file=chunk["source_file"])

with driver.session() as session:
    for chunk in chunks:
        session.execute_write(insert_chunk, chunk)
print("하나 끝")
