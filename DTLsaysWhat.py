# -*- coding: utf-8 -*-
"""
WHAT - Outil d'inventaire système inspiré de l'outil interne What de Stanley Rabinowitz pour VAX/VMS de DEC dans les années 80.
Conversion Python du script what.ps1.

Dépendances :
    pip install wmi pywin32 psutil

Usage :
    python what.py
    python what.py memory
    python what.py network
    python what.py all --output C:\\Temp\\inventaire.txt
    python what.py hardware --computer SERVEUR01

Catégories :
    all, system, hardware, memory, disk, gpu, network, software,
    services, processes, startup, security, updates, drivers,
    users, tasks, shares, events, perf, virt

Note : lancer avec  python -X utf8 what.py <categorie>
  ou définir la variable d'environnement PYTHONUTF8=1
  pour garantir l'affichage correct des accents sur Windows.
"""

import argparse
import ctypes
import datetime
import io
import os
import socket
import subprocess
import sys
import winreg

"""
Cette version est bilingue. Elle permet :
python dtlsayswhat.py all --lang fr
python dtlsayswhat.py all --lang en
"""

CURRENT_LANG = "fr"

I18N = {
    "fr": {
        "SYSTEM": "SYSTÈME",
        "HARDWARE": "MATÉRIEL",
        "MEMORY": "MÉMOIRE",

        "DISKS_AND_VOLUMES": "DISQUES ET VOLUMES",
        "GRAPHIC_CARDS": "CARTES GRAPHIQUES",

        "NETWORK": "RÉSEAU",
        "SOFTWARE": "LOGICIELS",

        "STARTED_SERVICES": "SERVICES",
        "RUNNING_PROCESSES": "PROCESSUS EN COURS D'EXÉCUTION",
        "STARTUP_INFO": "PROGRAMMES AU DÉMARRAGE",

        "SECURITY": "SÉCURITÉ",
        "INSTALLED_UPDATES": "MISES À JOUR INSTALLÉES",
        "INSTALLED_DRIVERS": "PILOTES INSTALLÉS",

        "USERS": "UTILISATEURS",
        "SCHEDULED_TASKS": "TÂCHES PLANIFIÉES",

        "NETWORK_SHARES": "PARTAGES RÉSEAU",
        "RECENT_EVENTS": "ÉVÉNEMENTS RÉCENTS",

        "PERFORMANCE": "PERFORMANCES",
        "VIRTUALISATION": "VIRTUALISATION",
    },

    "en": {
        "SYSTEM": "SYSTEM",
        "HARDWARE": "HARDWARE",
        "MEMORY": "MEMORY",

        "DISKS_AND_VOLUMES": "DISKS AND VOLUMES",
        "GRAPHIC_CARDS": "GRAPHIC CARDS",

        "NETWORK": "NETWORK",
        "SOFTWARE": "SOFTWARE",

        "STARTED_SERVICES": "SERVICES",
        "RUNNING_PROCESSES": "RUNNING PROCESSES",
        "STARTUP_INFO": "STARTUP PROGRAMS",

        "SECURITY": "SECURITY",
        "INSTALLED_UPDATES": "INSTALLED UPDATES",
        "INSTALLED_DRIVERS": "INSTALLED DRIVERS",

        "USERS": "USERS",
        "SCHEDULED_TASKS": "SCHEDULED TASKS",

        "NETWORK_SHARES": "NETWORK SHARES",
        "RECENT_EVENTS": "RECENT EVENTS",

        "PERFORMANCE": "PERFORMANCE",
        "VIRTUALISATION": "VIRTUALIZATION",
    }
}

def tr(key):
    return I18N[CURRENT_LANG].get(key, key)
    

# Forcer la sortie console en UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import wmi
except ImportError:
    print("Module 'wmi' manquant. Installer avec : pip install wmi pywin32")
    sys.exit(1)

try:
    import psutil
except ImportError:
    print("Module 'psutil' manquant. Installer avec : pip install psutil")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Page de codes OEM de cmd.exe (ex. 850 sur Windows francophones)
# ---------------------------------------------------------------------------

