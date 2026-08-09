#!/usr/bin/env python3
"""Seed development users script.

This script creates test users for development and testing purposes.
Run this once to set up initial users.

Usage:
    python scripts/seed_dev_users.py

Environment variables required:
    - DATABASE_URL (defaults to sqlite:///./data/app.db)
    - JWT_SECRET (required for the app to start)
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.core.security import get_password_hash
from src.database import create_tables, get_async_session_maker
from src.database.models import User


async def seed_users(
    member_email: str = "member@test.com",
    member_password: str = "testpass123",
    admin_email: str = "admin@test.com",
    admin_password: str = "adminpass123",
    force: bool = False,
) -> None:
    """Create test users if they don't exist.

    Args:
        member_email: Email for member user
        member_password: Password for member user
        admin_email: Email for admin user
        admin_password: Password for admin user
        force: If True, update existing users
    """
    # Create tables first
    await create_tables()

    session_maker = get_async_session_maker()
    async with session_maker() as session:
        users_to_create = [
            {"email": member_email, "password": member_password, "role": "member"},
            {"email": admin_email, "password": admin_password, "role": "admin"},
        ]

        for user_data in users_to_create:
            # Check if user exists
            result = await session.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                if force:
                    # Update password
                    existing_user.password_hash = get_password_hash(user_data["password"])
                    existing_user.role = user_data["role"]
                    print(f"Updated {user_data['role']}: {user_data['email']}")
                else:
                    print(f"User already exists: {user_data['email']} (use --force to update)")
                continue

            # Create new user
            new_user = User(
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                role=user_data["role"],
                preferred_language="en",
            )
            session.add(new_user)
            print(f"Created {user_data['role']}: {user_data['email']}")

        await session.commit()

    print("\nTest users seeded successfully!")
    print(f"  Member: {member_email} / {member_password}")
    print(f"  Admin:  {admin_email} / {admin_password}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed development test users"
    )
    parser.add_argument(
        "--member-email",
        default="member@test.com",
        help="Email for member user (default: member@test.com)",
    )
    parser.add_argument(
        "--member-password",
        default="testpass123",
        help="Password for member user (default: testpass123)",
    )
    parser.add_argument(
        "--admin-email",
        default="admin@test.com",
        help="Email for admin user (default: admin@test.com)",
    )
    parser.add_argument(
        "--admin-password",
        default="adminpass123",
        help="Password for admin user (default: adminpass123)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update existing users",
    )

    args = parser.parse_args()

    asyncio.run(
        seed_users(
            member_email=args.member_email,
            member_password=args.member_password,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
            force=args.force,
        )
    )


if __name__ == "__main__":
    main()
