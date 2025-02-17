_pg_databases()
{
    # -w was introduced in 8.4, https://launchpad.net/bugs/164772
    # "Access privileges" in output may contain linefeeds, hence the NF > 1
    COMPREPLY=( $( compgen -W "$( psql -AtqwlF $'\t' 2>/dev/null | \
        awk 'NF > 1 { print $1 }' )" -- "$cur" ) )
}

_pg_users()
{
    # -w was introduced in 8.4, https://launchpad.net/bugs/164772
    COMPREPLY=( $( compgen -W "$( psql -Atqwc 'select usename from pg_user' \
        template1 2>/dev/null )" -- "$cur" ) )
    [[ ${#COMPREPLY[@]} -eq 0 ]] && COMPREPLY=( $( compgen -u -- "$cur" ) )
}

_pg_services()
{
    # return list of available services
    local services
    if [[ -f "$HOME/.pg_service.conf" ]]; then
        services=$(grep -oP '(?<=^\[).*?(?=\])' "$HOME/.pg_service.conf")
    fi
    local suffix="${cur#*=}"
    COMPREPLY=( $(compgen -W "$services" -- "$suffix") )
}

_pgcli()
{
    local cur prev words cword
    _init_completion -s || return

    case $prev in
        -h|--host)
            _known_hosts_real "$cur"
            return 0
            ;;
        -U|--user)
            _pg_users
            return 0
            ;;
        -d|--dbname)
            _pg_databases
            return 0
            ;;
        --help|-v|--version|-p|--port|-R|--row-limit)
            # all other arguments are noop with these
            return 0
            ;;
    esac

    case "$cur" in
        service=*)
            _pg_services
            return 0
            ;;
        --*)
            # return list of available options
            COMPREPLY=( $( compgen -W '--host --port --user --password --no-password
                --single-connection --version --dbname --pgclirc --dsn
                --row-limit --help' -- "$cur" ) )
            [[ $COMPREPLY == *= ]] && compopt -o nospace
            return 0
            ;;
        -)
            # only complete long options
            compopt -o nospace
            COMPREPLY=( -- )
            return 0
            ;;
        *)
            # return list of available databases
            _pg_databases
    esac
} &&
complete -F _pgcli pgcli
