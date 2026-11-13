"""Módulo SIRIO — organização e relatório de investigações."""
import zipfile

from sirio_core import *  # noqa: F401,F403
from sirio_verificacoes import (ARQ_MODELO_COMUNICACAO, _linha_cabecalho,
                                _lista_numerada, _par, _run,
                                _texto_em_paragrafos, data_por_extenso)


SITUACOES_INVESTIGACAO = [
    ("em_andamento", "Em andamento"), ("aguardando_diligencia", "Aguardando diligência"),
    ("concluida", "Concluída"), ("arquivada", "Arquivada"),
]
SITUACAO_INVESTIGACAO_LABEL = dict(SITUACOES_INVESTIGACAO)
CAMPOS_INVESTIGACAO = [
    "titulo", "natureza", "numero_comunicacao", "data_comunicacao", "reds", "pcnet", "requisicao",
    "vitima", "investigados", "equipe", "dos_fatos", "diligencias_realizadas", "provas_documentais",
    "provas_testemunhais", "analise_digital", "fontes_abertas", "linha_tempo", "analise", "conclusao",
    "providencias_sugeridas", "situacao", "observacoes",
]
TIPOS_REFERENCIA = {
    "pessoa": ("Pessoa cadastrada", "pessoas"),
    "ocorrencia": ("Ocorrência", "ocorrencias"),
    "veiculo": ("Veículo", "veiculos"),
    "material": ("Material apreendido", "materiais_apreendidos"),
    "verificacao": ("Verificação de denúncia", "verificacoes"),
}


def inicia_banco_investigacoes():
    con = conexao()
    con.execute("""CREATE TABLE IF NOT EXISTS investigacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL, natureza TEXT, numero_comunicacao TEXT, data_comunicacao TEXT,
        reds TEXT, pcnet TEXT, requisicao TEXT, vitima TEXT, investigados TEXT, equipe TEXT,
        dos_fatos TEXT, diligencias_realizadas TEXT, provas_documentais TEXT,
        provas_testemunhais TEXT, analise_digital TEXT, fontes_abertas TEXT, linha_tempo TEXT,
        analise TEXT, conclusao TEXT, providencias_sugeridas TEXT,
        situacao TEXT NOT NULL DEFAULT 'em_andamento', observacoes TEXT,
        criado_em TEXT, criado_por INTEGER, atualizado_em TEXT, atualizado_por INTEGER
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS investigacao_referencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        investigacao_id INTEGER NOT NULL, tipo TEXT NOT NULL, referencia_id INTEGER NOT NULL,
        criado_em TEXT, criado_por INTEGER,
        UNIQUE (investigacao_id, tipo, referencia_id)
    )""")
    con.commit()
    con.close()


def _proximo_numero():
    ano = datetime.now().year
    con = conexao()
    numeros = con.execute("SELECT numero_comunicacao FROM investigacoes WHERE numero_comunicacao LIKE ?", (f"%/{ano}",)).fetchall()
    con.close()
    maior = 0
    for item in numeros:
        m = re.match(r"\s*(\d+)", item["numero_comunicacao"] or "")
        if m:
            maior = max(maior, int(m.group(1)))
    return f"{maior + 1:03d}/{ano}"


def _pill(situacao):
    classe = {"em_andamento": "em_verificacao", "aguardando_diligencia": "em_verificacao",
              "concluida": "ativo", "arquivada": "arquivado"}.get(situacao, "inativo")
    return f'<span class="pill p-{classe}">{e(SITUACAO_INVESTIGACAO_LABEL.get(situacao, situacao))}</span>'


def _referencias(investigacao_id):
    con = conexao()
    refs = con.execute("SELECT * FROM investigacao_referencias WHERE investigacao_id=? ORDER BY id", (investigacao_id,)).fetchall()
    resultado = []
    for ref in refs:
        if ref["tipo"] not in TIPOS_REFERENCIA:
            continue
        rotulo, tabela = TIPOS_REFERENCIA[ref["tipo"]]
        registro = con.execute(f"SELECT * FROM {tabela} WHERE id=?", (ref["referencia_id"],)).fetchone()
        if registro:
            resultado.append({"tipo": ref["tipo"], "rotulo": rotulo, "registro": dict(registro)})
    con.close()
    return resultado


