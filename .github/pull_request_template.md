## O que muda

<!-- Uma ou duas frases. -->

## Por quê

<!-- O sintoma, a causa ou a necessidade que motivou a mudança. Link da issue, se houver. -->

## Como validei

<!-- Comandos rodados e resultado. Se mexeu em oca-repos.conf ou no Dockerfile,
     inclua o resultado do make test (testes / falhas). -->

## Checklist

- [ ] Validei num clone limpo do meu fork (`make init`), não só no meu ambiente de trabalho
- [ ] `shellcheck scripts/*.sh` sem avisos (se mexi em `scripts/`)
- [ ] `./scripts/fetch-oca.sh --verify` e `make test` (se mexi em `oca-repos.conf` ou no `Dockerfile`)
- [ ] Documentação atualizada (`README.md` e, se for armadilha nova, `docs/deploy-local.md`)
- [ ] Nenhum segredo, `.env` ou `config/odoo.conf` no diff
