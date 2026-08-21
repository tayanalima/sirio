"""Módulo SIRIO — Violência Doméstica e Familiar contra a Mulher (núcleo).

Schema completo do módulo (todas as entidades já criadas nesta Onda 1, para
evitar migrações dolorosas mais adiante) + constantes + funções auxiliares.
As telas (páginas/rotas) de cada parte são construídas onda a onda, em
arquivos próprios (sirio_vd_casos.py nesta onda; sirio_vd_fonar.py,
sirio_vd_protetivas.py etc. nas próximas).

DECISÕES DE PROJETO (documentadas aqui para não se perderem):
  - Pessoas (mulher atendida, suposto autor, testemunhas etc.) REAPROVEITAM
    a tabela `pessoas` já existente no SIRIO — nunca duplicam cadastro. O
    vínculo com o caso e o papel exercido nele ficam em vd_caso_pessoas.
  - Ocorrências do caso REAPROVEITAM a tabela `ocorrencias` já existente
    (inclusive as importadas de Boletim de Ocorrência) — vd_caso_ocorrencias
    só faz o vínculo, não duplica dados do fato.
  - Formas de violência e marcadores operacionais usam o MESMO mecanismo de
    listas configuráveis pelo administrador (tabela opcoes_configuraveis)
    já usado em Tipos de crime, Categorias de material etc. — o
    Administrador gerencia essas listas na mesma aba Configurações, sem
    nenhuma tela nova.
  - O sistema NUNCA calcula uma pontuação de risco nem classifica
    "baixo/médio/alto" automaticamente (ver sirio_vd_fonar.py, Onda 2) —
    isso é decisão profissional, não do sistema.
  - Perfis de acesso: por ora, reaproveita os 3 perfis já existentes do
    SIRIO (consulta/analista/admin), com a mesma semântica de sempre.
    Perfis mais granulares (Gestor, Autoridade policial, Analista com
    dados pseudonimizados etc., conforme o documento original) são uma
    mudança maior no sistema todo — ainda NÃO implementados; ficam para
    quando isso for explicitamente decidido, já que afeta o SIRIO inteiro,
    não só este módulo.
  - Nível de sigilo do caso é um campo registrado e exibido, mas por
    enquanto NÃO restringe automaticamente quem pode ver o quê — isso
    também depende de uma definição institucional de regra (por unidade?
    por perfil? por caso específico?) antes de virar controle de acesso.
"""
from sirio_core import *  # noqa: F401,F403

# ----------------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------------

VD_PAPEIS = [
    ("mulher_atendida", "Mulher atendida"),
    ("suposto_autor", "Suposto autor"),
    ("testemunha", "Testemunha"),
    ("representante_legal", "Representante legal"),
    ("filho_dependente", "Filho(a) ou dependente"),
    ("familiar", "Familiar"),
    ("pessoa_confianca", "Pessoa de confiança"),
    ("profissional_rede", "Profissional da rede de proteção"),
    ("outro", "Outro envolvido"),
]
VD_PAPEL_LABEL = dict(VD_PAPEIS)

# Sugestão automática de papel VD a partir do tipo de envolvimento que o
# leitor de BO identifica — usa a própria terminologia do REDS (ex.: "VÍTIMA
# DE AÇÃO CRIMINAL / CÍVEL") para sugerir o papel mais provável. É só o valor
# inicial no formulário de revisão; a pessoa que revisa pode sempre trocar.
def vd_sugestao_papel(tipo_envolvimento):
    if not tipo_envolvimento:
        return ""
    t = tipo_envolvimento.upper()
    # sem acento tambem, ja que a extração do PDF às vezes perde acentuação
    t_sem_acento = (t.replace("Í", "I").replace("É", "E").replace("Á", "A")
                    .replace("Ã", "A").replace("Ê", "E").replace("Ç", "C"))
    if "AUTOR" in t:
        return "suposto_autor"
    if "VITIMA" in t_sem_acento:
        return "mulher_atendida"
    if "REPRESENTANTE LEGAL" in t:
        return "representante_legal"
    if "TESTEMUNHA" in t:
        return "testemunha"
    return ""

