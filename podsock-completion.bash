#!/bin/bash
# Bash completion for podsock

_podsock_completion() {
    local cur prev words cword
    _init_completion || return

    # Available +flags with descriptions
    declare -A flag_descriptions=(
        [w]="Wayland"
        [s]="SSH Agent"
        [g]="Graphics"
        [n]="Network"
        [d]="Debug"
    )
    local podsock_flags="w s g n d"

    # Complete +flags (allow combinations like +wsn)
    if [[ "$cur" == +* ]]; then
        local flag="${cur:1}"
        # Build list of remaining flags
        local remaining_flags=()
        for f in $podsock_flags; do
            if [[ "$flag" != *"$f"* ]]; then
                remaining_flags+=("$f")
            fi
        done

        # Always include the current partial flag as a valid completion
        COMPREPLY=("$cur")

        # Add remaining flags with descriptions
        for f in "${remaining_flags[@]}"; do
            COMPREPLY+=("${cur}${f} (${flag_descriptions[$f]})")
        done

        compopt -o nospace
        return
    fi

    # Filter out +flags from words for podman completion
    local filtered_words=()
    for word in "${words[@]}"; do
        if [[ "$word" != +* ]]; then
            filtered_words+=("$word")
        fi
    done

    # Use podman's __complete command
    local podman_args=("${filtered_words[@]:1}")
    local completions
    if completions=$(podman __complete "${podman_args[@]}" 2>/dev/null); then
        COMPREPLY=($(compgen -W "$completions" -- "$cur"))
    else
        # Fallback: suggest common podman subcommands
        local subcommands="run create exec start stop rm rmi ps images pull push build logs"
        COMPREPLY=($(compgen -W "$subcommands" -- "$cur"))
    fi
}

complete -F _podsock_completion podsock
