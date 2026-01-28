"""
CLI entry point for Obsidian Timemachine.

Provides the command-line interface for all sync operations.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ..runner import run_sync
from ..config import load_config, ConfigError, DEFAULT_CONFIG_FILE


@click.group()
@click.version_option(package_name="obsidian-timemachine")
def cli() -> None:
    """Obsidian Timemachine - Automated backup for your Obsidian Vault.
    
    Syncs your Obsidian vault to a Git repository and pushes to GitHub.
    """
    pass


@cli.command()
@click.option(
    "-c", "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file.",
)
def sync(config: Path | None) -> None:
    """Run the sync and push operation.
    
    This performs a complete backup cycle:
    1. Pull remote changes
    2. Wait for iCloud sync (if applicable)
    3. Sync files with rsync
    4. Commit and push to Git
    """
    result = run_sync(config_path=config)
    
    if not result.success:
        if result.errors:
            for error in result.errors:
                click.echo(f"Error: {error}", err=True)
        sys.exit(1)
    
    if result.warnings:
        for warning in result.warnings:
            click.echo(f"Warning: {warning}", err=True)
    
    click.echo("✅ Sync completed successfully!")


@cli.command()
@click.option(
    "-c", "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file.",
)
def status(config: Path | None) -> None:
    """Check the current configuration and sync status."""
    config_path = config or DEFAULT_CONFIG_FILE
    
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        click.echo(f"\nNo configuration found at {config_path}")
        click.echo("Run 'ot setup' to create a configuration.")
        sys.exit(1)
    
    click.echo("📋 Current Configuration:")
    click.echo(f"   Source:      {cfg.source_dir}")
    click.echo(f"   Destination: {cfg.dest_dir}")
    click.echo(f"   Log Dir:     {cfg.log_dir}")
    click.echo(f"   SSH Key:     {cfg.ssh_key_path or 'Not configured'}")
    click.echo(f"   Log Retention: {cfg.log_retention_days} days")
    
    # Check paths
    click.echo("\n🔍 Path Status:")
    
    if cfg.source_dir.exists():
        click.echo(f"   ✅ Source exists")
    else:
        click.echo(f"   ❌ Source not found: {cfg.source_dir}")
    
    if cfg.dest_dir.exists():
        from ..git_ops import is_git_repo, get_remote_url, get_current_branch
        
        if is_git_repo(cfg.dest_dir):
            click.echo(f"   ✅ Destination is a Git repository")
            
            branch = get_current_branch(cfg.dest_dir)
            if branch:
                click.echo(f"      Branch: {branch}")
            
            remote = get_remote_url(cfg.dest_dir)
            if remote:
                click.echo(f"      Remote: {remote}")
            else:
                click.echo(f"      ⚠️ No remote configured")
        else:
            click.echo(f"   ⚠️ Destination exists but is not a Git repo")
    else:
        click.echo(f"   ❌ Destination not found: {cfg.dest_dir}")
    
    # Check schedule
    from ..scheduler import get_current_schedule, describe_schedule
    
    schedule = get_current_schedule()
    click.echo("\n⏰ Schedule Status:")
    if schedule:
        click.echo(f"   ✅ Auto-sync enabled: {describe_schedule(schedule)}")
    else:
        click.echo("   ⚠️ No auto-sync scheduled (manual only)")


@cli.command()
def setup() -> None:
    """Run the interactive configuration wizard.
    
    This will guide you through setting up the sync configuration.
    """
    from .wizard import run_wizard
    
    config = run_wizard()
    if config is None:
        click.echo("Setup cancelled.", err=True)
        sys.exit(1)


@cli.group()
def schedule() -> None:
    """Manage automatic sync schedule."""
    pass


@schedule.command("set")
@click.argument(
    "frequency",
    type=click.Choice(["15min", "30min", "hourly", "daily"]),
)
def schedule_set(frequency: str) -> None:
    """Set the auto-sync frequency.
    
    FREQUENCY: 15min, 30min, hourly, or daily
    """
    from ..scheduler import add_sync_schedule, describe_schedule, SCHEDULE_PRESETS
    
    if add_sync_schedule(frequency):
        cron_expr = SCHEDULE_PRESETS.get(frequency, frequency)
        click.echo(f"✅ Auto-sync enabled: {describe_schedule(cron_expr)}")
    else:
        click.echo("❌ Failed to set schedule", err=True)
        sys.exit(1)


@schedule.command("remove")
def schedule_remove() -> None:
    """Remove the auto-sync schedule."""
    from ..scheduler import remove_sync_schedule
    
    if remove_sync_schedule():
        click.echo("✅ Auto-sync disabled")
    else:
        click.echo("❌ Failed to remove schedule", err=True)
        sys.exit(1)


@schedule.command("show")
def schedule_show() -> None:
    """Show the current sync schedule."""
    from ..scheduler import get_current_schedule, describe_schedule
    
    schedule = get_current_schedule()
    if schedule:
        click.echo(f"Current schedule: {describe_schedule(schedule)}")
        click.echo(f"Cron expression: {schedule}")
    else:
        click.echo("No auto-sync schedule configured.")
        click.echo("Use 'ot schedule set <frequency>' to enable.")


@cli.command()
@click.option(
    "--check", "-c",
    is_flag=True,
    help="Only check for updates, don't install.",
)
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Force reinstall even if already at latest version.",
)
def update(check: bool, force: bool) -> None:
    """Check for updates and upgrade to the latest version.
    
    By default, this will check for available updates and prompt
    before installing. Use --check to only display update info.
    """
    from ..updater import (
        UpdateError,
        check_for_updates,
        perform_update,
        get_update_command,
        GITHUB_REPO_URL,
    )
    
    click.echo("🔍 Checking for updates...")
    
    try:
        info = check_for_updates()
    except UpdateError as e:
        click.echo(f"❌ Failed to check for updates: {e}", err=True)
        sys.exit(1)
    
    click.echo(f"\n📦 Version Information:")
    click.echo(f"   Current:  {info.current_version}")
    click.echo(f"   Latest:   {info.latest_version}")
    
    if info.is_latest:
        click.echo(f"\n✅ You are running the latest version!")
        if not force:
            return
        click.echo("   (Force reinstall requested)")
    else:
        click.echo(f"\n🆕 A new version is available!")
        if info.release_url:
            click.echo(f"   Release: {info.release_url}")
        if info.release_notes:
            click.echo(f"\n📝 Release Notes:")
            # Truncate long release notes
            notes = info.release_notes[:500]
            if len(info.release_notes) > 500:
                notes += "..."
            for line in notes.split("\n"):
                click.echo(f"   {line}")
    
    if check:
        click.echo(f"\n💡 To update, run: ot update")
        click.echo(f"   Or manually: {get_update_command()}")
        return
    
    # Prompt before update unless force
    if not force and not info.is_latest:
        click.echo("")
        if not click.confirm("Do you want to install this update?"):
            click.echo("Update cancelled.")
            return
    
    click.echo("")
    try:
        if perform_update(force=force):
            click.echo("\n🎉 Update completed! Please restart the application.")
        else:
            click.echo("\n❌ Update failed.", err=True)
            sys.exit(1)
    except UpdateError as e:
        click.echo(f"\n❌ Update failed: {e}", err=True)
        click.echo(f"\n💡 Try updating manually:")
        click.echo(f"   {get_update_command()}")
        sys.exit(1)


@cli.command()
def version() -> None:
    """Show detailed version information."""
    from ..updater import get_current_version, GITHUB_REPO_URL
    
    try:
        ver = get_current_version()
    except Exception:
        ver = "unknown"
    
    click.echo(f"Obsidian Timemachine v{ver}")
    click.echo(f"Repository: {GITHUB_REPO_URL}")
    click.echo("")
    click.echo("Use 'ot update --check' to check for available updates.")


@cli.command()
def menu() -> None:
    """Open the interactive menu."""
    from .menu import run_menu
    
    run_menu()


if __name__ == "__main__":
    cli()
