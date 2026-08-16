from pydantic import BaseModel, Field


class Config(BaseModel):
    """Plugin Config"""

    group_heat_retention_days: int = Field(default=7, ge=1)
    """消息记录保留天数，更早的记录每日自动清理，默认 7 天"""
