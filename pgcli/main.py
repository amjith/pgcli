from zoneinfo import ZoneInfoNotFoundError
from configobj import ConfigObj, ParseError
from pgspecial.namedqueries import NamedQueries
from .config import skip_initial_comment

import atexit
import os
import re
import sys
import traceback
import logging
import threading
import shutil
import functools
import datetime as dt
import itertools
import pathlib
import platform
from time import time, sleep
from typing import Optional

from cli_helpers.tabular_output import TabularOutputFormatter
from cli_helpers.tabular_output.preprocessors import align_decimals, format_numbers
from cli_helpers.utils import strip_ansi
from .explain_output_formatter import ExplainOutputFormatter
import click
import tzlocal

try:
    import setproctitle
except ImportError:
    setproctitle = None
from prompt_toolkit.completion import DynamicCompleter, ThreadedCompleter
from prompt_toolkit.enums import DEFAULT_BUFFER, EditingMode
from prompt_toolkit.shortcuts import PromptSession, CompleteStyle
from prompt_toolkit.document import Document
from prompt_toolkit.filters import HasFocus, IsDone
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.layout.processors import (
    ConditionalProcessor,
    HighlightMatchingBracketProcessor,
    TabsProcessor,
)
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from pygments.lexers.sql import PostgresLexer

from pgspecial.main import PGSpecial, NO_QUERY, PAGER_OFF, PAGER_LONG_OUTPUT
import pgspecial as special

from . import auth
from .pgcompleter import PGCompleter
from .pgtoolbar import create_toolbar_tokens_func
from .pgstyle import style_factory, style_factory_output
from .pgexecute import PGExecute
from .completion_refresher import CompletionRefresher
from .config import (
    get_casing_file,
    load_config,
    config_location,
    ensure_dir_exists,
    get_config,
    get_config_filename,
)
from .key_bindings import pgcli_bindings
from .packages.formatter.sqlformatter import register_new_formatter
from .packages.prompt_utils import confirm, confirm_destructive_query
from .packages.parseutils import is_destructive
from .packages.parseutils import parse_destructive_warning
from .__init__ import __version__

click.disable_unicode_literals_warning = True

from urllib.parse import urlparse

from getpass import getuser

from psycopg import OperationalError, InterfaceError, Notify
from psycopg.conninfo import make_conninfo, conninfo_to_dict
from psycopg.errors import Diagnostic

from collections import namedtuple

try:
    import sshtunnel

    SSH_TUNNEL_SUPPORT = True
except ImportError:
    SSH_TUNNEL_SUPPORT = False


# Ref: https://stackoverflow.com/questions/30425105/filter-special-chars-such-as-color-codes-from-shell-output
COLOR_CODE_REGEX = re.compile(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))")
DEFAULT_MAX_FIELD_WIDTH = 500

# Query tuples are used for maintaining history
MetaQuery = namedtuple(
    "Query",
    [
        "query",  # The entire text of the command
        "successful",  # True If all subqueries were successful
        "total_time",  # Time elapsed executing the query and formatting results
        "execution_time",  # Time elapsed executing the query
        "meta_changed",  # True if any subquery executed create/alter/drop
        "db_changed",  # True if any subquery changed the database
        "path_changed",  # True if any subquery changed the search path
        "mutated",  # True if any subquery executed insert/update/delete
        "is_special",  # True if the query is a special command
    ],
)
MetaQuery.__new__.__defaults__ = ("", False, 0, 0, False, False, False, False)

OutputSettings = namedtuple(
    "OutputSettings",
    "table_format dcmlfmt floatfmt missingval expanded max_width case_function style_output max_field_width",
)
OutputSettings.__new__.__defaults__ = (
    None,
    None,
    None,
    "<null>",
    False,
    None,
    lambda x: x,
    None,
    DEFAULT_MAX_FIELD_WIDTH,
)


class PgCliQuitError(Exception):
    pass


def notify_callback(notify: Notify):
    click.secho(
        'Notification received on channel "{}" (PID {}):\n{}'.format(
            notify.channel, notify.pid, notify.payload
        ),
        fg="green",
    )


