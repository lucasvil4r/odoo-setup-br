#!/usr/bin/env bash
# Cria o esqueleto de um módulo de customização em addons/local/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?uso: $0 <nome_do_modulo>}"

if ! [[ "$NAME" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "erro: nome deve ser minúsculo com underscores (ex: l10n_br_acme_compras)" >&2
  exit 1
fi

DIR="$ROOT/addons/local/$NAME"
[ -e "$DIR" ] && { echo "erro: $DIR já existe" >&2; exit 1; }

mkdir -p "$DIR"/{models,views,security,tests}

cat > "$DIR/__manifest__.py" <<EOF
{
    "name": "$NAME",
    "summary": "Customização do cliente",
    "version": "18.0.1.0.0",
    "category": "Localization/Brazil",
    "license": "AGPL-3",
    "author": "",
    "depends": [
        "base",
        # Dependências típicas de customização fiscal, descomente conforme usar:
        # "l10n_br_fiscal",
        # "l10n_br_account",
        # "purchase",
        # "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        # "views/views.xml",
    ],
    "installable": True,
    "application": False,
}
EOF

cat > "$DIR/__init__.py" <<'EOF'
from . import models
EOF

cat > "$DIR/models/__init__.py" <<'EOF'
# from . import res_partner
EOF

cat > "$DIR/tests/__init__.py" <<'EOF'
# from . import test_exemplo
EOF

# Cabeçalho obrigatório: sem ele o Odoo ignora o arquivo silenciosamente.
cat > "$DIR/security/ir.model.access.csv" <<'EOF'
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
EOF

cat > "$DIR/README.md" <<EOF
# $NAME

Módulo de customização. Estende a base (Odoo + OCA) por herança — nunca
edite o código da OCA ou do core diretamente, senão a atualização da base
passa a custar retrabalho.

## Desenvolvimento

    make update m=$NAME     # aplica mudanças de código/views
    make shell              # inspeciona o ORM

Mudança em Python exige \`make update\`. Mudança só em XML de view também,
porque as views ficam gravadas no banco.
EOF

echo "módulo criado em addons/local/$NAME"
echo
echo "Próximos passos:"
echo "  make restart                # o Odoo relê o addons_path no boot"
echo "  make install m=$NAME"
