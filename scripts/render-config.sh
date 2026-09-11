#!/usr/bin/env bash
# Gera config/odoo.conf a partir de config/odoo.conf.template + .env + oca-repos.conf.
#
# O addons_path é derivado do manifesto: acrescentar um repositório OCA em
# oca-repos.conf e rodar `make config` basta. Editar addons_path na mão é a
# forma mais fácil de instalar a localização pela metade e só descobrir depois.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$ROOT/config/odoo.conf.template"
OUT="$ROOT/config/odoo.conf"

[ -f "$ROOT/.env" ] || { echo "erro: .env não existe. Rode: cp .env.example .env" >&2; exit 1; }
set -a
# shellcheck source=/dev/null
. "$ROOT/.env"
set +a

: "${PROJECT:?defina PROJECT no .env}"
: "${ADMIN_PASSWD:?defina ADMIN_PASSWD no .env}"

# /mnt/extra-addons é onde o compose monta ./addons dentro do container.
# Ordem importa: os nossos módulos vêm primeiro, para que uma customização
# possa sobrepor um módulo da OCA de mesmo nome se algum dia for preciso.
paths="/mnt/extra-addons/local"
while read -r name _url _branch _commit; do
  paths="$paths,/mnt/extra-addons/oca/$name"
done < <(grep -vE '^\s*(#|$)' "$ROOT/oca-repos.conf")
paths="$paths,/usr/lib/python3/dist-packages/odoo/addons"

# Aceita o banco do projeto e seus derivados (acme, acme_test, acme_staging).
db_filter="^${PROJECT}(_[a-z0-9_]+)?\$"

sed -e "s|{{ADDONS_PATH}}|$paths|" \
    -e "s|{{ADMIN_PASSWD}}|${ADMIN_PASSWD}|" \
    -e "s|{{DB_USER}}|${DB_USER:-odoo}|" \
    -e "s|{{DB_PASSWORD}}|${DB_PASSWORD:-odoo}|" \
    -e "s|{{DB_FILTER}}|$db_filter|" \
    -e "s|{{WORKERS}}|${WORKERS:-0}|" \
    -e "s|{{LOG_LEVEL}}|${LOG_LEVEL:-info}|" \
    "$TEMPLATE" > "$OUT"

# O container roda como uid 101; um arquivo 600 do host deixa o Odoo em
# crash-loop com "Permission denied" antes mesmo de logar o motivo.
chmod 644 "$OUT"

echo "config/odoo.conf gerado para PROJECT=$PROJECT"
echo "  addons_path: $paths"
echo "  db_filter:   $db_filter"
