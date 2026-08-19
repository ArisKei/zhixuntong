from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.errors import AppError
from app.models import Report
from app.services.alert import get_alert
from app.services.logutil import write_job_log
from schemas.notify import DingTalkNotifyIn, EmailNotifyIn, NotifyOut


def send_dingtalk(db: Session, clients: Clients, body: DingTalkNotifyIn) -> NotifyOut:
    alert = get_alert(db, body.alert_id)
    message = clients.notify.send_dingtalk(alert)
    write_job_log(db, "notify", "dingtalk sent", extra={"alert_id": body.alert_id})
    return NotifyOut(ok=True, channel="dingtalk", message=message)


def send_email(db: Session, clients: Clients, body: EmailNotifyIn) -> NotifyOut:
    if body.kind == "alert":
        if not body.alert_id:
            raise AppError("validation_error", "alert 类型邮件需要 alert_id", 400)
        alert = get_alert(db, body.alert_id)
        subject = f"【智讯通预警】{alert.title}"
        body_text = f"{alert.summary}\n影响：{alert.impact}\n建议：{alert.suggestion}"
    else:
        report = None
        if body.report_id:
            report = db.get(Report, body.report_id)
        else:
            report = db.query(Report).order_by(Report.id.desc()).first()
        if report is None:
            raise AppError("report_not_found", "没有可发送的报告", 404)
        subject = report.title
        body_text = report.content_md
    message = clients.notify.send_email(body.kind, subject, body_text, body.to)
    write_job_log(db, "notify", "email sent", extra={"kind": body.kind})
    return NotifyOut(ok=True, channel="email", message=message)
