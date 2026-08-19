from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import KnowledgeDoc
from app.paths import API_DIR
from schemas.common import Citation
from schemas.knowledge import KnowledgeDocOut

X1_CITATION = Citation(
    doc="X1产品说明书",
    page=13,
    snippet="X1产品最大日处理能力为6800件。",
    score=0.92,
)
COMPARE_CITATION = Citation(
    doc="产品对比-内部口径",
    page=2,
    snippet="A产品较竞品续航高12%。",
    score=0.88,
)


def _to_out(doc: KnowledgeDoc) -> KnowledgeDocOut:
    return KnowledgeDocOut.model_validate(doc)


class MockRagClient:
    def upload(self, db: Session, filename: str, content: bytes) -> KnowledgeDocOut:
        upload_dir = API_DIR / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / filename).write_bytes(content)
        doc = KnowledgeDoc(
            filename=filename,
            dataset="enterprise",
            status="ready",
            chunk_count=max(1, len(content) // 800),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return _to_out(doc)

    def search(self, db: Session, query: str, top_k: int = 5) -> list[Citation]:
        hits: list[Citation] = []
        if any(token in query for token in ("X1", "日处理", "6800", "处理能力")):
            hits.append(X1_CITATION)
        if any(token in query for token in ("优势", "竞品", "续航")):
            hits.append(COMPARE_CITATION)
        return hits[:top_k]

    def list_documents(self, db: Session) -> list[KnowledgeDocOut]:
        rows = db.query(KnowledgeDoc).order_by(KnowledgeDoc.id.desc()).all()
        return [_to_out(row) for row in rows]


class HttpRagClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def upload(self, db: Session, filename: str, content: bytes) -> KnowledgeDocOut:
        import httpx

        try:
            response = httpx.post(
                f"{self.base_url}/api/v1/datasets/enterprise/documents",
                files={"file": (filename, content)},
                timeout=60,
            )
            response.raise_for_status()
        except Exception as exc:
            raise AppError("rag_unavailable", "RAGFlow 不可用", 503) from exc
        return MockRagClient().upload(db, filename, content)

    def search(self, db: Session, query: str, top_k: int = 5) -> list[Citation]:
        import httpx

        try:
            response = httpx.post(
                f"{self.base_url}/api/v1/retrieval",
                json={"question": query, "top_k": top_k},
                timeout=30,
            )
            response.raise_for_status()
        except Exception as exc:
            raise AppError("rag_unavailable", "RAGFlow 不可用", 503) from exc
        payload = response.json()
        chunks = payload.get("chunks") or payload.get("data") or []
        citations: list[Citation] = []
        for chunk in chunks[:top_k]:
            citations.append(
                Citation(
                    doc=chunk.get("document_name") or chunk.get("doc") or "未知文档",
                    page=chunk.get("page"),
                    snippet=chunk.get("content") or chunk.get("snippet") or "",
                    score=chunk.get("score"),
                )
            )
        return citations

    def list_documents(self, db: Session) -> list[KnowledgeDocOut]:
        return MockRagClient().list_documents(db)
