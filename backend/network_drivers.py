# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
"""
Netmiko-based network auto-discovery engine + health metrics collectors.

Network discovery supports: Cisco IOS, Cisco NX-OS, Arista EOS, Juniper JunOS,
    Fortinet FortiOS, Palo Alto PAN-OS, Checkpoint Gaia.
Performs BFS topology crawl using LLDP / CDP neighbor tables.

Health metrics:
  NetworkHealthCollector — SSH into network devices to fetch interface CRC /
      error counters and firmware / serial details.
  ServerHealthCollector  — Polls BMC/OOB management interfaces:
      - Redfish REST API for Dell iDRAC and HP iLO
      - SNMP v2c for IBM / Lenovo IMM
"""

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException

logger = logging.getLogger(__name__)


@dataclass
class NeighborInfo:
    local_port: str
    remote_hostname: str
    remote_ip: str
    remote_port: str
    platform: str = "unknown"
    capability: str = "unknown"


@dataclass
class DeviceInventory:
    hostname: str
    ip_address: str
    device_type: str
    vendor: str
    os_version: str
    serial: str = "unknown"
    platform: str = "unknown"


@dataclass
class InterfaceStats:
    name: str
    input_errors: int = 0
    output_errors: int = 0
    crc_errors: int = 0
    resets: int = 0


@dataclass
class DeviceHealthMetrics:
    """Aggregated health metrics for a single device (network or server)."""

    ip_address: str
    hostname: str = "unknown"
    vendor: str = "unknown"
    firmware_version: str = "unknown"
    serial_number: str = "unknown"
    platform: str = "unknown"
    # Network-specific
    interface_stats: List[InterfaceStats] = field(default_factory=list)
    # Server-specific
    overall_health: str = "unknown"   # "OK", "Warning", "Critical", "unknown"
    cpu_health: str = "unknown"
    memory_health: str = "unknown"
    storage_health: str = "unknown"   # RAID / disk array status
    psu_health: str = "unknown"       # Redundant power supply status
    fan_health: str = "unknown"
    temperature_health: str = "unknown"
    raw_alerts: List[str] = field(default_factory=list)


# ─── Regex patterns ──────────────────────────────────────────────────────────

_LLDP_PATTERN = re.compile(
    r"Local Intf:\s*(?P<local_port>\S+).*?"
    r"Port ID\s*:\s*(?P<remote_port>\S+).*?"
    r"System Name:\s*(?P<hostname>\S+).*?"
    r"Management Address(?:es)?:\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3}).*?"
    r"System Capabilities:\s*(?P<capability>[^\n]+)",
    re.DOTALL,
)

_CDP_BLOCK_PATTERN = re.compile(
    r"-{3,}\n"
    r"Device ID:\s*(?P<hostname>\S+)\s*\n"
    r".*?IP [Aa]ddress(?:es)?:\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s*\n"
    r".*?Platform:\s*(?P<platform>[^\n,]+).*?\n"
    r".*?Interface:\s*(?P<local_port>\S+),\s*Port ID.*?:\s*(?P<remote_port>\S+)",
    re.DOTALL,
)

# Fortinet `get system lldp neighbors-detail` block pattern
_FORTI_LLDP_PATTERN = re.compile(
    r"Interface\s*:\s*(?P<local_port>\S+).*?"
    r"Port ID\s*:\s*(?P<remote_port>\S+).*?"
    r"System Name\s*:\s*(?P<hostname>\S+).*?"
    r"Management Address\s*:\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
    re.DOTALL,
)

# Palo Alto `show lldp neighbors` tabular line pattern
# Columns: local-port  remote-chassis-id  remote-port-id  remote-port-desc  remote-system-name  mgmt-addr
_PANOS_LLDP_LINE = re.compile(
    r"^(?P<local_port>\S+)\s+\S+\s+(?P<remote_port>\S+)\s+\S+\s+(?P<hostname>\S+)\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
)

# Checkpoint Gaia `show lldp neighbors` uses LLDP standard format; reuse _LLDP_PATTERN

_VERSION_PATTERNS: Dict[str, re.Pattern] = {
    "cisco_ios": re.compile(
        r"Cisco IOS.*?Version\s+(?P<version>\S+).*?hostname\s+(?P<hostname>\S+)",
        re.DOTALL,
    ),
    "cisco_nxos": re.compile(
        r"NXOS:\s*version\s+(?P<version>\S+).*?Device name:\s*(?P<hostname>\S+)",
        re.DOTALL,
    ),
    "arista_eos": re.compile(
        r"Arista\s+(?P<platform>\S+).*?EOS version:\s*(?P<version>\S+)",
        re.DOTALL,
    ),
    "juniper_junos": re.compile(
        r"Junos:\s*(?P<version>\S+).*?Hostname:\s*(?P<hostname>\S+)",
        re.DOTALL,
    ),
    "fortinet": re.compile(
        r"Version:\s*FortiGate-\S+\s+(?P<version>\S+).*?Hostname:\s*(?P<hostname>\S+)",
        re.DOTALL,
    ),
    "paloalto_panos": re.compile(
        r"hostname:\s*(?P<hostname>\S+).*?sw-version:\s*(?P<version>\S+)",
        re.DOTALL,
    ),
    "checkpoint_gaia": re.compile(
        r"Product version\s+(?P<version>\S+).*?Hostname:\s*(?P<hostname>\S+)",
        re.DOTALL,
    ),
}

# Interface error block from `show interfaces` (Cisco IOS / NX-OS / Arista)
_INTF_ERROR_PATTERN = re.compile(
    r"^(?P<intf>\S+) is .+?\n"
    r"(?:.*?\n)*?"
    r"\s+(?P<input_errors>\d+) input errors.*?\n"
    r".*?(?P<crc>\d+) CRC.*?\n",
    re.MULTILINE,
)

# Juniper `show interfaces extensive` CRC pattern
_JUNOS_CRC_PATTERN = re.compile(
    r"Physical interface:\s*(?P<intf>\S+).*?"
    r"Input errors:\s*\n.*?CRC\s+errors:\s*(?P<crc>\d+)",
    re.DOTALL,
)

# Fortinet `diagnose netlink interface list` packet error line
_FORTI_IF_PATTERN = re.compile(
    r"^if=(?P<intf>\S+)\s.*?rxerr=(?P<rxerr>\d+)\s.*?txerr=(?P<txerr>\d+)",
    re.MULTILINE,
)


