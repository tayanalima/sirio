"""Módulo SIRIO — Materiais apreendidos.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403


def pagina_materiais_lista(usuario, csrf, filtros):
    con = conexao()
    sql = ("SELECT m.*, o.tipo_crime AS oc_tipo, p.nome AS pessoa_nome "
           "FROM materiais_apreendidos m "
           "LEFT JOIN ocorrencias o ON o.id = m.ocorrencia_id "
           "LEFT JOIN pessoas p ON p.id = m.pessoa_id WHERE 1=1")
    args = []
    if filtros.get("categoria"):
        sql += " AND m.categoria = ?"; args.append(filtros["categoria"])
    if filtros.get("situacao"):
        sql += " AND m.situacao = ?"; args.append(filtros["situacao"])
    if filtros.get("cidade"):
        sql += " AND m.cidade LIKE ?"; args.append(f"%{filtros['cidade']}%")
    if filtros.get("bairro"):
        sql += " AND m.bairro LIKE ?"; args.append(f"%{filtros['bairro']}%")
    if filtros.get("pessoa_id"):
        sql += " AND m.pessoa_id = ?"; args.append(filtros["pessoa_id"])
    sql += " ORDER BY m.id DESC LIMIT 500"
    registros = con.execute(sql, args).fetchall()
    pessoas = con.execute("SELECT id, nome FROM pessoas ORDER BY nome").fetchall()
    pessoa_filtrada = None
    if filtros.get("pessoa_id"):
        pessoa_filtrada = con.execute("SELECT nome FROM pessoas WHERE id=?", (filtros["pessoa_id"],)).fetchone()
    con.close()
    dl_pessoas = "".join(f'<option value="{e(p["nome"])}" data-id="{p["id"]}">' for p in pessoas)

    pode_editar = usuario["perfil"] in ("admin", "analista")
    botao_novo = '<a class="botao" href="/materiais/novo">Novo material</a>' if pode_editar else ""

    linhas = ""
    for m in registros:
        link_oc = (f'<a class="nomelink" href="/ocorrencias/{m["ocorrencia_id"]}">{e(m["oc_tipo"]) or "Ver ocorrência"}</a>'
                   if m["ocorrencia_id"] else "—")
        vinculado = (f'<a class="nomelink" href="/pessoas/{m["pessoa_id"]}">{e(m["pessoa_nome"])}</a>'
                    if m["pessoa_id"] else "—")
        linhas += f"""<tr>
          <td>{e(m['categoria']) or '—'}</td><td>{e(m['objeto']) or '—'}</td>
          <td>{e(m['quantidade']) or '—'}</td>
          <td><span class="pill p-{'ativo' if m['situacao']=='Apreendido' else 'em_verificacao'}">{e(m['situacao']) or '—'}</span></td>
          <td>{e(m['bairro']) or '—'}</td><td>{e(m['cidade']) or '—'}</td>
          <td>{link_oc}</td>
          <td>{vinculado}</td></tr>"""

    tabela = (f"""<table><thead><tr><th>Categoria</th><th>Objeto</th><th>Qtd.</th><th>Situação</th>
        <th>Bairro</th><th>Cidade</th><th>Ocorrência</th><th>Vinculado a</th></tr></thead>
        <tbody>{linhas}</tbody></table>""" if registros else
        '<div class="vazio">Nenhum material apreendido encontrado com esse filtro.</div>')

    filtro_pessoa_label = ""
    if pessoa_filtrada:
        filtro_pessoa_label = (f'<p class="suave">Mostrando apenas materiais apreendidos com '
                               f'<strong>{e(pessoa_filtrada["nome"])}</strong> ao longo do tempo. '
                               f'<a href="/materiais">Limpar este filtro</a>.</p>')

    corpo = f"""
    <div class="cab"><h1>Materiais apreendidos</h1>{botao_novo}</div>
    {filtro_pessoa_label}
    <datalist id="dl_pessoas_filtro">{dl_pessoas}</datalist>
    <form method="get" action="/materiais" class="painel" style="grid-template-columns:repeat(5,1fr) auto">
      <select name="categoria"><option value="">Categoria: todas</option>{opcoes(lista_ativa('categoria_material'), filtros.get('categoria',''))}</select>
      <select name="situacao"><option value="">Situação: todas</option>{opcoes(lista_ativa('situacao_material'), filtros.get('situacao',''))}</select>
      <input name="bairro" placeholder="Filtrar por bairro" value="{e(filtros.get('bairro',''))}">
      <input name="cidade" placeholder="Filtrar por cidade" value="{e(filtros.get('cidade',''))}">
      <input list="dl_pessoas_filtro" id="filtro_pessoa_nome" placeholder="Filtrar por envolvido cadastrado"
        value="{e(pessoa_filtrada['nome']) if pessoa_filtrada else ''}">
      <input type="hidden" name="pessoa_id" id="filtro_pessoa_id" value="{e(filtros.get('pessoa_id',''))}">
      <button class="botao">Filtrar</button>
    </form>
    <script>
    document.getElementById('filtro_pessoa_nome')?.addEventListener('input', function() {{
      var opt = document.querySelector('#dl_pessoas_filtro option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
      document.getElementById('filtro_pessoa_id').value = opt ? opt.getAttribute('data-id') : '';
    }});
    </script>
    {tabela}"""
    return pagina("Materiais apreendidos", corpo, usuario)


def pagina_material_form(usuario, csrf, dados=None, erro=""):
    dados = dados or {}
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome):
        return dados.get(nome) or ""

    con = conexao()
    pessoas = con.execute("SELECT id, nome FROM pessoas ORDER BY nome").fetchall()
    ocorrencias = con.execute(
        "SELECT id, tipo_crime, data_fato FROM ocorrencias ORDER BY id DESC LIMIT 300").fetchall()
    con.close()
    dl_pessoas = "".join(f'<option value="{e(p["nome"])}" data-id="{p["id"]}">' for p in pessoas)
    dl_ocorrencias = "".join(
        f'<option value="{e(o["tipo_crime"] or "Ocorrência")} — {e(o["data_fato"]) or "sem data"} (#{o["id"]})" data-id="{o["id"]}">'
        for o in ocorrencias)

    corpo = f"""
    <div class="cab"><h1>Novo material apreendido</h1></div>
    <datalist id="dl_pessoas">{dl_pessoas}</datalist>
    <datalist id="dl_ocorrencias">{dl_ocorrencias}</datalist>
    <form method="post" action="/materiais/novo">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Material</legend><div class="grade">
        <label>Categoria<select name="categoria">{opcoes(lista_ativa('categoria_material'), v('categoria'))}</select></label>
        <label>Objeto<input name="objeto" value="{e(v('objeto'))}" placeholder="Ex.: Telefone celular Samsung"></label>
        <label>Quantidade<input name="quantidade" value="{e(v('quantidade')) or '1'}"></label>
        <label>Situação<select name="situacao">{opcoes(lista_ativa('situacao_material'), v('situacao') or 'Apreendido')}</select></label>
        <label>Marca<input name="marca" value="{e(v('marca'))}"></label>
        <label>Modelo<input name="modelo" value="{e(v('modelo'))}"></label>
        <label>Cor<input name="cor" value="{e(v('cor'))}"></label>
        <label>Nº do lacre/invólucro<input name="numero_lacre" value="{e(v('numero_lacre'))}"></label>
      </div></fieldset>
      <fieldset><legend>Local (para estatística por cidade/bairro)</legend><div class="grade">
        <label>Bairro<input name="bairro" value="{e(v('bairro'))}"></label>
        <label>Cidade<input name="cidade" value="{e(v('cidade'))}"></label>
      </div></fieldset>
      <fieldset><legend>Vínculos (opcionais)</legend><div class="grade">
        <label class="span2">Ocorrência relacionada
          <input list="dl_ocorrencias" name="ocorrencia_nome_livre" placeholder="Digite para localizar uma ocorrência">
          <input type="hidden" name="ocorrencia_id" id="mat_ocorrencia_id"></label>
        <label class="span2">Pessoa envolvida
          <input list="dl_pessoas" name="pessoa_nome_livre" placeholder="Digite o nome">
          <input type="hidden" name="pessoa_id" id="mat_pessoa_id"></label>
      </div></fieldset>
      <fieldset><legend>Observações</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="2">{e(v('observacoes'))}</textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/materiais">Cancelar</a>
        <button class="botao">Salvar material</button>
      </div>
    </form>
    <script>
    document.querySelector('input[name="pessoa_nome_livre"]')?.addEventListener('input', function() {{
      var opt = document.querySelector('#dl_pessoas option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
      document.getElementById('mat_pessoa_id').value = opt ? opt.getAttribute('data-id') : '';
    }});
    document.querySelector('input[name="ocorrencia_nome_livre"]')?.addEventListener('input', function() {{
      var opt = document.querySelector('#dl_ocorrencias option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
      document.getElementById('mat_ocorrencia_id').value = opt ? opt.getAttribute('data-id') : '';
    }});
    </script>"""
    return pagina("Novo material", corpo, usuario)
