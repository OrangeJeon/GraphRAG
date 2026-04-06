from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator
import asyncio
import ollama

from neo4j import GraphDatabase, basic_auth
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j.time import Date


# ─────────────────────────────────────────────────────────
# FastAPI app
# ────────────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────
# Request schema
# ────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str
    history: Optional[List[Message]] = []


# ─────────────────────────────────────────────────────────
# Ollama LLM wrapper
# ────────────────────────────────────────────────────────
class LLMResponse:
    def __init__(self, content: str):
        self.content = content


class OllamaLLM(LLMInterface):
    def __init__(self, model_name: str):
        self.model_name = model_name

    def invoke(self, input, **kwargs):
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate Neo4j Cypher queries only. "
                        "Return only a valid Cypher query. "
                        "Do not explain anything."
                    ),
                },
                {"role": "user", "content": str(input)},
            ],
            options={"temperature": 0},
        )

        content = response["message"]["content"].strip()

        if "QUERY:" in content:
            content = content.split("QUERY:")[-1].strip()

        if "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1].strip()
                if content.lower().startswith("cypher"):
                    content = content[6:].strip()

        return LLMResponse(content=content)

    async def ainvoke(self, input, **kwargs):
        return self.invoke(input, **kwargs)


# ─────────────────────────────────────────────────────────
# Neo4j schema helpers
# ────────────────────────────────────────────────────────
def get_node_datatype(value):
    if isinstance(value, str):
        return "STRING"
    elif isinstance(value, int):
        return "INTEGER"
    elif isinstance(value, float):
        return "FLOAT"
    elif isinstance(value, bool):
        return "BOOLEAN"
    elif isinstance(value, list):
        return f"LIST[{get_node_datatype(value[0])}]" if value else "LIST"
    elif isinstance(value, Date):
        return "DATE"
    else:
        return "UNKNOWN"


def get_schema(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
    with driver.session() as session:
        nodes = session.run("""
            MATCH (n)
            WITH DISTINCT labels(n) AS node_labels, keys(n) AS property_keys, n
            UNWIND node_labels AS label
            UNWIND property_keys AS key
            RETURN label, key, n[key] AS sample_value
        """)

        relationship = session.run("""
            MATCH ()-[r]->()
            WITH DISTINCT type(r) AS rel_type, keys(r) AS property_keys, r
            UNWIND property_keys AS key
            RETURN rel_type, key, r[key] AS sample_value
        """)

        rel_direction = session.run("""
            MATCH (a)-[r]->(b)
            RETURN DISTINCT labels(a) AS start_label, type(r) AS rel_type, labels(b) AS end_label
            ORDER BY start_label, rel_type, end_label
        """)

        schema = {"nodes": {}, "relationship": {}, "relations": []}

        for record in nodes:
            label = record["label"]
            key = record["key"]
            if label not in schema["nodes"]:
                schema["nodes"][label] = {}
            schema["nodes"][label][key] = get_node_datatype(record["sample_value"])

        for record in relationship:
            rel_type = record["rel_type"]
            key = record["key"]
            if rel_type not in schema["relationship"]:
                schema["relationship"][rel_type] = {}
            schema["relationship"][rel_type][key] = get_node_datatype(record["sample_value"])

        for record in rel_direction:
            if record["start_label"] and record["end_label"]:
                schema["relations"].append(
                    f"(:{record['start_label'][0]})=[:{record['rel_type']}]->(:{record['end_label'][0]})"
                )

    driver.close()
    return schema


def format_schema(schema):
    result = ["Node Properties"]

    for label, properties in schema["nodes"].items():
        props = ", ".join(f"{k}: {v}" for k, v in properties.items())
        result.append(f"{label} {{{props}}}")

    result.append("Relationship Properties")
    for rel_type, properties in schema["relationship"].items():
        props = ", ".join(f"{k}: {v}" for k, v in properties.items())
        result.append(f"{rel_type} {{{props}}}")

    result.append("The Relationship:")
    for relation in schema["relations"]:
        result.append(relation)

    return "\n".join(result)


# ─────────────────────────────────────────────────────────
# Global setup
# ────────────────────────────────────────────────────────
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "06180618"
OLLAMA_MODEL = "phi3:mini"
ANSWER_MODEL = "phi3:mini"

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD)
)

