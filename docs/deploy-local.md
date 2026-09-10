# Guia do ambiente — Odoo 18 + localização fiscal OCA

Complemento do `README.md`: o porquê das decisões e as armadilhas já mapeadas.
Tudo aqui foi verificado neste ambiente (Docker + WSL2) em 10/09/2026, contra
`OCA/l10n-brazil` branch 18.0, commit `ce9b416`.

---

## 1. Por que uma imagem própria, e não `odoo:18.0` direto

Dos 14 pacotes Python exigidos pelos manifests da OCA, **11 não existem na
imagem oficial** (`erpbrasil.*`, `nfelib`, `brazilfiscalreport`, `brazilcep`,
`workalendar`, `transitions`, ...). Instalar via `pip` num container em
execução não resolve: se perde no próximo `docker compose up`.

Por isso o `Dockerfile` (`FROM odoo:18.0`) e o `build:` no compose. Três
armadilhas que ele já trata, todas com sintomas que não apontam para a causa:

| Sintoma | Causa |
|---|---|
| `Package 'packaging' is required to parse ... external dependency` | `packaging` não vem na imagem oficial, mas o Odoo 18 precisa dele para interpretar os `external_dependencies` dos manifests |
| `ERROR: Cannot uninstall cryptography, RECORD file not found` | `cryptography` e `typing_extensions` vêm do apt sem metadados; o pip não consegue substituí-los. Resolvido com `--ignore-installed` |
| `AttributeError: module 'lib' has no attribute 'GEN_EMAIL'` no boot | `pyOpenSSL` do apt quebra com o `cryptography` novo; os dois têm que subir juntos |

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

Todos os 47 módulos do `l10n-brazil` estão migrados para 18.0 e marcados como
`installable`. A stack instalada por `make install-br` traz 16 módulos
`l10n_br_*` e os dados-mestre reais: 5.570 municípios com código IBGE, 11.543
NCMs, 619 CFOPs, 1.043 CESTs, 356 impostos.

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
