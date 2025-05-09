from typing import Any, Optional

from pydantic import BaseModel


class ConfigurationBase(BaseModel):
    project_id: str
    type: str
    value: dict[str, Any]


class ConfigurationCreate(ConfigurationBase):
    # ID will be auto-generated, so not needed here
    pass


class ConfigurationUpdate(BaseModel):
    value: Optional[dict[str, Any]] = None
    type: Optional[str] = None
    # project_id is usually not updatable, id is the identifier


class Configuration(ConfigurationBase):
    id: str

    class Config:
        orm_mode = True