class PGCli:
    default_prompt = "\\u@\\h:\\d> "
    max_len_prompt = 30

    def set_default_pager(self, config):
        configured_pager = config["main"].get("pager")
        os_environ_pager = os.environ.get("PAGER")

        if configured_pager:
            self.logger.info(
                'Default pager found in config file: "%s"', configured_pager
            )
            os.environ["PAGER"] = configured_pager
        elif os_environ_pager:
            self.logger.info(
                'Default pager found in PAGER environment variable: "%s"',
                os_environ_pager,
            )
            os.environ["PAGER"] = os_environ_pager
        else:
            self.logger.info(
                "No default pager found in environment. Using os default pager"
            )

        # Set default set of less recommended options, if they are not already set.
        # They are ignored if pager is different than less.
        if not os.environ.get("LESS"):
            os.environ["LESS"] = "-SRXF"

    def __init__(
        self,
        force_passwd_prompt=False,
        never_passwd_prompt=False,
        pgexecute=None,
        pgclirc_file=None,
        row_limit=None,
        application_name="pgcli",
        single_connection=False,
        less_chatty=None,
        prompt=None,
        prompt_dsn=None,
        auto_vertical_output=False,
        warn=None,
        ssh_tunnel_url: Optional[str] = None,
        log_file: Optional[str] = None,
    ):
        self.force_passwd_prompt = force_passwd_prompt
        self.never_passwd_prompt = never_passwd_prompt
        self.pgexecute = pgexecute
        self.dsn_alias = None
        self.watch_command = None

        # Load config.
        c = self.config = get_config(pgclirc_file)

        # at this point, config should be written to pgclirc_file if it did not exist. Read it.
        self.config_writer = load_config(get_config_filename(pgclirc_file))

        # make sure to use self.config_writer, not self.config
        NamedQueries.instance = NamedQueries.from_config(self.config_writer)

        self.logger = logging.getLogger(__name__)
        self.initialize_logging()

        self.set_default_pager(c)
        self.output_file = None
        self.pgspecial = PGSpecial()

        self.explain_mode = False
        self.multi_line = c["main"].as_bool("multi_line")
        self.multiline_mode = c["main"].get("multi_line_mode", "psql")
        self.vi_mode = c["main"].as_bool("vi")
        self.auto_expand = auto_vertical_output or c["main"].as_bool("auto_expand")
        self.auto_retry_closed_connection = c["main"].as_bool(
            "auto_retry_closed_connection"
        )
        self.expanded_output = c["main"].as_bool("expand")
        self.pgspecial.timing_enabled = c["main"].as_bool("timing")
        if row_limit is not None:
            self.row_limit = row_limit
        else:
            self.row_limit = c["main"].as_int("row_limit")

        self.application_name = application_name

        # if not specified, set to DEFAULT_MAX_FIELD_WIDTH
        # if specified but empty, set to None to disable truncation
        # ellipsis will take at least 3 symbols, so this can't be less than 3 if specified and > 0
        max_field_width = c["main"].get("max_field_width", DEFAULT_MAX_FIELD_WIDTH)
        if max_field_width and max_field_width.lower() != "none":
            max_field_width = max(3, abs(int(max_field_width)))
        else:
            max_field_width = None
        self.max_field_width = max_field_width

        self.min_num_menu_lines = c["main"].as_int("min_num_menu_lines")
        self.multiline_continuation_char = c["main"]["multiline_continuation_char"]
        self.table_format = c["main"]["table_format"]
        self.syntax_style = c["main"]["syntax_style"]
        self.cli_style = c["colors"]
        self.wider_completion_menu = c["main"].as_bool("wider_completion_menu")
        self.destructive_warning = parse_destructive_warning(
            warn or c["main"].as_list("destructive_warning")
        )
        self.destructive_warning_restarts_connection = c["main"].as_bool(
            "destructive_warning_restarts_connection"
        )
        self.destructive_statements_require_transaction = c["main"].as_bool(
            "destructive_statements_require_transaction"
        )

        self.less_chatty = bool(less_chatty) or c["main"].as_bool("less_chatty")
        self.verbose_errors = "verbose_errors" in c["main"] and c["main"].as_bool(
            "verbose_errors"
        )
        self.null_string = c["main"].get("null_string", "<null>")
        self.prompt_format = (
            prompt
            if prompt is not None
            else c["main"].get("prompt", self.default_prompt)
        )
        self.prompt_dsn_format = prompt_dsn
        self.on_error = c["main"]["on_error"].upper()
        self.decimal_format = c["data_formats"]["decimal"]
        self.float_format = c["data_formats"]["float"]
        auth.keyring_initialize(c["main"].as_bool("keyring"), logger=self.logger)
        self.show_bottom_toolbar = c["main"].as_bool("show_bottom_toolbar")

        self.pgspecial.pset_pager(
            self.config["main"].as_bool("enable_pager") and "on" or "off"
        )

        self.style_output = style_factory_output(self.syntax_style, c["colors"])

        self.now = dt.datetime.today()

        self.completion_refresher = CompletionRefresher()

        self.query_history = []

        # Initialize completer
        smart_completion = c["main"].as_bool("smart_completion")
        keyword_casing = c["main"]["keyword_casing"]
        single_connection = single_connection or c["main"].as_bool(
            "always_use_single_connection"
        )
        self.settings = {
            "casing_file": get_casing_file(c),
            "generate_casing_file": c["main"].as_bool("generate_casing_file"),
            "generate_aliases": c["main"].as_bool("generate_aliases"),
            "asterisk_column_order": c["main"]["asterisk_column_order"],
            "qualify_columns": c["main"]["qualify_columns"],
            "case_column_headers": c["main"].as_bool("case_column_headers"),
            "search_path_filter": c["main"].as_bool("search_path_filter"),
            "single_connection": single_connection,
            "less_chatty": less_chatty,
            "keyword_casing": keyword_casing,
            "alias_map_file": c["main"]["alias_map_file"] or None,
        }

        completer = PGCompleter(
            smart_completion, pgspecial=self.pgspecial, settings=self.settings
        )
        self.completer = completer
        self._completer_lock = threading.Lock()
        self.register_special_commands()

        self.prompt_app = None

        self.ssh_tunnel_config = c.get("ssh tunnels")
        self.ssh_tunnel_url = ssh_tunnel_url
        self.ssh_tunnel = None

        if log_file:
            with open(log_file, "a+"):
                pass  # ensure writeable
        self.log_file = log_file

        # formatter setup
        self.formatter = TabularOutputFormatter(format_name=c["main"]["table_format"])
        register_new_formatter(self.formatter)

    def quit(self):
        raise PgCliQuitError

    def register_special_commands(self):
        self.pgspecial.register(
            self.change_db,
            "\\c",
            "\\c[onnect] database_name",
            "Change to a new database.",
            aliases=("use", "\\connect", "USE"),
        )

        refresh_callback = lambda: self.refresh_completions(persist_priorities="all")

        self.pgspecial.register(
            self.quit,
            "\\q",
            "\\q",
            "Quit pgcli.",
            arg_type=NO_QUERY,
            case_sensitive=True,
            aliases=(":q",),
        )
        self.pgspecial.register(
            self.quit,
            "quit",
            "quit",
            "Quit pgcli.",
            arg_type=NO_QUERY,
            case_sensitive=False,
            aliases=("exit",),
        )
        self.pgspecial.register(
            refresh_callback,
            "\\#",
            "\\#",
            "Refresh auto-completions.",
            arg_type=NO_QUERY,
        )
        self.pgspecial.register(
            refresh_callback,
            "\\refresh",
            "\\refresh",
            "Refresh auto-completions.",
            arg_type=NO_QUERY,
        )
        self.pgspecial.register(
            self.execute_from_file, "\\i", "\\i filename", "Execute commands from file."
        )
        self.pgspecial.register(
            self.write_to_file,
            "\\o",
            "\\o [filename]",
            "Send all query results to file.",
        )
        self.pgspecial.register(
            self.write_to_logfile,
            "\\log-file",
            "\\log-file [filename]",
            "Log all query results to a logfile, in addition to the normal output destination.",
        )
        self.pgspecial.register(
            self.info_connection, "\\conninfo", "\\conninfo", "Get connection details"
        )
        self.pgspecial.register(
            self.change_table_format,
            "\\T",
            "\\T [format]",
            "Change the table format used to output results",
        )

        self.pgspecial.register(
            self.echo,
            "\\echo",
            "\\echo [string]",
            "Echo a string to stdout",
        )

        self.pgspecial.register(
            self.echo,
            "\\qecho",
            "\\qecho [string]",
            "Echo a string to the query output channel.",
        )

        self.pgspecial.register(
            self.toggle_verbose_errors,
            "\\v",
            "\\v [on|off]",
            "Toggle verbose errors.",
        )

    def toggle_verbose_errors(self, pattern, **_):
        flag = pattern.strip()

        if flag == "on":
            self.verbose_errors = True
        elif flag == "off":
            self.verbose_errors = False
        else:
            self.verbose_errors = not self.verbose_errors

        message = "Verbose errors " + "on." if self.verbose_errors else "off."
        return [(None, None, None, message)]

    def echo(self, pattern, **_):
        return [(None, None, None, pattern)]

    def change_table_format(self, pattern, **_):
        try:
            if pattern not in TabularOutputFormatter().supported_formats:
                raise ValueError()
            self.table_format = pattern
            yield (None, None, None, f"Changed table format to {pattern}")
        except ValueError:
            msg = f"Table format {pattern} not recognized. Allowed formats:"
            for table_type in TabularOutputFormatter().supported_formats:
                msg += f"\n\t{table_type}"
            msg += "\nCurrently set to: %s" % self.table_format
            yield (None, None, None, msg)

    def info_connection(self, **_):
        if self.pgexecute.host.startswith("/"):
            host = 'socket "%s"' % self.pgexecute.host
        else:
            host = 'host "%s"' % self.pgexecute.host

        yield (
            None,
            None,
            None,
            'You are connected to database "%s" as user '
            '"%s" on %s at port "%s".'
            % (self.pgexecute.dbname, self.pgexecute.user, host, self.pgexecute.port),
        )

    def change_db(self, pattern, **_):
        if pattern:
            # Get all the parameters in pattern, handling double quotes if any.
            infos = re.findall(r'"[^"]*"|[^"\'\s]+', pattern)
            # Now removing quotes.
            list(map(lambda s: s.strip('"'), infos))

            infos.extend([None] * (4 - len(infos)))
            db, user, host, port = infos
            try:
                self.pgexecute.connect(
                    database=db,
                    user=user,
                    host=host,
                    port=port,
                    **self.pgexecute.extra_args,
                )
            except OperationalError as e:
                click.secho(str(e), err=True, fg="red")
                click.echo("Previous connection kept")
        else:
            self.pgexecute.connect()

        yield (
            None,
            None,
            None,
            'You are now connected to database "%s" as '
            'user "%s"' % (self.pgexecute.dbname, self.pgexecute.user),
        )

    def execute_from_file(self, pattern, **_):
        if not pattern:
            message = "\\i: missing required argument"
            return [(None, None, None, message, "", False, True)]
        try:
            with open(os.path.expanduser(pattern), encoding="utf-8") as f:
                query = f.read()
        except OSError as e:
            return [(None, None, None, str(e), "", False, True)]

        if self.destructive_warning:
            if (
                self.destructive_statements_require_transaction
                and not self.pgexecute.valid_transaction()
                and is_destructive(query, self.destructive_warning)
            ):
                message = "Destructive statements must be run within a transaction. Command execution stopped."
                return [(None, None, None, message)]
            destroy = confirm_destructive_query(
                query, self.destructive_warning, self.dsn_alias
            )
            if destroy is False:
                message = "Wise choice. Command execution stopped."
                return [(None, None, None, message)]

        on_error_resume = self.on_error == "RESUME"
        return self.pgexecute.run(
            query,
            self.pgspecial,
            on_error_resume=on_error_resume,
            explain_mode=self.explain_mode,
        )

    def write_to_logfile(self, pattern, **_):
        if not pattern:
            self.log_file = None
            message = "Logfile capture disabled"
            return [(None, None, None, message, "", True, True)]

        log_file = pathlib.Path(pattern).expanduser().absolute()

        try:
            with open(log_file, "a+"):
                pass  # ensure writeable
        except OSError as e:
            self.log_file = None
            message = str(e) + "\nLogfile capture disabled"
            return [(None, None, None, message, "", False, True)]

        self.log_file = str(log_file)
        message = 'Writing to file "%s"' % self.log_file
        return [(None, None, None, message, "", True, True)]

    def write_to_file(self, pattern, **_):
        if not pattern:
            self.output_file = None
            message = "File output disabled"
            return [(None, None, None, message, "", True, True)]
        filename = os.path.abspath(os.path.expanduser(pattern))
        if not os.path.isfile(filename):
            try:
                open(filename, "w").close()
            except OSError as e:
                self.output_file = None
                message = str(e) + "\nFile output disabled"
                return [(None, None, None, message, "", False, True)]
        self.output_file = filename
        message = 'Writing to file "%s"' % self.output_file
        return [(None, None, None, message, "", True, True)]

    def initialize_logging(self):
        log_file = self.config["main"]["log_file"]
        if log_file == "default":
            log_file = config_location() + "log"
        ensure_dir_exists(log_file)
        log_level = self.config["main"]["log_level"]

        # Disable logging if value is NONE by switching to a no-op handler.
        # Set log level to a high value so it doesn't even waste cycles getting called.
        if log_level.upper() == "NONE":
            handler = logging.NullHandler()
        else:
            handler = logging.FileHandler(os.path.expanduser(log_file))

        level_map = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "NONE": logging.CRITICAL,
        }

        log_level = level_map[log_level.upper()]

        formatter = logging.Formatter(
            "%(asctime)s (%(process)d/%(threadName)s) "
            "%(name)s %(levelname)s - %(message)s"
        )

        handler.setFormatter(formatter)

        root_logger = logging.getLogger("pgcli")
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

        root_logger.debug("Initializing pgcli logging.")
        root_logger.debug("Log file %r.", log_file)

        pgspecial_logger = logging.getLogger("pgspecial")
        pgspecial_logger.addHandler(handler)
        pgspecial_logger.setLevel(log_level)

    def connect_dsn(self, dsn, **kwargs):
        self.connect(dsn=dsn, **kwargs)

    def connect_service(self, service, user):
        service_config, file = parse_service_info(service)
        if service_config is None:
            click.secho(
                f"service '{service}' was not found in {file}", err=True, fg="red"
            )
            sys.exit(1)
        self.connect(
            database=service_config.get("dbname"),
            host=service_config.get("host"),
            user=user or service_config.get("user"),
            port=service_config.get("port"),
            passwd=service_config.get("password"),
        )

    def connect_uri(self, uri):
        kwargs = conninfo_to_dict(uri)
        remap = {"dbname": "database", "password": "passwd"}
        kwargs = {remap.get(k, k): v for k, v in kwargs.items()}
        self.connect(**kwargs)

    def connect(
        self, database="", host="", user="", port="", passwd="", dsn="", **kwargs
    ):
        # Connect to the database.

        if not user:
            user = getuser()

        if not database:
            database = user

        kwargs.setdefault("application_name", self.application_name)

        # If password prompt is not forced but no password is provided, try
        # getting it from environment variable.
        if not self.force_passwd_prompt and not passwd:
            passwd = os.environ.get("PGPASSWORD", "")

        # Prompt for a password immediately if requested via the -W flag. This
        # avoids wasting time trying to connect to the database and catching a
        # no-password exception.
        # If we successfully parsed a password from a URI, there's no need to
        # prompt for it, even with the -W flag
        if self.force_passwd_prompt and not passwd:
            passwd = click.prompt(
                "Password for %s" % user, hide_input=True, show_default=False, type=str
            )

        key = f"{user}@{host}"

        if not passwd and auth.keyring:
            passwd = auth.keyring_get_password(key)

        def should_ask_for_password(exc):
            # Prompt for a password after 1st attempt to connect
            # fails. Don't prompt if the -w flag is supplied
            if self.never_passwd_prompt:
                return False
            error_msg = exc.args[0]
            if "no password supplied" in error_msg:
                return True
            if "password authentication failed" in error_msg:
                return True
            return False

        if dsn:
            parsed_dsn = conninfo_to_dict(dsn)
            if "host" in parsed_dsn:
                host = parsed_dsn["host"]
            if "port" in parsed_dsn:
                port = parsed_dsn["port"]

        if self.ssh_tunnel_config and not self.ssh_tunnel_url:
            for db_host_regex, tunnel_url in self.ssh_tunnel_config.items():
                if re.search(db_host_regex, host):
                    self.ssh_tunnel_url = tunnel_url
                    break

        if self.ssh_tunnel_url:
            # We add the protocol as urlparse doesn't find it by itself
            if "://" not in self.ssh_tunnel_url:
                self.ssh_tunnel_url = f"ssh://{self.ssh_tunnel_url}"

            tunnel_info = urlparse(self.ssh_tunnel_url)
            params = {
                "local_bind_address": ("127.0.0.1",),
                "remote_bind_address": (host, int(port or 5432)),
                "ssh_address_or_host": (tunnel_info.hostname, tunnel_info.port or 22),
                "logger": self.logger,
            }
            if tunnel_info.username:
                params["ssh_username"] = tunnel_info.username
            if tunnel_info.password:
                params["ssh_password"] = tunnel_info.password

            # Hack: sshtunnel adds a console handler to the logger, so we revert handlers.
            # We can remove this when https://github.com/pahaz/sshtunnel/pull/250 is merged.
            logger_handlers = self.logger.handlers.copy()
            try:
                self.ssh_tunnel = sshtunnel.SSHTunnelForwarder(**params)
                self.ssh_tunnel.start()
            except Exception as e:
                self.logger.handlers = logger_handlers
                self.logger.error("traceback: %r", traceback.format_exc())
                click.secho(str(e), err=True, fg="red")
                sys.exit(1)
            self.logger.handlers = logger_handlers

            atexit.register(self.ssh_tunnel.stop)
            host = "127.0.0.1"
            port = self.ssh_tunnel.local_bind_ports[0]

            if dsn:
                dsn = make_conninfo(dsn, host=host, port=port)

        # Attempt to connect to the database.
        # Note that passwd may be empty on the first attempt. If connection
        # fails because of a missing or incorrect password, but we're allowed to
        # prompt for a password (no -w flag), prompt for a passwd and try again.
        try:
            try:
                pgexecute = PGExecute(
                    database,
                    user,
                    passwd,
                    host,
                    port,
                    dsn,
                    notify_callback,
                    **kwargs,
                )
            except (OperationalError, InterfaceError) as e:
                if should_ask_for_password(e):
                    passwd = click.prompt(
                        "Password for %s" % user,
                        hide_input=True,
                        show_default=False,
                        type=str,
                    )
                    pgexecute = PGExecute(
                        database,
                        user,
                        passwd,
                        host,
                        port,
                        dsn,
                        notify_callback,
                        **kwargs,
                    )
                else:
                    raise e
            if passwd and auth.keyring:
                auth.keyring_set_password(key, passwd)

        except Exception as e:  # Connecting to a database could fail.
            self.logger.debug("Database connection failed: %r.", e)
            self.logger.error("traceback: %r", traceback.format_exc())
            click.secho(str(e), err=True, fg="red")
            sys.exit(1)

        self.pgexecute = pgexecute

    def handle_editor_command(self, text):
        r"""
        Editor command is any query that is prefixed or suffixed
        by a '\e'. The reason for a while loop is because a user
        might edit a query multiple times.
        For eg:
        "select * from \e"<enter> to edit it in vim, then come
        back to the prompt with the edited query "select * from
        blah where q = 'abc'\e" to edit it again.
        :param text: Document
        :return: Document
        """
        editor_command = special.editor_command(text)
        while editor_command:
            if editor_command == "\\e":
                filename = special.get_filename(text)
                query = special.get_editor_query(text) or self.get_last_query()
            else:  # \ev or \ef
                filename = None
                spec = text.split()[1]
                if editor_command == "\\ev":
                    query = self.pgexecute.view_definition(spec)
                elif editor_command == "\\ef":
                    query = self.pgexecute.function_definition(spec)
            sql, message = special.open_external_editor(filename, sql=query)
            if message:
                # Something went wrong. Raise an exception and bail.
                raise RuntimeError(message)
            while True:
                try:
                    text = self.prompt_app.prompt(default=sql)
                    break
                except KeyboardInterrupt:
                    sql = ""

            editor_command = special.editor_command(text)
        return text

    def execute_command(self, text, handle_closed_connection=True):
        logger = self.logger

        query = MetaQuery(query=text, successful=False)

        try:
            if self.destructive_warning:
                if (
                    self.destructive_statements_require_transaction
                    and not self.pgexecute.valid_transaction()
                    and is_destructive(text, self.destructive_warning)
                ):
                    click.secho(
                        "Destructive statements must be run within a transaction."
                    )
                    raise KeyboardInterrupt
                destroy = confirm_destructive_query(
                    text, self.destructive_warning, self.dsn_alias
                )
                if destroy is False:
                    click.secho("Wise choice!")
                    raise KeyboardInterrupt
                elif destroy:
                    click.secho("Your call!")

            output, query = self._evaluate_command(text)
        except KeyboardInterrupt:
            if self.destructive_warning_restarts_connection:
                # Restart connection to the database
                self.pgexecute.connect()
                logger.debug("cancelled query and restarted connection, sql: %r", text)
                click.secho(
                    "cancelled query and restarted connection", err=True, fg="red"
                )
            else:
                logger.debug("cancelled query, sql: %r", text)
                click.secho("cancelled query", err=True, fg="red")
        except NotImplementedError:
            click.secho("Not Yet Implemented.", fg="yellow")
        except OperationalError as e:
            logger.error("sql: %r, error: %r", text, e)
            logger.error("traceback: %r", traceback.format_exc())
            click.secho(str(e), err=True, fg="red")
            if handle_closed_connection:
                self._handle_server_closed_connection(text)
        except (PgCliQuitError, EOFError):
            raise
        except Exception as e:
            logger.error("sql: %r, error: %r", text, e)
            logger.error("traceback: %r", traceback.format_exc())
            click.secho(str(e), err=True, fg="red")
        else:
            try:
                if self.output_file and not text.startswith(
                    ("\\o ", "\\log-file", "\\? ", "\\echo ")
                ):
                    try:
                        with open(self.output_file, "a", encoding="utf-8") as f:
                            click.echo(text, file=f)
                            click.echo("\n".join(output), file=f)
                            click.echo("", file=f)  # extra newline
                    except OSError as e:
                        click.secho(str(e), err=True, fg="red")
                else:
                    if output:
                        self.echo_via_pager("\n".join(output))

                # Log to file in addition to normal output
                if (
                    self.log_file
                    and not text.startswith(("\\o ", "\\log-file", "\\? ", "\\echo "))
                    and not text.strip() == ""
                ):
                    try:
                        with open(self.log_file, "a", encoding="utf-8") as f:
                            click.echo(
                                dt.datetime.now().isoformat(), file=f
                            )  # timestamp log
                            click.echo(text, file=f)
                            click.echo("\n".join(output), file=f)
                            click.echo("", file=f)  # extra newline
                    except OSError as e:
                        click.secho(str(e), err=True, fg="red")
            except KeyboardInterrupt:
                pass

            if self.pgspecial.timing_enabled:
                # Only add humanized time display if > 1 second
                if query.total_time > 1:
                    print(
                        "Time: %0.03fs (%s), executed in: %0.03fs (%s)"
                        % (
                            query.total_time,
                            duration_in_words(query.total_time),
                            query.execution_time,
                            duration_in_words(query.execution_time),
                        )
                    )
                else:
                    print("Time: %0.03fs" % query.total_time)

            # Check if we need to update completions, in order of most
            # to least drastic changes
            if query.db_changed:
                with self._completer_lock:
                    self.completer.reset_completions()
                self.refresh_completions(persist_priorities="keywords")
            elif query.meta_changed:
                self.refresh_completions(persist_priorities="all")
            elif query.path_changed:
                logger.debug("Refreshing search path")
                with self._completer_lock:
                    self.completer.set_search_path(self.pgexecute.search_path())
                logger.debug("Search path: %r", self.completer.search_path)
        return query

    def _check_ongoing_transaction_and_allow_quitting(self):
        """Return whether we can really quit, possibly by asking the
        user to confirm so if there is an ongoing transaction.
        """
        if not self.pgexecute.valid_transaction():
            return True
        while 1:
            try:
                choice = click.prompt(
                    "A transaction is ongoing. Choose `c` to COMMIT, `r` to ROLLBACK, `a` to abort exit.",
                    default="a",
                )
            except click.Abort:
                # Print newline if user aborts with `^C`, otherwise
                # pgcli's prompt will be printed on the same line
                # (just after the confirmation prompt).
                click.echo(None, err=False)
                choice = "a"
            choice = choice.lower()
            if choice == "a":
                return False  # do not quit
            if choice == "c":
                query = self.execute_command("commit")
                return query.successful  # quit only if query is successful
            if choice == "r":
                query = self.execute_command("rollback")
                return query.successful  # quit only if query is successful

    def run_cli(self):
        logger = self.logger

        history_file = self.config["main"]["history_file"]
        if history_file == "default":
            history_file = config_location() + "history"
        history = FileHistory(os.path.expanduser(history_file))
        self.refresh_completions(history=history, persist_priorities="none")

        self.prompt_app = self._build_cli(history)

        if not self.less_chatty:
            print("Server: PostgreSQL", self.pgexecute.server_version)
            print("Version:", __version__)
            print("Home: http://pgcli.com")

        try:
            while True:
                try:
                    text = self.prompt_app.prompt()
                except KeyboardInterrupt:
                    continue
                except EOFError:
                    if not self._check_ongoing_transaction_and_allow_quitting():
                        continue
                    raise

                try:
                    text = self.handle_editor_command(text)
                except RuntimeError as e:
                    logger.error("sql: %r, error: %r", text, e)
                    logger.error("traceback: %r", traceback.format_exc())
                    click.secho(str(e), err=True, fg="red")
                    continue

                try:
                    self.handle_watch_command(text)
                except PgCliQuitError:
                    if not self._check_ongoing_transaction_and_allow_quitting():
                        continue
                    raise

                self.now = dt.datetime.today()

                # Allow PGCompleter to learn user's preferred keywords, etc.
                with self._completer_lock:
                    self.completer.extend_query_history(text)

        except (PgCliQuitError, EOFError):
            if not self.less_chatty:
                print("Goodbye!")

    def handle_watch_command(self, text):
        # Initialize default metaquery in case execution fails
        self.watch_command, timing = special.get_watch_command(text)

        # If we run \watch without a command, apply it to the last query run.
        if self.watch_command is not None and not self.watch_command.strip():
            try:
                self.watch_command = self.query_history[-1].query
            except IndexError:
                click.secho(
                    "\\watch cannot be used with an empty query", err=True, fg="red"
                )
                self.watch_command = None

        # If there's a command to \watch, run it in a loop.
        if self.watch_command:
            while self.watch_command:
                try:
                    query = self.execute_command(self.watch_command)
                    click.echo(f"Waiting for {timing} seconds before repeating")
                    sleep(timing)
                except KeyboardInterrupt:
                    self.watch_command = None

        # Otherwise, execute it as a regular command.
        else:
            query = self.execute_command(text)

        self.query_history.append(query)

    def _build_cli(self, history):
        key_bindings = pgcli_bindings(self)

        def get_message():
            if self.dsn_alias and self.prompt_dsn_format is not None:
                prompt_format = self.prompt_dsn_format
            else:
                prompt_format = self.prompt_format

            prompt = self.get_prompt(prompt_format)

            if (
                prompt_format == self.default_prompt
                and len(prompt) > self.max_len_prompt
            ):
                prompt = self.get_prompt("\\d> ")

            prompt = prompt.replace("\\x1b", "\x1b")
            return ANSI(prompt)

        def get_continuation(width, line_number, is_soft_wrap):
            continuation = self.multiline_continuation_char * (width - 1) + " "
            return [("class:continuation", continuation)]

        get_toolbar_tokens = create_toolbar_tokens_func(self)

        if self.wider_completion_menu:
            complete_style = CompleteStyle.MULTI_COLUMN
        else:
            complete_style = CompleteStyle.COLUMN

        with self._completer_lock:
            prompt_app = PromptSession(
                lexer=PygmentsLexer(PostgresLexer),
                reserve_space_for_menu=self.min_num_menu_lines,
                message=get_message,
                prompt_continuation=get_continuation,
                bottom_toolbar=get_toolbar_tokens if self.show_bottom_toolbar else None,
                complete_style=complete_style,
                input_processors=[
                    # Highlight matching brackets while editing.
                    ConditionalProcessor(
                        processor=HighlightMatchingBracketProcessor(chars="[](){}"),
                        filter=HasFocus(DEFAULT_BUFFER) & ~IsDone(),
                    ),
                    # Render \t as 4 spaces instead of "^I"
                    TabsProcessor(char1=" ", char2=" "),
                ],
                auto_suggest=AutoSuggestFromHistory(),
                tempfile_suffix=".sql",
                # N.b. pgcli's multi-line mode controls submit-on-Enter (which
                # overrides the default behaviour of prompt_toolkit) and is
                # distinct from prompt_toolkit's multiline mode here, which
                # controls layout/display of the prompt/buffer
                multiline=True,
                history=history,
                completer=ThreadedCompleter(DynamicCompleter(lambda: self.completer)),
                complete_while_typing=True,
                style=style_factory(self.syntax_style, self.cli_style),
                include_default_pygments_style=False,
                key_bindings=key_bindings,
                enable_open_in_editor=True,
                enable_system_prompt=True,
                enable_suspend=True,
                editing_mode=EditingMode.VI if self.vi_mode else EditingMode.EMACS,
                search_ignore_case=True,
            )

            return prompt_app

    def _should_limit_output(self, sql, cur):
        """returns True if the output should be truncated, False otherwise."""
        if self.explain_mode:
            return False
        if not is_select(sql):
            return False

        return (
            not self._has_limit(sql)
            and self.row_limit != 0
            and cur
            and cur.rowcount > self.row_limit
        )

    def _has_limit(self, sql):
        if not sql:
            return False
        return "limit " in sql.lower()

    def _limit_output(self, cur):
        limit = min(self.row_limit, cur.rowcount)
        new_cur = itertools.islice(cur, limit)
        new_status = "SELECT " + str(limit)
        click.secho("The result was limited to %s rows" % limit, fg="red")

        return new_cur, new_status

    def _evaluate_command(self, text):
        """Used to run a command entered by the user during CLI operation
        (Puts the E in REPL)

        returns (results, MetaQuery)
        """
        logger = self.logger
        logger.debug("sql: %r", text)

        # set query to formatter in order to parse table name
        self.formatter.query = text
        all_success = True
        meta_changed = False  # CREATE, ALTER, DROP, etc
        mutated = False  # INSERT, DELETE, etc
        db_changed = False
        path_changed = False
        output = []
        total = 0
        execution = 0

        # Run the query.
        start = time()
        on_error_resume = self.on_error == "RESUME"
        res = self.pgexecute.run(
            text,
            self.pgspecial,
            lambda x: exception_formatter(x, self.verbose_errors),
            on_error_resume,
            explain_mode=self.explain_mode,
        )

        is_special = None

        for title, cur, headers, status, sql, success, is_special in res:
            logger.debug("headers: %r", headers)
            logger.debug("rows: %r", cur)
            logger.debug("status: %r", status)

            if self._should_limit_output(sql, cur):
                cur, status = self._limit_output(cur)

            if self.pgspecial.auto_expand or self.auto_expand:
                max_width = self.prompt_app.output.get_size().columns
            else:
                max_width = None

            expanded = self.pgspecial.expanded_output or self.expanded_output
            settings = OutputSettings(
                table_format=self.table_format,
                dcmlfmt=self.decimal_format,
                floatfmt=self.float_format,
                missingval=self.null_string,
                expanded=expanded,
                max_width=max_width,
                case_function=(
                    self.completer.case
                    if self.settings["case_column_headers"]
                    else lambda x: x
                ),
                style_output=self.style_output,
                max_field_width=self.max_field_width,
            )
            execution = time() - start
            formatted = format_output(
                title, cur, headers, status, settings, self.explain_mode
            )

            output.extend(formatted)
            total = time() - start

            # Keep track of whether any of the queries are mutating or changing
            # the database
            if success:
                mutated = mutated or is_mutating(status)
                db_changed = db_changed or has_change_db_cmd(sql)
                meta_changed = meta_changed or has_meta_cmd(sql)
                path_changed = path_changed or has_change_path_cmd(sql)
            else:
                all_success = False

        meta_query = MetaQuery(
            text,
            all_success,
            total,
            execution,
            meta_changed,
            db_changed,
            path_changed,
            mutated,
            is_special,
        )

        return output, meta_query

    def _handle_server_closed_connection(self, text):
        """Used during CLI execution."""
        try:
            click.secho("Reconnecting...", fg="green")
            self.pgexecute.connect()
            click.secho("Reconnected!", fg="green")
        except OperationalError as e:
            click.secho("Reconnect Failed", fg="red")
            click.secho(str(e), err=True, fg="red")
        else:
            retry = self.auto_retry_closed_connection or confirm(
                "Run the query from before reconnecting?"
            )
            if retry:
                click.secho("Running query...", fg="green")
                # Don't get stuck in a retry loop
                self.execute_command(text, handle_closed_connection=False)

    def refresh_completions(self, history=None, persist_priorities="all"):
        """Refresh outdated completions

        :param history: A prompt_toolkit.history.FileHistory object. Used to
                        load keyword and identifier preferences

        :param persist_priorities: 'all' or 'keywords'
        """

        callback = functools.partial(
            self._on_completions_refreshed, persist_priorities=persist_priorities
        )
        return self.completion_refresher.refresh(
            self.pgexecute,
            self.pgspecial,
            callback,
            history=history,
            settings=self.settings,
        )

    def _on_completions_refreshed(self, new_completer, persist_priorities):
        self._swap_completer_objects(new_completer, persist_priorities)

        if self.prompt_app:
            # After refreshing, redraw the CLI to clear the statusbar
            # "Refreshing completions..." indicator
            self.prompt_app.app.invalidate()

    def _swap_completer_objects(self, new_completer, persist_priorities):
        """Swap the completer object with the newly created completer.

        persist_priorities is a string specifying how the old completer's
        learned prioritizer should be transferred to the new completer.

          'none'     - The new prioritizer is left in a new/clean state

          'all'      - The new prioritizer is updated to exactly reflect
                       the old one

          'keywords' - The new prioritizer is updated with old keyword
                       priorities, but not any other.

        """
        with self._completer_lock:
            old_completer = self.completer
            self.completer = new_completer

            if persist_priorities == "all":
                # Just swap over the entire prioritizer
                new_completer.prioritizer = old_completer.prioritizer
            elif persist_priorities == "keywords":
                # Swap over the entire prioritizer, but clear name priorities,
                # leaving learned keyword priorities alone
                new_completer.prioritizer = old_completer.prioritizer
                new_completer.prioritizer.clear_names()
            elif persist_priorities == "none":
                # Leave the new prioritizer as is
                pass
            self.completer = new_completer

    def get_completions(self, text, cursor_positition):
        with self._completer_lock:
            return self.completer.get_completions(
                Document(text=text, cursor_position=cursor_positition), None
            )

    def get_prompt(self, string):
        # should be before replacing \\d
        string = string.replace("\\dsn_alias", self.dsn_alias or "")
        string = string.replace("\\t", self.now.strftime("%x %X"))
        string = string.replace("\\u", self.pgexecute.user or "(none)")
        string = string.replace("\\H", self.pgexecute.host or "(none)")
        string = string.replace("\\h", self.pgexecute.short_host or "(none)")
        string = string.replace("\\d", self.pgexecute.dbname or "(none)")
        string = string.replace(
            "\\p",
            str(self.pgexecute.port) if self.pgexecute.port is not None else "5432",
        )
        string = string.replace("\\i", str(self.pgexecute.pid) or "(none)")
        string = string.replace("\\#", "#" if self.pgexecute.superuser else ">")
        string = string.replace("\\n", "\n")
        return string

    def get_last_query(self):
        """Get the last query executed or None."""
        return self.query_history[-1][0] if self.query_history else None

    def is_too_wide(self, line):
        """Will this line be too wide to fit into terminal?"""
        if not self.prompt_app:
            return False
        return (
            len(COLOR_CODE_REGEX.sub("", line))
            > self.prompt_app.output.get_size().columns
        )

    def is_too_tall(self, lines):
        """Are there too many lines to fit into terminal?"""
        if not self.prompt_app:
            return False
        return len(lines) >= (self.prompt_app.output.get_size().rows - 4)

    def echo_via_pager(self, text, color=None):
        if self.pgspecial.pager_config == PAGER_OFF or self.watch_command:
            click.echo(text, color=color)
        elif (
            self.pgspecial.pager_config == PAGER_LONG_OUTPUT
            and self.table_format != "csv"
        ):
            lines = text.split("\n")

            # The last 4 lines are reserved for the pgcli menu and padding
            if self.is_too_tall(lines) or any(self.is_too_wide(l) for l in lines):
                click.echo_via_pager(text, color=color)
            else:
                click.echo(text, color=color)
        else:
            click.echo_via_pager(text, color)


