import re

with open("backend/app/repo_scanner.py", "r") as f:
    content = f.read()

import_stmt = "import urllib.parse\n"
if "import urllib.parse" not in content:
    content = content.replace("import uuid", "import urllib.parse\nimport uuid")

resolve_method = """
    async def _resolve_username(self, query: str) -> str:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ThreatLens"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            if " " not in query:
                try:
                    res = await client.get(f"https://api.github.com/users/{urllib.parse.quote(query)}")
                    if res.status_code == 200:
                        return res.json()["login"]
                except Exception:
                    pass
            
            try:
                # Search across users and orgs
                res = await client.get("https://api.github.com/search/users", params={"q": query})
                if res.status_code == 200:
                    data = res.json()
                    if data.get("items"):
                        # Prioritize orgs
                        for item in data["items"]:
                            if item.get("type") == "Organization":
                                return item["login"]
                        return data["items"][0]["login"]
            except Exception:
                pass
                
        return query

    async def start_scan(self, username: str) -> dict[str, Any]:
        username = username.strip().strip("/")
        resolved_username = await self._resolve_username(username)
        username = resolved_username
"""

content = re.sub(r'    async def start_scan\(self, username: str\) -> dict\[str, Any\]:\n        username = username.strip\(\).strip\("/"\)', resolve_method, content)

content = content.replace(
    'return {"scan_id": scan_id, "repos_found": 0, "status": "scanning"}',
    'return {"scan_id": scan_id, "repos_found": 0, "status": "scanning", "resolved_username": username}'
)

with open("backend/app/repo_scanner.py", "w") as f:
    f.write(content)

print("Patched repo_scanner.py successfully.")