def salva_referencias_investigacao(con, investigacao_id, referencias, usuario_id):
    """Substitui os vínculos pelo conjunto selecionado no formulário."""
    con.execute("DELETE FROM investigacao_referencias WHERE investigacao_id=?", (investigacao_id,))
    validas = set()
    for valor in referencias or []:
        tipo, sep, ident = (valor or "").partition(":")
        if not sep or tipo not in TIPOS_REFERENCIA or not ident.isdigit():
            continue
        chave = (tipo, int(ident))
        if chave in validas:
            continue
        _, tabela = TIPOS_REFERENCIA[tipo]
        if con.execute(f"SELECT 1 FROM {tabela} WHERE id=?", (chave[1],)).fetchone():
            validas.add(chave)
    con.executemany(
        "INSERT INTO investigacao_referencias (investigacao_id, tipo, referencia_id, criado_em, criado_por) VALUES (?,?,?,?,?)",
        [(investigacao_id, tipo, ident, agora(), usuario_id) for tipo, ident in validas])


def _rotulo_referencia(ref):
    r, tipo = ref["registro"], ref["tipo"]
    if tipo == "pessoa": return r.get("nome") or "Pessoa sem nome"
    if tipo == "ocorrencia": return " — ".join(x for x in [r.get("numero_bo"), r.get("tipo_crime")] if x) or f"Ocorrência #{r['id']}"
    if tipo == "veiculo": return " — ".join(x for x in [r.get("placa"), r.get("marca"), r.get("modelo")] if x) or f"Veículo #{r['id']}"
    if tipo == "material": return r.get("objeto") or r.get("categoria") or f"Material #{r['id']}"
    return r.get("numero_comunicacao") or r.get("protocolo") or f"Verificação #{r['id']}"


def _link_referencia(ref):
    destinos = {"pessoa": "/pessoas", "ocorrencia": "/ocorrencias", "veiculo": "/veiculos", "material": "/materiais", "verificacao": "/verificacoes"}
    destino = destinos[ref["tipo"]]
    # Veículos e materiais são listagens; os demais têm ficha própria.
    href = destino if ref["tipo"] in ("veiculo", "material") else f"{destino}/{ref['registro']['id']}"
    return f'<a class="nomelink" href="{href}">{e(_rotulo_referencia(ref))}</a>'


def _bloco_referencias(referencias, completo=False):
    if not referencias:
        return ""
    itens = ""
    for ref in referencias:
        r = ref["registro"]
        if completo:
            ignorar = {"id", "criado_em", "criado_por", "atualizado_em", "atualizado_por", "senha_hash"}
            campos = "".join(li_campo(chave.replace("_", " ").capitalize(), valor)
                               for chave, valor in r.items() if chave not in ignorar and valor not in (None, ""))
            itens += f'<div class="cartao"><h3>{e(ref["rotulo"])}: {_link_referencia(ref)}</h3>{campos}</div>'
        else:
            itens += f'<li><strong>{e(ref["rotulo"])}:</strong> {_link_referencia(ref)}</li>'
    return (f'<section class="cartao"><h2>Elementos vinculados do SIRIO</h2>'
            f'{itens if completo else "<ul>" + itens + "</ul>"}</section>')


