# Popula uma base de DEMONSTRAÇÃO de oficina mecânica: empresa, cadastros,
# peças com NCM, serviços (LC 116 item 14.01), estoque, ordens de serviço,
# compras e um PDV de balcão. Tudo fictício — CNPJ/CPF/IE só têm dígito
# verificador válido para passar nas validações da OCA.
#
# Roda dentro do `odoo shell` (recebe `env` pronto). Use pelo make, que cria o
# banco separado antes:   make demo-oficina
#
# Nunca rode isto no banco de um cliente: a empresa principal é reescrita.

from datetime import timedelta

from odoo import Command, fields
from odoo.tests import Form

MARCADOR = "demo_oficina.populado"


def ean13(seq):
    """EAN-13 fictício com prefixo do Brasil (789) e dígito verificador correto,
    para o leitor de código de barras funcionar na demonstração do PDV."""
    base = f"7890000{seq:05d}"
    soma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base))
    return base + str((10 - soma % 10) % 10)


def configura_empresa(env):
    empresa = env.ref("base.main_company")
    sp = env.ref("base.state_br_sp")
    empresa.partner_id.write(
        {
            "name": "Auto Center Exemplo",
            "legal_name": "Auto Center Exemplo Serviços Automotivos Ltda",
            "is_company": True,
            "fiscal_profile_id": env.ref(
                "l10n_br_fiscal.partner_fiscal_profile_snc"
            ).id,
            "vat": "10.433.218/0001-93",
            "l10n_br_ie_code": "526.018.151.907",
            "street_name": "Avenida dos Mecânicos",
            "street_number": "1250",
            "district": "Vila Industrial",
            "zip": "03178-200",
            "country_id": env.ref("base.br").id,
            "state_id": sp.id,
            "city_id": env.ref("l10n_br_base.city_3550308").id,
            "city": "São Paulo",
            "phone": "(11) 3456-7890",
            "email": "contato@autocenterexemplo.com.br",
            "website": "www.autocenterexemplo.com.br",
        }
    )
    empresa.write(
        {
            "name": "Auto Center Exemplo",
            "currency_id": env.ref("base.BRL").id,
            "tax_framework": "1",  # Simples Nacional
            "cnae_main_id": env.ref("l10n_br_fiscal.cnae_4520001").id,
            "legal_nature_id": env.ref("l10n_br_fiscal.legal_nature_2062").id,
            "piscofins_id": env.ref(
                "l10n_br_fiscal.tax_pis_cofins_simples_nacional"
            ).id,
            "tax_icms_id": env.ref("l10n_br_fiscal.tax_icms_sn_com_credito").id,
            "sale_fiscal_operation_id": env.ref("l10n_br_fiscal.fo_venda").id,
            "purchase_fiscal_operation_id": env.ref("l10n_br_fiscal.fo_compras").id,
            # Senão a primeira entrega validada abre um assistente de SMS ao
            # cliente — inclusive no meio da apresentação.
            "stock_move_sms_validation": False,
        }
    )
    # O banco nasce com o plano genérico do Odoo (a empresa ainda não era BR
    # quando o módulo account foi instalado). Sem lançamentos, dá para trocar.
    if empresa.chart_template != "br_oca_generic":
        env["account.chart.template"].try_loading(
            "br_oca_generic", empresa, install_demo=False
        )
    return empresa


def configura_usuarios(env, empresa):
    pt_br = env["res.lang"]._activate_lang("pt_BR")
    admin = env.ref("base.user_admin")
    admin.write(
        {"name": "Administrador", "lang": pt_br.code, "tz": "America/Sao_Paulo"}
    )
    empresa.partner_id.lang = pt_br.code

    def grupos(*xmlids):
        return [Command.link(env.ref(x).id) for x in xmlids]

    usuarios = [
        (
            "Carla Souza (Balcão)",
            "balcao",
            grupos(
                "base.group_user",
                "point_of_sale.group_pos_user",
                "sales_team.group_sale_salesman",
                "stock.group_stock_user",
            ),
        ),
        (
            "Rafael Lima (Consultor técnico)",
            "consultor",
            grupos(
                "base.group_user",
                "sales_team.group_sale_salesman_all_leads",
                "stock.group_stock_user",
                "purchase.group_purchase_user",
            ),
        ),
    ]
    criados = env["res.users"]
    for nome, login, grupos_ in usuarios:
        criados |= env["res.users"].create(
            {
                "name": nome,
                "login": login,
                "password": login,
                "lang": pt_br.code,
                "tz": "America/Sao_Paulo",
                "company_id": empresa.id,
                "company_ids": [Command.link(empresa.id)],
                "groups_id": grupos_,
            }
        )
    return criados


