"""
Minimal MCP (Model Context Protocol) server exposing the agent's two tools.

The same functions the Semantic Kernel agent calls (app/services/agent_service.py)
are registered here as MCP tools, so any MCP client — Claude Desktop, Claude Code,
the MCP Inspector, or another agent framework — can discover and call them over
stdio without going through the FastAPI app or this project's own LLM:

  search_documents(query, top_k)       ChromaDB + sentence-transformers retrieval
  check_equipment_status(equipment_id) the MOCK equipment status lookup

Run:  python -m app.mcp_server        (stdio transport)

It reads the same vector store as the API (CHROMA_DB_PATH), so documents
ingested through POST /ingest are searchable here too.
"""
from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from app.services.agent_service import DocumentSearchPlugin, EquipmentStatusPlugin

mcp = FastMCP("rag-document-log-assistant")

_docs = DocumentSearchPlugin()
_equipment = EquipmentStatusPlugin()


@mcp.tool()
def search_documents(query: str, top_k: int = 4) -> str:
    """Search the indexed engineering documents (manuals, troubleshooting guides,
    logs, notes) for passages relevant to a query. Each passage is prefixed with
    its chunk_id, document name and relevance score."""
    return _docs.search_documents(query=query, top_k=top_k)


@mcp.tool()
def check_equipment_status(equipment_id: str) -> str:
    """Look up a piece of equipment's current status by ID (e.g. 'HX-9000',
    'SCU-400', 'PUMP-01'): status, active fault codes, last maintenance date,
    operating hours. Simulated/mock data, not a live feed."""
    return _equipment.check_equipment_status(equipment_id=equipment_id)


if __name__ == "__main__":
    # stdout carries the MCP protocol, so logs must go to stderr
    # (app.core.logging_config logs to stdout for the API server).
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    mcp.run()