@click.command()
# Default host is '' so psycopg can default to either localhost or unix socket
@click.option(
    "-h",
    "--host",
    default="",
    envvar="PGHOST",
    help="Host address of the postgres database.",
)
@click.option(
    "-p",
    "--port",
    default=5432,
    help="Port number at which the " "postgres instance is listening.",
    envvar="PGPORT",
    type=click.INT,
)
@click.option(
    "-U",
    "--username",
    "username_opt",
    help="Username to connect to the postgres database.",
)
@click.option(
    "-u", "--user", "username_opt", help="Username to connect to the postgres database."
)
@click.option(
    "-W",
    "--password",
    "prompt_passwd",
    is_flag=True,
    default=False,
    help="Force password prompt.",
)
@click.option(
    "-w",
    "--no-password",
    "never_prompt",
    is_flag=True,
    default=False,
    help="Never prompt for password.",
)
@click.option(
    "--single-connection",
    "single_connection",
    is_flag=True,
    default=False,
    help="Do not use a separate connection for completions.",
)
@click.option("-v", "--version", is_flag=True, help="Version of pgcli.")
@click.option("-d", "--dbname", "dbname_opt", help="database name to connect to.")
@click.option(
    "--pgclirc",
    default=config_location() + "config",
    envvar="PGCLIRC",
    help="Location of pgclirc file.",
    type=click.Path(dir_okay=False),
)
@click.option(
    "-D",
    "--dsn",
    default="",
    envvar="DSN",
    help="Use DSN configured into the [alias_dsn] section of pgclirc file.",
)
@click.option(
    "--list-dsn",
    "list_dsn",
    is_flag=True,
    help="list of DSN configured into the [alias_dsn] section of pgclirc file.",
)
@click.option(
    "--row-limit",
    default=None,
    envvar="PGROWLIMIT",
    type=click.INT,
    help="Set threshold for row limit prompt. Use 0 to disable prompt.",
)
@click.option(
    "--application-name",
    default="pgcli",
    envvar="PGAPPNAME",
    help="Application name for the connection.",
)
@click.option(
    "--less-chatty",
    "less_chatty",
    is_flag=True,
    default=False,
    help="Skip intro on startup and goodbye on exit.",
)
@click.option("--prompt", help='Prompt format (Default: "\\u@\\h:\\d> ").')
@click.option(
    "--prompt-dsn",
    help='Prompt format for connections using DSN aliases (Default: "\\u@\\h:\\d> ").',
)
@click.option(
    "-l",
    "--list",
    "list_databases",
    is_flag=True,
    help="list available databases, then exit.",
)
@click.option(
    "--ping",
    "ping_database",
    is_flag=True,
    default=False,
    help="Check database connectivity, then exit.",
)
@click.option(
    "--auto-vertical-output",
    is_flag=True,
    help="Automatically switch to vertical output mode if the result is wider than the terminal width.",
)
@click.option(
    "--warn",
    default=None,
    help="Warn before running a destructive query.",
)
@click.option(
    "--ssh-tunnel",
    default=None,
    help="Open an SSH tunnel to the given address and connect to the database from it.",
)
@click.option(
    "--log-file",
    default=None,
    help="Write all queries & output into a file, in addition to the normal output destination.",
)
@click.argument("dbname", default=lambda: None, envvar="PGDATABASE", nargs=1)
@click.argument("username", default=lambda: None, envvar="PGUSER", nargs=1)
def cli(
    dbname,
    username_opt,
    host,
    port,
    prompt_passwd,
    never_prompt,
    single_connection,
    dbname_opt,
    username,
    version,
    pgclirc,
    dsn,
    row_limit,
    application_name,
    less_chatty,
    prompt,
    prompt_dsn,
    list_databases,
    ping_database,
    auto_vertical_output,
    list_dsn,
    warn,
    ssh_tunnel: str,
    log_file: str,
):
    if version:
        print("Version:", __version__)
        sys.exit(0)

    config_dir = os.path.dirname(config_location())
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    # Migrate the config file from old location.
    config_full_path = config_location() + "config"
    if os.path.exists(os.path.expanduser("~/.pgclirc")):
        if not os.path.exists(config_full_path):
            shutil.move(os.path.expanduser("~/.pgclirc"), config_full_path)
            print("Config file (~/.pgclirc) moved to new location", config_full_path)
        else:
            print("Config file is now located at", config_full_path)
            print(
                "Please move the existing config file ~/.pgclirc to",
                config_full_path,
            )
    if list_dsn:
        try:
            cfg = load_config(pgclirc, config_full_path)
            for alias in cfg["alias_dsn"]:
                click.secho(alias + " : " + cfg["alias_dsn"][alias])
            sys.exit(0)
        except Exception as err:
            click.secho(
                "Invalid DSNs found in the config file. "
                'Please check the "[alias_dsn]" section in pgclirc.',
                err=True,
                fg="red",
            )
            sys.exit(1)

    if ssh_tunnel and not SSH_TUNNEL_SUPPORT:
        click.secho(
            'Cannot open SSH tunnel, "sshtunnel" package was not found. '
            "Please install pgcli with `pip install pgcli[sshtunnel]` if you want SSH tunnel support.",
            err=True,
            fg="red",
        )
        sys.exit(1)

    pgcli = PGCli(
        prompt_passwd,
        never_prompt,
        pgclirc_file=pgclirc,
        row_limit=row_limit,
        application_name=application_name,
        single_connection=single_connection,
        less_chatty=less_chatty,
        prompt=prompt,
        prompt_dsn=prompt_dsn,
        auto_vertical_output=auto_vertical_output,
        warn=warn,
        ssh_tunnel_url=ssh_tunnel,
        log_file=log_file,
    )

    # Choose which ever one has a valid value.
    if dbname_opt and dbname:
        # work as psql: when database is given as option and argument use the argument as user
        username = dbname
    database = dbname_opt or dbname or ""
    user = username_opt or username
    service = None
    if database.startswith("service="):
        service = database[8:]
    elif os.getenv("PGSERVICE") is not None:
        service = os.getenv("PGSERVICE")
    # because option --ping, --list or -l are not supposed to have a db name
    if list_databases or ping_database:
        database = "postgres"

    if dsn != "":
        try:
            cfg = load_config(pgclirc, config_full_path)
            dsn_config = cfg["alias_dsn"][dsn]
        except KeyError:
            click.secho(
                f"Could not find a DSN with alias {dsn}. "
                'Please check the "[alias_dsn]" section in pgclirc.',
                err=True,
                fg="red",
            )
            sys.exit(1)
        except Exception:
            click.secho(
                "Invalid DSNs found in the config file. "
                'Please check the "[alias_dsn]" section in pgclirc.',
                err=True,
                fg="red",
            )
            sys.exit(1)
        pgcli.connect_uri(dsn_config)
        pgcli.dsn_alias = dsn
    elif "://" in database:
        pgcli.connect_uri(database)
    elif "=" in database and service is None:
        pgcli.connect_dsn(database, user=user)
    elif service is not None:
        pgcli.connect_service(service, user)
    else:
        pgcli.connect(database, host, user, port)

    local_tz = None
    try:
        local_tz = tzlocal.get_localzone_name()

        if local_tz is None:
            click.secho(
                "No local time zone configuration found",
                err=True,
                fg="yellow",
            )
    except ZoneInfoNotFoundError as e:
        # e.args[0] is the pre-formatted message which includes a list
        # of conflicting sources
        click.secho(e.args[0], err=True, fg="yellow")

    if local_tz is not None:
        pgcli.pgexecute.set_timezone(local_tz)
    else:
        click.secho(
            "Continuing with the default server time zone",
            err=True,
            fg="yellow",
        )

    if list_databases:
        cur, headers, status = pgcli.pgexecute.full_databases()

        title = "List of databases"
        settings = OutputSettings(table_format="ascii", missingval="<null>")
        formatted = format_output(title, cur, headers, status, settings)
        pgcli.echo_via_pager("\n".join(formatted))

        sys.exit(0)

    if ping_database:
        try:
            list(pgcli.pgexecute.run("SELECT 1"))
        except Exception:
            click.secho(
                "Could not connect to the database. Please check that the database is running.",
                err=True,
                fg="red",
            )
            sys.exit(1)
        else:
            click.echo("PONG")
            sys.exit(0)

    pgcli.logger.debug(
        "Launch Params: \n" "\tdatabase: %r" "\tuser: %r" "\thost: %r" "\tport: %r",
        database,
        user,
        host,
        port,
    )

    if setproctitle:
        obfuscate_process_password()

    pgcli.run_cli()


