import os, sys
sys.path.append(os.getcwd())
from app.core.config import get_settings
import sqlalchemy as sa
s=get_settings()
print('DATABASE_URL=', s.database_url)
eng=sa.create_engine(s.database_url)
with eng.connect() as c:
    try:
        res=c.execute(sa.text("select * from alembic_version"))
        rows=res.fetchall()
        print('alembic_version rows:', rows)
    except Exception as e:
        print('alembic_version error:', repr(e))
    # list tables
    try:
        tables = c.execute(sa.text("select table_name from information_schema.tables where table_schema='public' order by table_name"))
        print('tables:')
        for r in tables.fetchall():
            print(' -', r[0])
    except Exception as e:
        print('tables error:', repr(e))
    # users columns
    try:
        cols = c.execute(sa.text("select column_name, data_type, is_nullable from information_schema.columns where table_schema='public' and table_name='users' order by ordinal_position"))
        rows=cols.fetchall()
        print('users columns:')
        for r in rows:
            print(' ', r)
    except Exception as e:
        print('users columns error:', repr(e))
    # auth_tokens exists?
    try:
        at = c.execute(sa.text("select column_name,data_type from information_schema.columns where table_schema='public' and table_name='auth_tokens' order by ordinal_position"))
        rows=at.fetchall()
        print('auth_tokens columns:')
        for r in rows:
            print(' ', r)
    except Exception as e:
        print('auth_tokens error:', repr(e))
