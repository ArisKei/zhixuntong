from app.config import settings
from app.db import SessionLocal, engine
from app.models import Base, CrawlerSource, KnowledgeDoc, User
from app.security import hash_password


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == "demo").first() is None:
            db.add(User(username="demo", password_hash=hash_password("demo123")))
        sources = [
            ("miit_policy", "政策信息"),
            ("ev_news", "行业新闻"),
            ("oem_news", "车企动态"),
        ]
        for source_id, name in sources:
            if db.query(CrawlerSource).filter(CrawlerSource.source_id == source_id).first() is None:
                db.add(CrawlerSource(source_id=source_id, name=name, enabled=True))
        if db.query(KnowledgeDoc).filter(KnowledgeDoc.filename == "X1产品说明书.pdf").first() is None:
            db.add(
                KnowledgeDoc(
                    filename="X1产品说明书.pdf",
                    dataset="enterprise",
                    status="ready",
                    chunk_count=12,
                )
            )
        db.commit()
    finally:
        db.close()