def pagina_investigacoes_lista(usuario, csrf, filtros):
    con = conexao()
    sql, args = "SELECT * FROM investigacoes WHERE 1=1", []
    if filtros.get("situacao"):
        sql += " AND situacao=?"; args.append(filtros["situacao"])
    if filtros.get("busca"):
        sql += " AND (titulo LIKE ? OR reds LIKE ? OR pcnet LIKE ? OR vitima LIKE ? OR investigados LIKE ?)"
        args += [f"%{filtros['busca']}%"] * 5
    sql += " ORDER BY atualizado_em DESC, id DESC LIMIT 500"
    registros = con.execute(sql, args).fetchall()
    con.close()
    novo = '<a class="botao" href="/investigacoes/nova">Nova investigação</a>' if usuario["perfil"] in ("admin", "analista") else ""
    linhas = "".join(f"""<tr><td><a class="nomelink" href="/investigacoes/{r['id']}">#{r['id']} — {e(r['titulo'])}</a></td>
      <td>{e(r['natureza']) or '—'}</td><td>{e(r['reds']) or '—'}</td><td>{e(r['vitima']) or '—'}</td>
      <td>{e(r['investigados']) or '—'}</td><td>{_pill(r['situacao'])}</td></tr>""" for r in registros)
    tabela = f"<table><thead><tr><th>Investigação</th><th>Natureza</th><th>REDS</th><th>Vítima</th><th>Investigados</th><th>Situação</th></tr></thead><tbody>{linhas}</tbody></table>" if linhas else '<div class="vazio">Nenhuma investigação encontrada.</div>'
    corpo = f"""<div class="cab"><h1>Investigações</h1>{novo}</div>
    <p class="suave">Organize os elementos da apuração e gere um relatório na estrutura das suas Comunicações de Serviço.</p>
    <form method="get" action="/investigacoes" class="painel" style="grid-template-columns:2fr 1fr auto">
      <input name="busca" value="{e(filtros.get('busca',''))}" placeholder="Título, REDS, PCNET, vítima ou investigado">
      <select name="situacao"><option value="">Situação: todas</option>{opcoes(SITUACOES_INVESTIGACAO, filtros.get('situacao',''))}</select><button class="botao">Filtrar</button>
    </form>{tabela}"""
    return pagina("Investigações", corpo, usuario)


