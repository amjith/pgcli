from pgcli.pgexecute import _parse_dsn
from utils import *

def test__parse_dsn():
    test_cases = [
            # Full dsn with all components.
            ('postgres://user:password@host:5432/dbname',
                ('dbname', 'user', 'password', 'host', '5432')),

            # dsn without password.
            ('postgres://user@host:5432/dbname',
                ('dbname', 'user', 'fpasswd', 'host', '5432')),

            # dsn without user or password.
            ('postgres://localhost:5432/dbname',
                ('dbname', 'fuser', 'fpasswd', 'localhost', '5432')),

            # dsn without port.
            ('postgres://user:password@host/dbname',
                ('dbname', 'user', 'password', 'host', '1234')),

            # dsn without password and port.
            ('postgres://user@host/dbname',
                ('dbname', 'user', 'fpasswd', 'host', '1234')),

            # dsn without user, password, port.
            ('postgres://localhost/dbname',
                ('dbname', 'fuser', 'fpasswd', 'localhost', '1234')),

            # dsn without user, password, port or host.
            ('postgres:///dbname',
                ('dbname', 'fuser', 'fpasswd', 'fhost', '1234')),

            # Full dsn with all components but with postgresql:// prefix.
            ('postgresql://user:password@host:5432/dbname',
                ('dbname', 'user', 'password', 'host', '5432'))
            ]

    for dsn, expected in test_cases:
        assert _parse_dsn(dsn, 'fuser', 'fpasswd', 'fhost', '1234') == expected

@dbtest
def test_conn(cursor, executor):
    data = executor.run('''create table test(id integer)''')
    assert not data