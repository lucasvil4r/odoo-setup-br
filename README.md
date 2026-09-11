# Odoo 18 + Localização Fiscal Brasileira — Template de Projeto

Base para iniciar projetos de ERP em clientes diferentes. Fork, ajuste o `.env`,
`make init`, e você tem um Odoo 18 com a localização fiscal brasileira da OCA
instalada, fixada por commit e com a suíte de testes rodando.

O que este template resolve é o setup — a parte que dá trabalho uma vez e depois
se repete igual em todo cliente. A configuração fiscal de cada empresa
(regime, operações, CFOPs, alíquotas por UF) é trabalho de implantação e fica
fora daqui, por ser específica de cada negócio.

## Começando um projeto novo

```bash
git clone https://github.com/lucasvil4r/odoo-setup-br.git cliente-acme && cd cliente-acme
cp .env.example .env          # ajuste PROJECT e ADMIN_PASSWD
make init                     # baixa OCA, gera config, builda, sobe
make install-br               # instala a localização fiscal
make install-ui               # menu de apps com ícones e campos visíveis
```

Odoo em `http://localhost:8069`. `make` sozinho lista todos os alvos.

### O que ajustar ao forkar

| Onde | O quê |
|---|---|
| `.env` | `PROJECT` (vira nome do banco e dos containers), `ADMIN_PASSWD`, `ODOO_PORT`, `DB_PORT` |
| `oca-repos.conf` | repositórios OCA extras, se o cliente precisar (NFS-e, RH, etc.) |
| `addons/local/` | os módulos de customização do cliente (`make new-module`) |
| `README.md` | este arquivo, descrevendo o projeto do cliente |

Trocar `PROJECT` isola containers, volumes e banco: dois clientes rodam lado a
lado na mesma máquina, bastando `ODOO_PORT` e `DB_PORT` diferentes.

## Arquitetura em camadas

```
┌─────────────────────────────────────────────┐
│   addons/local/  — customização do cliente   │
│   - Automações e fluxos de aprovação          │
│   - Regras de precificação                    │
│   - Integrações externas                      │
├─────────────────────────────────────────────┤
│   addons/oca/l10n-brazil — localização        │
│   - l10n_br_fiscal (CFOP, CST, NCM, impostos) │
│   - l10n_br_nfe (NF-e, DANFE, SEFAZ)          │
│   - l10n_br_account (contábil brasileiro)     │
├─────────────────────────────────────────────┤
│   Odoo 18.0 Community                         │
│   - Compras, Estoque, Vendas, Contabilidade   │
│   - ORM, segurança, framework de views        │
└─────────────────────────────────────────────┘
```

A separação entre `addons/local/` e `addons/oca/` é o ponto central: toda
customização entra por herança (de classe, de modelo, por delegação), nunca
editando o código da OCA ou do core. É o que permite atualizar a base sem
perder o que foi feito por cima — e o `.gitignore` reforça isso, versionando
só `addons/local/`.

### Por que Odoo 18.0 Community

- Licença LGPL: customização total, sem restrição comercial nem vendor lock-in.
- Cobre nativamente Compras, Estoque, Faturamento e Contabilidade, sobre uma
  arquitetura modular pensada desde o núcleo para ser estendida.
- É a versão que a OCA mantém como padrão para a localização brasileira
  (`OCA/l10n-brazil` branch 18.0).

Construir motor fiscal (NF-e/SPED) do zero significaria reinventar anos de
trabalho maduro, num domínio regulatório de alto risco — nota rejeitada, multa,
retrabalho contábil.

## Dependências OCA fixadas por commit

`oca-repos.conf` declara os cinco repositórios necessários e o commit exato de
cada um. Isso é o que garante que dois clientes forkados com meses de diferença
rodem o mesmo código, e que atualizar a base seja uma decisão consciente:

```bash
make check-updates              # o que mudou nos branches desde os pins
./scripts/fetch-oca.sh --update l10n-brazil
make fetch && make test         # valide ANTES de commitar o pin novo
```

Só `l10n-brazil` é a localização em si; os outros quatro entram porque
`l10n_br_fiscal` e `l10n_br_stock_account` dependem deles.

### Acrescentando um repositório OCA

Cedo ou tarde um cliente vai precisar de algo fora da stack padrão — NFS-e de
um município específico, folha, projetos. O caminho:

```bash
# 1. Descubra em qual repositório OCA o módulo vive (a OCA não tem índice único):
curl -s -o /dev/null -w "%{http_code}\n" \
  https://api.github.com/repos/OCA/<repositorio>/contents/<modulo>?ref=18.0
#    200 = existe nesse repositório, 404 = não

# 2. Acrescente uma linha em oca-repos.conf (nome, url, branch, commit).
#    Use o HEAD do branch como pin inicial:
git ls-remote https://github.com/OCA/<repositorio>.git refs/heads/18.0

# 3. Baixe, regenere o addons_path e confira o fecho de dependências:
make fetch config restart
make deps m=<modulo>
```

