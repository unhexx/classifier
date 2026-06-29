#!/usr/bin/env bash
# Обёртка для docker: автоматически выбирает способ доступа к демону
set -euo pipefail

_run() {
    if [[ "$1" == "compose" ]]; then
        shift
        docker compose "$@"
    else
        docker "$@"
    fi
}

if docker info &>/dev/null; then
    _run "$@"
    exit 0
fi

# Группа docker есть в passwd, но сессия ещё не обновилась — sg docker
if id -nG "$USER" 2>/dev/null | grep -qw docker; then
    if [[ "$1" == "compose" ]]; then
        exec sg docker -c "docker compose $(printf '%q ' "${@:2}")"
    else
        exec sg docker -c "docker $(printf '%q ' "$@")"
    fi
fi

# Passwordless sudo (если настроен)
if sudo -n docker info &>/dev/null; then
    if [[ "$1" == "compose" ]]; then
        shift
        exec sudo docker compose "$@"
    else
        exec sudo docker "$@"
    fi
fi

cat >&2 <<'EOF'
Ошибка: нет доступа к Docker (permission denied на /var/run/docker.sock).

Однократная настройка (выполните в терминале):

  sudo usermod -aG docker $USER
  newgrp docker          # или выйдите из сессии и войдите снова

Проверка:

  docker ps

Затем снова:

  make docker-run

Подробнее: scripts/setup-docker-access.sh
EOF
exit 1