def pagina_investigacao_form(usuario, csrf, dados=None, investigacao_id=None, erro=""):
    dados, novo = dados or {}, investigacao_id is None
    def v(c, padrao=""):
        return dados.get(c) if dados.get(c) not in (None, "") else padrao
    hoje = agora()[:10]
    con = conexao()
    pessoas = con.execute("SELECT id, nome, cpf FROM pessoas ORDER BY nome LIMIT 1000").fetchall()
    ocorrencias = con.execute("SELECT id, numero_bo, tipo_crime, data_fato FROM ocorrencias ORDER BY id DESC LIMIT 1000").fetchall()
    veiculos = con.execute("SELECT id, placa, marca, modelo FROM veiculos ORDER BY id DESC LIMIT 1000").fetchall()
    materiais = con.execute("SELECT id, categoria, objeto FROM materiais_apreendidos ORDER BY id DESC LIMIT 1000").fetchall()
    verificacoes = con.execute("SELECT id, numero_comunicacao, protocolo, nome_vitima FROM verificacoes ORDER BY id DESC LIMIT 1000").fetchall()
    con.close()
    selecionadas = dados.get("referencias") or []
    if isinstance(selecionadas, str):
        selecionadas = [selecionadas]
    def opcoes_refs(tipo, registros, texto):
        return "".join(f'<option value="{tipo}:{r["id"]}">{e(texto(r))}</option>' for r in registros)
    op_pessoas = opcoes_refs("pessoa", pessoas, lambda r: f'{r["nome"]} — CPF {r["cpf"] or "não informado"}')
    op_ocorrencias = opcoes_refs("ocorrencia", ocorrencias, lambda r: " — ".join(x for x in [r["numero_bo"], r["tipo_crime"], r["data_fato"]] if x) or f'Ocorrência #{r["id"]}')
    op_veiculos = opcoes_refs("veiculo", veiculos, lambda r: " — ".join(x for x in [r["placa"], r["marca"], r["modelo"]] if x) or f'Veículo #{r["id"]}')
    op_materiais = opcoes_refs("material", materiais, lambda r: " — ".join(x for x in [r["categoria"], r["objeto"]] if x) or f'Material #{r["id"]}')
    op_verificacoes = opcoes_refs("verificacao", verificacoes, lambda r: " — ".join(x for x in [r["numero_comunicacao"], r["protocolo"], r["nome_vitima"]] if x) or f'Verificação #{r["id"]}')
    html_selecionadas = "".join(f'<span class="pill p-em_verificacao" data-ref="{e(x)}">{e(x)} <button type="button" onclick="this.parentElement.remove()">×</button><input type="hidden" name="referencias" value="{e(x)}"></span>' for x in selecionadas)
    def campo(nome, rotulo, dica="", linhas=5):
        return f'''<label class="span2">{rotulo}<textarea name="{nome}" rows="{linhas}" placeholder="{e(dica)}">{e(v(nome))}</textarea></label>'''
    corpo = f"""<div class="cab"><h1>{'Nova investigação' if novo else 'Editar investigação #' + str(investigacao_id)}</h1></div>
    <form method="post" action="{'/investigacoes/nova' if novo else f'/investigacoes/{investigacao_id}/editar'}"><input type="hidden" name="csrf" value="{e(csrf)}">
    <fieldset><legend>Identificação da investigação</legend><div class="grade">
      <label class="span2">Título / objeto da apuração<input name="titulo" value="{e(v('titulo'))}" placeholder="Ex.: Análise de dados de aparelho celular"></label>
      <label>Natureza / tipo penal<input name="natureza" value="{e(v('natureza'))}"></label><label>REDS<input name="reds" value="{e(v('reds'))}"></label>
      <label>PCNET<input name="pcnet" value="{e(v('pcnet'))}"></label><label>Requisição / análise<input name="requisicao" value="{e(v('requisicao'))}"></label>
      <label>Nº da comunicação IPT<input name="numero_comunicacao" value="{e(v('numero_comunicacao', _proximo_numero() if novo else ''))}"></label><label>Data da comunicação<input type="date" name="data_comunicacao" value="{e(v('data_comunicacao', hoje))}"></label>
      <label>Vítima(s)<input name="vitima" value="{e(v('vitima'))}"></label><label>Investigado(s) / suspeito(s)<input name="investigados" value="{e(v('investigados'))}"></label>
      <label class="span2">Equipe responsável<input name="equipe" value="{e(v('equipe', usuario['nome']))}"></label>
    </div></fieldset>
    <fieldset><legend>Informações já cadastradas no SIRIO</legend>
      <p class="suave">Vincule registros existentes; eles também serão apresentados no relatório.</p><div class="grade">
      <label class="span2">Escolher registro existente<select id="referencia_seletor"><option value="">Selecione…</option><optgroup label="Pessoas cadastradas">{op_pessoas}</optgroup><optgroup label="Ocorrências">{op_ocorrencias}</optgroup><optgroup label="Veículos">{op_veiculos}</optgroup><optgroup label="Materiais apreendidos">{op_materiais}</optgroup><optgroup label="Verificações">{op_verificacoes}</optgroup></select></label>
      <div class="acoes span2" style="justify-content:flex-start"><button type="button" class="botao fantasma" onclick="adicionarReferencia()">Incluir na investigação</button></div>
      <div id="referencias_selecionadas" class="span2" style="display:flex;gap:.5rem;flex-wrap:wrap">{html_selecionadas}</div></div>
    </fieldset>
    <fieldset><legend>Contexto e diligências</legend><div class="grade">
      {campo('dos_fatos', 'Dos fatos', 'Trata-se de apuração de…', 8)}
      {campo('diligencias_realizadas', 'Diligências realizadas', 'Registre entrevistas, requisições, buscas, perícias e resultados. Um parágrafo para cada diligência.', 9)}
      {campo('linha_tempo', 'Linha do tempo', 'DD/MM/AAAA — fato ou informação relevante.', 7)}
    </div></fieldset>
    <fieldset><legend>Elementos de prova e análise</legend><div class="grade">
      {campo('provas_documentais', 'Documentos, laudos e registros', 'BOs, laudos, prontuários, ofícios, respostas e anexos relevantes.', 5)}
      {campo('provas_testemunhais', 'Evidências testemunhais', 'Síntese das entrevistas e depoimentos, indicando a origem da informação.', 5)}
      {campo('analise_digital', 'Análise digital', 'Aparelhos, contas, conversas, IMEIs, IPs, hashes, mídias e páginas.', 6)}
      {campo('fontes_abertas', 'Fontes abertas e vínculos identificados', 'Consultas públicas, perfis, domínios, empresas, endereços e suas correlações.', 5)}
      {campo('analise', 'Análise investigativa', 'Explique as conexões entre os elementos, distinguindo fato verificado de hipótese.', 7)}
    </div></fieldset>
    <fieldset><legend>Conclusão e encaminhamento</legend><div class="grade">
      {campo('conclusao', 'Conclusão', 'Síntese objetiva do que os elementos apurados demonstram.', 5)}
      {campo('providencias_sugeridas', 'Providências sugeridas', 'Uma providência por linha: intimação, requisição, perícia, afastamento de sigilo…', 5)}
      <label>Situação<select name="situacao">{opcoes(SITUACOES_INVESTIGACAO, v('situacao','em_andamento'))}</select></label>
      <label>Observações internas<input name="observacoes" value="{e(v('observacoes'))}"></label>
    </div></fieldset>
    {f'<p class="erro">{e(erro)}</p>' if erro else ''}
    <div class="acoes"><a class="botao fantasma" href="{'/investigacoes' if novo else f'/investigacoes/{investigacao_id}'}">Cancelar</a><button class="botao">Salvar investigação</button></div>
    <script>
    function adicionarReferencia() {{
      var seletor = document.getElementById('referencia_seletor'), valor = seletor.value;
      if (!valor || document.querySelector('[data-ref="' + CSS.escape(valor) + '"]')) return;
      var item = document.createElement('span'); item.className = 'pill p-em_verificacao'; item.setAttribute('data-ref', valor);
      item.append(document.createTextNode(seletor.options[seletor.selectedIndex].text + ' '));
      var remover = document.createElement('button'); remover.type = 'button'; remover.textContent = '×'; remover.onclick = function() {{ item.remove(); }};
      var oculto = document.createElement('input'); oculto.type = 'hidden'; oculto.name = 'referencias'; oculto.value = valor;
      item.append(remover, oculto); document.getElementById('referencias_selecionadas').appendChild(item); seletor.value = '';
    }}
    </script></form>"""
    return pagina("Investigação", corpo, usuario)