`make deps` é o passo que economiza tempo de verdade: ele calcula o fecho
**transitivo** e lista tudo que falta de uma vez. Sem ele, cada dependência
ausente custa uma tentativa de instalação inteira para ser descoberta — foi
assim que os quatro repositórios de apoio acima apareceram, um a um.

## Trazendo melhorias do template para um projeto já forkado

Correções feitas no template (um alvo novo no Makefile, uma armadilha
documentada, um ajuste no Dockerfile) não chegam sozinhas nos projetos já
iniciados. Configure o template como um segundo remoto e traga o que interessa:

```bash
git remote add template https://github.com/lucasvil4r/odoo-setup-br.git
git fetch template
git log --oneline HEAD..template/master     # o que existe lá e não aqui
git merge template/master                   # ou cherry-pick de commits soltos
```

Espere conflito em dois arquivos, e os dois são esperados:

- **`README.md`** — cada projeto reescreve o seu. Mantenha a versão do cliente.
- **`oca-repos.conf`** — os pins divergem de propósito: o cliente está numa
  versão validada da OCA e o template pode ter avançado. Mova o pin só de forma
  deliberada, e rode `make test` depois.

O resto (`Makefile`, `scripts/`, `Dockerfile`, `docs/`) costuma mesclar limpo,
porque é justamente a parte que não varia por cliente.

## Estrutura

```
.
├── .env                     # config do cliente (NÃO versionado)
├── .env.example             # modelo do .env
├── Dockerfile               # odoo:18.0 + libs Python da localização
├── Makefile                 # interface do dia a dia
├── docker-compose.yml       # Odoo + PostgreSQL, parametrizado pelo .env
├── oca-repos.conf           # repositórios OCA fixados por commit
├── config/
│   ├── odoo.conf.template   # modelo versionado
│   └── odoo.conf            # GERADO por make config (não versionado)
├── addons/
│   ├── oca/                 # clones da OCA (não versionados, veja make fetch)
│   └── local/               # customização do cliente (versionada)
├── scripts/
│   ├── fetch-oca.sh         # clona/atualiza a OCA nos pins
│   ├── render-config.sh     # gera odoo.conf do .env + oca-repos.conf
│   ├── check-deps.py        # fecho de dependências antes de instalar
│   └── new-module.sh        # esqueleto de módulo de customização
└── docs/deploy-local.md     # guia detalhado e armadilhas conhecidas
```

`config/odoo.conf` é gerado, não editado: o `addons_path` sai do
`oca-repos.conf`, e editá-lo à mão é a forma mais fácil de instalar a
localização pela metade e só descobrir depois.

## Desenvolvendo a customização

```bash
make new-module name=l10n_br_acme_compras
make restart                       # o Odoo relê o addons_path no boot
make install m=l10n_br_acme_compras
make update  m=l10n_br_acme_compras  # após cada mudança de código ou view
make shell                         # inspecionar o ORM
```

Mudança em XML de view também exige `make update`: as views ficam gravadas no
banco, não são lidas do disco a cada request.

## Testes

`make test` roda a suíte da OCA num banco descartável (`$PROJECT_test`) e
`make test-status` mostra o andamento. Vale rodar depois de mover qualquer pin
em `oca-repos.conf` — é a forma mais barata de pegar regressão na base.

Referência deste template: **332 testes, 0 falhas** contra `l10n-brazil`
`ce9b416` (10/09/2026), incluindo serialização de NF-e, validação de XML
contra schema, DANFE e os campos de IBS/CBS da Reforma Tributária.

## Licenciamento

- **Odoo 18 Community**: LGPL-3.
- **Módulos da OCA** (incluindo toda a `l10n-brazil`): **AGPL-3**.
- O esqueleto gerado por `make new-module` já vem com `"license": "AGPL-3"`.

O default é AGPL-3 porque um módulo que declara `depends` de um módulo AGPL-3
tende a ser tratado como trabalho derivado. Isso tem efeito prático quando a
customização é entregue ou hospedada para um cliente. Confirme com quem cuida
do jurídico de vocês antes de fechar contrato — não é uma questão técnica.

## Antes de ir para produção

Este setup é de desenvolvimento. Para um ambiente real:

- [ ] `ADMIN_PASSWD` forte no `.env` (o `.env.example` traz `troque-me`)
- [ ] Senha do PostgreSQL fora do padrão `odoo/odoo`
- [ ] `WORKERS` > 0 (regra prática: `2 * núcleos + 1`)
- [ ] Proxy reverso com HTTPS (Nginx/Traefik) e `proxy_mode = True`
- [ ] Backup do banco e do volume `data_dir` (anexos e XMLs de NF-e vivem lá)
- [ ] Certificado digital A1 para emissão de NF-e
