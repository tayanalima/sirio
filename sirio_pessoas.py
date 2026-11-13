"""Módulo SIRIO — Registros (cadastro de pessoas), fotos e mesclagem.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403


# Colunas que não fazem sentido na busca livre (identificadores internos e
# carimbos de data/hora). Todo o resto do cadastro é vasculhado, inclusive
# nome da mãe, do pai, dos filhos, da companheira e as observações.
COLUNAS_FORA_DA_BUSCA = {"id", "criado_por", "atualizado_por",
                         "criado_em", "atualizado_em"}


def colunas_buscaveis(con, tabela="pessoas"):
    """Lê as colunas da tabela no próprio banco. Assim, coluna nova criada por
    migração já entra na busca sozinha, sem ninguém precisar lembrar disso."""
    return [linha[1] for linha in con.execute(f"PRAGMA table_info({tabela})")
            if linha[1] not in COLUNAS_FORA_DA_BUSCA]


def _blob(colunas, prefixo=""):
    """Monta a expressão SQL que junta várias colunas num texto só."""
    partes = [f"IFNULL({prefixo}{c},'')" for c in colunas]
    return " || ' ' || ".join(partes)


def condicao_busca_livre(con, termos):
    """Devolve (pedaço de SQL, argumentos) para a busca livre.

    Cada palavra digitada precisa aparecer em algum lugar — no cadastro da
    pessoa, numa ocorrência ligada a ela ou num material apreendido. Buscar
    "maria josefa" acha quem tem Maria no nome e Josefa como nome da mãe.
    A comparação ignora acentos e maiúsculas."""
    colunas = colunas_buscaveis(con)
    blob_pessoa = _blob(colunas)
    sql, args = "", []
    for termo in termos:
        alvo = f"%{sem_acento(termo)}%"
        sql += (
            " AND ("
            f" sirio_norm({blob_pessoa}) LIKE ?"
            "  OR EXISTS (SELECT 1 FROM ocorrencias o WHERE o.pessoa_autor_id = pessoas.id"
            "    AND sirio_norm(IFNULL(o.tipo_crime,'') || ' ' || IFNULL(o.numero_bo,'')"
            "      || ' ' || IFNULL(o.endereco_fato,'')) LIKE ?)"
            "  OR EXISTS (SELECT 1 FROM materiais_apreendidos m WHERE m.pessoa_id = pessoas.id"
            "    AND sirio_norm(IFNULL(m.objeto,'') || ' ' || IFNULL(m.categoria,'')"
            "      || ' ' || IFNULL(m.marca,'') || ' ' || IFNULL(m.numero_lacre,'')) LIKE ?)"
            " )")
        args += [alvo] * 3
    return sql, args


def pagina_lista(usuario, params, csrf=""):
    q = (params.get("q") or "").strip()
    f_grau = params.get("grau") or ""
    f_fonte = params.get("fonte") or ""
    f_status = params.get("status") or ""
    f_preso = params.get("preso") or ""
    excluidos = params.get("excluidos") or ""

    con = conexao()

    sql = ("SELECT * FROM pessoas WHERE 1=1")
    args = []
    if q:
        # Aspas permitem procurar uma expressão inteira: "maria das gracas".
        termos = [t for t in re.findall(r'"([^"]+)"|(\S+)', q)]
        termos = [(a or b).strip() for a, b in termos]
        termos = [t for t in termos if t]
        pedaco, argumentos = condicao_busca_livre(con, termos)
        sql += pedaco
        args += argumentos
    if f_grau:
        sql += " AND grau_confiabilidade = ?"; args.append(f_grau)
    if f_fonte:
        sql += " AND fonte_informacao = ?"; args.append(f_fonte)
    if f_status:
        sql += " AND status = ?"; args.append(f_status)
    if f_preso:
        sql += " AND preso = ?"; args.append(f_preso)
    sql += " ORDER BY nome LIMIT 500"

    registros = con.execute(sql, args).fetchall()

    tipos_crime_por_pessoa = {}
    qtd_ocorrencias_por_pessoa = {}
    qtd_materiais_por_pessoa = {}
    if registros:
        ids = [p["id"] for p in registros]
        marcas = ",".join("?" for _ in ids)
        for r in con.execute(
                f"SELECT pessoa_autor_id, tipo_crime FROM ocorrencias"
                f" WHERE pessoa_autor_id IN ({marcas})", ids):
            qtd_ocorrencias_por_pessoa[r["pessoa_autor_id"]] = qtd_ocorrencias_por_pessoa.get(r["pessoa_autor_id"], 0) + 1
            if r["tipo_crime"]:
                tipos_crime_por_pessoa.setdefault(r["pessoa_autor_id"], [])
                if r["tipo_crime"] not in tipos_crime_por_pessoa[r["pessoa_autor_id"]]:
                    tipos_crime_por_pessoa[r["pessoa_autor_id"]].append(r["tipo_crime"])
        for r in con.execute(
                f"SELECT pessoa_id, COUNT(*) c FROM materiais_apreendidos"
                f" WHERE pessoa_id IN ({marcas}) GROUP BY pessoa_id", ids):
            qtd_materiais_por_pessoa[r["pessoa_id"]] = r["c"]
    con.close()

    botao_exportar = ""
    if usuario["perfil"] == "admin":
        botao_exportar = ('<a class="botao fantasma" href="/pessoas/mesclar">Mesclar registros</a> '
                          '<a class="botao fantasma" href="/importar-csv">Importar CSV</a> '
                          '<a class="botao fantasma" href="/exportar.csv">Exportar CSV</a>')

    selecao_em_massa = usuario["perfil"] == "admin"
    linhas = ""
    for p in registros:
        selo_p = ('<span class="selo s-preso">Preso(a)</span>' if p['preso'] == 'sim'
                  else '<span class="selo s-solto">Em liberdade</span>')
        tipos = tipos_crime_por_pessoa.get(p["id"], [])
        tipos_txt = ", ".join(tipos) or "—"
        tipos_title = f' title="{e(", ".join(tipos))}"' if len(tipos) > 1 else ""
        if len(tipos_txt) > 28:
            tipos_txt = tipos_txt[:27] + "…"
        qtd_oc = qtd_ocorrencias_por_pessoa.get(p["id"], 0)
        qtd_mat = qtd_materiais_por_pessoa.get(p["id"], 0)
        link_oc = (f'<a class="nomelink" href="/ocorrencias?pessoa_autor_id={p["id"]}">{qtd_oc}</a>'
                  if qtd_oc else "0")
        link_mat = (f'<a class="nomelink" href="/materiais?pessoa_id={p["id"]}">{qtd_mat}</a>'
                   if qtd_mat else "0")
        marcar = (f'<td><input type="checkbox" name="pessoa_ids" value="{p["id"]}" '
                  f'aria-label="Selecionar {e(p["nome"])}"></td>' if selecao_em_massa else "")
        linhas += f"""<tr>
          {marcar}
          <td><a class="nomelink" href="/pessoas/{p['id']}">{e(p['nome'])}</a></td>
          <td>{e(p['alcunha']) or '—'}</td>
          <td class="nowrap-col">{e(p['cpf']) or '—'}</td>
          <td>{e(p['organizacao']) or '—'}</td>
          <td>{e(p['cargo_orcrim']) or '—'}</td>
          <td{tipos_title}>{e(tipos_txt)}</td>
          <td class="num-col">{link_oc}</td>
          <td class="num-col">{link_mat}</td>
          <td>{selo_grau(p['grau_confiabilidade'])}</td>
          <td>{selo_p}</td>
          <td>{pill_status(p['status'])}</td></tr>"""

    barra = f"""<div class="barra-tabela">
      <span class="suave">{len(registros)} registro(s){' — mostrando os 500 primeiros' if len(registros) == 500 else ''}.
        Arraste o título de uma coluna para mudá-la de lugar.</span>
      <button type="button" class="botao fantasma mini"
        data-restaura-colunas="tab_registros">Restaurar ordem das colunas</button></div>"""

    coluna_selecao = '<col style="width:2.6rem">' if selecao_em_massa else ''
    cabecalho_selecao = ('<th><input type="checkbox" id="selecionar-todos" aria-label="Selecionar todos os registros exibidos"></th>'
                         if selecao_em_massa else '')
    acoes_massa = ("""<div class="acoes" style="margin:.75rem 0 0">
          <button class="botao perigo" id="excluir-selecionados" disabled>Excluir selecionados</button>
          <span class="suave" id="contagem-selecao">Nenhum registro selecionado.</span>
        </div>
        <script>
        (() => {
          const caixas = [...document.querySelectorAll('input[name="pessoa_ids"]')];
          const todos = document.getElementById('selecionar-todos');
          const botao = document.getElementById('excluir-selecionados');
          const texto = document.getElementById('contagem-selecao');
          const atualizar = () => {
            const quantidade = caixas.filter(c => c.checked).length;
            botao.disabled = quantidade === 0;
            texto.textContent = quantidade ? `${quantidade} registro(s) selecionado(s).` : 'Nenhum registro selecionado.';
            if (todos) todos.checked = quantidade > 0 && quantidade === caixas.length;
          };
          if (todos) todos.addEventListener('change', () => { caixas.forEach(c => c.checked = todos.checked); atualizar(); });
          caixas.forEach(c => c.addEventListener('change', atualizar));
          document.getElementById('form-exclusao-em-massa').addEventListener('submit', event => {
            const quantidade = caixas.filter(c => c.checked).length;
            if (!quantidade || !confirm(`Excluir DEFINITIVAMENTE ${quantidade} registro(s) selecionado(s)? Fotos e vínculos próprios também serão removidos; ocorrências e materiais serão preservados, sem vínculo com a pessoa.`)) event.preventDefault();
          });
        })();
        </script>""" if selecao_em_massa else "")

    tabela = (f"""{barra}
        <form method="post" action="/pessoas/excluir-em-massa" id="form-exclusao-em-massa">
        <input type="hidden" name="csrf" value="{e(csrf)}">
        <div class="tabela-rolavel tabela-alta"><table class="tab-registros colunas-moveis" id="tab_registros">
        <colgroup>{coluna_selecao}<col class="c-nome"><col class="c-alcunha"><col class="c-cpf"><col class="c-org">
        <col class="c-cargo"><col class="c-crime"><col class="c-oc"><col class="c-mat">
        <col class="c-conf"><col class="c-preso"><col class="c-status"></colgroup>
        <thead><tr>{cabecalho_selecao}<th>Nome</th><th>Alcunha</th><th>CPF</th>
        <th>Organização</th><th>Cargo</th><th>Tipo de crime</th><th>Ocorrências</th><th>Materiais</th>
        <th>Confiabilidade</th><th>Prisional</th><th>Status</th></tr></thead>
        <tbody>{linhas}</tbody></table></div>
        {acoes_massa}</form>
        {SCRIPT_COLUNAS_MOVEIS}
        <script>ativarColunasMoveis('tab_registros');</script>""" if registros else
        '<div class="vazio">Nenhum registro encontrado. Ajuste a busca ou cadastre um novo registro.</div>')

    aviso_exclusao = (f'<p class="aviso">{e(excluidos)} registro(s) excluído(s) definitivamente.</p>'
                     if excluidos.isdigit() and int(excluidos) else "")
    corpo = f"""
    <div class="cab"><h1>Registros</h1>{botao_exportar}</div>
    {aviso_exclusao}
    <form method="get" action="/" class="painel" style="grid-template-columns:repeat(4,1fr) auto">
      <input class="larga" name="q" value="{e(q)}"
        placeholder="Buscar em todo o cadastro — nome, alcunha, CPF, RG, nome da mãe e do pai, filhos, companheira, organização, cargo, endereço, crime da prisão, observações, BO e materiais…">
      <select name="grau"><option value="">Confiabilidade: todas</option>{opcoes(lista_ativa('grau_confiabilidade'), f_grau)}</select>
      <select name="fonte"><option value="">Fonte: todas</option>{opcoes(lista_ativa('fonte_informacao'), f_fonte)}</select>
      <select name="status"><option value="">Status: todos</option>{opcoes(STATUS, f_status)}</select>
      <select name="preso"><option value="">Situação prisional: todas</option>{opcoes([("sim", "Presos"), ("nao", "Em liberdade")], f_preso)}</select>
      <button class="botao">Buscar</button>
      <p class="suave larga" style="margin:0">A busca varre o cadastro inteiro e ignora acentos e
      maiúsculas. Digitando mais de uma palavra, o registro precisa ter todas elas — em qualquer
      campo: <em>maria josefa</em> encontra quem se chama Maria e é filha de Josefa. Para procurar
      uma expressão exata, use aspas: <em>"rua das flores"</em>.</p>
    </form>
    {tabela}"""
    return pagina("Registros", corpo, usuario)


def campo_form(nome, valor, csrf=None):
    rotulo = ROTULO[nome]
    v = e(valor)
    if nome == "fonte_informacao":
        return f'<label>{rotulo}<select name="{nome}"><option value="">Selecionar…</option>{opcoes(lista_ativa_com_atual("fonte_informacao", valor), valor)}</select></label>'
    if nome == "grau_confiabilidade":
        return f'<label>{rotulo}<select name="{nome}"><option value="">Selecionar…</option>{opcoes(lista_ativa_com_atual("grau_confiabilidade", valor), valor)}</select></label>'
    if nome == "status":
        return f'<label>{rotulo}<select name="{nome}">{opcoes(STATUS, valor or "em_verificacao")}</select></label>'
    if nome == "preso":
        return (f'<label>{rotulo}<select name="{nome}">'
                f'{opcoes([("nao", "Não"), ("sim", "Sim")], valor or "nao")}</select></label>')
    if nome == "data_ultima_prisao":
        return f'<label>{rotulo}<input type="date" name="{nome}" value="{v}"></label>'
    if nome == "crime_prisao":
        return (f'<label>{rotulo}<select name="{nome}"><option value="">Selecionar…</option>'
                f'{opcoes(lista_ativa_com_atual("tipo_crime", valor), valor)}</select></label>')
    if nome in ("observacoes", "resumo_investigativo", "endereco"):
        linhas = 8 if nome == "resumo_investigativo" else (4 if nome == "observacoes" else 2)
        return f'<label class="span2">{rotulo}<textarea name="{nome}" rows="{linhas}">{v}</textarea></label>'
    if nome == "data_nascimento":
        return f'<label>{rotulo}<input type="date" name="{nome}" value="{v}"></label>'
    if nome == "qtd_filhos":
        return f'<label>{rotulo}<input type="number" min="0" name="{nome}" value="{v}"></label>'
    extra = " required" if nome == "nome" else ""
    classe = ' class="span2"' if nome in ("nome", "nome_mae", "nome_pai", "nomes_filhos",
                                          "nome_companheira", "organizacao") else ""
    return f'<label{classe}>{rotulo}{" *" if nome == "nome" else ""}<input name="{nome}" value="{v}"{extra}></label>'


def pagina_form(usuario, csrf, dados=None, pessoa_id=None, erro="", fotos=None):
    dados = dados or {}
    titulo = "Editar registro" if pessoa_id else "Novo cadastro"
    acao = f"/pessoas/{pessoa_id}/editar" if pessoa_id else "/pessoas/nova"
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome):
        return dados.get(nome) or ""

    bloco_fotos = ""
    if pessoa_id:
        bloco_fotos = galeria_fotos(usuario, csrf, pessoa_id, fotos or [], origem="editar")

    corpo = f"""
    <div class="cab"><h1>{titulo}</h1></div>
    <form method="post" action="{acao}">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>1 · Identificação pessoal</legend><div class="grade">
        {campo_form('nome', v('nome'))}{campo_form('alcunha', v('alcunha'))}
        {campo_form('rg', v('rg'))}{campo_form('cpf', v('cpf'))}
        {campo_form('data_nascimento', v('data_nascimento'))}
      </div></fieldset>
      <fieldset><legend>2 · Filiação e família</legend><div class="grade">
        {campo_form('nome_mae', v('nome_mae'))}{campo_form('nome_pai', v('nome_pai'))}
        {campo_form('qtd_filhos', v('qtd_filhos'))}{campo_form('nomes_filhos', v('nomes_filhos'))}
        {campo_form('nome_companheira', v('nome_companheira'))}
      </div></fieldset>
      <fieldset><legend>3 · Vínculo criminal / investigativo</legend><div class="grade">
        {campo_form('organizacao', v('organizacao'))}
        {campo_form('cargo_orcrim', v('cargo_orcrim'))}
      </div></fieldset>
      <fieldset><legend>4 · Situação prisional</legend><div class="grade">
        {campo_form('preso', v('preso'))}
        {campo_form('data_ultima_prisao', v('data_ultima_prisao'))}
        {campo_form('crime_prisao', v('crime_prisao'))}
      </div>
      <p class="suave">A data de atualização do status prisional é registrada automaticamente
      pelo sistema sempre que o campo "Está preso(a)" for alterado{
        f' — última atualização: {fmt_data(dados.get("data_atualizacao_status_prisional"))}.'
        if dados.get('data_atualizacao_status_prisional') else '.'
      }</p></fieldset>
      <fieldset><legend>5 · Fonte e confiabilidade da informação</legend><div class="grade">
        {campo_form('fonte_informacao', v('fonte_informacao'))}
        {campo_form('grau_confiabilidade', v('grau_confiabilidade'))}
      </div></fieldset>
      <fieldset><legend>6 · Endereço e observações</legend><div class="grade">
        {campo_form('endereco', v('endereco'))}{campo_form('observacoes', v('observacoes'))}
        {campo_form('resumo_investigativo', v('resumo_investigativo'))}
      </div></fieldset>
      <fieldset><legend>7 · Controle administrativo</legend><div class="grade">
        {campo_form('status', v('status'))}
      </div>
      <p class="suave">Responsável e datas de cadastro/atualização são preenchidas automaticamente
      a partir do usuário autenticado e ficam na trilha de auditoria.</p></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/">Cancelar</a>
        <button class="botao">Salvar registro</button>
      </div>
    </form>
    {bloco_fotos}"""
    return pagina(titulo, corpo, usuario)


def galeria_fotos_leitura(fotos):
    """Galeria apenas para visualização (tela de detalhe): sem enviar nem excluir."""
    if not fotos:
        return ('<div class="cartao"><h2>Fotografias e tatuagens</h2>'
                '<p class="suave">Nenhuma imagem cadastrada. '
                'Use o botão Editar para adicionar.</p></div>')
    itens = ""
    for f in fotos:
        rotulo = "Tatuagem" if f["tipo"] == "tatuagem" else "Fotografia"
        itens += (
            f'<figure class="foto">'
            f'<a href="/fotos/{e(f["arquivo"])}" target="_blank" rel="noopener">'
            f'<img src="/fotos/{e(f["arquivo"])}" alt="{rotulo}" loading="lazy"></a>'
            f'<figcaption><span class="pill p-{f["tipo"]}">{rotulo}</span> '
            f'{e(f["legenda"]) or ""}</figcaption></figure>')
    return (f'<div class="cartao"><h2>Fotografias e tatuagens</h2>'
            f'<div class="galeria">{itens}</div></div>')


def galeria_fotos(usuario, csrf, pessoa_id, fotos, origem="detalhe"):
    pode_editar = usuario["perfil"] in ("admin", "analista")
    itens = ""
    for f in fotos:
        rotulo = "Tatuagem" if f["tipo"] == "tatuagem" else "Fotografia"
        excluir = ""
        if pode_editar:
            excluir = (f'<form method="post" action="/fotos/{f["id"]}/excluir" '
                       f'onsubmit="return confirm(\'Excluir esta imagem?\')">'
                       f'<input type="hidden" name="csrf" value="{e(csrf)}">'
                       f'<button class="botao perigo mini">Excluir</button></form>')
        itens += (
            f'<figure class="foto">'
            f'<a href="/fotos/{e(f["arquivo"])}" target="_blank" rel="noopener">'
            f'<img src="/fotos/{e(f["arquivo"])}" alt="{rotulo}" loading="lazy"></a>'
            f'<figcaption><span class="pill p-{f["tipo"]}">{rotulo}</span> '
            f'{e(f["legenda"]) or ""}</figcaption>{excluir}</figure>')
    galeria = (f'<div class="galeria">{itens}</div>' if fotos
               else '<p class="suave">Nenhuma imagem cadastrada.</p>')
    envio = ""
    if pode_editar:
        envio = (
            f'<form method="post" action="/pessoas/{pessoa_id}/fotos" '
            f'enctype="multipart/form-data" class="grade" style="margin-top:1rem">'
            f'<input type="hidden" name="csrf" value="{e(csrf)}">'
            f'<label>Tipo<select name="tipo">'
            f'<option value="fotografia">Fotografia</option>'
            f'<option value="tatuagem">Tatuagem</option></select></label>'
            f'<label>Legenda (opcional)<input name="legenda" '
            f'placeholder="Ex.: tatuagem antebraço direito, carpa"></label>'
            f'<label class="span2">Arquivos de imagem (JPG, PNG, WEBP ou GIF — até 10 MB cada)'
            f'<input type="file" name="imagem" accept=".jpg,.jpeg,.png,.webp,.gif,image/*" '
            f'multiple required></label>'
            f'<div class="acoes span2"><button class="botao">Enviar imagens</button></div></form>')
    return f'<div class="cartao"><h2>Fotografias e tatuagens</h2>{galeria}{envio}</div>'


def pagina_detalhe(usuario, csrf, p, trilha, nomes_usuarios, fotos, materiais=None, boletins=None, biqueiras=None):
    pode_editar = usuario["perfil"] in ("admin", "analista")
    alcunha = f'<span class="selo s-alcunha">“{e(p["alcunha"])}”</span>' if p["alcunha"] else ""
    selo_preso = ('<span class="selo s-preso">PRESO(A)</span>' if p["preso"] == "sim"
                 else '<span class="selo s-solto">Em liberdade</span>')

    acoes = ""
    if pode_editar:
        sel = opcoes(STATUS, p["status"])
        excluir = ""
        if usuario["perfil"] == "admin":
            excluir = f"""<form method="post" action="/pessoas/{p['id']}/excluir" style="display:inline"
              onsubmit="return confirm('Excluir DEFINITIVAMENTE este registro? Prefira Arquivar para preservar o histórico.')">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao perigo">Excluir</button></form>"""
        acoes = f"""
        <div class="acoes" style="margin:0">
          <a class="botao fantasma" href="/pessoas/{p['id']}/editar">Editar</a>
          <form method="post" action="/pessoas/{p['id']}/status" style="display:flex;gap:.4rem">
            <input type="hidden" name="csrf" value="{e(csrf)}">
            <select name="status">{sel}</select>
            <button class="botao mini fantasma">Alterar status</button>
          </form>
          {excluir}
        </div>"""

    filhos = p["nomes_filhos"] or ""
    if p["qtd_filhos"]:
        filhos = f"{p['qtd_filhos']} — {p['nomes_filhos'] or 'nomes não informados'}"

    # Foto de destaque: a primeira "fotografia"; se não houver, a primeira imagem qualquer.
    destaque = None
    for f in fotos:
        if f["tipo"] == "fotografia":
            destaque = f
            break
    if destaque is None and fotos:
        destaque = fotos[0]
    cartao_foto = ""
    if destaque:
        leg = e(destaque["legenda"]) or ("Tatuagem" if destaque["tipo"] == "tatuagem" else "Fotografia")
        cartao_foto = (
            f'<div class="cartao cartao-retrato"><h2>Imagem</h2>'
            f'<a href="/fotos/{e(destaque["arquivo"])}" target="_blank" rel="noopener">'
            f'<img class="retrato" src="/fotos/{e(destaque["arquivo"])}" alt="{leg}"></a>'
            f'<p class="suave" style="margin:.5rem 0 0">{leg}</p></div>')

    # A trilha de auditoria é restrita ao Administrador: ela expõe quem consultou
    # e alterou cada registro, o que não deve ficar visível a analistas/consulta.
    ve_auditoria = usuario["perfil"] == "admin"

    linhas_trilha = ""
    for a in (trilha if ve_auditoria else []):
        linhas_trilha += f"""<tr>
          <td>{fmt_data(a['timestamp'])}</td>
          <td>{e(nomes_usuarios.get(a['usuario_id'], '—'))}</td>
          <td><span class="pill p-{e(a['acao'])}">{e(a['acao'])}</span></td>
          <td>{e(ROTULO.get(a['campo'], a['campo'])) or '—'}</td>
          <td class="mono">{e(a['valor_anterior']) or '—'}</td>
          <td class="mono">{e(a['valor_novo']) or '—'}</td></tr>"""
    tabela_trilha = (f"""<table><thead><tr><th>Data/hora</th><th>Usuário</th><th>Ação</th>
        <th>Campo</th><th>Anterior</th><th>Novo</th></tr></thead><tbody>{linhas_trilha}</tbody></table>"""
        if trilha else '<p class="suave">Sem eventos registrados.</p>')
    cartao_trilha = (f'<div class="cartao"><h2>Trilha de auditoria</h2>{tabela_trilha}</div>'
                     if ve_auditoria else "")

    materiais = materiais or []
    linhas_mat = ""
    for m in materiais:
        link_oc = (f'<a class="nomelink" href="/ocorrencias/{m["ocorrencia_id"]}">{e(m["oc_tipo"]) or "Ver ocorrência"}</a>'
                   if m["ocorrencia_id"] else "—")
        linhas_mat += f"""<tr><td>{e(m['categoria']) or '—'}</td><td>{e(m['objeto']) or '—'}</td>
          <td>{e(m['situacao']) or '—'}</td><td>{link_oc}</td></tr>"""
    cartao_materiais = ""
    if materiais:
        cartao_materiais = f"""<div class="cartao"><h2>Materiais apreendidos desta pessoa</h2>
          <table><thead><tr><th>Categoria</th><th>Objeto</th><th>Situação</th><th>Ocorrência</th></tr></thead>
          <tbody>{linhas_mat}</tbody></table>
          <p class="suave" style="margin-top:.5rem">
            <a href="/materiais?pessoa_id={p['id']}">Ver na aba Materiais (com filtros)</a></p></div>"""

    boletins = boletins or []
    cartao_boletins = ""
    if boletins:
        itens_bo = ""
        for b in boletins:
            titulo_bo = f"BO/REDS {e(b['reds'])}" if b["reds"] else "Boletim de Ocorrência"
            data_txt = f" · {e(b['data_fato'])}" if b["data_fato"] else ""
            tipo_txt = f" · {e(b['tipo_envolvimento'])}" if b["tipo_envolvimento"] else ""
            link_oc = (f'<p class="suave" style="margin-top:.5rem"><a href="/ocorrencias/{b["ocorrencia_id"]}">'
                      f'Ver ocorrência vinculada</a></p>' if b["ocorrencia_id"] else "")
            corpo_hist = (f'<p style="white-space:pre-wrap;margin-top:.5rem">{e(b["historico"])}</p>'
                         if b["historico"] else '<p class="suave" style="margin-top:.5rem">Sem texto de histórico registrado.</p>')
            itens_bo += f"""
            <details style="margin-bottom:.6rem">
              <summary style="cursor:pointer;font-weight:600">{titulo_bo}{data_txt}{tipo_txt}</summary>
              {corpo_hist}{link_oc}
            </details>"""
        cartao_boletins = f"""<div class="cartao"><h2>Boletins de Ocorrência ({len(boletins)})</h2>
          <p class="suave">Clique em cada boletim para ver o histórico completo.</p>
          {itens_bo}</div>"""

    biqueiras = biqueiras or []
    linhas_biq = ""
    for b in biqueiras:
        excluir_b = ""
        if pode_editar:
            excluir_b = f"""<form method="post" action="/biqueiras/{b['id']}/excluir" style="display:inline"
              onsubmit="return confirm('Excluir este ponto de biqueira?')">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao perigo mini">Excluir</button></form>"""
        linhas_biq += f"""<tr><td>{e(b['local']) or '—'}</td><td>{e(b['endereco']) or '—'}</td>
          <td>{e(b['bairro']) or '—'}</td><td>{e(b['cidade']) or '—'}</td><td>{excluir_b}</td></tr>"""
    tabela_biq = (f"""<table><thead><tr><th>Local</th><th>Endereço</th><th>Bairro</th>
        <th>Cidade</th><th></th></tr></thead><tbody>{linhas_biq}</tbody></table>"""
        if biqueiras else '<p class="suave">Nenhum ponto de biqueira cadastrado para esta pessoa.</p>')
    form_biq = ""
    if pode_editar:
        form_biq = f"""
        <form method="post" action="/pessoas/{p['id']}/biqueiras" class="grade" style="margin-top:1rem">
          <input type="hidden" name="csrf" value="{e(csrf)}">
          <label class="span2">Local (nome/referência curta)<input name="local"
            placeholder="Ex.: Beco da Vila, esquina com a Rua das Flores"></label>
          <label class="span2">Endereço<input name="endereco" id="end_biq"></label>
          <label>Bairro<input name="bairro" id="bairro_biq"></label>
          <label>Cidade<input name="cidade" id="cidade_biq"></label>
          <label>Latitude<input name="lat" id="lat_biq"></label>
          <label>Longitude<input name="lon" id="lon_biq"></label>
          <div class="acoes span2" style="justify-content:flex-start">
            <button type="button" class="botao fantasma mini"
              onclick="geocodificar('end_biq','lat_biq','lon_biq','bairro_biq','cidade_biq')">Localizar coordenadas pelo endereço</button>
          </div>
          <label class="span2">Observações<input name="observacoes"></label>
          <div class="acoes span2"><button class="botao">Adicionar ponto de biqueira</button></div>
        </form>
        {SCRIPT_GEOCODIFICADOR}"""
    cartao_biqueiras = f"""<div class="cartao"><h2>Biqueiras (pontos de tráfico) — {len(biqueiras)}</h2>
        <p class="suave">Locais onde esta pessoa já foi localizada atuando.</p>
        {tabela_biq}{form_biq}</div>"""

    corpo = f"""
    <div class="cab">
      <div><h1>{e(p['nome'])}</h1>
        <div class="selos">{selo_preso}{alcunha}{selo_grau(p['grau_confiabilidade'])}{pill_status(p['status'])}</div>
      </div>
      {acoes}
    </div>
    <div class="cartoes">
      {cartao_foto}
      <div class="cartao"><h2>Identificação pessoal</h2>
        {li_campo('RG', p['rg'])}{li_campo('CPF', p['cpf'])}
        {li_campo('Data de nascimento', p['data_nascimento'])}</div>
      <div class="cartao"><h2>Filiação e família</h2>
        {li_campo('Mãe', p['nome_mae'])}{li_campo('Pai', p['nome_pai'])}
        {li_campo('Filhos', filhos)}{li_campo('Esposa / companheira', p['nome_companheira'])}</div>
      <div class="cartao"><h2>Vínculo investigativo</h2>
        {li_campo('Organização criminosa', p['organizacao'])}
        {li_campo('Cargo / função na organização', p['cargo_orcrim'])}
        {li_campo('Fonte da informação', p['fonte_informacao'])}
        {li_campo('Observações', p['observacoes'])}</div>
      <div class="cartao"><h2>Informações localizadas</h2>
        {li_campo('Resumo investigativo', p['resumo_investigativo'])}</div>
      <div class="cartao"><h2>Situação prisional</h2>
        {li_campo('Está preso(a)', 'Sim' if p['preso'] == 'sim' else 'Não')}
        {li_campo('Data da última prisão', p['data_ultima_prisao'])}
        {li_campo('Crime da prisão', p['crime_prisao'])}
        {li_campo('Status atualizado em', fmt_data(p['data_atualizacao_status_prisional']))}</div>
      <div class="cartao"><h2>Endereço</h2>
        {li_campo('Último endereço conhecido', p['endereco'])}</div>
      <div class="cartao"><h2>Controle administrativo</h2>
        {li_campo('Cadastrado em', fmt_data(p['criado_em']))}
        {li_campo('Cadastrado por', nomes_usuarios.get(p['criado_por'], '—'))}
        {li_campo('Última atualização', fmt_data(p['atualizado_em']))}
        {li_campo('Atualizado por', nomes_usuarios.get(p['atualizado_por'], '—'))}</div>
    </div>
    {cartao_biqueiras}
    {cartao_boletins}
    {galeria_fotos_leitura(fotos)}
    {cartao_materiais}
    {cartao_trilha}"""
    return pagina(p["nome"], corpo, usuario)


