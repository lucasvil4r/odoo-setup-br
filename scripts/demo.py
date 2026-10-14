# Popula uma base de DEMONSTRAÇÃO a partir de uma pasta de dados:
#
#   demo/<nome>/demo.toml       empresa, usuários, PDV, vendas e compras
#   demo/<nome>/produtos.csv    catálogo (produtos e serviços)
#   demo/<nome>/parceiros.csv   clientes e fornecedores
#   demo/<nome>/fotos/          fotos dos produtos (opcional)
#   demo/<nome>/logo.png        logo da empresa (opcional)
#
# O código não sabe nada de nenhum cliente: trocar a demonstração é trocar a
# pasta. demo/oficina é o exemplo que acompanha o template.
#
# Roda dentro do `odoo shell` (recebe `env` pronto), com DEMO_DIR apontando
# para a pasta montada no container. Use pelo make, que cria o banco antes:
#   make demo                    (pasta definida por DEMO_DADOS no .env)
#
# Nunca rode isto no banco de um cliente: a empresa principal é reescrita.

import base64
import csv
import html
import io
import os
import re
import tomllib
from datetime import timedelta
from pathlib import Path

from odoo import Command, fields
from odoo.tests import Form

MARCADOR = "demo.populado"
PASTA = Path(os.environ["DEMO_DIR"])

# Papéis do demo.toml -> grupos do Odoo. Um xmlid completo também é aceito.
PAPEIS = {
    "pdv": "point_of_sale.group_pos_user",
    "vendas": "sales_team.group_sale_salesman",
    "vendas_todas": "sales_team.group_sale_salesman_all_leads",
    "estoque": "stock.group_stock_user",
    "compras": "purchase.group_purchase_user",
}

# Cores das categorias no PDV, na ordem em que aparecem na planilha.
CORES_PDV = [1, 3, 4, 2, 5, 6, 7, 8, 9, 11, 10]


def le_planilha(nome):
    """Lê um CSV salvo pelo Excel ou à mão: aceita ';' ou ',' como separador
    e o BOM que o Excel grava no começo do arquivo."""
    texto = (PASTA / nome).read_text(encoding="utf-8-sig")
    separador = ";" if texto.split("\n", 1)[0].count(";") else ","
    # StringIO, e não splitlines(): célula com quebra de linha vem entre aspas,
    # e o csv só a reconhece se receber as quebras originais.
    linhas = csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador)
    return [
        {k.strip(): (v or "").strip() for k, v in linha.items()}
        for linha in linhas
        if any((v or "").strip() for v in linha.values())
    ]


def numero(texto):
    """'1.234,56' (Excel em português) ou '1234.56' -> 1234.56."""
    if not texto:
        return 0.0
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def digitos(texto):
    return re.sub(r"\D", "", texto or "")


def arquivo_b64(nome):
    if not nome:
        return False
    caminho = PASTA / nome
    if not caminho.is_file():
        raise FileNotFoundError(f"{caminho} não existe (citado nos dados da demo)")
    return base64.b64encode(caminho.read_bytes())


def ean13(seq):
    """EAN-13 fictício com prefixo do Brasil (789) e dígito verificador correto,
    para o leitor de código de barras funcionar na demonstração do PDV."""
    base = f"7890000{seq:05d}"
    soma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base))
    return base + str((10 - soma % 10) % 10)


def endereco(env, dados):
    cidade = env.ref(f"l10n_br_base.city_{digitos(dados['cidade_ibge'])}")
    return {
        "street_name": dados["rua"],
        "street_number": dados["numero"],
        "district": dados["bairro"],
        "zip": dados["cep"],
        "country_id": env.ref("base.br").id,
        "state_id": cidade.state_id.id,
        "city_id": cidade.id,
        "city": cidade.name,
    }


