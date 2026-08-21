"""Módulo SIRIO — Violência Doméstica: FONAR (Onda 2).

Versão eletrônica do Formulário Nacional de Avaliação de Risco (FONAR),
instituído pela Lei nº 14.149/2021 e pela Resolução Conjunta CNJ/CNMP nº 5/2020,
aplicado no primeiro atendimento à mulher em situação de violência doméstica.

REGRA ESSENCIAL (não é negociável, está documentada aqui para nunca ser
esquecida em manutenções futuras): este módulo NUNCA calcula uma pontuação
de risco nem classifica o caso como "baixo/médio/alto/extremo risco"
automaticamente. O sistema só identifica respostas que a literatura e o
Guia Interinstitucional de Avaliação de Risco do CNJ reconhecem como fatores
de atenção, e destaca isso visualmente — a leitura e a decisão continuam
sendo sempre do profissional responsável.

Cada aplicação do formulário é preservada para sempre; uma nova aplicação
nunca sobrescreve uma anterior — os dados de risco de uma mulher, ao longo
do tempo, formam um histórico.
"""
from sirio_core import *  # noqa: F401,F403
from sirio_vd_core import *  # noqa: F401,F403

# ----------------------------------------------------------------------------
# Estrutura do formulário — Parte I (perguntas objetivas)
# ----------------------------------------------------------------------------
# Cada pergunta: (codigo, bloco, texto, tipo, opções)
#   tipo "unica"    -> escolher uma opção (rádio)
#   tipo "multipla" -> escolher quantas opções fizerem sentido (caixas)
#   tipo "texto"    -> resposta livre curta
# "opções" é uma lista de strings; quando a pergunta tem opção "Outro/Especifique",
# isso é tratado à parte via um campo de texto complementar.

FONAR_BLOCOS = [
    ("identificacao", "Identificação das partes e vínculo"),
    ("bloco1", "Bloco I — Histórico de violência"),
    ("bloco2", "Bloco II — Sobre o(a) suposto(a) agressor(a)"),
    ("bloco3", "Bloco III — Sobre a vítima"),
    ("bloco4", "Bloco IV — Outras informações importantes"),
]