class NetworkDiscoveryEngine:
    """SSH-based LLDP/CDP topology discovery engine."""

    def __init__(self) -> None:
        self._seen_ips: set = set()

    # ─── Public interface ─────────────────────────────────────────────────

    def discover_neighbors(
        self, device_ip: str, credentials: Dict[str, str]
    ) -> List[NeighborInfo]:
        """SSH into *device_ip* and parse LLDP/CDP neighbor output."""
        conn_params = self._build_conn_params(device_ip, credentials)
        try:
            with ConnectHandler(**conn_params) as net_connect:
                return self._parse_neighbors(net_connect, credentials.get("device_type", "cisco_ios"))
        except (NetmikoAuthenticationException, NetmikoTimeoutException) as exc:
            logger.warning("Discovery failed for %s: %s", device_ip, exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error discovering %s: %s", device_ip, exc)
            return []

    def get_device_inventory(
        self, device_ip: str, credentials: Dict[str, str]
    ) -> Optional[DeviceInventory]:
        """Pull version/serial/platform info from *device_ip*."""
        conn_params = self._build_conn_params(device_ip, credentials)
        device_type = credentials.get("device_type", "cisco_ios")
        try:
            with ConnectHandler(**conn_params) as net_connect:
                return self._parse_inventory(net_connect, device_ip, device_type)
        except (NetmikoAuthenticationException, NetmikoTimeoutException) as exc:
            logger.warning("Inventory failed for %s: %s", device_ip, exc)
            return None
        except Exception as exc:
            logger.error("Inventory error for %s: %s", device_ip, exc)
            return None

    def build_topology_graph(
        self, seed_devices: List[str], credentials: Dict[str, str]
    ) -> Dict[str, Any]:
        """BFS crawl starting from *seed_devices*.

        Returns a dict with ``nodes`` (list of DeviceInventory dicts) and
        ``links`` (list of neighbor relationship dicts).
        """
        queue: deque = deque(seed_devices)
        self._seen_ips = set(seed_devices)
        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, str]] = []

        while queue:
            ip = queue.popleft()
            inventory = self.get_device_inventory(ip, credentials)
            if inventory:
                nodes.append(vars(inventory))
            neighbors = self.discover_neighbors(ip, credentials)
            for neighbor in neighbors:
                if neighbor.remote_ip and neighbor.remote_ip not in self._seen_ips:
                    self._seen_ips.add(neighbor.remote_ip)
                    queue.append(neighbor.remote_ip)
                links.append(
                    {
                        "source_ip": ip,
                        "target_ip": neighbor.remote_ip,
                        "source_port": neighbor.local_port,
                        "target_port": neighbor.remote_port,
                    }
                )

        return {"nodes": nodes, "links": links}

    # ─── Private helpers ─────────────────────────────────────────────────

    @staticmethod
    def _build_conn_params(ip: str, credentials: Dict[str, str]) -> Dict[str, Any]:
        return {
            "device_type": credentials.get("device_type", "cisco_ios"),
            "host": ip,
            "username": credentials.get("username", ""),
            "password": credentials.get("password", ""),
            "secret": credentials.get("secret", ""),
            "timeout": int(credentials.get("timeout", 15)),
        }

    @staticmethod
    def _parse_neighbors(
        net_connect: Any, device_type: str
    ) -> List[NeighborInfo]:
        neighbors: List[NeighborInfo] = []

        if device_type in ("cisco_ios", "cisco_nxos"):
            # Try LLDP first, fall back to CDP
            try:
                lldp_out = net_connect.send_command("show lldp neighbors detail")
                for m in _LLDP_PATTERN.finditer(lldp_out):
                    neighbors.append(
                        NeighborInfo(
                            local_port=m.group("local_port"),
                            remote_hostname=m.group("hostname"),
                            remote_ip=m.group("ip"),
                            remote_port=m.group("remote_port"),
                            capability=m.group("capability").strip(),
                        )
                    )
            except Exception:
                pass

            if not neighbors:
                try:
                    cdp_out = net_connect.send_command("show cdp neighbors detail")
                    for m in _CDP_BLOCK_PATTERN.finditer(cdp_out):
                        neighbors.append(
                            NeighborInfo(
                                local_port=m.group("local_port"),
                                remote_hostname=m.group("hostname"),
                                remote_ip=m.group("ip"),
                                remote_port=m.group("remote_port"),
                                platform=m.group("platform").strip(),
                            )
                        )
                except Exception:
                    pass

        elif device_type == "arista_eos":
            try:
                lldp_out = net_connect.send_command("show lldp neighbors detail")
                for m in _LLDP_PATTERN.finditer(lldp_out):
                    neighbors.append(
                        NeighborInfo(
                            local_port=m.group("local_port"),
                            remote_hostname=m.group("hostname"),
                            remote_ip=m.group("ip"),
                            remote_port=m.group("remote_port"),
                        )
                    )
            except Exception:
                pass

        elif device_type == "juniper_junos":
            try:
                lldp_out = net_connect.send_command("show lldp neighbors")
                for line in lldp_out.splitlines():
                    parts = line.split()
                    if len(parts) >= 4:
                        neighbors.append(
                            NeighborInfo(
                                local_port=parts[0],
                                remote_hostname=parts[2],
                                remote_ip="",
                                remote_port=parts[3],
                            )
                        )
            except Exception:
                pass

        elif device_type == "fortinet":
            try:
                lldp_out = net_connect.send_command("get system lldp neighbors-detail")
                for m in _FORTI_LLDP_PATTERN.finditer(lldp_out):
                    neighbors.append(
                        NeighborInfo(
                            local_port=m.group("local_port"),
                            remote_hostname=m.group("hostname"),
                            remote_ip=m.group("ip"),
                            remote_port=m.group("remote_port"),
                        )
                    )
            except Exception:
                pass

        elif device_type == "paloalto_panos":
            try:
                lldp_out = net_connect.send_command("show lldp neighbors")
                for line in lldp_out.splitlines():
                    m = _PANOS_LLDP_LINE.match(line.strip())
                    if m:
                        neighbors.append(
                            NeighborInfo(
                                local_port=m.group("local_port"),
                                remote_hostname=m.group("hostname"),
                                remote_ip=m.group("ip"),
                                remote_port=m.group("remote_port"),
                            )
                        )
            except Exception:
                pass

        elif device_type == "checkpoint_gaia":
            try:
                lldp_out = net_connect.send_command("show lldp neighbors detail")
                for m in _LLDP_PATTERN.finditer(lldp_out):
                    neighbors.append(
                        NeighborInfo(
                            local_port=m.group("local_port"),
                            remote_hostname=m.group("hostname"),
                            remote_ip=m.group("ip"),
                            remote_port=m.group("remote_port"),
                            capability=m.group("capability").strip(),
                        )
                    )
            except Exception:
                pass

        return neighbors

    @staticmethod
    def _parse_inventory(
        net_connect: Any, ip: str, device_type: str
    ) -> DeviceInventory:
        if device_type == "fortinet":
            show_ver_cmd = "get system status"
        elif device_type == "paloalto_panos":
            show_ver_cmd = "show system info"
        elif device_type == "checkpoint_gaia":
            show_ver_cmd = "show version all"
        else:
            show_ver_cmd = "show version"

        output = ""
        try:
            output = net_connect.send_command(show_ver_cmd)
        except Exception:
            pass

        hostname = ip
        version = "unknown"
        vendor = "unknown"
        platform = "unknown"
        serial = "unknown"

        if device_type in ("cisco_ios", "cisco_nxos"):
            vendor = "Cisco"
            m = re.search(r"hostname\s+(\S+)", output, re.IGNORECASE)
            if m:
                hostname = m.group(1)
            m = re.search(r"[Vv]ersion\s+(\S+)", output)
            if m:
                version = m.group(1).rstrip(",")
            m = re.search(r"[Ss]erial\s+[Nn]umber\s*:\s*(\S+)", output)
            if m:
                serial = m.group(1)
            m = re.search(r"[Cc]isco\s+(\S+)\s+processor", output)
            if m:
                platform = m.group(1)

        elif device_type == "arista_eos":
            vendor = "Arista"
            m = re.search(r"Arista\s+(\S+)", output)
            if m:
                platform = m.group(1)
            m = re.search(r"EOS version:\s*(\S+)", output)
            if m:
                version = m.group(1)

        elif device_type == "juniper_junos":
            vendor = "Juniper"
            m = re.search(r"Hostname:\s*(\S+)", output)
            if m:
                hostname = m.group(1)
            m = re.search(r"Junos:\s*(\S+)", output)
            if m:
                version = m.group(1)

        elif device_type == "fortinet":
            vendor = "Fortinet"
            # `get system status` output: "Version: FortiGate-100E v6.4.5,build1828,210318 (GA)"
            m = re.search(r"Version:\s*(FortiGate-\S+)\s+(\S+)", output)
            if m:
                platform = m.group(1)
                # Strip optional build/date suffix (e.g. "v6.4.5,build1828" → "v6.4.5")
                raw_ver = m.group(2)
                version = raw_ver.split(",")[0] if "," in raw_ver else raw_ver
            m = re.search(r"Hostname:\s*(\S+)", output)
            if m:
                hostname = m.group(1)
            m = re.search(r"Serial-Number:\s*(\S+)", output)
            if m:
                serial = m.group(1)

        elif device_type == "paloalto_panos":
            vendor = "Palo Alto"
            # `show system info` output
            m = re.search(r"^hostname:\s*(\S+)", output, re.MULTILINE)
            if m:
                hostname = m.group(1)
            m = re.search(r"^sw-version:\s*(\S+)", output, re.MULTILINE)
            if m:
                version = m.group(1)
            m = re.search(r"^model:\s*(.+)", output, re.MULTILINE)
            if m:
                platform = m.group(1).strip()
            m = re.search(r"^serial:\s*(\S+)", output, re.MULTILINE)
            if m:
                serial = m.group(1)

        elif device_type == "checkpoint_gaia":
            vendor = "Checkpoint"
            # `show version all` output: "Product version Check Point Gaia R81.10"
            m = re.search(r"Product version\s+(.+)", output)
            if m:
                version = m.group(1).strip()
            m = re.search(r"Hostname:\s*(\S+)", output, re.IGNORECASE)
            if m:
                hostname = m.group(1)

        return DeviceInventory(
            hostname=hostname,
            ip_address=ip,
            device_type=device_type,
            vendor=vendor,
            os_version=version,
            serial=serial,
            platform=platform,
        )


