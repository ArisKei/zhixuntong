from enum import Enum


class NewsCategory(str, Enum):
    policy = "policy"
    company = "company"
    market = "market"
    tech = "tech"
    risk = "risk"
    other = "other"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class ReportKind(str, Enum):
    daily = "daily"
    weekly = "weekly"
    incident = "incident"