FONAR_PERGUNTAS = [
    # --- Identificação e vínculo -------------------------------------------------
    ("ident_genero_vitima", "identificacao", "Identidade de gênero da vítima", "unica",
     ["Mulher cis", "Mulher trans", "Travesti", "Pessoa não-binária", "Prefiro não informar", "Outra"]),
    ("ident_orientacao_vitima", "identificacao", "Orientação sexual da vítima", "unica",
     ["Heterossexual", "Lésbica", "Bissexual", "Assexual", "Pansexual", "Prefiro não informar", "Outra"]),
    ("ident_escolaridade_vitima", "identificacao", "Escolaridade da vítima", "unica",
     ["Sem escolaridade e sem alfabetização", "Sem escolaridade e com alfabetização",
      "Ensino Fundamental incompleto", "Ensino Fundamental completo", "Ensino Médio incompleto",
      "Ensino Médio completo", "Ensino Superior incompleto", "Ensino Superior completo",
      "Pós-graduação incompleta", "Pós-graduação completa", "Prefiro não informar", "Outro"]),
    ("ident_cor_raca_vitima", "identificacao", "Cor/raça com a qual a vítima se identifica", "unica",
     ["Preta (Negra)", "Parda (Negra)", "Indígena", "Branca", "Amarela", "Prefiro não informar"]),
    ("ident_nacionalidade_vitima", "identificacao", "Nacionalidade da vítima", "unica",
     ["Brasil", "Apátrida", "Outra"]),
    ("ident_genero_agressor", "identificacao", "Identidade de gênero do(a) suposto(a) agressor(a)", "unica",
     ["Homem cis", "Mulher cis", "Homem trans", "Pessoa trans-masculina", "Mulher trans", "Travesti",
      "Pessoa não-binária", "Não sei", "Outra"]),
    ("ident_escolaridade_agressor", "identificacao", "Escolaridade do(a) suposto(a) agressor(a)", "unica",
     ["Sem escolaridade e sem alfabetização", "Sem escolaridade e com alfabetização",
      "Ensino Fundamental incompleto", "Ensino Fundamental completo", "Ensino Médio incompleto",
      "Ensino Médio completo", "Ensino Superior incompleto", "Ensino Superior completo",
      "Pós-graduação incompleta", "Pós-graduação completa", "Prefiro não informar", "Outro"]),
    ("vinculo_afetivo", "identificacao",
     "Vínculo do(a) suposto(a) agressor(a) com a vítima — relacionamento afetivo", "unica",
     ["Marido ou esposo(a)", "Companheiro(a)", "Namorado(a)", "Ex-marido ou ex-esposo(a)",
      "Ex-companheiro(a)", "Ex-namorado(a)", "Não se aplica (vínculo familiar ou doméstico)", "Outro"]),
    ("vinculo_familiar", "identificacao",
     "Vínculo do(a) suposto(a) agressor(a) com a vítima — relacionamento familiar", "unica",
     ["Pai", "Mãe", "Padrasto", "Madrasta", "Irmão(ã)", "Filho(a)", "Avô ou avó", "Tio(a)", "Primo(a)",
      "Cunhado(a)", "Sobrinho(a)", "Enteado(a)", "Genro ou nora",
      "Não se aplica (vínculo afetivo ou doméstico)", "Outro"]),
    ("vinculo_domestico", "identificacao",
     "Vínculo do(a) suposto(a) agressor(a) com a vítima — relacionamento doméstico", "unica",
     ["Pessoa que reside no mesmo lar", "Ex-residente do lar", "Cuidador(a)", "Empregado(a) doméstico(a)",
      "Não se aplica (vínculo afetivo ou familiar)", "Outro"]),

    # --- Bloco I: histórico de violência ------------------------------------------
    ("q1", "bloco1", "1. O(a) suposto(a) agressor(a) já ameaçou a vítima ou algum familiar para atingi-la?",
     "unica", ["Sim, com arma de fogo", "Sim, com faca", "Sim, de outra forma", "Não"]),
    ("q2", "bloco1",
     "2. O(a) suposto(a) agressor(a) já praticou alguma destas formas graves de agressão física?",
     "multipla", ["Queimadura", "Enforcamento", "Sufocamento", "Estrangulamento", "Tiro", "Afogamento",
                  "Facada", "Paulada", "Outro", "Nenhuma agressão física grave"]),
    ("q2_1", "bloco1", "2.1. Já praticou alguma destas agressões físicas (não graves)?", "multipla",
     ["Soco", "Chute", "Tapa", "Empurrão", "Puxão de cabelo", "Outro", "Nenhuma agressão física"]),
    ("q2_2", "bloco1",
     "2.2. A vítima necessitou de atendimento médico e/ou internação após alguma dessas agressões?",
     "unica", ["Sim", "Não", "Prefiro não informar"]),
    ("q3", "bloco1",
     "3. O(a) suposto(a) agressor(a) já obrigou a vítima a ter relações sexuais ou praticar atos sexuais "
     "contra a vontade dela?", "unica", ["Sim", "Não", "Não sei"]),
    ("q4", "bloco1", "4. O(a) suposto(a) agressor(a) já teve algum destes comportamentos?", "multipla",
     ['Disse algo como "se não for minha, não será de mais ninguém"',
      "Perturbou, perseguiu ou vigiou a vítima nos locais que frequenta",
      "Proibiu a vítima de visitar familiares ou amigos", "Proibiu a vítima de trabalhar ou estudar",
      "Fez ligações, mensagens ou e-mails de forma insistente",
      "Impediu acesso a dinheiro, conta bancária, documentos ou outros bens",
      "Outros comportamentos de ciúme excessivo ou controle",
      "Nenhum comportamento de ciúme excessivo ou controle"]),
    ("q5", "bloco1",
     "5. A vítima já registrou ocorrência policial ou solicitou medida protetiva de urgência contra "
     "o(a) suposto(a) agressor(a)?", "unica",
     ["Sim, registrou ocorrência e solicitou medida protetiva", "Sim, registrou apenas ocorrência policial",
      "Sim, solicitou apenas medida protetiva", "Não, nunca registrou nem solicitou"]),
    ("q5_1", "bloco1", "5.1. O(a) suposto(a) agressor(a) já descumpriu medida protetiva anteriormente?",
     "unica", ["Sim", "Não", "Não sei"]),
    ("q6", "bloco1",
     "6. As agressões ou ameaças se tornaram mais frequentes e/ou mais graves nos últimos 12 meses?",
     "unica", ["Sim, ficaram mais frequentes e/ou mais graves", "Não houve aumento", "Não sei"]),

    # --- Bloco II: sobre o(a) agressor(a) ------------------------------------------
    ("q7", "bloco2", "7. O(a) suposto(a) agressor(a) faz uso abusivo de álcool, drogas ou medicamentos?",
     "multipla", ["Álcool", "Drogas", "Medicamentos", "Não faz uso das substâncias listadas", "Não sei"]),
    ("q8", "bloco2", "8. Tem alguma doença mental comprovada por avaliação médica?", "unica",
     ["Sim, e faz uso de medicação", "Sim, e não faz uso de medicação", "Não", "Não sei"]),
    ("q9", "bloco2", "9. Já tentou suicídio ou falou em suicidar-se?", "unica",
     ["Sim, já tentou suicídio", "Sim, já falou em suicidar-se, mas nunca tentou",
      "Não, nunca tentou nem falou sobre suicídio", "Não sei"]),
    ("q10", "bloco2", "10. Está desempregado(a) ou tem dificuldades financeiras?", "unica",
     ["Sim", "Não", "Não sei"]),
    ("q11", "bloco2", "11. Tem fácil acesso a arma de fogo?", "unica",
     ["Sim", "Não", "Não sei", "Prefiro não informar"]),
    ("q12", "bloco2",
     "12. Já ameaçou ou agrediu filhos(as), outros familiares, outras parceiras, amigos(as), colegas, "
     "pessoas desconhecidas ou animais de estimação?", "multipla",
     ["Filhos(as)", "Outros familiares", "Animais de estimação", "Outras parceiras íntimas",
      "Outras pessoas (amigos, colegas, desconhecidos)", "Não", "Não sei"]),
    ("q12_1", "bloco2",
     "12.1. Há conhecimento de ocorrência policial e/ou medida protetiva contra ele/ela por essas outras "
     "violências?", "unica", ["Sim", "Não"]),

    # --- Bloco III: sobre a vítima ---------------------------------------------------
    ("q13", "bloco3", "13. A vítima terminou, tentou ou manifestou intenção de terminar o relacionamento "
     "recentemente?", "unica",
     ["Sim, terminou recentemente", "Sim, tentou terminar mas ainda está na relação",
      "Sim, manifestou intenção de terminar", "Não"]),
    ("q14", "bloco3", "14. A vítima tem filhos?", "unica",
     ["Sim, de outro relacionamento", "Sim, com o(a) suposto(a) agressor(a)", "Não possui filhos"]),
    ("q14_1", "bloco3", "14.1. Faixa etária dos filhos (marque quantas se aplicarem)", "multipla",
     ["0 a 11 anos", "12 a 17 anos", "A partir de 18 anos", "Não se aplica"]),
    ("q14_2", "bloco3", "14.2. Algum dos filhos é pessoa com deficiência?", "unica",
     ["Sim", "Não", "Não se aplica"]),
    ("q14_3", "bloco3", "14.3. Há conflito quanto à guarda, visitas ou pensão com o(a) suposto(a) "
     "agressor(a)?", "unica", ["Sim", "Não", "Não sei", "Não se aplica"]),
    ("q14_4", "bloco3", "14.4. Os filhos já presenciaram atos de violência do(a) suposto(a) agressor(a) "
     "contra a vítima?", "unica", ["Sim", "Não", "Não sei", "Não se aplica"]),
    ("q15", "bloco3", "15. A vítima sofreu violência durante a gravidez ou até 18 meses após o parto?",
     "unica",
     ["Sim, está grávida atualmente e sofre violência",
      "Sim, teve filho(a) nos últimos 18 meses e sofre violência atualmente",
      "Sim, sofreu nesses períodos mas não atualmente", "Não sofreu violência nesses períodos"]),
    ("q16", "bloco3", "16. Em um novo relacionamento, as ameaças ou agressões aumentaram por causa disso?",
     "unica", ["Sim", "Não", "Não se aplica"]),
    ("q17", "bloco3", "17. A vítima se sente isolada de amigos, familiares, comunidade ou trabalho?",
     "unica", ["Sim", "Não", "Não sei"]),
    ("q18", "bloco3",
     "18. A vítima possui deficiência ou doença degenerativa que acarreta vulnerabilidade física ou "
     "mental?", "multipla",
     ["Deficiência física", "Deficiência visual", "Deficiência auditiva", "Deficiência intelectual",
      "Doença degenerativa", "Outra", "Não", "Prefiro não informar"]),
    ("q19", "bloco3", "19. Cor/raça com a qual a vítima se identifica (repetido do FONAR oficial)",
     "unica", ["Preta (Negra)", "Parda (Negra)", "Indígena", "Branca", "Amarela", "Prefiro não informar"]),

    # --- Bloco IV: outras informações ------------------------------------------------
    ("q20", "bloco4",
     "20. A vítima considera morar em bairro, comunidade, área rural, território indígena ou outro local "
     "de maior risco de violência?", "unica",
     ["Sim, área rural", "Sim, território indígena", "Sim, área urbana", "Não", "Não sei"]),
    ("q21", "bloco4", "21. Situação de moradia da vítima", "unica",
     ["Própria", "Alugada", "Cedida ou \"de favor\""]),
    ("q22", "bloco4", "22. A vítima atualmente reside no mesmo imóvel que o(a) suposto(a) agressor(a)?",
     "unica", ["Sim", "Não"]),
    ("q23", "bloco4", "23. A vítima se considera financeiramente dependente do(a) suposto(a) agressor(a)?",
     "unica", ["Sim, totalmente", "Sim, parcialmente", "Não depende financeiramente",
               "Prefiro não informar"]),
    ("q24", "bloco4", "24. A vítima quer e aceita abrigamento temporário?", "unica",
     ["Sim, quer e aceita", "Não deseja"]),
]

