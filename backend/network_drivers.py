# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/network_drivers.py — Device discovery and topology builder

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

import models
import schemas

logger = logging.getLogger(__name__)

# ── Demo devices inserted when the DB is empty ────────────────────────────────
DEMO_DEVICES = [
    schemas.DeviceCreate(
        hostname="Switch-Core-01",
        ip_address="192.168.1.1",
        device_type="cisco_ios",
        vendor="Cisco",
        model="Catalyst 9300",
        status="up",
        topology_x=250.0,
        topology_y=150.0,
    ),
    schemas.DeviceCreate(
        hostname="Router-WAN-01",
        ip_address="192.168.1.254",
        device_type="cisco_ios",
        vendor="Cisco",
        model="ASR 1001-X",
        status="up",
        topology_x=500.0,
        topology_y=150.0,
    ),
    schemas.DeviceCreate(
        hostname="Switch-Access-02",
        ip_address="192.168.1.2",
        device_type="cisco_ios",
        vendor="Cisco",
        model="Catalyst 2960",
        status="warning",
        topology_x=375.0,
        topology_y=350.0,
    ),
]


def discover_devices(
    cidr: str,
    username: str,
    password: str,
    device_type: str = "cisco_ios",
) -> List[schemas.DeviceCreate]:
    """
    Attempt LLDP/CDP discovery via Netmiko.  Falls back to demo devices if
    Netmiko or nmap are unavailable or if no hosts respond.
    """
    discovered: List[schemas.DeviceCreate] = []

    try:
        import nmap  # type: ignore

        nm = nmap.PortScanner()
        nm.scan(hosts=cidr, arguments="-sn --host-timeout 5s")
        live_hosts = nm.all_hosts()
    except Exception as exc:
        logger.warning("nmap scan failed (%s); using demo fallback.", exc)
        return DEMO_DEVICES

    for ip in live_hosts:
        try:
            from netmiko import ConnectHandler  # type: ignore

            connection = ConnectHandler(
                device_type=device_type,
                host=ip,
                username=username,
                password=password,
                timeout=10,
            )

            # Try LLDP first, then CDP
            try:
                output = connection.send_command("show lldp neighbors detail")
            except Exception:
                output = connection.send_command("show cdp neighbors detail")

            hostname = _parse_hostname(output) or ip
            vendor = _parse_vendor(output)
            connection.disconnect()

            discovered.append(
                schemas.DeviceCreate(
                    hostname=hostname,
                    ip_address=ip,
                    device_type=device_type,
                    vendor=vendor,
                    status="up",
                )
            )
        except Exception as exc:
            logger.debug("Could not connect to %s: %s", ip, exc)

    return discovered if discovered else DEMO_DEVICES


def _parse_hostname(output: str) -> Optional[str]:
    for line in output.splitlines():
        lower = line.lower()
        if "system name" in lower or "device id" in lower:
            parts = line.split(":")
            if len(parts) > 1:
                return parts[1].strip()
    return None


def _parse_vendor(output: str) -> Optional[str]:
    for line in output.splitlines():
        lower = line.lower()
        if "system description" in lower or "platform" in lower:
            if "cisco" in lower:
                return "Cisco"
            if "juniper" in lower:
                return "Juniper"
            if "arista" in lower:
                return "Arista"
            if "huawei" in lower:
                return "Huawei"
    return "Unknown"


def get_topology(db: Session) -> schemas.TopologyResponse:
    """Build a React Flow–compatible topology from the devices in the database."""
    devices = db.query(models.Device).all()
    links = db.query(models.Topology).all()

    nodes = [
        schemas.TopologyNode(
            id=str(device.id),
            data={
                "label": device.hostname,
                "ip": device.ip_address,
                "status": device.status,
                "vendor": device.vendor,
                "model": device.model,
                "device_type": device.device_type,
            },
            position={"x": device.topology_x, "y": device.topology_y},
            type="default",
        )
        for device in devices
    ]

    edges = [
        schemas.TopologyEdge(
            id=f"e{link.id}",
            source=str(link.source_device_id),
            target=str(link.target_device_id),
            label=link.link_type,
        )
        for link in links
    ]

    return schemas.TopologyResponse(nodes=nodes, edges=edges)


def ensure_demo_devices(db: Session) -> None:
    """Insert demo devices, alerts and topology links if the DB is empty."""
    if db.query(models.Device).count() > 0:
        return

    device_objs = []
    for d in DEMO_DEVICES:
        obj = models.Device(**d.model_dump())
        db.add(obj)
        db.flush()
        device_objs.append(obj)

    db.commit()
    for obj in device_objs:
        db.refresh(obj)

    # Demo alerts
    switch_access = next((d for d in device_objs if d.hostname == "Switch-Access-02"), None)
    router_wan = next((d for d in device_objs if d.hostname == "Router-WAN-01"), None)
    switch_core = next((d for d in device_objs if d.hostname == "Switch-Core-01"), None)

    if switch_access:
        db.add(
            models.Alert(
                device_id=switch_access.id,
                severity="warning",
                message="High CPU utilisation detected (>85%)",
                is_resolved=False,
            )
        )
    if router_wan:
        db.add(
            models.Alert(
                device_id=router_wan.id,
                severity="info",
                message="Scheduled maintenance window tomorrow 02:00–04:00 UTC",
                is_resolved=False,
            )
        )

    # Demo topology links (Switch-Core ↔ Router-WAN, Switch-Core ↔ Switch-Access)
    if switch_core and router_wan:
        db.add(
            models.Topology(
                source_device_id=switch_core.id,
                target_device_id=router_wan.id,
                link_type="uplink",
                bandwidth="10G",
            )
        )
    if switch_core and switch_access:
        db.add(
            models.Topology(
                source_device_id=switch_core.id,
                target_device_id=switch_access.id,
                link_type="access",
                bandwidth="1G",
            )
        )

    db.commit()