def obfuscate_process_password():
    process_title = setproctitle.getproctitle()
    if "://" in process_title:
        process_title = re.sub(r":(.*):(.*)@", r":\1:xxxx@", process_title)
    elif "=" in process_title:
        process_title = re.sub(
            r"password=(.+?)((\s[a-zA-Z]+=)|$)", r"password=xxxx\2", process_title
        )

    setproctitle.setproctitle(process_title)


def has_meta_cmd(query):
    """Determines if the completion needs a refresh by checking if the sql
    statement is an alter, create, drop, commit or rollback."""
    try:
        first_token = query.split()[0]
        if first_token.lower() in ("alter", "create", "drop", "commit", "rollback"):
            return True
    except Exception:
        return False

    return False


def has_change_db_cmd(query):
    """Determines if the statement is a database switch such as 'use' or '\\c'"""
    try:
        first_token = query.split()[0]
        if first_token.lower() in ("use", "\\c", "\\connect"):
            return True
    except Exception:
        return False

    return False


def has_change_path_cmd(sql):
    """Determines if the search_path should be refreshed by checking if the
    sql has 'set search_path'."""
    return "set search_path" in sql.lower()


def is_mutating(status):
    """Determines if the statement is mutating based on the status."""
    if not status:
        return False

    mutating = {"insert", "update", "delete"}
    return status.split(None, 1)[0].lower() in mutating


