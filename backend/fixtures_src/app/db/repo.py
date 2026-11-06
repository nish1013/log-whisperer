from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String, unique=True, nullable=False),
)


def create_user(conn, username):
    conn.execute(insert(users).values(username=username))


def register_twice():
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as conn:
        create_user(conn, "ana")
        create_user(conn, "ana")
