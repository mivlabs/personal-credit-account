from pydantic import ConfigDict

from app.schemas.base import ApiModel


class HealthOut(ApiModel):
    status: str
    database: str

    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ok", "database": "ok"}]})