def is_select(status):
    """Returns true if the first word in status is 'select'."""
    if not status:
        return False
    return status.split(None, 1)[0].lower() == "select"


def diagnostic_output(diagnostic: Diagnostic) -> str:
    fields = []

    if diagnostic.severity is not None:
        fields.append("Severity: " + diagnostic.severity)

    if diagnostic.severity_nonlocalized is not None:
        fields.append("Severity (non-localized): " + diagnostic.severity_nonlocalized)

    if diagnostic.sqlstate is not None:
        fields.append("SQLSTATE code: " + diagnostic.sqlstate)

    if diagnostic.message_primary is not None:
        fields.append("Message: " + diagnostic.message_primary)

    if diagnostic.message_detail is not None:
        fields.append("Detail: " + diagnostic.message_detail)

    if diagnostic.message_hint is not None:
        fields.append("Hint: " + diagnostic.message_hint)

    if diagnostic.statement_position is not None:
        fields.append("Position: " + diagnostic.statement_position)

    if diagnostic.internal_position is not None:
        fields.append("Internal position: " + diagnostic.internal_position)

    if diagnostic.internal_query is not None:
        fields.append("Internal query: " + diagnostic.internal_query)

    if diagnostic.context is not None:
        fields.append("Where: " + diagnostic.context)

    if diagnostic.schema_name is not None:
        fields.append("Schema name: " + diagnostic.schema_name)

    if diagnostic.table_name is not None:
        fields.append("Table name: " + diagnostic.table_name)

    if diagnostic.column_name is not None:
        fields.append("Column name: " + diagnostic.column_name)

    if diagnostic.datatype_name is not None:
        fields.append("Data type name: " + diagnostic.datatype_name)

    if diagnostic.constraint_name is not None:
        fields.append("Constraint name: " + diagnostic.constraint_name)

    if diagnostic.source_file is not None:
        fields.append("File: " + diagnostic.source_file)

    if diagnostic.source_line is not None:
        fields.append("Line: " + diagnostic.source_line)

    if diagnostic.source_function is not None:
        fields.append("Routine: " + diagnostic.source_function)

    return "\n".join(fields)


