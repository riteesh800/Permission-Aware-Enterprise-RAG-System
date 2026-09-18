from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    company_name: str | None = None


class SendOtpRequest(BaseModel):
    email: EmailStr


class VerifyAdminRegistrationRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=6, max_length=256)
    otp: str = Field(min_length=6, max_length=6)


class ForgotPasswordResetRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6, max_length=256)

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=256)


class UserPublic(BaseModel):
    id: str
    unique_identifier: str
    email: str
    full_name: str
    app_role: str
    department_id: str | None
    is_active: bool
    must_change_password: bool
    company_name: str | None = None
    role_names: list[str] = Field(default_factory=list)
    group_names: list[str] = Field(default_factory=list)


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=6, max_length=256)
    department_id: str | None = None
    app_role: str = "EMPLOYEE"
    unique_identifier: str | None = None
    must_change_password: bool = True


class PatchUserRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    department_id: str | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None
    app_role: str | None = None


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=6, max_length=256)
    must_change_password: bool = True


class DeleteUserRequest(BaseModel):
    token: str | None = None
    password: str | None = None
    confirmation: str | None = None

class VerifyDeleteRequest(BaseModel):
    password: str | None = None
    otp: str | None = None



class AclEntry(BaseModel):
    principal_type: str
    principal_id: str | None = None
    permission: str = "READ"
    department_scoped: bool = False


class PatchDocumentRequest(BaseModel):
    title: str | None = None
    department_id: str | None = None
    owner_user_id: str | None = None
    acls: list[AclEntry] | None = None
    disabled: bool | None = None


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class CreateDepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
