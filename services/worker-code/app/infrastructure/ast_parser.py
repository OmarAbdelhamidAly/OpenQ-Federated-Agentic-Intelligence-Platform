import os
import structlog
from tree_sitter import Language, Parser

# Import all supported grammars
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_java
import tree_sitter_cpp
import tree_sitter_go
import tree_sitter_rust
import tree_sitter_ruby
import tree_sitter_php
import tree_sitter_c_sharp
import tree_sitter_html
import tree_sitter_css


logger = structlog.get_logger(__name__)

_MAX_FILE_BYTES = 1024 * 1024  # 1MB size limit

# ── Language Registry Definition ───────────────────────────────────────────

class LanguageSpec:
    def __init__(self, language: Language, extensions: list[str], node_map: dict[str, list[str]]):
        self.language = language
        self.extensions = extensions
        self.node_map = node_map  # Maps "Class" or "Function" to tree-sitter node types

def load_languages():
    registry: dict[str, LanguageSpec] = {}
    
    try:
        # Python
        registry['python'] = LanguageSpec(
            Language(tree_sitter_python.language()),
            [".py"],
            {
                "Class":    ["class_definition"], 
                "Function": ["function_definition"],
                "Import":   ["import_statement", "import_from_statement"],
                "Call":     ["call"]
            }
        )
        
        # JS / TS (React / Next.js)
        registry['javascript'] = LanguageSpec(
            Language(tree_sitter_javascript.language()),
            [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"],
            {
                "Class":    ["class_declaration", "class"],
                "Function": ["function_declaration", "method_definition", "function", "arrow_function", "export_statement"],
                "Import":   ["import_statement"],
                "Call":     ["call_expression"]
            }
        )


        # HTML
        registry['html'] = LanguageSpec(
            Language(tree_sitter_html.language()),
            [".html", ".htm"],
            {"Class": ["element"], "Function": ["script_element", "style_element"]}
        )

        # CSS
        registry['css'] = LanguageSpec(
            Language(tree_sitter_css.language()),
            [".css", ".scss", ".sass", ".less"],
            {"Class": ["class_selector"], "Function": ["id_selector", "media_statement"]}
        )

        # Java
        registry['java'] = LanguageSpec(

            Language(tree_sitter_java.language()),
            [".java"],
            {"Class": ["class_declaration"], "Function": ["method_declaration"]}
        )

        # C++
        registry['cpp'] = LanguageSpec(
            Language(tree_sitter_cpp.language()),
            [".cpp", ".hpp", ".cc", ".cxx", ".c", ".h"],
            {"Class": ["class_specifier", "struct_specifier"], "Function": ["function_definition"]}
        )

        # Go
        registry['go'] = LanguageSpec(
            Language(tree_sitter_go.language()),
            [".go"],
            {"Class": ["type_declaration"], "Function": ["function_declaration", "method_declaration"]}
        )

        # Rust
        registry['rust'] = LanguageSpec(
            Language(tree_sitter_rust.language()),
            [".rs"],
            {"Class": ["struct_item", "enum_item", "trait_item"], "Function": ["function_item"]}
        )

        # Ruby
        registry['ruby'] = LanguageSpec(
            Language(tree_sitter_ruby.language()),
            [".rb"],
            {"Class": ["class", "module"], "Function": ["method"]}
        )

        # PHP
        registry['php'] = LanguageSpec(
            Language(tree_sitter_php.language()),
            [".php"],
            {"Class": ["class_declaration"], "Function": ["function_definition", "method_declaration"]}
        )

        # C#
        registry['c_sharp'] = LanguageSpec(
            Language(tree_sitter_c_sharp.language()),
            [".cs"],
            {"Class": ["class_declaration", "struct_declaration"], "Function": ["method_declaration"]}
        )

    except Exception as exc:
        logger.error("tree_sitter_registry_init_failed", error=str(exc))
        
    return registry

LANGUAGE_REGISTRY = load_languages()

EXT_TO_LANG: dict[str, str] = {}
for lang_id, spec in LANGUAGE_REGISTRY.items():
    for ext in spec.extensions:
        EXT_TO_LANG[ext.lower()] = lang_id


class ASTParser:
    """
    Universal Codebase Parser supporting both Backend (Python, Java, etc.)
    and Frontend (React, Next.js, HTML, CSS, Vue) technologies.
    """

    def __init__(self):
        self.parsers: dict[str, Parser] = {}
        for lang_id, spec in LANGUAGE_REGISTRY.items():
            p = Parser(spec.language)
            self.parsers[lang_id] = p

    def parse_file(self, file_path: str) -> list[dict]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in EXT_TO_LANG:
            return []

        lang_id = EXT_TO_LANG[ext]
        parser = self.parsers.get(lang_id)
        if not parser:
            return []

        try:
            file_size = os.path.getsize(file_path)
            if file_size > _MAX_FILE_BYTES:
                return []
            
            with open(file_path, "rb") as fh:
                code_bytes = fh.read()
        except OSError:
            return []

        try:
            tree = parser.parse(code_bytes)
            spec = LANGUAGE_REGISTRY[lang_id]
            return self._extract_nodes_generic(tree.root_node, code_bytes, spec.node_map, lang_id)
        except Exception as exc:
            logger.error("ast_parse_failed", file_path=file_path, lang=lang_id, error=str(exc))
            return []

    def _extract_nodes_generic(self, root_node, code_bytes: bytes, node_map: dict[str, list[str]], lang_id: str) -> list[dict]:
        entities = []
        ts_to_entity = {}
        for entity_type, ts_types in node_map.items():
            for ts_type in ts_types:
                ts_to_entity[ts_type] = entity_type

        def get_node_name(node, entity_type):
            # 1. Specialized Extraction for Imports/Calls
            if entity_type == "Import":
                if lang_id == 'python':
                    # import_statement or import_from_statement
                    module_node = node.child_by_field_name("module_name") or node.child_by_field_name("name")
                    if module_node:
                        return code_bytes[module_node.start_byte:module_node.end_byte].decode("utf-8", errors="replace")
                elif lang_id == 'javascript':
                    # import_statement source: (string)
                    source_node = node.child_by_field_name("source")
                    if source_node:
                        return source_node.text.decode("utf-8", errors="replace").strip('"\'')
                return "unknown_import"

            if entity_type == "Call":
                # call (py) or call_expression (js)
                func_node = node.child_by_field_name("function")
                if func_node:
                    # Could be identifier or member_expression/attribute
                    if func_node.type in ["identifier", "property_identifier"]:
                        return func_node.text.decode("utf-8", errors="replace")
                    # nested case: obj.method
                    last_child = func_node.named_children[-1] if func_node.named_children else None
                    if last_child:
                        return last_child.text.decode("utf-8", errors="replace")
                return "anonymous_call"

            # 2. Existing Class/Function logic
            name_node = node.child_by_field_name("name")
            if name_node:
                return code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
            
            # Language specific fallbacks
            if lang_id == 'css' and node.type == 'class_selector':
                return node.text.decode("utf-8", errors="replace")
            
            if lang_id == 'html' and node.type == 'element':
                for child in node.children:
                    if child.type == 'start_tag':
                        for attr in child.children:
                            if attr.type == 'attribute':
                                name_attr = attr.child_by_field_name('name')
                                if name_attr and name_attr.text == b'id':
                                    val_attr = attr.child_by_field_name('value')
                                    if val_attr:
                                        return val_attr.text.decode("utf-8", errors="replace").strip('"\'')
                return "html_element"

            # Generic identifier search
            for child in node.children:
                if child.type in ["identifier", "property_identifier", "variable_identifier"]:
                    return code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            
            return None

        def traverse(node, context_stack):
            entity_type = ts_to_entity.get(node.type)
            name = None
            if entity_type:
                name = get_node_name(node, entity_type)
                if name:
                    entity_dict = {
                        "type":       entity_type,
                        "name":       name,
                        "code":       code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace") if entity_type in ["Class", "Function"] else "",
                        "line_start": node.start_point[0] + 1,
                        "line_end":   node.end_point[0] + 1,
                    }
                    if entity_type == "Call":
                        entity_dict["caller_name"] = context_stack[-1] if context_stack else "global"
                    
                    entities.append(entity_dict)
            
            new_stack = list(context_stack)
            if entity_type in ["Class", "Function"] and name:
                new_stack.append(name)

            for child in node.children:
                traverse(child, new_stack)

        traverse(root_node, [])
        return entities

