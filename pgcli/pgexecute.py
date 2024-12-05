import ipaddress
import logging
import traceback
from collections import namedtuple
import re
import pgspecial as special
import psycopg
import psycopg.sql
from psycopg.conninfo import make_conninfo
import sqlparse

from .packages.parseutils.meta import FunctionMetadata, ForeignKey

_logger = logging.getLogger(__name__)

ViewDef = namedtuple(
    "ViewDef", "nspname relname relkind viewdef reloptions checkoption"
)


# we added this funcion to strip beginning comments
# because sqlparse didn't handle tem well.  It won't be needed if sqlparse
# does parsing of this situation better


def remove_beginning_comments(command):
    # Regular expression pattern to match comments
    pattern = r"^(/\*.*?\*/|--.*?)(?:\n|$)"

    # Find and remove all comments from the beginning
    cleaned_command = command
    comments = []
    match = re.match(pattern, cleaned_command, re.DOTALL)
    while match:
        comments.append(match.group())
        cleaned_command = cleaned_command[len(match.group()) :].lstrip()
        match = re.match(pattern, cleaned_command, re.DOTALL)

    return [cleaned_command, comments]


def register_typecasters(connection):
    """Casts date and timestamp values to string, resolves issues with out-of-range
    dates (e.g. BC) which psycopg can't handle"""
    for forced_text_type in [
        "date",
        "time",
        "timestamp",
        "timestamptz",
        "bytea",
        "json",
        "jsonb",
    ]:
        connection.adapters.register_loader(
            forced_text_type, psycopg.types.string.TextLoader
        )


# pg3: I don't know what is this
class ProtocolSafeCursor(psycopg.Cursor):
    """This class wraps and suppresses Protocol Errors with pgbouncer database.
    See https://github.com/dbcli/pgcli/pull/1097.
    Pgbouncer database is a virtual database with its own set of commands."""

    def __init__(self, *args, **kwargs):
        self.protocol_error = False
        self.protocol_message = ""
        super().__init__(*args, **kwargs)

    def __iter__(self):
        if self.protocol_error:
            raise StopIteration
        return super().__iter__()

    def fetchall(self):
        if self.protocol_error:
            return [(self.protocol_message,)]
        return super().fetchall()

    def fetchone(self):
        if self.protocol_error:
            return (self.protocol_message,)
        return super().fetchone()

    # def mogrify(self, query, params):
    #     args = [Literal(v).as_string(self.connection) for v in params]
    #     return query % tuple(args)
    #
    def execute(self, *args, **kwargs):
        try:
            super().execute(*args, **kwargs)
            self.protocol_error = False
            self.protocol_message = ""
        except psycopg.errors.ProtocolViolation as ex:
            self.protocol_error = True
            self.protocol_message = str(ex)
            _logger.debug("%s: %s" % (ex.__class__.__name__, ex))