def _bloco(titulo, texto):
    if not texto:
        return ""
    paragrafos = "".join(f"<p>{e(p)}</p>" for p in re.split(r"\n\s*\n|\n", texto) if p.strip())
    return f'<section class="cartao"><h2>{e(titulo)}</h2>{paragrafos}</section>'


def corpo_comunicacao_investigacao_xml(item, usuario, referencias=()):
    """Monta o corpo Word da Comunicação de Serviço de uma investigação.

    O timbre e os estilos permanecem no modelo da unidade; aqui entram somente
    os campos preenchidos pelo usuário, na sequência das comunicações usadas
    como referência.
    """
    xml = ""
    xml += _linha_cabecalho("Assunto", "Comunicação (faz)")
    xml += _linha_cabecalho("Serviço", "do Agente desta Delegacia de Polícia.")
    xml += _par([_run("Data: "), _run(data_por_extenso(item["data_comunicacao"] or agora()[:10]))], jc="both")
    if item["pcnet"]:
        xml += _linha_cabecalho("PCNET", item["pcnet"], True)
    if item["reds"]:
        xml += _linha_cabecalho("REDS", item["reds"], True)
    xml += _linha_cabecalho("Vítima", (item["vitima"] or "Não identificada").upper())
    xml += _linha_cabecalho("Investigados", (item["investigados"] or "Não identificados").upper())
    if item["requisicao"]:
        xml += _linha_cabecalho("REQ", item["requisicao"])
    if item["equipe"]:
        xml += _linha_cabecalho("Equipe responsável", item["equipe"])

    numero = item["numero_comunicacao"] or str(item["id"])
    xml += _par([_run(f"Comunicação n° IPT - {numero}.", sz=28)], estilo="Ttulo1", jc="center")
    xml += _par([_run("Senhor(a) Delegado(a),")], jc="both")
    xml += _par([_run("Cumprindo determinação de Vossa Excelência, devidamente orientada "
                      "pela chefia imediata, no sentido de empreender diligências a fim de "
                      "apurar os fatos noticiados, temos a relatar o que abaixo segue.")],
                estilo="Standard", recuo=True)

    secoes = [
        ("Dos fatos.", item["dos_fatos"]),
        ("Das diligências realizadas.", item["diligencias_realizadas"]),
        ("Dos documentos, laudos e registros.", item["provas_documentais"]),
        ("Das evidências testemunhais.", item["provas_testemunhais"]),
        ("Da análise digital.", item["analise_digital"]),
        ("Das fontes abertas e vínculos identificados.", item["fontes_abertas"]),
        ("Da linha do tempo.", item["linha_tempo"]),
        ("Da análise investigativa.", item["analise"]),
        ("Da conclusão.", item["conclusao"]),
    ]
    for titulo, texto in secoes:
        if texto:
            xml += _par([_run(titulo, sz=None)], estilo="Ttulo2", jc="left")
            xml += _texto_em_paragrafos(texto)

    if referencias:
        xml += _par([_run("Dos elementos vinculados no SIRIO.", sz=None)], estilo="Ttulo2", jc="left")
        for ref in referencias:
            xml += _par([_run(f"{ref['rotulo']}: ", negrito=True),
                         _run(_rotulo_referencia(ref))], estilo="Standard", recuo=True)

    if item["providencias_sugeridas"]:
        xml += _par([_run("Das providências sugeridas.", sz=None)], estilo="Ttulo2", jc="left")
        xml += _lista_numerada(item["providencias_sugeridas"])

    xml += _par([_run("Face ao exposto, e no aguardo de novas determinações, deixa-se esta "
                      "à apreciação de Vossa Excelência.")], estilo="ComunicaodeServio", recuo=True)
    xml += _par([_run("")], jc="center")
    xml += _par([_run("_____________________________________")], jc="center")
    xml += _par([_run(usuario["nome"])], jc="center")
    if item["equipe"] and item["equipe"] != usuario["nome"]:
        xml += _par([_run(item["equipe"])], jc="center")
    return xml


