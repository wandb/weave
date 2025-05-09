import uuid

from sqlalchemy import JSON, Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Configuration(Base):
    __tablename__ = "configurations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String, index=True, nullable=False)
    type = Column(String, index=True, nullable=False)
    value = Column(JSON, nullable=False)

    def __repr__(self):
        return f"<Configuration(id='{self.id}', project_id='{self.project_id}', type='{self.type}')>"
