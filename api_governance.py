import yaml
import re
import sys
from pathlib import Path

ACRONYMS = {"ID", "ISO", "UTC", "URL", "URI", "JSON", "API"}
PROPER_WORDS = {
    "Seller", "Buyer", "Carrier", "Auction", "Charity", "Publisher",
    "Peddle Carrier", "Offer", "Instant Offer", "Bid", "Additional Fee",
    "Facility", "Company"
}


# =====================================================
# YAML Literal Block Support (Fixes \n Issue)
# =====================================================

class LiteralString(str):
    pass


def literal_representer(dumper, data):
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str",
        data,
        style="|"
    )


yaml.add_representer(LiteralString, literal_representer)


# =====================================================
# Utility Functions
# =====================================================

def split_snake_case(name):
    return name.split("_")


def capitalize_acronyms(text):
    # Combine acronyms and proper words for easy processing
    special_words = list(ACRONYMS) + list(PROPER_WORDS)
    
    # Sort terms by length (longest first) to avoid incorrect partial matches 
    # (e.g., matching "Offer" inside "Instant Offer")
    special_words.sort(key=len, reverse=True)

    for word in special_words:
        # Use word boundaries and ignore case to find and fix capitalization
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        text = pattern.sub(word, text)
    return text


def to_sentence_case(text):
    if not text:
        return ""
    
    # Lowercase everything first to normalize
    text = text.lower()
    
    # Split by common sentence boundaries while keeping the separators
    parts = re.split(r'([.!?]\s*)', text)
    
    result = []
    capitalize_next = True
    
    for part in parts:
        if not part:
            continue
            
        if capitalize_next:
            # Find the first alphanumeric character in this segment
            for i, char in enumerate(part):
                if char.isalnum():
                    part = part[:i] + char.upper() + part[i+1:]
                    capitalize_next = False
                    break
        
        # If this part contains a sentence ender, the NEXT segment should be capitalized
        if re.search(r'[.!?]', part):
            capitalize_next = True
            
        result.append(part)
        
    final_text = "".join(result)
    return capitalize_acronyms(final_text)


