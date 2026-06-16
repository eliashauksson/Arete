from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.utcnow()


class Athlete(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    display_name: Optional[str] = None
    strava_connected: bool = False
    last_strava_sync: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Goal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    athlete_id: int = Field(foreign_key="athlete.id")
    race_name: Optional[str] = None
    race_date: Optional[date] = None
    race_distance: Optional[str] = None
    target_time: Optional[str] = None
    weekly_hours: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class TrainingPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    athlete_id: int = Field(foreign_key="athlete.id")
    goal_id: int = Field(foreign_key="goal.id")
    status: str = "active"
    created_at: datetime = Field(default_factory=utcnow)


class PlannedSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="trainingplan.id")
    date: date
    sport_type: str
    title: str
    description: Optional[str] = None
    hr_zone: Optional[int] = None
    structure: Optional[str] = None  # JSON array of workout blocks
    planned_duration_min: Optional[int] = None
    planned_load: Optional[float] = None
    status: str = "planned"
    strava_activity_id: Optional[int] = Field(default=None, foreign_key="stravaactivity.id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StravaActivity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    athlete_id: int = Field(foreign_key="athlete.id")
    strava_id: int = Field(unique=True, index=True)
    name: str
    sport_type: str
    start_date: datetime
    distance: float
    moving_time: int
    elapsed_time: int
    total_elevation_gain: float
    average_heartrate: Optional[float] = None
    relative_effort: Optional[float] = None
    raw_json: Optional[str] = None
    ai_summary: Optional[str] = None
    gpx_data: Optional[str] = None    # JSON: [[lat, lng], ...]
    hr_data: Optional[str] = None     # JSON: {"times": [s,...], "values": [bpm,...]}
    pace_data: Optional[str] = None   # JSON: {"times": [s,...], "values": [min/km,...]}
    created_at: datetime = Field(default_factory=utcnow)
