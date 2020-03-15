from sqlalchemy import Column, Integer, String
from redclay.modelbase import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True)
    passhash = Column(String, nullable=False)

    def __repr__(self):
        return f"<Account id={self.id}, username={self.username}>"
