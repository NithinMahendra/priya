from app.services.dependency_scanner import DependencyScanner


def test_dependency_scanner_flags_outdated_python_packages() -> None:
    manifest = """
django==3.2.0
pyyaml==5.3
requests==2.25.0
""".strip()
    scanner = DependencyScanner()
    issues = scanner.scan(manifest, manifest_type="requirements")
    assert len(issues) >= 2
    assert any("django" in issue["message"].lower() for issue in issues)


def test_dependency_scanner_flags_outdated_npm_packages() -> None:
    manifest = """
{
  "dependencies": {
    "lodash": "4.17.15",
    "axios": "1.0.0"
  }
}
""".strip()
    scanner = DependencyScanner()
    issues = scanner.scan(manifest, manifest_type="package_json")
    assert any("lodash" in issue["message"].lower() for issue in issues)
