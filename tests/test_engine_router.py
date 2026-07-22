from core.engine_router import detect_engine


def test_python_is_default():
    assert detect_engine("print('VERDICT: PASS')") == "python"


def test_sympy_marker_routes_to_python():
    assert detect_engine("# ASTRA_ENGINE: sympy\nimport sympy") == "python"


def test_lean_marker_is_detected():
    code = "# ASTRA_ENGINE: lean\nimport Mathlib\ntheorem truth : True := by trivial"
    assert detect_engine(code) == "lean"


def test_lean_source_is_detected_without_marker():
    assert detect_engine("import Mathlib\ntheorem truth : True := by trivial") == "lean"
