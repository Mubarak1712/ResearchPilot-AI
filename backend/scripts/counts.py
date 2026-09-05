import os, sys
import sqlalchemy as sa
sys.path.append(os.getcwd())
from app.core.config import get_settings
s=get_settings()
eng=sa.create_engine(s.database_url)
with eng.connect() as c:
    u=c.execute(sa.text('select count(*) from users')).scalar()
    p=c.execute(sa.text('select count(*) from papers')).scalar()
    up=c.execute(sa.text('select count(*) from user_saved_papers')).scalar()
    print('counts:', u, p, up)
