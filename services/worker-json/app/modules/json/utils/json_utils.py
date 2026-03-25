import pandas as pd
from typing import Any, Dict, List

def flatten_json(data: Any) -> List[Dict[str, Any]]:
    """Flatten nested JSON data into a list of simple dicts for tabular use."""
    if not data:
        return []
    
    if isinstance(data, list):
        flattened_list = []
        for item in data:
            if isinstance(item, dict):
                flattened_list.append(_flatten_dict(item))
            else:
                flattened_list.append({"value": item})
        return flattened_list
    
    if isinstance(data, dict):
        return [_flatten_dict(data)]
        
    return [{"value": data}]

def _flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """Recursive dict flattener."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)