class PGExecute:
    # The boolean argument to the current_schemas function indicates whether
    # implicit schemas, e.g. pg_catalog
    search_path_query = """
        SELECT * FROM unnest(current_schemas(true))"""

    schemata_query = """
        SELECT  nspname
        FROM    pg_catalog.pg_namespace
        ORDER BY 1 """

    tables_query = """
        SELECT  n.nspname schema_name,
                c.relname table_name
        FROM    pg_catalog.pg_class c
                LEFT JOIN pg_catalog.pg_namespace n
                    ON n.oid = c.relnamespace
        WHERE   c.relkind = ANY(%s)
        ORDER BY 1,2;"""

    databases_query = """
        SELECT d.datname
        FROM pg_catalog.pg_database d
        ORDER BY 1"""

    full_databases_query = """
        SELECT d.datname as "Name",
            pg_catalog.pg_get_userbyid(d.datdba) as "Owner",
            pg_catalog.pg_encoding_to_char(d.encoding) as "Encoding",
            d.datcollate as "Collate",
            d.datctype as "Ctype",
            pg_catalog.array_to_string(d.datacl, E'\n') AS "Access privileges"
        FROM pg_catalog.pg_database d
        ORDER BY 1"""

    socket_directory_query = """
        SELECT setting
        FROM pg_settings
        WHERE name = 'unix_socket_directories'
    """

    view_definition_query = """
        WITH v AS (SELECT %s::pg_catalog.regclass::pg_catalog.oid AS v_oid)
        SELECT nspname, relname, relkind,
               pg_catalog.pg_get_viewdef(c.oid, true),
               array_remove(array_remove(c.reloptions,'check_option=local'),
                            'check_option=cascaded') AS reloptions,
               CASE
                 WHEN 'check_option=local' = ANY (c.reloptions) THEN 'LOCAL'::text
                 WHEN 'check_option=cascaded' = ANY (c.reloptions) THEN 'CASCADED'::text
                 ELSE NULL
               END AS checkoption
        FROM pg_catalog.pg_class c
        LEFT JOIN pg_catalog.pg_namespace n ON (c.relnamespace = n.oid)
        JOIN v ON (c.oid = v.v_oid)"""

    function_definition_query = """
        WITH f AS
            (SELECT %s::pg_catalog.regproc::pg_catalog.oid AS f_oid)
        SELECT pg_catalog.pg_get_functiondef(f.f_oid)
        FROM f"""

    def __init__(
        self,
        database=None,
        user=None,
        password=None,
        host=None,
        port=None,
        dsn=None,
        notify_callback=None,
        **kwargs,
    ):
        self._conn_params = {}
        self._is_virtual_database = None
        self.conn = None
        self.dbname = None
        self.user = None
        self.password = None
        self.host = None
        self.port = None
        self.server_version = None
        self.extra_args = None
        self.notify_callback = notify_callback
        self.connect(database, user, password, host, port, dsn, **kwargs)
        self.reset_expanded = None

    def is_virtual_database(self):
        if self._is_virtual_database is None:
            self._is_virtual_database = self.is_protocol_error()
        return self._is_virtual_database

    def copy(self):
        """Returns a clone of the current executor."""
        return self.__class__(**self._conn_params)

    def connect(
        self,
        database=None,
        user=None,
        password=None,
        host=None,
        port=None,
        dsn=None,
        **kwargs,
    ):
        conn_params = self._conn_params.copy()

        new_params = {
            "dbname": database,
            "user": user,
            "password": password,
            "host": host,
            "port": port,
            "dsn": dsn,
        }
        new_params.update(kwargs)

        if new_params["dsn"]:
            new_params = {"dsn": new_params["dsn"], "password": new_params["password"]}

            if new_params["password"]:
                new_params["dsn"] = make_conninfo(
                    new_params["dsn"], password=new_params.pop("password")
                )

        conn_params.update({k: v for k, v in new_params.items() if v})

        if "dsn" in conn_params:
            other_params = {k: v for k, v in conn_params.items() if k != "dsn"}
            conn_info = make_conninfo(conn_params["dsn"], **other_params)
        else:
            conn_info = make_conninfo(**conn_params)
        conn = psycopg.connect(conn_info)
        conn.cursor_factory = ProtocolSafeCursor

        self._conn_params = conn_params
        if self.conn:
            self.conn.close()
        self.conn = conn
        self.conn.autocommit = True

        if self.notify_callback is not None:
            self.conn.add_notify_handler(self.notify_callback)

        # When we connect using a DSN, we don't really know what db,
        # user, etc. we connected to. Let's read it.
        # Note: moved this after setting autocommit because of #664.
        dsn_parameters = conn.info.get_parameters()

        if dsn_parameters:
            self.dbname = dsn_parameters.get("dbname")
            self.user = dsn_parameters.get("user")
            self.host = dsn_parameters.get("host")
            self.port = dsn_parameters.get("port")
        else:
            self.dbname = conn_params.get("database")
            self.user = conn_params.get("user")
            self.host = conn_params.get("host")
            self.port = conn_params.get("port")

        self.password = password
        self.extra_args = kwargs

        if not self.host:
            self.host = (
                "pgbouncer"
                if self.is_virtual_database()
                else self.get_socket_directory()
            )

        self.pid = conn.info.backend_pid
        self.superuser = conn.info.parameter_status("is_superuser") in ("on", "1")
        self.server_version = conn.info.parameter_status("server_version") or ""

        # _set_wait_callback(self.is_virtual_database())

        if not self.is_virtual_database():
            register_typecasters(conn)

    @property
    def short_host(self):
        try:
            ipaddress.ip_address(self.host)
            return self.host
        except ValueError:
            pass
        if "," in self.host:
            host, _, _ = self.host.partition(",")
        else:
            host = self.host
        short_host, _, _ = host.partition(".")
        return short_host

    def _select_one(self, cur, sql):
        """
        Helper method to run a select and retrieve a single field value
        :param cur: cursor
        :param sql: string
        :return: string
        """
        cur.execute(sql)
        return cur.fetchone()

    def failed_transaction(self):
        return self.conn.info.transaction_status == psycopg.pq.TransactionStatus.INERROR

    def valid_transaction(self):
        status = self.conn.info.transaction_status
        return (
            status == psycopg.pq.TransactionStatus.ACTIVE
            or status == psycopg.pq.TransactionStatus.INTRANS
        )

    def run(
        self,
        statement,
        pgspecial=None,
        exception_formatter=None,
        on_error_resume=False,
        explain_mode=False,
    ):
        """Execute the sql in the database and return the results.

        :param statement: A string containing one or more sql statements
        :param pgspecial: PGSpecial object
        :param exception_formatter: A callable that accepts an Exception and
               returns a formatted (title, rows, headers, status) tuple that can
               act as a query result. If an exception_formatter is not supplied,
               psycopg2 exceptions are always raised.
        :param on_error_resume: Bool. If true, queries following an exception
               (assuming exception_formatter has been supplied) continue to
               execute.

        :return: Generator yielding tuples containing
                 (title, rows, headers, status, query, success, is_special)
        """

        # Remove spaces and EOL
        statement = statement.strip()
        if not statement:  # Empty string
            yield None, None, None, None, statement, False, False

        # sql parse doesn't split on a comment first + special
        # so we're going to do it

        removed_comments = []
        sqlarr = []
        cleaned_command = ""

        # could skip if statement doesn't match ^-- or ^/*
        cleaned_command, removed_comments = remove_beginning_comments(statement)

        sqlarr = sqlparse.split(cleaned_command)

        # now re-add the beginning comments if there are any, so that they show up in
        # log files etc when running these commands

        if len(removed_comments) > 0:
            sqlarr = removed_comments + sqlarr

        # run each sql query
        for sql in sqlarr:
            # Remove spaces, eol and semi-colons.
            sql = sql.rstrip(";")
            sql = sqlparse.format(sql, strip_comments=False).strip()
            if not sql:
                continue
            try:
                if explain_mode:
                    sql = self.explain_prefix() + sql
                elif pgspecial:
                    # \G is treated specially since we have to set the expanded output.
                    if sql.endswith("\\G"):
                        if not pgspecial.expanded_output:
                            pgspecial.expanded_output = True
                            self.reset_expanded = True
                        sql = sql[:-2].strip()

                    # First try to run each query as special
                    _logger.debug("Trying a pgspecial command. sql: %r", sql)
                    try:
                        cur = self.conn.cursor()
                    except psycopg.InterfaceError:
                        # edge case when connection is already closed, but we
                        # don't need cursor for special_cmd.arg_type == NO_QUERY.
                        # See https://github.com/dbcli/pgcli/issues/1014.
                        cur = None
                    try:
                        response = pgspecial.execute(cur, sql)
                        if cur and cur.protocol_error:
                            yield None, None, None, cur.protocol_message, statement, False, False
                            # this would close connection. We should reconnect.
                            self.connect()
                            continue
                        for result in response:
                            # e.g. execute_from_file already appends these
                            if len(result) < 7:
                                yield result + (sql, True, True)
                            else:
                                yield result
                        continue
                    except special.CommandNotFound:
                        pass

                # Not a special command, so execute as normal sql
                yield self.execute_normal_sql(sql) + (sql, True, False)
            except psycopg.DatabaseError as e:
                _logger.error("sql: %r, error: %r", sql, e)
                _logger.error("traceback: %r", traceback.format_exc())

                if self._must_raise(e) or not exception_formatter:
                    raise

                yield None, None, None, exception_formatter(e), sql, False, False

                if not on_error_resume:
                    break
            finally:
                if self.reset_expanded:
                    pgspecial.expanded_output = False
                    self.reset_expanded = None

    def _must_raise(self, e):
        """Return true if e is an error that should not be caught in ``run``.

        An uncaught error will prompt the user to reconnect; as long as we
        detect that the connection is still open, we catch the error, as
        reconnecting won't solve that problem.

        :param e: DatabaseError. An exception raised while executing a query.

        :return: Bool. True if ``run`` must raise this exception.

        """
        return self.conn.closed != 0

    def execute_normal_sql(self, split_sql):
        """Returns tuple (title, rows, headers, status)"""
        _logger.debug("Regular sql statement. sql: %r", split_sql)

        title = ""

        def handle_notices(n):
            nonlocal title
            title = f"{title}"
            if n.message_primary is not None:
                title = f"{title}\n{n.message_primary}"
            if n.message_detail is not None:
                title = f"{title}\n{n.message_detail}"

        self.conn.add_notice_handler(handle_notices)

        if self.is_virtual_database() and "show help" in split_sql.lower():
            # see https://github.com/psycopg/psycopg/issues/303
            # special case "show help" in pgbouncer
            res = self.conn.pgconn.exec_(split_sql.encode())
            return title, None, None, res.command_status.decode()

        cur = self.conn.cursor()
        cur.execute(split_sql)

        # cur.description will be None for operations that do not return
        # rows.
        if cur.description:
            headers = [x[0] for x in cur.description]
            return title, cur, headers, cur.statusmessage
        elif cur.protocol_error:
            _logger.debug("Protocol error, unsupported command.")
            return title, None, None, cur.protocol_message
        else:
            _logger.debug("No rows in result.")
            return title, None, None, cur.statusmessage

    def search_path(self):
        """Returns the current search path as a list of schema names"""

        try:
            with self.conn.cursor() as cur:
                _logger.debug("Search path query. sql: %r", self.search_path_query)
                cur.execute(self.search_path_query)
                return [x[0] for x in cur.fetchall()]
        except psycopg.ProgrammingError:
            fallback = "SELECT * FROM current_schemas(true)"
            with self.conn.cursor() as cur:
                _logger.debug("Search path query. sql: %r", fallback)
                cur.execute(fallback)
                return cur.fetchone()[0]

    def view_definition(self, spec):
        """Returns the SQL defining views described by `spec`"""

        # 2: relkind, v or m (materialized)
        # 4: reloptions, null
        # 5: checkoption: local or cascaded
        with self.conn.cursor() as cur:
            sql = self.view_definition_query
            _logger.debug("View Definition Query. sql: %r\nspec: %r", sql, spec)
            try:
                cur.execute(sql, (spec,))
            except psycopg.ProgrammingError:
                raise RuntimeError(f"View {spec} does not exist.")
            result = ViewDef(*cur.fetchone())
            if result.relkind == "m":
                template = "CREATE OR REPLACE MATERIALIZED VIEW {name} AS \n{stmt}"
            else:
                template = "CREATE OR REPLACE VIEW {name} AS \n{stmt}"
            return (
                psycopg.sql.SQL(template)
                .format(
                    name=psycopg.sql.Identifier(result.nspname, result.relname),
                    stmt=psycopg.sql.SQL(result.viewdef),
                )
                .as_string(self.conn)
            )

    def function_definition(self, spec):
        """Returns the SQL defining functions described by `spec`"""

        with self.conn.cursor() as cur:
            sql = self.function_definition_query
            _logger.debug("Function Definition Query. sql: %r\nspec: %r", sql, spec)
            try:
                cur.execute(sql, (spec,))
                result = cur.fetchone()
                return result[0]
            except psycopg.ProgrammingError:
                raise RuntimeError(f"Function {spec} does not exist.")

    def schemata(self):
        """Returns a list of schema names in the database"""

        with self.conn.cursor() as cur:
            _logger.debug("Schemata Query. sql: %r", self.schemata_query)
            cur.execute(self.schemata_query)
            return [x[0] for x in cur.fetchall()]

    def _relations(self, kinds=("r", "p", "f", "v", "m")):
        """Get table or view name metadata

        :param kinds: list of postgres relkind filters:
                'r' - table
                'p' - partitioned table
                'f' - foreign table
                'v' - view
                'm' - materialized view
        :return: (schema_name, rel_name) tuples
        """

        with self.conn.cursor() as cur:
            # sql = cur.mogrify(self.tables_query, kinds)
            # _logger.debug("Tables Query. sql: %r", sql)
            cur.execute(self.tables_query, [kinds])
            yield from cur

    def tables(self):
        """Yields (schema_name, table_name) tuples"""
        yield from self._relations(kinds=["r", "p", "f"])

    def views(self):
        """Yields (schema_name, view_name) tuples.

        Includes both views and and materialized views
        """
        yield from self._relations(kinds=["v", "m"])

    def _columns(self, kinds=("r", "p", "f", "v", "m")):
        """Get column metadata for tables and views

        :param kinds: kinds: list of postgres relkind filters:
                'r' - table
                'p' - partitioned table
                'f' - foreign table
                'v' - view
                'm' - materialized view
        :return: list of (schema_name, relation_name, column_name, column_type) tuples
        """

        if self.conn.info.server_version >= 80400:
            columns_query = """
                SELECT  nsp.nspname schema_name,
                        cls.relname table_name,
                        att.attname column_name,
                        att.atttypid::regtype::text type_name,
                        att.atthasdef AS has_default,
                        pg_catalog.pg_get_expr(def.adbin, def.adrelid, true) as default
                FROM    pg_catalog.pg_attribute att
                        INNER JOIN pg_catalog.pg_class cls
                            ON att.attrelid = cls.oid
                        INNER JOIN pg_catalog.pg_namespace nsp
                            ON cls.relnamespace = nsp.oid
                        LEFT OUTER JOIN pg_attrdef def
                            ON def.adrelid = att.attrelid
                            AND def.adnum = att.attnum
                WHERE   cls.relkind = ANY(%s)
                        AND NOT att.attisdropped
                        AND att.attnum  > 0
                ORDER BY 1, 2, att.attnum"""
        else:
            columns_query = """
                SELECT  nsp.nspname schema_name,
                        cls.relname table_name,
                        att.attname column_name,
                        typ.typname type_name,
                        NULL AS has_default,
                        NULL AS default
                FROM    pg_catalog.pg_attribute att
                        INNER JOIN pg_catalog.pg_class cls
                            ON att.attrelid = cls.oid
                        INNER JOIN pg_catalog.pg_namespace nsp
                            ON cls.relnamespace = nsp.oid
                        INNER JOIN pg_catalog.pg_type typ
                            ON typ.oid = att.atttypid
                WHERE   cls.relkind = ANY(%s)
                        AND NOT att.attisdropped
                        AND att.attnum  > 0
                ORDER BY 1, 2, att.attnum"""

        with self.conn.cursor() as cur:
            # sql = cur.mogrify(columns_query, kinds)
            # _logger.debug("Columns Query. sql: %r", sql)
            cur.execute(columns_query, [kinds])
            yield from cur

    def table_columns(self):
        yield from self._columns(kinds=["r", "p", "f"])

    def view_columns(self):
        yield from self._columns(kinds=["v", "m"])

    def databases(self):
        with self.conn.cursor() as cur:
            _logger.debug("Databases Query. sql: %r", self.databases_query)
            cur.execute(self.databases_query)
            return [x[0] for x in cur.fetchall()]

    def full_databases(self):
        with self.conn.cursor() as cur:
            _logger.debug("Databases Query. sql: %r", self.full_databases_query)
            cur.execute(self.full_databases_query)
            headers = [x[0] for x in cur.description]
            return cur.fetchall(), headers, cur.statusmessage

    def is_protocol_error(self):
        query = "SELECT 1"
        with self.conn.cursor() as cur:
            _logger.debug("Simple Query. sql: %r", query)
            cur.execute(query)
            return bool(cur.protocol_error)

    def get_socket_directory(self):
        with self.conn.cursor() as cur:
            _logger.debug(
                "Socket directory Query. sql: %r", self.socket_directory_query
            )
            cur.execute(self.socket_directory_query)
            result = cur.fetchone()
            return result[0] if result else ""

    def foreignkeys(self):
        """Yields ForeignKey named tuples"""

        if self.conn.info.server_version < 90000:
            return

        with self.conn.cursor() as cur:
            query = """
                SELECT s_p.nspname AS parentschema,
                       t_p.relname AS parenttable,
                       unnest((
                        select
                            array_agg(attname ORDER BY i)
                        from
                            (select unnest(confkey) as attnum, generate_subscripts(confkey, 1) as i) x
                            JOIN pg_catalog.pg_attribute c USING(attnum)
                            WHERE c.attrelid = fk.confrelid
                        )) AS parentcolumn,
                       s_c.nspname AS childschema,
                       t_c.relname AS childtable,
                       unnest((
                        select
                            array_agg(attname ORDER BY i)
                        from
                            (select unnest(conkey) as attnum, generate_subscripts(conkey, 1) as i) x
                            JOIN pg_catalog.pg_attribute c USING(attnum)
                            WHERE c.attrelid = fk.conrelid
                        )) AS childcolumn
                FROM pg_catalog.pg_constraint fk
                JOIN pg_catalog.pg_class      t_p ON t_p.oid = fk.confrelid
                JOIN pg_catalog.pg_namespace  s_p ON s_p.oid = t_p.relnamespace
                JOIN pg_catalog.pg_class      t_c ON t_c.oid = fk.conrelid
                JOIN pg_catalog.pg_namespace  s_c ON s_c.oid = t_c.relnamespace
                WHERE fk.contype = 'f';
                """
            _logger.debug("Functions Query. sql: %r", query)
            cur.execute(query)
            for row in cur:
                yield ForeignKey(*row)

    def functions(self):
        """Yields FunctionMetadata named tuples"""

        if self.conn.info.server_version >= 110000:
            query = """
                SELECT n.nspname schema_name,
                        p.proname func_name,
                        p.proargnames,
                        COALESCE(proallargtypes::regtype[], proargtypes::regtype[])::text[],
                        p.proargmodes,
                        prorettype::regtype::text return_type,
                        p.prokind = 'a' is_aggregate,
                        p.prokind = 'w' is_window,
                        p.proretset is_set_returning,
                        d.deptype = 'e' is_extension,
                        pg_get_expr(proargdefaults, 0) AS arg_defaults
                FROM pg_catalog.pg_proc p
                        INNER JOIN pg_catalog.pg_namespace n
                            ON n.oid = p.pronamespace
                LEFT JOIN pg_depend d ON d.objid = p.oid and d.deptype = 'e'
                WHERE p.prorettype::regtype != 'trigger'::regtype
                ORDER BY 1, 2
                """
        elif self.conn.info.server_version > 90000:
            query = """
                SELECT n.nspname schema_name,
                        p.proname func_name,
                        p.proargnames,
                        COALESCE(proallargtypes::regtype[], proargtypes::regtype[])::text[],
                        p.proargmodes,
                        prorettype::regtype::text return_type,
                        p.proisagg is_aggregate,
                        p.proiswindow is_window,
                        p.proretset is_set_returning,
                        d.deptype = 'e' is_extension,
                        pg_get_expr(proargdefaults, 0) AS arg_defaults
                FROM pg_catalog.pg_proc p
                        INNER JOIN pg_catalog.pg_namespace n
                            ON n.oid = p.pronamespace
                LEFT JOIN pg_depend d ON d.objid = p.oid and d.deptype = 'e'
                WHERE p.prorettype::regtype != 'trigger'::regtype
                ORDER BY 1, 2
                """
        elif self.conn.info.server_version >= 80400:
            query = """
                SELECT n.nspname schema_name,
                        p.proname func_name,
                        p.proargnames,
                        COALESCE(proallargtypes::regtype[], proargtypes::regtype[])::text[],
                        p.proargmodes,
                        prorettype::regtype::text,
                        p.proisagg is_aggregate,
                        false is_window,
                        p.proretset is_set_returning,
                        d.deptype = 'e' is_extension,
                        NULL AS arg_defaults
                FROM pg_catalog.pg_proc p
                        INNER JOIN pg_catalog.pg_namespace n
                            ON n.oid = p.pronamespace
                LEFT JOIN pg_depend d ON d.objid = p.oid and d.deptype = 'e'
                WHERE p.prorettype::regtype != 'trigger'::regtype
                ORDER BY 1, 2
                """
        else:
            query = """
                SELECT n.nspname schema_name,
                        p.proname func_name,
                        p.proargnames,
                        NULL arg_types,
                        NULL arg_modes,
                        '' ret_type,
                        p.proisagg is_aggregate,
                        false is_window,
                        p.proretset is_set_returning,
                        d.deptype = 'e' is_extension,
                        NULL AS arg_defaults
                FROM pg_catalog.pg_proc p
                        INNER JOIN pg_catalog.pg_namespace n
                            ON n.oid = p.pronamespace
                LEFT JOIN pg_depend d ON d.objid = p.oid and d.deptype = 'e'
                WHERE p.prorettype::regtype != 'trigger'::regtype
                ORDER BY 1, 2
                """

        with self.conn.cursor() as cur:
            _logger.debug("Functions Query. sql: %r", query)
            cur.execute(query)
            for row in cur:
                yield FunctionMetadata(*row)

    def datatypes(self):
        """Yields tuples of (schema_name, type_name)"""

        with self.conn.cursor() as cur:
            if self.conn.info.server_version > 90000:
                query = """
                    SELECT n.nspname schema_name,
                           t.typname type_name
                    FROM   pg_catalog.pg_type t
                           INNER JOIN pg_catalog.pg_namespace n
                              ON n.oid = t.typnamespace
                    WHERE ( t.typrelid = 0  -- non-composite types
                            OR (  -- composite type, but not a table
                                  SELECT c.relkind = 'c'
                                  FROM pg_catalog.pg_class c
                                  WHERE c.oid = t.typrelid
                                )
                          )
                          AND NOT EXISTS( -- ignore array types
                                SELECT  1
                                FROM    pg_catalog.pg_type el
                                WHERE   el.oid = t.typelem AND el.typarray = t.oid
                              )
                          AND n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                    ORDER BY 1, 2;
                    """
            else:
                query = """
                    SELECT n.nspname schema_name,
                      pg_catalog.format_type(t.oid, NULL) type_name
                    FROM pg_catalog.pg_type t
                         LEFT JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                    WHERE (t.typrelid = 0 OR (SELECT c.relkind = 'c' FROM pg_catalog.pg_class c WHERE c.oid = t.typrelid))
                      AND t.typname !~ '^_'
                          AND n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                      AND pg_catalog.pg_type_is_visible(t.oid)
                    ORDER BY 1, 2;
                """
            _logger.debug("Datatypes Query. sql: %r", query)
            cur.execute(query)
            yield from cur

    def casing(self):
        """Yields the most common casing for names used in db functions"""
        with self.conn.cursor() as cur:
            query = r"""
          WITH Words AS (
                SELECT regexp_split_to_table(prosrc, '\W+') AS Word, COUNT(1)
                FROM pg_catalog.pg_proc P
                JOIN pg_catalog.pg_namespace N ON N.oid = P.pronamespace
                JOIN pg_catalog.pg_language L ON L.oid = P.prolang
                WHERE L.lanname IN ('sql', 'plpgsql')
                AND N.nspname NOT IN ('pg_catalog', 'information_schema')
                GROUP BY Word
            ),
            OrderWords AS (
                SELECT Word,
                    ROW_NUMBER() OVER(PARTITION BY LOWER(Word) ORDER BY Count DESC)
                FROM Words
                WHERE Word ~* '.*[a-z].*'
            ),
            Names AS (
                --Column names
                SELECT attname AS Name
                FROM pg_catalog.pg_attribute
                UNION -- Table/view names
                SELECT relname
                FROM pg_catalog.pg_class
                UNION -- Function names
                SELECT proname
                FROM pg_catalog.pg_proc
                UNION -- Type names
                SELECT typname
                FROM pg_catalog.pg_type
                UNION -- Schema names
                SELECT nspname
                FROM pg_catalog.pg_namespace
                UNION -- Parameter names
                SELECT unnest(proargnames)
                FROM pg_proc
            )
            SELECT Word
            FROM OrderWords
            WHERE LOWER(Word) IN (SELECT Name FROM Names)
            AND Row_Number = 1;
            """
            _logger.debug("Casing Query. sql: %r", query)
            cur.execute(query)
            for row in cur:
                yield row[0]

    def explain_prefix(self):
        return "EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) "

    def set_timezone(self, timezone: str):
        query = psycopg.sql.SQL("set time zone {}").format(
            psycopg.sql.Identifier(timezone)
        )
        with self.conn.cursor() as cur:
            cur.execute(query)
