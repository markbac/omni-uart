"""Unit test for OmniUART performance benchmarking suite (#224, #340)."""

import pytest
from omniuart.benchmarks import (
    BenchmarkMetric,
    PerformanceBenchmarkSuite,
    compare_against_baseline,
    save_baseline,
)


def test_performance_benchmark_suite_execution():
    suite = PerformanceBenchmarkSuite()
    report = suite.run_suite()

    assert "environment" in report
    assert "benchmarks" in report

    benchmarks = report["benchmarks"]
    assert "codec_encode" in benchmarks
    assert "codec_decode" in benchmarks
    assert "stream_extract" in benchmarks
    assert "transport_roundtrip" in benchmarks

    encode = benchmarks["codec_encode"]
    assert encode["operations_count"] > 0
    assert encode["ops_per_sec"] > 0
    assert encode["throughput_mb_per_sec"] > 0
    assert encode["avg_latency_us"] > 0


def test_individual_benchmark_metrics():
    suite = PerformanceBenchmarkSuite()
    metric = suite.benchmark_codec_encode(iterations=100)

    assert isinstance(metric, BenchmarkMetric)
    assert metric.name == "codec_encode"
    assert metric.operations_count == 100
    assert metric.duration_sec > 0


def test_benchmarks_fail_on_decode_error(monkeypatch):
    """Assert that decode benchmark raises RuntimeError on decode failure instead of skipping (#340)."""
    suite = PerformanceBenchmarkSuite()
    from omniuart.core.codec import DecodedFrame
    monkeypatch.setattr(suite.codec, "decode", lambda *args, **kwargs: DecodedFrame(raw=b"", kind="request", error="Simulated decode error"))

    with pytest.raises(RuntimeError, match="Decode iteration 0 failed"):
        suite.benchmark_codec_decode(iterations=5)


def test_benchmarks_fail_on_stream_extract_empty(monkeypatch):
    """Assert that stream extract benchmark raises RuntimeError instead of dividing by zero (#340)."""
    suite = PerformanceBenchmarkSuite()
    monkeypatch.setattr(suite.codec, "extract_frames", lambda *args, **kwargs: ([], b""))

    with pytest.raises(RuntimeError, match="Stream extract iteration 0 extracted no frames"):
        suite.benchmark_stream_extract(iterations=5)


def test_baseline_save_and_comparison(tmp_path):
    """Test saving baseline and detecting regressions (#340)."""
    suite = PerformanceBenchmarkSuite()
    results = suite.run_suite()

    baseline_file = tmp_path / "baseline_test.json"
    save_baseline(results, baseline_file)
    assert baseline_file.exists()

    # Compare against identical baseline -> passes
    cmp_res = compare_against_baseline(results, baseline_file)
    assert cmp_res["passed"] is True
    assert len(cmp_res["regressions"]) == 0

    # Simulate severe regression in current run
    regressed_results = dict(results)
    regressed_results["benchmarks"] = dict(results["benchmarks"])
    regressed_results["benchmarks"]["codec_encode"] = dict(results["benchmarks"]["codec_encode"])
    regressed_results["benchmarks"]["codec_encode"]["ops_per_sec"] = 1.0  # Massive drop

    cmp_regressed = compare_against_baseline(regressed_results, baseline_file, allowed_regression_pct=20.0)
    assert cmp_regressed["passed"] is False
    assert len(cmp_regressed["regressions"]) == 1
    assert cmp_regressed["regressions"][0]["metric"] == "codec_encode"