def configura_empresa(env, dados):
    if dados.get("regime", "simples") != "simples":
        # As alíquotas abaixo são as do Simples. Outro regime pede outro
        # conjunto de impostos, e errar aqui só aparece ao faturar.
        raise ValueError("demo.toml: só o regime 'simples' é suportado")
    empresa = env.ref("base.main_company")
    empresa.partner_id.write(
        {
            "name": dados["nome"],
            "legal_name": dados["razao_social"],
            "is_company": True,
            "fiscal_profile_id": env.ref(
                "l10n_br_fiscal.partner_fiscal_profile_snc"
            ).id,
            "vat": dados["cnpj"],
            "l10n_br_ie_code": dados.get("ie", ""),
            "phone": dados.get("telefone", ""),
            "email": dados["email"],
            "website": dados.get("site", ""),
            **endereco(env, dados["endereco"]),
        }
    )
    valores = {
        "name": dados["nome"],
        "currency_id": env.ref("base.BRL").id,
        "tax_framework": "1",  # Simples Nacional
        "cnae_main_id": env.ref(f"l10n_br_fiscal.cnae_{digitos(dados['cnae'])}").id,
        "legal_nature_id": env.ref(
            f"l10n_br_fiscal.legal_nature_{digitos(dados['natureza_juridica'])}"
        ).id,
        "piscofins_id": env.ref("l10n_br_fiscal.tax_pis_cofins_simples_nacional").id,
        "tax_icms_id": env.ref("l10n_br_fiscal.tax_icms_sn_com_credito").id,
        "sale_fiscal_operation_id": env.ref("l10n_br_fiscal.fo_venda").id,
        "purchase_fiscal_operation_id": env.ref("l10n_br_fiscal.fo_compras").id,
        # Sem documento padrão, faturar o pedido falha com "You need to set a
        # default fiscal document". Mercadorias saem nele; os serviços, a
        # operação fiscal já manda para NFS-e, em fatura separada.
        "document_type_id": env.ref(
            f"l10n_br_fiscal.document_{dados.get('documento_fiscal', '55')}"
        ).id,
        # Senão a primeira entrega validada abre um assistente de SMS ao
        # cliente — inclusive no meio da apresentação.
        "stock_move_sms_validation": False,
    }
    if dados.get("logo"):
        valores["logo"] = arquivo_b64(dados["logo"])
    # Cores dos relatórios (pedido, fatura): o layout de documento usa estas.
    for campo, chave in (("primary_color", "cor_primaria"),
                         ("secondary_color", "cor_secundaria")):
        if dados.get(chave):
            valores[campo] = dados[chave]
    empresa.write(valores)
    # O banco nasce com o plano genérico do Odoo (a empresa ainda não era BR
    # quando o módulo account foi instalado). Sem lançamentos, dá para trocar.
    if empresa.chart_template != "br_oca_generic":
        env["account.chart.template"].try_loading(
            "br_oca_generic", empresa, install_demo=False
        )
    return empresa


def configura_usuarios(env, empresa, usuarios):
    pt_br = env["res.lang"]._activate_lang("pt_BR")
    dominio = empresa.partner_id.email.split("@")[1]
    # Todo usuário precisa de e-mail: abrir o caixa do PDV registra a nota de
    # abertura no histórico da sessão, e o Odoo recusa mensagem de autor sem
    # e-mail ("Configure o endereço de e-mail do remetente"). Nada é enviado
    # de fato; não há servidor de e-mail configurado.
    env.ref("base.user_admin").write(
        {
            "name": "Administrador",
            "email": f"admin@{dominio}",
            "lang": pt_br.code,
            "tz": "America/Sao_Paulo",
        }
    )
    empresa.partner_id.lang = pt_br.code

    criados = env["res.users"]
    for u in usuarios:
        grupos = ["base.group_user"] + [PAPEIS.get(p, p) for p in u["papeis"]]
        criados |= env["res.users"].create(
            {
                "name": u["nome"],
                "login": u["login"],
                "password": u["login"],
                "email": f"{u['login']}@{dominio}",
                "lang": pt_br.code,
                "tz": "America/Sao_Paulo",
                "company_id": empresa.id,
                "company_ids": [Command.link(empresa.id)],
                "groups_id": [Command.link(env.ref(g).id) for g in grupos],
            }
        )
    return criados


