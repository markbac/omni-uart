"""Hardware-in-the-Loop (HIL) Test Orchestrator for OmniUART (#222).

Provides repeatable hardware-in-the-loop orchestration for physical or virtual target devices,
including power/reset line pulsing, setup/teardown sequences, capture artifact collection, and CI exit codes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from omniuart.core.catalog import CatalogManager
from omniuart.core.recorder import SessionRecorder
from omniuart.core.runner import ScriptRunner, StepStatus
from omniuart.core.session import DeviceSession, create_transport
from omniuart.core.transport import AsyncTransport

logger = logging.getLogger(__name__)


@dataclass
class HILConfig:
    """Configuration specification for HIL test environment and target hardware."""

    port: Optional[str] = None
    baudrate: Optional[int] = None
    virtual: bool = False
    pulse_reset: bool = False
    power_pin: Optional[str] = "dtr"
    reset_pin: Optional[str] = "rts"
    power_cycle_delay_ms: float = 100.0
    setup_sequence: List[Dict[str, Any]] = field(default_factory=list)
    teardown_sequence: List[Dict[str, Any]] = field(default_factory=list)
    artifacts_dir: Optional[str] = None


@dataclass
class HILTestResult:
    """Outcome summary of a HIL test campaign execution."""

    success: bool
    total_steps: int
    passed_steps: int
    failed_steps: int
    duration_ms: float
    skipped_steps: int = 0
    artifacts: List[str] = field(default_factory=list)
    error_summary: Optional[str] = None
    runner_exit_code: int = 0

    @property
    def exit_code(self) -> int:
        return self.runner_exit_code if self.runner_exit_code != 0 else (0 if self.success else 1)


class HILOrchestrator:
    """Hardware-In-The-Loop test runner and hardware state orchestrator."""

    def __init__(self, config: HILConfig, catalog: Optional[CatalogManager] = None) -> None:
        self.config = config
        self.catalog = catalog or CatalogManager()

    async def power_cycle_device(self, transport: AsyncTransport) -> None:
        """Pulse DTR/RTS lines to perform emergency power/reset cycle on target hardware."""
        logger.info("Performing HIL hardware power/reset cycle...")
        pin_seq = []
        if self.config.power_pin:
            pin_seq.append({"pin": self.config.power_pin, "state": False, "duration_ms": self.config.power_cycle_delay_ms})
            pin_seq.append({"pin": self.config.power_pin, "state": True, "duration_ms": 50})
        if self.config.reset_pin:
            pin_seq.append({"pin": self.config.reset_pin, "state": True, "duration_ms": 50})
            pin_seq.append({"pin": self.config.reset_pin, "state": False, "duration_ms": 50})

        if pin_seq:
            await transport.pulse_pins(pin_seq)

    async def run_hil_test(
        self,
        script_query: str,
        read_only: bool = False,
    ) -> HILTestResult:
        """Orchestrate end-to-end HIL test execution against target hardware."""
        start_time = asyncio.get_running_loop().time()

        script = self.catalog.get_script(script_query)
        if script is None:
            raise ValueError(f"HIL Script '{script_query}' not found.")

        spec = self.catalog.resolve_script_protocol(script)
        if spec is None:
            raise ValueError(f"Protocol '{script.meta.protocol}' declared by script not found.")


        transport = create_transport(
            spec,
            port=self.config.port,
            baudrate=self.config.baudrate,
            virtual=self.config.virtual,
        )

        recorder = SessionRecorder(protocol_name=spec.metadata.name)
        artifacts: List[str] = []

        if not transport.is_open:
            await transport.open()

        session: Optional[DeviceSession] = None
        error_summary: Optional[str] = None
        script_result = None
        try:
            # 1. Optional reset / power cycle device (only when opted-in and not read-only)
            if self.config.pulse_reset and not read_only:
                await self.power_cycle_device(transport)

            session = DeviceSession(
                spec=spec,
                transport=transport,
                recorder=recorder,
                read_only=read_only,
            )

            # 2. Execute setup sequence if declared
            if self.config.setup_sequence:
                for setup_step in self.config.setup_sequence:
                    cmd_name = setup_step.get("command") or setup_step.get("command_name")
                    params = setup_step.get("params") or {}
                    if cmd_name:
                        ex = await session.send(cmd_name, params=params)
                        if not ex.ok:
                            raise RuntimeError(f"HIL setup step '{cmd_name}' failed: {ex.error}")

            # 3. Run Script
            runner = ScriptRunner(
                script=script,
                session=session,
            )
            script_result = await runner.run()

        except Exception as exc:
            logger.exception("HIL test execution failed: %s", exc)
            error_summary = str(exc)

        finally:
            # Execute teardown sequence in finally
            if session is not None and self.config.teardown_sequence and transport.is_open:
                try:
                    for td_step in self.config.teardown_sequence:
                        cmd_name = td_step.get("command") or td_step.get("command_name")
                        params = td_step.get("params") or {}
                        if cmd_name:
                            await session.send(cmd_name, params=params)
                except Exception as exc:
                    logger.warning("HIL teardown step failed: %s", exc)

            # Export artifacts in finally so failure captures are collected too
            if self.config.artifacts_dir:
                try:
                    art_path = Path(self.config.artifacts_dir)
                    art_path.mkdir(parents=True, exist_ok=True)

                    pcap_file = art_path / "hil_capture.pcapng"
                    recorder.export_pcapng(pcap_file)
                    artifacts.append(str(pcap_file))

                    json_file = art_path / "hil_session.json"
                    recorder.export_session_json(json_file)
                    artifacts.append(str(json_file))
                except Exception as exc:
                    logger.warning("Failed exporting HIL artifacts: %s", exc)

            if transport.is_open:
                await transport.close()

        step_results = script_result.steps if script_result else []
        passed = sum(1 for r in step_results if r.status == StepStatus.PASSED)
        skipped = sum(1 for r in step_results if r.status == StepStatus.SKIPPED)
        failed = sum(1 for r in step_results if r.status == StepStatus.FAILED)
        duration_ms = (asyncio.get_running_loop().time() - start_time) * 1000.0

        if error_summary is None:
            if failed > 0 or (script_result and not script_result.passed):
                failed_msgs = [f"Step {r.name}: {r.message}" for r in step_results if r.status == StepStatus.FAILED]
                error_summary = "; ".join(failed_msgs) if failed_msgs else "HIL test step(s) failed"
            elif not step_results:
                error_summary = "No test steps were executed"

        runner_exit = script_result.exit_code if script_result else 1
        is_success = (failed == 0 and len(step_results) > 0 and error_summary is None)

        return HILTestResult(
            success=is_success,
            total_steps=len(step_results),
            passed_steps=passed,
            failed_steps=failed,
            skipped_steps=skipped,
            duration_ms=duration_ms,
            artifacts=artifacts,
            error_summary=error_summary,
            runner_exit_code=runner_exit,
        )
