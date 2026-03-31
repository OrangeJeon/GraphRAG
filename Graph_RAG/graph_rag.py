import ollama
from neo4j import GraphDatabase, basic_auth, READ_ACCESS
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j import GraphDatabase
from neo4j.time import Date

# Ollama LLM 클래스 정의
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
        return LLMResponse(content = response['message']['content'])

    async def ainvoke(self, input, **kwargs):
        return self.invoke(input, **kwargs)

# Neo4j 연결
driver = GraphDatabase.driver(
    "neo4j://127.0.0.1:7687",
    auth=basic_auth("neo4j", "06180618"))

llm = OllamaLLM(model_name="tinyllama")

def get_node_datatype(value):
    """
    입력된 노드 value의 데이터 타입을 반환
    """

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
    """
    Graph DB의 정보를 받아 노드 및 관계의 프로퍼티를 추출하고 스키마 딕셔너리를 반환
    """

    driver = GraphDatabase.driver(
        uri, 
        auth=basic_auth("neo4j", "06180618")
    )

    with driver.session() as session:
        #노드 프로퍼티 및 타입 추출
        node_query="""
        MATCH (n)
        WITH DISTINCT labels(n) AS node_labels, keys(n) AS property_keys, n
        UNWIND node_labels AS label
        UNWIND property_keys AS key
        RETURN label, key, n[key] AS sample_value
        """
        nodes = session.run(node_query)

        #관계 프로퍼티 및 타입 추출
        rel_query = """
        MATCH ()-[r]->()
        WITH DISTINCT type(r) AS rel_type, keys(r) AS property_keys, r
        UNWIND property_keys AS key
        RETURN rel_type, key, r[key] AS sample_value
        """
        relationship = session.run(rel_query)

        #관계 유형 및 방향 추출
        rel_direction_query = """
        MATCH (a)-[r]->(b)
        RETURN DISTINCT labels(a) AS start_label, type(r) AS rel_type, labels(b) AS end_label
        ORDER BY start_label, rel_type, end_label
        """
        rel_direction = session.run(rel_direction_query)

        #스키마 딕셔너리 생성
        schema = {"nodes": {}, "relationship": {}, "relations": []}

        for record in nodes:
            label = record["label"]
            key = record["key"]
            sample_value = record["sample_value"] #데이터 타입을 추론하기 위한 샘플
            inferred_type = get_node_datatype(sample_value)
            if label not in schema["nodes"]:
                schema["nodes"][label] = {}
            schema["nodes"][label][key] = inferred_type
        
        for record in relationship:
            rel_type = record["rel_type"]
            key = record["key"]
            sample_value = record["sample_value"]
            inferred_type = get_node_datatype(sample_value)
            if rel_type not in schema["relationship"]:
                schema["relationship"][rel_type] = {}
            schema["relationship"][rel_type][key] = inferred_type

        for record in rel_direction:
            start_label = record["start_label"][0]
            rel_type = record["rel_type"]
            end_label = record["end_label"][0]
            schema["relations"].append(f"(:{start_label})=[:{rel_type}]->(:{end_label})")
        return schema
    
def format_schema(schema):
        """
        스키마 딕셔너리를 LLM에 제공하기 위해 원하는 형태로 formatting
        """
        result = []

        #노드 프로퍼티 출력
        result.append("Node Properties")
        for label, properties in schema["nodes"].items():
            props = ", ".join(f"{k}: {v}" for k, v in properties.items())
            result.append(f"{label} {{{props}}}")

        #관계 프로퍼티 추가
        result.append("Relationship Properties")
        for rel_type, properties in schema["relationship"].items():
            props = ",".join(f"{k}, {v}" for k, v in properties.items())
            result.append(f"{rel_type} {{{props}}}")

        #관계 프로퍼티 출력
        result.append("The Relationship: ")
        for relation in schema["relations"]:
            result.append(relation)
        return "\n".join(result)

#print("get_schema 시작")
schema = get_schema("neo4j://127.0.0.1:7687", "neo4j", "06180618")
#print("get_schema 완료")
neo4j_schema = format_schema(schema)
#print("format_schema 완료")
#print(neo4j_schema)

examples = [
   "댐 및 수도시설 관련 사업관리는? QUERY: MATCH (a:Article) WHERE a.title CONTAINS '댐' OR a.title CONTAINS '사업관리' RETURN a.content",
    "안전관리 규정은? QUERY: MATCH (a:Article) WHERE a.title CONTAINS '안전관리' RETURN a.content",
    "제2장에 속하는 조항은? QUERY: MATCH (a:Article)-[:BELONGS_TO_CHAPTER]->(c:Chapter) WHERE c.name CONTAINS '제2장' RETURN a.title, a.content",
]

retriever = Text2CypherRetriever(
    driver = driver,
    llm = llm,
    neo4j_schema=neo4j_schema,
    examples= examples,
    neo4j_database="neo4j",
)

query_text = "댐 및 수도시설 관련 사업관리 알려줘"
search_result = retriever.search(query_text=query_text)

print(search_result)