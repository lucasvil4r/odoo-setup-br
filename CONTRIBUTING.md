# Contribuindo

Este template existe para que o setup de um projeto Odoo 18 com a localização
fiscal brasileira seja feito uma vez e se repita igual em todo cliente.
Contribuições que melhoram essa base são bem-vindas.

## O que entra

- Correção de armadilha do ambiente (build, OCA, Docker, WSL), com o sintoma
  registrado em `docs/deploy-local.md`.
- Melhorias em `Makefile`, `scripts/`, `Dockerfile` e `docker-compose.yml`.
- Atualização de pins em `oca-repos.conf`, validada com `make test`.
- Documentação.

## O que não entra

- **Customização de cliente** — módulos de negócio, configuração fiscal de uma
  empresa. Isso vive no fork do projeto, não no template.
- **Mudança no código da OCA ou do Odoo.** Proponha no repositório de origem
  (por exemplo, `OCA/l10n-brazil`); aqui só entram os pins.
- **Segredos de qualquer tipo.** `.env` e `config/odoo.conf` não são
  versionados, e continuam não sendo.

## Fluxo

1. Para mudança grande — repositório OCA novo na stack padrão, troca de versão
   do PostgreSQL, reestruturação de alvos — abra uma issue antes para alinhar.
2. Faça fork e crie um branch a partir de `master`.
3. Abra o pull request para `master`. O merge é feito pelo mantenedor, por
   squash, depois da revisão e com o CI verde.

Em pull request vindo de fork, o CI só roda depois que o mantenedor aprova a
execução. É uma proteção do repositório, não um problema no seu PR.

## Antes de abrir o pull request

Valide num **clone limpo** do seu fork, não no seu ambiente de trabalho — é o
que um projeto novo vai enxergar. Se já houver outro ambiente rodando na
máquina, troque `ODOO_PORT` e `DB_PORT` no `.env` do clone.

```bash
git clone <url-do-seu-fork> teste-template && cd teste-template
cp .env.example .env
make init && make install-br && make install-ui
```

E, conforme o que mudou:

| Mudou | Rode |
|---|---|
| `scripts/` | `shellcheck scripts/*.sh` |
| `oca-repos.conf` | `./scripts/fetch-oca.sh --verify`, `make deps` e `make test` |
| `Dockerfile` | `make build && make up` e `make test` |
| `Makefile` | o alvo alterado, de ponta a ponta |

Para `make test`, informe no PR o resultado (`make test-status`): quantos
testes rodaram e quantas falhas.

## Convenções

- **Mensagens de commit em português.** O assunto diz o que muda ("Corrige…",
  "Adiciona…"); o corpo explica o porquê — o sintoma, a causa e por que esta
  solução. O `git log` tem exemplos.
- **Comentários explicam decisões e armadilhas**, não o que o código já diz.
- **Armadilha nova vai para a tabela sintoma → causa** em `docs/deploy-local.md`.
- **Pin se move com `./scripts/fetch-oca.sh --update <repo>`** seguido de
  `make test`. Não edite o SHA à mão.

## Licença

Ao contribuir, você concorda que sua contribuição seja distribuída sob a
[licença MIT](LICENSE) deste repositório.

## Segurança

Vulnerabilidade não vai em issue pública — veja [`SECURITY.md`](SECURITY.md).
