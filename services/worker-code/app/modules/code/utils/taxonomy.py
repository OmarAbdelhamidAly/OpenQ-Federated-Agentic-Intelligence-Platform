"""Centralized Codebase Taxonomy for Insightify."""

# Maps component types to architectural roles
CODE_ROLES = {
    "Infrastructure": "Database connections, API clients, Redis/Cache setup, Environment config.",
    "API / Interface": "Endpoints, Controllers, Routes, Request/Response schemas.",
    "Business Logic": "Service layer, Core algorithms, Domain rules, Calculation engines.",
    "Data Models": "ORM models, Schema definitions, DTOs, Entities.",
    "UI / Frontend": "React/Next.js components, Styles, Assets, Hooks.",
    "Utilities": "Helper functions, String formatting, Date parsing, Shared tools.",
    "Security": "Authentication, Authorization, Encryption, Guardrails."
}

# Standard exclusion list for codebase scanning
DEFAULT_EXCLUSIONS = [
    "node_modules", "venv", ".venv", "env", ".env", "dist", "build", "target",
    ".git", ".github", ".vscode", "__pycache__", ".pytest_cache", ".next",
    ".idea", "coverage"
]