VD_SITUACOES = [
    ("rascunho", "Rascunho"),
    ("atendimento_iniciado", "Atendimento iniciado"),
    ("aguardando_providencia", "Aguardando providência"),
    ("em_apuracao", "Em apuração"),
    ("medida_solicitada", "Medida protetiva solicitada"),
    ("aguardando_decisao", "Aguardando decisão"),
    ("medida_deferida", "Medida deferida"),
    ("acompanhamento", "Em acompanhamento"),
    ("suspenso", "Suspenso"),
    ("encerrado", "Encerrado"),
    ("reaberto", "Reaberto"),
    # Cadastro feito por engano (duplicado, teste, dados trocados). Sai das
    # listagens e dos painéis, mas continua no banco e pode ser revertido.
    # Não confundir com "Encerrado", que é desfecho real de um caso real.
    ("cancelado", "Cancelado (cadastro incorreto)"),
]

# Situações que representam registro que não deve entrar em listagem nem em
# estatística. Hoje só o cancelamento.
VD_SITUACOES_OCULTAS = ("cancelado",)
VD_SITUACAO_LABEL = dict(VD_SITUACOES)

VD_NIVEIS_SIGILO = [
    ("normal", "Normal"),
    ("restrito", "Restrito"),
    ("sigiloso", "Sigiloso"),
]
VD_SIGILO_LABEL = dict(VD_NIVEIS_SIGILO)

VD_SITUACOES_MEDIDA = [
    ("em_elaboracao", "Em elaboração"),
    ("solicitada", "Solicitada"),
    ("enviada", "Enviada ao juízo"),
    ("aguardando_decisao", "Aguardando decisão"),
    ("deferida", "Deferida"),
    ("parcialmente_deferida", "Parcialmente deferida"),
    ("indeferida", "Indeferida"),
    ("pendente_intimacao", "Pendente de intimação"),
    ("vigente", "Vigente"),
    ("descumprida", "Descumprida"),
    ("revogada", "Revogada"),
    ("substituida", "Substituída"),
    ("encerrada", "Encerrada"),
]
VD_SITUACAO_MEDIDA_LABEL = dict(VD_SITUACOES_MEDIDA)

VD_SITUACOES_ITEM_MEDIDA = [
    ("vigente", "Vigente"),
    ("cumprida", "Cumprida"),
    ("descumprida", "Descumprida"),
    ("encerrada", "Encerrada"),
]
VD_SITUACAO_ITEM_LABEL = dict(VD_SITUACOES_ITEM_MEDIDA)

VD_SITUACOES_APURACAO = [
    ("registrado", "Registrado, aguardando apuração"),
    ("em_apuracao", "Em apuração"),
    ("concluido", "Apuração concluída"),
    ("arquivado", "Arquivado"),
]
VD_SITUACAO_APURACAO_LABEL = dict(VD_SITUACOES_APURACAO)

VD_SITUACOES_DILIGENCIA = [
    ("pendente", "Pendente"),
    ("distribuida", "Distribuída"),
    ("em_andamento", "Em andamento"),
    ("aguardando_resposta", "Aguardando resposta"),
    ("concluida", "Concluída"),
    ("prejudicada", "Prejudicada"),
    ("cancelada", "Cancelada"),
]
VD_SITUACAO_DILIGENCIA_LABEL = dict(VD_SITUACOES_DILIGENCIA)
VD_SITUACOES_DILIGENCIA_ABERTAS = {"pendente", "distribuida", "em_andamento", "aguardando_resposta"}

VD_PRIORIDADES_DILIGENCIA = [
    ("baixa", "Baixa"), ("media", "Média"), ("alta", "Alta"), ("urgente", "Urgente"),
]
VD_PRIORIDADE_DILIGENCIA_LABEL = dict(VD_PRIORIDADES_DILIGENCIA)

VD_SITUACOES_ENCAMINHAMENTO = [
    ("encaminhado", "Encaminhado"),
    ("confirmado", "Confirmado pelo serviço"),
    ("em_atendimento", "Em atendimento"),
    ("concluido", "Concluído"),
    ("sem_retorno", "Sem retorno"),
]
VD_SITUACAO_ENCAMINHAMENTO_LABEL = dict(VD_SITUACOES_ENCAMINHAMENTO)

