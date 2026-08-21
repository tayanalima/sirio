"""Módulo SIRIO — Violência Doméstica: Casos (Onda 1).

Cadastro do caso, vínculo de pessoas com papéis (reaproveitando o cadastro
de pessoas já existente no SIRIO), dados do fato, características de
violência e vínculo com ocorrências já cadastradas.
"""
from sirio_core import *  # noqa: F401,F403
from sirio_vd_core import *  # noqa: F401,F403
from sirio_vd_fonar import *  # noqa: F401,F403
from sirio_vd_protetivas import *  # noqa: F401,F403
from sirio_vd_gestao import *  # noqa: F401,F403


def pagina_vd_lista(usuario, csrf, filtros):
    sql = "SELECT * FROM vd_casos WHERE 1=1"
    args = []
    if filtros.get("situacao"):
        sql += " AND situacao = ?"; args.append(filtros["situacao"])
    else:
        # Cadastros cancelados só aparecem quando explicitamente filtrados por
        # situação. Fora isso, ficam de fora das listagens.
        marcas = ",".join("?" for _ in VD_SITUACOES_OCULTAS)
        sql += f" AND situacao NOT IN ({marcas})"; args += list(VD_SITUACOES_OCULTAS)
    if filtros.get("municipio"):
        sql += " AND municipio LIKE ?"; args.append(f"%{filtros['municipio']}%")
    if filtros.get("q"):
        sql += (" AND (numero_reds LIKE ? OR numero_inquerito LIKE ? OR"
                " numero_processo_judicial LIKE ? OR local_fato LIKE ?)")
        args += [f"%{filtros['q']}%"] * 4
    sql += " ORDER BY id DESC LIMIT 500"

    con = conexao()
    casos = con.execute(sql, args).fetchall()
    # nome da mulher atendida de cada caso, para exibir na listagem
    nomes_mulher = {}
    tipos_penais = {}
    casos_com_descumprimento = set()
    casos_com_diligencia_vencida = set()
    if casos:
        ids = [c["id"] for c in casos]
        marcas = ",".join("?" for _ in ids)
        for r in con.execute(
                f"SELECT cp.caso_id, p.nome FROM vd_caso_pessoas cp "
                f"JOIN pessoas p ON p.id = cp.pessoa_id "
                f"WHERE cp.papel='mulher_atendida' AND cp.caso_id IN ({marcas})", ids):
            nomes_mulher.setdefault(r["caso_id"], []).append(r["nome"])
        for r in con.execute(
                f"SELECT vo.caso_id, o.tipo_crime FROM vd_caso_ocorrencias vo "
                f"JOIN ocorrencias o ON o.id = vo.ocorrencia_id "
                f"WHERE vo.caso_id IN ({marcas}) AND o.tipo_crime IS NOT NULL", ids):
            tipos_penais.setdefault(r["caso_id"], []).append(r["tipo_crime"])
        for r in con.execute(
                f"SELECT mp.caso_id FROM vd_descumprimentos dc "
                f"JOIN vd_medidas_protetivas mp ON mp.id = dc.medida_id "
                f"WHERE mp.caso_id IN ({marcas}) "
                f"AND (dc.situacao_apuracao IS NULL OR dc.situacao_apuracao IN ('registrado','em_apuracao'))", ids):
            casos_com_descumprimento.add(r["caso_id"])
        hoje = agora()[:10]
        marcas_situacao = ",".join("?" for _ in VD_SITUACOES_DILIGENCIA_ABERTAS)
        for r in con.execute(
                f"SELECT caso_id FROM vd_diligencias WHERE caso_id IN ({marcas}) "
                f"AND prazo IS NOT NULL AND prazo < ? AND situacao IN ({marcas_situacao})",
                ids + [hoje] + list(VD_SITUACOES_DILIGENCIA_ABERTAS)):
            casos_com_diligencia_vencida.add(r["caso_id"])
    con.close()

    pode_editar = usuario["perfil"] in ("admin", "analista")
    botao_novo = '<a class="botao" href="/vd/novo">Novo caso</a>' if pode_editar else ""

    linhas = ""
    for c in casos:
        mulheres = ", ".join(nomes_mulher.get(c["id"], [])) or "—"
        tipo_penal = ", ".join(dict.fromkeys(tipos_penais.get(c["id"], []))) or "—"
        selos_alerta = []
        if c["id"] in casos_com_descumprimento:
            selos_alerta.append('<span class="selo s-preso">Descumprimento</span>')
        if c["id"] in casos_com_diligencia_vencida:
            selos_alerta.append('<span class="selo s-preso">Diligência vencida</span>')
        alerta = " ".join(selos_alerta) or "—"
        linhas += f"""<tr>
          <td><a class="nomelink" href="/vd/{c['id']}">#{c['id']}</a></td>
          <td>{e(mulheres)}</td>
          <td>{e(c['numero_reds']) or '—'}</td>
          <td>{e(tipo_penal)}</td>
          <td>{e(c['municipio']) or '—'}</td>
          <td>{e(c['data_hora_fato']) or '—'}</td>
          <td><span class="pill p-em_verificacao">{e(VD_SITUACAO_LABEL.get(c['situacao'], c['situacao']))}</span></td>
          <td>{e(VD_SIGILO_LABEL.get(c['nivel_sigilo'], c['nivel_sigilo']))}</td>
          <td>{alerta}</td></tr>"""

    tabela = (f"""<table><thead><tr><th>Nº</th><th>Mulher atendida</th><th>REDS</th>
        <th>Tipo penal</th><th>Município</th><th>Data do fato</th><th>Situação</th><th>Sigilo</th>
        <th>Alerta</th></tr></thead>
        <tbody>{linhas}</tbody></table>""" if casos else
        '<div class="vazio">Nenhum caso cadastrado ainda.</div>')

    corpo = f"""
    <div class="cab"><h1>Violência Doméstica — Casos</h1>{botao_novo}</div>
    <p class="suave"><a href="/vd/painel">Painel operacional</a> ·
      <a href="/vd/painel-gerencial">Painel gerencial</a></p>
    <p class="aviso">Módulo de apoio ao registro, acompanhamento e gestão de casos de
    violência doméstica e familiar contra a mulher. Não substitui a análise profissional
    nem a decisão da autoridade policial.</p>
    <form method="get" action="/vd" class="painel" style="grid-template-columns:1fr 1fr 1fr auto">
      <input name="q" value="{e(filtros.get('q',''))}" placeholder="Buscar por REDS, inquérito, processo ou local">
      <select name="situacao"><option value="">Situação: todas</option>{opcoes(VD_SITUACOES, filtros.get('situacao',''))}</select>
      <input name="municipio" value="{e(filtros.get('municipio',''))}" placeholder="Filtrar por município">
      <button class="botao">Filtrar</button>
    </form>
    {tabela}"""
    return pagina("Violência Doméstica", corpo, usuario)


