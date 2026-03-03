from app.services.performance_analyzer import PerformanceAnalyzer


def test_performance_analyzer_detects_nested_python_loops() -> None:
    code = """
def run(values):
    total = 0
    for outer in values:
        for inner in values:
            total += outer * inner
    return total
""".strip()
    analyzer = PerformanceAnalyzer()
    result = analyzer.analyze(code=code, language="python")
    assert result["time_complexity"] in {"O(n^2)", "O(n^k)"}
    assert isinstance(result["hotspots"], list)
    assert len(result["hotspots"]) >= 1


def test_performance_analyzer_detects_nested_java_loops() -> None:
    code = """
class Sample {
    void run(int[] arr) {
        for (int i = 0; i < arr.length; i++) {
            for (int j = 0; j < arr.length; j++) {
                System.out.println(arr[i] + arr[j]);
            }
        }
    }
}
""".strip()
    analyzer = PerformanceAnalyzer()
    result = analyzer.analyze(code=code, language="java")
    assert result["time_complexity"] in {"O(n^2)", "O(n^k)"}
    assert result["space_complexity"] in {"O(1)", "O(n)"}
