# DTLsaysWhat

DTLsaysWhat is a Windows system inventory tool inspired by the classic **WHAT**
utility written by Stanley Rabinowitz for DEC VAX/VMS systems in the 1980s.

Its goal is to produce a complete, readable report about a Windows machine from
a single command, without a central server or a heavy installation process.

The current source reports `APP_VERSION = "v1.0-2"`.

## Features

- System identification and operating system details
- Hardware inventory
- Physical and virtual memory
- Disks and logical volumes
- Graphics adapters
- Network configuration
- Probable Internet services, grouped by service and protocol
- IPv4 default gateway, IPv4 DNS servers, and IPv4 routing table
- Installed software and Microsoft Store / AppX packages
- Windows services
- Running processes, grouped by process name
- Optional process sorting by decreasing total RAM usage
- Startup programs
- Windows security status
- Installed updates
- Installed drivers, with duplicate entries removed
- Local users and loaded profiles
- Scheduled tasks
- Local SMB shares and mapped network drives
- Recent Windows event log analysis
- Performance snapshot
- Virtualization detection
- Text report
- HTML report

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or later
- PowerShell

Install the Python dependencies:

```bash
pip install psutil wmi pywin32
```

## Usage

Show help:

```bash
python DTLsaysWhat.py -h
```

Generate a system report:

```bash
python DTLsaysWhat.py system
```

Generate a network report:

```bash
python DTLsaysWhat.py network
```

Generate a full report:

```bash
python DTLsaysWhat.py all
```

Generate a report for a remote computer through WMI:

```bash
python DTLsaysWhat.py system --computer PC-BEN-001
```

Use English labels:

```bash
python DTLsaysWhat.py system --lang en
```

Write the text report to a specific file:

```bash
python DTLsaysWhat.py all --output C:\Temp\inventory.txt
```

Sort running processes by decreasing total RAM usage:

```bash
python DTLsaysWhat.py processes --sorted
```

## Categories

Available categories are:

```text
all, system, hardware, memory, disk, gpu, network, software,
services, processes, startup, security, updates, drivers,
users, tasks, shares, events, perf, virt
```

When no category is provided, `system` is used.

## Command-Line Options

```text
--lang fr|en          Main report label language. Defaults to fr.
--output, -o FILE     Write the text report to FILE.
--computer NAME_OR_IP Target computer for WMI-based collection.
--sorted              For processes, sort by decreasing total RAM usage.
```

`--computer` depends on Windows/WMI permissions and network access. Some
PowerShell-based sections still run locally.

## Output

DTLsaysWhat writes:

- a text report (`.txt`)
- an HTML report (`.html`)

If `--output` is not provided, the text report is named:

```text
DTLsaysWhat_<hostname>_<YYYYMMDD_HHMMSS>.txt
```

The HTML report uses the same base name with an `.html` extension.

## Network Report Notes

The network section is intentionally written for readability:

- active Internet connections are summarized as probable services;
- local communications are counted separately;
- the default gateway is shown as IPv4;
- DNS servers are shown as IPv4;
- the routing table is limited to IPv4.

Probable Internet services are inferred from ports, known IP ranges, and the
owning process name when available. Reverse DNS is not used.

## Process Report Notes

The process list is grouped by executable name. For duplicate processes, the
number of instances is shown in parentheses:

```text
chrome.exe (13)     PID: 2148   RAM totale: 1.40 GB
explorer.exe        PID: 17144  RAM totale: 298.41 MB
```

Only one representative PID is displayed. For detailed per-process inspection,
use a dedicated tool such as Process Monitor or Process Explorer.

## Event Log Analysis

The `events` category uses `Get-WinEvent`, not the older `Get-EventLog`.

It reads up to 1000 recent warning and error events from the `System` and
`Application` logs, then groups them by:

- log name;
- provider/source;
- event ID;
- level.

The report shows occurrence counts, the most recent occurrence, and a short
interpretation when the DTL knowledge base contains one.

Unknown events are reported as:

```text
Base DTL            : Aucune interprétation disponible.
```

## Event Knowledge Base

Event interpretations are stored outside the Python source in:

```text
events.json
```

Each entry has this shape:

```json
{
  "provider": "disk",
  "event_id": 153,
  "severity": "watch",
  "cause": "High storage response time or retried disk command.",
  "action": "Monitor the disk, cables, controller, and SMART status if the event returns."
}
```

Supported severities are:

```text
ignore, plan, watch, other
```

When packaged with PyInstaller, `events.json` is included by
`DTLsaysWhat.spec`.

## Documentation

The repository also contains user guides and reference manuals in French and
English, plus example HTML reports.

## License

This project is distributed under the MIT license.
