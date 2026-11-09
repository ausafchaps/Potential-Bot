from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccountDeletion(BaseModel):
    password: str = Field(min_length=1, max_length=128, repr=False)
    confirmation: Literal["delete-my-account"]

    model_config = ConfigDict(extra="forbid")