def _get_oem_encoding():
    """Lit la page de codes OEM depuis le registre Windows."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Nls\CodePage"
        )
        val, _ = winreg.QueryValueEx(key, "OEMCP")
        winreg.CloseKey(key)
        return f"cp{val}"
    except Exception:
        return "cp850"

_OEM_ENCODING = _get_oem_encoding()

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

CATEGORIES = [
    'all', 'system', 'hardware', 'memory', 'disk', 'gpu', 'network',
    'software', 'services', 'processes', 'startup', 'security',
    'updates', 'drivers', 'users', 'tasks', 'shares', 'events', 'perf', 'virt'
]

output_lines = []

# Structured HTML output: list of dicts with type in ('line','header','section')
html_entries = []


def out(line=""):
    output_lines.append(line)
    html_entries.append({'type': 'line', 'text': line})
    print(line)


def header(title):
    output_lines.append("")
    output_lines.append("=" * 60)
    output_lines.append(f"  {title}")
    output_lines.append("=" * 60)
    html_entries.append({'type': 'header', 'text': title})
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def section(title):
    output_lines.append("")
    output_lines.append(f"--- {title} ---")
    html_entries.append({'type': 'section', 'text': title})
    print()
    print(f"--- {title} ---")


def fmt_bytes(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "N/A"
    if n >= 1 << 30:
        return f"{n / (1 << 30):.2f} GB"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.2f} MB"
    if n >= 1 << 10:
        return f"{n / (1 << 10):.2f} KB"
    return f"{n} B"


def safe_str(val, default="N/A"):
    if val is None:
        return default
    if isinstance(val, bytes):
        for enc in ('utf-8', 'cp1252', 'latin-1'):
            try:
                return val.decode(enc).strip() or default
            except UnicodeDecodeError:
                continue
    s = str(val).strip()
    return s if s else default


def wmi_date(val):
    """Convertit une date WMI (format DMTFDateTime) en chaîne lisible."""
    if not val:
        return "N/A"
    try:
        return datetime.datetime.strptime(val[:14], "%Y%m%d%H%M%S").strftime("%d-%m-%Y %H:%M:%S")
    except Exception:
        return str(val)


def run(cmd, shell=True, is_powershell=False):
    """Exécute une commande et retourne stdout sous forme de liste de lignes."""
    try:
        # Pour les commandes PowerShell, on encapsule pour forcer UTF-8
        if is_powershell:
            # -OutputEncoding force PowerShell à écrire en UTF-8 sur stdout
            inner = cmd if not cmd.startswith('powershell') else cmd[len('powershell'):].lstrip()
            # On retire le préfixe "powershell -Command " si présent
            for prefix in ('powershell -Command ', 'powershell -command '):
                if cmd.startswith(prefix):
                    inner = cmd[len(prefix):]
                    break
            else:
                inner = cmd
            wrapped = (
                'powershell -NoProfile -NonInteractive '
                '-Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; '
                f'{inner.strip(chr(34))}"'
            )
            result = subprocess.run(
                wrapped, shell=True, capture_output=True, timeout=30
            )
            return result.stdout.decode('utf-8', errors='replace').splitlines()
        else:
            result = subprocess.run(cmd, shell=shell, capture_output=True, timeout=15)
            raw = result.stdout
            for enc in (_OEM_ENCODING, 'cp850', 'cp1252', 'utf-8'):
                try:
                    return raw.decode(enc).splitlines()
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw.decode('utf-8', errors='replace').splitlines()
    except Exception:
        return []


def ps(cmd):
    """Raccourci : exécute une commande PowerShell avec encodage UTF-8 forcé."""
    result = subprocess.run(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command',
         f'[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; {cmd}'],
        capture_output=True, timeout=30
    )
    return result.stdout.decode('utf-8', errors='replace').splitlines()


# ---------------------------------------------------------------------------
# Connexion WMI
# ---------------------------------------------------------------------------

def get_wmi(computer=None):
    try:
        if computer and computer.upper() != socket.gethostname().upper():
            return wmi.WMI(computer=computer)
        return wmi.WMI()
    except Exception as e:
        print(f"Erreur connexion WMI : {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def get_system_info(c):
    header(tr("SYSTEM"))

    chassis_types = {
        1: 'Autre', 2: 'Inconnu', 3: 'Desktop', 4: 'Low Profile Desktop',
        8: 'Portable', 9: 'Laptop', 10: 'Notebook', 11: 'Sous-portable',
        12: 'Docking Station', 14: 'All-in-One', 17: 'Rack Mount',
        23: 'Blade', 24: 'Blade Enclosure'
    }

    section(tr("Identification"))
    for cs in c.Win32_ComputerSystem():
        domain_type = "domaine" if cs.PartOfDomain else "workgroup"
        out(f"Nom machine         : {safe_str(cs.Name)}")
        out(f"Domaine / Workgroup : {safe_str(cs.Domain)} ({domain_type})")
        out(f"Fabricant           : {safe_str(cs.Manufacturer)}")
        out(f"Modèle              : {safe_str(cs.Model)}")

    for prod in c.Win32_ComputerSystemProduct():
        out(f"Numéro de série     : {safe_str(prod.IdentifyingNumber)}")
        out(f"UUID                : {safe_str(prod.UUID)}")

    for enc in c.Win32_SystemEnclosure():
        types = enc.ChassisTypes
        t = int(types[0]) if types else 0
        out(f"Type châssis        : {chassis_types.get(t, f'Type {t}')}")

    section(tr("Système d'exploitation"))
    for os_info in c.Win32_OperatingSystem():
        out(f"OS                  : {safe_str(os_info.Caption)}")
        out(f"Version / Build     : {safe_str(os_info.Version)} (Build {safe_str(os_info.BuildNumber)})")
        out(f"Architecture        : {safe_str(os_info.OSArchitecture)}")
        out(f"Répertoire Windows  : {safe_str(os_info.WindowsDirectory)}")
        out(f"Installation        : {wmi_date(os_info.InstallDate)}")
        boot = wmi_date(os_info.LastBootUpTime)
        try:
            boot_dt = datetime.datetime.strptime(os_info.LastBootUpTime[:14], "%Y%m%d%H%M%S")
            delta = datetime.datetime.now() - boot_dt
            days = delta.days
            hours, rem = divmod(delta.seconds, 3600)
            minutes = rem // 60
            uptime_str = f"{days}j {hours}h {minutes}m"
        except Exception:
            uptime_str = "N/A"
        out(f"Dernier démarrage   : {boot}  (uptime : {uptime_str})")

    section(tr("Fuseau horaire"))
    try:
        for tz in c.Win32_TimeZone():
            out(f"Fuseau horaire      : {safe_str(tz.Caption)}")
    except Exception:
        tz_name = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()
        out(f"Fuseau horaire      : {tz_name}")


def get_hardware_info(c):
    header(tr("HARDWARE"))

    section(tr("Processeur(s)"))
    arch_map = {0: 'x86', 1: 'MIPS', 2: 'Alpha', 3: 'PowerPC',
                5: 'ARM', 6: 'Itanium', 9: 'x64', 12: 'ARM64'}
    for cpu in c.Win32_Processor():
        arch = arch_map.get(cpu.Architecture, str(cpu.Architecture))
        out(f"Nom                 : {safe_str(cpu.Name)}")
        out(f"Fabricant           : {safe_str(cpu.Manufacturer)}")
        out(f"Cœurs physiques     : {safe_str(cpu.NumberOfCores)}")
        out(f"Cœurs logiques      : {safe_str(cpu.NumberOfLogicalProcessors)}")
        out(f"Fréquence base      : {safe_str(cpu.MaxClockSpeed)} MHz")
        out(f"Socket              : {safe_str(cpu.SocketDesignation)}")
        out(f"Architecture        : {arch}")
        out(f"Cache L2            : {safe_str(cpu.L2CacheSize)} KB")
        out(f"Cache L3            : {safe_str(cpu.L3CacheSize)} KB")
        out()

    section(tr("Carte mère"))
    for mb in c.Win32_BaseBoard():
        out(f"Fabricant           : {safe_str(mb.Manufacturer)}")
        out(f"Produit             : {safe_str(mb.Product)}")
        out(f"Version             : {safe_str(mb.Version)}")
        out(f"Numéro de série     : {safe_str(mb.SerialNumber)}")

    section(tr("BIOS / UEFI"))
    for bios in c.Win32_BIOS():
        out(f"Fabricant           : {safe_str(bios.Manufacturer)}")
        out(f"Version             : {safe_str(bios.SMBIOSBIOSVersion)}")
        out(f"Date                : {wmi_date(bios.ReleaseDate)}")
        out(f"Version SMBIOS      : {safe_str(bios.SMBIOSMajorVersion)}.{safe_str(bios.SMBIOSMinorVersion)}")


def get_memory_info(c):
    header(tr("MEMORY"))

    for os_info in c.Win32_OperatingSystem():
        total  = int(os_info.TotalVisibleMemorySize or 0) * 1024
        free   = int(os_info.FreePhysicalMemory or 0) * 1024
        vtotal = int(os_info.TotalVirtualMemorySize or 0) * 1024
        vfree  = int(os_info.FreeVirtualMemory or 0) * 1024
        out(f"RAM totale          : {fmt_bytes(total)}")
        out(f"RAM disponible      : {fmt_bytes(free)}")
        out(f"Mémoire virtuelle   : {fmt_bytes(vtotal)} total / {fmt_bytes(vfree)} libre")

    section(tr("Barrettes physiques"))
    mem_types = {
        0: 'Inconnu', 20: 'DDR', 21: 'DDR2', 22: 'DDR2 FB-DIMM',
        24: 'DDR3', 26: 'DDR4', 34: 'DDR5'
    }
    dimms = list(c.Win32_PhysicalMemory())
    for i, dimm in enumerate(dimms, 1):
        t = int(dimm.MemoryType or 0)
        type_str = mem_types.get(t, f"Type {t}")
        cap = fmt_bytes(int(dimm.Capacity or 0))
        out(
            f"Slot {i:<2} : {safe_str(dimm.BankLabel):<10} "
            f"{cap:<8} {safe_str(dimm.Speed)} MHz  "
            f"Type: {type_str}  Fabricant: {safe_str(dimm.Manufacturer)}"
            f"  SN: {safe_str(dimm.SerialNumber)}"
        )
    out()
    out(f"Nombre de barrettes : {len(dimms)}")


def get_disk_info(c):
    header(tr("DISKS AND VOLUMES"))

    section(tr("Disques physiques"))
    for disk in c.Win32_DiskDrive():
        out(f"Disque {safe_str(disk.Index)} : {safe_str(disk.Model)}")
        out(f"  Taille      : {fmt_bytes(disk.Size)}")
        out(f"  Interface   : {safe_str(disk.InterfaceType)}")
        out(f"  Partitions  : {safe_str(disk.Partitions)}")
        out(f"  SN          : {safe_str(disk.SerialNumber)}")
        out(f"  Statut      : {safe_str(disk.Status)}")

    section(tr("Volumes logiques"))
    drive_types = {2: 'Amovible', 3: 'Fixe', 4: 'Réseau', 5: 'CD/DVD', 6: 'RAM disk'}
    for vol in c.Win32_LogicalDisk():
        t = int(vol.DriveType or 0)
        type_str = drive_types.get(t, 'Inconnu')
        size = fmt_bytes(vol.Size)
        free = fmt_bytes(vol.FreeSpace)
        out(
            f"{safe_str(vol.DeviceID)}  [{type_str}]  "
            f"{safe_str(vol.FileSystem):<10}  "
            f"{size} total / {free} libre  Label: {safe_str(vol.VolumeName)}"
        )


def get_gpu_info(c):
    header(tr("GRAPHIC CARDS"))
    for gpu in c.Win32_VideoController():
        out(f"Nom                 : {safe_str(gpu.Name)}")
        out(f"Fabricant           : {safe_str(gpu.AdapterCompatibility)}")
        out(f"VRAM                : {fmt_bytes(gpu.AdapterRAM)}")
        out(
            f"Résolution actuelle : {safe_str(gpu.CurrentHorizontalResolution)} x "
            f"{safe_str(gpu.CurrentVerticalResolution)} @ "
            f"{safe_str(gpu.CurrentRefreshRate)} Hz"
        )
        out(f"Pilote              : {safe_str(gpu.DriverVersion)} du {wmi_date(gpu.DriverDate)}")
        out(f"Statut              : {safe_str(gpu.Status)}")
        out()


def get_network_info(c):
    header(tr("NETWORK"))

    section(tr("Interfaces réseau et adresses IP"))
    for iface, addrs in psutil.net_if_addrs().items():
        stats  = psutil.net_if_stats().get(iface)
        status = "Up" if (stats and stats.isup) else "Down"
        speed  = f"{stats.speed} Mbps" if (stats and stats.speed) else "N/A"
        out(f"{iface:<30} Statut: {status}  Vitesse: {speed}")
        for addr in addrs:
            fam = str(addr.family)
            if '2'  in fam: fam = 'IPv4'
            elif '23' in fam: fam = 'IPv6'
            elif '17' in fam: fam = 'MAC '
            out(f"  {fam:<6} {addr.address}")

    section(tr("Passerelles par défaut"))
    for line in run("ipconfig /all"):
        if "Passerelle" in line or "Gateway" in line or "Default" in line:
            out(f"  {line.strip()}")

    section(tr("DNS configuré"))
    for line in run("ipconfig /all"):
        if "DNS" in line and ":" in line:
            out(f"  {line.strip()}")

    section(tr("Table de routage"))
    for line in run("route print"):
        out(line)

    section(tr("Connexions TCP actives"))
    conns = psutil.net_connections(kind='tcp')
    established = sorted(
        [cn for cn in conns if cn.status == 'ESTABLISHED'],
        key=lambda x: x.laddr.port
    )
    for cn in established:
        laddr = f"{cn.laddr.ip}:{cn.laddr.port}"
        raddr = f"{cn.raddr.ip}:{cn.raddr.port}" if cn.raddr else "N/A"
        out(f"{laddr}  =>  {raddr}  [{cn.status}]")

    section(tr("Partages SMB locaux"))
    for line in run("net share"):
        out(line)

    section(tr("Lecteurs réseau mappés"))
    for line in run("net use"):
        out(line)

    section(tr("Proxy (utilisateur courant)"))
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if proxy_enable:
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            out(f"Proxy actif         : {proxy_server}")
        else:
            out("Proxy               : non configuré")
        winreg.CloseKey(key)
    except Exception:
        out("Proxy               : information non disponible")


def get_software_info(c):
    header(tr("SOFTWARE"))

    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    apps = []
    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path)
            i = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(key, i)
                    sub_key  = winreg.OpenKey(key, sub_name)
                    try:
                        name, _    = winreg.QueryValueEx(sub_key, "DisplayName")
                        version, _ = winreg.QueryValueEx(sub_key, "DisplayVersion")
                    except FileNotFoundError:
                        name = version = None
                    try:
                        publisher, _ = winreg.QueryValueEx(sub_key, "Publisher")
                    except FileNotFoundError:
                        publisher = ""
                    if name and name.strip():
                        apps.append((name.strip(), version or "", publisher or ""))
                    winreg.CloseKey(sub_key)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception:
            pass

    apps.sort(key=lambda x: x[0].lower())
    for name, version, publisher in apps:
        out(f"{name[:49]:<50} {version[:19]:<20} {publisher}")
    out()
    out(f"Total : {len(apps)} application(s)")

    section(tr("Applications Store (AppX)"))
    for line in ps("Get-AppxPackage | Select-Object Name,Version | Format-Table -AutoSize"):
        out(line)


def get_services_info(c):
    header(tr("STARTED_SERVICES"))

    section(tr("Services démarrés"))
    for svc in sorted(c.Win32_Service(), key=lambda s: s.DisplayName or ""):
        if svc.State == "Running":
            out(f"{safe_str(svc.DisplayName):<45} [{safe_str(svc.StartMode)}]")

    section(tr("Services arrêtés (démarrage automatique)"))
    for svc in sorted(c.Win32_Service(), key=lambda s: s.DisplayName or ""):
        if svc.State != "Running" and svc.StartMode == "Auto":
            out(f"{safe_str(svc.DisplayName):<45} Statut: {safe_str(svc.State)}")


def get_processes_info(c):
    header(tr("RUNNING_PROCESSES"))

    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_times']):
        try:
            mem     = p.info['memory_info'].rss if p.info['memory_info'] else 0
            cpu     = p.info['cpu_times']
            cpu_sec = round((cpu.user + cpu.system), 1) if cpu else 0
            procs.append((p.info['name'], p.info['pid'], mem, cpu_sec))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    procs.sort(key=lambda x: (x[0] or "").lower())
    for name, pid, mem, cpu_sec in procs:
        out(f"{safe_str(name):<35} PID: {pid:<8} RAM: {fmt_bytes(mem):<10} CPU: {cpu_sec}s")


def get_startup_info(c):
    header(tr("STARTUP_INFO"))

    section(tr("Entrées WMI Win32_StartupCommand"))
    for item in c.Win32_StartupCommand():
        out(
            f"{safe_str(item.Name):<35} "
            f"Utilisateur: {safe_str(item.User):<20} "
            f"Commande: {safe_str(item.Command)}"
        )

    section(tr("Registre (HKLM\\...\\Run)"))
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run")
        i = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(key, i)
                out(f"{name:<40} {val}")
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception:
        out("Registre HKLM Run : accès refusé ou clé absente")

    section(tr("Registre (HKCU\\...\\Run)"))
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run")
        i = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(key, i)
                out(f"{name:<40} {val}")
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception:
        out("Registre HKCU Run : accès refusé ou clé absente")


def get_security_info(c):
    header(tr("SECURITY"))

    section(tr("Windows Defender"))
    lines = ps(
        "Get-MpComputerStatus | "
        "Select-Object AntivirusEnabled,AntivirusSignatureVersion,"
        "AntivirusSignatureLastUpdated,RealTimeProtectionEnabled,"
        "AntispywareEnabled | Format-List"
    )
    if lines:
        for line in lines:
            out(line)
    else:
        out("Windows Defender : informations non disponibles")

    section(tr("Pare-feu"))
    for line in ps(
        "Get-NetFirewallProfile | "
        "Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction | "
        "Format-Table -AutoSize"
    ):
        out(line)

    section(tr("BitLocker"))
    bl_lines = ps(
        "Get-BitLockerVolume | "
        "Select-Object MountPoint,VolumeStatus,ProtectionStatus | "
        "Format-Table -AutoSize"
    )
    if any(l.strip() for l in bl_lines):
        for line in bl_lines:
            out(line)
    else:
        out("BitLocker : non disponible ou non configuré")

    section(tr("Secure Boot"))
    sb_lines = ps("Confirm-SecureBootUEFI")
    if sb_lines:
        val = sb_lines[0].strip()
        out(f"Secure Boot : {'Activé' if val == 'True' else 'Désactivé'}")
    else:
        out("Secure Boot : non applicable (BIOS legacy ou accès refusé)")

    section(tr("TPM"))
    for line in ps("Get-Tpm | Format-List"):
        out(line)


def get_updates_info(c):
    header(tr("INSTALLED_UPDATES"))
    for hf in sorted(
        c.Win32_QuickFixEngineering(),
        key=lambda x: x.InstalledOn or "",
        reverse=True
    ):
        out(
            f"{safe_str(hf.HotFixID):<15} "
            f"{safe_str(hf.InstalledOn):<15} "
            f"{safe_str(hf.InstalledBy):<30} "
            f"{safe_str(hf.Description)}"
        )


def get_drivers_info(c):
    header(tr("INSTALLED_DRIVERS"))
    drivers = sorted(
        [d for d in c.Win32_PnPSignedDriver() if d.DeviceName],
        key=lambda d: d.DeviceName or ""
    )
    for d in drivers:
        name = safe_str(d.DeviceName)[:44]
        out(f"{name:<45} {safe_str(d.DriverVersion):<20} {safe_str(d.Manufacturer)}")


def get_users_info(c):
    header(tr("USERS"))

    section(tr("Comptes locaux"))
    for line in ps("Get-LocalUser | Select-Object Name,Enabled,LastLogon | Format-Table -AutoSize"):
        out(line)

    section(tr("Profils utilisateurs"))
    for profile in c.Win32_UserProfile():
        if not profile.Special:
            out(f"{safe_str(profile.LocalPath):<40} Chargé: {safe_str(profile.Loaded)}")

    section(tr("Utilisateur courant"))
    out(f"Compte              : {os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}")
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    out(f"Administrateur      : {is_admin}")


def get_tasks_info(c):
    header(tr("SCHEDULED_TASKS"))
    for line in ps(
        "Get-ScheduledTask | "
        "Where-Object { $_.State -ne 'Disabled' -and $_.TaskPath -notlike '\\Microsoft\\*' } | "
        "Select-Object TaskPath,TaskName,State | "
        "Sort-Object TaskPath | "
        "Format-Table -AutoSize | "
        "Out-String -Width 4096"
    ):
        out(line)


def get_shares_info(c):
    header(tr("NETWORK_SHARES"))

    section(tr("Partages locaux (SMB)"))
    for share in c.Win32_Share():
        out(f"{safe_str(share.Name):<20} {safe_str(share.Path):<40} {safe_str(share.Description)}")

    section(tr("Lecteurs réseau mappés"))
    for net in c.Win32_NetworkConnection():
        out(f"{safe_str(net.LocalName)}  =>  {safe_str(net.RemoteName)}  [{safe_str(net.Status)}]")


def get_events_info(c):
    header(tr("RECENT_EVENTS"))

    for log_name in ("System", "Application"):
        section(f"Journal : {log_name}")
        lines = ps(
            f"Get-EventLog -LogName {log_name} "
            f"-EntryType Error,Warning -Newest 20 | "
            f"Select-Object TimeGenerated,EntryType,EventID,Message | "
            f"Format-List"
        )
        for line in lines:
            out(line)


def get_perf_info(c):
    header(tr("PERFORMANCE"))

    section(tr("CPU"))
    cpu_pct = psutil.cpu_percent(interval=1, percpu=True)
    for i, pct in enumerate(cpu_pct):
        out(f"Core {i:<3} : {pct}%")
    out(f"Charge globale      : {psutil.cpu_percent(interval=0)}%")

    section(tr("Mémoire"))
    mem = psutil.virtual_memory()
    out(f"Total               : {fmt_bytes(mem.total)}")
    out(f"Utilisée            : {fmt_bytes(mem.used)} ({mem.percent}%)")
    out(f"Libre               : {fmt_bytes(mem.available)}")

    swap = psutil.swap_memory()
    out(f"Swap total          : {fmt_bytes(swap.total)}")
    out(f"Swap utilisé        : {fmt_bytes(swap.used)} ({swap.percent}%)")

    section(tr("Disques"))
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            pct   = usage.percent
            out(
                f"{part.mountpoint}  {fmt_bytes(usage.used)} / "
                f"{fmt_bytes(usage.total)} utilisés ({pct}%)  "
                f"[{part.fstype}]"
            )
        except PermissionError:
            out(f"{part.mountpoint}  accès refusé")


def get_virt_info(c):
    header(tr("VIRTUALISATION"))

    section(tr("Détection : cette machine est-elle une VM ?"))
    vm_indicators = ['VMware', 'VirtualBox', 'Hyper-V', 'VBOX', 'QEMU', 'KVM', 'Xen', 'Microsoft Corporation']
    model_str = ""
    for cs in c.Win32_ComputerSystem():
        model_str += f" {safe_str(cs.Model)} {safe_str(cs.Manufacturer)}"
    for bios in c.Win32_BIOS():
        model_str += f" {safe_str(bios.Version)}"
    found = [ind for ind in vm_indicators if ind.lower() in model_str.lower()]
    if found:
        out(f"VM détectée         : oui (indicateurs : {', '.join(found)})")
    else:
        out("VM détectée         : non (probablement physique)")

    section(tr("Hyper-V"))
    for line in ps(
        "Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V "
        "| Select-Object FeatureName,State | Format-List"
    ):
        out(line)

    section(tr("Machines virtuelles Hyper-V (si rôle activé)"))
    for line in ps("Get-VM | Select-Object Name,State,MemoryAssigned,Generation | Format-Table -AutoSize"):
        out(line)

    section(tr("WSL"))
    wsl_lines = run("wsl --list --verbose")
    if wsl_lines:
        for line in wsl_lines:
            out(line)
    else:
        out("WSL : non installé ou non accessible")



# ---------------------------------------------------------------------------
# Génération HTML
# ---------------------------------------------------------------------------

_HTML_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: #0a0a0a;
    color: #00cc44;
    font-family: 'Courier New', Courier, monospace;
    font-size: 13px;
    padding: 0;
}
#sidebar {
    position: fixed;
    top: 0; left: 0;
    width: 220px;
    height: 100vh;
    background: #050505;
    border-right: 1px solid #004d1a;
    overflow-y: auto;
    padding: 12px 0;
    z-index: 100;
}
#sidebar h2 {
    color: #00ff66;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    padding: 0 14px 10px;
    border-bottom: 1px solid #004d1a;
    margin-bottom: 8px;
}
#sidebar a {
    display: block;
    color: #009933;
    text-decoration: none;
    padding: 4px 14px;
    font-size: 11px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color 0.15s, background 0.15s;
}
#sidebar a:hover { color: #00ff66; background: #0d1f12; }
#main {
    margin-left: 220px;
    padding: 30px 40px 60px;
    max-width: 1100px;
}
.meta {
    color: #006622;
    font-size: 11px;
    margin-bottom: 24px;
    border-bottom: 1px solid #004d1a;
    padding-bottom: 10px;
}
.header-block {
    margin-top: 40px;
    margin-bottom: 4px;
}
.header-block .hbar {
    color: #00ff66;
    font-size: 11px;
    letter-spacing: 1px;
}
.header-block h1 {
    color: #00ff66;
    font-size: 16px;
    font-weight: bold;
    letter-spacing: 3px;
    text-transform: uppercase;
    text-shadow: 0 0 8px #00cc44;
    padding: 4px 0;
}
.section-block {
    margin-top: 22px;
    margin-bottom: 6px;
}
.section-block h2 {
    color: #00cc44;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 1px;
    border-left: 3px solid #00cc44;
    padding-left: 8px;
}
.line {
    color: #00aa33;
    white-space: pre;
    line-height: 1.55;
    font-size: 12px;
}
.line.empty { line-height: 0.7; }
.scanline {
    pointer-events: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        to bottom,
        transparent 0px,
        transparent 3px,
        rgba(0,0,0,0.08) 3px,
        rgba(0,0,0,0.08) 4px
    );
    z-index: 9999;
}
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #050505; }
::-webkit-scrollbar-thumb { background: #004d1a; border-radius: 3px; }
"""

