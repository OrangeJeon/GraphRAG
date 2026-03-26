from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from typing import List
from langchain_classic import document_loaders
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import requests

#os.environ["OPENAI_API_KEY"] = "(나중에 키 여기에다가)"
os.environ["LANGCHAIN_USER_AGENT"] = "my-app-name"
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["CURL_CA_BUNDLE"] = ""
urls = [
    "https://sean-j.tistory.com/entry/LangGraph-Add-summary-of-the-conversation-history", # 멀티턴 글
    "https://sean-j.tistory.com/entry/LangGraph-Branches-for-parallel-node-execution" # 병렬 노드 글
]

docs = [WebBaseLoader(url).load()for url in urls] #데이터 수집
docs_list = [item for sublsit in docs for item in sublsit] #데이터분할

#400자 단위로 쪼개는데, 50자씩 겹치도록 한다.
text_splitter = RecursiveCharacterTextSplitter(chunk_size = 400, chunk_overlap = 50)   
doc_splits = text_splitter.split_documents(docs_list) 

#벡터 저장소
vectorstore = Chroma.from_documents(
    doc_splits,
    OpenAIEmbeddings(), #텍스트를 수학적 좌표로 변환한다. 
    collection_name="kwater" 
)

#검색기 역할
retriever = vectorstore.as_retriever()

#데이터 포맷 함수
def format_docs(docs: List[document_loaders]) -> str:  #출처확인용..?
    return "\n".join(
        [
        f"<document><content>{doc.page_content}</content><source>{doc.metadata['source']}</source></document>"
        for doc in docs
        ]
    )

@tool #AI 에이전트가 사용할 수 있는 도구

#블로그들을 검색해서 반환해라, query를 받으면 시작
def retrieve_from_blog(query: str) -> str:
    docs = retriever.invoke(query)
    formatted_docs = format_docs(docs)
    return formatted_docs

#도구 목록
tools = [retrieve_from_blog]

