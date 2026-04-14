"""Centralized Document Taxonomy for Insightify PDF Pillar."""
from typing import Dict, Any, Optional

_HINT_TO_META: Dict[str, Dict[str, str]] = {
    # ── Finance & Accounting ──
    "invoice":          {"doc_type": "Invoice / Receipt",           "industry": "Finance & Accounting"},
    "financial_report": {"doc_type": "Financial Report",            "industry": "Finance & Accounting"},
    "tax_return":       {"doc_type": "Tax Return / Declaration",    "industry": "Finance & Accounting"},
    "bank_statement":   {"doc_type": "Bank / Account Statement",    "industry": "Finance & Accounting"},
    "purchase_order":   {"doc_type": "Purchase Order",              "industry": "Finance & Accounting"},
    # ── Legal & Compliance ──
    "contract":         {"doc_type": "Legal Contract / Agreement",  "industry": "Legal & Compliance"},
    "nda":              {"doc_type": "Non-Disclosure Agreement",    "industry": "Legal & Compliance"},
    "policy":           {"doc_type": "Policy / Compliance Document","industry": "Legal & Compliance"},
    "audit_report":     {"doc_type": "Audit / Compliance Report",   "industry": "Legal & Compliance"},
    # ── Human Resources ──
    "hr_record":        {"doc_type": "HR / Personnel Record",       "industry": "Human Resources"},
    "resume":           {"doc_type": "Resume / CV",                 "industry": "Human Resources"},
    "perf_review":      {"doc_type": "Performance Review",          "industry": "Human Resources"},
    # ── Medical & Healthcare ──
    "medical_record":   {"doc_type": "Medical / Clinical Record",   "industry": "Medical & Healthcare"},
    "prescription":     {"doc_type": "Medical Prescription",        "industry": "Medical & Healthcare"},
    "lab_result":       {"doc_type": "Lab / Test Result",           "industry": "Medical & Healthcare"},
    # ── Tech & Engineering ──
    "tech_spec":        {"doc_type": "Technical Specification",     "industry": "Tech & Engineering"},
    "api_doc":          {"doc_type": "API / Developer Documentation","industry": "Tech & Engineering"},
    "arch_diagram":     {"doc_type": "Architecture Diagram / Doc",  "industry": "Tech & Engineering"},
    # ── Logistics & Supply Chain ──
    "bill_of_lading":   {"doc_type": "Bill of Lading",              "industry": "Logistics & Supply Chain"},
    "customs_decl":     {"doc_type": "Customs Declaration",         "industry": "Logistics & Supply Chain"},
    "inventory":        {"doc_type": "Inventory / Stock Report",    "industry": "Logistics & Supply Chain"},
    # ── Real Estate ──
    "lease_agreement":  {"doc_type": "Lease / Rental Agreement",    "industry": "Real Estate"},
    "property_deed":    {"doc_type": "Property Deed / Title",       "industry": "Real Estate"},
    # ── Construction & Engineering ──
    "floor_plan":       {"doc_type": "Floor Plan / Blueprint",      "industry": "Construction & Engineering"},
    "building_permit":  {"doc_type": "Building Permit / License",   "industry": "Construction & Engineering"},
    "construction_contract": {"doc_type": "Construction Contract",  "industry": "Construction & Engineering"},
    # ── General Business ──
    "business_report":  {"doc_type": "Business / Strategy Report",  "industry": "General Business"},
    "meeting_minutes":  {"doc_type": "Meeting Minutes",             "industry": "General Business"},
    # ── Marketing & Strategy ──
    "marketing_mat":    {"doc_type": "Marketing Material / Deck",   "industry": "Marketing & Strategy"},
    "campaign_plan":    {"doc_type": "Campaign / Marketing Plan",   "industry": "Marketing & Strategy"},
    "brand_guidelines": {"doc_type": "Brand Guidelines",            "industry": "Marketing & Strategy"},
    # ── Literature & Education ──
    "other_book":       {"doc_type": "Book / E-Book",               "industry": "Literature & Education"},
    "other_manual":     {"doc_type": "Instruction Manual",          "industry": "Literature & Education"},
    "textbook":         {"doc_type": "Textbook / Course Material",  "industry": "Literature & Education"},
    # ── Academic & Research ──
    "other_research":   {"doc_type": "Research Paper",              "industry": "Academic & Research"},
    "other_article":    {"doc_type": "News Article / Blog",         "industry": "Academic & Research"},
    "thesis":           {"doc_type": "Thesis / Dissertation",       "industry": "Academic & Research"},
    # ── Other / Custom ──
    "other_misc":       {"doc_type": "General Document",            "industry": "Other / Custom"},
}

def get_document_taxonomy(hint: Optional[str] = None) -> Dict[str, str]:
    """Retrieve structured metadata based on user-selected hint."""
    if not hint:
        return {"doc_type": "Unclassified Document", "industry": "Unknown"}
    
    clean_hint = hint.strip().lower()
    return _HINT_TO_META.get(clean_hint, {"doc_type": "Custom Document", "industry": "Unknown"})