def cria_parceiros(env):
    # O perfil padrão é decidido antes de is_company valer (cai em pessoa física
    # não contribuinte): PJ com IE precisa do perfil explícito para sair como
    # contribuinte de ICMS e pegar a operação fiscal certa.
    contribuinte = env.ref("l10n_br_fiscal.partner_fiscal_profile_cnt").id
    parceiros = {}
    for p in le_planilha("parceiros.csv"):
        pj = len(digitos(p["cpf_cnpj"])) == 14
        valores = {
            "ref": p["ref"],
            "name": p["nome"],
            "vat": p["cpf_cnpj"],
            "phone": p["telefone"],
            "email": p["email"],
            **endereco(env, p),
        }
        if pj:
            valores.update(
                {
                    "is_company": True,
                    "legal_name": p["razao_social"] or p["nome"],
                    "l10n_br_ie_code": p["ie"],
                }
            )
            if p["ie"]:
                valores["fiscal_profile_id"] = contribuinte
        if p["tipo"] == "fornecedor":
            valores["supplier_rank"] = 1
        if p["observacao"]:
            valores["comment"] = "<p>%s</p>" % html.escape(p["observacao"]).replace(
                "\n", "<br/>"
            )
        parceiros[p["ref"]] = env["res.partner"].create(valores)
    return parceiros


def cria_produtos(env, raiz):
    linhas = le_planilha("produtos.csv")
    categ_raiz = env["product.category"].create({"name": raiz})
    categorias = {}
    for linha in linhas:
        nome = linha["categoria"]
        if nome not in categorias:
            seq = len(categorias)
            categorias[nome] = (
                env["product.category"].create({"name": nome, "parent_id": categ_raiz.id}),
                env["pos.category"].create(
                    {"name": nome, "sequence": seq, "color": CORES_PDV[seq % len(CORES_PDV)]}
                ),
            )

    produtos = {}
    seq_ean = 0
    estoque = env.ref("stock.warehouse0").lot_stock_id
    quants = env["stock.quant"]
    for linha in linhas:
        categ, pos_categ = categorias[linha["categoria"]]
        valores = {
            "name": linha["nome"],
            "default_code": linha["codigo"],
            "categ_id": categ.id,
            "pos_categ_ids": [Command.set(pos_categ.ids)],
            "available_in_pos": True,
            "list_price": numero(linha["preco"]),
            "standard_price": numero(linha["custo"]),
        }
        if linha.get("foto"):
            valores["image_1920"] = arquivo_b64(f"fotos/{linha['foto']}")
        if linha["tipo"] == "servico":
            valores.update(
                {
                    "type": "service",
                    "ncm_id": env.ref("l10n_br_fiscal.ncm_00000000").id,
                    "fiscal_type": "09",  # Serviços
                    # Explícito: o default do campo (ICMS) vence o compute no
                    # create, e o serviço cairia em "Serviço de Industrialização".
                    "tax_icms_or_issqn": "issqn",
                    "service_type_id": env.ref(
                        f"l10n_br_fiscal.service_type_{digitos(linha['lc116'])}"
                    ).id,
                    "nbs_id": env.ref(f"l10n_br_fiscal.nbs_{digitos(linha['nbs'])}").id,
                }
            )
        else:
            seq_ean += 1
            valores.update(
                {
                    "type": "consu",
                    "is_storable": True,
                    "barcode": linha.get("codigo_barras") or ean13(seq_ean),
                    "ncm_id": env.ref(f"l10n_br_fiscal.ncm_{digitos(linha['ncm'])}").id,
                    "fiscal_type": "00",  # Mercadoria para revenda
                    "icms_origin": "0",  # Nacional
                }
            )
        produto = env["product.template"].create(valores).product_variant_id
        produtos[linha["codigo"]] = produto

        if linha["tipo"] != "servico" and linha.get("estoque"):
            quants |= env["stock.quant"].with_context(inventory_mode=True).create(
                {
                    "product_id": produto.id,
                    "location_id": estoque.id,
                    "inventory_quantity": numero(linha["estoque"]),
                }
            )
        # Regra de reposição: Compras sugere pedido quando cair abaixo do
        # mínimo. Deixe o estoque abaixo dele em algum item para ter o que
        # mostrar.
        if linha.get("estoque_min"):
            env["stock.warehouse.orderpoint"].create(
                {
                    "product_id": produto.id,
                    "location_id": estoque.id,
                    "product_min_qty": numero(linha["estoque_min"]),
                    "product_max_qty": numero(linha["estoque_max"]),
                }
            )
    quants.action_apply_inventory()
    return produtos


