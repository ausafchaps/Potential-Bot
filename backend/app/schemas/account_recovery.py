from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecoveryEmail(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or any(c in value for c in "\r\n"):
            raise ValueError("Enter a valid email address")
        return value


class LinkToken(BaseModel):
    token: str = Field(min_length=32, max_length=256, repr=False)
    model_config = ConfigDict(extra="forbid")


class ResetPassword(LinkToken):
    password: str = Field(min_length=12, max_length=128, repr=False)


class RecoveryMessage(BaseModel):
    message: str


class AuthCapabilities(BaseModel):
    account_email_enabled: bool
    verification_required: bool
