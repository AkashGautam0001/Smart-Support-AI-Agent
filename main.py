"""
main.py
━━━━━━━
SmartSupport AI — Main Entry Point
Production-level customer support intelligence platform.

Usage:
  python main.py                    # Run full demo with sample tickets
  python main.py --ticket           # Interactive single ticket mode
  python main.py --test             # Run all unit tests
  python main.py --optimize billing # Show optimization suggestions for a dept
  python main.py --ab billing       # Show A/B test status for a dept

Requires: ANTHROPIC_API_KEY environment variable
"""

import sys
import os
import argparse
import logging
import subprocess

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging — INFO level shows pipeline steps, DEBUG shows full prompts
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
# Suppress noisy HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)


def run_demo():
    """Run the full demo with all 8 sample tickets."""
    from rich.console import Console
    from rich.prompt import Confirm
    from core.pipeline import SupportPipeline, TicketRequest
    from data.sample_tickets import SAMPLE_TICKETS
    from utils.display import (
        console, print_header, print_ticket_input,
        print_guard_result, print_analysis, print_response, print_report
    )

    print_header()
    console.print(f"[dim]Running demo with {len(SAMPLE_TICKETS)} sample tickets...[/dim]")
    console.print()

    pipeline = SupportPipeline()

    for i, ticket in enumerate(SAMPLE_TICKETS, 1):
        console.print(f"\n[dim]Ticket {i}/{len(SAMPLE_TICKETS)}[/dim]")
        print_ticket_input(
            ticket.ticket_id,
            ticket.customer_name,
            ticket.customer_tier,
            ticket.message
        )

        result = pipeline.process(ticket)

        if result.injection_blocked:
            print_guard_result(result)
        else:
            console.print(f"  [green]✓[/green] [dim]Guard: PASS[/dim]")
            if result.analysis:
                print_analysis(result.analysis)
            print_response(result)

        # Pause between tickets for readability
        if i < len(SAMPLE_TICKETS):
            console.print()
            try:
                if not Confirm.ask("[dim]Continue to next ticket?[/dim]", default=True):
                    break
            except (EOFError, KeyboardInterrupt):
                break

    # Final report
    print_report(pipeline.full_report())


def run_interactive():
    """Interactive single ticket mode."""
    from rich.console import Console
    from rich.prompt import Prompt
    from core.pipeline import SupportPipeline, TicketRequest
    from utils.display import (
        console, print_header, print_ticket_input,
        print_guard_result, print_analysis, print_response
    )

    print_header()
    pipeline = SupportPipeline()

    console.print("[bold]Interactive Ticket Mode[/bold] — type your customer message\n")

    while True:
        try:
            name = Prompt.ask("[cyan]Customer name[/cyan]", default="Customer")
            tier = Prompt.ask("[cyan]Tier[/cyan]", choices=["standard", "premium", "enterprise"], default="standard")
            prior = int(Prompt.ask("[cyan]Prior contacts on this issue[/cyan]", default="0"))
            message = Prompt.ask("[cyan]Customer message[/cyan]")

            if not message.strip():
                continue

            request = TicketRequest(
                message=message,
                customer_name=name,
                customer_tier=tier,
                prior_contacts=prior,
            )

            print_ticket_input(request.ticket_id, name, tier, message)
            result = pipeline.process(request)

            if result.injection_blocked:
                print_guard_result(result)
            else:
                if result.analysis:
                    print_analysis(result.analysis)
                print_response(result)

            console.print()
            again = Prompt.ask("[dim]Process another ticket? (y/n)[/dim]", default="y")
            if again.lower() != "y":
                break

        except (KeyboardInterrupt, EOFError):
            break

    console.print("\n[dim]Exiting SmartSupport. Goodbye.[/dim]")


def run_tests():
    """Run the unit test suite."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_components.py", "-v", "--tb=short"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    sys.exit(result.returncode)


def run_optimization(department: str):
    """Show optimization analysis for a department."""
    from rich.console import Console
    from rich.panel import Panel
    from core.pipeline import SupportPipeline
    from data.sample_tickets import SAMPLE_TICKETS

    console = Console()
    console.print(f"\n[bold cyan]Running optimization analysis for: {department}[/bold cyan]\n")

    pipeline = SupportPipeline()

    # Process all tickets to build performance data
    console.print("[dim]Processing sample tickets to build performance data...[/dim]")
    for ticket in SAMPLE_TICKETS[:4]:
        pipeline.process(ticket)

    # Get refinement suggestion
    suggestion = pipeline.optimizer.analyze_failures_and_suggest_refinement(
        department=department,
        current_prompt_excerpt=f"You are a {department} support agent. Respond to customer tickets.",
    )

    if "error" in suggestion:
        console.print(f"[red]Error: {suggestion['error']}[/red]")
        return

    console.print(Panel(
        f"[bold]Root Cause:[/bold]\n{suggestion.get('root_cause', 'N/A')}\n\n"
        f"[bold]Suggested Refinement:[/bold]\n{suggestion.get('refined_prompt', 'N/A')}\n\n"
        f"[bold]Expected Improvement:[/bold]\n{suggestion.get('expected_improvement', 'N/A')}",
        title=f"[yellow]Prompt Optimization for {department}[/yellow]",
        border_style="yellow",
        padding=(1, 2),
    ))


def main():
    parser = argparse.ArgumentParser(description="SmartSupport AI — Customer Intelligence Platform")
    parser.add_argument("--ticket", action="store_true", help="Interactive single ticket mode")
    parser.add_argument("--test", action="store_true", help="Run unit tests")
    parser.add_argument("--optimize", metavar="DEPT", help="Run optimization for a department")
    parser.add_argument("--demo", action="store_true", help="Run full demo (default)")
    args = parser.parse_args()

    if args.test:
        run_tests()
    elif args.ticket:
        run_interactive()
    elif args.optimize:
        run_optimization(args.optimize)
    else:
        run_demo()


if __name__ == "__main__":
    main()