# ─── Network Health Collector ─────────────────────────────────────────────────

class NetworkHealthCollector:
    """Collects health metrics (interface errors, firmware, serial) from network devices.

    Supports the same device types as :class:`NetworkDiscoveryEngine`:
    ``cisco_ios``, ``cisco_nxos``, ``arista_eos``, ``juniper_junos``,
    ``fortinet``, ``paloalto_panos``, ``checkpoint_gaia``.
    """

    def get_health_metrics(
        self, device_ip: str, credentials: Dict[str, str]
    ) -> Optional[DeviceHealthMetrics]:
        """SSH into *device_ip* and return :class:`DeviceHealthMetrics`."""
        conn_params = NetworkDiscoveryEngine._build_conn_params(device_ip, credentials)
        device_type = credentials.get("device_type", "cisco_ios")
        try:
            with ConnectHandler(**conn_params) as conn:
                return self._collect(conn, device_ip, device_type)
        except (NetmikoAuthenticationException, NetmikoTimeoutException) as exc:
            logger.warning("Health collection failed for %s: %s", device_ip, exc)
            return None
        except Exception as exc:
            logger.error("Health collection error for %s: %s", device_ip, exc)
            return None

    @staticmethod
    def _collect(conn: Any, ip: str, device_type: str) -> DeviceHealthMetrics:
        metrics = DeviceHealthMetrics(ip_address=ip, vendor=_VENDOR_MAP.get(device_type, "unknown"))

        if device_type in ("cisco_ios", "cisco_nxos"):
            _collect_cisco(conn, metrics)
        elif device_type == "arista_eos":
            _collect_arista(conn, metrics)
        elif device_type == "juniper_junos":
            _collect_junos(conn, metrics)
        elif device_type == "fortinet":
            _collect_fortinet(conn, metrics)
        elif device_type == "paloalto_panos":
            _collect_panos(conn, metrics)
        elif device_type == "checkpoint_gaia":
            _collect_checkpoint(conn, metrics)

        return metrics


_VENDOR_MAP = {
    "cisco_ios": "Cisco",
    "cisco_nxos": "Cisco",
    "arista_eos": "Arista",
    "juniper_junos": "Juniper",
    "fortinet": "Fortinet",
    "paloalto_panos": "Palo Alto",
    "checkpoint_gaia": "Checkpoint",
}


def _safe_send(conn: Any, cmd: str) -> str:
    try:
        return conn.send_command(cmd)
    except Exception:
        return ""