llm = OllamaLLM(model_name=OLLAMA_MODEL)

schema = get_schema(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
neo4j_schema = format_schema(schema)

examples = [
    "USER INPUT: '계획급수인구는?' QUERY: MATCH (c:Chunk) WHERE c.content CONTAINS '계획급수인구' RETURN c.heading_path, c.content LIMIT 3",
    "USER INPUT: '백곡정수장 개량 계획은?' QUERY: MATCH (c:Chunk) WHERE c.content CONTAINS '백곡정수장' RETURN c.heading_path, c.content LIMIT 3",
    "USER INPUT: '비상연계 방안은?' QUERY: MATCH (c:Chunk) WHERE c.heading_path CONTAINS '비상연계' RETURN c.heading_path, c.content LIMIT 3",
    "USER INPUT: '5장 내용은?' QUERY: MATCH (c:Chunk) WHERE c.heading_path CONTAINS '제 5 장' RETURN c.heading_path, c.content LIMIT 5",
    "USER INPUT: '이미지가 있는 항목은?' QUERY: MATCH (c:Chunk)-[:HAS_IMAGE]->(img:Image) RETURN c.heading_path, img.image_path LIMIT 5",
]

retriever = Text2CypherRetriever(
    driver=driver,
    llm=llm,
    neo4j_schema=neo4j_schema,
    examples=examples,
    neo4j_database="neo4j",
)


# ─────────────────────────────────────────────────────────
# Helper: retrieval result -> context text
# ────────────────────────────────────────────────────────
def build_context_from_search_result(search_result) -> str:
    if not search_result or not getattr(search_result, "items", None):
        return "검색 결과가 없습니다."

    lines = []
    for idx, item in enumerate(search_result.items, start=1):
        lines.append(f"[검색결과 {idx}]")
        lines.append(str(item.content))
        lines.append("")

    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────────────
# Helper: answer stream
# ────────────────────────────────────────────────────────
async def generate_answer_stream(query: str, context: str) -> AsyncGenerator[str, None]:
    system_prompt = (
        "당신은 K-water(한국수자원공사)의 마스코트 방울이입니다. "
        "진천군 수도정비 기본계획 문서를 기반으로 검색된 결과를 참고해 답변합니다. "
        "밝고 친근한 말투로 답변하되, 과장하지 말고 근거 기반으로 설명하세요. "
        "모르면 모른다고 말하세요. 한국어로 답변하세요."
    )

    user_prompt = f"""
사용자 질문:
{query}

검색 결과:
{context}

지침:
- 검색 결과를 바탕으로만 답변하세요.
- 핵심 내용을 먼저 간단히 설명하세요.
- 필요하면 항목별로 정리하세요.
- 방울이다운 친근한 표현은 과하지 않게 사용하세요.
"""

    stream = ollama.chat(
        model=ANSWER_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
        options={"temperature": 0.3},
    )

    for chunk in stream:
        text = chunk.get("message", {}).get("content", "")
        if text:
            yield text
        await asyncio.sleep(0)


# ─────────────────────────────────────────────────────────
# API route
# ────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(req: ChatRequest):
    query = req.query.strip()

    if not query:
        async def empty_stream():
            yield "질문을 입력해주세요."
        return StreamingResponse(empty_stream(), media_type="text/plain; charset=utf-8")

    try:
        search_result = retriever.search(query_text=query)
        context = build_context_from_search_result(search_result)

        return StreamingResponse(
            generate_answer_stream(query, context),
            media_type="text/plain; charset=utf-8"
        )

    except Exception as e:
        error_message = str(e)

        async def error_stream():
            yield f"앗, 검색 중 오류가 발생했어요. ({error_message})"

        return StreamingResponse(
            error_stream(),
            media_type="text/plain; charset=utf-8"
        )