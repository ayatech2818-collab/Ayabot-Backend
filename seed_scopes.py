from app.db.session import SessionLocal
from app.services.scope_service import seed_default_scopes


def main():
    db = SessionLocal()

    try:
        scopes = seed_default_scopes(db)

        print(f"Created {len(scopes)} scopes:")

        for scope in scopes:
            print(f"- {scope.name}")

    finally:
        db.close()


if __name__ == "__main__":
    main()