def _collect_cisco(conn: Any, m: DeviceHealthMetrics) -> None:
    ver_out = _safe_send(conn, "show version")
    h = re.search(r"hostname\s+(\S+)", ver_out, re.IGNORECASE)
    if h:
        m.hostname = h.group(1)
    v = re.search(r"[Vv]ersion\s+(\S+)", ver_out)
    if v:
        m.firmware_version = v.group(1).rstrip(",")
    s = re.search(r"[Ss]erial\s+[Nn]umber\s*:\s*(\S+)", ver_out)
    if s:
        m.serial_number = s.group(1)
    p = re.search(r"[Cc]isco\s+(\S+)\s+processor", ver_out)
    if p:
        m.platform = p.group(1)

    intf_out = _safe_send(conn, "show interfaces")
    # Parse blocks: "<Intf> is up" … "X input errors" … "Y CRC"
    # Using a line-by-line state machine for robustness
    current_intf = None
    in_err = out_err = crc = 0
    for line in intf_out.splitlines():
        intf_m = re.match(r"^(\S+) is ", line)
        if intf_m:
            if current_intf:
                m.interface_stats.append(InterfaceStats(
                    name=current_intf,
                    input_errors=in_err,
                    output_errors=out_err,
                    crc_errors=crc,
                ))
            current_intf = intf_m.group(1)
            in_err = out_err = crc = 0
        elif current_intf:
            ie = re.search(r"(\d+)\s+input errors", line)
            if ie:
                in_err = int(ie.group(1))
            oe = re.search(r"(\d+)\s+output errors", line)
            if oe:
                out_err = int(oe.group(1))
            cr = re.search(r"(\d+)\s+CRC", line)
            if cr:
                crc = int(cr.group(1))
    if current_intf:
        m.interface_stats.append(InterfaceStats(
            name=current_intf,
            input_errors=in_err,
            output_errors=out_err,
            crc_errors=crc,
        ))


def _collect_arista(conn: Any, m: DeviceHealthMetrics) -> None:
    ver_out = _safe_send(conn, "show version")
    v = re.search(r"EOS version:\s*(\S+)", ver_out)
    if v:
        m.firmware_version = v.group(1)
    p = re.search(r"Arista\s+(\S+)", ver_out)
    if p:
        m.platform = p.group(1)
    s = re.search(r"[Ss]erial\s+[Nn]umber\s*:\s*(\S+)", ver_out)
    if s:
        m.serial_number = s.group(1)
    # Arista uses same `show interfaces` format as Cisco
    _collect_cisco_style_interfaces(conn, m)


def _collect_cisco_style_interfaces(conn: Any, m: DeviceHealthMetrics) -> None:
    intf_out = _safe_send(conn, "show interfaces")
    current_intf = None
    in_err = out_err = crc = 0
    for line in intf_out.splitlines():
        intf_m = re.match(r"^(\S+) is ", line)
        if intf_m:
            if current_intf:
                m.interface_stats.append(InterfaceStats(
                    name=current_intf, input_errors=in_err,
                    output_errors=out_err, crc_errors=crc,
                ))
            current_intf = intf_m.group(1)
            in_err = out_err = crc = 0
        elif current_intf:
            ie = re.search(r"(\d+)\s+input errors", line)
            if ie:
                in_err = int(ie.group(1))
            oe = re.search(r"(\d+)\s+output errors", line)
            if oe:
                out_err = int(oe.group(1))
            cr = re.search(r"(\d+)\s+CRC", line)
            if cr:
                crc = int(cr.group(1))
    if current_intf:
        m.interface_stats.append(InterfaceStats(
            name=current_intf, input_errors=in_err,
            output_errors=out_err, crc_errors=crc,
        ))


def _collect_junos(conn: Any, m: DeviceHealthMetrics) -> None:
    ver_out = _safe_send(conn, "show version")
    h = re.search(r"Hostname:\s*(\S+)", ver_out)
    if h:
        m.hostname = h.group(1)
    v = re.search(r"Junos:\s*(\S+)", ver_out)
    if v:
        m.firmware_version = v.group(1)
    s = re.search(r"Chassis:\s*(\S+)", ver_out)
    if s:
        m.serial_number = s.group(1)

    intf_out = _safe_send(conn, "show interfaces extensive")
    for match in _JUNOS_CRC_PATTERN.finditer(intf_out):
        m.interface_stats.append(InterfaceStats(
            name=match.group("intf"),
            crc_errors=int(match.group("crc")),
        ))


def _collect_fortinet(conn: Any, m: DeviceHealthMetrics) -> None:
    status_out = _safe_send(conn, "get system status")
    ver_m = re.search(r"Version:\s*(FortiGate-\S+)\s+(\S+)", status_out)
    if ver_m:
        m.platform = ver_m.group(1)
        raw = ver_m.group(2)
        m.firmware_version = raw.split(",")[0] if "," in raw else raw
    h = re.search(r"Hostname:\s*(\S+)", status_out)
    if h:
        m.hostname = h.group(1)
    s = re.search(r"Serial-Number:\s*(\S+)", status_out)
    if s:
        m.serial_number = s.group(1)

    # Interface stats via `diagnose netlink interface list`
    intf_out = _safe_send(conn, "diagnose netlink interface list")
    for match in _FORTI_IF_PATTERN.finditer(intf_out):
        m.interface_stats.append(InterfaceStats(
            name=match.group("intf"),
            input_errors=int(match.group("rxerr")),
            output_errors=int(match.group("txerr")),
        ))


def _collect_panos(conn: Any, m: DeviceHealthMetrics) -> None:
    info_out = _safe_send(conn, "show system info")
    h = re.search(r"^hostname:\s*(\S+)", info_out, re.MULTILINE)
    if h:
        m.hostname = h.group(1)
    v = re.search(r"^sw-version:\s*(\S+)", info_out, re.MULTILINE)
    if v:
        m.firmware_version = v.group(1)
    p = re.search(r"^model:\s*(.+)", info_out, re.MULTILINE)
    if p:
        m.platform = p.group(1).strip()
    s = re.search(r"^serial:\s*(\S+)", info_out, re.MULTILINE)
    if s:
        m.serial_number = s.group(1)

    # PAN-OS: `show interface all` — line format: name  state  ipaddr  ...
    intf_out = _safe_send(conn, "show interface all")
    # PAN-OS does not expose CRC counters via CLI; parse error counters from show counter global
    counter_out = _safe_send(conn, "show counter global filter delta yes")
    err_m = re.search(r"rcv_err\s+(\d+)", counter_out)
    if err_m:
        m.interface_stats.append(InterfaceStats(
            name="global",
            input_errors=int(err_m.group(1)),
        ))


