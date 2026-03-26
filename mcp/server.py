from mcp.server.fastmcp import FastMCP
import os
import warnings

# SSL 경고 무시
#warnings.filterwarnings('ignore')
#os.environ['PYTHONHTTPSVERIFY'] = '0'
#os.environ['CURL_CA_BUNDLE'] = ''
#os.environ['REQUESTS_CA_BUNDLE'] = ''

# requests 라이브러리의 SSL 검증 비활성화
#import requests
#from urllib3.exceptions import InsecureRequestWarning
#requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Notion API를 직접 호출 (notion-client 대신)
mcp = FastMCP("mcp_project")

NOTION_TOKEN = "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"
DEFAULT_PARENT_PAGE_ID = "306f6f3c474c8069b1f9e16d5d78124a"

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b

@mcp.tool()
def create_notion_page(title: str, content: str) -> dict:
    """
    Create a new page in Notion with title and content
    
    Args:
        title: Title of the new page
        content: Text content to add to the page
    
    Returns:
        Dictionary with page URL and ID
    """
    try:
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        data = {
            "parent": {"page_id": DEFAULT_PARENT_PAGE_ID},
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            },
            "children": [{
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            }]
        }
        
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=data,
            verify=False  # SSL 검증 완전 비활성화
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "page_id": result["id"],
                "url": result["url"],
                "title": title
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
# Add a dynamic greeing resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


if __name__ == "__main__":
    mcp.run(transport='stdio')