def pagina_vd_form(usuario, csrf, dados=None, caso_id=None, erro=""):
    dados = dados or {}
    titulo = "Editar caso" if caso_id else "Novo caso"
    acao = f"/vd/{caso_id}/editar" if caso_id else "/vd/novo"
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome):
        return dados.get(nome) or ""

    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    con.close()
    servidor_padrao = v("servidor_responsavel_id") or str(usuario["id"])
    opcoes_usuarios = "".join(
        f'<option value="{u["id"]}"{" selected" if str(u["id"]) == servidor_padrao else ""}>{e(u["nome"])}</option>'
        for u in usuarios)

    corpo = f"""
    <div class="cab"><h1>{titulo}</h1></div>
    <form method="post" action="{acao}">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>1 · Identificação do caso</legend><div class="grade">
        <label>Número do REDS/BO<input name="numero_reds" value="{e(v('numero_reds'))}"></label>
        <label>Número do inquérito policial<input name="numero_inquerito" value="{e(v('numero_inquerito'))}"></label>
        <label>Outro procedimento<input name="numero_outro_procedimento" value="{e(v('numero_outro_procedimento'))}"></label>
        <label>Número do processo judicial<input name="numero_processo_judicial" value="{e(v('numero_processo_judicial'))}"></label>
        <label>Número da medida protetiva<input name="numero_medida_protetiva" value="{e(v('numero_medida_protetiva'))}"></label>
        <label>Nível de sigilo<select name="nivel_sigilo">{opcoes(VD_NIVEIS_SIGILO, v('nivel_sigilo') or 'normal')}</select></label>
      </div></fieldset>
      <fieldset><legend>2 · Atendimento</legend><div class="grade">
        <label>Unidade responsável<input name="unidade_responsavel" value="{e(v('unidade_responsavel'))}"></label>
        <label>Município<input name="municipio" value="{e(v('municipio'))}"></label>
        <label>Data e hora do atendimento<input type="datetime-local" name="data_hora_atendimento" value="{e(v('data_hora_atendimento'))}"></label>
        <label>Servidor responsável<select name="servidor_responsavel_id">{opcoes_usuarios}</select></label>
        <label>Autoridade responsável<input name="autoridade_responsavel" value="{e(v('autoridade_responsavel'))}"></label>
        <label>Origem da demanda<select name="origem_demanda"><option value="">Selecionar…</option>{opcoes(VD_ORIGENS_DEMANDA, v('origem_demanda'))}</select></label>
        <label>Canal de atendimento<select name="canal_atendimento"><option value="">Selecionar…</option>{opcoes(VD_CANAIS_ATENDIMENTO, v('canal_atendimento'))}</select></label>
      </div></fieldset>
      <fieldset><legend>3 · Dados do fato</legend><div class="grade">
        <label>Data e hora do fato<input type="datetime-local" name="data_hora_fato" value="{e(v('data_hora_fato'))}"></label>
        <label class="span2">Local do fato<input name="local_fato" value="{e(v('local_fato'))}"></label>
        <label class="span2">Descrição livre do fato<textarea name="descricao_fato" rows="3">{e(v('descricao_fato'))}</textarea></label>
        <label class="span2">Relato da mulher (registrado como relato, não como fato confirmado)
          <textarea name="relato_mulher" rows="4">{e(v('relato_mulher'))}</textarea></label>
        <label class="span2">Observações do servidor (separadas do relato)
          <textarea name="observacoes_servidor" rows="3">{e(v('observacoes_servidor'))}</textarea></label>
        <label>Fonte do relato<input name="fonte_relato" value="{e(v('fonte_relato'))}" placeholder="Ex.: relato direto, BO, terceiros"></label>
      </div></fieldset>
      <fieldset><legend>4 · Observações gerais</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="2">{e(v('observacoes'))}</textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd">Cancelar</a>
        <button class="botao">Salvar como rascunho / continuar depois</button>
      </div>
      <p class="suave" style="text-align:right;margin-top:.3rem">O caso é salvo com situação
      "Rascunho" e pode ser retomado a qualquer momento — nada obriga a preencher tudo de uma vez.</p>
    </form>"""
    return pagina(titulo, corpo, usuario)


