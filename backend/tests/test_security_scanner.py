from app.services.security_scanner import SecurityScanner


def test_security_scanner_detects_common_issues() -> None:
    code = """
query = "SELECT * FROM users WHERE id=" + user_input
cursor.execute(query)
result = eval(user_input)
obj = pickle.loads(payload)
subprocess.run(command, shell=True)
API_KEY = "THIS_SHOULD_NOT_BE_HARDCODED"
""".strip()

    scanner = SecurityScanner()
    issues = scanner.scan(code)

    severities = [issue["severity"] for issue in issues]
    messages = [issue["message"] for issue in issues]

    assert "Critical" in severities
    assert any("eval" in message.lower() for message in messages)
    assert any("deserialization" in message.lower() for message in messages)
    assert any("subprocess" in message.lower() for message in messages)
