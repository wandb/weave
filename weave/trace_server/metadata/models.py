import uuid

from sqlalchemy import JSON, Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Configuration(Base):
    __tablename__ = "configurations"

    id = Column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4()), index=True
    )
    project_id = Column(String(64), index=True, nullable=False)
    type = Column(String(64), index=True, nullable=False)
    value = Column(JSON, nullable=False)
    wb_user_id = Column(String(64), nullable=True)

    def __repr__(self):
        return f"<Configuration(id='{self.id}', project_id='{self.project_id}', type='{self.type}')>"