def cria_parceiros(env):
    sp = env.ref("base.state_br_sp").id
    br = env.ref("base.br").id
    sao_paulo = env.ref("l10n_br_base.city_3550308").id
    # O perfil padrão é decidido antes de is_company valer (cai em pessoa física
    # não contribuinte): PJ precisa do perfil explícito para sair como
    # contribuinte de ICMS e pegar a operação fiscal certa.
    contribuinte = env.ref("l10n_br_fiscal.partner_fiscal_profile_cnt").id

    def endereco(rua, numero, bairro, cep):
        return {
            "street_name": rua,
            "street_number": numero,
            "district": bairro,
            "zip": cep,
            "country_id": br,
            "state_id": sp,
            "city_id": sao_paulo,
            "city": "São Paulo",
        }

    # (nome, cpf, telefone, e-mail, endereço, veículos)
    pessoas = [
        ("Marcos Antônio Pereira", "809.570.154-88", "(11) 98123-4567",
         "marcos.pereira@email.com.br",
         endereco("Rua das Acácias", "45", "Mooca", "03104-020"),
         "VW Gol 1.6 2018 — placa FHT2A31"),
        ("Juliana Ferreira Costa", "303.911.718-10", "(11) 99234-5678",
         "juliana.costa@email.com.br",
         endereco("Rua Coronel Rodovalho", "312", "Penha", "03632-000"),
         "Chevrolet Onix 1.0 Turbo 2021 — placa GKD7B12"),
        ("Roberto Almeida Santos", "227.824.896-07", "(11) 97345-6789",
         "roberto.santos@email.com.br",
         endereco("Rua Tuiuti", "980", "Tatuapé", "03081-000"),
         "Fiat Strada 1.3 2022 — placa EQP4C56\nHonda Civic 2.0 2017 — placa FJR8E19"),
        ("Patrícia Gomes Oliveira", "383.465.787-50", "(11) 96456-7890",
         "patricia.oliveira@email.com.br",
         endereco("Avenida Celso Garcia", "2200", "Belenzinho", "03015-000"),
         "Hyundai HB20 1.0 2020 — placa DZE3F45"),
        ("Fernando Ribeiro Lopes", "133.150.983-10", "(11) 95567-8901",
         "fernando.lopes@email.com.br",
         endereco("Rua Siqueira Bueno", "1500", "Belenzinho", "03173-010"),
         "Toyota Corolla 2.0 2019 — placa FRL1G23"),
    ]
    clientes = env["res.partner"]
    for nome, cpf, fone, email, end, veiculos in pessoas:
        clientes |= env["res.partner"].create(
            {
                "name": nome,
                "vat": cpf,
                "phone": fone,
                "email": email,
                "comment": f"<p>Veículos:<br/>{veiculos.replace(chr(10), '<br/>')}</p>",
                **end,
            }
        )

    # (nome, razão social, cnpj, ie, telefone, e-mail, endereço, observação)
    empresas = [
        ("Transportadora Rota Leste", "Transportadora Rota Leste Ltda",
         "83.863.794/0001-44", "830.166.136.186", "(11) 3211-4400",
         "frota@rotaleste.com.br",
         endereco("Rua Guaianases", "700", "Vila Matilde", "03510-000"),
         "Cliente frotista: 12 veículos leves. Faturamento mensal, 28 dias."),
        ("Locadora Bom Caminho", "Bom Caminho Locação de Veículos Ltda",
         "15.594.078/0001-59", "609.139.099.965", "(11) 3322-5500",
         "manutencao@bomcaminho.com.br",
         endereco("Avenida Aricanduva", "5555", "Aricanduva", "03527-000"),
         "Cliente frotista: revisões preventivas a cada 10.000 km."),
    ]
    frotistas = env["res.partner"]
    for nome, razao, cnpj, ie, fone, email, end, obs in empresas:
        frotistas |= env["res.partner"].create(
            {
                "name": nome,
                "legal_name": razao,
                "is_company": True,
                "vat": cnpj,
                "l10n_br_ie_code": ie,
                "fiscal_profile_id": contribuinte,
                "phone": fone,
                "email": email,
                "comment": f"<p>{obs}</p>",
                **end,
            }
        )

    fornecedores_dados = [
        ("Distribuidora AutoPeças Paulista", "AutoPeças Paulista Distribuidora Ltda",
         "34.131.647/0001-74", "030.824.623.818", "(11) 2233-1100",
         "vendas@autopecaspaulista.com.br",
         endereco("Rua do Gasômetro", "410", "Brás", "03004-000")),
        ("LubriMax Lubrificantes", "LubriMax Comércio de Lubrificantes Ltda",
         "27.648.350/0001-15", "948.219.933.515", "(11) 2344-2200",
         "pedidos@lubrimax.com.br",
         endereco("Avenida Presidente Wilson", "3100", "Ipiranga", "04220-000")),
        ("Pneus & Cia Atacado", "Pneus e Cia Atacadista Ltda",
         "67.242.388/0001-08", "819.093.785.659", "(11) 2455-3300",
         "comercial@pneusecia.com.br",
         endereco("Rodovia Presidente Dutra", "1800", "Vila Maria", "02151-000")),
    ]
    fornecedores = env["res.partner"]
    for nome, razao, cnpj, ie, fone, email, end in fornecedores_dados:
        fornecedores |= env["res.partner"].create(
            {
                "name": nome,
                "legal_name": razao,
                "is_company": True,
                "vat": cnpj,
                "l10n_br_ie_code": ie,
                "fiscal_profile_id": contribuinte,
                "phone": fone,
                "email": email,
                "supplier_rank": 1,
                **end,
            }
        )
    return clientes, frotistas, fornecedores