VD_ORIGENS_DEMANDA = [
    "Comparecimento espontâneo", "Boletim de Ocorrência", "Encaminhamento da rede de proteção",
    "Disque 180 / 190", "Determinação judicial", "Denúncia de terceiros", "Outra",
]

VD_CANAIS_ATENDIMENTO = [
    "Presencial na unidade", "Patrulha Maria da Penha", "Telefone", "Plantão", "Outro",
]

SIM_NAO = [("sim", "Sim"), ("nao", "Não"), ("nao_sabe", "Não sabe / não informado")]
SIM_NAO_LABEL = dict(SIM_NAO)


def opcoes_sim_nao(valor):
    return opcoes(SIM_NAO, valor or "")


# ----------------------------------------------------------------------------
# Banco de dados — schema completo do módulo
# ----------------------------------------------------------------------------

# Colunas acrescentadas depois que o módulo já estava em uso. Cada entrada é
# (tabela, coluna, tipo) e só roda se a coluna faltar no banco. Ao criar uma
# coluna nova em qualquer tabela vd_*, acrescente a linha aqui — senão a
# unidade que já usa o sistema recebe a atualização e ela falha.
MIGRACOES_VD = [
    # (nenhuma pendente até aqui — o schema acima está atualizado)
]


def exclui_caso_vd_em_cascata(con, cid):
    """Apaga um caso de Violência Doméstica e tudo que depende dele.

    O banco não declara chaves estrangeiras, então a cascata é feita aqui. Um
    caso deixa rastro em quinze tabelas: sem isto, restariam o relato da mulher,
    o FONAR e o endereço seguro apontando para um caso que não existe mais.

    Devolve a lista de arquivos de anexo que precisam sair do disco.
    """
    arquivos = [a["arquivo"] for a in
                con.execute("SELECT arquivo FROM vd_anexos WHERE caso_id=?", (cid,))
                if a["arquivo"]]

    # Pessoas vinculadas: ficha específica e FONAR pendem de vd_caso_pessoas.
    for cp in con.execute("SELECT id FROM vd_caso_pessoas WHERE caso_id=?", (cid,)).fetchall():
        cpid = cp["id"]
        for ap in con.execute(
                "SELECT id FROM vd_fonar_aplicacoes WHERE caso_pessoa_id=?", (cpid,)).fetchall():
            con.execute("DELETE FROM vd_fonar_respostas WHERE aplicacao_id=?", (ap["id"],))
        con.execute("DELETE FROM vd_fonar_aplicacoes WHERE caso_pessoa_id=?", (cpid,))
        con.execute("DELETE FROM vd_dados_mulher WHERE caso_pessoa_id=?", (cpid,))
        con.execute("DELETE FROM vd_dados_autor WHERE caso_pessoa_id=?", (cpid,))
    con.execute("DELETE FROM vd_caso_pessoas WHERE caso_id=?", (cid,))

    # Medidas protetivas: itens e descumprimentos pendem da medida.
    for md in con.execute(
            "SELECT id FROM vd_medidas_protetivas WHERE caso_id=?", (cid,)).fetchall():
        con.execute("DELETE FROM vd_itens_medida_protetiva WHERE medida_id=?", (md["id"],))
        con.execute("DELETE FROM vd_descumprimentos WHERE medida_id=?", (md["id"],))
    con.execute("DELETE FROM vd_medidas_protetivas WHERE caso_id=?", (cid,))

    for tabela in ("vd_avaliacoes_profissionais", "vd_diligencias", "vd_encaminhamentos",
                   "vd_contatos_acompanhamento", "vd_caso_ocorrencias",
                   "vd_caso_tipos_violencia", "vd_caso_marcadores", "vd_anexos",
                   "vd_eventos_linha_tempo"):
        con.execute(f"DELETE FROM {tabela} WHERE caso_id=?", (cid,))

    con.execute("DELETE FROM vd_casos WHERE id=?", (cid,))
    return arquivos