FONAR_PERGUNTA_POR_CODIGO = {p[0]: p for p in FONAR_PERGUNTAS}

# Formas de preenchimento (campo do CNJ "Para preenchimento do(a) profissional")
FONAR_FORMAS_PREENCHIMENTO = [
    "Vítima respondeu sem ajuda profissional",
    "Vítima respondeu com auxílio profissional",
    "Vítima não teve condições de responder",
    "Vítima recusou-se a preencher",
    "Terceiro comunicante respondeu",
]

# ----------------------------------------------------------------------------
# Fatores de atenção — baseados nas respostas do FONAR oficial que a literatura
# e o Guia Interinstitucional de Avaliação de Risco do CNJ reconhecem como
# indicadores de agravamento. Isto NÃO é uma pontuação nem uma classificação de
# risco — é só um realce visual de respostas que merecem leitura profissional
# imediata. (código da pergunta, valores de resposta que acionam o destaque, texto do alerta)
FONAR_FATORES_ATENCAO = [
    ("q1", {"Sim, com arma de fogo", "Sim, com faca", "Sim, de outra forma"},
     "Já houve ameaça contra a vítima ou familiar"),
    ("q2", None, "Já houve agressão física grave (queimadura, enforcamento, estrangulamento, tiro etc.)"),
    ("q2_2", {"Sim"}, "A vítima já precisou de atendimento médico/internação por agressão"),
    ("q3", {"Sim"}, "Já houve violência sexual"),
    ("q4", {"Perturbou, perseguiu ou vigiou a vítima nos locais que frequenta"},
     "Há histórico de perseguição/vigilância"),
    ("q5_1", {"Sim"}, "Já houve descumprimento de medida protetiva"),
    ("q6", {"Sim, ficaram mais frequentes e/ou mais graves"}, "Aumento recente de frequência/gravidade"),
    ("q9", {"Sim, já tentou suicídio", "Sim, já falou em suicidar-se, mas nunca tentou"},
     "Suposto(a) agressor(a) com histórico de ideação/tentativa de suicídio"),
    ("q11", {"Sim"}, "Suposto(a) agressor(a) com fácil acesso a arma de fogo"),
    ("q12", None, "Há histórico de ameaça/agressão a filhos, familiares ou outras pessoas"),
    ("q13", {"Sim, terminou recentemente", "Sim, tentou terminar mas ainda está na relação",
             "Sim, manifestou intenção de terminar"}, "Situação recente de ruptura/tentativa de separação"),
    ("q14_4", {"Sim"}, "Filhos já presenciaram episódios de violência"),
    ("q15", {"Sim, está grávida atualmente e sofre violência",
             "Sim, teve filho(a) nos últimos 18 meses e sofre violência atualmente"},
     "Violência atual durante gravidez ou puerpério"),
    ("q17", {"Sim"}, "A vítima relata sentir-se isolada"),
    ("q22", {"Sim"}, "A vítima reside atualmente com o(a) suposto(a) agressor(a)"),
    ("q23", {"Sim, totalmente"}, "Dependência financeira total do(a) suposto(a) agressor(a)"),
]


