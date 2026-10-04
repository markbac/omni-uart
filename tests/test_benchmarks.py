"""Unit test for OmniUART performance benchmarking suite (#224)."""

import pytest
from omniuart.benchmarks import PerformanceBenchmarkSuite, BenchmarkMetric


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