def cria_categorias(env):
    categ = env["product.category"]
    pos_categ = env["pos.category"]
    raiz = categ.create({"name": "Oficina"})
    # nome: (cor da categoria no PDV)
    nomes = {
        "Peças": 1,
        "Lubrificantes e Fluidos": 3,
        "Pneus": 4,
        "Serviços": 10,
    }
    categorias = {}
    for seq, (nome, cor) in enumerate(nomes.items()):
        categorias[nome] = (
            categ.create({"name": nome, "parent_id": raiz.id}),
            pos_categ.create({"name": nome, "sequence": seq, "color": cor}),
        )
    return categorias


def cria_produtos(env, categorias):
    ref = env.ref
    # (nome, código, NCM, categoria, custo, preço)
    pecas = [
        ("Óleo de motor 5W30 sintético 1L", "LUB-5W30", "27101932",
         "Lubrificantes e Fluidos", 28.90, 54.90),
        ("Óleo de motor 15W40 semissintético 1L", "LUB-15W40", "27101932",
         "Lubrificantes e Fluidos", 19.50, 38.90),
        ("Fluido de freio DOT 4 500ml", "FLU-DOT4", "38190000",
         "Lubrificantes e Fluidos", 17.80, 34.90),
        ("Aditivo para radiador concentrado 1L", "FLU-ADT", "38200000",
         "Lubrificantes e Fluidos", 14.20, 29.90),
        ("Filtro de óleo", "FIL-OLEO", "84212300", "Peças", 16.40, 39.90),
        ("Filtro de ar do motor", "FIL-AR", "84213100", "Peças", 22.10, 49.90),
        ("Filtro de combustível", "FIL-COMB", "84212300", "Peças", 18.70, 44.90),
        ("Filtro de ar-condicionado (cabine)", "FIL-CAB", "84213100", "Peças",
         21.30, 54.90),
        ("Jogo de pastilhas de freio dianteiras", "FRE-PAST", "68138110", "Peças",
         68.00, 149.90),
        ("Disco de freio ventilado (par)", "FRE-DISC", "87083090", "Peças",
         189.00, 389.90),
        ("Vela de ignição (unidade)", "IGN-VELA", "85111000", "Peças", 19.90, 42.90),
        ("Correia dentada", "MOT-CORR", "40103100", "Peças", 79.00, 169.90),
        ("Bomba d'água", "MOT-BOMB", "84133090", "Peças", 115.00, 249.90),
        ("Kit de embreagem", "TRA-EMBR", "87089300", "Peças", 420.00, 849.90),
        ("Amortecedor dianteiro", "SUS-AMOR", "87088000", "Peças", 165.00, 329.90),
        ("Bateria 60Ah", "ELE-BAT60", "85071010", "Peças", 349.00, 599.90),
        ("Lâmpada H4 halógena 12V", "ELE-H4", "85392110", "Peças", 12.50, 29.90),
        ("Palheta do limpador (par)", "ACE-PALH", "85129000", "Peças", 24.00, 59.90),
        ("Pneu 175/70 R14", "PNE-17570", "40111000", "Pneus", 289.00, 469.90),
        ("Pneu 185/65 R15", "PNE-18565", "40111000", "Pneus", 329.00, 529.90),
    ]
    # (nome, código, preço)
    servicos = [
        ("Troca de óleo e filtro (mão de obra)", "SRV-OLEO", 60.00),
        ("Alinhamento de direção", "SRV-ALIN", 90.00),
        ("Balanceamento (por roda)", "SRV-BAL", 25.00),
        ("Revisão preventiva 10.000 km", "SRV-REV10", 280.00),
        ("Diagnóstico eletrônico (scanner)", "SRV-DIAG", 150.00),
        ("Troca de pastilhas de freio (mão de obra)", "SRV-FREIO", 120.00),
        ("Troca de correia dentada (mão de obra)", "SRV-CORR", 350.00),
        ("Higienização do ar-condicionado", "SRV-ARCOND", 140.00),
    ]

    produtos = {}
    for seq, (nome, codigo, ncm, cat, custo, preco) in enumerate(pecas, start=1):
        categ, pos_categ = categorias[cat]
        tmpl = env["product.template"].create(
            {
                "name": nome,
                "default_code": codigo,
                "barcode": ean13(seq),
                "type": "consu",
                "is_storable": True,
                "categ_id": categ.id,
                "pos_categ_ids": [Command.set(pos_categ.ids)],
                "available_in_pos": True,
                "standard_price": custo,
                "list_price": preco,
                "ncm_id": ref(f"l10n_br_fiscal.ncm_{ncm}").id,
                "fiscal_type": "00",  # Mercadoria para revenda
                "icms_origin": "0",  # Nacional
            }
        )
        produtos[codigo] = tmpl.product_variant_id

    categ, pos_categ = categorias["Serviços"]
    for nome, codigo, preco in servicos:
        tmpl = env["product.template"].create(
            {
                "name": nome,
                "default_code": codigo,
                "type": "service",
                "categ_id": categ.id,
                "pos_categ_ids": [Command.set(pos_categ.ids)],
                "available_in_pos": True,
                "list_price": preco,
                "ncm_id": ref("l10n_br_fiscal.ncm_00000000").id,
                "fiscal_type": "09",  # Serviços
                # Explícito: o default do campo (ICMS) vence o compute no create,
                # e o serviço cairia na operação "Serviço de Industrialização".
                "tax_icms_or_issqn": "issqn",
                # LC 116, 14.01: lubrificação, revisão, conserto e manutenção de veículos
                "service_type_id": ref("l10n_br_fiscal.service_type_1401").id,
                "nbs_id": ref("l10n_br_fiscal.nbs_120013110").id,
            }
        )
        produtos[codigo] = tmpl.product_variant_id
    return produtos