FONAR_SEPARADOR_MULTIPLA = " | "  # opções de algumas perguntas contêm vírgula no próprio texto


def fonar_fatores_presentes(respostas):
    """Recebe {codigo: resposta_texto} e devolve a lista de textos de alerta cujos
    critérios estão presentes nas respostas — nunca uma pontuação, só presença/ausência."""
    achados = []
    for codigo, valores_gatilho, texto in FONAR_FATORES_ATENCAO:
        resposta = respostas.get(codigo, "")
        if not resposta:
            continue
        pergunta = FONAR_PERGUNTA_POR_CODIGO.get(codigo)
        # Só separa em itens quando a pergunta é de múltipla escolha (onde as opções
        # marcadas são unidas pelo separador); em perguntas de escolha única o texto
        # da própria opção pode conter vírgula (ex.: "Sim, com arma de fogo").
        if pergunta and pergunta[3] == "multipla":
            valores_pessoa = {v.strip() for v in resposta.split(FONAR_SEPARADOR_MULTIPLA)}
        else:
            valores_pessoa = {resposta.strip()}
        if valores_gatilho is None:
            neutras = {"Nenhuma agressão física grave", "Nenhuma agressão física", "Não", "Não sei",
                      "Nenhum comportamento de ciúme excessivo ou controle"}
            if valores_pessoa and not valores_pessoa.issubset(neutras):
                achados.append(texto)
        elif valores_pessoa & valores_gatilho:
            achados.append(texto)
    return achados


