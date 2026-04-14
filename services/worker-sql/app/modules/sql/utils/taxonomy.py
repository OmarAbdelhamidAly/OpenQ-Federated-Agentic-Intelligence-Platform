"""Centralized SQL Taxonomy for Insightify."""

SQL_DOMAINS = {
    "FINANCE": "Accounting, Invoices, Transactions, Revenue, Tax",
    "CRM": "Customers, Leads, Contacts, Interactions",
    "HR": "Employees, Payroll, Performance, Recruitment",
    "LOGISTICS": "Inventory, Shipping, Warehousing, Supply Chain",
    "TECH": "System Logs, Configuration, Metadata, API Usage",
    "MARKETING": "Campaigns, Analytics, SEO, Social Media",
    "LEGAL": "Contracts, Compliance, Intellectual Property"
}

COLUMN_ARCHETYPES = [
    "IDENTIFIER",  # Keys (ID, Serial)
    "TEMPORAL",    # Dates, Timestamps
    "PII",         # Personal Data (Name, Email, Phone)
    "FINANCIAL",   # Currencies, Prices
    "METRIC",      # Aggregatable numbers (Quantity, Score)
    "CATEGORICAL", # Enums, Statuses, Types
    "LOCATION",    # Address, Country, Lat/Long
    "GEOMETRY",    # Spatial data
    "METADATA"     # Internal system flags
]