def pagina_vd_detalhe(usuario, csrf, caso, pessoas_vinculadas, ocorrencias_vinculadas,
                       tipos_violencia, marcadores, nomes_usuarios, reincidencia=None, avaliacoes=None,
                       medidas=None, diligencias=None, encaminhamentos=None, acompanhamentos=None):
    pode_editar = usuario["perfil"] in ("admin", "analista")

    acoes = ""
    if pode_editar:
        opcoes_situacao = opcoes(VD_SITUACOES, caso["situacao"])
        # Cancelar é para cadastro feito por engano: nada é apagado e dá para
        # reverter. Excluir apaga de vez e é exclusivo do Administrador.
        cancelar = ""
        if caso["situacao"] != "cancelado":
            cancelar = f"""
          <form method="post" action="/vd/{caso['id']}/cancelar" style="display:inline"
            onsubmit="return pedirMotivoCancelamento(this)">
            <input type="hidden" name="csrf" value="{e(csrf)}">
            <button class="botao mini fantasma">Cancelar cadastro</button></form>"""
        excluir = ""
        if usuario["perfil"] == "admin":
            excluir = f"""
          <form method="post" action="/vd/{caso['id']}/excluir" style="display:inline"
            onsubmit="return confirmarExclusaoCaso()">
            <input type="hidden" name="csrf" value="{e(csrf)}">
            <button class="botao perigo">Excluir</button></form>"""
        acoes = f"""
        <div class="acoes" style="margin:0">
          <a class="botao fantasma" href="/vd/{caso['id']}/editar">Editar</a>
          <form method="post" action="/vd/{caso['id']}/situacao" style="display:flex;gap:.4rem"
            onsubmit="return confirmarMudancaSituacao(this)">
            <input type="hidden" name="csrf" value="{e(csrf)}">
            <select name="situacao">{opcoes_situacao}</select>
            <button class="botao mini fantasma">Alterar situação</button>
          </form>
          {cancelar}
          {excluir}
        </div>
        <script>
        function pedirMotivoCancelamento(form) {{
          var motivo = prompt(
            'Cancelar é para cadastro feito por engano (duplicado, teste, dados trocados).\\n'
            + 'O caso sai das listagens e dos painéis, mas nada é apagado e dá para reverter.\\n\\n'
            + 'Para um caso real que chegou ao fim, use Alterar situação > Encerrado.\\n\\n'
            + 'Motivo do cancelamento (obrigatório):');
          if (!motivo || motivo.trim().length < 5) {{
            alert('É necessário informar o motivo do cancelamento.');
            return false;
          }}
          var campo = document.createElement('input');
          campo.type = 'hidden'; campo.name = 'motivo'; campo.value = motivo.trim();
          form.appendChild(campo);
          return true;
        }}
        function confirmarExclusaoCaso() {{
          return confirm(
            'EXCLUIR DEFINITIVAMENTE este caso?\\n\\n'
            + 'Serão apagados o relato da mulher, o FONAR, as avaliações, as medidas '
            + 'protetivas, os descumprimentos, as diligências, os encaminhamentos e o '
            + 'acompanhamento. A ação NÃO pode ser desfeita.\\n\\n'
            + 'Se o objetivo é apenas tirar um cadastro errado da tela, use '
            + '"Cancelar cadastro" — nada é perdido e dá para reverter.');
        }}
        </script>
        <script>
        function confirmarMudancaSituacao(form) {{
          var sel = form.querySelector('select[name="situacao"]').value;
          if (sel === 'encerrado' || sel === 'reaberto') {{
            var motivo = prompt(sel === 'encerrado'
              ? 'Justificativa do encerramento (obrigatória):'
              : 'Motivo da reabertura (obrigatório):');
            if (!motivo || !motivo.trim()) {{ alert('É necessário informar a justificativa.'); return false; }}
            var campo = document.createElement('input');
            campo.type = 'hidden';
            campo.name = sel === 'encerrado' ? 'motivo_encerramento' : 'motivo_reabertura';
            campo.value = motivo.trim();
            form.appendChild(campo);
          }}
          return true;
        }}
        </script>"""

    aviso_sigilo = ""
    if caso["nivel_sigilo"] != "normal":
        aviso_sigilo = (f'<p class="aviso">Nível de sigilo: '
                        f'<strong>{e(VD_SIGILO_LABEL.get(caso["nivel_sigilo"]))}</strong>. '
                        f'Trate as informações deste caso com o cuidado correspondente.</p>')

    aviso_reincidencia = ""
    if reincidencia and (reincidencia.get("casos_mulher", 0) > 1 or reincidencia.get("casos_autor", 0) > 1):
        partes = []
        if reincidencia.get("casos_mulher", 0) > 1:
            partes.append(f'{reincidencia["casos_mulher"]} caso(s) no sistema envolvendo a mesma mulher atendida')
        if reincidencia.get("casos_autor", 0) > 1:
            partes.append(f'{reincidencia["casos_autor"]} caso(s) no sistema envolvendo o mesmo suposto autor')
        aviso_reincidencia = (
            f'<p class="aviso"><strong>Possível reincidência encontrada:</strong> {"; ".join(partes)}. '
            f'A confirmação de que se trata da mesma pessoa deve ser feita por análise humana '
            f'(mesmo nome não significa necessariamente a mesma pessoa).</p>')

    medidas = medidas or []
    medidas_com_descumprimento = [m for m in medidas if m["tem_descumprimento_aberto"]]
    aviso_descumprimento = ""
    if medidas_com_descumprimento:
        links = ", ".join(f'<a href="/vd/medidas/{m["id"]}">#{m["id"]}</a>' for m in medidas_com_descumprimento)
        aviso_descumprimento = (
            f'<p class="erro"><strong>⚠ Descumprimento de medida protetiva em aberto</strong> — '
            f'medida(s) {links}. Verifique providências urgentes.</p>')

    diligencias = diligencias or []
    n_vencidas = sum(1 for dl in diligencias if diligencia_vencida(dl))
    aviso_diligencias = ""
    if n_vencidas:
        aviso_diligencias = (
            f'<p class="aviso"><strong>{n_vencidas} diligência(s) com prazo vencido</strong> '
            f'ainda em aberto neste caso.</p>')

    # Pessoas vinculadas, agrupadas por papel
    linhas_pessoas = ""
    for cp in pessoas_vinculadas:
        excluir = ""
        dados_extra = ""
        if cp["papel"] in ("mulher_atendida", "suposto_autor"):
            dados_extra = f' · <a href="/vd/caso-pessoas/{cp["id"]}/dados">Dados específicos</a>'
        if cp["papel"] == "mulher_atendida":
            dados_extra += f' · <a href="/vd/caso-pessoas/{cp["id"]}/fonar">FONAR</a>'
        if pode_editar:
            excluir = f"""<form method="post" action="/vd/caso-pessoas/{cp['id']}/excluir" style="display:inline"
              onsubmit="return confirm('Desvincular esta pessoa do caso? O cadastro dela no SIRIO não é afetado.')">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao perigo mini">Desvincular</button></form>"""
        linhas_pessoas += f"""<tr>
          <td><span class="pill p-em_verificacao">{e(VD_PAPEL_LABEL.get(cp['papel'], cp['papel']))}</span></td>
          <td><a class="nomelink" href="/pessoas/{cp['pessoa_id']}">{e(cp['nome'])}</a>{dados_extra}</td>
          <td>{excluir}</td></tr>"""
    tabela_pessoas = (f"""<table><thead><tr><th>Papel</th><th>Pessoa</th><th></th></tr></thead>
        <tbody>{linhas_pessoas}</tbody></table>""" if pessoas_vinculadas
        else '<p class="suave">Nenhuma pessoa vinculada a este caso ainda.</p>')

    form_pessoa = ""
    if pode_editar:
        con = conexao()
        pessoas = con.execute("SELECT id, nome, alcunha FROM pessoas ORDER BY nome").fetchall()
        con.close()
        def _opcao_pessoa(p):
            apelido = ' ({})'.format(e(p['alcunha'])) if p['alcunha'] else ''
            rotulo = '{}{} · #{}'.format(e(p['nome']), apelido, p['id'])
            return '<option value="{}" data-id="{}">'.format(rotulo, p['id'])

        dl = "".join(_opcao_pessoa(p) for p in pessoas)
        form_pessoa = f"""
        <datalist id="dl_vd_pessoas">{dl}</datalist>
        <form method="post" action="/vd/{caso['id']}/pessoas" class="grade" style="margin-top:1rem">
          <input type="hidden" name="csrf" value="{e(csrf)}">
          <label class="span2">Pessoa (busque no cadastro do SIRIO ou{" "}
            <a href="/pessoas/nova" target="_blank">cadastre uma nova</a> antes de vincular)
            <input list="dl_vd_pessoas" id="vd_pessoa_nome" placeholder="Digite o nome" required>
            <input type="hidden" name="pessoa_id" id="vd_pessoa_id"></label>
          <label>Papel no caso<select name="papel">{opcoes(VD_PAPEIS, '')}</select></label>
          <div class="acoes span2" style="justify-content:flex-start">
            <button class="botao fantasma">Vincular ao caso</button></div>
        </form>
        <script>
        document.getElementById('vd_pessoa_nome')?.addEventListener('input', function() {{
          var opt = document.querySelector('#dl_vd_pessoas option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
          document.getElementById('vd_pessoa_id').value = opt ? opt.getAttribute('data-id') : '';
        }});
        </script>"""
    cartao_pessoas = f"""<div class="cartao"><h2>Pessoas envolvidas</h2>{tabela_pessoas}{form_pessoa}</div>"""

    # Ocorrências vinculadas
    linhas_oc = ""
    for vo in ocorrencias_vinculadas:
        excluir_oc = ""
        if pode_editar:
            excluir_oc = f"""<form method="post" action="/vd/caso-ocorrencias/{vo['vinculo_id']}/excluir" style="display:inline"
              onsubmit="return confirm('Desvincular esta ocorrência do caso?')">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao perigo mini">Desvincular</button></form>"""
        linhas_oc += f"""<tr>
          <td><a class="nomelink" href="/ocorrencias/{vo['id']}">{e(vo['tipo_crime']) or 'Ocorrência'}</a></td>
          <td>{e(vo['data_fato']) or '—'}</td><td>{e(vo['endereco_fato']) or '—'}</td>
          <td>{excluir_oc}</td></tr>"""
    tabela_oc = (f"""<table><thead><tr><th>Tipo</th><th>Data</th><th>Local</th><th></th></tr></thead>
        <tbody>{linhas_oc}</tbody></table>""" if ocorrencias_vinculadas
        else '<p class="suave">Nenhuma ocorrência vinculada.</p>')
    form_oc = ""
    if pode_editar:
        con = conexao()
        ocs = con.execute(
            "SELECT id, tipo_crime, data_fato FROM ocorrencias ORDER BY id DESC LIMIT 300").fetchall()
        con.close()
        dl_oc = "".join(
            f'<option value="{e(o["tipo_crime"] or "Ocorrência")} — {e(o["data_fato"]) or "sem data"} (#{o["id"]})" data-id="{o["id"]}">'
            for o in ocs)
        form_oc = f"""
        <datalist id="dl_vd_ocorrencias">{dl_oc}</datalist>
        <form method="post" action="/vd/{caso['id']}/ocorrencias" class="grade" style="margin-top:1rem">
          <input type="hidden" name="csrf" value="{e(csrf)}">
          <label class="span2">Ocorrência já cadastrada no SIRIO (inclusive as importadas de BO)
            <input list="dl_vd_ocorrencias" id="vd_oc_nome" placeholder="Digite para localizar">
            <input type="hidden" name="ocorrencia_id" id="vd_oc_id"></label>
          <div class="acoes span2" style="justify-content:flex-start">
            <button class="botao fantasma">Vincular ocorrência</button></div>
        </form>
        <script>
        document.getElementById('vd_oc_nome')?.addEventListener('input', function() {{
          var opt = document.querySelector('#dl_vd_ocorrencias option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
          document.getElementById('vd_oc_id').value = opt ? opt.getAttribute('data-id') : '';
        }});
        </script>"""
    cartao_oc = f"""<div class="cartao"><h2>Ocorrências vinculadas</h2>
      <p class="suave">Vincula ocorrências já cadastradas no SIRIO (inclusive vindas de Boletim de
      Ocorrência importado) a este caso — os dados do fato continuam existindo só na ocorrência,
      não são duplicados aqui.</p>
      {tabela_oc}{form_oc}</div>"""

    # Caracterização da violência
    checks_tipo = ""
    for valor in lista_ativa("vd_tipo_violencia"):
        marcado = "checked" if valor in tipos_violencia else ""
        checks_tipo += (f'<label style="flex-direction:row;gap:.4rem;align-items:center">'
                        f'<input type="checkbox" name="tipo" value="{e(valor)}" {marcado} style="width:auto">{e(valor)}</label>')
    checks_marcador = ""
    for valor in lista_ativa("vd_marcador_operacional"):
        marcado = "checked" if valor in marcadores else ""
        checks_marcador += (f'<label style="flex-direction:row;gap:.4rem;align-items:center">'
                            f'<input type="checkbox" name="marcador" value="{e(valor)}" {marcado} style="width:auto">{e(valor)}</label>')
    form_violencia = ""
    if pode_editar:
        form_violencia = f"""
        <form method="post" action="/vd/{caso['id']}/violencia">
          <input type="hidden" name="csrf" value="{e(csrf)}">
          <p class="suave">Formas de violência (Lei Maria da Penha):</p>
          <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem">{checks_tipo}</div>
          <p class="suave">Marcadores operacionais complementares:</p>
          <div style="display:flex;gap:1rem;flex-wrap:wrap">{checks_marcador}</div>
          <div class="acoes"><button class="botao">Salvar caracterização</button></div>
        </form>
        <p class="suave">Essas listas são gerenciadas pelo Administrador na aba Configurações
        ("Violência doméstica — Formas de violência" / "— Marcadores operacionais").</p>"""
    else:
        lista_tv = ", ".join(tipos_violencia) or "Nenhuma forma de violência caracterizada ainda."
        lista_mk = ", ".join(marcadores) or "Nenhum marcador registrado."
        form_violencia = f"<p>{e(lista_tv)}</p><p class=\"suave\">{e(lista_mk)}</p>"
    cartao_violencia = f"""<div class="cartao"><h2>Caracterização da violência</h2>{form_violencia}</div>"""

    botao_avaliacao = (f'<a class="botao fantasma" href="/vd/{caso["id"]}/avaliacao/nova">'
                       f'Nova avaliação profissional</a>' if pode_editar else "")
    cartao_avaliacao = cartao_avaliacoes_profissionais(avaliacoes or [], nomes_usuarios)

    corpo = f"""
    <div class="cab"><div><h1>Caso #{caso['id']}</h1>
      <div class="selos"><span class="pill p-em_verificacao">{e(VD_SITUACAO_LABEL.get(caso['situacao'], caso['situacao']))}</span>
      <span class="selo">{e(VD_SIGILO_LABEL.get(caso['nivel_sigilo'], caso['nivel_sigilo']))}</span></div></div>
      {acoes}</div>
    <p class="suave"><a href="/vd/{caso['id']}/linha-tempo">Ver linha do tempo</a> ·
      <a href="/vd/{caso['id']}/relatorio">Gerar relatório do caso</a></p>
    {aviso_sigilo}{aviso_reincidencia}{aviso_descumprimento}{aviso_diligencias}
    <div class="cartoes">
      <div class="cartao"><h2>Identificação</h2>
        {li_campo('REDS/BO', caso['numero_reds'])}{li_campo('Inquérito policial', caso['numero_inquerito'])}
        {li_campo('Outro procedimento', caso['numero_outro_procedimento'])}
        {li_campo('Processo judicial', caso['numero_processo_judicial'])}
        {li_campo('Medida protetiva', caso['numero_medida_protetiva'])}</div>
      <div class="cartao"><h2>Atendimento</h2>
        {li_campo('Unidade responsável', caso['unidade_responsavel'])}{li_campo('Município', caso['municipio'])}
        {li_campo('Data/hora atendimento', fmt_data(caso['data_hora_atendimento']) if caso['data_hora_atendimento'] and ':' in str(caso['data_hora_atendimento']) else caso['data_hora_atendimento'])}
        {li_campo('Servidor responsável', nomes_usuarios.get(caso['servidor_responsavel_id'], '—'))}
        {li_campo('Autoridade responsável', caso['autoridade_responsavel'])}
        {li_campo('Origem da demanda', caso['origem_demanda'])}{li_campo('Canal de atendimento', caso['canal_atendimento'])}</div>
      <div class="cartao"><h2>Dados do fato</h2>
        {li_campo('Data/hora do fato', caso['data_hora_fato'])}{li_campo('Local do fato', caso['local_fato'])}
        {li_campo('Descrição do fato', caso['descricao_fato'])}</div>
      <div class="cartao"><h2>Relato</h2>
        {li_campo('Relato da mulher', caso['relato_mulher'])}
        {li_campo('Observações do servidor', caso['observacoes_servidor'])}
        {li_campo('Fonte do relato', caso['fonte_relato'])}</div>
      <div class="cartao"><h2>Controle administrativo</h2>
        {li_campo('Criado em', fmt_data(caso['criado_em']))}{li_campo('Criado por', nomes_usuarios.get(caso['criado_por'], '—'))}
        {li_campo('Última atualização', fmt_data(caso['atualizado_em']))}
        {li_campo('Motivo de encerramento', caso['motivo_encerramento'])}
        {li_campo('Motivo de reabertura', caso['motivo_reabertura'])}</div>
      <div class="cartao"><h2>Observações gerais</h2>{li_campo('', caso['observacoes'])}</div>
    </div>
    {cartao_pessoas}
    {cartao_violencia}
    {cartao_medidas_protetivas(medidas, caso['id'], pode_editar)}
    <div class="cab" style="margin-bottom:.5rem">{botao_avaliacao}</div>
    {cartao_avaliacao}
    {cartao_diligencias(diligencias, caso['id'], pode_editar)}
    {cartao_encaminhamentos(encaminhamentos or [], caso['id'], pode_editar)}
    {cartao_acompanhamentos(acompanhamentos or [], caso['id'], pode_editar)}
    {cartao_oc}"""
    return pagina(f"Caso #{caso['id']}", corpo, usuario)


