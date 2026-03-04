from abc import ABC, abstractmethod

from pydantic import BaseModel


class CategorizationArgs(BaseModel):
    project_id: str
    call_ids: list[str]
    wb_user_id: str
    external_project_id: str | None = None
    wb_username: str | None = None


class CategorizationDispatcher(ABC):
    @abstractmethod
    def dispatch(self, args: CategorizationArgs) -> None:
        pass
