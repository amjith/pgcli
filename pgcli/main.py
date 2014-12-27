#!/usr/bin/env python
from __future__ import unicode_literals
from __future__ import print_function

import os

import click

from prompt_toolkit import CommandLineInterface, AbortAction, Exit
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.prompt import DefaultPrompt
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_bindings.emacs import emacs_bindings
from pygments.lexers.sql import SqlLexer

from .packages.tabulate import tabulate
from .packages.pgspecial import (CASE_SENSITIVE_COMMANDS,
        NON_CASE_SENSITIVE_COMMANDS)
from .pgcompleter import PGCompleter
from .pgtoolbar import PGToolbar
from .pgstyle import PGStyle
from .pgexecute import PGExecute
from .pgline import PGLine
from .config import write_default_config, load_config
from .key_bindings import pgcli_bindings

@click.command()
@click.option('-h', '--host', default='', help='Host address of the '
        'postgres database.')
@click.option('-p', '--port', default=5432, help='Port number at which the '
        'postgres instance is listening.')
@click.option('-U', '--user', prompt=True, envvar='USER', help='User name to '
        'connect to the postgres database.')
@click.option('-W', '--password', is_flag=True, help='Force password prompt.')
@click.argument('database', envvar='USER')
def cli(database, user, password, host, port):

    if password:
        passwd = click.prompt('Password', hide_input=True, show_default=False,
                type=str)
    else:
        passwd = ''

    from pgcli import __file__ as package_root
    package_root = os.path.dirname(package_root)

    default_config = os.path.join(package_root, 'pgclirc')
    # Write default config.
    write_default_config(default_config, '~/.pgclirc')

    # Load config.
    config = load_config('~/.pgclirc')
    smart_completion = config.getboolean('main', 'smart_completion')

    less_opts = os.environ.get('LESS', '')
    if not less_opts:
        os.environ['LESS'] = '-RXF'

    if 'X' not in less_opts:
        os.environ['LESS'] += 'X'
    if 'F' not in less_opts:
        os.environ['LESS'] += 'F'

    # Connect to the database.
    try:
        pgexecute = PGExecute(database, user, passwd, host, port)
    except Exception as e:  # Connecting to a database could fail.
        click.secho(e.message, err=True, fg='red')
        exit(1)
    layout = Layout(before_input=DefaultPrompt('%s> ' % pgexecute.dbname),
            menus=[CompletionsMenu(max_height=10)],
            lexer=SqlLexer,
            bottom_toolbars=[
                PGToolbar()])
    completer = PGCompleter(smart_completion)
    completer.extend_special_commands(CASE_SENSITIVE_COMMANDS.keys())
    completer.extend_special_commands(NON_CASE_SENSITIVE_COMMANDS.keys())
    tables = pgexecute.tables()
    completer.extend_table_names(tables)
    for table in tables:
        completer.extend_column_names(table, pgexecute.columns(table))
    completer.extend_database_names(pgexecute.databases())
    line = PGLine(always_multiline=False, completer=completer,
            history=FileHistory(os.path.expanduser('~/.pgcli-history')))
    cli = CommandLineInterface(style=PGStyle, layout=layout, line=line,
            key_binding_factories=[emacs_bindings, pgcli_bindings])

    try:
        while True:
            cli.layout.before_input = DefaultPrompt('%s> ' % pgexecute.dbname)
            document = cli.read_input(on_exit=AbortAction.RAISE_EXCEPTION)

            # The reason we check here instead of inside the pgexecute is
            # because we want to raise the Exit exception which will be caught
            # by the try/except block that wraps the pgexecute.run() statement.
            if (document.text.strip().lower() == 'exit'
                    or document.text.strip().lower() == 'quit'
                    or document.text.strip() == '\q'
                    or document.text.strip() == ':q'):
                raise Exit
            try:
                res = pgexecute.run(document.text)
                output = []
                for rows, headers, status in res:
                    if rows:
                        output.append(tabulate(rows, headers, tablefmt='psql'))
                    if status:  # Only print the status if it's not None.
                        output.append(status)
                    click.echo_via_pager('\n'.join(output))
            except Exception as e:
                click.secho(e.message, err=True, fg='red')

            # Refresh the table names and column names if necessary.
            if document.text and need_completion_refresh(document.text):
                completer.reset_completions()
                tables = pgexecute.tables()
                completer.extend_table_names(tables)
                for table in tables:
                    completer.extend_column_names(table,
                            pgexecute.columns(table))
    except Exit:
        print ('GoodBye!')
    finally:  # Reset the less opts back to normal.
        if less_opts:
            os.environ['LESS'] = less_opts

def need_completion_refresh(sql):
    try:
        first_token = sql.split()[0]
        return first_token in ('alter', 'create', 'use', '\c', 'drop')
    except Exception:
        return False
