from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    professional_title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    skills: list[str] | None = Field(default=None, max_length=50)
    experience: str | None = Field(default=None, max_length=5000)
    avatar_url: str | None = Field(default=None, max_length=1000)

    def to_update_dict(self) -> dict:
        return self.model_dump(exclude_none=True)
