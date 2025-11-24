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
@click.option('--email', required=True, help='User email')
@click.option('--set', 'set_tester', is_flag=True, help='Set tester status')
@click.option('--remove', 'remove_tester', is_flag=True, help='Remove tester status')
@click.option('--list', 'list_testers', is_flag=True, help='List all testers')
def tester(email, set_tester, remove_tester, list_testers):
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
                    click.echo(f"  - {user.email} (ID: {user.id}, Plan: {user.plan_tier})")
            return
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            click.echo(f"❌ User not found: {email}", err=True)
            return
        
        if set_tester:
            if user.is_tester:
                click.echo(f"✓ User {email} is already a tester")
            else:
                tester_count = db.query(User).filter(User.is_tester == True).count()
                if tester_count >= 100:
                    click.echo(f"❌ Tester limit reached (100)", err=True)
                    return
                user.is_tester = True
                db.commit()
                click.echo(f"✓ Set tester status for {email}")
        elif remove_tester:
            if not user.is_tester:
                click.echo(f"✓ User {email} is not a tester")
            else:
                user.is_tester = False
                db.commit()
                click.echo(f"✓ Removed tester status for {email}")
        else:
            status = "tester" if user.is_tester else "not a tester"
            click.echo(f"User {email} is {status}")
    except Exception as e:
        db.rollback()
        logger.error(f"CLI error: {e}")
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()

if __name__ == '__main__':
    cli()