def ajusta_estoque(env, produtos):
    estoque = env.ref("stock.warehouse0").lot_stock_id
    # Algumas peças de propósito abaixo do mínimo, para a demonstração de
    # reposição (Compras) ter o que mostrar.
    quantidades = {
        "LUB-5W30": 48, "LUB-15W40": 36, "FLU-DOT4": 20, "FLU-ADT": 18,
        "FIL-OLEO": 30, "FIL-AR": 22, "FIL-COMB": 15, "FIL-CAB": 12,
        "FRE-PAST": 10, "FRE-DISC": 4, "IGN-VELA": 40, "MOT-CORR": 6,
        "MOT-BOMB": 3, "TRA-EMBR": 2, "SUS-AMOR": 4, "ELE-BAT60": 5,
        "ELE-H4": 25, "ACE-PALH": 14, "PNE-17570": 8, "PNE-18565": 2,
    }
    quants = env["stock.quant"]
    for codigo, qtd in quantidades.items():
        quants |= env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": produtos[codigo].id,
                "location_id": estoque.id,
                "inventory_quantity": qtd,
            }
        )
    quants.action_apply_inventory()

    # Regras de reposição: Compras sugere pedido quando cair abaixo do mínimo.
    for codigo, minimo, maximo in [
        ("PNE-18565", 4, 12), ("TRA-EMBR", 2, 4), ("MOT-BOMB", 2, 6),
        ("FIL-OLEO", 15, 40), ("LUB-5W30", 24, 60),
    ]:
        env["stock.warehouse.orderpoint"].create(
            {
                "product_id": produtos[codigo].id,
                "location_id": estoque.id,
                "product_min_qty": minimo,
                "product_max_qty": maximo,
            }
        )


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
            # é melhor que deixar a OS "entregue" com a separação pendente.
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


