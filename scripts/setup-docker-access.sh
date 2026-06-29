#!/usr/bin/env bash
# Однократная настройка доступа к Docker без sudo при каждой команде
set -euo pipefail

echo "=== Настройка доступа к Docker для пользователя: $USER ==="

if docker info &>/dev/null; then
    echo "Docker уже доступен. Ничего делать не нужно."
    docker ps
    exit 0
fi

if ! getent group docker &>/dev/null; then
    echo "Группа docker не найдена. Установите Docker:"
    echo "  sudo pacman -S docker docker-compose"
    echo "  sudo systemctl enable --now docker"
    exit 1
fi

if ! id -nG "$USER" | grep -qw docker; then
    echo "Добавляем $USER в группу docker (требуется sudo)..."
    sudo usermod -aG docker "$USER"
    echo "Пользователь добавлен в группу docker."
else
    echo "Пользователь уже в группе docker, но текущая сессия не обновлена."
fi

echo ""
echo "Активируйте группу в текущем терминале:"
echo "  newgrp docker"
echo ""
echo "Или перелогиньтесь, затем:"
echo "  make docker-run"