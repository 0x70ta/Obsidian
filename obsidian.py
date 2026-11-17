import argparse
import getpass
import sys
import time

import serial
from serial.tools import list_ports
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
import pyfiglet

console = Console()

def banner():
    ascii_art = pyfiglet.figlet_format("OBSIDIAN", font="smslant")
    art = Text(ascii_art, style="bold purple")
    credit = Text.from_markup(
        "Created by [bold white] Mahmoud Ibrahiem [/bold white]  •  "
        "[bold blue link=https://github.com/0x70ta]github.com/0x70ta[/bold blue link]"
    )
    console.print(Panel.fit(Text.assemble(art, "\n", credit),
                            border_style="purple", padding=(1, 3)))

def password_hex(prompt):
    value = getpass.getpass(prompt)
    raw = value.encode("utf-8")
    if len(raw) < 8 or len(raw) > 64:
        raise ValueError("Password must encode to 8–64 UTF-8 bytes.")
    return raw.hex()

class Device:
    def __init__(self, port):
        self.ser = serial.Serial(port, 115200, timeout=0.25, write_timeout=5)
        time.sleep(2)
        self.ser.reset_input_buffer()

    def command(self, line, wait_for=None, timeout=20):
        self.ser.reset_input_buffer()
        self.ser.write((line + "\n").encode("ascii"))
        self.ser.flush()
        lines=[]
        start=time.monotonic()
        while time.monotonic()-start < timeout:
            raw=self.ser.readline()
            if raw:
                s=raw.decode("utf-8","replace").strip()
                if s:
                    lines.append(s)
                    console.print(s)
                    if wait_for and s.startswith(wait_for):
                        break
                    if not wait_for and len(lines)>0 and time.monotonic()-start>1:
                        break
            elif lines and time.monotonic()-start>2:
                break
        return lines

def choose_port():
    ports=list(list_ports.comports())
    if not ports:
        raise RuntimeError("No serial ports found.")
    table=Table(title="Serial ports")
    table.add_column("Port",style="cyan")
    table.add_column("Description")
    for p in ports: table.add_row(p.device,p.description or "")
    console.print(table)
    return console.input("[cyan]Port (e.g. COM9): [/cyan]").strip()

def main():
    parser=argparse.ArgumentParser(description="Obsidian v2 desktop manager")
    parser.add_argument("--port")
    args=parser.parse_args()
    banner()
    port=args.port or choose_port()
    try:
        dev=Device(port)
    except Exception as e:
        console.print(f"[red]Cannot open {port}: {e}[/red]")
        return 2
    try:
        console.print("[green]Connected.[/green]")
        dev.command("PING")
        while True:
            console.print("\n[bold purple]OBSIDIAN CONTROL[/bold purple]")
            console.print("1 Status   2 Initialize/format   3 Unlock decoy")
            console.print("4 Unlock hidden   5 Lock   6 Help   0 Exit")
            choice=console.input("[cyan]Select: [/cyan]").strip()
            try:
                if choice=="1":
                    dev.command("STATUS")
                elif choice=="2":
                    console.print("[yellow]This writes volume headers to SD sectors 0 and 1.[/yellow]")
                    confirm=console.input("Type FORMAT to continue: ")
                    if confirm!="FORMAT": continue
                    d1=password_hex("New decoy password: ")
                    d2=password_hex("Confirm decoy password: ")
                    if d1!=d2: raise ValueError("Decoy passwords do not match.")
                    h1=password_hex("New hidden password: ")
                    h2=password_hex("Confirm hidden password: ")
                    if h1!=h2: raise ValueError("Hidden passwords do not match.")
                    if d1==h1: raise ValueError("Use different passwords for the two volumes.")
                    dev.command(f"FORMAT {d1} {h1}", "FORMAT_RESULT=", 60)
                elif choice in ("3","4"):
                    vol="D" if choice=="3" else "H"
                    pw=password_hex("Volume password: ")
                    dev.command(f"UNLOCK {vol} {pw}", "UNLOCK_RESULT=", 60)
                    console.print("[yellow]If unlock succeeds, Windows should enumerate a USB drive. "
                                  "Eject it in Windows before locking.[/yellow]")
                elif choice=="5":
                    dev.command("LOCK","LOCK_RESULT=",15)
                elif choice=="6":
                    dev.command("HELP")
                elif choice=="0":
                    break
                else:
                    console.print("[red]Invalid choice.[/red]")
            except (ValueError, KeyboardInterrupt) as e:
                console.print(f"[red]{e}[/red]")
    finally:
        dev.ser.close()
    return 0

if __name__=="__main__":
    sys.exit(main())
