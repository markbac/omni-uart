"""Performance Benchmarking Suite for OmniUART (#224, #340).

Provides reproducible benchmarks for codec throughput, frame latency, stream decoding,
session replay, and transport overhead tied to current system runtime environment.
Stores and compares measured metrics against baseline targets.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
        """Measure decoding throughput and per-frame latency (#340). Fails loudly on error."""
        payload = self.codec.encode_command("sensor_reading", {"temp": 23.5, "humidity": 55.0, "status": 1})
        start = time.perf_counter()
        total_bytes = 0

        for i in range(iterations):
            decoded = self.codec.decode(payload, direction="request")
            if not decoded.ok:
                raise RuntimeError(f"Decode iteration {i} failed: {decoded.error}")
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
        """Measure stream frame extraction from continuous byte stream (#340). Fails loudly on zero frames."""
        frame_bytes = self.codec.encode_command("sensor_reading", {"temp": 23.5, "humidity": 55.0, "status": 1})
        stream_buffer = frame_bytes * 10
        total_bytes = 0
        extracted_frames = 0

        start = time.perf_counter()
        for i in range(iterations):
            frames, _ = self.codec.extract_frames(stream_buffer, direction="request")
            if not frames:
                raise RuntimeError(f"Stream extract iteration {i} extracted no frames")
            extracted_frames += len(frames)
            total_bytes += len(stream_buffer)

        if extracted_frames == 0:
            raise RuntimeError("Stream extract produced 0 frames across all iterations")

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
            for i in range(iterations):
                written = await transport.write(payload)
                resp = await transport.read(size=written, timeout_ms=100)
                if not resp:
                    raise RuntimeError(f"Transport roundtrip iteration {i} received no reply")
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


def get_default_baseline_path(env: Optional[Dict[str, Any]] = None) -> Path:
    """Get canonical baseline targets file path per environment (#340)."""
    plat = (env.get("platform") if env else sys.platform) or sys.platform
    py_ver = f"py{sys.version_info.major}{sys.version_info.minor}"
    base_dir = Path("benchmarks")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"baseline_{plat}_{py_ver}.json"


def save_baseline(results: Dict[str, Any], path: Optional[Union[str, Path]] = None) -> Path:
    """Store benchmark targets baseline file."""
    target_path = Path(path) if path else get_default_baseline_path(results.get("environment"))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return target_path


def compare_against_baseline(
    current: Dict[str, Any],
    baseline_path: Optional[Union[str, Path]] = None,
    allowed_regression_pct: float = 50.0,
) -> Dict[str, Any]:
    """Compare current results against stored baseline targets and detect performance regressions (#340)."""
    path = Path(baseline_path) if baseline_path else get_default_baseline_path(current.get("environment"))
    if not path.is_file():
        return {
            "has_baseline": False,
            "baseline_path": str(path),
            "regressions": [],
            "message": f"No existing baseline file found at {path}",
        }

    try:
        baseline_data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "has_baseline": False,
            "baseline_path": str(path),
            "regressions": [],
            "error": f"Failed reading baseline: {exc}",
        }

    regressions: List[Dict[str, Any]] = []
    comparisons: Dict[str, Any] = {}
    base_benchmarks = baseline_data.get("benchmarks", {})
    curr_benchmarks = current.get("benchmarks", {})

    for name, curr_m in curr_benchmarks.items():
        base_m = base_benchmarks.get(name)
        if not base_m or "ops_per_sec" not in base_m:
            continue
        base_ops = float(base_m["ops_per_sec"])
        curr_ops = float(curr_m.get("ops_per_sec", 0.0))
        delta_pct = ((curr_ops - base_ops) / max(base_ops, 1e-9)) * 100.0

        comparisons[name] = {
            "baseline_ops": base_ops,
            "current_ops": curr_ops,
            "delta_pct": round(delta_pct, 2),
        }

        # Check for regression greater than threshold
        if delta_pct < -allowed_regression_pct:
            regressions.append({
                "metric": name,
                "baseline_ops": base_ops,
                "current_ops": curr_ops,
                "drop_pct": round(abs(delta_pct), 2),
            })

    return {
        "has_baseline": True,
        "baseline_path": str(path),
        "comparisons": comparisons,
        "regressions": regressions,
        "passed": len(regressions) == 0,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running benchmark suite and managing baselines."""
    parser = argparse.ArgumentParser(description="OmniUART Performance Benchmarks Suite")
    parser.add_argument("--save-baseline", action="store_true", help="Save run results as baseline for this environment")
    parser.add_argument("--compare-baseline", action="store_true", help="Compare run against existing baseline targets")
    parser.add_argument("--baseline-file", type=str, default=None, help="Explicit path to baseline JSON file")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON output")
    args = parser.parse_args(argv)

    suite = PerformanceBenchmarkSuite()
    results = suite.run_suite()

    if args.save_baseline:
        out_p = save_baseline(results, args.baseline_file)
        if not args.json:
            print(f"Saved benchmark baseline targets to: {out_p}")

    comparison = None
    if args.compare_baseline:
        comparison = compare_against_baseline(results, args.baseline_file)
        if not args.json:
            if comparison.get("has_baseline"):
                print(f"\nCompared against baseline: {comparison['baseline_path']}")
                for k, v in comparison.get("comparisons", {}).items():
                    print(f"  - {k}: {v['current_ops']} ops/s (baseline: {v['baseline_ops']} ops/s, delta: {v['delta_pct']:+}%)")
                if comparison.get("regressions"):
                    print(f"\n[WARN] REGRESSIONS DETECTED ({len(comparison['regressions'])}):")
                    for reg in comparison["regressions"]:
                        print(f"  - {reg['metric']}: {reg['drop_pct']}% drop from baseline")
                else:
                    print("[OK] All benchmarks meet baseline targets.")
            else:
                print(f"Note: {comparison.get('message') or comparison.get('error')}")

    if args.json:
        output_dict = {"results": results}
        if comparison:
            output_dict["comparison"] = comparison
        print(json.dumps(output_dict, indent=2))
    elif not args.save_baseline and not args.compare_baseline:
        print("\nOmniUART Performance Benchmarks:")
        for name, m in results["benchmarks"].items():
            print(f"  - {name}: {m['ops_per_sec']} ops/s ({m['throughput_mb_per_sec']} MB/s, {m['avg_latency_us']} µs avg)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
