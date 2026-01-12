#!/usr/bin/env python3
"""
Generate a bcrypt password hash for the admin password.
Usage: python scripts/hash_password.py <password>
"""

import sys
from passlib.hash import bcrypt


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/hash_password.py <password>")
        sys.exit(1)
    
    password = sys.argv[1]
    hashed = bcrypt.hash(password)
    
    print("\nAdd this to your .env file:\n")
    print(f"ADMIN_PASSWORD_HASH={hashed}")
    print()


if __name__ == "__main__":
    main()
