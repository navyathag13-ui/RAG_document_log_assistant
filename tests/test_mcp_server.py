"""The MCP server, exercised through a real MCP client session (in-memory transport)."""
import asyncio
import json
from pathlib import Path

from mcp.shared.memory import create_connected_server_and_client_session

from app.mcp_server import mcp
from app.services import ingest_service

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_docs" / "manual.txt"


def test_mcp_client_can_list_and_call_both_tools():
    ingest_service.ingest_file(str(SAMPLE), original_filename="manual.txt")

    async def run():
        async with create_connected_server_and_client_session(mcp) as session:
            tools = await session.list_tools()
            status = await session.call_tool("check_equipment_status", {"equipment_id": "SCU-400"})
            search = await session.call_tool("search_documents", {"query": "maximum operating pressure", "top_k": 2})
            return tools, status, search

    tools, status, search = asyncio.run(run())

    assert {t.name for t in tools.tools} == {"search_documents", "check_equipment_status"}

    record = json.loads(status.content[0].text)
    assert record["status"] == "fault" and record["current_fault_codes"] == ["FAULT-T02"]

    assert not search.isError
    assert search.content[0].text.count("[chunk_id: manual") == 2