def cria_ordens_de_servico(env, clientes, frotistas, produtos, usuarios):
    consultor = usuarios.filtered(lambda u: u.login == "consultor")
    agora = fields.Datetime.now()

    # (cliente, placa/veículo, dias atrás, situação, [(código, qtd)], observação)
    # situação: rascunho | enviado | confirmado | entregue
    ordens = [
        (clientes[0], "FHT2A31 · VW Gol 1.6 2018", 18, "entregue",
         [("LUB-15W40", 4), ("FIL-OLEO", 1), ("SRV-OLEO", 1)],
         "Troca de óleo com 60.120 km. Próxima troca: 70.000 km."),
        (clientes[1], "GKD7B12 · Chevrolet Onix 1.0 Turbo 2021", 12, "entregue",
         [("FRE-PAST", 1), ("FLU-DOT4", 1), ("SRV-FREIO", 1)],
         "Cliente relatou ruído ao frear. Pastilhas no limite."),
        (frotistas[0], "FMA9D88 · VW Delivery Express 2020", 9, "entregue",
         [("SRV-REV10", 1), ("LUB-15W40", 8), ("FIL-OLEO", 1), ("FIL-AR", 1),
          ("FIL-COMB", 1)],
         "Revisão preventiva conforme contrato de frota."),
        (clientes[2], "EQP4C56 · Fiat Strada 1.3 2022", 4, "confirmado",
         [("MOT-CORR", 1), ("MOT-BOMB", 1), ("SRV-CORR", 1)],
         "Troca preventiva de correia dentada e bomba d'água. Veículo no box 2."),
        (frotistas[1], "QWE5H67 · Renault Kwid 1.0 2023", 3, "confirmado",
         [("SRV-ALIN", 1), ("SRV-BAL", 4), ("PNE-17570", 2)],
         "Dois pneus dianteiros novos, alinhamento e balanceamento."),
        (clientes[3], "DZE3F45 · Hyundai HB20 1.0 2020", 2, "enviado",
         [("SRV-DIAG", 1), ("ELE-BAT60", 1)],
         "Luz de injeção acesa. Orçamento enviado por WhatsApp, aguardando aprovação."),
        (clientes[4], "FRL1G23 · Toyota Corolla 2.0 2019", 1, "enviado",
         [("TRA-EMBR", 1), ("SUS-AMOR", 2)],
         "Embreagem patinando e amortecedores dianteiros vazando."),
        (clientes[0], "FHT2A31 · VW Gol 1.6 2018", 0, "rascunho",
         [("SRV-ARCOND", 1), ("FIL-CAB", 1)],
         "Cliente pediu orçamento de higienização do ar-condicionado."),
    ]
    pedidos = env["sale.order"]
    for cliente, veiculo, dias, situacao, itens, obs in ordens:
        pedido = novo_pedido(
            env,
            "sale.order",
            {"partner_id": cliente, "user_id": consultor, "client_order_ref": veiculo},
            [(produtos[codigo], qtd, None) for codigo, qtd in itens],
            "product_uom_qty",
        )
        pedido.note = obs
        if situacao == "enviado":
            pedido.action_quotation_sent()
        elif situacao in ("confirmado", "entregue"):
            pedido.action_confirm()
            if situacao == "entregue":
                entrega(pedido)
        # Datas espalhadas no passado, para os painéis terem histórico.
        pedido.date_order = agora - timedelta(days=dias, hours=dias % 5)
        pedidos |= pedido
    return pedidos


