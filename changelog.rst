Dev
===

Features
--------
* Add a `--ping` command line option; allows pgcli to replace `pg_isready`
* Changed the packaging metadata from setup.py to pyproject.toml
* The session time zone setting is set to the system time zone by default

Bug fixes:
----------
* Avoid raising `NameError` when exiting unsuccessfully in some cases

4.1.0 (2024-03-09)
==================

Features:
---------
* Support `PGAPPNAME` as an environment variable and `--application-name` as a command line argument.
* Add `verbose_errors` config and `\v` special command which enable the
  displaying of all Postgres error fields received.
* Show Postgres notifications.
* Support sqlparse 0.5.x
* Add `--log-file [filename]` cli argument and `\log-file [filename]` special commands to
  log to an external file in addition to the normal output

Bug fixes:
----------

* Fix display of "short host" in prompt (with `\h`) for IPv4 addresses ([issue 964](https://github.com/dbcli/pgcli/issues/964)).
* Fix backwards display of NOTICEs from a Function ([issue 1443](https://github.com/dbcli/pgcli/issues/1443))
* Fix psycopg errors when installing on Windows.  ([issue 1413](https://https://github.com/dbcli/pgcli/issues/1413))
* Use a home-made function to display query duration instead of relying on a third-party library (the general behaviour does not change), which fixes the installation of `pgcli` on 32-bit architectures ([issue 1451](https://github.com/dbcli/pgcli/issues/1451))

==================
4.0.1 (2023-10-30)
==================

Internal:
---------
* Allow stable version of pendulum.

==================
4.0.0 (2023-10-27)
==================

Features:
---------

* Ask for confirmation when quitting cli while a transaction is ongoing.
* New `destructive_statements_require_transaction` config option to refuse to execute a
  destructive SQL statement if outside a transaction. This option is off by default.
* Changed the `destructive_warning` config to be a list of commands that are considered
  destructive. This would allow you to be warned on `create`, `grant`, or `insert` queries.
* Destructive warnings will now include the alias dsn connection string name if provided (-D option).
* pgcli.magic will now work with connection URLs that use TLS client certificates for authentication
* Have config option to retry queries on operational errors like connections being lost.
  Also prevents getting stuck in a retry loop.
* Config option to not restart connection when cancelling a `destructive_warning` query. By default,
  it will now not restart.
* Config option to always run with a single connection.
* Add comment explaining default LESS environment variable behavior and change example pager setting.
* Added `\echo` & `\qecho` special commands. ([issue 1335](https://github.com/dbcli/pgcli/issues/1335)).

Bug fixes:
----------

* Fix `\ev` not producing a correctly quoted "schema"."view"
* Fix 'invalid connection option "dsn"' ([issue 1373](https://github.com/dbcli/pgcli/issues/1373)).
* Fix explain mode when used with `expand`, `auto_expand`, or `--explain-vertical-output` ([issue 1393](https://github.com/dbcli/pgcli/issues/1393)).
* Fix sql-insert format emits NULL as 'None' ([issue 1408](https://github.com/dbcli/pgcli/issues/1408)).
* Improve check for prompt-toolkit 3.0.6 ([issue 1416](https://github.com/dbcli/pgcli/issues/1416)).
* Allow specifying an `alias_map_file` in the config that will use
  predetermined table aliases instead of generating aliases programmatically on
  the fly
* Fixed SQL error when there is a comment on the first line: ([issue 1403](https://github.com/dbcli/pgcli/issues/1403))
* Fix wrong usage of prompt instead of confirm when confirm execution of destructive query

Internal:
---------

* Drop support for Python 3.7 and add 3.12.

3.5.0 (2022/09/15):
===================

Features:
---------

* New formatter is added to export query result to sql format (such as sql-insert, sql-update) like mycli.

Bug fixes:
----------

* Fix exception when retrieving password from keyring ([issue 1338](https://github.com/dbcli/pgcli/issues/1338)).
* Fix using comments with special commands ([issue 1362](https://github.com/dbcli/pgcli/issues/1362)).
* Small improvements to the Windows developer experience
* Fix submitting queries in safe multiline mode ([1360](https://github.com/dbcli/pgcli/issues/1360)).

Internal:
---------

* Port to psycopg3 (https://github.com/psycopg/psycopg).
* Fix typos

3.4.1 (2022/03/19)
==================

Bug fixes:
----------

* Fix the bug with Redshift not displaying word count in status ([related issue](https://github.com/dbcli/pgcli/issues/1320)).
* Show the error status for CSV output format.


3.4.0 (2022/02/21)
==================

Features:
---------

* Add optional support for automatically creating an SSH tunnel to a machine with access to the remote database ([related issue](https://github.com/dbcli/pgcli/issues/459)).

3.3.1 (2022/01/18)
==================

Bug fixes:
----------

* Prompt for password when -W is provided even if there is a password in keychain. Fixes #1307.
* Upgrade cli_helpers to 2.2.1

3.3.0 (2022/01/11)
==================

Features:
---------

* Add `max_field_width` setting to config, to enable more control over field truncation ([related issue](https://github.com/dbcli/pgcli/issues/1250)).
* Re-run last query via bare `\watch`. (Thanks: `Saif Hakim`_)

Bug fixes:
----------

* Pin the version of pygments to prevent breaking change

3.2.0
=====

Release date: 2021/08/23

Features:
---------

* Consider `update` queries destructive and issue a warning. Change
  `destructive_warning` setting to `all|moderate|off`, vs `true|false`. (#1239)
* Skip initial comment in .pg_session even if it doesn't start with '#'
* Include functions from schemas in search_path. (`Amjith Ramanujam`_)
* Easy way to show explain output under F5

Bug fixes:
----------

* Fix issue where `syntax_style` config value would not have any effect. (#1212)
* Fix crash because of not found `InputMode.REPLACE_SINGLE` with prompt-toolkit < 3.0.6
* Fix comments being lost in config when saving a named query. (#1240)
* Fix IPython magic for ipython-sql >= 0.4.0
* Fix pager not being used when output format is set to csv. (#1238)
* Add function literals random, generate_series, generate_subscripts
* Fix ANSI escape codes in first line make the cli choose expanded output incorrectly
* Fix pgcli crashing with virtual `pgbouncer` database. (#1093)

3.1.0
=====

Features:
---------

* Make the output more compact by removing the empty newline. (Thanks: `laixintao`_)
* Add support for using [pspg](https://github.com/okbob/pspg) as a pager (#1102)
* Update python version in Dockerfile
* Support setting color for null, string, number, keyword value
* Support Prompt Toolkit 2
* Support sqlparse 0.4.x
* Update functions, datatypes literals for auto-suggestion field
* Add suggestion for schema in function auto-complete

Bug fixes:
----------

* Minor typo fixes in `pgclirc`. (Thanks: `anthonydb`_)
* Fix for list index out of range when executing commands from a file (#1193). (Thanks: `Irina Truong`_)
* Move from `humanize` to `pendulum` for displaying query durations (#1015)
* More explicit error message when connecting using DSN alias and it is not found.

3.0.0
=====

Features:
---------

* Add `__main__.py` file to execute pgcli as a package directly (#1123).
* Add support for ANSI escape sequences for coloring the prompt (#1122).
* Add support for partitioned tables (relkind "p").
* Add support for `pg_service.conf` files
* Add config option show_bottom_toolbar.

Bug fixes:
----------

* Fix warning raised for using `is not` to compare string literal
* Close open connection in completion_refresher thread

Internal:
---------

* Drop Python2.7, 3.4, 3.5 support. (Thanks: `laixintao`_)
* Support Python3.8. (Thanks: `laixintao`_)
* Fix dead link in development guide. (Thanks: `BrownShibaDog`_)
* Upgrade python-prompt-toolkit to v3.0. (Thanks: `laixintao`_)


2.2.0:
======

Features:
---------

* Add `\\G` as a terminator to sql statements that will show the results in expanded mode. This feature is copied from mycli. (Thanks: `Amjith Ramanujam`_)
* Removed limit prompt and added automatic row limit on queries with no LIMIT clause (#1079) (Thanks: `Sebastian Janko`_)
* Function argument completions now take account of table aliases (#1048). (Thanks: `Owen Stephens`_)

Bug fixes:
----------

* Error connecting to PostgreSQL 12beta1 (#1058). (Thanks: `Irina Truong`_ and `Amjith Ramanujam`_)
* Empty query caused error message (#1019) (Thanks: `Sebastian Janko`_)
* History navigation bindings in multiline queries (#1004) (Thanks: `Pedro Ferrari`_)
* Can't connect to pgbouncer database (#1093). (Thanks: `Irina Truong`_)
* Fix broken multi-line history search (#1031). (Thanks: `Owen Stephens`_)
* Fix slow typing/movement when multi-line query ends in a semicolon (#994). (Thanks: `Owen Stephens`_)
* Fix for PQconninfo not available in libpq < 9.3 (#1110). (Thanks: `Irina Truong`_)

Internal:
---------

* Add optional but default squash merge request to PULL_REQUEST_TEMPLATE

2.1.1
=====

Bug fixes:
----------
* Escape switches to VI navigation mode when not canceling completion popup. (Thanks: `Nathan Verzemnieks`_)
* Allow application_name to be overridden. (Thanks: `raylu`_)
* Fix for "no attribute KeyringLocked" (#1040). (Thanks: `Irina Truong`_)
* Pgcli no longer works with password containing spaces (#1043). (Thanks: `Irina Truong`_)
* Load keyring only when keyring is enabled in the config file (#1041). (Thanks: `Zhaolong Zhu`_)
* No longer depend on sqlparse as being less than 0.3.0 with the release of sqlparse 0.3.0. (Thanks: `VVelox`_)
* Fix the broken support for pgservice . (Thanks: `Xavier Francisco`_)
* Connecting using socket is broken in current master. (#1053). (Thanks: `Irina Truong`_)
* Allow usage of newer versions of psycopg2 (Thanks: `Telmo "Trooper"`_)
* Update README in alignment with the usage of newer versions of psycopg2 (Thanks: `Alexander Zawadzki`_)

Internal:
---------

* Add python 3.7 to travis build matrix. (Thanks: `Irina Truong`_)
* Apply `black` to code. (Thanks: `Irina Truong`_)

2.1.0
=====

Features:
---------

* Keybindings for closing the autocomplete list. (Thanks: `easteregg`_)
* Reconnect automatically when server closes connection. (Thanks: `Scott Brenstuhl`_)

Bug fixes:
----------
* Avoid error message on the server side if hstore extension is not installed in the current database (#991). (Thanks: `Marcin Cieślak`_)
* All pexpect submodules have been moved into the pexpect package as of version 3.0. Use pexpect.TIMEOUT (Thanks: `Marcin Cieślak`_)
* Resizing pgcli terminal kills the connection to postgres in python 2.7 (Thanks: `Amjith Ramanujam`_)
* Fix crash retrieving server version with ``--single-connection``. (Thanks: `Irina Truong`_)
* Cannot quit application without reconnecting to database (#1014). (Thanks: `Irina Truong`_)
* Password authentication failed for user "postgres" when using non-default password (#1020). (Thanks: `Irina Truong`_)

Internal:
---------

* (Fixup) Clean up and add behave logging. (Thanks: `Marcin Cieślak`_, `Dick Marinus`_)
* Override VISUAL environment variable for behave tests. (Thanks: `Marcin Cieślak`_)
* Remove build dir before running sdist, remove stray files from wheel distribution. (Thanks: `Dick Marinus`_)
* Fix unit tests, unhashable formatted text since new python prompttoolkit  version. (Thanks: `Dick Marinus`_)

2.0.2:
======

Features:
---------

* Allows passing the ``-u`` flag to specify a username. (Thanks: `Ignacio Campabadal`_)
* Fix for lag in v2 (#979). (Thanks: `Irina Truong`_)
* Support for multihost connection string that is convenient if you have postgres cluster. (Thanks: `Mikhail Elovskikh`_)

Internal:
---------

* Added tests for special command completion. (Thanks: `Amjith Ramanujam`_)

2.0.1:
======

Bug fixes:
----------

* Tab press on an empty line increases the indentation instead of triggering
  the auto-complete pop-up. (Thanks: `Artur Balabanov`_)
* Fix for loading/saving named queries from provided config file (#938). (Thanks: `Daniel Egger`_)
* Set default port in `connect_uri` when none is given. (Thanks: `Daniel Egger`_)
* Fix for error listing databases (#951). (Thanks: `Irina Truong`_)
* Enable Ctrl-Z to suspend the app (Thanks: `Amjith Ramanujam`_).
* Fix StopIteration exception raised at runtime for Python 3.7 (Thanks: `Amjith Ramanujam`_).

Internal:
---------

* Clean up and add behave logging. (Thanks: `Dick Marinus`_)
* Require prompt_toolkit>=2.0.6. (Thanks: `Dick Marinus`_)
* Improve development guide. (Thanks: `Ignacio Campabadal`_)

2.0.0:
======

* Update to ``prompt-toolkit`` 2.0. (Thanks: `Jonathan Slenders`_, `Dick Marinus`_, `Irina Truong`_)

1.11.0
======

Features:
---------

* Respect `\pset pager on` and use pager when output is longer than terminal height (Thanks: `Max Rothman`_)

1.10.3
======

Bug fixes:
----------

* Adapt the query used to get functions metadata to PG11 (#919). (Thanks: `Lele Gaifax`_).
* Fix for error retrieving version in Redshift (#922). (Thanks: `Irina Truong`_)
* Fix for keyring not disabled properly (#920). (Thanks: `Irina Truong`_)

1.10.2
======

Features:
---------

* Make `keyring` optional (Thanks: `Dick Marinus`_)

1.10.1
======

Bug fixes:
----------

* Fix for missing keyring. (Thanks: `Kenny Do`_)
* Fix for "-l" Flag Throws Error (#909). (Thanks: `Irina Truong`_)

1.10.0
======

Features:
---------
* Add quit commands to the completion menu. (Thanks: `Jason Ribeiro`_)
* Add table formats to ``\T`` completion. (Thanks: `Jason Ribeiro`_)
* Support `\\ev``, ``\ef`` (#754). (Thanks: `Catherine Devlin`_)
* Add ``application_name`` to help identify pgcli connection to database (issue #868) (Thanks: `François Pietka`_)
* Add `--user` option, duplicate of `--username`, the same cli option like `psql` (Thanks: `Alexandr Korsak`_)

Internal changes:
-----------------

* Mark tests requiring a running database server as dbtest (Thanks: `Dick Marinus`_)
* Add an is_special command flag to MetaQuery (Thanks: `Rishi Ramraj`_)
* Ported Destructive Warning from mycli.
* Refactor Destructive Warning behave tests (Thanks: `Dick Marinus`_)

Bug Fixes:
----------
* Disable pager when using \watch (#837). (Thanks: `Jason Ribeiro`_)
* Don't offer to reconnect when we can't change a param in realtime (#807). (Thanks: `Amjith Ramanujam`_ and `Saif Hakim`_)
* Make keyring optional. (Thanks: `Dick Marinus`_)
* Fix ipython magic connection (#891). (Thanks: `Irina Truong`_)
* Fix not enough values to unpack. (Thanks: `Matthieu Guilbert`_)
* Fix unbound local error when destructive_warning is false. (Thanks: `Matthieu Guilbert`_)
* Render tab characters as 4 spaces instead of `^I`. (Thanks: `Artur Balabanov`_)

1.9.1:
======

Features:
---------

* Change ``\h`` format string in prompt to only return the first part of the hostname,
  up to the first '.' character.  Add ``\H`` that returns the entire hostname (#858).
  (Thanks: `Andrew Kuchling`_)
* Add Color of table by parameter. The color of table is function of syntax style

Internal changes:
-----------------

* Add tests, AUTHORS and changelog.rst to release. (Thanks: `Dick Marinus`_)

Bug Fixes:
----------
* Fix broken pgcli --list command line option (#850). (Thanks: `Dmitry B`_)

1.9.0
=====

Features:
---------

* manage pager by \pset pager and add enable_pager to the config file (Thanks: `Frederic Aoustin`_).
* Add support for `\T` command to change format output. (Thanks: `Frederic Aoustin`_).
* Add option list-dsn (Thanks: `Frederic Aoustin`_).


Internal changes:
-----------------

* Removed support for Python 3.3. (Thanks: `Irina Truong`_)

1.8.2
=====

Features:
---------

* Use other prompt (prompt_dsn) when connecting using --dsn parameter. (Thanks: `Marcin Sztolcman`_)
* Include username into password prompt. (Thanks: `Bojan Delić`_)

Internal changes:
-----------------
* Use temporary dir as config location in tests. (Thanks: `Dmitry B`_)
* Fix errors in the ``tee`` test (#795 and #797). (Thanks: `Irina Truong`_)
* Increase timeout for quitting pgcli. (Thanks: `Dick Marinus`_)

Bug Fixes:
----------
* Do NOT quote the database names in the completion menu (Thanks: `Amjith Ramanujam`_)
* Fix error in ``unix_socket_directories`` (#805). (Thanks: `Irina Truong`_)
* Fix the --list command line option tries to connect to 'personal' DB (#816). (Thanks: `Isank`_)

1.8.1
=====

Internal changes:
-----------------
* Remove shebang and git execute permission from pgcli/main.py. (Thanks: `Dick Marinus`_)
* Require cli_helpers 0.2.3 (fix #791). (Thanks: `Dick Marinus`_)

1.8.0
=====

Features:
---------

* Add fish-style auto-suggestion from history. (Thanks: `Amjith Ramanujam`_)
* Improved formatting of arrays in output (Thanks: `Joakim Koljonen`_)
* Don't quote identifiers that are non-reserved keywords. (Thanks: `Joakim Koljonen`_)
* Remove the ``...`` in the continuation prompt and use empty space instead. (Thanks: `Amjith Ramanujam`_)
* Add \conninfo and handle more parameters with \c (issue #716) (Thanks: `François Pietka`_)

Internal changes:
-----------------
* Preliminary work for a future change in outputting results that uses less memory. (Thanks: `Dick Marinus`_)
* Remove import workaround for OrderedDict, required for python < 2.7. (Thanks: `Andrew Speed`_)
* Use less memory when formatting results for display (Thanks: `Dick Marinus`_).
* Port auto_vertical feature test from mycli to pgcli. (Thanks: `Dick Marinus`_)
* Drop wcwidth dependency (Thanks: `Dick Marinus`_)

Bug Fixes:
----------

* Fix the way we get host when using DSN (issue #765) (Thanks: `François Pietka`_)
* Add missing keyword COLUMN after DROP (issue #769) (Thanks: `François Pietka`_)
* Don't include arguments in function suggestions for backslash commands (Thanks: `Joakim Koljonen`_)
* Optionally use POSTGRES_USER, POSTGRES_HOST POSTGRES_PASSWORD from environment (Thanks: `Dick Marinus`_)

1.7.0
=====

* Refresh completions after `COMMIT` or `ROLLBACK`. (Thanks: `Irina Truong`_)
* Fixed DSN aliases not being read from custom pgclirc (issue #717). (Thanks: `Irina Truong`_).
* Use dbcli's Homebrew tap for installing pgcli on macOS (issue #718) (Thanks: `Thomas Roten`_).
* Only set `LESS` environment variable if it's unset. (Thanks: `Irina Truong`_)
* Quote schema in `SET SCHEMA` statement (issue #469) (Thanks: `Irina Truong`_)
* Include arguments in function suggestions (Thanks: `Joakim Koljonen`_)
* Use CLI Helpers for pretty printing query results (Thanks: `Thomas Roten`_).
* Skip serial columns when expanding * for `INSERT INTO foo(*` (Thanks: `Joakim Koljonen`_).
* Command line option to list databases (issue #206) (Thanks: `François Pietka`_)

1.6.0
=====

Features:
---------
* Add time option for prompt (Thanks: `Gustavo Castro`_)
* Suggest objects from all schemas (not just those in search_path) (Thanks: `Joakim Koljonen`_)
* Casing for column headers (Thanks: `Joakim Koljonen`_)
* Allow configurable character to be used for multi-line query continuations. (Thanks: `Owen Stephens`_)
* Completions after ORDER BY and DISTINCT now take account of table aliases. (Thanks: `Owen Stephens`_)
* Narrow keyword candidates based on previous keyword. (Thanks: `Étienne Bersac`_)
* Opening an external editor will edit the last-run query. (Thanks: `Thomas Roten`_)
* Support query options in postgres URIs such as ?sslcert=foo.pem (Thanks: `Alexander Schmolck`_)

Bug fixes:
----------
* Fixed external editor bug (issue #668). (Thanks: `Irina Truong`_).
* Standardize command line option names. (Thanks: `Russell Davies`_)
* Improve handling of ``lock_not_available`` error (issue #700). (Thanks: `Jackson Popkin <https://github.com/jdpopkin>`_)
* Fixed user option precedence (issue #697). (Thanks: `Irina Truong`_).

Internal changes:
-----------------
* Run pep8 checks in travis (Thanks: `Irina Truong`_).
* Add pager wrapper for behave tests (Thanks: `Dick Marinus`_).
* Behave quit pgcli nicely (Thanks: `Dick Marinus`_).
* Behave test source command (Thanks: `Dick Marinus`_).
* Behave fix clean up. (Thanks: `Dick Marinus`_).
* Test using behave the tee command (Thanks: `Dick Marinus`_).
* Behave remove boiler plate code (Thanks: `Dick Marinus`_).
* Behave fix pgspecial update (Thanks: `Dick Marinus`_).
* Add behave to tox (Thanks: `Dick Marinus`_).

1.5.1
=====

Features:
---------
* Better suggestions when editing functions (Thanks: `Joakim Koljonen`_)
* Command line option for ``--less-chatty``. (Thanks: `tk`_)
* Added ``MATERIALIZED VIEW`` keywords. (Thanks: `Joakim Koljonen`_).

Bug fixes:
----------

* Support unicode chars in expanded mode. (Thanks: `Amjith Ramanujam`_)
* Fixed "set_session cannot be used inside a transaction" when using dsn. (Thanks: `Irina Truong`_).

1.5.0
=====

Features:
---------
* Upgraded pgspecial to 1.7.0. (See `pgspecial changelog <https://github.com/dbcli/pgspecial/blob/master/changelog.rst>`_ for list of fixes)
* Add a new config setting to allow expandable mode (Thanks: `Jonathan Boudreau <https://github.com/AGhost-7>`_)
* Make pgcli prompt width short when the prompt is too long (Thanks: `Jonathan Virga <https://github.com/jnth>`_)
* Add additional completion for ``ALTER`` keyword (Thanks: `Darik Gamble`_)
* Make the menu size configurable. (Thanks `Darik Gamble`_)

Bug Fixes:
----------
* Handle more connection failure cases. (Thanks: `Amjith Ramanujam`_)
* Fix the connection failure issues with latest psycopg2. (Thanks: `Amjith Ramanujam`_)

Internal Changes:
-----------------

* Add testing for Python 3.5 and 3.6. (Thanks: `Amjith Ramanujam`_)

1.4.0
=====

Features:
---------

* Search table suggestions using initialisms. (Thanks: `Joakim Koljonen`_).
* Support for table-qualifying column suggestions. (Thanks: `Joakim Koljonen`_).
* Display transaction status in the toolbar. (Thanks: `Joakim Koljonen`_).
* Display vi mode in the toolbar. (Thanks: `Joakim Koljonen`_).
* Added --prompt option. (Thanks: `Irina Truong`_).

Bug Fixes:
----------

* Fix scoping for columns from CTEs. (Thanks: `Joakim Koljonen`_)
* Fix crash after `with`. (Thanks: `Joakim Koljonen`_).
* Fix issue #603 (`\i` raises a TypeError). (Thanks: `Lele Gaifax`_).


Internal Changes:
-----------------

* Set default data_formatting to nothing. (Thanks: `Amjith Ramanujam`_).
* Increased minimum prompt_toolkit requirement to 1.0.9. (Thanks: `Irina Truong`_).


1.3.1
=====

Bug Fixes:
----------
* Fix a crashing bug due to sqlparse upgrade. (Thanks: `Darik Gamble`_)


1.3.0
=====

IMPORTANT: Python 2.6 is not officially supported anymore.

Features:
---------
* Add delimiters to displayed numbers. This can be configured via the config file. (Thanks: `Sergii`_).
* Fix broken 'SHOW ALL' in redshift. (Thanks: `Manuel Barkhau`_).
* Support configuring keyword casing preferences. (Thanks: `Darik Gamble`_).
* Add a new multi_line_mode option in config file. The values can be `psql` or `safe`. (Thanks: `Joakim Koljonen`_)
  Setting ``multi_line_mode = safe`` will make sure that a query will only be executed when Alt+Enter is pressed.

Bug Fixes:
----------
* Fix crash bug with leading parenthesis. (Thanks: `Joakim Koljonen`_).
* Remove cumulative addition of timing data. (Thanks: `Amjith Ramanujam`_).
* Handle unrecognized keywords gracefully. (Thanks: `Darik Gamble`_)
* Use raw strings in regex specifiers. This preemptively fixes a crash in Python 3.6. (Thanks `Lele Gaifax`_)

Internal Changes:
-----------------
* Set sqlparse version dependency to >0.2.0, <0.3.0. (Thanks: `Amjith Ramanujam`_).
* XDG_CONFIG_HOME support for config file location. (Thanks: `Fabien Meghazi`_).
* Remove Python 2.6 from travis test suite. (Thanks: `Amjith Ramanujam`_)

1.2.0
=====

Features:
---------

* Add more specifiers to pgcli prompt. (Thanks: `Julien Rouhaud`_).
   ``\p`` for port info ``\#`` for super user and ``\i`` for pid.
* Add `\watch` command to periodically execute a command. (Thanks: `Stuart Quin`_).
    ``> SELECT * FROM django_migrations; \watch 1  /* Runs the command every second */``
* Add command-line option --single-connection to prevent pgcli from using multiple connections. (Thanks: `Joakim Koljonen`_).
* Add priority to the suggestions to sort based on relevance. (Thanks: `Joakim Koljonen`_).
* Configurable null format via the config file. (Thanks: `Adrian Dries`_).
* Add support for CTE aware auto-completion. (Thanks: `Darik Gamble`_).
* Add host and user information to default pgcli prompt. (Thanks: `Lim H`_).
* Better scoping for tables in insert statements to improve suggestions. (Thanks: `Joakim Koljonen`_).

Bug Fixes:
----------

* Do not install setproctitle on cygwin. (Thanks: `Janus Troelsen`_).
* Work around sqlparse crashing after AS keyword. (Thanks: `Joakim Koljonen`_).
* Fix a crashing bug with named queries. (Thanks: `Joakim Koljonen`_).
* Replace  timestampz alias since AWS Redshift does not support it. (Thanks: `Tahir Butt`_).
* Prevent pgcli from hanging indefinitely when Postgres instance is not running. (Thanks: `Darik Gamble`_)

Internal Changes:
-----------------

* Upgrade to sqlparse-0.2.0. (Thanks: `Tiziano Müller`_).
* Upgrade to pgspecial 1.6.0. (Thanks: `Stuart Quin`_).


1.1.0
=====

Features:
---------

* Add support for ``\db`` command. (Thanks: `Irina Truong`_)

Bugs:
-----

* Fix the crash at startup while parsing the postgres url with port number. (Thanks: `Eric Wald`_)
* Fix the crash with Redshift databases. (Thanks: `Darik Gamble`_)

Internal Changes:
-----------------

* Upgrade pgspecial to 1.5.0 and above.

1.0.0
=====

Features:
---------

* Upgrade to prompt-toolkit 1.0.0. (Thanks: `Jonathan Slenders`_).
* Add support for `\o` command to redirect query output to a file. (Thanks: `Tim Sanders`_).
* Add `\i` path completion. (Thanks: `Anthony Lai`_).
* Connect to a dsn saved in config file. (Thanks: `Rodrigo Ramírez Norambuena`_).
* Upgrade sqlparse requirement to version 0.1.19. (Thanks: `Fernando L. Canizo`_).
* Add timestamptz to DATE custom extension. (Thanks: `Fernando Mora`_).
* Ensure target dir exists when copying config. (Thanks: `David Szotten`_).
* Handle dates that fall in the B.C. range. (Thanks: `Stuart Quin`_).
* Pager is selected from config file or else from environment variable. (Thanks: `Fernando Mora`_).
* Add support for Amazon Redshift. (Thanks: `Timothy Cleaver`_).
* Add support for Postgres 8.x. (Thanks: `Timothy Cleaver`_ and `Darik Gamble`_)
* Don't error when completing parameter-less functions. (Thanks: `David Szotten`_).
* Concat and return all available notices. (Thanks: `Stuart Quin`_).
* Handle unicode in record type. (Thanks: `Amjith Ramanujam`_).
* Added humanized time display. Connect #396. (Thanks: `Irina Truong`_).
* Add EXPLAIN keyword to the completion list. (Thanks: `Amjith Ramanujam`_).
* Added sdist upload to release script. (Thanks: `Irina Truong`_).
* Sort completions based on most recently used. (Thanks: `Darik Gamble`)
* Expand '*' into column list during completion. This can be triggered by hitting `<tab>` after the '*' character in the sql while typing. (Thanks: `Joakim Koljonen`_)
* Add a limit to the warning about too many rows. This is controlled by a new config value in ~/.config/pgcli/config. (Thanks: `Anže Pečar`_)
* Improved argument list in function parameter completions. (Thanks: `Joakim Koljonen`_)
* Column suggestions after the COLUMN keyword. (Thanks: `Darik Gamble`_)
* Filter out trigger implemented functions from the suggestion list. (Thanks: `Daniel Rocco`_)
* State of the art JOIN clause completions that suggest entire conditions. (Thanks: `Joakim Koljonen`_)
* Suggest fully formed JOIN clauses based on Foreign Key relations. (Thanks: `Joakim Koljonen`_)
* Add support for `\dx` meta command to list the installed extensions. (Thanks: `Darik Gamble`_)
* Add support for `\copy` command. (Thanks: `Catherine Devlin`_)

Bugs:
-----

* Fix bug where config writing would leave a '~' dir. (Thanks: `James Munson`_).
* Fix auto-completion breaking for table names with caps. (Thanks: `Anthony Lai`_).
* Fix lexical ordering bug. (Thanks: `Anthony Lai`_).
* Use lexical order to break ties when fuzzy matching. (Thanks: `Daniel Rocco`_).
* Fix the bug in auto-expand mode when there are no rows to display. (Thanks: `Amjith Ramanujam`_).
* Fix broken `\i` after #395. (Thanks: `David Szotten`_).
* Fix multi-way joins in auto-completion. (Thanks: `Darik Gamble`_)
* Display null values as <null> in expanded output. (Thanks: `Amjith Ramanujam`_).
* Robust support for Postgres version less than 9.x. (Thanks: `Darik Gamble`_)

Internal Changes:
-----------------

* Update config file location in README. (Thanks: `Ari Summer`_).
* Explicitly add wcwidth as a dependency. (Thanks: `Amjith Ramanujam`_).
* Add tests for the format_output. (Thanks: `Amjith Ramanujam`_).
* Lots of tests for pgcompleter. (Thanks: `Darik Gamble`_).
* Update pgspecial dependency to 1.4.0.


0.20.1
======

Bug Fixes:
----------
* Fixed logging in Windows by switching the location of log and history file based on OS. (Thanks: Amjith, `Darik Gamble`_, `Irina Truong`_).

0.20.0
======

Features:
---------
* Perform auto-completion refresh in background. (Thanks: Amjith, `Darik Gamble`_, `Irina Truong`_).
  When the auto-completion entries are refreshed, the update now happens in a
  background thread. This means large databases with thousands of tables are
  handled without blocking.
* Add ``CONCURRENTLY`` to keyword completion. (Thanks: `Johannes Hoff`_).
* Add support for ``\h`` command. (Thanks: `Stuart Quin`_).
  This is a huge deal. Users can now get help on an SQL command by typing:
  ``\h COMMAND_NAME`` in the pgcli prompt.
* Add support for ``\x auto``. (Thanks: `Stuart Quin`_).
  ``\\x auto`` will automatically switch to expanded mode if the output is wider
  than the display window.
* Don't hide functions from pg_catalog. (Thanks: `Darik Gamble`_).
* Suggest set-returning functions as tables. (Thanks: `Darik Gamble`_).
  Functions that return table like results will now be suggested in places of tables.
* Suggest fields from functions used as tables. (Thanks: `Darik Gamble`_).
* Using ``pgspecial`` as a separate module. (Thanks: `Irina Truong`_).
* Make "enter" key behave as "tab" key when the completion menu is displayed. (Thanks: `Matheus Rosa`_).
* Support different error-handling options when running multiple queries. (Thanks: `Darik Gamble`_).
  When ``on_error = STOP`` in the config file, pgcli will abort execution if one of the queries results in an error.
* Hide the password displayed in the process name in ``ps``. (Thanks: `Stuart Quin`_)

Bug Fixes:
----------
* Fix the ordering bug in `\\d+` display, this bug was displaying the wrong table name in the reference. (Thanks: `Tamas Boros`_).
* Only show expanded layout if valid list of headers provided. (Thanks: `Stuart Quin`_).
* Fix suggestions in compound join clauses. (Thanks: `Darik Gamble`_).
* Fix completion refresh in multiple query scenario. (Thanks: `Darik Gamble`_).
* Fix the broken timing information.
* Fix the removal of whitespaces in the output. (Thanks: `Jacek Wielemborek`_)
* Fix PyPI badge. (Thanks: `Artur Dryomov`_).

Improvements:
-------------
* Move config file to `~/.config/pgcli/config` instead of `~/.pgclirc` (Thanks: `inkn`_).
* Move literal definitions to standalone JSON files. (Thanks: `Darik Gamble`_).

Internal Changes:
-----------------
* Improvements to integration tests to make it more robust. (Thanks: `Irina Truong`_).

0.19.2
======

Features:
---------

* Autocompletion for database name in \c and \connect. (Thanks: `Darik Gamble`_).
* Improved multiline query support by correctly handling open quotes. (Thanks: `Darik Gamble`_).
* Added \pager command.
* Enhanced \i to run multiple queries and display the results for each of them
* Added keywords to suggestions after WHERE clause.
* Enabled autocompletion in named queries. (Thanks: `Irina Truong`_).
* Path to .pgclirc can be specified in command line. (Thanks: `Irina Truong`_).
* Added support for pg_service_conf file. (Thanks: `Irina Truong`_).
* Added custom styles. (Contributor: `Darik Gamble`_).

Internal Changes:
-----------------

* More completer test cases. (Thanks: `Darik Gamble`_).
* Updated sqlparse version from 0.1.14 to 0.1.16. (Thanks: `Darik Gamble`_).
* Upgraded to prompt_toolkit 0.46. (Thanks: `Jonathan Slenders`_).

BugFixes:
---------
* Fixed the completer crashing on invalid SQL. (Thanks: `Darik Gamble`_).
* Fixed unicode issues, updated tests and fixed broken tests.

0.19.1
======

BugFixes:
---------

* Fix an autocompletion bug that was crashing the completion engine when unknown keyword is entered. (Thanks: `Darik Gamble`_)

0.19.0
======

Features:
---------

* Wider completion menus can be enabled via the config file. (Thanks: `Jonathan Slenders`_)

  Open the config file (~/.pgclirc) and check if you have
  ``wider_completion_menu`` option available. If not add it in and set it to
  ``True``.

* Completion menu now has metadata information such as schema, table, column, view, etc., next to the suggestions. (Thanks: `Darik Gamble`_)
* Customizable history file location via config file. (Thanks: `Çağatay Yüksel`_)

  Add this line to your config file (~/.pgclirc) to customize where to store the history file.

::

  history_file = /path/to/history/file

* Add support for running queries from a file using ``\i`` special command. (Thanks: `Michael Kaminsky`_)

BugFixes:
---------

* Always use utf-8 for database encoding regardless of the default encoding used by the database.
* Fix for None dereference on ``\d schemaname.`` with sequence. (Thanks: `Nathan Jhaveri`_)
* Fix a crashing bug in the autocompletion engine for some ``JOIN`` queries.
* Handle KeyboardInterrupt in pager and not quit pgcli as a consequence.

Internal Changes:
-----------------

* Added more behaviorial tests (Thanks: `Irina Truong`_)
* Added code coverage to the tests. (Thanks: `Irina Truong`_)
* Run behaviorial tests as part of TravisCI (Thanks: `Irina Truong`_)
* Upgraded prompt_toolkit version to 0.45 (Thanks: `Jonathan Slenders`_)
* Update the minimum required version of click to 4.1.

0.18.0
======

Features:
---------

* Add fuzzy matching for the table names and column names.

  Matching very long table/column names are now easier with fuzzy matching. The
  fuzzy match works like the fuzzy open in SublimeText or Vim's Ctrl-P plugin.

  eg: Typing ``djmv`` will match `django_migration_views` since it is able to
  match parts of the input to the full table name.

* Change the timing information to seconds.

  The ``Command Time`` and ``Format Time`` are now displayed in seconds instead
  of a unitless number displayed in scientific notation.

* Support for named queries (favorite queries). (Thanks: `Brett Atoms`_)

  Frequently typed queries can now be saved and recalled using a name using
  newly added special commands (``\n[+]``, ``\ns``, ``\nd``).

  eg:

::

    # Save a query
    pgcli> \ns simple select * from foo
    saved

    # List all saved queries
    pgcli> \n+

    # Execute a saved query
    pgcli> \n simple

    # Delete a saved query
    pgcli> \nd simple

* Pasting queries into the pgcli repl is orders of magnitude faster. (Thanks: `Jonathan Slenders`_)

* Add support for PGPASSWORD environment variable to pass the password for the
  postgres database. (Thanks: `Irina Truong`_)

* Add the ability to manually refresh autocompletions by typing ``\#`` or
  ``\refresh``. This is useful if the database was updated by an external means
  and you'd like to refresh the auto-completions to pick up the new change.

Bug Fixes:
----------

* Fix an error when running ``\d table_name`` when running on a table with rules. (Thanks: `Ali Kargın`_)
* Fix a pgcli crash when entering non-ascii characters in Windows. (Thanks: `Darik Gamble`_, `Jonathan Slenders`_)
* Faster rendering of expanded mode output by making the horizontal separator a fixed length string.
* Completion suggestions for the ``\c`` command are not auto-escaped by default.

Internal Changes:
-----------------

* Complete refactor of handling the back-slash commands.
* Upgrade prompt_toolkit to 0.42. (Thanks: `Jonathan Slenders`_)
* Change the config file management to use ConfigObj.(Thanks: `Brett Atoms`_)
* Add integration tests using ``behave``. (Thanks: `Irina Truong`_)

0.17.0
======

Features:
---------

* Add support for auto-completing view names. (Thanks: `Darik Gamble`_)
* Add support for building RPM and DEB packages. (Thanks: dp_)
* Add subsequence matching for completion. (Thanks: `Daniel Rocco`_)
  Previously completions only matched a table name if it started with the
  partially typed word. Now completions will match even if the partially typed
  word is in the middle of a suggestion.
  eg: When you type 'mig', 'django_migrations' will be suggested.
* Completion for built-in tables and temporary tables are suggested after entering a prefix of ``pg_``. (Thanks: `Darik Gamble`_)
* Add place holder doc strings for special commands that are planned for implementation. (Thanks: `Irina Truong`_)
* Updated version of prompt_toolkit, now matching braces are highlighted. (Thanks: `Jonathan Slenders`_)
* Added support of ``\\e`` command. Queries can be edited in an external editor. (Thanks: `Irina Truong`_)
  eg: When you type ``SELECT * FROM \e`` it will be opened in an external editor.
* Add special command ``\dT`` to show datatypes. (Thanks: `Darik Gamble`_)
* Add auto-completion support for datatypes in CREATE, SELECT etc. (Thanks: `Darik Gamble`_)
* Improve the auto-completion in WHERE clause with logical operators. (Thanks: `Darik Gamble`_)
*

Bug Fixes:
----------

* Fix the table formatting while printing multi-byte characters (Chinese, Japanese etc). (Thanks: `蔡佳男`_)
* Fix a crash when pg_catalog was present in search path. (Thanks: `Darik Gamble`_)
* Fixed a bug that broke `\\e` when prompt_tookit was updated. (Thanks: `François Pietka`_)
* Fix the display of triggers as shown in the ``\d`` output. (Thanks: `Dimitar Roustchev`_)
* Fix broken auto-completion for INNER JOIN, LEFT JOIN etc. (Thanks: `Darik Gamble`_)
* Fix incorrect super() calls in pgbuffer, pgtoolbar and pgcompleter. No change in functionality but protects against future problems. (Thanks: `Daniel Rocco`_)
* Add missing schema completion for CREATE and DROP statements. (Thanks: `Darik Gamble`_)
* Minor fixes around cursor cleanup.

0.16.3
======

Bug Fixes:
----------
* Add more SQL keywords for auto-complete suggestion.
* Messages raised as part of stored procedures are no longer ignored.
* Use postgres flavored syntax highlighting instead of generic ANSI SQL.

0.16.2
======

Bug Fixes:
----------
* Fix a bug where the schema qualifier was ignored by the auto-completion.
  As a result the suggestions for tables vs functions are cleaner. (Thanks: `Darik Gamble`_)
* Remove scientific notation when formatting large numbers. (Thanks: `Daniel Rocco`_)
* Add the FUNCTION keyword to auto-completion.
* Display NULL values as <null> instead of empty strings.
* Fix the completion refresh when ``\connect`` is executed.

0.16.1
======

Bug Fixes:
----------
* Fix unicode issues with hstore.
* Fix a silent error when database is changed using \\c.

0.16.0
======

Features:
---------
* Add \ds special command to show sequences.
* Add Vi mode for keybindings. This can be enabled by adding 'vi = True' in ~/.pgclirc. (Thanks: `Jay Zeng`_)
* Add a -v/--version flag to pgcli.
* Add completion for TEMPLATE keyword and smart-completion for
  'CREATE DATABASE blah WITH TEMPLATE <tab>'. (Thanks: `Daniel Rocco`_)
* Add custom decoders to json/jsonb to emulate the behavior of psql. This
  removes the unicode prefix (eg: u'Éowyn') in the output. (Thanks: `Daniel Rocco`_)
* Add \df special command to show functions. (Thanks: `Darik Gamble`_)
* Make suggestions for special commands smarter. eg: \dn - only suggests schemas. (Thanks: `Darik Gamble`_)
* Print out the version and other meta info about pgcli at startup.

Bug Fixes:
----------
* Fix a rare crash caused by adding new schemas to a database. (Thanks: `Darik Gamble`_)
* Make \dt command honor the explicit schema specified in the arg. (Thanks: `Darik Gamble`_)
* Print BIGSERIAL type as Integer instead of Float.
* Show completions for special commands at the beginning of a statement. (Thanks: `Daniel Rocco`_)
* Allow special commands to work in a multi-statement case where multiple sql
  statements are separated by semi-colon in the same line.

0.15.4
======
* Dummy version to replace accidental PyPI entry deletion.

0.15.3
======
* Override the LESS options completely instead of appending to it.

0.15.2
======
* Revert back to using psycopg2 as the postgres adapter. psycopg2cffi fails for some tests in Python 3.

0.15.0
======

Features:
---------
* Add syntax color styles to config.
* Add auto-completion for COPY statements.
* Change Postgres adapter to psycopg2cffi, to make it PyPy compatible.
  Now pgcli can be run by PyPy.

Bug Fixes:
----------
* Treat boolean values as strings instead of ints.
* Make \di, \dv and \dt to be schema aware. (Thanks: `Darik Gamble`_)
* Make column name display unicode compatible.

0.14.0
======

Features:
---------
* Add alias completion support to ON keyword. (Thanks: `Irina Truong`_)
* Add LIMIT keyword to completion.
* Auto-completion for Postgres schemas. (Thanks: `Darik Gamble`_)
* Better unicode handling for datatypes, dbname and roles.
* Add \timing command to time the sql commands.
  This can be set via config file (~/.pgclirc) using `timing = True`.
* Add different table styles for displaying output.
  This can be changed via config file (~/.pgclirc) using `table_format = fancy_grid`.
* Add confirmation before printing results that have more than 1000 rows.

Bug Fixes:
----------

* Performance improvements to expanded view display (\x).
* Cast bytea files to text while displaying. (Thanks: `Daniel Rocco`_)
* Added a list of reserved words that should be auto-escaped.
* Auto-completion is now case-insensitive.
* Fix the broken completion for multiple sql statements. (Thanks: `Darik Gamble`_)

0.13.0
======

Features:
---------

* Add -d/--dbname option to the commandline.
  eg: pgcli -d database
* Add the username as an argument after the database.
  eg: pgcli dbname user

Bug Fixes:
----------
* Fix the crash when \c fails.
* Fix the error thrown by \d when triggers are present.
* Fix broken behavior on \?. (Thanks: `Darik Gamble`_)

0.12.0
======

Features:
---------

* Upgrade to prompt_toolkit version 0.26 (Thanks: https://github.com/macobo)
  * Adds Ctrl-left/right to move the cursor one word left/right respectively.
  * Internal API changes.
* IPython integration through `ipython-sql`_ (Thanks: `Darik Gamble`_)
  * Add an ipython magic extension to embed pgcli inside ipython.
  * Results from a pgcli query are sent back to ipython.
* Multiple sql statements in the same line separated by semi-colon. (Thanks: https://github.com/macobo)

.. _`ipython-sql`: https://github.com/catherinedevlin/ipython-sql

Bug Fixes:
----------

* Fix 'message' attribute not found exception in Python 3. (Thanks: https://github.com/GMLudo)
* Use the database username as the database name instead of defaulting to OS username. (Thanks: https://github.com/fpietka)
* Auto-completion for auto-escaped column/table names.
* Fix i-reverse-search to work in prompt_toolkit version 0.26.

0.11.0
======

Features:
---------

* Add \dn command. (Thanks: https://github.com/CyberDem0n)
* Add \x command. (Thanks: https://github.com/stuartquin)
* Auto-escape special column/table names. (Thanks: https://github.com/qwesda)
* Cancel a command using Ctrl+C. (Thanks: https://github.com/macobo)
* Faster startup by reading all columns and tables in a single query. (Thanks: https://github.com/macobo)
* Improved psql compliance with env vars and password prompting. (Thanks: `Darik Gamble`_)
* Pressing Alt-Enter will introduce a line break. This is a way to break up the query into multiple lines without switching to multi-line mode. (Thanks: https://github.com/pabloab).

Bug Fixes:
----------
* Fix the broken behavior of \d+. (Thanks: https://github.com/macobo)
* Fix a crash during auto-completion. (Thanks: https://github.com/Erethon)
* Avoid losing pre_run_callables on error in editing.  (Thanks: https://github.com/catherinedevlin)

Improvements:
-------------
* Faster test runs on TravisCI. (Thanks: https://github.com/macobo)
* Integration tests with Postgres!! (Thanks: https://github.com/macobo)

.. _`Amjith Ramanujam`: https://blog.amjith.com
.. _`Andrew Kuchling`: https://github.com/akuchling
.. _`Darik Gamble`: https://github.com/darikg
.. _`Daniel Rocco`: https://github.com/drocco007
.. _`Jay Zeng`:  https://github.com/jayzeng
.. _`蔡佳男`: https://github.com/xalley
.. _dp: https://github.com/ceocoder
.. _`Jonathan Slenders`: https://github.com/jonathanslenders
.. _`Dimitar Roustchev`: https://github.com/droustchev
.. _`François Pietka`: https://github.com/fpietka
.. _`Ali Kargın`: https://github.com/sancopanco
.. _`Brett Atoms`: https://github.com/brettatoms
.. _`Nathan Jhaveri`: https://github.com/nathanjhaveri
.. _`Çağatay Yüksel`: https://github.com/cagatay
.. _`Michael Kaminsky`: https://github.com/mikekaminsky
.. _`inkn`: inkn
.. _`Johannes Hoff`: Johannes Hoff
.. _`Matheus Rosa`: Matheus Rosa
.. _`Artur Dryomov`: https://github.com/ming13
.. _`Stuart Quin`: https://github.com/stuartquin
.. _`Tamas Boros`: https://github.com/TamasNo1
.. _`Jacek Wielemborek`: https://github.com/d33tah
.. _`Rodrigo Ramírez Norambuena`: https://github.com/roramirez
.. _`Anthony Lai`: https://github.com/ajlai
.. _`Ari Summer`: Ari Summer
.. _`David Szotten`: David Szotten
.. _`Fernando L. Canizo`: Fernando L. Canizo
.. _`Tim Sanders`: https://github.com/Gollum999
.. _`Irina Truong`: https://github.com/j-bennet
.. _`James Munson`: https://github.com/jmunson
.. _`Fernando Mora`: https://github.com/fernandomora
.. _`Timothy Cleaver`: Timothy Cleaver
.. _`gtxx`: gtxx
.. _`Joakim Koljonen`: https://github.com/koljonen
.. _`Anže Pečar`: https://github.com/Smotko
.. _`Catherine Devlin`: https://github.com/catherinedevlin
.. _`Eric Wald`: https://github.com/eswald
.. _`avdd`: https://github.com/avdd
.. _`Adrian Dries`: Adrian Dries
.. _`Julien Rouhaud`: https://github.com/rjuju
.. _`Lim H`: Lim H
.. _`Tahir Butt`: Tahir Butt
.. _`Tiziano Müller`: https://github.com/dev-zero
.. _`Janus Troelsen`: https://github.com/ysangkok
.. _`Fabien Meghazi`: https://github.com/amigrave
.. _`Manuel Barkhau`: https://github.com/mbarkhau
.. _`Sergii`: https://github.com/foxyterkel
.. _`Lele Gaifax`: https://github.com/lelit
.. _`tk`: https://github.com/kanet77
.. _`Owen Stephens`: https://github.com/owst
.. _`Russell Davies`: https://github.com/russelldavies
.. _`Dick Marinus`: https://github.com/meeuw
.. _`Étienne Bersac`: https://github.com/bersace
.. _`Thomas Roten`: https://github.com/tsroten
.. _`Gustavo Castro`: https://github.com/gustavo-castro
.. _`Alexander Schmolck`: https://github.com/aschmolck
.. _`Andrew Speed`: https://github.com/AndrewSpeed
.. _`Dmitry B`: https://github.com/oxitnik
.. _`Marcin Sztolcman`: https://github.com/msztolcman
.. _`Isank`: https://github.com/isank
.. _`Bojan Delić`: https://github.com/delicb
.. _`Frederic Aoustin`: https://github.com/fraoustin
.. _`Jason Ribeiro`: https://github.com/jrib
.. _`Rishi Ramraj`: https://github.com/RishiRamraj
.. _`Matthieu Guilbert`: https://github.com/gma2th
.. _`Alexandr Korsak`: https://github.com/oivoodoo
.. _`Saif Hakim`: https://github.com/saifelse
.. _`Artur Balabanov`: https://github.com/arturbalabanov
.. _`Kenny Do`: https://github.com/kennydo
.. _`Max Rothman`: https://github.com/maxrothman
.. _`Daniel Egger`: https://github.com/DanEEStar
.. _`Ignacio Campabadal`: https://github.com/igncampa
.. _`Mikhail Elovskikh`: https://github.com/wronglink
.. _`Marcin Cieślak`: https://github.com/saper
.. _`Scott Brenstuhl`: https://github.com/808sAndBR
.. _`easteregg`: https://github.com/verfriemelt-dot-org
.. _`Nathan Verzemnieks`: https://github.com/njvrzm
.. _`raylu`: https://github.com/raylu
.. _`Zhaolong Zhu`: https://github.com/zzl0
.. _`Xavier Francisco`: https://github.com/Qu4tro
.. _`VVelox`: https://github.com/VVelox
.. _`Telmo "Trooper"`: https://github.com/telmotrooper
.. _`Alexander Zawadzki`: https://github.com/zadacka
.. _`Sebastian Janko`: https://github.com/sebojanko
.. _`Pedro Ferrari`: https://github.com/petobens
.. _`BrownShibaDog`: https://github.com/BrownShibaDog
.. _`thegeorgeous`: https://github.com/thegeorgeous
.. _`laixintao`: https://github.com/laixintao
.. _`anthonydb`: https://github.com/anthonydb
.. _`Daniel Kukula`: https://github.com/dkuku
