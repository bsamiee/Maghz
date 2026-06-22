"""Core result contracts: the outcome algebra and the JSON envelope every rail emits."""

from admin.core.model import completed, Detail, Envelope, fault, Report, Row
from admin.core.status import Status


__all__ = ["Detail", "Envelope", "Report", "Row", "Status", "completed", "fault"]
