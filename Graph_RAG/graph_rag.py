import ollama
from neo4j import GraphDatabase, basic_auth
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.generation import GraphRAG
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
    "bolt://3.83.135.243:7687",
    auth=basic_auth("neo4j", "interiors-representative-cranks"))

# 쿼리
cypher_query = '''
MATCH (m:Movie {title:$movie})<-[:ACTED_IN]-(p:Person)-[:ACTED_IN]->(rec:Movie)
RETURN DISTINCT rec.title AS recommendation LIMIT 20
'''

# Neo4j 검색
with driver.session(database="neo4j") as session:
    results = session.execute_read(
        lambda tx: tx.run(cypher_query,
                          movie="The Matrix").data())
    recommendations = [record['recommendation'] for record in results]

def generate_embedding(text):
    response = ollama.embeddings(
        model='tinyllama',
        prompt= text
    )
    return response['embedding']

def add_embedding_to_movie(tx):
    result = tx.run("MATCH (m:Movie) WHERE m.tagline IS NOT NULL RETURN m.title AS title, m.tagline AS plot, elementId(m) AS id LIMIT 100")
    cnt = 0
    for record in result:
        cnt+=1
        print(cnt)
        title = record["title"]
        plot = record["plot"]
        node_id = record["id"]
        print(plot)
        print("==============")
        embedding = generate_embedding(plot)
        tx.run("MATCH (m:Movie) WHERE elementId(m) = $id SET m.plotEmbedding = $embedding",
               id = node_id, embedding = embedding)
        print(f"Updated movie '{title}' with embedding")
with driver.session() as session:
    session.execute_write(add_embedding_to_movie)

class OllamaEmbedder(Embedder):
    def __init__(self, model_name):
        self.model_name = model_name

    def embed_query(self, text):
        response = ollama.embeddings(model=self.model_name, prompt=text)
        return response['embedding']

embedder = OllamaEmbedder(model_name="tinyllama")

retriever = VectorRetriever(
    driver,
    index_name="moviePlotsEmbedding",
    embedder=embedder,
    return_properties=["title", "tagline"]  # plot → tagline으로 변경
)

#query_text = "A cowboy doll is jealous when a new spaceman figure becomes the top toy."
#retriever_result = retriever.search(query_text=query_text, top_k = 3)
#print(retriever_result)

llm = OllamaLLM(model_name="tinyllama")
rag = GraphRAG(retriever = retriever, llm = llm)

query_text = "What movies are sad romances?"
response = rag.search(query_text=query_text, retriever_config={"top_k": 5})
print(response.answer)

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
        auth=basic_auth("neo4j", "interiors-representative-cranks")
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
        schema = {"nodes": {}, "relationship": {}, "relations": {}}

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

