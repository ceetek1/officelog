"""Settings, all from environment variables (spec §3, decision D5)."""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from app.rules.schedule import WeekSchedule, parse_holidays, parse_schedule


def _psycopg_url(url: str) -> str:
    """Accept the postgres:// URLs that Railway and others hand out."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The database owner's URL. Used to run migrations and set up the app's own role.
    database_url: str
    # The app connects as this role, which may not UPDATE or DELETE append-only tables.
    app_db_role: str = "attendance_app"
    app_db_password: str = Field(min_length=12)
    # Optional: a full URL for the app role. If empty it is built from DATABASE_URL.
    app_database_url: str = ""

    # Shown on the sign-in screen, e.g. "Acme Ltd attendance".
    company_name: str = ""

    # Public address of the site, e.g. https://attendance.example.com (used in invite links).
    base_url: str = "http://localhost:8000"

    timezone: str = "Africa/Lagos"
    schedule_json: str = ""
    holidays: str = ""

    session_days: int = 30
    cookie_secure: bool = True

    # Where the built frontend lives. Empty disables static serving (API only).
    frontend_dist: str = "frontend/dist"

    @field_validator("database_url", "app_database_url")
    @classmethod
    def _normalise_url(cls, v: str) -> str:
        return _psycopg_url(v) if v else v

    @field_validator("app_db_role")
    @classmethod
    def _safe_role(cls, v: str) -> str:
        if not v.replace("_", "").isalnum() or not v[0].isalpha():
            raise ValueError("APP_DB_ROLE must be letters, digits and underscores")
        return v

    @field_validator("base_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def schedule(self) -> WeekSchedule:
        return parse_schedule(self.schedule_json)

    @property
    def holiday_dates(self):
        return parse_holidays(self.holidays)

    @property
    def resolved_app_database_url(self) -> str:
        if self.app_database_url:
            return self.app_database_url
        url = make_url(self.database_url).set(username=self.app_db_role, password=self.app_db_password)
        return url.render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    s = Settings()  # type: ignore[call-arg]
    # Fail at start-up, not on the first request, if the schedule is malformed.
    s.schedule  # noqa: B018
    s.holiday_dates  # noqa: B018
    s.tz  # noqa: B018
    return s
