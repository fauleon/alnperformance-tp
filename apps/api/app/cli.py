"""Operations CLI.

python -m app.cli bootstrap --email you@x.com --name "Nome" --org "ALN Performance" --workspace "Cliente"
python -m app.cli rotate-keys      # re-encrypt tokens with the first key of TOKEN_ENCRYPTION_KEYS
python -m app.cli generate-key     # prints a new Fernet key
"""

import argparse
import asyncio
import getpass
import sys
from decimal import Decimal

from cryptography.fernet import Fernet
from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import AdConnection, Membership, OAuthState, Organization, User, Workspace
from .security import hash_password, password_problem, rotate


async def bootstrap(email: str, name: str, org_name: str, workspace_name: str, password: str) -> None:
    async with SessionLocal() as session:
        email = email.lower()
        user = await session.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, name=name, password_hash=hash_password(password))
            session.add(user)
        org = await session.scalar(select(Organization).where(Organization.name == org_name))
        if not org:
            org = Organization(name=org_name)
            session.add(org)
        await session.flush()
        if not await session.scalar(
            select(Membership).where(Membership.user_id == user.id, Membership.organization_id == org.id)
        ):
            session.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
        if not await session.scalar(
            select(Workspace).where(Workspace.organization_id == org.id, Workspace.name == workspace_name)
        ):
            session.add(
                Workspace(
                    organization_id=org.id,
                    name=workspace_name,
                    daily_budget_limit=Decimal(settings.default_daily_budget_limit),
                )
            )
        await session.commit()
        print(f'Pronto: {email} é proprietário de "{org_name}" (cliente "{workspace_name}").')


async def rotate_keys() -> None:
    async with SessionLocal() as session:
        count = 0
        for connection in await session.scalars(select(AdConnection)):
            connection.encrypted_access_token = rotate(connection.encrypted_access_token)
            connection.encrypted_refresh_token = rotate(connection.encrypted_refresh_token)
            count += 1
        for state in await session.scalars(select(OAuthState).where(OAuthState.used_at.is_(None))):
            state.encrypted_code_verifier = rotate(state.encrypted_code_verifier)
        await session.commit()
        print(f"{count} conexões recifradas com a chave mais nova.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("bootstrap", help="cria o primeiro proprietário, organização e cliente")
    boot.add_argument("--email", required=True)
    boot.add_argument("--name", required=True)
    boot.add_argument("--org", required=True)
    boot.add_argument("--workspace", required=True)
    sub.add_parser("rotate-keys")
    sub.add_parser("generate-key")
    args = parser.parse_args()
    if args.command == "generate-key":
        print(Fernet.generate_key().decode())
    elif args.command == "rotate-keys":
        asyncio.run(rotate_keys())
    else:
        password = getpass.getpass("Senha do proprietário: ")
        if problem := password_problem(password):
            sys.exit(problem)
        asyncio.run(bootstrap(args.email, args.name, args.org, args.workspace, password))


if __name__ == "__main__":
    main()
