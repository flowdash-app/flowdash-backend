import click
from app.core.database import SessionLocal
from app.models.user import User
from app.models.quota import Quota
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

@click.group()
def cli():
    """FlowDash CLI commands"""
    pass

@cli.command()
@click.option('--email', required=False, help='User email')
@click.option('--id', 'user_id', required=False, help='User id (Firebase UID)')
@click.option('--set', 'set_tester', is_flag=True, help='Set tester status')
@click.option('--remove', 'remove_tester', is_flag=True, help='Remove tester status')
@click.option('--list', 'list_testers', is_flag=True, help='List all testers')
def tester(email, user_id, set_tester, remove_tester, list_testers):
    """Manage tester status for users"""
    db = SessionLocal()
    try:
        if list_testers:
            testers = db.query(User).filter(User.is_tester == True).all()
            if not testers:
                click.echo("No testers found")
            else:
                click.echo(f"\nFound {len(testers)} testers:\n")
                for user in testers:
                    click.echo(f"  - {user.email or '<no-email>'} (ID: {user.id}, Plan: {user.plan_tier})")
            return

        if not email and not user_id:
            click.echo("❌ Please provide --email or --id for this operation", err=True)
            return

        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        else:
            user = db.query(User).filter(User.email == email).first()

        if not user:
            target = user_id or email
            click.echo(f"❌ User not found: {target}", err=True)
            return

        display_ident = user.email or user.id
        if set_tester:
            if user.is_tester:
                click.echo(f"✓ User {display_ident} is already a tester")
            else:
                tester_count = db.query(User).filter(User.is_tester == True).count()
                if tester_count >= 100:
                    click.echo(f"❌ Tester limit reached (100)", err=True)
                    return
                user.is_tester = True
                db.commit()
                click.echo(f"✓ Set tester status for {display_ident}")
        elif remove_tester:
            if not user.is_tester:
                click.echo(f"✓ User {display_ident} is not a tester")
            else:
                user.is_tester = False
                db.commit()
                click.echo(f"✓ Removed tester status for {display_ident}")
        else:
            status = "tester" if user.is_tester else "not a tester"
            click.echo(f"User {display_ident} is {status}")
    except Exception as e:
        db.rollback()
        logger.error(f"CLI error: {e}")
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()

@cli.command()
@click.option('--email', required=False, help='User email')
@click.option('--id', 'user_id', required=False, help='User id (Firebase UID)')
@click.option('--quota-type', 'quota_type', required=False, help='Quota type to reset (toggles, refreshes, error_views)')
@click.option('--date', 'quota_date', required=False, help='Quota date (YYYY-MM-DD). Defaults to today')
@click.option('-y', '--yes', 'confirm', is_flag=True, help='Skip confirmation')
@click.option('--dry-run', 'dry_run', is_flag=True, help='Show what would be changed without committing')
def reset_quota(email, user_id, quota_type, quota_date, confirm, dry_run):
    """Reset quota counts for a user (set counts to 0)"""
    db = SessionLocal()
    try:
        if not email and not user_id:
            click.echo("❌ Please provide --email or --id for this operation", err=True)
            return

        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        else:
            user = db.query(User).filter(User.email == email).first()

        if not user:
            target = user_id or email
            click.echo(f"❌ User not found: {target}", err=True)
            return

        target_date = None
        if quota_date:
            try:
                target_date = datetime.strptime(quota_date, "%Y-%m-%d").date()
            except Exception:
                click.echo("❌ Invalid date format. Use YYYY-MM-DD", err=True)
                return

        display_ident = user.email or user.id
        action_desc = f"Reset quotas for {display_ident}"
        if quota_type:
            action_desc += f" (type: {quota_type})"
        if target_date:
            action_desc += f" on {target_date.isoformat()}"
        else:
            action_desc += f" on {date.today().isoformat()}"

        if dry_run:
            click.echo(f"🔍 Dry run: would {action_desc}")
            today = target_date or date.today()
            query = db.query(Quota).filter(Quota.user_id == user.id, Quota.quota_date == today)
            if quota_type:
                query = query.filter(Quota.quota_type == quota_type)
            rows = query.all()
            if not rows:
                click.echo("No quota rows would be affected")
            else:
                click.echo(f"Found {len(rows)} quota rows that would be reset:")
                for r in rows:
                    click.echo(f"  - type: {r.quota_type}, count: {r.count}, date: {r.quota_date}")
            return

        if not confirm:
            try:
                if not click.confirm(f"Are you sure you want to {action_desc}?", default=False):
                    click.echo("Aborted")
                    return
            except click.exceptions.Abort:
                click.echo("\nAborted")
                return
            except Exception:
                click.echo("❌ Non-interactive mode detected. Use -y or --yes to skip confirmation.", err=True)
                return

        # Perform reset directly (avoid QuotaService to skip Firebase init)
        from sqlalchemy import and_
        reset_date = target_date or date.today()
        query = db.query(Quota).filter(
            and_(
                Quota.user_id == user.id,
                Quota.quota_date == reset_date
            )
        )
        if quota_type:
            query = query.filter(Quota.quota_type == quota_type)
        rows = query.update({"count": 0})
        db.commit()
        click.echo(f"✓ Reset {rows} quota rows for {display_ident}")
    except Exception as e:
        db.rollback()
        logger.error(f"CLI error: {e}")
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()

if __name__ == '__main__':
    cli()