def exception_formatter(e, verbose_errors: bool = False):
    s = str(e)
    if verbose_errors:
        s += "\n" + diagnostic_output(e.diag)
    return click.style(s, fg="red")


def format_output(title, cur, headers, status, settings, explain_mode=False):
    output = []
    expanded = settings.expanded or settings.table_format == "vertical"
    table_format = "vertical" if settings.expanded else settings.table_format
    max_width = settings.max_width
    case_function = settings.case_function
    if explain_mode:
        formatter = ExplainOutputFormatter(max_width or 100)
    else:
        formatter = TabularOutputFormatter(format_name=table_format)

    def format_array(val):
        if val is None:
            return settings.missingval
        if not isinstance(val, list):
            return val
        return "{" + ",".join(str(format_array(e)) for e in val) + "}"

    def format_arrays(data, headers, **_):
        data = list(data)
        for row in data:
            row[:] = [
                format_array(val) if isinstance(val, list) else val for val in row
            ]

        return data, headers

    def format_status(cur, status):
        # redshift does not return rowcount as part of status.
        # See https://github.com/dbcli/pgcli/issues/1320
        if cur and hasattr(cur, "rowcount") and cur.rowcount is not None:
            if status and not status.endswith(str(cur.rowcount)):
                status += " %s" % cur.rowcount
        return status

    output_kwargs = {
        "sep_title": "RECORD {n}",
        "sep_character": "-",
        "sep_length": (1, 25),
        "missing_value": settings.missingval,
        "integer_format": settings.dcmlfmt,
        "float_format": settings.floatfmt,
        "preprocessors": (format_numbers, format_arrays),
        "disable_numparse": True,
        "preserve_whitespace": True,
        "style": settings.style_output,
        "max_field_width": settings.max_field_width,
    }
    if not settings.floatfmt:
        output_kwargs["preprocessors"] = (align_decimals,)

    if table_format == "csv":
        # The default CSV dialect is "excel" which is not handling newline values correctly
        # Nevertheless, we want to keep on using "excel" on Windows since it uses '\r\n'
        # as the line terminator
        # https://github.com/dbcli/pgcli/issues/1102
        dialect = "excel" if platform.system() == "Windows" else "unix"
        output_kwargs["dialect"] = dialect

    if title:  # Only print the title if it's not None.
        output.append(title)

    if cur:
        headers = [case_function(x) for x in headers]
        if max_width is not None:
            cur = list(cur)
        column_types = None
        if hasattr(cur, "description"):
            column_types = []
            for d in cur.description:
                col_type = cur.adapters.types.get(d.type_code)
                type_name = col_type.name if col_type else None
                if type_name in ("numeric", "float4", "float8"):
                    column_types.append(float)
                if type_name in ("int2", "int4", "int8"):
                    column_types.append(int)
                else:
                    column_types.append(str)

        formatted = formatter.format_output(cur, headers, **output_kwargs)
        if isinstance(formatted, str):
            formatted = iter(formatted.splitlines())
        first_line = next(formatted)
        formatted = itertools.chain([first_line], formatted)
        if (
            not explain_mode
            and not expanded
            and max_width
            and len(strip_ansi(first_line)) > max_width
            and headers
        ):
            formatted = formatter.format_output(
                cur,
                headers,
                format_name="vertical",
                column_types=column_types,
                **output_kwargs,
            )
            if isinstance(formatted, str):
                formatted = iter(formatted.splitlines())

        output = itertools.chain(output, formatted)

    # Only print the status if it's not None
    if status:
        output = itertools.chain(output, [format_status(cur, status)])

    return output