def normalize_punctuation(text):
    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    sentences = re.split(r"\.\s+|\.$", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 1:
        return text.rstrip(".")

    fixed = []
    for s in sentences:
        if not s.endswith("."):
            s += "."
        fixed.append(s)

    return " ".join(fixed)


def remove_examples(text):
    text = re.sub(r"\([^)]*\b(?:e\.g\.|eg\b|ex\.|ex\b|examples?\b)[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[\s\-,;]*\b(?:e\.g\.|eg\b|ex\.|ex\b|examples?\b).*", "", text, flags=re.IGNORECASE)
    
    text = text.strip()
    if text.endswith("("):
        text = text[:-1].strip()
        
    text = re.sub(r"[,:;/\-]\s*$", "", text)
    return text.strip()


def normalize_text(text):
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace(".", "")
    return text


def build_field_base(field_name, suffix):
    parts = split_snake_case(field_name)
    if parts and parts[-1] == suffix:
        parts = parts[:-1]
    return " ".join(word.capitalize() for word in parts)


def get_object_name(path):
    """Extract parent object name from path (e.g., Buyer)."""
    if len(path) >= 3 and path[-2] == "properties":
        return path[-3]
    return "property"


def generate_boolean_description(field_name, path):
    """Generate standardized 'True, if...' descriptions for boolean fields."""
    obj_name = get_object_name(path)
    lower_name = field_name.lower()
    has_is = lower_name.startswith("is_")
    has_enabled = lower_name.endswith("_enabled")
    
    # Check if this is an "Active" field (case-insensitive)
    is_active_base = lower_name.replace("is_", "").replace("_enabled", "").strip() == "active"

    suggestions = []
    
    # Suggestion 1: is_ prefix style or "Active" override
    if is_active_base:
        suggestions.append(f"True, if {obj_name} is active")
    else:
        base = field_name[3:] if has_is else field_name
        words = base.replace("_", " ").strip()
        parts = words.split()
        if len(parts) > 1:
            suggestions.append(f"True, if {' '.join(parts[:-1])} is {parts[-1]}")
        else:
            suggestions.append(f"True, if {words} is {words}")

    # Suggestion 2: enabled suffix style
    # Always include this suggestion for ambiguous/invalid names
    base = field_name[:-8] if has_enabled else field_name
    # Also strip is_ if we're suggesting an enabled suffix style
    if base.lower().startswith("is_"):
        base = base[3:]
    words = base.replace("_", " ").strip()
    suggestions.append(f"True, if {words} is enabled")

    # If the name is valid, return only the corresponding suggestion
    if has_is and not has_enabled:
        return suggestions[0]
    if has_enabled and not has_is:
        return suggestions[1]
        
    # Ambiguous or invalid (both or neither): return both separated by ||
    unique_suggestions = list(dict.fromkeys(suggestions))
    return " || ".join(unique_suggestions)


# =====================================================
# Rule Engine
# =====================================================

class RuleEngine:

    def __init__(self, mode, user_actions=None):
        self.mode = mode
        self.violations = []
        self.changes = []
        self.user_actions = user_actions or {}

    def get_user_action(self, path_str, issue_type):
        key = f"{path_str}|{issue_type}"
        return self.user_actions.get(key, {})

    def validate_and_fix_datatype(self, field_name, field_body, current_path, expected_type, expected_format):

        current_type = field_body.get("type", "")
        current_format = field_body.get("format", "")

        if current_type != expected_type or current_format != expected_format:
            path_str = ".".join(str(p) for p in current_path)
            
            expected_str = expected_type
            if expected_format:
                expected_str += f" + {expected_format}"
                
            found_str = current_type
            if current_format:
                found_str += f" + {current_format}"

            if self.mode == "validate":
                self.violations.append({
                    "field": field_name,
                    "path": path_str,
                    "issue": "datatype",
                    "expected": expected_str,
                    "found": found_str
                })
            else:
                action = self.get_user_action(path_str, "datatype")
                if action.get("ignore"):
                    return
                
                edit_val = action.get("edit")
                if edit_val:
                    # parse "type + format" or just "type"
                    parts = [p.strip() for p in edit_val.split("+")]
                    field_body["type"] = parts[0]
                    if len(parts) > 1:
                        field_body["format"] = parts[1]
                    elif "format" in field_body:
                        del field_body["format"]
                    self.changes.append(f"MANUAL FIX DATATYPE -> {field_name} (path: {path_str}) to {edit_val}")
                else:
                    field_body["type"] = expected_type
                    if expected_format:
                        field_body["format"] = expected_format
                    elif "format" in field_body:
                        del field_body["format"]
                    self.changes.append(f"AUTO FIX DATATYPE -> {field_name} (path: {path_str}) to {expected_str}")

    # =====================================================
    # DATA TYPE VALIDATION
    # =====================================================

    def apply_rules(self, field_name, field_body, current_path):

        old_description = field_body.get("description", "")
        new_description = None
        path_str = ".".join(str(p) for p in current_path)

        # ------------------------------------------------
        # Step 1: Clean examples + fix punctuation
        # ------------------------------------------------
        if old_description:
            cleaned = remove_examples(old_description)
            # Enforce sentence casing and fix acronyms
            sentence_cased = to_sentence_case(cleaned)
            normalized_existing = normalize_punctuation(sentence_cased)

            if old_description != normalized_existing:
                if self.mode == "fix":
                    action = self.get_user_action(path_str, "formatting")
                    if not action.get("ignore"):
                        final_val = action.get("edit") or normalized_existing
                        field_body["description"] = final_val
                        self.changes.append(
                            f"FIX FORMATTING -> {field_name} (path: {path_str})\n"
                            f"OLD: {old_description}\n"
                            f"NEW: {final_val}\n"
                        )
                        old_description = final_val
                else:
                    self.violations.append({
                        "field": field_name,
                        "path": path_str,
                        "issue": "formatting",
                        "expected": normalized_existing,
                        "found": old_description
                    })

        # ------------------------------------------------
        # Step 2: Field-based rules
        # ------------------------------------------------

        if field_name.endswith("_at"):
            base = build_field_base(field_name, "at")
            new_description = f"{base} date and time in ISO 8601 UTC timezone"
            self.validate_and_fix_datatype(field_name, field_body, current_path, "string", "date-time")

        elif field_name.endswith("_on"):
            base = build_field_base(field_name, "on")
            new_description = f"{base} date in yyyy-mm-dd format"
            self.validate_and_fix_datatype(field_name, field_body, current_path, "string", "date")

        elif field_name.endswith("_time"):
            base = build_field_base(field_name, "time")
            new_description = f"{base} time in hh:mm:ss format"
            self.validate_and_fix_datatype(field_name, field_body, current_path, "string", "time")

        # ------------------------------------------------
        # Step 2.5: Boolean Naming Rule
        # ------------------------------------------------
        if field_body.get("type") == "boolean":
            has_is = field_name.startswith("is_")
            has_enabled = field_name.endswith("_enabled")

            if (has_is and has_enabled) or (not has_is and not has_enabled):
                path_str = ".".join(str(p) for p in current_path)
                
                expected = ""
                if has_is and has_enabled:
                    expected = f"Choose either is_ prefix or _enabled suffix (not both)"
                else:
                    expected = f"Should start with is_ or end with _enabled"

                self.violations.append({
                    "field": field_name,
                    "path": path_str,
                    "issue": "boolean_naming",
                    "expected": expected,
                    "found": field_name
                })

            # Boolean Description Rule
            expected_desc = generate_boolean_description(field_name, current_path)
            
            is_ambiguous = " || " in expected_desc
            if is_ambiguous:
                options = [o.strip() for o in expected_desc.split("||")]
                is_valid_bool_desc = old_description in options
            else:
                is_valid_bool_desc = (old_description == expected_desc)

            if not is_valid_bool_desc:
                
                if self.mode == "fix":
                    action = self.get_user_action(path_str, "boolean_description")
                    if not action.get("ignore"):
                        final_val = action.get("edit")
                        # Only auto-fix if NOT ambiguous
                        if not final_val and not is_ambiguous:
                            final_val = expected_desc
                            
                        if final_val:
                            field_body["description"] = final_val
                            self.changes.append(
                                f"FIX BOOLEAN DESCRIPTION -> {field_name} (path: {path_str})\n"
                                f"OLD: {old_description}\n"
                                f"NEW: {final_val}\n"
                            )
                else:
                    self.violations.append({
                        "field": field_name,
                        "path": path_str,
                        "issue": "boolean_description",
                        "expected": expected_desc,
                        "found": old_description
                    })

        # ------------------------------------------------
        # Step 3: Format generated description
        # ------------------------------------------------
        if new_description:
            new_description = remove_examples(new_description)
            new_description = to_sentence_case(new_description)
            new_description = normalize_punctuation(new_description)

        # ------------------------------------------------
        # Step 4: Missing description
        # ------------------------------------------------
        if not old_description and new_description:
            if self.mode == "fix":
                action = self.get_user_action(path_str, "missing_description")
                if not action.get("ignore"):
                    final_val = action.get("edit") or new_description
                    field_body["description"] = final_val
                    self.changes.append(f"ADD DESCRIPTION -> {field_name} (path: {path_str}) NEW: {final_val}\n")
            else:
                self.violations.append({
                    "field": field_name,
                    "path": path_str,
                    "issue": "missing_description",
                    "expected": new_description,
                    "found": ""
                })
            return

        # ------------------------------------------------
        # Step 5: Compare and update
        # ------------------------------------------------
        if old_description and new_description:

            normalized_old = normalize_text(old_description)
            normalized_new = normalize_text(new_description)

            if normalized_old == normalized_new:
                return
                
            if self.mode == "fix":
                action = self.get_user_action(path_str, "description_mismatch")
                if not action.get("ignore"):
                    final_val = action.get("edit") or new_description
                    field_body["description"] = final_val
                    self.changes.append(
                        f"FIX DESCRIPTION -> {field_name} (path: {path_str})\n"
                        f"OLD: {old_description}\n"
                        f"NEW: {final_val}\n"
                    )
            else:
                self.violations.append({
                    "field": field_name,
                    "path": path_str,
                    "issue": "description_mismatch",
                    "expected": new_description,
                    "found": old_description
                })

    # =====================================================
    # Traversal
    # =====================================================

    def traverse(self, node, current_path=None):
        if current_path is None:
            current_path = []

        if isinstance(node, dict):

            if node.get("type") == "object" and "properties" in node:
                for field_name, field_body in node["properties"].items():
                    if isinstance(field_body, dict):
                        field_path = current_path + ["properties", field_name]
                        self.apply_rules(field_name, field_body, field_path)

            for key, value in node.items():
                self.traverse(value, current_path + [key])

        elif isinstance(node, list):
            for i, item in enumerate(node):
                self.traverse(item, current_path + [i])


# =====================================================
# OpenAPI Extraction
# =====================================================

def extract_openapi_definition(data):

    if "openapi" in data:
        return data, None

    if (
        data.get("kind") == "API"
        and data.get("spec", {}).get("type") == "openapi"
        and "definition" in data.get("spec", {})
    ):
        definition_str = data["spec"]["definition"]
        parsed_definition = yaml.safe_load(definition_str)
        return parsed_definition, "backstage"

    return None, None


# =====================================================
# Main
# =====================================================

def main(file_path, mode, user_actions=None):

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    openapi_data, wrapper_type = extract_openapi_definition(data)

    if not openapi_data:
        return []

    engine = RuleEngine(mode, user_actions)
    engine.traverse(openapi_data)

    if mode == "validate":
        return engine.violations

    if mode == "fix":
        if wrapper_type == "backstage":
            dumped_definition = yaml.dump(
                openapi_data,
                sort_keys=False,
                default_flow_style=False
            )
            data["spec"]["definition"] = LiteralString(dumped_definition)
            updated_content = data
        else:
            updated_content = openapi_data

        output_path = Path(file_path).with_name(
            Path(file_path).stem + "_updated.yaml"
        )

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                updated_content,
                f,
                sort_keys=False,
                default_flow_style=False
            )

        return engine.changes


def run_governance(file_path, mode, user_actions=None):
    return main(file_path, mode, user_actions)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[2] != "--mode":
        print("Usage: python api_governance.py file.yaml --mode validate|fix")
    else:
        print(main(sys.argv[1], sys.argv[3]))