def entrega(pedido):
    for picking in pedido.picking_ids.filtered(
        lambda p: p.state not in ("done", "cancel")
    ):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.move_ids.picked = True
        resultado = picking.with_context(skip_sms=True).button_validate()
        if resultado is not True:
            # Um assistente (backorder, SMS...) pediu confirmação: falhar alto
            # é melhor que deixar o pedido "entregue" com a separação pendente.
            raise RuntimeError(f"{picking.name} não validou: {resultado}")


def novo_pedido(env, modelo, valores, itens, campo_qtd):
    """Cria o pedido pelo Form, que roda os onchanges como a tela faz: é o que
    preenche operação fiscal, CFOP e impostos da OCA em cada linha. Um create
    direto no ORM deixaria esses campos vazios."""
    with Form(env[modelo]) as form:
        for campo, valor in valores.items():
            setattr(form, campo, valor)
        for produto, qtd, preco in itens:
            with form.order_line.new() as linha:
                linha.product_id = produto
                setattr(linha, campo_qtd, qtd)
                if preco is not None:
                    linha.price_unit = preco
    return form.record


def cria_vendas(env, vendas, parceiros, produtos, usuarios):
    agora = fields.Datetime.now()
    pedidos = env["sale.order"]
    for v in vendas:
        valores = {"partner_id": parceiros[v["cliente"]]}
        if v.get("vendedor"):
            valores["user_id"] = usuarios.filtered(lambda u: u.login == v["vendedor"])
        if v.get("referencia"):
            valores["client_order_ref"] = v["referencia"]
        pedido = novo_pedido(
            env,
            "sale.order",
            valores,
            [(produtos[codigo], qtd, None) for codigo, qtd in v["itens"]],
            "product_uom_qty",
        )
        pedido.note = v.get("observacao", "")
        situacao = v["situacao"]  # rascunho | enviado | confirmado | entregue
        if situacao == "enviado":
            pedido.action_quotation_sent()
        elif situacao in ("confirmado", "entregue"):
            pedido.action_confirm()
            if situacao == "entregue":
                entrega(pedido)
        # Datas espalhadas no passado, para os painéis terem histórico.
        dias = v.get("dias_atras", 0)
        pedido.date_order = agora - timedelta(days=dias, hours=dias % 5)
        pedidos |= pedido
    return pedidos


def cria_compras(env, compras, parceiros, produtos):
    for c in compras:
        pedido = novo_pedido(
            env,
            "purchase.order",
            {"partner_id": parceiros[c["fornecedor"]]},
            [(produtos[codigo], qtd, preco) for codigo, qtd, preco in c["itens"]],
            "product_qty",
        )
        situacao = c["situacao"]  # cotacao | confirmada | recebida
        if situacao in ("confirmada", "recebida"):
            pedido.button_confirm()
            if situacao == "recebida":
                entrega(pedido)


def cria_pdv(env, empresa, dados):
    diario_vendas = env["account.journal"]._ensure_company_account_journal()
    banco = env["account.journal"].search(
        [("type", "=", "bank"), ("company_id", "=", empresa.id)], limit=1
    )
    caixa = env["account.journal"].create(
        {
            "name": f"Caixa {dados['nome']}",
            "code": "CXPDV",
            "type": "cash",
            "company_id": empresa.id,
        }
    )
    metodos = env["pos.payment.method"].create(
        [
            {"name": "Dinheiro", "journal_id": caixa.id, "sequence": 1},
            {"name": "PIX", "journal_id": banco.id, "sequence": 2},
            {"name": "Cartão de Débito", "journal_id": banco.id, "sequence": 3},
            {"name": "Cartão de Crédito", "journal_id": banco.id, "sequence": 4},
            # Venda a prazo: vai para contas a receber do cliente.
            {"name": "Faturar para o cliente", "split_transactions": True,
             "sequence": 5},
        ]
    )
    return env["pos.config"].create(
        {
            "name": dados["nome"],
            "company_id": empresa.id,
            "journal_id": diario_vendas.id,
            "payment_method_ids": [Command.set(metodos.ids)],
            "is_header_or_footer": True,
            "receipt_header": dados.get("cabecalho", ""),
            "receipt_footer": dados.get("rodape", ""),
        }
    )