def pagina_pessoas_mesclar_selecionar(usuario, csrf, erro=""):
    con = conexao()
    pessoas = con.execute("SELECT id, nome, alcunha FROM pessoas ORDER BY nome").fetchall()
    con.close()
    def _opcao_pessoa(p):
        apelido = ' ({})'.format(e(p['alcunha'])) if p['alcunha'] else ''
        rotulo = '{}{} · #{}'.format(e(p['nome']), apelido, p['id'])
        return '<option value="{}" data-id="{}">'.format(rotulo, p['id'])

    dl = "".join(_opcao_pessoa(p) for p in pessoas)
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    corpo = f"""
    <div class="cab"><h1>Mesclar registros</h1></div>
    <div class="cartao">
      <p class="suave">Use quando dois cadastros forem, na verdade, a mesma pessoa (ex.: importados
      de BOs diferentes). Escolha os dois registros — na próxima tela você decide, campo a campo,
      o que manter. Fotos, ocorrências, materiais apreendidos e boletins dos dois são reunidos no
      registro final, sem duplicar. O outro registro é removido ao final. Esta ação não pode ser desfeita.</p>
      <datalist id="dl_mesclar">{dl}</datalist>
      <form method="get" action="/pessoas/mesclar" class="grade">
        <label class="span2">Registro A
          <input list="dl_mesclar" name="nome_a" placeholder="Digite o nome" required>
          <input type="hidden" name="pessoa_a"></label>
        <label class="span2">Registro B
          <input list="dl_mesclar" name="nome_b" placeholder="Digite o nome" required>
          <input type="hidden" name="pessoa_b"></label>
        {msg}
        <div class="acoes span2"><button class="botao">Comparar registros</button></div>
      </form>
    </div>
    <script>
    function ligarBusca(idNome, idId) {{
      document.getElementsByName(idNome)[0].addEventListener('input', function() {{
        var opt = document.querySelector('#dl_mesclar option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
        document.getElementsByName(idId)[0].value = opt ? opt.getAttribute('data-id') : '';
      }});
    }}
    ligarBusca('nome_a', 'pessoa_a');
    ligarBusca('nome_b', 'pessoa_b');
    </script>"""
    return pagina("Mesclar registros", corpo, usuario)


