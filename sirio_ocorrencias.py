"""Módulo SIRIO — Ocorrências e testemunhas.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403


def pagina_ocorrencias_lista(usuario, csrf, filtro_tipo="", filtro_pessoa_autor_id=""):
    con = conexao()
    sql = "SELECT * FROM ocorrencias WHERE 1=1"
    args = []
    if filtro_tipo:
        sql += " AND tipo_crime = ?"
        args.append(filtro_tipo)
    if filtro_pessoa_autor_id:
        sql += " AND pessoa_autor_id = ?"
        args.append(filtro_pessoa_autor_id)
    sql += " ORDER BY data_fato DESC, id DESC LIMIT 500"
    registros = con.execute(sql, args).fetchall()
    pessoa_filtrada = None
    if filtro_pessoa_autor_id:
        pessoa_filtrada = con.execute(
            "SELECT nome FROM pessoas WHERE id=?", (filtro_pessoa_autor_id,)).fetchone()
    con.close()

    pode_editar = usuario["perfil"] in ("admin", "analista")
    botao_novo = '<a class="botao" href="/ocorrencias/nova">Nova ocorrência</a>' if pode_editar else ""

    linhas = ""
    for o in registros:
        linhas += f"""<tr>
          <td><a class="nomelink" href="/ocorrencias/{o['id']}">{e(o['tipo_crime']) or '—'}</a></td>
          <td>{e(o['data_fato']) or '—'}</td>
          <td>{e(o['endereco_fato']) or '—'}</td>
          <td>{e(o['nome_autor']) or '—'}</td>
          <td>{e(o['nome_vitima']) or '—'}</td></tr>"""

    tabela = (f"""<table><thead><tr><th>Tipo de crime</th><th>Data do fato</th>
        <th>Local do fato</th><th>Autor</th><th>Vítima</th></tr></thead>
        <tbody>{linhas}</tbody></table>""" if registros else
        '<div class="vazio">Nenhuma ocorrência cadastrada ainda.</div>')

    filtro_pessoa_label = ""
    if pessoa_filtrada:
        filtro_pessoa_label = (f'<p class="suave">Mostrando apenas ocorrências em que '
                               f'<strong>{e(pessoa_filtrada["nome"])}</strong> é a autora vinculada. '
                               f'<a href="/ocorrencias">Limpar este filtro</a>.</p>')

    corpo = f"""
    <div class="cab"><h1>Ocorrências</h1>{botao_novo}</div>
    {filtro_pessoa_label}
    <form method="get" action="/ocorrencias" class="painel" style="grid-template-columns:1fr auto">
      <input type="hidden" name="pessoa_autor_id" value="{e(filtro_pessoa_autor_id)}">
      <select name="tipo"><option value="">Tipo de crime: todos</option>{opcoes(lista_ativa('tipo_crime'), filtro_tipo)}</select>
      <button class="botao">Filtrar</button>
    </form>
    {tabela}"""
    return pagina("Ocorrências", corpo, usuario)


def pagina_ocorrencia_form(usuario, csrf, dados=None, ocorrencia_id=None, erro=""):
    dados = dados or {}
    titulo = "Editar ocorrência" if ocorrencia_id else "Nova ocorrência"
    acao = f"/ocorrencias/{ocorrencia_id}/editar" if ocorrencia_id else "/ocorrencias/nova"
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome):
        return dados.get(nome) or ""

    con = conexao()
    pessoas = con.execute("SELECT id, nome FROM pessoas ORDER BY nome").fetchall()
    con.close()
    lista_pessoas = "".join(f'<option value="{e(p["nome"])}" data-id="{p["id"]}">' for p in pessoas)

    def campo_coord(prefixo, rotulo, mostrar_pessoa=False, mostrar_cidade_bairro=False):
        campo_pessoa = ""
        if mostrar_pessoa:
            campo_pessoa = f"""
            <label class="span2">Vincular a pessoa já cadastrada (opcional)
              <input list="dl_pessoas" name="pessoa_autor_nome" value="{e(v('pessoa_autor_nome'))}"
                placeholder="Digite o nome para localizar um registro existente">
              <input type="hidden" name="pessoa_autor_id" id="pessoa_autor_id" value="{e(v('pessoa_autor_id'))}">
            </label>"""
        # Só o bloco do fato tem campos separados de bairro e cidade; para eles,
        # a busca de coordenadas precisa desse contexto. Nos blocos de autor,
        # vítima e testemunha o endereço é texto único e já traz bairro e cidade.
        contexto_geocod = ",'bairro_fato','cidade_fato'" if mostrar_cidade_bairro else ""
        campo_cidade_bairro = ""
        if mostrar_cidade_bairro:
            campo_cidade_bairro = f"""
            <label>Bairro (para estatística por bairro)<input name="bairro_fato" id="bairro_fato" value="{e(v('bairro_fato'))}"></label>
            <label>Cidade (para estatística por cidade)<input name="cidade_fato" id="cidade_fato" value="{e(v('cidade_fato'))}"></label>"""
        return f"""
        <fieldset><legend>{rotulo}</legend><div class="grade">
          {campo_pessoa}
          <label class="span2">Nome<input name="nome_{prefixo}" value="{e(v(f'nome_{prefixo}'))}"></label>
          <label class="span2">Endereço<input name="endereco_{prefixo}" id="end_{prefixo}"
            value="{e(v(f'endereco_{prefixo}'))}"></label>
          {campo_cidade_bairro}
          <label>Latitude<input name="lat_{prefixo}" id="lat_{prefixo}" value="{e(v(f'lat_{prefixo}'))}"
            placeholder="Ex.: -22.4267"></label>
          <label>Longitude<input name="lon_{prefixo}" id="lon_{prefixo}" value="{e(v(f'lon_{prefixo}'))}"
            placeholder="Ex.: -45.4581"></label>
          <div class="acoes span2" style="justify-content:flex-start">
            <button type="button" class="botao fantasma mini"
              onclick="geocodificar('end_{prefixo}','lat_{prefixo}','lon_{prefixo}'{contexto_geocod})">
              Localizar coordenadas pelo endereço</button>
          </div>
        </div></fieldset>"""

    corpo = f"""
    <div class="cab"><h1>{titulo}</h1></div>
    <datalist id="dl_pessoas">{lista_pessoas}</datalist>
    <form method="post" action="{acao}">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Tipo de ocorrência</legend><div class="grade">
        <label>Tipo de crime<select name="tipo_crime">{opcoes(lista_ativa('tipo_crime'), v('tipo_crime'))}</select></label>
        <label>Número do BO (opcional)<input name="numero_bo" value="{e(v('numero_bo'))}"></label>
        <label>Data do fato<input type="date" name="data_fato" value="{e(v('data_fato'))}"></label>
      </div></fieldset>
      {campo_coord('fato', '1 · Local do fato', mostrar_cidade_bairro=True)}
      {campo_coord('autor', '2 · Autor', mostrar_pessoa=True)}
      {campo_coord('vitima', '3 · Vítima')}
      <fieldset><legend>4 · Observações</legend><div class="grade">
        <label class="span2">Observações<textarea name="observacoes" rows="3">{e(v('observacoes'))}</textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/ocorrencias">Cancelar</a>
        <button class="botao">Salvar ocorrência</button>
      </div>
    </form>
    <script>
    document.querySelector('input[name="pessoa_autor_nome"]')?.addEventListener('input', function() {{
      var opt = document.querySelector('#dl_pessoas option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
      document.getElementById('pessoa_autor_id').value = opt ? opt.getAttribute('data-id') : '';
    }});
    </script>
    {SCRIPT_GEOCODIFICADOR}"""
    return pagina(titulo, corpo, usuario)


def pagina_ocorrencia_detalhe(usuario, csrf, o, testemunhas, nome_autor_pessoa, materiais, lista_pessoas_html):
    pode_editar = usuario["perfil"] in ("admin", "analista")
    acoes = ""
    if pode_editar:
        excluir = ""
        if usuario["perfil"] == "admin":
            excluir = f"""<form method="post" action="/ocorrencias/{o['id']}/excluir" style="display:inline"
              onsubmit="return confirm('Excluir esta ocorrência, suas testemunhas e materiais vinculados?')">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao perigo">Excluir</button></form>"""
        acoes = f"""<div class="acoes" style="margin:0">
          <a class="botao fantasma" href="/ocorrencias/{o['id']}/editar">Editar</a>{excluir}</div>"""

    vinc = f' — vínculo: <a href="/pessoas/{o["pessoa_autor_id"]}">{e(nome_autor_pessoa)}</a>' if nome_autor_pessoa else ""

    linhas_test = ""
    for t in testemunhas:
        excluir_t = ""
        if pode_editar:
            excluir_t = f"""<form method="post" action="/testemunhas/{t['id']}/excluir" style="display:inline"
              onsubmit="return confirm('Excluir esta testemunha?')">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao perigo mini">Excluir</button></form>"""
        linhas_test += f"""<tr><td>{e(t['nome']) or '—'}</td><td>{e(t['endereco']) or '—'}</td>
          <td>{e(t['lat'])}, {e(t['lon'])}</td><td>{excluir_t}</td></tr>"""
    tabela_test = (f"""<table><thead><tr><th>Nome</th><th>Endereço</th><th>Coordenadas</th><th></th></tr></thead>
        <tbody>{linhas_test}</tbody></table>""" if testemunhas
        else '<p class="suave">Nenhuma testemunha cadastrada.</p>')

    form_test = ""
    if pode_editar:
        form_test = f"""
        <form method="post" action="/ocorrencias/{o['id']}/testemunhas" class="grade" style="margin-top:1rem">
          <input type="hidden" name="csrf" value="{e(csrf)}">
          <label class="span2">Nome<input name="nome"></label>
          <label class="span2">Endereço<input name="endereco" id="end_test"></label>
          <label>Latitude<input name="lat" id="lat_test"></label>
          <label>Longitude<input name="lon" id="lon_test"></label>
          <div class="acoes span2" style="justify-content:flex-start">
            <button type="button" class="botao fantasma mini"
              onclick="geocodificar('end_test','lat_test','lon_test')">Localizar coordenadas pelo endereço</button>
          </div>
          <div class="acoes span2"><button class="botao">Adicionar testemunha</button></div>
        </form>"""

    linhas_mat = ""
    for m in materiais:
        excluir_m = ""
        if pode_editar:
            excluir_m = f"""<form method="post" action="/materiais/{m['id']}/excluir" style="display:inline"
              onsubmit="return confirm('Excluir este material?')">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao perigo mini">Excluir</button></form>"""
        vinculado = f'<a href="/pessoas/{m["pessoa_id"]}">{e(m["pessoa_nome"])}</a>' if m["pessoa_id"] else "—"
        linhas_mat += f"""<tr>
          <td>{e(m['categoria']) or '—'}</td><td>{e(m['objeto']) or '—'}</td>
          <td>{e(m['quantidade']) or '—'}</td>
          <td>{' / '.join(x for x in [m['marca'], m['modelo'], m['cor']] if x) or '—'}</td>
          <td><span class="pill p-{'ativo' if m['situacao']=='Apreendido' else 'em_verificacao'}">{e(m['situacao']) or '—'}</span></td>
          <td>{vinculado}</td><td>{excluir_m}</td></tr>"""
    tabela_mat = (f"""<table><thead><tr><th>Categoria</th><th>Objeto</th><th>Qtd.</th>
        <th>Marca/modelo/cor</th><th>Situação</th><th>Vinculado a</th><th></th></tr></thead>
        <tbody>{linhas_mat}</tbody></table>""" if materiais
        else '<p class="suave">Nenhum material apreendido cadastrado.</p>')

    form_mat = ""
    if pode_editar:
        form_mat = f"""
        <form method="post" action="/ocorrencias/{o['id']}/materiais" class="grade" style="margin-top:1rem">
          <input type="hidden" name="csrf" value="{e(csrf)}">
          <label>Categoria<select name="categoria">{opcoes(lista_ativa('categoria_material'), '')}</select></label>
          <label>Objeto<input name="objeto" placeholder="Ex.: Telefone celular Samsung"></label>
          <label>Quantidade<input name="quantidade" value="1"></label>
          <label>Situação<select name="situacao">{opcoes(lista_ativa('situacao_material'), 'Apreendido')}</select></label>
          <label>Marca<input name="marca"></label>
          <label>Modelo<input name="modelo"></label>
          <label>Cor<input name="cor"></label>
          <label>Nº do lacre/invólucro<input name="numero_lacre"></label>
          <label class="span2">Vincular à pessoa envolvida (opcional)
            <input list="dl_pessoas_mat" name="pessoa_nome_livre" placeholder="Digite o nome">
            <input type="hidden" name="pessoa_id" id="mat_pessoa_id"></label>
          <label class="span2">Observações<input name="observacoes"></label>
          <div class="acoes span2"><button class="botao">Adicionar material</button></div>
        </form>
        <datalist id="dl_pessoas_mat">{lista_pessoas_html}</datalist>
        <script>
        document.querySelector('input[name="pessoa_nome_livre"]')?.addEventListener('input', function() {{
          var opt = document.querySelector('#dl_pessoas_mat option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
          document.getElementById('mat_pessoa_id').value = opt ? opt.getAttribute('data-id') : '';
        }});
        </script>"""

    script_geocod = SCRIPT_GEOCODIFICADOR if pode_editar else ""

    corpo = f"""
    <div class="cab"><div><h1>{e(o['tipo_crime']) or 'Ocorrência'}</h1>
      <p class="suave">Data do fato: {e(o['data_fato']) or 'não informada'}
      {' · BO ' + e(o['numero_bo']) if o['numero_bo'] else ''}</p></div>{acoes}</div>
    <div class="cartoes">
      <div class="cartao"><h2>Local do fato</h2>
        {li_campo('Endereço', o['endereco_fato'])}
        {li_campo('Bairro', o['bairro_fato'])}
        {li_campo('Cidade', o['cidade_fato'])}
        {li_campo('Coordenadas', f"{o['lat_fato']}, {o['lon_fato']}" if o['lat_fato'] else None)}</div>
      <div class="cartao"><h2>Autor{vinc}</h2>
        {li_campo('Nome', o['nome_autor'])}
        {li_campo('Endereço', o['endereco_autor'])}
        {li_campo('Coordenadas', f"{o['lat_autor']}, {o['lon_autor']}" if o['lat_autor'] else None)}</div>
      <div class="cartao"><h2>Vítima</h2>
        {li_campo('Nome', o['nome_vitima'])}
        {li_campo('Endereço', o['endereco_vitima'])}
        {li_campo('Coordenadas', f"{o['lat_vitima']}, {o['lon_vitima']}" if o['lat_vitima'] else None)}</div>
      <div class="cartao"><h2>Observações</h2>{li_campo('', o['observacoes'])}</div>
    </div>
    <div class="cartao"><h2>Testemunhas</h2>{tabela_test}{form_test}</div>
    <div class="cartao"><h2>Materiais apreendidos</h2>{tabela_mat}{form_mat}</div>
    {script_geocod}"""
    return pagina(e(o["tipo_crime"]) or "Ocorrência", corpo, usuario)