def gera_comunicacao_investigacao_docx(item, usuario):
    """Gera a Comunicação de Serviço Word usando o modelo timbrado da unidade."""
    if not os.path.exists(ARQ_MODELO_COMUNICACAO):
        raise FileNotFoundError(ARQ_MODELO_COMUNICACAO)
    referencias = _referencias(item["id"])
    corpo = corpo_comunicacao_investigacao_xml(item, usuario, referencias)
    saida = io.BytesIO()
    with zipfile.ZipFile(ARQ_MODELO_COMUNICACAO) as origem:
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as destino:
            for arquivo in origem.infolist():
                dados = origem.read(arquivo.filename)
                if arquivo.filename == "word/document.xml":
                    dados = dados.decode("utf-8").replace("<!--CORPO-->", corpo).encode("utf-8")
                destino.writestr(arquivo, dados)
    return saida.getvalue()


def nome_arquivo_comunicacao_investigacao(item):
    numero = re.sub(r"[^A-Za-z0-9._-]", "_", item["numero_comunicacao"] or str(item["id"]))
    return f"Comunicacao_de_servico_{numero}.docx"


def pagina_investigacao_detalhe(usuario, csrf, item, referencias=()):
    editar = f'<a class="botao fantasma" href="/investigacoes/{item["id"]}/editar">Editar</a>' if usuario["perfil"] in ("admin", "analista") else ""
    corpo = f"""<div class="cab"><div><h1>{e(item['titulo'])}</h1><p class="suave">{_pill(item['situacao'])} · REDS {e(item['reds']) or 'não informado'}</p></div>
      <div class="acoes">{editar}<a class="botao fantasma" href="/investigacoes/{item['id']}/comunicacao.docx">Exportar Comunicação Word</a><a class="botao" href="/investigacoes/{item['id']}/relatorio">Gerar relatório</a></div></div>
      <div class="cartoes"><div class="cartao">{li_campo('Natureza', item['natureza'])}{li_campo('PCNET', item['pcnet'])}{li_campo('Requisição', item['requisicao'])}</div>
      <div class="cartao">{li_campo('Vítima(s)', item['vitima'])}{li_campo('Investigado(s)', item['investigados'])}{li_campo('Equipe', item['equipe'])}</div></div>
      {_bloco_referencias(referencias)}{_bloco('Dos fatos', item['dos_fatos'])}{_bloco('Diligências realizadas', item['diligencias_realizadas'])}{_bloco('Análise investigativa', item['analise'])}{_bloco('Conclusão', item['conclusao'])}"""
    return pagina("Investigação", corpo, usuario)