def valida(dados):
    """Confere as referências entre demo.toml e as planilhas antes de gravar
    qualquer coisa: um código digitado errado vira uma lista de erros legível,
    e não um KeyError no meio da criação."""
    produtos = {p["codigo"]: p for p in le_planilha("produtos.csv")}
    parceiros = {p["ref"]: p for p in le_planilha("parceiros.csv")}
    logins = {u["login"] for u in dados.get("usuarios", [])}
    erros = []
    for codigo, p in produtos.items():
        if p["tipo"] not in ("produto", "servico"):
            erros.append(f"produtos.csv {codigo}: tipo '{p['tipo']}' (use produto ou servico)")
        if p["tipo"] == "servico" and not (p["lc116"] and p["nbs"]):
            erros.append(f"produtos.csv {codigo}: serviço sem lc116 ou nbs")
        if p["tipo"] == "produto" and not p["ncm"]:
            erros.append(f"produtos.csv {codigo}: produto sem ncm")
        if p.get("foto") and not (PASTA / "fotos" / p["foto"]).is_file():
            erros.append(f"produtos.csv {codigo}: fotos/{p['foto']} não existe")
    for ref, p in parceiros.items():
        if p["tipo"] not in ("cliente", "fornecedor"):
            erros.append(f"parceiros.csv {ref}: tipo '{p['tipo']}' (use cliente ou fornecedor)")
    for i, v in enumerate(dados.get("vendas", []), 1):
        if v["cliente"] not in parceiros:
            erros.append(f"demo.toml venda {i}: cliente {v['cliente']} não está em parceiros.csv")
        if v.get("vendedor") and v["vendedor"] not in logins:
            erros.append(f"demo.toml venda {i}: vendedor {v['vendedor']} não está em [[usuarios]]")
        erros += [f"demo.toml venda {i}: produto {c} não está em produtos.csv"
                  for c, *_ in v["itens"] if c not in produtos]
    for i, c in enumerate(dados.get("compras", []), 1):
        if c["fornecedor"] not in parceiros:
            erros.append(f"demo.toml compra {i}: fornecedor {c['fornecedor']} não está em parceiros.csv")
        erros += [f"demo.toml compra {i}: produto {p} não está em produtos.csv"
                  for p, *_ in c["itens"] if p not in produtos]
    if erros:
        raise SystemExit("Dados da demo com problema:\n  " + "\n  ".join(erros))


def main(env):
    icp = env["ir.config_parameter"].sudo()
    if icp.get_param(MARCADOR):
        print(f"Base já populada com a demonstração '{icp.get_param(MARCADOR)}'; "
              "nada a fazer. Para recriar: make demo-reset")
        return

    dados = tomllib.loads((PASTA / "demo.toml").read_text(encoding="utf-8"))
    valida(dados)
    empresa = configura_empresa(env, dados["empresa"])
    usuarios = configura_usuarios(env, empresa, dados.get("usuarios", []))
    parceiros = cria_parceiros(env)
    produtos = cria_produtos(env, dados.get("catalogo", {}).get("raiz", empresa.name))
    cria_compras(env, dados.get("compras", []), parceiros, produtos)
    pedidos = cria_vendas(env, dados.get("vendas", []), parceiros, produtos, usuarios)
    pdv = cria_pdv(env, empresa, dados["pdv"])

    icp.set_param(MARCADOR, PASTA.name)
    env.cr.commit()

    print(
        f"Demonstração '{PASTA.name}' criada: {len(produtos)} produtos/serviços, "
        f"{len(parceiros)} parceiros, {len(pedidos)} pedidos de venda, PDV id={pdv.id}."
    )
    print("Usuários (senha = login):")
    print("  admin / admin  Administrador")
    for u in usuarios:
        print(f"  {u.login} / {u.login}  {u.name}")
    print("Atalhos de app no Windows (rode no cmd, na pasta do repositório):")
    print(f"  scripts\\atalhos-windows.bat localhost "
          f"{os.environ.get('ODOO_PORT', '8069')} {env.cr.dbname} {pdv.id}")


main(env)  # noqa: F821 — `env` vem do odoo shell
