import json
import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box
from . import __version__
from .intel import parse_number
from .engine import scan
from .modules import ALL_MODULES, SOURCE_NAMES
from .assessment import assess

console = Console()

BANNER = """
[bold cyan]  ╔─ WHONUM ─────────────────────────────────────────────╗[/bold cyan]
[bold cyan]  │[/bold cyan]  [bold white]phone osint[/bold white] [dim]· number intelligence · caller id[/dim]    [bold cyan]│[/bold cyan]
[bold cyan]  ╚───────────────────────────────────────────────────────╝[/bold cyan]
"""


@click.command()
@click.argument("number")
@click.option("--region", "-r", default=None, help="Default region if no + prefix (e.g. GB, US)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--timeout", "-t", default=12, show_default=True, help="Timeout per source (seconds)")
@click.option("--no-banner", is_flag=True, hidden=True)
def main(number, region, as_json, timeout, no_banner):
    """Look up a phone NUMBER — caller ID, spam reports, platform presence."""

    if not as_json and not no_banner:
        console.print(BANNER)

    try:
        intel = parse_number(number, region)
    except ValueError as e:
        console.print(f"[red]Invalid number: {e}[/red]")
        raise SystemExit(1)

    if not as_json:
        _print_intel(intel)
        console.print(f"[dim]Checking {len(ALL_MODULES)} sources...[/dim]\n")

    results = asyncio.run(scan(intel, timeout=timeout))
    risk = assess(intel, results)

    if as_json:
        click.echo(json.dumps({"intel": intel, "results": results, "sim_farm": risk}, indent=2))
        return

    # Filter API-key-required sources that have no key set
    display = [r for r in results if not (r["found"] is None and (r.get("error") or "").startswith("set "))]

    found = [r for r in display if r["found"] is True]
    not_found = [r for r in display if r["found"] is False]
    unknown = [r for r in display if r["found"] is None]

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim")
    table.add_column("Source", style="bold", min_width=18)
    table.add_column("Status", min_width=14)
    table.add_column("Detail", style="dim")

    for r in found + not_found + unknown:
        if r["found"] is True:
            status = Text("● ACTIVE", style="bold green")
        elif r["found"] is False:
            status = Text("○ not found", style="dim")
        else:
            err = r.get("error") or "unknown"
            status = Text(f"? {err}"[:32], style="dim yellow")
        detail = (r.get("detail") or "")[:60]
        table.add_row(r["name"], status, detail)

    if table.row_count:
        console.print(table)

    # SIM-farm / virtual-number risk assessment
    style_map = {
        "HIGH": "bold red", "ELEVATED": "bold yellow",
        "LOW": "yellow", "CLEAN": "dim green",
    }
    icon_map = {"HIGH": "⚠", "ELEVATED": "⚡", "LOW": "•", "CLEAN": "✓"}
    rstyle = style_map.get(risk["level"], "dim")
    console.print(
        f"\n  {Text(icon_map[risk['level']] + '  SIM-FARM RISK: ' + risk['level'], style=rstyle)}"
    )
    console.print(f"  [{rstyle}]{risk['label']}[/{rstyle}] [dim](score {risk['score']}/100)[/dim]")
    for s in risk["signals"]:
        console.print(f"    [dim]·[/dim] {s}")
    console.print(
        f"\n  [bold green]{len(found)} hits[/bold green]  "
        f"[dim]{len(not_found)} clean  {len(unknown)} unknown[/dim]\n"
    )


def _print_intel(intel: dict):
    console.print(f"  [dim]Number[/dim]      [bold cyan]{intel['international']}[/bold cyan]")
    console.print(f"  [dim]E.164[/dim]       [bold]{intel['e164']}[/bold]")
    console.print(f"  [dim]Country[/dim]     {intel['country']} [dim]({intel['region_code']})[/dim]")
    if intel["region"] and intel["region"] not in (intel["country"], "Unknown"):
        console.print(f"  [dim]Region[/dim]      {intel['region']}")
    console.print(f"  [dim]Type[/dim]        {intel['type']}")
    if intel["carrier"] and intel["carrier"] != "Unknown":
        console.print(f"  [dim]Carrier[/dim]     {intel['carrier']}")
    if intel["timezones"]:
        console.print(f"  [dim]Timezone[/dim]    {', '.join(intel['timezones'][:2])}")
    console.print(f"  [dim]Valid[/dim]       {'[bold green]Yes[/bold green]' if intel['valid'] else '[yellow]Possible[/yellow]'}")
    console.print()
