"""
CLI for managing ClickHouse backfills.

Usage:
    python -m weave.trace_server.backfills list [--database=weave] [--status=pending]
    python -m weave.trace_server.backfills run --database=weave --version=1
    python -m weave.trace_server.backfills status --database=weave --version=1
    python -m weave.trace_server.backfills pause --database=weave --version=1
    python -m weave.trace_server.backfills resume --database=weave --version=1
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from clickhouse_connect import get_client

from weave.trace_server.backfills import BackfillError, ClickHouseBackfillManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def get_manager() -> ClickHouseBackfillManager:
    """
    Create and return a ClickHouseBackfillManager instance from environment variables.
    
    Environment variables:
        CLICKHOUSE_HOST: ClickHouse host (default: localhost)
        CLICKHOUSE_PORT: ClickHouse port (default: 8123)
        CLICKHOUSE_USER: Username (default: default)
        CLICKHOUSE_PASSWORD: Password (default: empty)
    
    Returns:
        ClickHouseBackfillManager: Configured manager instance.
    """
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    user = os.getenv("CLICKHOUSE_USER", "default")
    password = os.getenv("CLICKHOUSE_PASSWORD", "")
    
    logger.info(f"Connecting to ClickHouse at {host}:{port} as {user}")
    
    ch_client = get_client(
        host=host,
        port=port,
        username=user,
        password=password,
    )
    
    return ClickHouseBackfillManager(ch_client)


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_rows(count: int) -> str:
    """Format row count with thousands separators."""
    return f"{count:,}"


def cmd_list(args: argparse.Namespace) -> None:
    """Handle list command."""
    manager = get_manager()
    
    backfills = manager.list_backfills(
        database=args.database,
        status=args.status,
    )
    
    if not backfills:
        print("\nNo backfills found.")
        return
    
    print(f"\n{'Version':<10} {'Database':<15} {'Status':<12} {'Rows Processed':<18} {'Started':<20} {'Updated':<20}")
    print("=" * 110)
    
    for bf in backfills:
        print(
            f"{bf['migration_version']:<10} "
            f"{bf['db_name']:<15} "
            f"{bf['status']:<12} "
            f"{format_rows(bf['rows_processed']):<18} "
            f"{format_datetime(bf['started_at']):<20} "
            f"{format_datetime(bf['updated_at']):<20}"
        )
    
    print()


def cmd_run(args: argparse.Namespace) -> None:
    """Handle run command."""
    manager = get_manager()
    
    try:
        logger.info(f"Starting backfill for database={args.database}, version={args.version}")
        if args.max_batches:
            logger.info(f"Limited to {args.max_batches} batches for testing")
        
        manager.run_backfill(
            database=args.database,
            version=args.version,
            max_batches=args.max_batches,
        )
        logger.info("✓ Backfill completed successfully")
    except KeyboardInterrupt:
        logger.info("\n⚠ Backfill interrupted by user - checkpoint saved")
        sys.exit(1)
    except BackfillError as e:
        logger.error(f"✗ Backfill failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    """Handle status command."""
    manager = get_manager()
    
    status = manager.get_status(args.database, args.version)
    
    if not status.get("found"):
        print(f"\n✗ Backfill not found: {args.database}_{args.version}")
        print("\nTip: Run 'list' to see available backfills")
        return
    
    print(f"\n{'='*60}")
    print(f"Backfill Status: {status['backfill_id']}")
    print(f"{'='*60}")
    print(f"Status:          {status['status']}")
    print(f"Rows Processed:  {format_rows(status['rows_processed'])}")
    print(f"Started:         {format_datetime(status['started_at'])}")
    print(f"Updated:         {format_datetime(status['updated_at'])}")
    print(f"Completed:       {format_datetime(status['completed_at'])}")
    
    if status.get("error_log"):
        print(f"\n{'─'*60}")
        print("Last Error:")
        print(f"{'─'*60}")
        print(status['error_log'])
    
    if status.get("checkpoint"):
        print(f"\n{'─'*60}")
        print("Checkpoint Details:")
        print(f"{'─'*60}")
        checkpoint = status['checkpoint']
        print(f"  Batches Completed:  {checkpoint.get('batches_completed', 0)}")
        print(f"  Current Batch Size: {checkpoint.get('current_batch_size', 'N/A'):,}")
        
        print(f"\n  Position:")
        for key, value in checkpoint.items():
            if key not in ['batches_completed', 'current_batch_size', 'rows_processed', 'started_at', 'last_updated']:
                print(f"    {key}: {value}")
    
    print()


def cmd_pause(args: argparse.Namespace) -> None:
    """Handle pause command."""
    manager = get_manager()
    
    try:
        manager.pause_backfill(args.database, args.version)
        print(f"\n✓ Backfill paused: {args.database}_{args.version}")
    except Exception as e:
        logger.error(f"✗ Failed to pause backfill: {e}")
        sys.exit(1)


def cmd_resume(args: argparse.Namespace) -> None:
    """Handle resume command."""
    manager = get_manager()
    
    try:
        logger.info(f"Resuming backfill for database={args.database}, version={args.version}")
        if args.max_batches:
            logger.info(f"Limited to {args.max_batches} batches for testing")
        
        manager.resume_backfill(
            database=args.database,
            version=args.version,
            max_batches=args.max_batches,
        )
        logger.info("✓ Backfill completed successfully")
    except KeyboardInterrupt:
        logger.info("\n⚠ Backfill interrupted by user - checkpoint saved")
        sys.exit(1)
    except BackfillError as e:
        logger.error(f"✗ Failed to resume backfill: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        sys.exit(1)


def cmd_clear(args: argparse.Namespace) -> None:
    """Handle clear command."""
    manager = get_manager()
    
    try:
        if args.all:
            # Clear all checkpoints
            manager.ch_client.command("DELETE FROM db_management.backfills")
            print("✓ Cleared all backfill checkpoints")
        else:
            # Clear specific backfill - validate required args
            if not args.database or not args.version:
                print("✗ Error: --database and --version are required when not using --all")
                sys.exit(1)
                
            backfill_id = f"{args.database}_{args.version}"
            result = manager.ch_client.command(f"DELETE FROM db_management.backfills WHERE backfill_id = '{backfill_id}'")
            print(f"✓ Cleared checkpoint for backfill: {backfill_id}")
            
            # Show confirmation
            status = manager.get_status(args.database, args.version)
            if not status.get("found"):
                print(f"  Confirmed: {backfill_id} no longer exists")
            else:
                print(f"  Warning: {backfill_id} still exists (deletion may have failed)")
                
    except Exception as e:
        logger.error(f"✗ Failed to clear checkpoint: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ClickHouse Backfill Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all backfills
  python -m weave.trace_server.backfills list

  # List pending backfills for a database
  python -m weave.trace_server.backfills list --database=weave --status=pending

  # Run a backfill
  python -m weave.trace_server.backfills run --database=weave --version=1

  # Run with limited batches for testing
  python -m weave.trace_server.backfills run --database=weave --version=1 --max-batches=10

  # Check status
  python -m weave.trace_server.backfills status --database=weave --version=1

  # Pause and resume
  python -m weave.trace_server.backfills pause --database=weave --version=1
  python -m weave.trace_server.backfills resume --database=weave --version=1

  # Clear checkpoints
  python -m weave.trace_server.backfills clear --database=weave --version=1
  python -m weave.trace_server.backfills clear --all

Environment Variables:
  CLICKHOUSE_HOST        ClickHouse host (default: localhost)
  CLICKHOUSE_PORT        ClickHouse port (default: 8123)
  CLICKHOUSE_USER        Username (default: default)
  CLICKHOUSE_PASSWORD    Password (default: empty)
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True
    
    # List command
    list_parser = subparsers.add_parser("list", help="List backfills")
    list_parser.add_argument("--database", help="Filter by database name")
    list_parser.add_argument("--status", help="Filter by status (pending, running, completed, failed, paused)")
    list_parser.set_defaults(func=cmd_list)
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a backfill")
    run_parser.add_argument("--database", required=True, help="Target database name")
    run_parser.add_argument("--version", type=int, required=True, help="Backfill version number")
    run_parser.add_argument("--max-batches", type=int, help="Maximum batches to run (for testing)")
    run_parser.set_defaults(func=cmd_run)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show backfill status")
    status_parser.add_argument("--database", required=True, help="Target database name")
    status_parser.add_argument("--version", type=int, required=True, help="Backfill version number")
    status_parser.set_defaults(func=cmd_status)
    
    # Pause command
    pause_parser = subparsers.add_parser("pause", help="Pause a running backfill")
    pause_parser.add_argument("--database", required=True, help="Target database name")
    pause_parser.add_argument("--version", type=int, required=True, help="Backfill version number")
    pause_parser.set_defaults(func=cmd_pause)
    
    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume a paused backfill")
    resume_parser.add_argument("--database", required=True, help="Target database name")
    resume_parser.add_argument("--version", type=int, required=True, help="Backfill version number")
    resume_parser.add_argument("--max-batches", type=int, help="Maximum batches to run (for testing)")
    resume_parser.set_defaults(func=cmd_resume)
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear backfill checkpoints")
    clear_group = clear_parser.add_mutually_exclusive_group(required=True)
    clear_group.add_argument("--database", help="Target database name (use with --version)")
    clear_group.add_argument("--all", action="store_true", help="Clear all backfill checkpoints")
    clear_parser.add_argument("--version", type=int, help="Backfill version number (use with --database)")
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