def cria_compras(env, fornecedores, produtos):
    autopecas, lubrimax, pneus = fornecedores

    def compra(fornecedor, itens):
        return novo_pedido(
            env,
            "purchase.order",
            {"partner_id": fornecedor},
            [(produtos[codigo], qtd, preco) for codigo, qtd, preco in itens],
            "product_qty",
        )

    # Recebida: mostra a entrada no estoque.
    recebida = compra(lubrimax, [("LUB-5W30", 24, 28.90), ("FLU-DOT4", 12, 17.80)])
    recebida.button_confirm()
    entrega(recebida)

    # Confirmada, aguardando o fornecedor entregar.
    compra(pneus, [("PNE-18565", 8, 329.00)]).button_confirm()

    # Pedido de cotação ainda não enviado.
    compra(autopecas, [("TRA-EMBR", 2, 420.00), ("MOT-BOMB", 3, 115.00)])


def cria_pdv(env, empresa):
    diario_vendas = env["account.journal"]._ensure_company_account_journal()
    banco = env["account.journal"].search(
        [("type", "=", "bank"), ("company_id", "=", empresa.id)], limit=1
    )
    caixa = env["account.journal"].create(
        {
            "name": "Caixa Balcão",
            "code": "CXBAL",
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
            # Fiado de frotista: vai para contas a receber do cliente.
            {"name": "Faturar para o cliente", "split_transactions": True,
             "sequence": 5},
        ]
    )
    return env["pos.config"].create(
        {
            "name": "Balcão de Peças",
            "company_id": empresa.id,
            "journal_id": diario_vendas.id,
            "payment_method_ids": [Command.set(metodos.ids)],
            "is_header_or_footer": True,
            "receipt_header": "Auto Center Exemplo\nMecânica em geral · Peças · Pneus",
            "receipt_footer": "Garantia de 90 dias para serviços.\n"
            "Documento sem valor fiscal (demonstração).",
        }
    )


def main(env):
    icp = env["ir.config_parameter"].sudo()
    if icp.get_param(MARCADOR):
        print("Base já populada com a demonstração da oficina; nada a fazer.")
        return

    empresa = configura_empresa(env)
    usuarios = configura_usuarios(env, empresa)
    clientes, frotistas, fornecedores = cria_parceiros(env)
    categorias = cria_categorias(env)
    produtos = cria_produtos(env, categorias)
    ajusta_estoque(env, produtos)
    cria_compras(env, fornecedores, produtos)
    pedidos = cria_ordens_de_servico(env, clientes, frotistas, produtos, usuarios)
    pdv = cria_pdv(env, empresa)

    icp.set_param(MARCADOR, fields.Datetime.now())
    env.cr.commit()

    print(
        f"Demonstração da oficina criada: {len(produtos)} produtos/serviços, "
        f"{len(clientes) + len(frotistas)} clientes, {len(fornecedores)} "
        f"fornecedores, {len(pedidos)} ordens de serviço, PDV id={pdv.id}."
    )


main(env)  # noqa: F821 — `env` vem do odoo shell
