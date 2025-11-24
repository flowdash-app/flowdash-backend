import click
from app.core.database import SessionLocal
from app.models.user import User
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

        # Must provide either email or user_id for non-list operations
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

if __name__ == '__main__':
    cli()
