"""Models package — import all models so Alembic can discover them."""

from app.core.database import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.data_source import DataSource
from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult

__all__ = [
    "Base",
    "Tenant",
    "User",
    "DataSource",
    "AnalysisJob",
    "AnalysisResult",
]