def inicia_banco_vd():
    con = conexao()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS vd_casos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_reds TEXT, numero_inquerito TEXT, numero_outro_procedimento TEXT,
        numero_processo_judicial TEXT, numero_medida_protetiva TEXT,
        unidade_responsavel TEXT, municipio TEXT,
        data_hora_atendimento TEXT, data_hora_fato TEXT, local_fato TEXT,
        servidor_responsavel_id INTEGER, autoridade_responsavel TEXT,
        origem_demanda TEXT, canal_atendimento TEXT,
        situacao TEXT NOT NULL DEFAULT 'rascunho',
        nivel_sigilo TEXT NOT NULL DEFAULT 'normal',
        relato_mulher TEXT, observacoes_servidor TEXT, descricao_fato TEXT,
        fonte_relato TEXT, observacoes TEXT,
        motivo_encerramento TEXT, motivo_reabertura TEXT,
        criado_em TEXT, criado_por INTEGER,
        atualizado_em TEXT, atualizado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_caso_pessoas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        pessoa_id INTEGER NOT NULL,
        papel TEXT NOT NULL,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_dados_mulher (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_pessoa_id INTEGER NOT NULL UNIQUE,
        telefone_seguro TEXT, telefone_alt_seguro TEXT,
        autoriza_ligacao TEXT, autoriza_mensagem TEXT,
        forma_contato_segura TEXT, melhor_horario_contato TEXT,
        palavras_proibidas_mensagem TEXT,
        telefone_controlado_agressor TEXT,
        endereco_seguro TEXT,
        pessoa_confianca_nome TEXT, pessoa_confianca_contato TEXT,
        dependencia_economica TEXT, gravidez TEXT, puerperio TEXT,
        deficiencia TEXT, dificuldade_locomocao TEXT,
        necessidade_interprete TEXT, necessidade_atendimento_acessivel TEXT,
        vinculo_rede_protecao TEXT,
        existe_local_seguro TEXT, interesse_acolhimento TEXT,
        percepcao_risco TEXT,
        atualizado_em TEXT, atualizado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_dados_autor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_pessoa_id INTEGER NOT NULL UNIQUE,
        relacionamento_mulher TEXT, relacionamento_atual TEXT,
        convivencia_atual TEXT, tempo_relacionamento TEXT,
        filhos_em_comum TEXT, veiculos TEXT,
        acesso_arma_fogo TEXT, vinculo_forcas_seguranca TEXT,
        uso_alcool TEXT, uso_drogas TEXT,
        historico_ameacas TEXT, historico_agressoes TEXT, historico_perseguicao TEXT,
        medidas_protetivas_anteriores TEXT, descumprimentos_anteriores TEXT,
        outras_vitimas TEXT, outras_ocorrencias TEXT, outros_procedimentos TEXT,
        grau_verificacao TEXT, observacoes TEXT,
        atualizado_em TEXT, atualizado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_caso_ocorrencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        ocorrencia_id INTEGER NOT NULL,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_caso_tipos_violencia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        tipo TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS vd_caso_marcadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        marcador TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS vd_anexos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        tipo TEXT NOT NULL DEFAULT 'documento',
        arquivo TEXT NOT NULL,
        nome_original TEXT,
        legenda TEXT, origem_cadeia TEXT,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_eventos_linha_tempo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        tipo_evento TEXT NOT NULL,
        descricao TEXT,
        usuario_id INTEGER,
        timestamp TEXT NOT NULL,
        referencia_tabela TEXT, referencia_id INTEGER
    );

    -- Tabelas para as próximas ondas (schema já criado agora para evitar
    -- migrações depois; sem tela própria ainda).
    CREATE TABLE IF NOT EXISTS vd_fonar_aplicacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_pessoa_id INTEGER NOT NULL,
        data_hora TEXT, aplicador_id INTEGER,
        impossibilidade_responder TEXT,
        data_prevista_reavaliacao TEXT,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_fonar_respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aplicacao_id INTEGER NOT NULL,
        pergunta_codigo TEXT NOT NULL,
        resposta TEXT, observacao TEXT
    );
    CREATE TABLE IF NOT EXISTS vd_avaliacoes_profissionais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        sintese TEXT, fatores_risco TEXT, fatores_protecao TEXT, vulnerabilidades TEXT,
        percepcao_mulher TEXT, criancas_expostas TEXT, existe_arma TEXT,
        risco_separacao TEXT, providencias_imediatas TEXT, justificativa TEXT,
        responsavel_id INTEGER, data_hora TEXT,
        necessita_reavaliacao TEXT, data_prevista_reavaliacao TEXT,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_medidas_protetivas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        data_solicitacao TEXT, autoridade_solicitante TEXT,
        numero_processo TEXT, orgao_judicial TEXT,
        situacao TEXT NOT NULL DEFAULT 'em_elaboracao',
        data_decisao TEXT, resultado TEXT,
        data_ciencia_mulher TEXT, data_intimacao_autor TEXT,
        responsavel_intimacao TEXT, forma_intimacao TEXT,
        vigencia TEXT, data_revisao TEXT, data_encerramento TEXT,
        documento_arquivo TEXT, observacoes TEXT,
        criado_em TEXT, criado_por INTEGER,
        atualizado_em TEXT, atualizado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_itens_medida_protetiva (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medida_id INTEGER NOT NULL,
        tipo_medida TEXT NOT NULL,
        situacao TEXT, data_inicial TEXT, data_final TEXT,
        detalhes TEXT, observacoes TEXT
    );
    CREATE TABLE IF NOT EXISTS vd_descumprimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medida_id INTEGER NOT NULL,
        data_hora TEXT, local TEXT, forma TEXT, relato TEXT,
        provas TEXT, testemunhas TEXT,
        contato_autor TEXT, meio_utilizado TEXT,
        aproximacao_fisica TEXT, ameaca TEXT, agressao TEXT,
        providencias TEXT, ocorrencia_id INTEGER, numero_procedimento TEXT,
        houve_prisao TEXT, responsavel_id INTEGER,
        situacao_apuracao TEXT,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_diligencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        descricao TEXT NOT NULL, tipo TEXT,
        responsavel_id INTEGER, unidade_responsavel TEXT,
        prioridade TEXT, prazo TEXT,
        situacao TEXT NOT NULL DEFAULT 'pendente',
        resultado TEXT, data_conclusao TEXT, observacoes TEXT,
        criado_em TEXT, criado_por INTEGER,
        atualizado_em TEXT, atualizado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_encaminhamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        instituicao TEXT NOT NULL, servico TEXT, profissional_setor TEXT,
        motivo TEXT, data TEXT, documento_enviado TEXT,
        confirmacao_recebimento TEXT, retorno_recebido TEXT,
        situacao TEXT, observacoes TEXT, responsavel_id INTEGER,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vd_contatos_acompanhamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL,
        data_prevista TEXT, data_realizada TEXT,
        responsavel_id INTEGER, meio_contato TEXT,
        contato_seguro_confirmado TEXT, resultado TEXT,
        situacao_atual_informada TEXT, novos_fatos TEXT,
        descumprimento_relatado TEXT,
        necessita_providencia TEXT, necessita_reavaliacao TEXT,
        observacoes TEXT,
        criado_em TEXT, criado_por INTEGER
    );
    """)
    aplica_migracoes(con, MIGRACOES_VD)
    con.commit()
    con.close()


def vd_registra_evento(con, caso_id, tipo_evento, descricao, usuario_id,
                        referencia_tabela=None, referencia_id=None):
    """Registra um evento na linha do tempo do caso. A tela da linha do
    tempo em si (juntando isso com o histórico geral) vem numa onda futura;
    por ora só alimentamos a tabela para não perder nada pelo caminho."""
    con.execute(
        "INSERT INTO vd_eventos_linha_tempo (caso_id, tipo_evento, descricao, usuario_id,"
        " timestamp, referencia_tabela, referencia_id) VALUES (?,?,?,?,?,?,?)",
        (caso_id, tipo_evento, descricao, usuario_id, agora(), referencia_tabela, referencia_id))
