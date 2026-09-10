# Interface do dia a dia. `make` sem argumentos lista os alvos.
.DEFAULT_GOAL := help
SHELL := /bin/bash

-include .env
export

PROJECT   ?= odoo18
ODOO_PORT ?= 8069
DC        := docker compose
ODOO      := $(DC) exec -T odoo odoo -c /etc/odoo/odoo.conf

# Base de cliente nasce sem dados fictícios. Para um ambiente de avaliação,
# em que navegar com conteúdo dentro ajuda:  make install-br DEMO=1
DEMO      ?= 0
DEMO_FLAG := $(if $(filter 1 yes true,$(DEMO)),,--without-demo=all)

# Stack mínima da localização fiscal brasileira validada neste template.
# Uma linha só: em Make, barra-invertida + quebra vira um espaço, e o espaço
# faz o Odoo tratar o resto da lista como argumentos soltos.
BR_MODULES := l10n_br_base,l10n_br_zip,l10n_br_coa_generic,l10n_br_account,l10n_br_fiscal,l10n_br_nfe,l10n_br_purchase,l10n_br_sale,l10n_br_stock_account

.PHONY: help init fetch check-updates config build up down restart logs ps \
        install install-br update shell psql deps test new-module reset

help:
	@echo "Setup de um projeto novo:"
	@echo "  make init             cp .env.example .env, baixa OCA, gera config, sobe tudo"
	@echo
	@echo "Ambiente:"
	@echo "  make up / down / restart / logs / ps"
	@echo "  make build            reconstrói a imagem (após mexer no Dockerfile)"
	@echo "  make reset            APAGA os dados (volumes) e sobe do zero"
	@echo
	@echo "Dependências OCA:"
	@echo "  make fetch            clona/atualiza addons/oca/ conforme oca-repos.conf"
	@echo "  make check-updates    mostra o que mudou nos branches OCA desde os pins"
	@echo "  make config           regenera config/odoo.conf (.env + oca-repos.conf)"
	@echo "  make deps             confere o fecho de dependências antes de instalar"
	@echo
	@echo "Módulos:"
	@echo "  make install-br       instala a localização fiscal brasileira (sem demo)"
	@echo "  make install-br DEMO=1  idem, com dados de demonstração"
	@echo "  make install m=a,b    instala módulos"
	@echo "  make update m=a,b     atualiza módulos (use após mexer no seu código)"
	@echo "  make new-module name=x  cria o esqueleto de um módulo em addons/local/"
	@echo
	@echo "Diagnóstico:"
	@echo "  make shell / psql     shell do ORM / psql no banco"
	@echo "  make test             roda a suíte de testes da OCA"
	@echo
	@echo "PROJECT=$(PROJECT)  banco=$(PROJECT)  porta=$(ODOO_PORT)"

init:
	@test -f .env || (cp .env.example .env && echo "-> .env criado a partir do .env.example. Ajuste PROJECT e ADMIN_PASSWD e rode 'make init' de novo." && exit 1)
	@$(MAKE) fetch config build up
	@echo
	@echo "Ambiente no ar em http://localhost:$(ODOO_PORT)"
	@echo "Próximo passo: make install-br"

fetch:
	@./scripts/fetch-oca.sh

check-updates:
	@./scripts/fetch-oca.sh --check-updates

config:
	@./scripts/render-config.sh

build:
	@$(DC) build odoo

up:
	@$(DC) up -d

down:
	@$(DC) down

restart:
	@$(DC) restart odoo

logs:
	@$(DC) logs -f odoo

ps:
	@$(DC) ps

install-br:
	@$(MAKE) install m="$(BR_MODULES)"

install:
	@test -n "$(m)" || (echo "uso: make install m=modulo1,modulo2" >&2; exit 1)
	$(ODOO) -d $(PROJECT) -i $(m) $(DEMO_FLAG) --load-language=pt_BR --stop-after-init
	@$(DC) restart odoo

update:
	@test -n "$(m)" || (echo "uso: make update m=modulo1,modulo2" >&2; exit 1)
	$(ODOO) -d $(PROJECT) -u $(m) --stop-after-init
	@$(DC) restart odoo

shell:
	@$(DC) exec odoo odoo shell -c /etc/odoo/odoo.conf -d $(PROJECT) --no-http

psql:
	@$(DC) exec db psql -U $(DB_USER) -d $(PROJECT)

deps:
	@$(DC) exec -T -e MODULES="$(if $(m),$(m),$(BR_MODULES))" odoo python3 - < scripts/check-deps.py

# A suíte roda destacada dentro do container e numa porta livre: com '&' no host
# o processo morre junto com o shell e o log fica truncado, dando falso sucesso.
# Não rode 'make restart/down/build' enquanto ela estiver rodando — o processo
# vai junto com o container e o log congela no meio, sem falha aparente.
test:
	@$(DC) exec -T db dropdb -U $(DB_USER) --if-exists $(PROJECT)_test
	@$(DC) exec -d odoo bash -c "odoo -c /etc/odoo/odoo.conf -d $(PROJECT)_test \
	  --http-port=8099 --test-enable --stop-after-init --log-level=test \
	  -i $(BR_MODULES) \
	  --test-tags '/l10n_br_base,/l10n_br_fiscal,/l10n_br_coa_generic,/l10n_br_account,/l10n_br_nfe,/l10n_br_purchase,/l10n_br_sale,/l10n_br_stock_account,/spec_driven_model' \
	  > /tmp/test.log 2>&1; echo \"RUN-FINISHED rc=\$$?\" >> /tmp/test.log"
	@echo "Suíte rodando. Acompanhe com:  make test-status"

.PHONY: test-status
# A conclusão é detectada por um sentinela gravado no fim do log, não por
# pgrep: qualquer padrão passado ao pgrep -f aparece na linha de comando do
# próprio shell que o executa, e ele casa consigo mesmo.
test-status:
	@$(DC) exec -T odoo bash -c '\
	  if grep -q "^RUN-FINISHED" /tmp/test.log; then echo "STATUS: $$(grep "^RUN-FINISHED" /tmp/test.log)"; else echo "STATUS: rodando"; fi; \
	  echo "testes iniciados: $$(grep -cE "Starting .*\.\.\." /tmp/test.log)"; \
	  echo "falhas:           $$(grep -cE " (FAIL|ERROR): " /tmp/test.log)"; \
	  grep -E " (FAIL|ERROR): " /tmp/test.log | head -10'

new-module:
	@test -n "$(name)" || (echo "uso: make new-module name=l10n_br_acme" >&2; exit 1)
	@./scripts/new-module.sh $(name)

reset:
	@echo "Isso APAGA o banco e os arquivos do Odoo do projeto $(PROJECT)."
	@read -p "Digite o nome do projeto para confirmar: " c; \
	  [ "$$c" = "$(PROJECT)" ] || { echo "cancelado"; exit 1; }
	@$(DC) down -v && $(DC) up -d
