from typing import Optional

from sqlalchemy.orm import Session

from app.models import JobLog
from app.logging import get_logger


def write_job_log(db: Session, job_name: str, message: str, level: str = "info", extra: Optional[dict] = None) -> None:
    db.add(JobLog(job_name=job_name, level=level, message=message, extra=extra))
    db.commit()
    logger = get_logger(job_name)
    if level == "error":
        logger.error(message, **(extra or {}))
    else:
        logger.info(message, **(extra or {}))