def _collect_checkpoint(conn: Any, m: DeviceHealthMetrics) -> None:
    ver_out = _safe_send(conn, "show version all")
    v = re.search(r"Product version\s+(.+)", ver_out)
    if v:
        m.firmware_version = v.group(1).strip()
    h = re.search(r"Hostname:\s*(\S+)", ver_out, re.IGNORECASE)
    if h:
        m.hostname = h.group(1)

    # Checkpoint `show interface all` — simple table
    intf_out = _safe_send(conn, "show interface all")
    for line in intf_out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.match(r"eth\d+|bond\d+|lo", parts[0]):
            m.interface_stats.append(InterfaceStats(name=parts[0]))


# ─── Server Health Collector (Redfish + SNMP) ─────────────────────────────────

class ServerHealthCollector:
    """BMC/OOB health collector for Dell iDRAC, HP iLO, and IBM/Lenovo IMM.

    - Dell iDRAC and HP iLO expose the Redfish v1 REST API over HTTPS.
    - IBM/Lenovo IMM exposes health status via SNMP v2c.

    ``bmc_type`` accepted values: ``"idrac"``, ``"ilo"``, ``"imm"``.
    """

    def get_redfish_health(
        self,
        bmc_ip: str,
        username: str,
        password: str,
        bmc_type: str = "idrac",
        verify_ssl: bool = False,
    ) -> DeviceHealthMetrics:
        """Query Redfish REST API on *bmc_ip* and return health metrics.

        Args:
            bmc_ip: IP or FQDN of the BMC management interface.
            username: BMC local account username.
            password: BMC local account password.
            bmc_type: ``"idrac"`` (Dell) or ``"ilo"`` (HP).
            verify_ssl: Whether to verify the BMC's TLS certificate.

        Returns:
            :class:`DeviceHealthMetrics` populated from Redfish endpoints.
        """
        try:
            import httpx
        except ImportError:
            logger.error("httpx is required for Redfish health collection.")
            return DeviceHealthMetrics(ip_address=bmc_ip)

        base = f"https://{bmc_ip}/redfish/v1"
        auth = (username, password)
        metrics = DeviceHealthMetrics(ip_address=bmc_ip, vendor=_BMC_VENDOR.get(bmc_type, "unknown"))

        try:
            with httpx.Client(
                auth=auth,
                verify=verify_ssl,
                timeout=10.0,
                headers={"Accept": "application/json"},
            ) as client:
                metrics = _redfish_system(client, base, metrics)
                metrics = _redfish_chassis(client, base, metrics)
                metrics = _redfish_storage(client, base, metrics)
        except httpx.RequestError as exc:
            logger.warning("Redfish request error for %s: %s", bmc_ip, exc)
        except Exception as exc:
            logger.error("Redfish collection error for %s: %s", bmc_ip, exc)

        return metrics

    def get_snmp_health(
        self,
        device_ip: str,
        community: str = "public",
        bmc_type: str = "imm",
    ) -> DeviceHealthMetrics:
        """Query SNMP v2c on *device_ip* and return health metrics.

        Supports IBM/Lenovo IMM MIB (``bmc_type="imm"``).

        Args:
            device_ip: IP of the IMM/BMC SNMP interface.
            community: SNMP v2c community string.
            bmc_type: Currently only ``"imm"`` is supported.

        Returns:
            :class:`DeviceHealthMetrics` populated from SNMP.
        """
        metrics = DeviceHealthMetrics(ip_address=device_ip, vendor="IBM/Lenovo")
        try:
            from pysnmp.hlapi import (
                CommunityData,
                ContextData,
                ObjectIdentity,
                ObjectType,
                SnmpEngine,
                UdpTransportTarget,
                getCmd,
            )

            def _get(oid: str) -> str:
                for err_indication, err_status, _, var_binds in getCmd(
                    SnmpEngine(),
                    CommunityData(community, mpModel=1),
                    UdpTransportTarget((device_ip, 161), timeout=5, retries=1),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                ):
                    if err_indication or err_status:
                        return "unknown"
                    for _, val in var_binds:
                        return str(val)
                return "unknown"

            # IBM IMM2 / Lenovo XCC MIB OIDs (IBM-LAN-ADAPTERS-MIB / BLADECENTER-MIB)
            # System name: 1.3.6.1.2.1.1.5.0
            # System description: 1.3.6.1.2.1.1.1.0 (includes model and firmware)
            # IMM overall health: 1.3.6.1.4.1.2.3.51.3.1.4.1.0 (systemHealthStat)
            #   1=Good, 2=Warning, 3=Bad, 255=Unknown
            # PSU status: 1.3.6.1.4.1.2.3.51.3.1.11.1.1.6.1 (powerSupplyHealthStatus)
            # Temperature sensor: 1.3.6.1.4.1.2.3.51.3.1.2.1.2.1 (temperatureStat)

            metrics.hostname = _get("1.3.6.1.2.1.1.5.0")
            sysDescr = _get("1.3.6.1.2.1.1.1.0")
            if sysDescr != "unknown":
                # sysDescr typically contains model and firmware info
                fw_m = re.search(r"firmware\s+version[:\s]+(\S+)", sysDescr, re.IGNORECASE)
                if fw_m:
                    metrics.firmware_version = fw_m.group(1)
                model_m = re.search(r"model[:\s]+(\S+)", sysDescr, re.IGNORECASE)
                if model_m:
                    metrics.platform = model_m.group(1)

            health_code = _get("1.3.6.1.4.1.2.3.51.3.1.4.1.0")
            metrics.overall_health = _IMM_HEALTH_MAP.get(health_code, "unknown")

            psu_code = _get("1.3.6.1.4.1.2.3.51.3.1.11.1.1.6.1")
            metrics.psu_health = _IMM_HEALTH_MAP.get(psu_code, "unknown")

            temp_code = _get("1.3.6.1.4.1.2.3.51.3.1.2.1.2.1")
            metrics.temperature_health = _IMM_HEALTH_MAP.get(temp_code, "unknown")

        except ImportError:
            logger.error("pysnmp is required for SNMP health collection.")
        except Exception as exc:
            logger.error("SNMP collection error for %s: %s", device_ip, exc)

        return metrics


_BMC_VENDOR: Dict[str, str] = {
    "idrac": "Dell",
    "ilo": "HP",
    "imm": "IBM/Lenovo",
}

_IMM_HEALTH_MAP: Dict[str, str] = {
    "1": "OK",
    "2": "Warning",
    "3": "Critical",
    "255": "unknown",
}

