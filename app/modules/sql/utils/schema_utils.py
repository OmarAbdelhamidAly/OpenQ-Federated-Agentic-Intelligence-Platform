"""SQL Schema Utilities.

Shared logic for generating ERDs and inferring relationships from SQL metadata.
"""

from typing import Any, Dict, List, Set

def generate_mermaid_erd(tables: List[Dict[str, Any]], foreign_keys: List[Dict[str, Any]]) -> str:
    """Generate a Mermaid ERD string from tables and foreign keys."""
    erd_lines = ["erDiagram"]
    
    # Shorten types for Mermaid readability
    def _get_mermaid_type(sql_type: str) -> str:
        sql_type = str(sql_type).lower()
        if any(t in sql_type for t in ("int", "serial", "numeric", "decimal", "float", "double")):
            return "number"
        if any(t in sql_type for t in ("date", "time")):
            return "datetime"
        if "bool" in sql_type:
            return "boolean"
        return "string"

    for table in tables:
        t_name = table["table"]
        erd_lines.append(f'    "{t_name}" {{')
        for col in table.get("columns", []):
            col_name = col["name"]
            m_type = _get_mermaid_type(col["dtype"])
            pk_marker = "PK" if col.get("primary_key") else ""
            
            # Check if this column is a foreign key
            is_fk = any(
                fk["from_table"] == t_name and fk["from_col"] == col_name 
                for fk in foreign_keys
            )
            fk_marker = "FK" if is_fk else ""
            
            # Formatting line with markers
            line = f'        {m_type} {col_name}'
            if pk_marker or fk_marker:
                line += f' {pk_marker}{" " if pk_marker and fk_marker else ""}{fk_marker}'
            erd_lines.append(line)
        erd_lines.append('    }')
    
    # Relationships
    fk_set = set()
    for fk in foreign_keys:
        # Mermaid relationship string
        # using ||--o{ for one-to-many as a standard heuristic
        fk_str = f'    "{fk["from_table"]}" ||--o{{ "{fk["to_table"]}" : "{fk["from_col"]}->{fk["to_col"]}"'
        if fk_str not in fk_set:
            erd_lines.append(fk_str)
            fk_set.add(fk_str)
            
    return "\n".join(erd_lines)

def infer_foreign_keys(tables: List[Dict[str, Any]], existing_fks: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Heuristic logic to infer relationships in databases without formal FK constraints."""
    foreign_keys = list(existing_fks) if existing_fks else []
    
    if len(tables) <= 1:
        return foreign_keys

    # Map for quick lookup
    existing_map = set((fk["from_table"].lower(), fk["from_col"].lower(), fk["to_table"].lower()) for fk in foreign_keys)

    for t1 in tables:
        t1_name = t1["table"].lower()
        for c1 in t1["columns"]:
            col_name = c1["name"].lower()
            
            # Heuristic 1: ID-based linking (customer_id -> customers.id)
            target_base = None
            if col_name.endswith("_id") and col_name != "id":
                target_base = col_name[:-3]
            elif col_name.endswith("_zip_code_prefix"):
                target_base = col_name.replace("_zip_code_prefix", "")
            elif col_name.endswith("id") and len(col_name) > 2:
                target_base = col_name[:-2].rstrip("_")
            
            if target_base:
                for t2 in tables:
                    t2_name = t2["table"].lower()
                    if t1_name == t2_name: continue
                    
                    clean_t2 = t2_name.replace("olist_", "").replace("_dataset", "").replace("tbl_", "")
                    
                    is_match = (
                        t2_name == target_base or 
                        t2_name == target_base + "s" or 
                        t2_name == target_base + "es" or
                        clean_t2 == target_base or
                        clean_t2 == target_base + "s" or
                        (target_base.endswith("y") and t2_name == target_base[:-1] + "ies") or
                        f"_{target_base}" in t2_name or
                        (target_base in t2_name and "_dataset" in t2_name)
                    )
                    
                    if is_match:
                        # Find potential PK in target table
                        t2_cols = [c["name"] for c in t2["columns"]]
                        t2_cols_lower = [c.lower() for c in t2_cols]
                        
                        pk_col = None
                        if col_name in t2_cols_lower:
                            pk_col = t2_cols[t2_cols_lower.index(col_name)]
                        elif "id" in t2_cols_lower:
                            pk_col = t2_cols[t2_cols_lower.index("id")]
                        
                        if pk_col:
                            if (t1["table"].lower(), c1["name"].lower(), t2["table"].lower()) not in existing_map:
                                foreign_keys.append({
                                    "from_table": t1["table"],
                                    "from_col": c1["name"],
                                    "to_table": t2["table"],
                                    "to_col": pk_col
                                })
                                existing_map.add((t1["table"].lower(), c1["name"].lower(), t2["table"].lower()))
                                break

            # Heuristic 2: Unusual Shared Column Names (length > 8)
            if len(col_name) > 8 and not col_name.endswith("id"):
                if col_name in ("created_at", "updated_at", "status", "description", "timestamp", "last_updated"):
                    continue
                    
                for t2 in tables:
                    t2_name = t2["table"].lower()
                    if t1_name == t2_name: continue
                    
                    t2_cols = [c["name"] for c in t2["columns"]]
                    t2_cols_lower = [c.lower() for c in t2_cols]
                    
                    if col_name in t2_cols_lower:
                        if (t1["table"].lower(), c1["name"].lower(), t2["table"].lower()) not in existing_map:
                            foreign_keys.append({
                                "from_table": t1["table"],
                                "from_col": c1["name"],
                                "to_table": t2["table"],
                                "to_col": t2_cols[t2_cols_lower.index(col_name)]
                            })
                            existing_map.add((t1["table"].lower(), c1["name"].lower(), t2["table"].lower()))

    return foreign_keys
