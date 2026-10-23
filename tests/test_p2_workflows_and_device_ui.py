"""Unit tests for Batch 1 P2 issues: Transfer Workflows & Device UI (#247, #248, #249, #250, #251, #235, #236, #237, #238, #239, #240, #318)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest
from omniuart.core.codec import DecodedFrame
from omniuart.core.device_explorer import DeviceExplorer
from omniuart.core.device_state import LiveDeviceState
from omniuart.core.device_ui import (
    DeviceIdentity,
    DeviceUIOverride,
    DeviceUISpec,
    GroupSpec,
    PanelSpec,
    TransferProtocolSpec,
    UIMode,
    WidgetSpec,
    infer_device_model_from_traffic,
)
from omniuart.core.engineer_view import EngineerProtocolView
from omniuart.core.models import (
    CommandSafety,
    CommandSpec,
    FramingConfig,
    FramingType,
    IntegritySpec,
    ProtocolMeta,
    ProtocolSpec,
    SerialConfig,
)
from omniuart.core.session import Exchange, ExchangeStatus
from omniuart.core.transfer import (
    CommitPolicy,
    ConfigurationWorkflow,
    FirmwareUpdateWorkflow,
    TransferCheckpoint,
    TransferChunk,
    TransferManager,
    TransferMetadata,
    TransferState,
)
from omniuart.dashboard_generator import generate_device_dashboard_html


# -----------------------------------------------------------------------------
# #247: Resumable Transfers & Checkpoints
# -----------------------------------------------------------------------------
def test_transfer_checkpointing_and_resume() -> None:
    """Verify transfer state checkpointing and resumption from interruption point (#247)."""
    mgr = TransferManager()
    data = b"0123456789" * 40  # 400 bytes
    meta = TransferMetadata(file_name="resumable.bin", total_size=len(data))

    ok, _ = mgr.prepare_upload(meta, data, chunk_size=100, window_size=2)
    assert ok is True
    mgr.start_transfer()

    # Transmit & ack chunk 0 and 1
    chunks = mgr.get_next_chunks()
    assert len(chunks) == 2
    mgr.acknowledge_chunk(0)
    mgr.acknowledge_chunk(1)

    # Simulate interruption & checkpoint creation
    checkpoint = mgr.create_checkpoint()
    assert checkpoint is not None
    assert checkpoint.file_name == "resumable.bin"
    assert checkpoint.acknowledged_chunks == [0, 1]
    assert checkpoint.total_chunks == 4

    # Serialise / deserialise checkpoint
    ck_dict = checkpoint.to_dict()
    restored_ck = TransferCheckpoint.from_dict(ck_dict)
    assert restored_ck.acknowledged_chunks == [0, 1]

    # Resume transfer on a fresh manager
    resume_mgr = TransferManager()
    ok, err = resume_mgr.resume_from_checkpoint(restored_ck, data, window_size=2)
    assert ok is True
    assert err is None
    assert resume_mgr.state == TransferState.TRANSFERRING
    assert resume_mgr.progress.bytes_transferred == 200

    # Next available chunk should be chunk 2 (chunk 0 and 1 already acked)
    next_chunks = resume_mgr.get_next_chunks()
    assert len(next_chunks) == 2
    assert [c.sequence_number for c in next_chunks] == [2, 3]

    resume_mgr.acknowledge_chunk(2)
    resume_mgr.acknowledge_chunk(3)
    assert resume_mgr.state == TransferState.VERIFYING
    assert resume_mgr.verify_and_commit() is True
    assert resume_mgr.state == TransferState.COMPLETED


# -----------------------------------------------------------------------------
# #248: Integrity & Commit Semantics
# -----------------------------------------------------------------------------
def test_commit_semantics_hooks_and_rollback() -> None:
    """Verify commit policies, pre/post commit hooks, and rollback on failure (#248)."""
    mgr = TransferManager()
    data = b"PAYLOAD_DATA"
    meta = TransferMetadata(file_name="payload.bin", total_size=len(data), version="1.2.0")

    mgr.prepare_upload(meta, data, chunk_size=len(data))
    mgr.start_transfer()
    mgr.acknowledge_chunk(0)
    assert mgr.state == TransferState.VERIFYING

    rollback_called = False

    def on_rollback() -> None:
        nonlocal rollback_called
        rollback_called = True

    # Pre-commit hook rejecting
    res = mgr.commit(
        policy=CommitPolicy.ATOMIC_WITH_ROLLBACK,
        pre_commit_hook=lambda: False,
        rollback_hook=on_rollback,
    )
    assert res.success is False
    assert rollback_called is True
    assert mgr.state == TransferState.FAILED

    # Successful commit
    mgr2 = TransferManager()
    mgr2.prepare_upload(meta, data, chunk_size=len(data))
    mgr2.start_transfer()
    mgr2.acknowledge_chunk(0)

    res2 = mgr2.commit(
        policy=CommitPolicy.EXPLICIT_VERIFIED,
        pre_commit_hook=lambda: True,
        post_commit_hook=lambda: True,
    )
    assert res2.success is True
    assert res2.checksum_verified is True
    assert res2.committed_version == "1.2.0"
    assert mgr2.state == TransferState.COMPLETED


# -----------------------------------------------------------------------------
# #249: Firmware Update Workflow
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_firmware_update_workflow() -> None:
    """Verify firmware validation, chunked upload, reboot, and post-update version check (#249)."""
    workflow = FirmwareUpdateWorkflow()
    image = b"OMNI_FW_IMAGE_V3.0.0" * 10  # 200 bytes

    reboot_occurred = False
    active_version = "1.0.0"

    async def mock_channel(chunk: TransferChunk) -> bool:
        await asyncio.sleep(0.001)
        return True

    async def mock_reboot() -> None:
        nonlocal reboot_occurred, active_version
        await asyncio.sleep(0.001)
        reboot_occurred = True
        active_version = "3.0.0"

    async def query_version() -> str:
        return active_version

    ok, err = await workflow.execute_update(
        firmware_bytes=image,
        file_name="fw_v3.bin",
        version="3.0.0",
        chunk_sender=mock_channel,
        reboot_fn=mock_reboot,
        verify_version_fn=query_version,
        chunk_size=50,
    )

    assert ok is True
    assert err is None
    assert reboot_occurred is True
    assert workflow.manager.state == TransferState.COMPLETED


# -----------------------------------------------------------------------------
# #250: Configuration Workflow
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_configuration_workflow() -> None:
    """Verify configuration validation, diff computation, and application (#250)."""
    workflow = ConfigurationWorkflow()

    # Format validation
    valid_json = b'{"baudrate": 115200, "parity": "none"}'
    ok, parsed, err = workflow.validate_configuration(valid_json)
    assert ok is True
    assert parsed == {"baudrate": 115200, "parity": "none"}

    # Diff calculation
    current = {"baudrate": 9600, "parity": "none", "timeout": 5}
    new = {"baudrate": 115200, "parity": "none", "retries": 3}
    diff = workflow.compute_diff(current, new)
    assert diff["has_changes"] is True
    assert "retries" in diff["added"]
    assert "timeout" in diff["removed"]
    assert diff["modified"]["baudrate"]["old"] == 9600
    assert diff["modified"]["baudrate"]["new"] == 115200

    applied_config = {}

    async def mock_apply(cfg: Dict[str, Any]) -> None:
        nonlocal applied_config
        applied_config = cfg

    async def mock_sender(c: TransferChunk) -> bool:
        return True

    ok, err = await workflow.import_configuration(
        config_bytes=valid_json,
        file_name="node_config.json",
        chunk_sender=mock_sender,
        apply_fn=mock_apply,
        apply_immediately=True,
    )
    assert ok is True
    assert applied_config == {"baudrate": 115200, "parity": "none"}


# -----------------------------------------------------------------------------
# #251, #235, #237: Device UI Schema Extensions, Modes & Overrides
# -----------------------------------------------------------------------------
def test_device_ui_modes_and_overrides() -> None:
    """Verify UI modes, transfer protocol definitions, and declarative overrides (#251, #235, #237)."""
    spec = DeviceUISpec(
        identity=DeviceIdentity(name="BaseDevice", model="BD-1"),
        protocol_ref="BaseProtocol",
        transfer_protocol=TransferProtocolSpec(
            start_command="start_xfer",
            chunk_command="send_chunk",
            ack_command="ack_chunk",
        ),
        panels=[
            PanelSpec(
                name="p1",
                title="P1",
                groups=[
                    GroupSpec(
                        name="g1",
                        title="G1",
                        widgets=[
                            WidgetSpec(widget_type="button", field_ref="cmd1", label="Cmd 1"),
                            WidgetSpec(widget_type="slider", field_ref="temp", label="Temperature", min=0, max=100),
                        ],
                    )
                ],
            )
        ],
    )

    assert spec.transfer_protocol is not None
    assert spec.transfer_protocol.start_command == "start_xfer"
    assert UIMode.OPERATOR in spec.supported_modes
    assert UIMode.ENGINEER in spec.supported_modes
    assert UIMode.DEVELOPER in spec.supported_modes

    # Apply override: rename device, hide temp widget, override cmd1 label
    override = DeviceUIOverride(
        device_name="CustomizedDevice",
        hidden_widgets=["temp"],
        widget_overrides={"cmd1": {"label": "Run Quick Command"}},
    )

    customized = override.apply_overrides(spec)
    assert customized.identity.name == "CustomizedDevice"
    widgets = customized.panels[0].groups[0].widgets
    assert len(widgets) == 1
    assert widgets[0].field_ref == "cmd1"
    assert widgets[0].label == "Run Quick Command"


# -----------------------------------------------------------------------------
# #238: Traffic to Device Model Inference
# -----------------------------------------------------------------------------
def test_infer_device_model_from_traffic() -> None:
    """Verify inferring a device model and UI layout from decoded traffic frames (#238)."""
    frames = [
        DecodedFrame(raw=b"\x01", kind="command", name="set_speed", fields={"speed": 120}),
        DecodedFrame(raw=b"\x02", kind="telemetry", name="sensor_status", fields={"voltage": 12.4, "online": True}),
    ]

    ui_spec = infer_device_model_from_traffic(frames, protocol_name="InferredMotor")
    assert ui_spec.identity.name == "InferredMotor"
    assert len(ui_spec.panels) >= 1
    groups = ui_spec.panels[0].groups
    group_names = [g.name for g in groups]
    assert "controls" in group_names
    assert "telemetry" in group_names


# -----------------------------------------------------------------------------
# #239 & #240: Multi-Device Management & Comparison
# -----------------------------------------------------------------------------
def test_multi_device_management_and_comparison() -> None:
    """Verify DeviceExplorer multi-device tracking and comparison views (#239, #240)."""
    explorer = DeviceExplorer()

    proto1 = ProtocolSpec(
        metadata=ProtocolMeta(name="SensorA", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.BINARY),
        commands=[CommandSpec(name="ping", id=1), CommandSpec(name="read_temp", id=2)],
    )
    proto2 = ProtocolSpec(
        metadata=ProtocolMeta(name="SensorB", version="2.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.BINARY),
        commands=[CommandSpec(name="ping", id=1), CommandSpec(name="read_humidity", id=3)],
    )

    dev_a = explorer.register_active_device("dev_1", proto1, port_or_address="COM3")
    dev_b = explorer.register_active_device("dev_2", proto2, port_or_address="COM4")
    assert dev_b.id == "dev_2"

    assert len(explorer.list_active_devices()) == 2
    assert explorer.get_active_device("dev_1") == dev_a

    # Compare devices
    cmp_res = explorer.compare_devices("dev_1", "dev_2")
    assert cmp_res["commands_comparison"]["common"] == ["ping"]
    assert cmp_res["commands_comparison"]["unique_a"] == ["read_temp"]
    assert cmp_res["commands_comparison"]["unique_b"] == ["read_humidity"]

    # Remove device
    assert explorer.remove_active_device("dev_1") is True
    assert len(explorer.list_active_devices()) == 1


# -----------------------------------------------------------------------------
# #318: Device UI Bugs (Status, State Model, Engineer View CRC)
# -----------------------------------------------------------------------------
def test_device_state_monotonic_staleness_and_connection_loss() -> None:
    """Verify LiveDeviceState uses monotonic clock, namespacing, and marks offline immediately (#318)."""
    state = LiveDeviceState(device_id="node_1", default_stale_s=10.0)

    # Namespacing: two commands with same field name 'channel'
    v1 = state.update_field("channel", 1, namespace="rx_config")
    v2 = state.update_field("channel", 7, namespace="tx_config")

    assert state.get_field("channel", namespace="rx_config") is not None
    assert state.get_field("channel", namespace="rx_config").value == 1  # type: ignore[union-attr]
    assert state.get_field("channel", namespace="tx_config").value == 7  # type: ignore[union-attr]

    # Verify connection online and quality
    assert state.connection_online is True
    assert v1.quality == "good"
    assert v1.is_stale is False

    # Simulate connection loss
    state.mark_connection_lost()
    assert state.connection_online is False
    # Immediately marks quality as offline and stale (#318)
    assert v1.quality == "offline"
    assert v1.is_stale is True
    assert v2.quality == "offline"


def test_engineer_view_crc_valid_not_true_on_no_response() -> None:
    """Verify EngineerProtocolView reports CRC valid as None when no response arrived (#318)."""
    spec = ProtocolSpec(
        metadata=ProtocolMeta(name="Node", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(
            type=FramingType.BINARY,
            integrity=IntegritySpec(algorithm="crc16_modbus"),
        ),
        commands=[CommandSpec(name="ping", id=1)],
    )

    view = EngineerProtocolView(spec)

    # Exchange with TIMEOUT (no response received)
    timeout_exchange = Exchange(
        command="ping",
        request=b"\x01\x00",
        status=ExchangeStatus.TIMEOUT,
        response_bytes=b"",
        response=None,
    )

    detail = view.inspect_exchange(timeout_exchange)
    # Must NOT report crc_valid = True when no response was received (#318)
    assert detail.crc_valid is None

    html_summary = view.render_engineer_html_summary(detail.exchange_id)
    assert "N/A" in html_summary
    assert "VALID" not in html_summary


def test_dashboard_renders_dynamic_status_and_mode_tabs() -> None:
    """Verify dashboard renders dynamic connection status, baudrate, and Operator/Engineer/Dev tabs (#318, #235)."""
    spec = ProtocolSpec(
        metadata=ProtocolMeta(name="MyBaudDevice", version="1.0.0"),
        serial_config=SerialConfig(baudrate=460800),
        framing=FramingConfig(type=FramingType.DELIMITED),
        commands=[CommandSpec(name="status", id=1, safety=CommandSafety.READ_ONLY)],
    )

    # Disconnected state
    html_disc = generate_device_dashboard_html(spec, is_connected=False)
    assert "DISCONNECTED (460800 bps)" in html_disc
    assert "status-disconnected" in html_disc

    # Connected state
    html_conn = generate_device_dashboard_html(spec, is_connected=True)
    assert "CONNECTED (460800 bps)" in html_conn
    assert "status-connected" in html_conn

    # Check mode navigation tabs (#235)
    assert 'data-mode="operator"' in html_conn
    assert 'data-mode="engineer"' in html_conn
    assert 'data-mode="developer"' in html_conn
    assert 'id="operatorView"' in html_conn
    assert 'id="engineerView"' in html_conn
    assert 'id="developerView"' in html_conn
