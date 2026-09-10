"""Confere o fecho de dependências dos módulos ANTES de tentar instalá-los.

Roda dentro do container (via `make deps`) e lê o addons_path real do
config/odoo.conf gerado — então reflete exatamente o que o Odoo enxerga.

Existe porque a OCA espalha as dependências da localização brasileira por
vários repositórios, e elas são transitivas: instalar e descobrir uma de
cada vez custa uma reinstalação inteira por dependência faltando.
"""
import ast
import configparser
import os
import sys

CONF = "/etc/odoo/odoo.conf"

cfg = configparser.ConfigParser()
cfg.read(CONF)
paths = [p.strip() for p in cfg.get("options", "addons_path").split(",") if p.strip()]

modules = [m.strip() for m in os.environ.get("MODULES", "").replace("\n", "").split(",") if m.strip()]
if not modules:
    sys.exit("defina MODULES=mod1,mod2")


def manifest(name):
    for p in paths:
        f = os.path.join(p, name, "__manifest__.py")
        if os.path.isfile(f):
            return f
    return None


seen, missing = set(), {}
stack = list(modules)
while stack:
    mod = stack.pop()
    if mod in seen:
        continue
    seen.add(mod)
    f = manifest(mod)
    if not f:
        continue
    try:
        depends = ast.literal_eval(open(f).read()).get("depends", [])
    except Exception:
        depends = []
    for dep in depends:
        if manifest(dep):
            stack.append(dep)
        else:
            missing.setdefault(dep, set()).add(mod)

print(f"addons_path: {len(paths)} diretórios")
print(f"módulos no fecho de dependências: {len(seen)}")
if missing:
    print(f"\nFALTANDO ({len(missing)}):")
    for dep in sorted(missing):
        print(f"  {dep:<34} exigido por: {', '.join(sorted(missing[dep]))}")
    print("\nAdicione o repositório OCA que contém esses módulos em oca-repos.conf,")
    print("depois rode: make fetch config restart")
    sys.exit(1)
print("\nNenhuma dependência faltando — pode instalar.")
