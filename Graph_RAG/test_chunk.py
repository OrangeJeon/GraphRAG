from neo4j import GraphDatabase, basic_auth

driver = GraphDatabase.driver(
    "bolt://127.0.0.1:7687",
    auth=basic_auth("neo4j", "06180618")
)

try:
    driver.verify_connectivity()
    print("Neo4j 연결 성공")

    with driver.session(database="neo4j") as session:
        result = session.run("RETURN 1 AS ok")
        print(result.single()["ok"])

except Exception as e:
    print("연결 실패:", repr(e))
finally:
    driver.close()