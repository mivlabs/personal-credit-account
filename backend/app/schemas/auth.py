from pydantic import ConfigDict, Field

from app.domain.enums import UserRole
from app.schemas.base import ApiModel


class LoginRequest(ApiModel):
    login: str = Field(min_length=1, max_length=64, description="Логин")
    password: str = Field(min_length=1, max_length=128, description="Пароль")

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"login": "client_fast", "password": "demo1234"}]}
    )


class RegisterRequest(ApiModel):
    login: str = Field(max_length=64, description="Логин: 3–32 символа `a-z`, `0-9`, `_`, `.`, `-`")
    password: str = Field(max_length=128, description="Пароль, не короче 8 символов")
    inn: str = Field(
        max_length=32, description="ИНН: 10 цифр (организация) или 12 (ИП), контрольные числа ФНС"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"login": "my_company", "password": "secret123", "inn": "7702000011"}]
        }
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
