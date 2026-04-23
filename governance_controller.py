import yaml
import re

# ==========================================
# YAML Boolean Patch (Fixes yes/no -> true/false)
# ==========================================

def patch_yaml_booleans():
    """ 
    Restricts PyYAML's boolean resolver to only true/false (YAML 1.2 style).
    This prevents 'yes', 'no', 'on', 'off' from being auto-converted to booleans.
    """
    strict_bool_re = re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$', re.X)
    
    for char in "yYnNoOtTfF":
        if char in yaml.SafeLoader.yaml_implicit_resolvers:
            resolvers = yaml.SafeLoader.yaml_implicit_resolvers[char]
            new_resolvers = []
            for tag, regexp in resolvers:
                if tag == 'tag:yaml.org,2002:bool':
                    new_resolvers.append((tag, strict_bool_re))
                else:
                    new_resolvers.append((tag, regexp))
            yaml.SafeLoader.yaml_implicit_resolvers[char] = new_resolvers

# Apply patch immediately
patch_yaml_booleans()

from api_governance import run_governance as run_api
from event_governance import run_governance as run_event


# ==========================================
# Naming Convention Detection (Fallback)
# ==========================================

def detect_by_naming(data):
    snake_count = 0
    pascal_count = 0

    def traverse(node):
        nonlocal snake_count, pascal_count

        if isinstance(node, dict):
            for key, value in node.items():

                # snake_case detection
                if re.match(r"^[a-z]+(_[a-z0-9]+)+$", key):
                    snake_count += 1

                # PascalCase detection
                if re.match(r"^[A-Z][a-zA-Z0-9]+$", key):
                    pascal_count += 1

                traverse(value)

        elif isinstance(node, list):
            for item in node:
                traverse(item)

    traverse(data)

    if snake_count > pascal_count:
        return "api"
    if pascal_count > snake_count:
        return "event"

    return None


# ==========================================
# Spec Detection
# ==========================================

def detect_spec_type(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return None

    # Backstage wrapped spec
    if isinstance(data, dict):
        if data.get("kind") == "API":
            spec_type = data.get("spec", {}).get("type")
            if spec_type == "openapi":
                return "api"
            if spec_type == "asyncapi":
                return "event"

        # Pure spec
        if "openapi" in data:
            return "api"
        if "asyncapi" in data:
            return "event"

        # Fallback detection
        return detect_by_naming(data)

    return None


# ==========================================
# Unified Runner
# ==========================================

def run_governance(file_path, mode, override=None, user_actions=None):

    if override in ["api", "event"]:
        spec_type = override
    else:
        spec_type = detect_spec_type(file_path)

    if spec_type == "api":
        result = run_api(file_path, mode, user_actions)
        return result, "OpenAPI"

    if spec_type == "event":
        result = run_event(file_path, mode, user_actions)
        return result, "AsyncAPI"

    return [], "Unknown"