"""Unified data source loader — returns a DataFrame for CSV or a SQLAlchemy connection string for SQL.

This is NOT a LangChain tool. It is a shared helper used by agents to abstract
the CSV vs SQL source type difference before dispatching to analysis tools.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pandas as pd


def build_connection_string(config: Dict[str, Any]) -> str:
    """Build a SQLAlchemy connection string from a decrypted SQL config dict.

    Expected config keys (from AES-256 decrypted JSON — stored by connect_sql router):
        engine   : "postgresql" | "mysql" | "mssql" | "sqlite"
        host     : e.g. "localhost" or "db.example.com"
        port     : integer port number
        database : database / schema name
        username : DB username
        password : DB password

    Returns a fully-formed SQLAlchemy URL string that is safe to pass to
    create_engine() or run_sql_query tool.
    """
    # Key is 'engine' (set by SQLConnectionRequest schema in connect_sql router)
    engine = config.get("engine", "postgresql").lower()
    host = config.get("host", "localhost")
    port = config.get("port")
    database = config.get("database", "")
    username = config.get("username", "")
    password = config.get("password", "")

    # Encode special characters in password
    from urllib.parse import quote_plus
    safe_password = quote_plus(str(password)) if password else ""

    if engine in ("postgresql", "postgres"):
        driver = "postgresql+psycopg2"
    elif engine == "mysql":
        driver = "mysql+pymysql"
    elif engine == "mssql":
        driver = "mssql+pyodbc"
    elif engine == "sqlite":
        # SQLite: database is a file path
        return f"sqlite:///{database}"
    else:
        driver = engine

    if port:
        return f"{driver}://{username}:{safe_password}@{host}:{port}/{database}"
    return f"{driver}://{username}:{safe_password}@{host}/{database}"


def load_csv(file_path: str) -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame with smart dtype inference."""
    df = pd.read_csv(file_path)
    # Attempt to parse object columns that look like dates
    for col in df.select_dtypes(include=["object"]).columns:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            # Only convert if ≥50% of rows parsed successfully
            if parsed.notna().sum() > len(df) * 0.5:
                df[col] = parsed
        except Exception:
            pass
    return df


def resolve_data_path(state: Dict[str, Any]) -> Optional[str]:
    """Return the effective CSV path: cleaned version first, then raw."""
    return state.get("clean_dataframe_ref") or state.get("file_path")


def ensure_async_connection_string(conn_str: str) -> str:
    """Ensure the connection string uses an async-compatible driver.
    
    Translates:
    - postgresql:// or postgresql+psycopg2:// -> postgresql+asyncpg://
    - mysql:// or mysql+pymysql:// -> mysql+aiomysql://
    - sqlite:/// -> sqlite+aiosqlite:///
    """
    if not conn_str:
        return conn_str
        
    if conn_str.startswith("postgresql://") or conn_str.startswith("postgres://"):
        return conn_str.replace("postgresql://", "postgresql+asyncpg://").replace("postgres://", "postgresql+asyncpg://")
    elif conn_str.startswith("postgresql+psycopg2://"):
        return conn_str.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    elif conn_str.startswith("mysql://"):
        return conn_str.replace("mysql://", "mysql+aiomysql://")
    elif conn_str.startswith("mysql+pymysql://"):
        return conn_str.replace("mysql+pymysql://", "mysql+aiomysql://")
    elif conn_str.startswith("sqlite:///"):
        return conn_str.replace("sqlite:///", "sqlite+aiosqlite:///")
    
    return conn_str


def get_connection_string(state: Dict[str, Any]) -> Optional[str]:
    """Decrypt SQL config from state and return a SQLAlchemy connection string.

    Handles two SQL sub-cases:
    1. Uploaded SQLite file → file_path is set, config_encrypted is None
       → returns sqlite:///file_path directly (no decryption needed)
    2. Remote SQL DB → config_encrypted is set with AES-encrypted credentials
       → decrypts and builds a full connection string

    Returns None if neither is available.
    """
    config_encrypted = state.get("config_encrypted")
    file_path = state.get("file_path")
    
    # Fallback for manual/test strings
    if state.get("connection_string"):
        return state["connection_string"]

    # Case 1: Uploaded SQLite database file (no credentials to decrypt)
    if not config_encrypted and file_path:
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        if ext in ("sqlite", "db"):
            import os
            # Ensure path is absolute for SQLAlchemy
            abs_path = os.path.abspath(file_path)
            return f"sqlite:///{abs_path}"
        # Not a SQLite file and no credentials — cannot connect
        return None

    # Case 2: Remote SQL database — decrypt credentials
    try:
        from app.infrastructure.adapters.encryption import decrypt_json
        config = decrypt_json(config_encrypted)
        return build_connection_string(config)
    except Exception as exc:
        raise ValueError(f"Failed to decrypt SQL connection config: {exc}") from exc


def get_source_type(state: Dict[str, Any]) -> str:
    """Return normalised source type: 'csv' or 'sql'."""
    raw = (state.get("source_type") or "csv").lower()
    # Normalise any sql-family types
    return "sql" if raw in ("sql", "sqlite", "postgresql", "mysql", "mssql") else "csv"
