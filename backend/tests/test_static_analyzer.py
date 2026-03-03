from app.services.static_analyzer import StaticAnalyzer


def test_static_analyzer_detects_key_patterns() -> None:
    code = "\n".join(
        [
            "API_KEY = '1234567890ABCDEF'",
            "# TODO: refactor this",
            "def very_long_function():",
            *["    value = 1" for _ in range(52)],
            "    return value",
            "",
            "def nested():",
            "    for a in range(1):",
            "        for b in range(1):",
            "            for c in range(1):",
            "                print(a, b, c)",
            "    return 1",
        ]
    )

    analyzer = StaticAnalyzer()
    issues = analyzer.analyze(code)

    messages = {item["message"] for item in issues}
    assert any("hardcoded secret" in message.lower() for message in messages)
    assert any("TODO" in message for message in messages)
    assert any("lines long" in message for message in messages)
    assert any("nested loops" in message.lower() for message in messages)


def test_static_analyzer_detects_java_missing_semicolon() -> None:
    code = "\n".join(
        [
            "class arrayleftshift{",
            "    public static void main(String[] args){",
            '        System.out.println("niy")',
            "    }",
            "}",
        ]
    )
    analyzer = StaticAnalyzer()
    issues = analyzer.analyze(code=code, language="java", filename="Sample.java")
    messages = {item["message"] for item in issues}
    assert any("missing semicolon" in message.lower() for message in messages)
