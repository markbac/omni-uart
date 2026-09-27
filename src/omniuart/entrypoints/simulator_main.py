"""Virtual MCU Simulator Binary Entry Point for OmniUART."""

from __future__ import annotations

import asyncio
import logging
import sys
from omniuart.core.catalog import CatalogManager
from omniuart.core.simulator import ATModemSimulator, IoTSensorSimulator, ModbusRtuSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main_async() -> int:
    catalog = CatalogManager()
    summary = catalog.catalog_summary()
    protocols = summary.get("protocols", [])

    print("========================================================")
    print("  ⚡ OmniUART Virtual MCU Simulator Running")
    print(f"  Loaded Protocol Schemas: {len(protocols)}")
    print("  Emulated Virtual Devices: AT Modem, IoT Sensor, Modbus RTU")
    print("========================================================")
    print("Press Ctrl+C to terminate simulator...")

    # Instantiate simulators
    at_spec = catalog.get_protocol("at-commands-uart-interface.yaml")
    iot_spec = catalog.get_protocol("binary_sensor_node.yaml")
    modbus_spec = catalog.get_protocol("modbus_rtu_device.yaml")

    sims = []
    if at_spec:
        sims.append(ATModemSimulator(spec=at_spec))
    if iot_spec:
        sims.append(IoTSensorSimulator(spec=iot_spec, telemetry_interval_sec=1.0))
    if modbus_spec:
        sims.append(ModbusRtuSimulator(spec=modbus_spec))

    for sim in sims:
        await sim.start()

    try:
        while True:
            await asyncio.sleep(1.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutting down virtual device simulators...")
        for sim in sims:
            await sim.stop()

    return 0


def run() -> int:
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(run())
