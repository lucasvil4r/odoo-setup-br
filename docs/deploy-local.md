# Guia do ambiente — Odoo 18 + localização fiscal OCA

Complemento do `README.md`: o porquê das decisões e as armadilhas já mapeadas.
Tudo aqui foi verificado neste ambiente (Docker + WSL2) em 10/09/2026, contra
`OCA/l10n-brazil` branch 18.0, commit `ce9b416`. Revisto em 11/10/2026 ao mover
o pin para `6bddf53` (§1, §5 e §9).

---

## 1. Por que uma imagem própria, e não `odoo:18.0` direto

Dos 14 pacotes Python exigidos pelos manifests da OCA, **11 não existem na
imagem oficial** (`erpbrasil.*`, `nfelib`, `brazilfiscalreport`, `brazilcep`,
`workalendar`, `transitions`, ...). Instalar via `pip` num container em
execução não resolve: se perde no próximo `docker compose up`.

Por isso o `Dockerfile` (`FROM odoo:18.0`) e o `build:` no compose. As
armadilhas que ele já trata, todas com sintomas que não apontam para a causa:

| Sintoma | Causa |
|---|---|
| `Package 'packaging' is required to parse ... external dependency` | `packaging` não vem na imagem oficial, mas o Odoo 18 precisa dele para interpretar os `external_dependencies` dos manifests |
| `ERROR: Cannot uninstall cryptography, RECORD file not found` | `cryptography` e `typing_extensions` vêm do apt sem metadados; o pip não consegue substituí-los. Resolvido com `--ignore-installed` |
| `AttributeError: module 'lib' has no attribute 'GEN_EMAIL'` no boot | `pyOpenSSL` do apt quebra com o `cryptography` novo; os dois têm que subir juntos |
| `ModuleNotFoundError: No module named 'openupgradelib'` no `-u` | os scripts de `migrations/` da OCA usam `openupgradelib`. A instalação do zero não roda migração, então o erro só aparece ao mover um pin num banco existente |
| `Some modules are not loaded` logo após mover o pin | o manifest passou a exigir versão mínima de lib (`nfelib>=2.6.0`, por exemplo). As mínimas ficam explícitas no `Dockerfile`; o pip não atualiza o que já está instalado sem elas |

O `pip` instala sem versão a maioria das libs, então um `make build` com cache
mantém as versões antigas. Quando um manifest da OCA passar a exigir mínima,
escreva a mínima no `Dockerfile`: além de documentar, invalida o cache.

Após qualquer mudança no `Dockerfile`: `make build && make up`.

## 2. Por que cinco repositórios OCA

`l10n-brazil` sozinho não instala: `l10n_br_fiscal` depende de `uom_alias`
(em `OCA/product-attribute`) e `l10n_br_stock_account` depende de
`stock_picking_invoicing` (em `OCA/account-invoicing`), que por sua vez puxa
`stock_picking_invoice_link` (`OCA/stock-logistics-workflow`) e
`base_view_inheritance_extension` (`OCA/server-tools`).

Essas dependências são **transitivas**: descobrir uma por vez custa uma
tentativa de instalação inteira por dependência faltando. Por isso `make deps`,
que calcula o fecho completo antes de instalar e diz exatamente o que falta.

O Odoo **não varre subdiretórios recursivamente** — cada repositório precisa
entrar no `addons_path` individualmente. É o que `scripts/render-config.sh`
faz a partir do `oca-repos.conf`.

## 3. Permissões do `config/odoo.conf`

O container roda como uid 101. Um `odoo.conf` com modo `600` (o padrão de
alguns umask) deixa o Odoo em crash-loop com `Permission denied` **antes** de
conseguir logar o motivo — o erro visível é um `configparser.NoSectionError`
enganoso. `render-config.sh` já aplica `chmod 644`.

## 4. Rodando a suíte de testes da OCA

`make test` cuida disso, mas se for rodar na mão, duas ressalvas que custam
tempo:

- Use **porta diferente** (`--http-port=8099`): o servidor já ocupa a 8069 e o
  processo de teste morre com "Address already in use".
- Rode **destacado dentro do container** (`docker compose exec -d`), não com
  `&` no host. Com `&`, o processo morre junto com o shell, o log fica
  truncado e o exit code 0 dá falsa impressão de sucesso.

Enquanto a suíte roda, não use `make restart`, `make down` ou `make build`: o
processo de teste está destacado *dentro* do container e vai junto com ele. O
log congela no meio da execução, sem nenhuma falha aparente — `make test-status`
fica em "rodando" para sempre porque o sentinela de conclusão nunca é gravado.