def _esc(text):
    """Échappe les caractères HTML."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def generate_html(category, computer, generated_at):
    """Construit le fichier HTML à partir de html_entries."""
    headers_seen = []
    for e in html_entries:
        if e['type'] == 'header':
            headers_seen.append(e['text'])

    # Barre latérale
    nav_items = "\n".join(
        f'<a href="#hdr-{i}">{_esc(t)}</a>'
        for i, t in enumerate(headers_seen)
    )

    # Contenu principal
    body_parts = []
    hdr_idx = -1
    for e in html_entries:
        t = e['type']
        text = e['text']
        if t == 'header':
            hdr_idx += 1
            anchor = f'hdr-{hdr_idx}'
            body_parts.append(
                f'<div class="header-block" id="{anchor}">'
                f'<div class="hbar">{"=" * 60}</div>'
                f'<h1>{_esc(text)}</h1>'
                f'<div class="hbar">{"=" * 60}</div>'
                f'</div>'
            )
        elif t == 'section':
            body_parts.append(
                f'<div class="section-block">'
                f'<h2>--- {_esc(text)} ---</h2>'
                f'</div>'
            )
        else:  # line
            if text.strip() == "":
                body_parts.append('<div class="line empty">&nbsp;</div>')
            else:
                body_parts.append(f'<div class="line">{_esc(text)}</div>')

    body_html = "\n".join(body_parts)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DTLsaysWhat :: {_esc(computer)}</title>
<style>{_HTML_CSS}</style>
</head>
<body>
<div class="scanline"></div>
<nav id="sidebar">
  <h2>Navigation</h2>
  {nav_items}
</nav>
<div id="main">
  <div class="meta">
    DTLsaysWhat &nbsp;|&nbsp; Machine : {_esc(computer)}
    &nbsp;|&nbsp; Catégorie : {_esc(category.upper())}
    &nbsp;|&nbsp; {_esc(generated_at)}
  </div>
  {body_html}
</div>
</body>
</html>"""
    return html

