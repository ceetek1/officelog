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
    # Who to contact about personal data, shown in the privacy notice (spec §7),
    # e.g. "Folake Adeyemi, MD · folake@example.com · 0803 000 0000".
    privacy_contact: str = ""

    # Public address of the site, e.g. https://attendance.example.com (used in invite links).
    base_url: str = "http://localhost:8000"

    # Secret behind the rotating TV codes (spec §5). At least 32 characters.
    master_secret: str = Field(min_length=32)
    # Extra web origins allowed for Face ID (e.g. the Vite dev server). BASE_URL is always allowed.
    extra_origins: str = ""

    timezone: str = "Africa/Lagos"
    schedule_json: str = ""
    holidays: str = ""

    session_days: int = 30
    cookie_secure: bool = True

    # Identifies the running build; the TV reloads itself when it changes. Railway sets this.
    railway_git_commit_sha: str = "dev"

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
    def rp_id(self) -> str:
        """WebAuthn relying-party id: the site's host name, e.g. attendance.example.com."""
        from urllib.parse import urlsplit

        return urlsplit(self.base_url).hostname or "localhost"

    @property
    def origins(self) -> list[str]:
        return [self.base_url] + [o.strip().rstrip("/") for o in self.extra_origins.split(",") if o.strip()]

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