CAMPOS_SELECT_MESCLAGEM = {"fonte_informacao", "grau_confiabilidade", "status", "preso", "crime_prisao"}
CAMPOS_TEXTAREA_MESCLAGEM = {"observacoes", "endereco"}


def pagina_pessoas_mesclar_comparar(usuario, csrf, pa, pb):
    linhas = ""
    for campo, rotulo in CAMPOS_PESSOA:
        va, vb = pa[campo], pb[campo]
        va_label = STATUS_LABEL.get(va, va) if campo == "status" else va
        vb_label = STATUS_LABEL.get(vb, vb) if campo == "status" else vb
        usar_b_por_padrao = (not va) and bool(vb)
        marcado_a = "" if usar_b_por_padrao else "checked"
        marcado_b = "checked" if usar_b_por_padrao else ""
        valor_inicial = vb if usar_b_por_padrao else va
        campo_final = campo_form(campo, valor_inicial)
        botao_ambos = ""
        if campo not in CAMPOS_SELECT_MESCLAGEM and va and vb and va != vb:
            sep = "\\n\\n" if campo in CAMPOS_TEXTAREA_MESCLAGEM else " / "
            botao_ambos = (f'<button type="button" class="botao mini fantasma" style="margin-top:.3rem" '
                          f'onclick="usarAmbos(\'{campo}\', \'{js_attr(va)}\', \'{js_attr(vb)}\', \'{sep}\')">'
                          f'Manter os dois</button>')
        linhas += f"""<tr>
          <td>{e(rotulo)}</td>
          <td><label style="flex-direction:row;gap:.4rem;align-items:center">
            <input type="radio" name="escolha_{campo}" data-campo="{campo}" data-valor="{e(va) or ''}"
              {marcado_a} style="width:auto" onchange="usarValor(this)">
            <span>{e(va_label) or '<span class="suave">vazio</span>'}</span></label></td>
          <td><label style="flex-direction:row;gap:.4rem;align-items:center">
            <input type="radio" name="escolha_{campo}" data-campo="{campo}" data-valor="{e(vb) or ''}"
              {marcado_b} style="width:auto" onchange="usarValor(this)">
            <span>{e(vb_label) or '<span class="suave">vazio</span>'}</span></label></td>
          <td>{campo_final}{botao_ambos}</td>
        </tr>"""

    corpo = f"""
    <div class="cab"><h1>Conferir e mesclar</h1></div>
    <p class="suave">Para cada campo, use os botões A/B como atalho para preencher rapidamente
    a coluna "Valor final" com o dado do Registro A
    (<strong>{e(pa['nome'])}</strong>, #{pa['id']}) ou do Registro B
    (<strong>{e(pb['nome'])}</strong>, #{pb['id']}) — mas a coluna "Valor final" é o que
    realmente será salvo, e pode ser editada livremente (para corrigir, combinar ou
    digitar um valor diferente dos dois). O registro final ficará salvo com o número
    #{pa['id']}; o #{pb['id']} será removido, mas fotos, ocorrências, materiais e boletins dele
    passam automaticamente para o registro final.</p>
    <form method="post" action="/pessoas/mesclar/executar">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <input type="hidden" name="pessoa_a_id" value="{pa['id']}">
      <input type="hidden" name="pessoa_b_id" value="{pb['id']}">
      <table><thead><tr><th>Campo</th><th>Registro A (#{pa['id']})</th>
        <th>Registro B (#{pb['id']})</th><th>Valor final (editável)</th></tr></thead>
        <tbody>{linhas}</tbody></table>
      <p class="erro" style="margin-top:1rem">Esta ação não pode ser desfeita: o registro #{pb['id']}
      será excluído após a mesclagem.</p>
      <div class="acoes">
        <a class="botao fantasma" href="/pessoas/mesclar">Cancelar</a>
        <button class="botao">Confirmar mesclagem</button>
      </div>
    </form>
    <script>
    function usarValor(radio) {{
      var campo = radio.getAttribute('data-campo');
      var valor = radio.getAttribute('data-valor');
      var alvo = document.querySelector('[name="' + campo + '"]');
      if (!alvo) return;
      if (alvo.tagName === 'SELECT') {{
        var existe = Array.from(alvo.options).some(function(o) {{ return o.value === valor; }});
        if (!existe && valor) {{
          var op = document.createElement('option');
          op.value = valor; op.textContent = valor + ' (não está mais na lista)';
          alvo.appendChild(op);
        }}
      }}
      alvo.value = valor;
    }}
    function usarAmbos(campo, va, vb, sep) {{
      var alvo = document.querySelector('[name="' + campo + '"]');
      if (!alvo) return;
      alvo.value = va + sep + vb;
    }}
    </script>"""
    return pagina("Conferir e mesclar", corpo, usuario)
