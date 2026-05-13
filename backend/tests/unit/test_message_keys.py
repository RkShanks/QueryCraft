"""T-184: Backend error responses use message_key from en.json.

Verifies that:
1. Every concrete custom exception class exposes a non-empty message_key attribute.
2. Every exception message_key value exists in frontend/src/locales/en.json.
3. Every HTTPException detail dict in backend source contains a message_key.
4. Every message_key referenced in HTTPException detail dicts exists in en.json.
"""

import ast
import inspect
import json
from pathlib import Path

import pytest

from app.core import exceptions as exc_module


def _get_concrete_exception_classes():
    """Return exception classes that are leaf nodes (not base classes)."""
    all_classes = {
        getattr(exc_module, name)
        for name in dir(exc_module)
        if inspect.isclass(cls := getattr(exc_module, name))
        and issubclass(cls, exc_module.QueryCraftError)
        and cls is not exc_module.QueryCraftError
        and not name.startswith("_")
    }
    # Filter out classes that are subclassed by others in the set
    leaf_classes = set()
    for cls in all_classes:
        if not any(issubclass(other, cls) for other in all_classes if other is not cls):
            leaf_classes.add(cls)
    return leaf_classes


class TestMessageKeys:
    """Unit tests for backend error message_key consistency with en.json."""

    @pytest.fixture(scope="class")
    def en_json_keys(self):
        """Load and flatten all keys from en.json."""
        en_path = Path(__file__).parents[3] / "frontend" / "src" / "locales" / "en.json"
        with open(en_path, encoding="utf-8") as f:
            data = json.load(f)

        def flatten(obj, prefix=""):
            keys = set()
            for k, v in obj.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.update(flatten(v, full))
                else:
                    keys.add(full)
            return keys

        return flatten(data)

    def test_all_exceptions_have_message_key(self):
        """Every concrete exception class should expose a non-empty message_key."""
        leaf_classes = _get_concrete_exception_classes()
        assert leaf_classes, "No concrete exception classes found"
        for cls in leaf_classes:
            instance = cls()
            assert hasattr(instance, "message_key"), f"{cls.__name__} missing message_key attribute"
            assert instance.message_key, f"{cls.__name__}.message_key is empty"

    def test_all_exception_keys_exist_in_en_json(self, en_json_keys):
        """Every concrete exception's message_key must be present in en.json."""
        missing = []
        for cls in _get_concrete_exception_classes():
            instance = cls()
            key = instance.message_key
            if key and key not in en_json_keys:
                missing.append((cls.__name__, key))
        assert not missing, f"Missing keys in en.json: {missing}"

    def test_no_hardcoded_strings_in_http_exception_handlers(self):
        """Scan backend source for HTTPException calls lacking message_key."""
        src_dir = Path(__file__).parents[2] / "src" / "app"
        violations = []

        for py_file in src_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    is_http_exc = (isinstance(func, ast.Name) and func.id == "HTTPException") or (
                        isinstance(func, ast.Attribute) and func.attr == "HTTPException"
                    )
                    if not is_http_exc:
                        continue

                    detail_arg = None
                    for kw in node.keywords:
                        if kw.arg == "detail":
                            detail_arg = kw.value
                            break

                    if detail_arg is None:
                        continue

                    if isinstance(detail_arg, ast.Dict):
                        keys = [
                            k.value for k in detail_arg.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)
                        ]
                        if "message_key" not in keys:
                            violations.append(f"{py_file.relative_to(src_dir)}:{node.lineno}")
                    elif isinstance(detail_arg, ast.Constant) and isinstance(detail_arg.value, str):
                        violations.append(f"{py_file.relative_to(src_dir)}:{node.lineno}")

        assert not violations, f"HTTPException calls without message_key found at: {violations}"

    def test_all_handler_message_keys_exist_in_en_json(self, en_json_keys):
        """Every message_key referenced in HTTPException detail dicts must exist in en.json."""
        src_dir = Path(__file__).parents[2] / "src" / "app"
        handler_keys = set()

        for py_file in src_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    is_http_exc = (isinstance(func, ast.Name) and func.id == "HTTPException") or (
                        isinstance(func, ast.Attribute) and func.attr == "HTTPException"
                    )
                    if not is_http_exc:
                        continue

                    for kw in node.keywords:
                        if kw.arg == "detail" and isinstance(kw.value, ast.Dict):
                            # Find the message_key value in the dict
                            for i, key_node in enumerate(kw.value.keys):
                                if isinstance(key_node, ast.Constant) and key_node.value == "message_key":
                                    val_node = kw.value.values[i]
                                    if isinstance(val_node, ast.Constant) and isinstance(val_node.value, str):
                                        handler_keys.add(val_node.value)
                                    break

        missing = [k for k in handler_keys if k not in en_json_keys]
        assert not missing, f"Handler message_keys missing in en.json: {missing}"
