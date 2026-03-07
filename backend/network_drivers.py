"""
Netmiko-based network auto-discovery engine.

Supports: Cisco IOS, Cisco NX-OS, Arista EOS, Juniper JunOS,
          Fortinet FortiOS, Palo Alto PAN-OS, Checkpoint Gaia.
Performs BFS topology crawl using LLDP / CDP neighbor tables.
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