_REDFISH_STATUS_MAP: Dict[str, str] = {
    "OK": "OK",
    "Warning": "Warning",
    "Critical": "Critical",
}


def _redfish_get(client: Any, url: str) -> Dict[str, Any]:
    """GET *url* and return parsed JSON, or empty dict on error."""
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.debug("Redfish GET %s failed: %s", url, exc)
        return {}


def _redfish_system(client: Any, base: str, m: DeviceHealthMetrics) -> DeviceHealthMetrics:
    """Populate metrics from Redfish /Systems/1 (or first system member)."""
    systems = _redfish_get(client, f"{base}/Systems")
    members = systems.get("Members", [])
    sys_url = members[0].get("@odata.id", "") if members else f"{base}/Systems/1"
    if not sys_url.startswith("http"):
        sys_url = f"https://{m.ip_address}{sys_url}"

    system = _redfish_get(client, sys_url)
    m.hostname = system.get("HostName") or system.get("Name") or m.hostname
    m.platform = system.get("Model", m.platform)
    m.serial_number = system.get("SerialNumber", m.serial_number)
    m.firmware_version = (
        system.get("BiosVersion")
        or system.get("FirmwareVersion")
        or m.firmware_version
    )

    status = system.get("Status", {})
    m.overall_health = _REDFISH_STATUS_MAP.get(status.get("Health", ""), "unknown")

    proc_summary = system.get("ProcessorSummary", {})
    m.cpu_health = _REDFISH_STATUS_MAP.get(
        proc_summary.get("Status", {}).get("Health", ""), "unknown"
    )

    mem_summary = system.get("MemorySummary", {})
    m.memory_health = _REDFISH_STATUS_MAP.get(
        mem_summary.get("Status", {}).get("Health", ""), "unknown"
    )

    return m


def _redfish_chassis(client: Any, base: str, m: DeviceHealthMetrics) -> DeviceHealthMetrics:
    """Populate PSU, fan, and temperature health from Redfish /Chassis/1."""
    chassis_list = _redfish_get(client, f"{base}/Chassis")
    members = chassis_list.get("Members", [])
    ch_url = members[0].get("@odata.id", "") if members else f"{base}/Chassis/1"
    if not ch_url.startswith("http"):
        ch_url = f"https://{m.ip_address}{ch_url}"

    chassis = _redfish_get(client, ch_url)

    # Power (PSU)
    power_url = chassis.get("Power", {}).get("@odata.id", "")
    if power_url:
        if not power_url.startswith("http"):
            power_url = f"https://{m.ip_address}{power_url}"
        power = _redfish_get(client, power_url)
        psu_statuses = [
            p.get("Status", {}).get("Health", "")
            for p in power.get("PowerSupplies", [])
        ]
        if psu_statuses:
            m.psu_health = (
                "OK" if all(s == "OK" for s in psu_statuses)
                else "Warning" if "Warning" in psu_statuses
                else "Critical"
            )

    # Thermal (fans + temperature)
    thermal_url = chassis.get("Thermal", {}).get("@odata.id", "")
    if thermal_url:
        if not thermal_url.startswith("http"):
            thermal_url = f"https://{m.ip_address}{thermal_url}"
        thermal = _redfish_get(client, thermal_url)
        fan_statuses = [
            f.get("Status", {}).get("Health", "")
            for f in thermal.get("Fans", [])
        ]
        if fan_statuses:
            m.fan_health = (
                "OK" if all(s == "OK" for s in fan_statuses)
                else "Warning" if "Warning" in fan_statuses
                else "Critical"
            )
        temp_statuses = [
            t.get("Status", {}).get("Health", "")
            for t in thermal.get("Temperatures", [])
        ]
        if temp_statuses:
            m.temperature_health = (
                "OK" if all(s == "OK" for s in temp_statuses)
                else "Warning" if "Warning" in temp_statuses
                else "Critical"
            )

    return m


def _redfish_storage(client: Any, base: str, m: DeviceHealthMetrics) -> DeviceHealthMetrics:
    """Populate RAID/disk health from Redfish /Systems/1/Storage."""
    systems = _redfish_get(client, f"{base}/Systems")
    members = systems.get("Members", [])
    sys_path = members[0].get("@odata.id", "/redfish/v1/Systems/1") if members else "/redfish/v1/Systems/1"
    storage_url = f"https://{m.ip_address}{sys_path}/Storage"

    storage_list = _redfish_get(client, storage_url)
    ctrl_members = storage_list.get("Members", [])
    disk_statuses: List[str] = []

    for ctrl_ref in ctrl_members:
        ctrl_url = ctrl_ref.get("@odata.id", "")
        if not ctrl_url:
            continue
        ctrl = _redfish_get(client, f"https://{m.ip_address}{ctrl_url}")
        for drive_ref in ctrl.get("Drives", []):
            drive_url = drive_ref.get("@odata.id", "")
            if not drive_url:
                continue
            drive = _redfish_get(client, f"https://{m.ip_address}{drive_url}")
            h = drive.get("Status", {}).get("Health", "")
            if h:
                disk_statuses.append(h)
            if drive.get("FailurePredicted"):
                m.raw_alerts.append(f"Drive {drive.get('Name','?')}: failure predicted")

    if disk_statuses:
        m.storage_health = (
            "OK" if all(s == "OK" for s in disk_statuses)
            else "Warning" if "Warning" in disk_statuses
            else "Critical"
        )

    return m


@dataclass
class NeighborInfo:
    local_port: str
    remote_hostname: str
    remote_ip: str
    remote_port: str
    platform: str = "unknown"
    capability: str = "unknown"


@dataclass
class DeviceInventory:
    hostname: str
    ip_address: str
    device_type: str
    vendor: str
    os_version: str
    serial: str = "unknown"
    platform: str = "unknown"


# ─── Regex patterns ──────────────────────────────────────────────────────────

_LLDP_PATTERN = re.compile(
    r"Local Intf:\s*(?P<local_port>\S+).*?"
    r"Port ID\s*:\s*(?P<remote_port>\S+).*?"
    r"System Name:\s*(?P<hostname>\S+).*?"
    r"Management Address(?:es)?:\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3}).*?"
    r"System Capabilities:\s*(?P<capability>[^\n]+)",
    re.DOTALL,
)

_CDP_BLOCK_PATTERN = re.compile(
    r"-{3,}\n"
    r"Device ID:\s*(?P<hostname>\S+)\s*\n"
    r".*?IP [Aa]ddress(?:es)?:\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s*\n"
    r".*?Platform:\s*(?P<platform>[^\n,]+).*?\n"
    r".*?Interface:\s*(?P<local_port>\S+),\s*Port ID.*?:\s*(?P<remote_port>\S+)",
    re.DOTALL,
)

