from pydantic import ConfigDict, Field

from app.domain.enums import UserRole
from app.schemas.base import ApiModel


class LoginRequest(ApiModel):
    login: str = Field(min_length=1, max_length=64, description="Логин")
    password: str = Field(min_length=1, max_length=128, description="Пароль")

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"login": "client_fast", "password": "demo1234"}]}
    )


class UserOut(ApiModel):
    id: int
    name: str = Field(description="ФИО")
    role: UserRole
    company_id: int | None = Field(default=None, description="Компания клиента; у андеррайтера пусто")


class LoginResponse(ApiModel):
    access_token: str = Field(description="JWT; передавать как `Authorization: Bearer <token>`")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(description="Срок жизни токена, секунд")
    user: UserOut

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "tokenType": "Bearer",
                    "expiresIn": 28800,
                    "user": {
                        "id": 1,
                        "name": "Иванов Пётр Сергеевич",
                        "role": "CLIENT",
                        "companyId": 1,
                    },
                }
            ]
        }
    )