def pagina_vd_dados_papel(usuario, csrf, caso, cp, pessoa, dados_extra, erro=""):
    pode_editar = usuario["perfil"] in ("admin", "analista")
    eh_mulher = cp["papel"] == "mulher_atendida"
    dados_extra = dados_extra or {}
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome):
        return dados_extra.get(nome) or ""

    if eh_mulher:
        avisos_contato = ""
        if v("telefone_controlado_agressor") == "sim":
            avisos_contato = ('<p class="erro"><strong>ATENÇÃO:</strong> o telefone desta pessoa foi '
                              'indicado como controlado/acessado pelo agressor.</p>')
        corpo_campos = f"""
        <p class="aviso">Antes de telefonar ou enviar mensagem, verifique as restrições de contato
        seguro registradas abaixo.</p>
        {avisos_contato}
        <fieldset><legend>Contato seguro</legend><div class="grade">
          <label>Telefone seguro<input name="telefone_seguro" value="{e(v('telefone_seguro'))}"></label>
          <label>Telefone alternativo seguro<input name="telefone_alt_seguro" value="{e(v('telefone_alt_seguro'))}"></label>
          <label>Autorização para ligação<select name="autoriza_ligacao">{opcoes_sim_nao(v('autoriza_ligacao'))}</select></label>
          <label>Autorização para mensagem<select name="autoriza_mensagem">{opcoes_sim_nao(v('autoriza_mensagem'))}</select></label>
          <label>Forma mais segura de contato<input name="forma_contato_segura" value="{e(v('forma_contato_segura'))}"></label>
          <label>Melhor horário para contato<input name="melhor_horario_contato" value="{e(v('melhor_horario_contato'))}"></label>
          <label class="span2">Palavras/informações que NÃO podem aparecer em mensagens
            <input name="palavras_proibidas_mensagem" value="{e(v('palavras_proibidas_mensagem'))}"></label>
          <label>Telefone controlado/acessado pelo agressor?<select name="telefone_controlado_agressor">{opcoes_sim_nao(v('telefone_controlado_agressor'))}</select></label>
          <label class="span2">Endereço considerado seguro<input name="endereco_seguro" value="{e(v('endereco_seguro'))}"></label>
        </div></fieldset>
        <fieldset><legend>Rede de apoio</legend><div class="grade">
          <label>Pessoa de confiança<input name="pessoa_confianca_nome" value="{e(v('pessoa_confianca_nome'))}"></label>
          <label>Contato da pessoa de confiança<input name="pessoa_confianca_contato" value="{e(v('pessoa_confianca_contato'))}"></label>
          <label class="span2">Vínculo com serviços da rede de proteção<input name="vinculo_rede_protecao" value="{e(v('vinculo_rede_protecao'))}"></label>
        </div></fieldset>
        <fieldset><legend>Situação e vulnerabilidades</legend><div class="grade">
          <label>Dependência econômica do suposto autor?<select name="dependencia_economica">{opcoes_sim_nao(v('dependencia_economica'))}</select></label>
          <label>Gravidez<select name="gravidez">{opcoes_sim_nao(v('gravidez'))}</select></label>
          <label>Puerpério<select name="puerperio">{opcoes_sim_nao(v('puerperio'))}</select></label>
          <label>Deficiência<select name="deficiencia">{opcoes_sim_nao(v('deficiencia'))}</select></label>
          <label>Dificuldade de locomoção<select name="dificuldade_locomocao">{opcoes_sim_nao(v('dificuldade_locomocao'))}</select></label>
          <label>Necessidade de intérprete<select name="necessidade_interprete">{opcoes_sim_nao(v('necessidade_interprete'))}</select></label>
          <label>Necessidade de atendimento acessível<select name="necessidade_atendimento_acessivel">{opcoes_sim_nao(v('necessidade_atendimento_acessivel'))}</select></label>
          <label>Existe local seguro para permanecer?<select name="existe_local_seguro">{opcoes_sim_nao(v('existe_local_seguro'))}</select></label>
          <label>Interesse/necessidade de acolhimento<select name="interesse_acolhimento">{opcoes_sim_nao(v('interesse_acolhimento'))}</select></label>
        </div></fieldset>
        <fieldset><legend>Percepção de risco</legend><div class="grade">
          <label class="span2">Manifestação espontânea da mulher sobre percepção de risco
            <textarea name="percepcao_risco" rows="3">{e(v('percepcao_risco'))}</textarea></label>
        </div></fieldset>"""
    else:
        corpo_campos = f"""
        <fieldset><legend>Relacionamento</legend><div class="grade">
          <label>Relacionamento com a mulher<input name="relacionamento_mulher" value="{e(v('relacionamento_mulher'))}"></label>
          <label>Relacionamento atual ou anterior?<input name="relacionamento_atual" value="{e(v('relacionamento_atual'))}" placeholder="Atual / Anterior"></label>
          <label>Convivência atual?<select name="convivencia_atual">{opcoes_sim_nao(v('convivencia_atual'))}</select></label>
          <label>Tempo de relacionamento<input name="tempo_relacionamento" value="{e(v('tempo_relacionamento'))}"></label>
          <label>Filhos em comum?<select name="filhos_em_comum">{opcoes_sim_nao(v('filhos_em_comum'))}</select></label>
          <label>Veículos<input name="veiculos" value="{e(v('veiculos'))}"></label>
        </div></fieldset>
        <fieldset><legend>Fatores de risco relatados</legend><div class="grade">
          <label>Acesso conhecido a arma de fogo<select name="acesso_arma_fogo">{opcoes_sim_nao(v('acesso_arma_fogo'))}</select></label>
          <label>Vínculo com forças policiais/militares/segurança<select name="vinculo_forcas_seguranca">{opcoes_sim_nao(v('vinculo_forcas_seguranca'))}</select></label>
          <label>Uso problemático de álcool (relatado)<select name="uso_alcool">{opcoes_sim_nao(v('uso_alcool'))}</select></label>
          <label>Uso de drogas (relatado)<select name="uso_drogas">{opcoes_sim_nao(v('uso_drogas'))}</select></label>
          <label>Histórico de ameaças<select name="historico_ameacas">{opcoes_sim_nao(v('historico_ameacas'))}</select></label>
          <label>Histórico de agressões<select name="historico_agressoes">{opcoes_sim_nao(v('historico_agressoes'))}</select></label>
          <label>Histórico de perseguição<select name="historico_perseguicao">{opcoes_sim_nao(v('historico_perseguicao'))}</select></label>
          <label>Medidas protetivas anteriores<select name="medidas_protetivas_anteriores">{opcoes_sim_nao(v('medidas_protetivas_anteriores'))}</select></label>
          <label>Descumprimentos anteriores<select name="descumprimentos_anteriores">{opcoes_sim_nao(v('descumprimentos_anteriores'))}</select></label>
        </div></fieldset>
        <fieldset><legend>Outros vínculos</legend><div class="grade">
          <label class="span2">Outras vítimas relacionadas<input name="outras_vitimas" value="{e(v('outras_vitimas'))}"></label>
          <label class="span2">Outras ocorrências<input name="outras_ocorrencias" value="{e(v('outras_ocorrencias'))}"></label>
          <label class="span2">Outros procedimentos<input name="outros_procedimentos" value="{e(v('outros_procedimentos'))}"></label>
        </div></fieldset>
        <fieldset><legend>Confiabilidade dos dados acima</legend><div class="grade">
          <label class="span2">Estes dados são, em geral
            <select name="grau_verificacao">
              <option value="">Selecionar…</option>
              <option value="Relatado pela mulher"{' selected' if v('grau_verificacao')=='Relatado pela mulher' else ''}>Informação relatada pela mulher</option>
              <option value="Confirmado em consulta"{' selected' if v('grau_verificacao')=='Confirmado em consulta' else ''}>Informação confirmada em consulta</option>
              <option value="Pendente de verificação"{' selected' if v('grau_verificacao')=='Pendente de verificação' else ''}>Pendente de verificação</option>
            </select></label>
          <label class="span2">Observações<textarea name="observacoes" rows="3">{e(v('observacoes'))}</textarea></label>
        </div></fieldset>"""

    corpo = f"""
    <div class="cab"><h1>Dados específicos — {e(VD_PAPEL_LABEL.get(cp['papel']))}</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a> ·
    Pessoa: <a href="/pessoas/{pessoa['id']}">{e(pessoa['nome'])}</a></p>
    {'<form method="post">' if not pode_editar else f'<form method="post" action="/vd/caso-pessoas/{cp["id"]}/dados">'}
      <input type="hidden" name="csrf" value="{e(csrf)}">
      {corpo_campos}
      {msg}
      {'<div class="acoes"><button class="botao">Salvar</button></div>' if pode_editar else ''}
    </form>"""
    return pagina("Dados específicos", corpo, usuario)
