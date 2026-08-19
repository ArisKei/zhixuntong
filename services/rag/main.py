"""成员 C：RAGFlow 独立 HTTP 封装服务。

暴露中台 `HttpRagClient`（services/api/app/clients/rag.py）已调用的两个端点，
内部持 RAGFlow API Key 转发真 RAGFlow 并翻译字段。中台零改动。

- POST /api/v1/datasets/enterprise/documents   multipart file
- POST /api/v1/retrieval                        body {"question","top_k"}
"""

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse

import ragflow

app = FastAPI(title="智讯通 RAG 封装", version="0.1.0")


@app.exception_handler(ragflow.RagflowError)
async def handle_ragflow_error(_request: Request, exc: ragflow.RagflowError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"code": "rag_unavailable", "message": str(exc)},
    )


@app.post("/api/v1/datasets/enterprise/documents")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or "untitled.bin"
    doc = ragflow.upload_document(filename, content)
    return {"document": doc.model_dump()}


@app.post("/api/v1/retrieval")
async def retrieve(payload: dict):
    query = str(payload.get("question") or "")
    top_k = int(payload.get("top_k") or 5)
    citations = ragflow.search(query, top_k)
    chunks = [
        {
            "document_name": c.doc,
            "page": c.page,
            "content": c.snippet,
            "score": c.score,
        }
        for c in citations
    ]
    return {"chunks": chunks}