# ----------------------------------------------------------------------------
# Renderização do formulário
# ----------------------------------------------------------------------------

def _campo_pergunta_fonar(codigo, bloco, texto, tipo, opcoes_lista, valor_salvo="", obs_salva="", somente_leitura=False):
    valores_marcados = set(valor_salvo.split(FONAR_SEPARADOR_MULTIPLA)) if (tipo == "multipla" and valor_salvo) else {valor_salvo}
    if somente_leitura:
        if not valor_salvo:
            resposta_html = '<span class="suave">Não respondida</span>'
        elif tipo == "multipla":
            itens = "".join(f"<li>{e(v)}</li>" for v in valor_salvo.split(FONAR_SEPARADOR_MULTIPLA))
            resposta_html = f'<ul style="margin:.2rem 0 0 1.1rem;padding:0">{itens}</ul>'
        else:
            resposta_html = f"<strong>{e(valor_salvo)}</strong>"
        obs_html = f'<p class="suave" style="margin-top:.3rem">Observação: {e(obs_salva)}</p>' if obs_salva else ""
        return f'<div class="li-campo"><span class="rot">{e(texto)}</span><span class="val">{resposta_html}</span></div>{obs_html}'

    tipo_input = "radio" if tipo == "unica" else "checkbox"
    opcoes_html = ""
    for op in opcoes_lista:
        marcado = "checked" if op in valores_marcados else ""
        opcoes_html += (
            f'<label style="flex-direction:row;gap:.4rem;align-items:center;font-weight:400">'
            f'<input type="{tipo_input}" name="resp_{codigo}" value="{e(op)}" {marcado} style="width:auto">'
            f'{e(op)}</label>')
    return f"""<div style="margin-bottom:1rem;padding-bottom:.8rem;border-bottom:1px dashed var(--linha)">
      <p style="font-weight:600;margin:0 0 .4rem">{e(texto)}</p>
      <div style="display:flex;flex-direction:column;gap:.25rem">{opcoes_html}</div>
      <input name="obs_{codigo}" value="{e(obs_salva)}" placeholder="Observação/complemento (opcional)"
        style="margin-top:.4rem;max-width:420px">
    </div>"""


