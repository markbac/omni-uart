"""Hardware-in-the-Loop (HIL) Test Orchestrator for OmniUART (#222).

Provides repeatable hardware-in-the-loop orchestration for physical or virtual target devices,
including power/reset line pulsing, setup/teardown sequences, capture artifact collection, and CI exit codes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from omniuart.core.catalog import CatalogManager
from omniuart.core.models import ProtocolSpec, load_script
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
    artifacts: List[str] = field(default_factory=list)
    error_summary: Optional[str] = None

    @property
    def exit_code(self) -> int:
        return 0 if self.success else 1


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

        try:
            # 1. Reset / power cycle device
            await self.power_cycle_device(transport)

            # 2. Run Script
            session = DeviceSession(
                spec=spec,
                transport=transport,
                recorder=recorder,
                read_only=read_only,
            )
            runner = ScriptRunner(
                script=script,
                session=session,
            )
            script_result = await runner.run()
            step_results = script_result.steps

            # 3. Export artifacts if directory configured
            if self.config.artifacts_dir:
                art_path = Path(self.config.artifacts_dir)
                art_path.mkdir(parents=True, exist_ok=True)

                pcap_file = art_path / "hil_capture.pcapng"
                recorder.export_pcapng(pcap_file)
                artifacts.append(str(pcap_file))

                json_file = art_path / "hil_session.json"
                recorder.export_session_json(json_file)
                artifacts.append(str(json_file))

            passed = sum(1 for r in step_results if r.status == StepStatus.PASSED)
            failed = len(step_results) - passed
            duration_ms = (asyncio.get_running_loop().time() - start_time) * 1000.0

            return HILTestResult(
                success=(failed == 0 and len(step_results) > 0),
                total_steps=len(step_results),
                passed_steps=passed,
                failed_steps=failed,
                duration_ms=duration_ms,
                artifacts=artifacts,
            )

        finally:
            if transport.is_open:
                await transport.close()
