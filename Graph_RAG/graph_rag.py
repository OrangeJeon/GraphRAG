#import os
#os.environ["OPENAI_API_KEY"] = ""
import ollama
#ollama.pull('phi3')

from neo4j import GraphDatabase, basic_auth
import openai

print("start")
response = ollama.chat(model='phi3', messages=[
    {
    'role': 'user',
    'content': 'Which movies did Tom Hanks star in?',
    },
]) 
print(response['message']['content'])


    