def pagina_fonar_novo(usuario, csrf, caso, caso_pessoa, pessoa, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    total_anteriores = con.execute(
        "SELECT COUNT(*) FROM vd_fonar_aplicacoes WHERE caso_pessoa_id=?", (caso_pessoa["id"],)).fetchone()[0]
    con.close()
    opcoes_usuarios = "".join(
        f'<option value="{u["id"]}"{" selected" if u["id"]==usuario["id"] else ""}>{e(u["nome"])}</option>'
        for u in usuarios)

    aviso_anteriores = ""
    if total_anteriores:
        aviso_anteriores = (f'<p class="aviso">Esta pessoa já tem {total_anteriores} aplicação(ões) '
                            f'anterior(es) do FONAR neste caso — nenhuma delas será substituída. '
                            f'<a href="/vd/caso-pessoas/{caso_pessoa["id"]}/fonar">Ver aplicações anteriores</a>.</p>')

    blocos_html = ""
    for cod_bloco, rotulo_bloco in FONAR_BLOCOS:
        perguntas_bloco = "".join(
            _campo_pergunta_fonar(codigo, bloco, texto, tipo, opcoes_lista)
            for codigo, bloco, texto, tipo, opcoes_lista in FONAR_PERGUNTAS if bloco == cod_bloco)
        blocos_html += f'<fieldset><legend>{e(rotulo_bloco)}</legend>{perguntas_bloco}</fieldset>'

    corpo = f"""
    <div class="cab"><h1>Novo FONAR</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <p class="aviso">Formulário Nacional de Avaliação de Risco (Lei nº 14.149/2021, Resolução Conjunta
    CNJ/CNMP nº 5/2020) — mulher atendida: <strong>{e(pessoa['nome'])}</strong>. Este formulário NÃO calcula
    uma pontuação de risco: o sistema apenas realça, na tela de visualização, respostas que costumam exigir
    atenção imediata. A leitura e a decisão são sempre do profissional responsável.</p>
    {aviso_anteriores}
    <form method="post" action="/vd/caso-pessoas/{caso_pessoa['id']}/fonar/novo">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Dados da aplicação</legend><div class="grade">
        <label>Data e hora da aplicação<input type="datetime-local" name="data_hora" required></label>
        <label>Profissional aplicador<select name="aplicador_id">{opcoes_usuarios}</select></label>
        <label class="span2">Forma de preenchimento
          <select name="impossibilidade_responder"><option value="">Selecionar…</option>
          {opcoes(FONAR_FORMAS_PREENCHIMENTO, "")}</select></label>
      </div></fieldset>
      {blocos_html}
      <fieldset><legend>Reavaliação</legend><div class="grade">
        <label>Necessita reavaliação em data futura?<input type="date" name="data_prevista_reavaliacao"></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar aplicação do FONAR</button>
      </div>
      <p class="suave" style="text-align:right;margin-top:.3rem">Perguntas deixadas em branco ficam
      registradas como "não respondida" — não é preciso preencher tudo para salvar.</p>
    </form>"""
    return pagina("Novo FONAR", corpo, usuario)


def pagina_fonar_lista(usuario, csrf, caso, caso_pessoa, pessoa, aplicacoes):
    pode_editar = usuario["perfil"] in ("admin", "analista")
    botao_novo = (f'<a class="botao" href="/vd/caso-pessoas/{caso_pessoa["id"]}/fonar/novo">'
                 f'Aplicar novo FONAR</a>' if pode_editar else "")

    linhas = ""
    for ap in aplicacoes:
        n_fatores = ap["n_fatores"]
        selo_fatores = (f'<span class="selo s-preso">{n_fatores} fator(es) de atenção</span>'
                        if n_fatores else '<span class="suave">Nenhum fator destacado</span>')
        linhas += f"""<tr>
          <td><a class="nomelink" href="/vd/fonar/{ap['id']}">{fmt_data(ap['data_hora']) if ':' in str(ap['data_hora'] or '') else e(ap['data_hora']) or '—'}</a></td>
          <td>{e(ap['aplicador_nome']) or '—'}</td>
          <td>{e(ap['impossibilidade_responder']) or '—'}</td>
          <td>{selo_fatores}</td></tr>"""
    tabela = (f"""<table><thead><tr><th>Data da aplicação</th><th>Aplicador</th>
        <th>Forma de preenchimento</th><th>Fatores de atenção</th></tr></thead>
        <tbody>{linhas}</tbody></table>""" if aplicacoes else
        '<div class="vazio">Nenhuma aplicação do FONAR registrada ainda para esta pessoa.</div>')

    corpo = f"""
    <div class="cab"><h1>FONAR — {e(pessoa['nome'])}</h1>{botao_novo}</div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <p class="suave">Todas as aplicações ficam preservadas — uma nova aplicação nunca substitui
    ou apaga uma anterior. Isso permite acompanhar a evolução do caso ao longo do tempo.</p>
    {tabela}"""
    return pagina("FONAR", corpo, usuario)


def pagina_fonar_detalhe(usuario, csrf, aplicacao, respostas, caso, caso_pessoa, pessoa, aplicador_nome):
    respostas_dict = {r["pergunta_codigo"]: r["resposta"] for r in respostas}
    obs_dict = {r["pergunta_codigo"]: r["observacao"] for r in respostas}
    fatores = fonar_fatores_presentes(respostas_dict)

    aviso_fatores = ""
    if fatores:
        itens = "".join(f"<li>{e(f)}</li>" for f in fatores)
        aviso_fatores = f"""<div class="erro" style="margin-bottom:1rem">
          <strong>⚠ ATENÇÃO:</strong> foram identificados fatores que exigem avaliação profissional
          imediata e análise de possíveis providências urgentes.
          <ul style="margin:.4rem 0 0 1.1rem">{itens}</ul>
          <p class="suave" style="margin:.4rem 0 0;color:inherit">Isto é apenas um realce de respostas —
          não é uma classificação de risco automática. A avaliação é sempre profissional.</p>
        </div>"""

    blocos_html = ""
    for cod_bloco, rotulo_bloco in FONAR_BLOCOS:
        perguntas_bloco = "".join(
            _campo_pergunta_fonar(codigo, bloco, texto, tipo, opcoes_lista,
                                  respostas_dict.get(codigo, ""), obs_dict.get(codigo, ""), somente_leitura=True)
            for codigo, bloco, texto, tipo, opcoes_lista in FONAR_PERGUNTAS if bloco == cod_bloco)
        blocos_html += f'<div class="cartao"><h2>{e(rotulo_bloco)}</h2>{perguntas_bloco}</div>'

    corpo = f"""
    <div class="cab"><h1>FONAR — {fmt_data(aplicacao['data_hora']) if ':' in str(aplicacao['data_hora'] or '') else e(aplicacao['data_hora'])}</h1></div>
    <p class="suave"><a href="/vd/caso-pessoas/{caso_pessoa['id']}/fonar">« Voltar às aplicações de {e(pessoa['nome'])}</a>
    · <a href="/vd/{caso['id']}">Ver caso #{caso['id']}</a></p>
    <div class="cartao"><h2>Dados da aplicação</h2>
      {li_campo('Mulher atendida', pessoa['nome'])}
      {li_campo('Aplicador', aplicador_nome)}
      {li_campo('Forma de preenchimento', aplicacao['impossibilidade_responder'])}
      {li_campo('Reavaliação prevista', aplicacao['data_prevista_reavaliacao'])}</div>
    {aviso_fatores}
    {blocos_html}"""
    return pagina("FONAR", corpo, usuario)


# ----------------------------------------------------------------------------
# Avaliação profissional (etapa seguinte ao FONAR, sempre atribuída a uma pessoa)
# ----------------------------------------------------------------------------

def pagina_avaliacao_nova(usuario, csrf, caso, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    con.close()
    opcoes_usuarios = "".join(
        f'<option value="{u["id"]}"{" selected" if u["id"]==usuario["id"] else ""}>{e(u["nome"])}</option>'
        for u in usuarios)

    corpo = f"""
    <div class="cab"><h1>Nova avaliação profissional</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <p class="aviso">A conclusão desta avaliação é sempre atribuída ao profissional responsável — o
    sistema não produz diagnóstico nem decide sobre medida protetiva ou arquivamento.</p>
    <form method="post" action="/vd/{caso['id']}/avaliacao/nova">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Análise</legend><div class="grade">
        <label class="span2">Síntese do caso<textarea name="sintese" rows="3"></textarea></label>
        <label class="span2">Fatores de risco identificados<textarea name="fatores_risco" rows="3"></textarea></label>
        <label class="span2">Fatores de proteção<textarea name="fatores_protecao" rows="3"></textarea></label>
        <label class="span2">Vulnerabilidades<textarea name="vulnerabilidades" rows="2"></textarea></label>
        <label class="span2">Percepção da mulher sobre o risco<textarea name="percepcao_mulher" rows="2"></textarea></label>
      </div></fieldset>
      <fieldset><legend>Pontos de atenção específicos</legend><div class="grade">
        <label>Há crianças/dependentes expostos?<select name="criancas_expostas">{opcoes_sim_nao("")}</select></label>
        <label>Há indício de arma?<select name="existe_arma">{opcoes_sim_nao("")}</select></label>
        <label class="span2">Possibilidade de novo contato com o suposto autor
          <textarea name="risco_separacao" rows="2"></textarea></label>
      </div></fieldset>
      <fieldset><legend>Conclusão do profissional</legend><div class="grade">
        <label class="span2">Providências imediatas consideradas<textarea name="providencias_imediatas" rows="3"></textarea></label>
        <label class="span2">Justificativa da avaliação<textarea name="justificativa" rows="3"></textarea></label>
        <label>Responsável pela avaliação<select name="responsavel_id">{opcoes_usuarios}</select></label>
        <label>Data e hora<input type="datetime-local" name="data_hora" required></label>
        <label>Necessita reavaliação?<select name="necessita_reavaliacao">{opcoes_sim_nao("")}</select></label>
        <label>Data prevista de reavaliação<input type="date" name="data_prevista_reavaliacao"></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar avaliação</button>
      </div>
    </form>"""
    return pagina("Nova avaliação profissional", corpo, usuario)


def cartao_avaliacoes_profissionais(avaliacoes, nomes_usuarios):
    if not avaliacoes:
        return """<div class="cartao"><h2>Avaliações profissionais</h2>
          <p class="suave">Nenhuma avaliação profissional registrada ainda.</p></div>"""
    itens = ""
    for av in avaliacoes:
        responsavel = nomes_usuarios.get(av["responsavel_id"], "—")
        reavaliacao = (f' · Reavaliação prevista: {e(av["data_prevista_reavaliacao"])}'
                       if av["necessita_reavaliacao"] == "sim" and av["data_prevista_reavaliacao"] else "")
        itens += f"""<details style="margin-bottom:.6rem">
          <summary style="cursor:pointer;font-weight:600">
            {fmt_data(av['data_hora']) if ':' in str(av['data_hora'] or '') else e(av['data_hora'])}
            — {e(responsavel)}{reavaliacao}</summary>
          <div style="margin-top:.5rem">
            {li_campo('Síntese do caso', av['sintese'])}
            {li_campo('Fatores de risco identificados', av['fatores_risco'])}
            {li_campo('Fatores de proteção', av['fatores_protecao'])}
            {li_campo('Vulnerabilidades', av['vulnerabilidades'])}
            {li_campo('Percepção da mulher', av['percepcao_mulher'])}
            {li_campo('Crianças/dependentes expostos', 'Sim' if av['criancas_expostas']=='sim' else ('Não' if av['criancas_expostas']=='nao' else av['criancas_expostas']))}
            {li_campo('Indício de arma', 'Sim' if av['existe_arma']=='sim' else ('Não' if av['existe_arma']=='nao' else av['existe_arma']))}
            {li_campo('Possibilidade de novo contato', av['risco_separacao'])}
            {li_campo('Providências imediatas', av['providencias_imediatas'])}
            {li_campo('Justificativa', av['justificativa'])}
          </div>
        </details>"""
    return f'<div class="cartao"><h2>Avaliações profissionais ({len(avaliacoes)})</h2>{itens}</div>'
