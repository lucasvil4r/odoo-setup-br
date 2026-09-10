#!/usr/bin/env bash
# Clona/atualiza os repositórios OCA declarados em oca-repos.conf, em addons/oca/.
# Idempotente: rodar de novo com o mesmo pin não faz nada além de verificar.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$ROOT/oca-repos.conf"
DEST="$ROOT/addons/oca"

entries() { grep -vE '^\s*(#|$)' "$MANIFEST"; }

check_updates() {
  printf '%-28s %-10s %s\n' REPO STATUS "COMMIT FIXADO -> HEAD DO BRANCH"
  entries | while read -r name url branch commit; do
    head=$(git ls-remote "$url" "refs/heads/$branch" | cut -f1)
    if [ "$head" = "$commit" ]; then
      printf '%-28s %-10s %s\n' "$name" "em-dia" "${commit:0:8}"
    else
      behind=""
      if [ -d "$DEST/$name/.git" ]; then
        git -C "$DEST/$name" fetch -q origin "$branch" 2>/dev/null || true
        behind=" ($(git -C "$DEST/$name" rev-list --count "$commit..origin/$branch" 2>/dev/null || echo '?') commits atrás)"
      fi
      printf '%-28s %-10s %s\n' "$name" "ATRASADO" "${commit:0:8} -> ${head:0:8}$behind"
    fi
  done
}

update_pin() {
  local target="$1" found=0
  entries | while read -r name url branch commit; do
    [ "$name" = "$target" ] || continue
    head=$(git ls-remote "$url" "refs/heads/$branch" | cut -f1)
    # Atualiza o pin no manifesto preservando o alinhamento das colunas.
    sed -i "s|^\(${name}[[:space:]]\+${url}[[:space:]]\+${branch}[[:space:]]\+\)${commit}|\1${head}|" "$MANIFEST"
    echo "pin de $name: ${commit:0:8} -> ${head:0:8}"
    echo "Rode 'make fetch && make test' antes de commitar essa mudança."
  done
  grep -q "^${target}[[:space:]]" "$MANIFEST" || { echo "repositório '$target' não está em oca-repos.conf" >&2; exit 1; }
}

fetch_all() {
  mkdir -p "$DEST"
  entries | while read -r name url branch commit; do
    local_dir="$DEST/$name"
    if [ ! -d "$local_dir/.git" ]; then
      echo "==> clonando $name"
      git clone -q --filter=blob:none --branch "$branch" "$url" "$local_dir"
    fi
    current=$(git -C "$local_dir" rev-parse HEAD)
    if [ "$current" = "$commit" ]; then
      echo "==> $name já em ${commit:0:8}"
      continue
    fi
    echo "==> $name: ${current:0:8} -> ${commit:0:8}"
    git -C "$local_dir" fetch -q origin "$branch"
    git -C "$local_dir" checkout -q "$commit"
  done
  echo
  echo "Repositórios OCA em addons/oca/ conforme oca-repos.conf."
  echo "Lembre de rodar 'make config' se a lista de repositórios mudou."
}

case "${1:-}" in
  --check-updates) check_updates ;;
  --update)        update_pin "${2:?uso: $0 --update <nome-do-repo>}" ;;
  "")              fetch_all ;;
  *) echo "uso: $0 [--check-updates | --update <repo>]" >&2; exit 1 ;;
esac