Sem `--test-tags` a suíte roda também os testes do core do Odoo, e o
`base.tests.test_configmanager` falha (4 testes) só porque usamos um
`odoo.conf` customizado — ruído, não defeito.

Os testes precisam de duas libs que só existem para isso (`odoo-test-helper`,
exigida por `spec_driven_model`, e `xmldiff`, pelos testes de serialização de
NF-e). Já estão no `Dockerfile`.

## 5. Estado da localização em 18.0

Todos os 55 módulos do `l10n-brazil` estão migrados para 18.0 e marcados como
`installable`. A stack instalada por `make install-br` traz 15 módulos
`l10n_br_*` e os dados-mestre reais: 5.570 municípios com código IBGE, 11.543
NCMs, 619 CFOPs, 1.043 CESTs, 359 impostos.

Desde `6bddf53`, o `l10n_br_nfe` não depende mais do `l10n_br_fiscal_dfe`
(download de NF-e na SEFAZ, que agora exige `queue_job`, do `OCA/queue`). Ele
saiu do fecho do `make install-br`. Quem precisar de DF-e instala
`l10n_br_nfe_dfe` e acrescenta `OCA/queue` em `oca-repos.conf`.

Os motores de validação funcionam em execução, não só as tabelas: CNPJ e CPF
inválidos são rejeitados, e a Inscrição Estadual é validada por UF.

O modelo de documento fiscal já tem campos `amount_ibs_*` e `amount_cbs_*` e
há testes de IBS/CBS passando — a OCA está acompanhando a Reforma Tributária.

### Uma pegadinha da lib `erpbrasil`

`ie.validar('SP', n)` e `ie.validar('sp', n)` retornam resultados **diferentes**
para o mesmo número: a forma maiúscula aceita IEs inválidos. A OCA chama em
minúsculas (correto). Se código nosso chamar essa lib direto, use minúsculas.

### Mudança de API vindo de versões anteriores

No 18.0 o CNPJ/CPF é guardado no campo padrão `vat` do Odoo. `cnpj_cpf` virou
computado. Código portado de Odoo 14/16 que escreve em `cnpj_cpf` falha com
`KeyError`.

## 6. Comandos do dia a dia

```bash
make                 # lista todos os alvos
make logs            # acompanha o log do Odoo
make shell           # shell do ORM
make psql            # psql no banco do projeto
make reset           # APAGA volumes e sobe do zero (pede confirmação)
```

O `odoo shell` faz **rollback ao sair**: para persistir algo feito nele, chame
`env.cr.commit()` explicitamente. Scripts de teste que criam dados em sessões
separadas não enxergam o que a sessão anterior criou.

## 7. Referência rápida: sintoma → causa

Todos estes já aconteceram na montagem deste template. O traço comum é que
quase nenhum aponta para a causa real — vários dão *falso sucesso*, que é pior
que um erro barulhento.

