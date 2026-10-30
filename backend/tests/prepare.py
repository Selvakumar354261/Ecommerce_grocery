"""Create only the dedicated test database, never touch the application DB."""
import os
import psycopg
url=os.environ['DATABASE_URL'].replace('postgresql+psycopg://','postgresql://')
assert url.rsplit('/',1)[1]=='grocery_test','Refusing to prepare a non-test database'
admin=url.rsplit('/',1)[0]+'/postgres'
with psycopg.connect(admin,autocommit=True) as connection:
    if not connection.execute("SELECT 1 FROM pg_database WHERE datname='grocery_test'").fetchone():
        connection.execute('CREATE DATABASE grocery_test')

