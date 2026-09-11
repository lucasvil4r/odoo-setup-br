# Política de segurança

## Versões suportadas

Só o branch `master` recebe correções. Projetos já forkados trazem a correção
pelo fluxo descrito no README, em *Trazendo melhorias do template para um
projeto já forkado*.

## Como reportar

**Não abra issue nem pull request público.** Use o reporte privado do GitHub:
aba **Security** → **Report a vulnerability**.

Inclua o que é afetado (arquivo, alvo do `make`, configuração), como reproduzir
e qual o impacto. O reporte fica visível só para você e para o mantenedor até a
correção ser publicada.

## Escopo

**Dentro:** o que este repositório entrega e os padrões que ele cria —
`Dockerfile`, `docker-compose.yml`, `Makefile`, `scripts/`, o CI em `.github/`,
portas expostas, permissões de arquivos gerados, pins em `oca-repos.conf`.

**Fora — reporte na origem:**

- **Odoo:** <https://www.odoo.com/security-report>
- **Módulos da OCA:** no repositório do módulo (por exemplo, `OCA/l10n-brazil`),
  pelo mesmo reporte privado do GitHub.
- **Imagens `odoo` e `postgres`:** nos respectivos projetos.

Este é um setup de desenvolvimento. Os itens que o README lista em *Antes de ir
para produção* (senhas padrão, `WORKERS`, HTTPS, backup) são limitações
conhecidas, não vulnerabilidades.
