"""Start the MCP server as a subprocess and call both tools over stdio, as an MCP client would.

The four sample documents are ingested into a temporary vector store first, so
this never touches data/chroma_db.

Run:  python bench/mcp_stdio_check.py
"""
import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
tmp = tempfile.mkdtemp(prefix="rag_mcp_check_")
env = {**os.environ, "CHROMA_DB_PATH": os.path.join(tmp, "chroma"), "EXPERIMENTS_DB_PATH": os.path.join(tmp, "experiments.db")}

subprocess.run(
    [sys.executable, "-c",
     "import pathlib; from app.services import ingest_service as i; "
     "[i.ingest_file(str(p), original_filename=p.name) for p in sorted(pathlib.Path('data/sample_docs').iterdir())]"],
    cwd=ROOT, env=env, check=True, capture_output=True,
)


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(ROOT), env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("server:", init.serverInfo.name, "| protocol:", init.protocolVersion)
            print("tools:", [t.name for t in (await session.list_tools()).tools])
            res = await session.call_tool("check_equipment_status", {"equipment_id": "PUMP-01"})
            print("check_equipment_status(PUMP-01):", res.content[0].text)
            res = await session.call_tool("search_documents", {"query": "What is the maximum flow rate?", "top_k": 2})
            print("search_documents:", res.content[0].text[:200].replace("\n", " "), "...")


asyncio.run(main())
