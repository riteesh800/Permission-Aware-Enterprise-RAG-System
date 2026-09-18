from __future__ import annotations

import enum


class AppRole(str, enum.Enum):
    ADMIN = "ADMIN"
    EMPLOYEE = "EMPLOYEE"


class PrincipalType(str, enum.Enum):
    USER = "USER"
    ROLE = "ROLE"
    GROUP = "GROUP"
    DEPARTMENT = "DEPARTMENT"
    PUBLIC = "PUBLIC"


class AclPermission(str, enum.Enum):
    READ = "READ"
    DENY_READ = "DENY_READ"





class IngestionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class AuditStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILURE = "FAILURE"
    RATE_LIMITED = "RATE_LIMITED"
