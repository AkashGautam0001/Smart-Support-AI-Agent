"""
utils/display.py
━━━━━━━━━━━━━━━
Rich terminal display helpers for SmartSupport CLI.
Provides color-coded panels, tables, and status indicators.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich import box
from rich.columns import Columns
from rich.padding import Padding

console = Console()

PRIORITY_COLORS = {
    "low": "green",
    "medium": "yellow",
    "high": "red",
    "critical": "bold red",
}

SENTIMENT_COLORS = {
    "positive": "green",
    "neutral": "cyan",
    "frustrated": "yellow",
    "angry": "red",
    "urgent": "bold red",
    "unknown": "white",
}

DEPT_COLORS = {
    "billing": "cyan",
    "technical": "blue",
    "returns": "magenta",
    "escalation": "bold red",
    "general": "white",
    "security": "bold red",
}


def print_header():
    console.print()
    console.print(Rule("[bold cyan]SmartSupport AI — Production Customer Intelligence Platform[/bold cyan]"))
    console.print(
        "[dim]Tool Use & Function Calling · Chain-of-Thought · Role Prompting · "
        "XML Tags · System Prompts · Negative Constraints · Iterative Refinement · Injection Defense[/dim]"
    )
    console.print()


def print_ticket_input(ticket_id: str, customer: str, tier: str, message: str):
    console.print(Rule(f"[yellow]Ticket {ticket_id}[/yellow]"))
    meta = f"[bold]{customer}[/bold]  tier=[cyan]{tier}[/cyan]"
    console.print(Panel(
        f"{meta}\n\n[white]{message}[/white]",
        title="[yellow]📨 Incoming Ticket[/yellow]",
        border_style="yellow",
        padding=(1, 2),
    ))


def print_guard_result(result):
    if result.injection_blocked:
        console.print(Panel(
            f"[bold red]🛡 INJECTION BLOCKED[/bold red]\n"
            f"Threat level: [red]CRITICAL[/red]\n"
            f"[dim]{result.final_response}[/dim]",
            title="[red]Security Guard[/red]",
            border_style="red",
        ))
        return False
    else:
        console.print(f"  [green]✓[/green] [dim]Injection guard: PASS — input sanitized & XML-isolated[/dim]")
        return True


def print_analysis(analysis: dict):
    dept = analysis.get("category", "general")
    priority = analysis.get("priority", "medium")
    sentiment = analysis.get("sentiment", "neutral")
    dept_color = DEPT_COLORS.get(dept, "white")
    pri_color = PRIORITY_COLORS.get(priority, "white")
    sent_color = SENTIMENT_COLORS.get(sentiment, "white")

    thinking = analysis.get("thinking", "")
    summary = analysis.get("summary", "")
    actions = analysis.get("suggested_actions", [])
    repeat = analysis.get("repeat_contact", False)

    # CoT thinking block
    if thinking:
        short_thinking = thinking[:400] + "..." if len(thinking) > 400 else thinking
        console.print(Panel(
            f"[dim]{short_thinking}[/dim]",
            title="[blue]🧠 CoT Reasoning (Chain-of-Thought)[/blue]",
            border_style="blue dim",
            padding=(0, 1),
        ))

    # Analysis result
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", justify="right")
    grid.add_column()
    grid.add_row("Department", f"[{dept_color}]{dept.upper()}[/{dept_color}]")
    grid.add_row("Priority", f"[{pri_color}]{priority.upper()}[/{pri_color}]")
    grid.add_row("Sentiment", f"[{sent_color}]{sentiment}[/{sent_color}]")
    grid.add_row("Summary", summary)
    grid.add_row("Repeat Contact", "[red]YES[/red]" if repeat else "[green]No[/green]")
    grid.add_row("ETA", analysis.get("estimated_resolution_time", "unknown"))
    if actions:
        grid.add_row("Actions", "\n".join(f"• {a}" for a in actions))

    console.print(Panel(grid, title="[blue]🔍 Ticket Analysis[/blue]", border_style="blue", padding=(1, 2)))


def print_response(response: TicketResponse):
    dept_color = DEPT_COLORS.get(response.department, "white")
    qa_color = "green" if response.quality_passed else "yellow"
    qa_icon = "✓" if response.quality_passed else "⚠"

    console.print(Panel(
        f"[white]{response.final_response}[/white]",
        title=f"[{dept_color}]💬 Agent Response[/{dept_color}]  "
              f"[dim]persona={response.department} · {response.shot_technique}[/dim]",
        border_style=dept_color,
        padding=(1, 2),
    ))

    # QA badge
    issues_text = ""
    if response.quality_issues:
        issues_text = "\n" + "\n".join(f"  [yellow]⚠ {i}[/yellow]" for i in response.quality_issues[:3])

    console.print(
        f"  [{qa_color}]{qa_icon}[/{qa_color}] [dim]QA Score: "
        f"[bold]{response.quality_score}/100[/bold] · "
        f"{response.processing_time_ms:.0f}ms[/dim]"
        + issues_text
    )


def print_report(report: dict):
    console.print()
    console.print(Rule("[bold cyan]📊 Session Report[/bold cyan]"))

    # Overview table
    overview = Table(box=box.ROUNDED, border_style="cyan", show_header=True)
    overview.add_column("Metric", style="dim")
    overview.add_column("Value", style="bold")

    overview.add_row("Tickets Processed", str(report.get("tickets_processed", 0)))
    overview.add_row("Avg Quality Score", f"{report.get('avg_quality_score', 0)}/100")
    overview.add_row("Avg Processing Time", f"{report.get('avg_processing_ms', 0):.0f}ms")
    overview.add_row("Injections Blocked", str(report.get("injection_blocked", 0)))

    qa = report.get("qa_stats", {})
    if qa:
        overview.add_row("QA Pass Rate", qa.get("pass_rate", "N/A"))
        overview.add_row("QA Issues Found", str(qa.get("total_issues_found", 0)))

    console.print(overview)

    # By department
    by_dept = report.get("by_department", {})
    if by_dept:
        dept_table = Table(title="By Department", box=box.SIMPLE, border_style="blue")
        dept_table.add_column("Department")
        dept_table.add_column("Count", justify="right")
        for dept, count in sorted(by_dept.items(), key=lambda x: -x[1]):
            color = DEPT_COLORS.get(dept, "white")
            dept_table.add_row(f"[{color}]{dept}[/{color}]", str(count))
        console.print(dept_table)

    # Optimizer
    opt = report.get("optimizer_report", {})
    if opt and opt.get("by_shot_technique"):
        tech_table = Table(title="Avg Score by Shot Technique", box=box.SIMPLE, border_style="magenta")
        tech_table.add_column("Technique")
        tech_table.add_column("Avg Score", justify="right")
        for tech, score in opt.get("by_shot_technique", {}).items():
            tech_table.add_row(tech, f"{score:.1f}")
        console.print(tech_table)


# Avoid circular import — import TicketResponse here
from core.pipeline import TicketResponse


def print_response(response: "TicketResponse"):
    dept_color = DEPT_COLORS.get(response.department, "white")
    qa_color = "green" if response.quality_passed else "yellow"
    qa_icon = "✓" if response.quality_passed else "⚠"

    console.print(Panel(
        f"[white]{response.final_response}[/white]",
        title=f"[{dept_color}]💬 Agent Response[/{dept_color}]  "
              f"[dim]persona={response.department} · {response.shot_technique}[/dim]",
        border_style=dept_color,
        padding=(1, 2),
    ))

    issues_text = ""
    if response.quality_issues:
        issues_text = "\n" + "\n".join(f"  [yellow]⚠ {i}[/yellow]" for i in response.quality_issues[:3])

    console.print(
        f"  [{qa_color}]{qa_icon}[/{qa_color}] [dim]QA Score: "
        f"[bold]{response.quality_score}/100[/bold] · "
        f"{response.processing_time_ms:.0f}ms[/dim]"
        + issues_text
    )