def pagina_relatorio_investigacao(usuario, item, referencias=()):
    def paragrafos(texto):
        return "".join(f"<p>{e(paragrafo)}</p>" for paragrafo in
                       re.split(r"\n\s*\n|\n", texto or "") if paragrafo.strip())

    capitulos = [
        ("Identificação e objeto da apuração", "identificacao", None),
        ("Dos fatos", "dos-fatos", item["dos_fatos"]),
        ("Das diligências realizadas", "diligencias", item["diligencias_realizadas"]),
        ("Dos documentos, laudos e registros", "provas-documentais", item["provas_documentais"]),
        ("Das evidências testemunhais", "provas-testemunhais", item["provas_testemunhais"]),
        ("Da análise digital", "analise-digital", item["analise_digital"]),
        ("Das fontes abertas e vínculos identificados", "fontes-abertas", item["fontes_abertas"]),
        ("Linha do tempo", "linha-tempo", item["linha_tempo"]),
        ("Da análise investigativa", "analise", item["analise"]),
        ("Da conclusão", "conclusao", item["conclusao"]),
        ("Das providências sugeridas", "providencias", item["providencias_sugeridas"]),
    ]
    if referencias:
        capitulos.insert(3, ("Elementos vinculados do SIRIO", "elementos-vinculados", "__referencias__"))

    data = item["data_comunicacao"] or agora()[:10]
    numero = item["numero_comunicacao"] or str(item["id"])
    identificacao = "".join(li_campo(rotulo, item[campo]) for rotulo, campo in [
        ("Objeto da apuração", "titulo"), ("Natureza", "natureza"), ("REDS", "reds"),
        ("PCNET", "pcnet"), ("Requisição", "requisicao"), ("Vítima(s)", "vitima"),
        ("Investigado(s)", "investigados"), ("Equipe responsável", "equipe")])
    sumario, capitulos_renderizados = [], []
    for titulo, ancora, texto in capitulos:
        conteudo = _bloco_referencias(referencias, True) if texto == "__referencias__" else paragrafos(texto)
        if ancora == "identificacao":
            conteudo = identificacao
        if not conteudo:
            continue
        indice = len(capitulos_renderizados) + 1
        sumario.append(f'<li><a href="#{ancora}">{e(titulo)}</a></li>')
        abertura = ("<p>Senhor(a) Delegado(a),</p><p>Cumprindo determinação de Vossa Excelência, "
                    "devidamente orientada pela chefia imediata, no sentido de empreender diligências "
                    "a fim de apurar os fatos noticiados, temos a relatar o que abaixo segue.</p>"
                    if ancora == "identificacao" else "")
        capitulos_renderizados.append(
            f'<section class="relatorio-capitulo" id="{ancora}"><h2><span class="numero-capitulo">{indice}.</span>{e(titulo)}</h2>{abertura}{conteudo}</section>')

    capa = f"""<section class="relatorio-capa"><div class="sigla">SIRIO</div>
      <p class="suave">Sistema Interno de Registro de Investigados e Organizações</p>
      <h1>Relatório de Investigação</h1><p class="subtitulo">{e(item['titulo'])}</p>
      <div class="metadados">{li_campo('Comunicação', f'IPT-{numero}')}{li_campo('Data', data)}
      {li_campo('REDS', item['reds'])}{li_campo('PCNET', item['pcnet'])}{li_campo('Equipe responsável', item['equipe'] or usuario['nome'])}</div>
      <p class="suave" style="margin-top:2rem">USO RESTRITO — informações sensíveis de investigação.</p></section>"""
    corpo = f"""<div class="cabecalho-relatorio cabecalho-relatorio-investigacao"><div><a class="sigla" href="/">SIRIO</a><p class="suave">Relatório de investigação</p></div><div class="acoes"><a class="botao fantasma" href="/investigacoes/{item['id']}">Voltar</a><button class="botao" onclick="window.print()">Imprimir / salvar em PDF</button></div></div>
      <div class="marca-dagua">USO RESTRITO</div>{capa}<section class="relatorio-sumario"><h2>Sumário</h2><ol>{''.join(sumario)}</ol></section>{''.join(capitulos_renderizados)}
      <div class="rodape-relatorio"><span>Uso restrito — informações sensíveis de investigação.</span><span>{e(item['equipe']) or e(usuario['nome'])}</span></div>"""
    return pagina("Relatório de investigação", corpo, usuario)


def valida_investigacao(d):
    if not (d.get("titulo") or "").strip():
        return "Informe o título ou objeto da investigação."
    for campo in CAMPOS_INVESTIGACAO:
        erro = valida_tamanho(d.get(campo), campo.replace("_", " ").capitalize(), 40000)
        if erro:
            return erro
    if d.get("situacao") not in SITUACAO_INVESTIGACAO_LABEL:
        return "Situação inválida."
    return ""


def valores_investigacao(d):
    return {campo: (d.get(campo) or "").strip() for campo in CAMPOS_INVESTIGACAO}