# Fortinet `get system lldp neighbors-detail` block pattern
_FORTI_LLDP_PATTERN = re.compile(
    r"Interface\s*:\s*(?P<local_port>\S+).*?"
    r"Port ID\s*:\s*(?P<remote_port>\S+).*?"
    r"System Name\s*:\s*(?P<hostname>\S+).*?"
    r"Management Address\s*:\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
    re.DOTALL,
)

# Palo Alto `show lldp neighbors` tabular line pattern
# Columns: local-port  remote-chassis-id  remote-port-id  remote-port-desc  remote-system-name  mgmt-addr
_PANOS_LLDP_LINE = re.compile(
    r"^(?P<local_port>\S+)\s+\S+\s+(?P<remote_port>\S+)\s+\S+\s+(?P<hostname>\S+)\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
)

# Checkpoint Gaia `show lldp neighbors` uses LLDP standard format; reuse _LLDP_PATTERN

_VERSION_PATTERNS: Dict[str, re.Pattern] = {
    "cisco_ios": re.compile(
        r"Cisco IOS.*?Version\s+(?P<version>\S+).*?hostname\s+(?P<hostname>\S+)",
        re.DOTALL,
    ),
    "cisco_nxos": re.compile(
        r"NXOS:\s*version\s+(?P<version>\S+).*?Device name:\s*(?P<hostname>\S+)",
        re.DOTALL,
    ),
    "arista_eos": re.compile(
        r"Arista\s+(?P<platform>\S+).*?EOS version:\s*(?P<version>\S+)",
        re.DOTALL,
    ),
    "juniper_junos": re.compile(
        r"Junos:\s*(?P<version>\S+).*?Hostname:\s*(?P<hostname>\S+)",
        re.DOTALL,
    ),
    "fortinet": re.compile(
        r"Version:\s*FortiGate-\S+\s+(?P<version>\S+).*?Hostname:\s*(?P<hostname>\S+)",
        re.DOTALL,
    ),
    "paloalto_panos": re.compile(
        r"hostname:\s*(?P<hostname>\S+).*?sw-version:\s*(?P<version>\S+)",
        re.DOTALL,
    ),
    "checkpoint_gaia": re.compile(
        r"Product version\s+(?P<version>\S+).*?Hostname:\s*(?P<hostname>\S+)",
        re.DOTALL,
    ),
}


