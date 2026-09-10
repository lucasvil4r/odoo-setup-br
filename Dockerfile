FROM odoo:18.0

# Dependências Python exigidas pelos manifests da OCA l10n-brazil (branch 18.0).
# Ver addons/l10n-brazil/requirements.txt — replicadas aqui para que o ambiente seja
# reproduzível: instalar via pip num container em execução se perde no proximo recreate.
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential python3-dev libxml2-dev libxslt1-dev libffi-dev libssl-dev \
    `# packaging nao vem na imagem odoo:18.0, mas o Odoo precisa dele para interpretar` \
    `# os external_dependencies dos manifests — sem ele a instalacao da OCA falha.` \
    `# typing_extensions/cryptography/pyOpenSSL vem do apt sem RECORD, entao o pip nao` \
    `# consegue desinstala-los; --ignore-installed instala por cima. pyOpenSSL precisa` \
    `# subir junto com cryptography: a versao do apt quebra o boot do Odoo com o novo.` \
    && pip3 install --no-cache-dir --break-system-packages \
        packaging \
    && pip3 install --no-cache-dir --break-system-packages --ignore-installed \
        typing_extensions cryptography pyOpenSSL \
    && pip3 install --no-cache-dir --break-system-packages \
        brazilcep \
        brazilfiscalreport \
        email-validator \
        erpbrasil.assinatura \
        erpbrasil.base \
        erpbrasil.edoc \
        erpbrasil.transmissao \
        nfelib \
        nfselib.paulistana \
        transitions \
        workalendar \
    `# dependencias usadas apenas pelos testes da OCA (odoo --test-enable):` \
    `# odoo-test-helper e exigido por spec_driven_model; xmldiff pelos testes de` \
    `# serializacao de NFe, que comparam o XML gerado com um XML de referencia.` \
    && pip3 install --no-cache-dir --break-system-packages \
        odoo-test-helper \
        xmldiff \
    && apt-get purge -y build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

USER odoo
