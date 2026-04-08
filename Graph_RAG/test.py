from neo4j import GraphDatabase, basic_auth
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.retrievers import Text2CypherRetriever
import ollama

class LLMResponse:
    def __init__(self, content: str):
        self.content = content

class OllamaLLM(LLMInterface):
    def __init__(self, model_name: str):
        self.model_name = model_name

    def invoke(self, input, **kwargs):
        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": str(input)}],
            options={"temperature": 0},
        )
        return LLMResponse(content=response["message"]["content"].strip())

    async def ainvoke(self, input, **kwargs):
        return self.invoke(input, **kwargs)

driver = GraphDatabase.driver("neo4j://127.0.0.1:7687", auth=basic_auth("neo4j", "06180618"))
llm = OllamaLLM("phi3:mini")

neo4j_schema = "Node Properties\nChunk {chunk_id: STRING, content: STRING, heading: STRING, heading_path: STRING, pages: LIST[INTEGER], source: STRING}"

retriever = Text2CypherRetriever(
    driver=driver,
    llm=llm,
    neo4j_schema=neo4j_schema,
    neo4j_database="neo4j",
)

result = retriever.search(query_text="계획급수인구는?")
print(type(result))
for item in result.items:
    print("type:", type(item))
    print("dir:", dir(item))
    print("content:", item.content)
    break