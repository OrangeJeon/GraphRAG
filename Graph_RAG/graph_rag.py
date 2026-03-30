import ollama
from neo4j import GraphDatabase, basic_auth
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.generation import GraphRAG

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
"""
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
"""
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

