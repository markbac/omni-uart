"""Unit tests for telemetry metrics collector and performance profiling (#223)."""

from omniuart.core.telemetry import MetricsCollector, PerformanceMetrics


def test_metrics_collector_initialization():
    collector = MetricsCollector()
    snapshot = collector.snapshot()

    assert snapshot["tx_bytes"] == 0
    assert snapshot["rx_bytes"] == 0
    assert snapshot["decoded_frames"] == 0
    assert snapshot["timeouts"] == 0
    assert snapshot["retries"] == 0
    assert snapshot["errors"] == 0
    assert "resource_limits" in snapshot


def test_metrics_collector_records_events():
    collector = MetricsCollector()

    collector.record_tx(128)
    collector.record_rx(64)
    collector.record_decode(2.5)
    collector.record_decode(1.5)
    collector.record_transport_latency(10.0)
    collector.record_timeout()
    collector.record_retry()
    collector.record_error()
    collector.update_queue_depth(5)

    snapshot = collector.snapshot()

    assert snapshot["tx_bytes"] == 128
    assert snapshot["rx_bytes"] == 64
    assert snapshot["decoded_frames"] == 2
    assert snapshot["decode_latency_ms"]["avg"] == 2.0
    assert snapshot["decode_latency_ms"]["min"] == 1.5
    assert snapshot["decode_latency_ms"]["max"] == 2.5
    assert snapshot["timeouts"] == 1
    assert snapshot["retries"] == 1
    assert snapshot["errors"] == 1
    assert snapshot["queue_depth"] == 5