| Sintoma | Causa provável | Onde |
|---|---|---|
| Odoo em crash-loop com `NoSectionError: 'options'` | `config/odoo.conf` com modo 600; o container (uid 101) não consegue ler | §3 |
| `Package 'packaging' is required to parse ...` | imagem oficial não traz `packaging`; use `make build` | §1 |
| `Cannot uninstall cryptography, RECORD file not found` | pacote veio do apt; precisa de `--ignore-installed` | §1 |
| `AttributeError: module 'lib' has no attribute 'GEN_EMAIL'` | `pyOpenSSL` do apt incompatível com `cryptography` novo | §1 |
| `módulo X depende de Y, que não está disponível` | falta um repositório OCA no `addons_path`; rode `make deps` | §2 |
| Módulo novo não aparece em Apps | `addons_path` não regenerado (`make config`) ou Odoo não reiniciado | §2 |
| Mudança em `.py` ou em XML de view não surte efeito | falta `make update m=<modulo>`; views ficam gravadas no banco | §6 |
| Teste roda e "passa" mas o log tem 9 linhas | processo lançado com `&` no host, morreu com o shell | §4 |
| `Address already in use` ao rodar testes | servidor já ocupa a 8069; use `--http-port=8099` | §4 |
| `make test-status` fica em "rodando" para sempre | container reiniciado durante a suíte; o sentinela nunca é gravado | §4 |
| Dados criados no `odoo shell` somem | o shell faz rollback ao sair; chame `env.cr.commit()` | §6 |
| `KeyError: 'cnpj_cpf'` ao criar parceiro | no 18.0 o CNPJ vai no campo `vat` | §5 |
| IE inválida aceita pelo seu código | `ie.validar` da `erpbrasil` é sensível a maiúsculas; use minúsculas | §5 |
| Lista de módulos quebrada em argumentos soltos | `\` de continuação numa variável de Make vira espaço | — |
| Tela quebra com `"x"."y" field is undefined` depois de mover um pin | Python novo rodando sobre banco da versão anterior; falta `make upgrade` | §9 |
| `Some modules are not loaded ...` no log após mover um pin | módulo instalado ganhou dependência que o ambiente não tem (repositório, módulo do core ou versão de lib) | §1, §9 |
| `-u` aborta com "depends on the module ... not available" | dependência nova fora do `addons_path`: acrescente o repositório ou desinstale o módulo | §9 |
| Desinstalar um módulo levou outros junto | lista de módulos do banco desatualizada após mover o pin; rode `update_list()` antes | §9 |
| `ModuleNotFoundError: openupgradelib` no `-u` | lib dos scripts de migração da OCA; já está no `Dockerfile` | §1 |
| Instalação morre em `DeadlockDetected` no `ir_module_module` | servidor no ar carregando o mesmo banco (o cron varre todos); pare o servidor | §9 |
| `DeprecationWarning: verify() is deprecated` com stack trace no boot | aviso do `signxml`, que a `erpbrasil.assinatura` prende em `<4`; ruído, não erro | — |

## 8. Ambiente de avaliação vs. base de cliente

`make install-br` instala **sem** dados de demonstração: uma base de cliente não
deve nascer com dados fictícios, e limpá-los depois é pior que não criá-los.

Para explorar a plataforma com conteúdo dentro (avaliação, treinamento, demo
comercial), use um banco separado com demo:

```bash
make install-br DEMO=1
```

E para começar do zero a qualquer momento: `make reset` (apaga volumes, pede
confirmação digitando o nome do projeto).

## 9. Movendo um pin num banco que já existe

Mover um pin em `oca-repos.conf` troca o código, não o banco. Até rodar a
migração, o Python novo roda sobre tabelas e views da versão anterior. O
sintoma no navegador é `"product.supplierinfo"."partner_uom_factor" field is
undefined` ou parecido: a view gravada no banco cita um campo de um módulo que
o servidor nem conseguiu carregar.

Ordem que funciona:

```bash
./scripts/fetch-oca.sh --check-updates   # o que muda desde os pins
make fetch config                         # código nos pins novos
make deps                                 # dependências novas (repositórios OCA)
make build                                # libs novas; veja as mínimas nos manifests
docker compose exec -T db pg_dump -U odoo -Fc acme > acme.dump   # backup, por banco
make upgrade                              # e make upgrade db=<outro banco>, um por banco
make test                                 # a suíte da OCA na versão nova
```

O `make upgrade` para o servidor durante a migração. Com ele no ar, o cron
varre todo banco aceito pelo `db_filter`, tenta carregar um banco pela metade e
a migração morre em `DeadlockDetected` no `ir_module_module`.

O `-u all` já instala dependência nova que exista no `addons_path`: foi o caso
do módulo `certificate` do core, exigido pelo `l10n_br_fiscal_certificate` desde
`6bddf53`. Dependência que **não** existe aborta a migração inteira. Aí há duas
saídas: acrescentar o repositório em `oca-repos.conf`, ou desinstalar o módulo
que a exige, se nada mais depender dele. Na passagem de `ce9b416` para
`6bddf53`, o `l10n_br_fiscal_dfe` passou a exigir `queue_job` e deixou de ser
necessário para o `l10n_br_nfe`. Foi desinstalado antes do `-u`.

**Atualize a lista de módulos antes de desinstalar.** As dependências que o
banco conhece são as do manifest antigo. Sem atualizar, desinstalar o
`l10n_br_fiscal_dfe` leva junto o `l10n_br_nfe`, que no manifest antigo ainda
dependia dele. Aconteceu numa das bases deste template.

```bash
make shell
>>> Mod = env['ir.module.module']
>>> Mod.update_list()                       # dependências do código novo
>>> dfe = Mod.search([('name', '=', 'l10n_br_fiscal_dfe')])
>>> dfe.downstream_dependencies().mapped('name')   # tem que vir vazio
>>> dfe.button_immediate_uninstall()
>>> env.cr.commit()
```

Desinstalar apaga as tabelas do módulo. Num banco com uso real do módulo, a
saída é acrescentar o repositório, não desinstalar.
