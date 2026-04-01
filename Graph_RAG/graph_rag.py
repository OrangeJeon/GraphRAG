import ollama
from neo4j import GraphDatabase, basic_auth
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j.time import Date


# ── Ollama LLM ────────────────────────────────────────────────────────────────
class LLMResponse:
    def __init__(self, content):
        self.content = content

class OllamaLLM(LLMInterface):
    def __init__(self, model_name):
        self.model_name = model_name

    
    def invoke(self, input, **kwargs):
        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": str(input)}]
        )
        content = response['message']['content']

        # "QUERY:" 접두사 제거
        if "QUERY:" in content:
            content = content.split("QUERY:")[-1].strip()

        # 코드블록 제거 (```cypher ... ``` 형태)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("cypher"):
                content = content[len("cypher"):].strip()

        return LLMResponse(content=content)

    async def ainvoke(self, input, **kwargs):
        return self.invoke(input, **kwargs)


# ── Neo4j 연결 ────────────────────────────────────────────────────────────────
driver = GraphDatabase.driver(
    "neo4j://127.0.0.1:7687",
    auth=basic_auth("neo4j", "06180618")
)

llm = OllamaLLM(model_name="tinyllama")


# ── 스키마 추출 ───────────────────────────────────────────────────────────────
def get_node_datatype(value):
    if isinstance(value, str):   return "STRING"
    elif isinstance(value, int):   return "INTEGER"
    elif isinstance(value, float): return "FLOAT"
    elif isinstance(value, bool):  return "BOOLEAN"
    elif isinstance(value, list):  return f"LIST[{get_node_datatype(value[0])}]" if value else "LIST"
    elif isinstance(value, Date):  return "DATE"
    else: return "UNKNOWN"

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
            key   = record["key"]
            if label not in schema["nodes"]:
                schema["nodes"][label] = {}
            schema["nodes"][label][key] = get_node_datatype(record["sample_value"])
        for record in relationship:
            rel_type = record["rel_type"]
            key      = record["key"]
            if rel_type not in schema["relationship"]:
                schema["relationship"][rel_type] = {}
            schema["relationship"][rel_type][key] = get_node_datatype(record["sample_value"])
        for record in rel_direction:
            schema["relations"].append(
                f"(:{record['start_label'][0]})=[:{record['rel_type']}]->(:{record['end_label'][0]})"
            )
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


schema = get_schema("neo4j://127.0.0.1:7687", "neo4j", "06180618")
neo4j_schema = format_schema(schema)


# ── Examples ──────────────────────────────────────────────────────────────────
examples = [
    "계획급수인구는? QUERY: MATCH (c:Chunk) WHERE c.content CONTAINS '계획급수인구' RETURN c.heading_path, c.content LIMIT 3",
    "백곡정수장 개량 계획은? QUERY: MATCH (c:Chunk) WHERE c.content CONTAINS '백곡정수장' RETURN c.heading_path, c.content LIMIT 3",
    "비상연계 방안은? QUERY: MATCH (c:Chunk) WHERE c.heading_path CONTAINS '비상연계' RETURN c.heading_path, c.content LIMIT 3",
    "수질관리 계획 알려줘 QUERY: MATCH (c:Chunk) WHERE c.heading_path CONTAINS '수질관리' RETURN c.heading_path, c.content LIMIT 3",
    "5장 내용은? QUERY: MATCH (c:Chunk) WHERE c.heading_path CONTAINS '제 5 장' RETURN c.heading_path, c.content LIMIT 5",
]



# ── Retriever ─────────────────────────────────────────────────────────────────
retriever = Text2CypherRetriever(
    driver=driver,
    llm=llm,
    neo4j_schema=neo4j_schema,
    examples=examples,
    neo4j_database="neo4j",
)

query_text = "백곡정수장 개량 계획 알려줘"
search_result = retriever.search(query_text=query_text)

print(search_result)