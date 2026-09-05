# Database

This folder now holds the Alembic migration environment for the PostgreSQL-backed research store.

The application uses:

- PostgreSQL for persistence
- SQLAlchemy for the ORM/session layer
- Alembic for schema migrations

Configuration

- Copy `backend/.env.example` to `backend/.env` or set the same environment variables in your shell.
- Set `DATABASE_URL` to a PostgreSQL connection string, for example:

  `postgresql+psycopg://postgres:postgres@localhost:5432/researchpilot`

- `SQLALCHEMY_ECHO=false` is optional and controls SQL logging.

Run migrations from the repository root with:

`alembic -c database/migrations/alembic.ini upgrade head`

To create new migrations later, keep them in `database/migrations/versions/`.