def parse_service_info(service):
    service = service or os.getenv("PGSERVICE")
    service_file = os.getenv("PGSERVICEFILE")
    if not service_file:
        # try ~/.pg_service.conf (if that exists)
        if platform.system() == "Windows":
            service_file = os.getenv("PGSYSCONFDIR") + "\\pg_service.conf"
        elif os.getenv("PGSYSCONFDIR"):
            service_file = os.path.join(os.getenv("PGSYSCONFDIR"), ".pg_service.conf")
        else:
            service_file = os.path.expanduser("~/.pg_service.conf")
    if not service or not os.path.exists(service_file):
        # nothing to do
        return None, service_file
    with open(service_file, newline="") as f:
        skipped_lines = skip_initial_comment(f)
        try:
            service_file_config = ConfigObj(f)
        except ParseError as err:
            err.line_number += skipped_lines
            raise err
    if service not in service_file_config:
        return None, service_file
    service_conf = service_file_config.get(service)
    return service_conf, service_file


def duration_in_words(duration_in_seconds: float) -> str:
    if not duration_in_seconds:
        return "0 seconds"
    components = []
    hours, remainder = divmod(duration_in_seconds, 3600)
    if hours > 1:
        components.append(f"{hours} hours")
    elif hours == 1:
        components.append("1 hour")
    minutes, seconds = divmod(remainder, 60)
    if minutes > 1:
        components.append(f"{minutes} minutes")
    elif minutes == 1:
        components.append("1 minute")
    if seconds >= 2:
        components.append(f"{int(seconds)} seconds")
    elif seconds >= 1:
        components.append("1 second")
    elif seconds:
        components.append(f"{round(seconds, 3)} second")
    return " ".join(components)


if __name__ == "__main__":
    cli()