class NetworkDiscoveryEngine:
    """SSH-based LLDP/CDP topology discovery engine."""

    def __init__(self) -> None:
        self._seen_ips: set = set()

    # ─── Public interface ─────────────────────────────────────────────────

    def discover_neighbors(
        self, device_ip: str, credentials: Dict[str, str]
    ) -> List[NeighborInfo]:
        """SSH into *device_ip* and parse LLDP/CDP neighbor output."""
        conn_params = self._build_conn_params(device_ip, credentials)
        try:
            with ConnectHandler(**conn_params) as net_connect:
                return self._parse_neighbors(net_connect, credentials.get("device_type", "cisco_ios"))
        except (NetmikoAuthenticationException, NetmikoTimeoutException) as exc:
            logger.warning("Discovery failed for %s: %s", device_ip, exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error discovering %s: %s", device_ip, exc)
            return []

    def get_device_inventory(
        self, device_ip: str, credentials: Dict[str, str]
    ) -> Optional[DeviceInventory]:
        """Pull version/serial/platform info from *device_ip*."""
        conn_params = self._build_conn_params(device_ip, credentials)
        device_type = credentials.get("device_type", "cisco_ios")
        try:
            with ConnectHandler(**conn_params) as net_connect:
                return self._parse_inventory(net_connect, device_ip, device_type)
        except (NetmikoAuthenticationException, NetmikoTimeoutException) as exc:
            logger.warning("Inventory failed for %s: %s", device_ip, exc)
            return None
        except Exception as exc:
            logger.error("Inventory error for %s: %s", device_ip, exc)
            return None

    def build_topology_graph(
        self, seed_devices: List[str], credentials: Dict[str, str]
    ) -> Dict[str, Any]:
        """BFS crawl starting from *seed_devices*.

        Returns a dict with ``nodes`` (list of DeviceInventory dicts) and
        ``links`` (list of neighbor relationship dicts).
        """
        queue: deque = deque(seed_devices)
        self._seen_ips = set(seed_devices)
        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, str]] = []

        while queue:
            ip = queue.popleft()
            inventory = self.get_device_inventory(ip, credentials)
            if inventory:
                nodes.append(vars(inventory))
            neighbors = self.discover_neighbors(ip, credentials)
            for neighbor in neighbors:
                if neighbor.remote_ip and neighbor.remote_ip not in self._seen_ips:
                    self._seen_ips.add(neighbor.remote_ip)
                    queue.append(neighbor.remote_ip)
                links.append(
                    {
                        "source_ip": ip,
                        "target_ip": neighbor.remote_ip,
                        "source_port": neighbor.local_port,
                        "target_port": neighbor.remote_port,
                    }
                )

        return {"nodes": nodes, "links": links}

    # ─── Private helpers ─────────────────────────────────────────────────

    @staticmethod
    def _build_conn_params(ip: str, credentials: Dict[str, str]) -> Dict[str, Any]:
        return {
            "device_type": credentials.get("device_type", "cisco_ios"),
            "host": ip,
            "username": credentials.get("username", ""),
            "password": credentials.get("password", ""),
            "secret": credentials.get("secret", ""),
            "timeout": int(credentials.get("timeout", 15)),
        }

    @staticmethod
    def _parse_neighbors(
        net_connect: Any, device_type: str
    ) -> List[NeighborInfo]:
        neighbors: List[NeighborInfo] = []

        if device_type in ("cisco_ios", "cisco_nxos"):
            # Try LLDP first, fall back to CDP
            try:
                lldp_out = net_connect.send_command("show lldp neighbors detail")
                for m in _LLDP_PATTERN.finditer(lldp_out):
                    neighbors.append(
                        NeighborInfo(
                            local_port=m.group("local_port"),
                            remote_hostname=m.group("hostname"),
                            remote_ip=m.group("ip"),
                            remote_port=m.group("remote_port"),
                            capability=m.group("capability").strip(),
                        )
                    )
            except Exception:
                pass

            if not neighbors:
                try:
                    cdp_out = net_connect.send_command("show cdp neighbors detail")
                    for m in _CDP_BLOCK_PATTERN.finditer(cdp_out):
                        neighbors.append(
                            NeighborInfo(
                                local_port=m.group("local_port"),
                                remote_hostname=m.group("hostname"),
                                remote_ip=m.group("ip"),
                                remote_port=m.group("remote_port"),
                                platform=m.group("platform").strip(),
                            )
                        )
                except Exception:
                    pass

        elif device_type == "arista_eos":
            try:
                lldp_out = net_connect.send_command("show lldp neighbors detail")
                for m in _LLDP_PATTERN.finditer(lldp_out):
                    neighbors.append(
                        NeighborInfo(
                            local_port=m.group("local_port"),
                            remote_hostname=m.group("hostname"),
                            remote_ip=m.group("ip"),
                            remote_port=m.group("remote_port"),
                        )
                    )
            except Exception:
                pass

        elif device_type == "juniper_junos":
            try:
                lldp_out = net_connect.send_command("show lldp neighbors")
                for line in lldp_out.splitlines():
                    parts = line.split()
                    if len(parts) >= 4:
                        neighbors.append(
                            NeighborInfo(
                                local_port=parts[0],
                                remote_hostname=parts[2],
                                remote_ip="",
                                remote_port=parts[3],
                            )
                        )
            except Exception:
                pass

        elif device_type == "fortinet":
            try:
                lldp_out = net_connect.send_command("get system lldp neighbors-detail")
                for m in _FORTI_LLDP_PATTERN.finditer(lldp_out):
                    neighbors.append(
                        NeighborInfo(
                            local_port=m.group("local_port"),
                            remote_hostname=m.group("hostname"),
                            remote_ip=m.group("ip"),
                            remote_port=m.group("remote_port"),
                        )
                    )
            except Exception:
                pass

        elif device_type == "paloalto_panos":
            try:
                lldp_out = net_connect.send_command("show lldp neighbors")
                for line in lldp_out.splitlines():
                    m = _PANOS_LLDP_LINE.match(line.strip())
                    if m:
                        neighbors.append(
                            NeighborInfo(
                                local_port=m.group("local_port"),
                                remote_hostname=m.group("hostname"),
                                remote_ip=m.group("ip"),
                                remote_port=m.group("remote_port"),
                            )
                        )
            except Exception:
                pass

        elif device_type == "checkpoint_gaia":
            try:
                lldp_out = net_connect.send_command("show lldp neighbors detail")
                for m in _LLDP_PATTERN.finditer(lldp_out):
                    neighbors.append(
                        NeighborInfo(
                            local_port=m.group("local_port"),
                            remote_hostname=m.group("hostname"),
                            remote_ip=m.group("ip"),
                            remote_port=m.group("remote_port"),
                            capability=m.group("capability").strip(),
                        )
                    )
            except Exception:
                pass

        return neighbors

    @staticmethod
    def _parse_inventory(
        net_connect: Any, ip: str, device_type: str
    ) -> DeviceInventory:
        if device_type == "fortinet":
            show_ver_cmd = "get system status"
        elif device_type == "paloalto_panos":
            show_ver_cmd = "show system info"
        elif device_type == "checkpoint_gaia":
            show_ver_cmd = "show version all"
        else:
            show_ver_cmd = "show version"

        output = ""
        try:
            output = net_connect.send_command(show_ver_cmd)
        except Exception:
            pass

        hostname = ip
        version = "unknown"
        vendor = "unknown"
        platform = "unknown"
        serial = "unknown"

        if device_type in ("cisco_ios", "cisco_nxos"):
            vendor = "Cisco"
            m = re.search(r"hostname\s+(\S+)", output, re.IGNORECASE)
            if m:
                hostname = m.group(1)
            m = re.search(r"[Vv]ersion\s+(\S+)", output)
            if m:
                version = m.group(1).rstrip(",")
            m = re.search(r"[Ss]erial\s+[Nn]umber\s*:\s*(\S+)", output)
            if m:
                serial = m.group(1)
            m = re.search(r"[Cc]isco\s+(\S+)\s+processor", output)
            if m:
                platform = m.group(1)

        elif device_type == "arista_eos":
            vendor = "Arista"
            m = re.search(r"Arista\s+(\S+)", output)
            if m:
                platform = m.group(1)
            m = re.search(r"EOS version:\s*(\S+)", output)
            if m:
                version = m.group(1)

        elif device_type == "juniper_junos":
            vendor = "Juniper"
            m = re.search(r"Hostname:\s*(\S+)", output)
            if m:
                hostname = m.group(1)
            m = re.search(r"Junos:\s*(\S+)", output)
            if m:
                version = m.group(1)

        elif device_type == "fortinet":
            vendor = "Fortinet"
            # `get system status` output: "Version: FortiGate-100E v6.4.5,build1828,210318 (GA)"
            m = re.search(r"Version:\s*(FortiGate-\S+)\s+(\S+)", output)
            if m:
                platform = m.group(1)
                # Strip optional build/date suffix (e.g. "v6.4.5,build1828" → "v6.4.5")
                raw_ver = m.group(2)
                version = raw_ver.split(",")[0] if "," in raw_ver else raw_ver
            m = re.search(r"Hostname:\s*(\S+)", output)
            if m:
                hostname = m.group(1)
            m = re.search(r"Serial-Number:\s*(\S+)", output)
            if m:
                serial = m.group(1)

        elif device_type == "paloalto_panos":
            vendor = "Palo Alto"
            # `show system info` output
            m = re.search(r"^hostname:\s*(\S+)", output, re.MULTILINE)
            if m:
                hostname = m.group(1)
            m = re.search(r"^sw-version:\s*(\S+)", output, re.MULTILINE)
            if m:
                version = m.group(1)
            m = re.search(r"^model:\s*(.+)", output, re.MULTILINE)
            if m:
                platform = m.group(1).strip()
            m = re.search(r"^serial:\s*(\S+)", output, re.MULTILINE)
            if m:
                serial = m.group(1)

        elif device_type == "checkpoint_gaia":
            vendor = "Checkpoint"
            # `show version all` output: "Product version Check Point Gaia R81.10"
            m = re.search(r"Product version\s+(.+)", output)
            if m:
                version = m.group(1).strip()
            m = re.search(r"Hostname:\s*(\S+)", output, re.IGNORECASE)
            if m:
                hostname = m.group(1)

        return DeviceInventory(
            hostname=hostname,
            ip_address=ip,
            device_type=device_type,
            vendor=vendor,
            os_version=version,
            serial=serial,
            platform=platform,
        )

