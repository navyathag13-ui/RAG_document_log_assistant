"""
Gradio demo UI for the RAG assistant.

A thin client over the running FastAPI service: every button calls the same
HTTP endpoints the React frontend and MCP server use (/ingest, /documents,
/ask, /agent), so the UI never bypasses validation, safety checks or tracing.

Run the API first, then:
    python -m app.ui.gradio_app --api http://localhost:8000
"""
from __future__ import annotations

import argparse
from pathlib import Path

import httpx

SOURCE_HEADERS = ["Document", "Score", "Excerpt"]
TOOL_HEADERS = ["Tool", "Arguments", "Result (excerpt)"]
DOC_HEADERS = ["Document", "Type", "Chunks"]


def _error(r: httpx.Response) -> str:
    try:
        detail = r.json().get("detail", r.text)
    except ValueError:
        detail = r.text
    return f"Error {r.status_code}: {detail}"


# ── Handlers (plain functions so they can be tested without a browser) ────────

def ingest(client: httpx.Client, file_path: str | None) -> str:
    if not file_path:
        return "Choose a file first."
    path = Path(file_path)
    with open(path, "rb") as f:
        r = client.post("/ingest", files={"file": (path.name, f)})
    if r.status_code != 201:
        return _error(r)
    body = r.json()
    return f"Ingested {path.name}: {body['chunks_created']} chunks ({body['file_type']})."


def list_documents(client: httpx.Client) -> list[list]:
    r = client.get("/documents")
    if r.status_code != 200:
        return []
    return [[d["doc_id"], d["file_type"], d["chunks"]] for d in r.json()["documents"]]


def ask(client: httpx.Client, question: str, top_k: int) -> tuple[str, list[list], str]:
    if not question.strip():
        return "Type a question first.", [], ""
    r = client.post("/ask", json={"question": question, "top_k": int(top_k)})
    if r.status_code != 200:
        return _error(r), [], ""
    body = r.json()
    sources = [[s["doc_name"], round(s["score"], 3), s["text_excerpt"]] for s in body["sources"]]
    mode = body["llm_provider"] if body["llm_used"] else "retrieval only (no LLM configured)"
    status = f"Answered by: {mode} · {body['retrieval_count']} sources"
    return body["answer"], sources, status


def run_agent(client: httpx.Client, query: str) -> tuple[str, list[list]]:
    if not query.strip():
        return "Type a request first.", []
    r = client.post("/agent", json={"query": query})
    if r.status_code != 200:
        return _error(r), []
    body = r.json()
    calls = [[c["tool"], str(c["arguments"]), c["result_excerpt"]] for c in body["tool_calls"]]
    return body["answer"], calls


# ── Layout ────────────────────────────────────────────────────────────────────

def build_ui(client: httpx.Client):
    import gradio as gr

    with gr.Blocks(title="Engineering RAG Assistant") as demo:
        gr.Markdown("# Engineering RAG Assistant\nAsk questions about your manuals and logs, with sources.")

        with gr.Tab("Ask"):
            question = gr.Textbox(label="Question", placeholder="How do I reset the pump controller?")
            top_k = gr.Slider(1, 20, value=5, step=1, label="Sources to retrieve")
            ask_btn = gr.Button("Ask", variant="primary")
            answer = gr.Markdown()
            status = gr.Markdown()
            sources = gr.Dataframe(headers=SOURCE_HEADERS, label="Sources", wrap=True)
            ask_btn.click(lambda q, k: ask(client, q, k), [question, top_k], [answer, sources, status])
            question.submit(lambda q, k: ask(client, q, k), [question, top_k], [answer, sources, status])

        with gr.Tab("Agent"):
            query = gr.Textbox(label="Request", placeholder="Is pump P-101 running, and what does the manual say about its alarms?")
            agent_btn = gr.Button("Run agent", variant="primary")
            agent_answer = gr.Markdown()
            tool_calls = gr.Dataframe(headers=TOOL_HEADERS, label="Tool calls (audit trace)", wrap=True)
            agent_btn.click(lambda q: run_agent(client, q), [query], [agent_answer, tool_calls])

        with gr.Tab("Documents"):
            upload = gr.File(label="Upload a PDF, TXT, MD or LOG file", type="filepath")
            ingest_btn = gr.Button("Ingest")
            ingest_status = gr.Markdown()
            docs = gr.Dataframe(headers=DOC_HEADERS, label="Indexed documents")
            ingest_btn.click(lambda p: ingest(client, p), [upload], [ingest_status]).then(
                lambda: list_documents(client), None, [docs]
            )
            demo.load(lambda: list_documents(client), None, [docs])

    return demo


def main() -> None:
    parser = argparse.ArgumentParser(description="Gradio UI for the RAG assistant")
    parser.add_argument("--api", default="http://localhost:8000", help="Base URL of the running FastAPI service")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    client = httpx.Client(base_url=args.api, timeout=120)
    build_ui(client).launch(server_port=args.port)


if __name__ == "__main__":
    main()
