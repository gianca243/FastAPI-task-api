from sqlmodel import Field, SQLModel

class Task(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str = Field(index=True)
    duration: int
    user_id: int | None = Field(foreign_key="user.id")
