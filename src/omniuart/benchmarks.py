"""Performance Benchmarking Suite for OmniUART (#224).

Provides reproducible benchmarks for codec throughput, frame latency, stream decoding,
session replay, and transport overhead tied to current system runtime environment.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from omniuart.core.codec import FrameCodec
from omniuart.core.models import load_protocol
from omniuart.core.transport import VirtualTransport

SAMPLE_PROTOCOL_YAML = """
schema_version: "1.0.0"
metadata: {name: BenchmarkProto, version: "1.0.0"}
serial_config: {baudrate: 115200}
framing:
  type: binary
  header: [0xAA, 0x55]
  length: {type: uint16, endian: little, includes: payload_only}
  command_id: {type: uint8}
  integrity: {algorithm: crc16_modbus}
  footer: [0x55, 0xAA]
commands:
  - name: sensor_reading
    id: 0x01
    parameters:
      - {name: temp, type: float32, endian: little}
      - {name: humidity, type: float32, endian: little}
      - {name: status, type: uint8}
    response:
      id: 0x81
      fields:
        - {name: ack, type: uint8}
"""


@dataclass
class BenchmarkMetric:
    name: str
    operations_count: int
    duration_sec: float
    ops_per_sec: float
    throughput_mb_per_sec: float
    avg_latency_us: float


class PerformanceBenchmarkSuite:
    """Benchmark runner for OmniUART codec, stream parser, replay, and transport performance."""

    def __init__(self) -> None:
        self.spec = load_protocol(SAMPLE_PROTOCOL_YAML)
        self.codec = FrameCodec(self.spec)

    def benchmark_codec_encode(self, iterations: int = 5000) -> BenchmarkMetric:
        """Measure encoding throughput and per-frame latency."""
        params = {"temp": 23.5, "humidity": 55.0, "status": 1}
        start = time.perf_counter()
        total_bytes = 0

        for _ in range(iterations):
            payload = self.codec.encode_command("sensor_reading", params)
            total_bytes += len(payload)

        duration = max(time.perf_counter() - start, 1e-9)
        ops_per_sec = iterations / duration
        mb_per_sec = (total_bytes / (1024 * 1024)) / duration
        avg_latency_us = (duration / iterations) * 1e6

        return BenchmarkMetric(
            name="codec_encode",
            operations_count=iterations,
            duration_sec=round(duration, 5),
            ops_per_sec=round(ops_per_sec, 2),
            throughput_mb_per_sec=round(mb_per_sec, 3),
            avg_latency_us=round(avg_latency_us, 2),
        )

    def benchmark_codec_decode(self, iterations: int = 5000) -> BenchmarkMetric:
        """Measure decoding throughput and per-frame latency."""
        payload = self.codec.encode_command("sensor_reading", {"temp": 23.5, "humidity": 55.0, "status": 1})
        start = time.perf_counter()
        total_bytes = 0

        for _ in range(iterations):
            decoded = self.codec.decode(payload, direction="request")
            if decoded.ok:
                total_bytes += len(payload)

        duration = max(time.perf_counter() - start, 1e-9)
        ops_per_sec = iterations / duration
        mb_per_sec = (total_bytes / (1024 * 1024)) / duration
        avg_latency_us = (duration / iterations) * 1e6

        return BenchmarkMetric(
            name="codec_decode",
            operations_count=iterations,
            duration_sec=round(duration, 5),
            ops_per_sec=round(ops_per_sec, 2),
            throughput_mb_per_sec=round(mb_per_sec, 3),
            avg_latency_us=round(avg_latency_us, 2),
        )

    def benchmark_stream_extract(self, iterations: int = 1000) -> BenchmarkMetric:
        """Measure stream frame extraction from continuous byte stream."""
        frame_bytes = self.codec.encode_command("sensor_reading", {"temp": 23.5, "humidity": 55.0, "status": 1})
        stream_buffer = frame_bytes * 10
        total_bytes = 0
        extracted_frames = 0

        start = time.perf_counter()
        for _ in range(iterations):
            frames, _ = self.codec.extract_frames(stream_buffer, direction="request")
            extracted_frames += len(frames)
            total_bytes += len(stream_buffer)

        duration = max(time.perf_counter() - start, 1e-9)
        ops_per_sec = extracted_frames / duration
        mb_per_sec = (total_bytes / (1024 * 1024)) / duration
        avg_latency_us = (duration / extracted_frames) * 1e6

        return BenchmarkMetric(
            name="stream_extract",
            operations_count=extracted_frames,
            duration_sec=round(duration, 5),
            ops_per_sec=round(ops_per_sec, 2),
            throughput_mb_per_sec=round(mb_per_sec, 3),
            avg_latency_us=round(avg_latency_us, 2),
        )

    async def benchmark_virtual_transport_roundtrip(self, iterations: int = 50) -> BenchmarkMetric:
        """Measure async virtual transport roundtrip latency."""
        transport = VirtualTransport(self.spec, latency_ms=0.0, jitter_ms=0.0)
        await transport.open()
        payload = self.codec.encode_command("sensor_reading", {"temp": 21.0, "humidity": 45.0, "status": 0})
        total_bytes = 0

        start = time.perf_counter()
        try:
            for _ in range(iterations):
                written = await transport.write(payload)
                resp = await transport.read(size=written, timeout_ms=100)
                total_bytes += written + len(resp)
        finally:
            await transport.close()

        duration = max(time.perf_counter() - start, 1e-9)
        ops_per_sec = iterations / duration
        mb_per_sec = (total_bytes / (1024 * 1024)) / duration
        avg_latency_us = (duration / iterations) * 1e6

        return BenchmarkMetric(
            name="transport_roundtrip",
            operations_count=iterations,
            duration_sec=round(duration, 5),
            ops_per_sec=round(ops_per_sec, 2),
            throughput_mb_per_sec=round(mb_per_sec, 3),
            avg_latency_us=round(avg_latency_us, 2),
        )

    def run_suite(self) -> Dict[str, Any]:
        """Run all performance benchmarks and return measured targets."""
        encode_m = self.benchmark_codec_encode()
        decode_m = self.benchmark_codec_decode()
        stream_m = self.benchmark_stream_extract()
        transport_m = asyncio.run(self.benchmark_virtual_transport_roundtrip())

        return {
            "environment": {
                "python_version": sys.version.split()[0],
                "platform": sys.platform,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "benchmarks": {
                encode_m.name: encode_m.__dict__,
                decode_m.name: decode_m.__dict__,
                stream_m.name: stream_m.__dict__,
                transport_m.name: transport_m.__dict__,
            },
        }
