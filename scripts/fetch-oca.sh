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
  local target="$1"
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

# Confere, sem baixar o código, que cada pin é um commit do branch declarado.
# No GitHub, um commit de fork também é acessível pela URL do repositório
# original; por isso a checagem é de pertencer ao branch, não só de existir.
verify_pins() {
  local rc=0
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  while read -r name url branch commit; do
    if ! [[ "$commit" =~ ^[0-9a-f]{40}$ ]]; then
      printf '%-28s ERRO: pin "%s" não é um SHA completo\n' "$name" "$commit"
      rc=1; continue
    fi
    if ! git clone -q --bare --filter=tree:0 --single-branch --no-tags \
         --branch "$branch" "$url" "$tmp/$name" 2>/dev/null; then
      printf '%-28s ERRO: branch %s inacessível em %s\n' "$name" "$branch" "$url"
      rc=1; continue
    fi
    if git -C "$tmp/$name" merge-base --is-ancestor "$commit" "refs/heads/$branch" 2>/dev/null; then
      printf '%-28s ok    %s pertence a %s\n' "$name" "${commit:0:8}" "$branch"
    else
      printf '%-28s ERRO: %s não pertence a %s\n' "$name" "${commit:0:8}" "$branch"
      rc=1
    fi
  done < <(entries)
  return "$rc"
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
  --verify)        verify_pins ;;
  "")              fetch_all ;;
  *) echo "uso: $0 [--check-updates | --update <repo> | --verify]" >&2; exit 1 ;;
esac