# ---------------------------------------------------------------------------
# Bannière
# ---------------------------------------------------------------------------

def banner(category, computer):
    out()
    out(" __        ___  _    _  _____  ")
    out(r" \ \      / / || |  / \|_   _| ")
    out(r"  \ \ /\ / /|_||_| / _ \ | |   ")
    out(r"   \ V  V / |_||_|/ ___ \| |   ")
    out(r"    \_/\_/  |_||_/_/   \_\_|   ")
    out()
    now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    out(f"Machine : {computer}   Date : {now}")
    out(f"Catégorie sélectionnée : {category.upper()}")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

DISPATCH = {
    'system':    get_system_info,
    'hardware':  get_hardware_info,
    'memory':    get_memory_info,
    'disk':      get_disk_info,
    'gpu':       get_gpu_info,
    'network':   get_network_info,
    'software':  get_software_info,
    'services':  get_services_info,
    'processes': get_processes_info,
    'startup':   get_startup_info,
    'security':  get_security_info,
    'updates':   get_updates_info,
    'drivers':   get_drivers_info,
    'users':     get_users_info,
    'tasks':     get_tasks_info,
    'shares':    get_shares_info,
    'events':    get_events_info,
    'perf':      get_perf_info,
    'virt':      get_virt_info,
}


def main():
    parser = argparse.ArgumentParser(
        prog="what",
        description="WHAT - Outil d'inventaire système Windows (inspiré du What de DEC VAX/VMS)"
    )
    
    parser.add_argument(
        "--lang",
        choices=["fr", "en"],
        default="fr",
        help="Language"
    )
    
    parser.add_argument(
        "category",
        nargs="?",
        default="system",
        choices=CATEGORIES,
        metavar="CATÉGORIE",
        help="Catégorie à interroger : " + ", ".join(CATEGORIES)
    )
    
    parser.add_argument(
        "--output", "-o",
        metavar="FICHIER",
        help="Sauvegarder le rapport dans un fichier texte"
    )
    
    parser.add_argument(
        "--computer",
        metavar="NOM_OU_IP",
        default=socket.gethostname(),
        help="Nom ou IP de la machine cible (défaut : machine locale)"
    )
    args = parser.parse_args()
    
    global CURRENT_LANG
    CURRENT_LANG = args.lang
    print("LANG =", CURRENT_LANG)

    c = get_wmi(args.computer)
    banner(args.category, args.computer)

    if args.category == 'all':
        for fn in DISPATCH.values():
            fn(c)
    else:
        DISPATCH[args.category](c)

    now = datetime.datetime.now()
    out()
    out(f"=== Fin du rapport  {now.strftime('%d-%m-%Y %H:%M:%S')} ===")

    if args.output:
        output_path = args.output
    else:
        hostname = socket.gethostname()
        date_str = now.strftime("%Y%m%d_%H%M%S")
        output_path = f"DTLsaysWhat_{hostname}_{date_str}.txt"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        print(f"Rapport texte sauvegardé : {output_path}")
    except OSError as e:
        print(f"Impossible d'écrire dans : {output_path}")
        print(str(e))

    html_path = output_path.replace(".txt", ".html") if output_path.endswith(".txt") else output_path + ".html"
    try:
        html_content = generate_html(
            args.category,
            args.computer,
            now.strftime("%d-%m-%Y %H:%M:%S")
        )
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Rapport HTML  sauvegardé : {html_path}")
    except OSError as e:
        print(f"Impossible d'écrire dans : {html_path}")
        print(str(e))


if __name__ == "__main__":
    main()
