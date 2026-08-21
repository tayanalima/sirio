"""Módulo SIRIO — Violência Doméstica: Linha do Tempo, Painéis e Relatórios (Onda 5).

Fecha o conjunto de telas do módulo. A linha do tempo reaproveita os eventos
já registrados por TODAS as ondas anteriores (tabela vd_eventos_linha_tempo,
alimentada desde a Onda 1) — nada precisou ser recriado, só exibido.

Os relatórios são páginas HTML com estilo próprio de impressão (o navegador
gera o PDF, sem precisar de nenhuma biblioteca nova) — mantém o SIRIO com
zero dependências de instalação, como desde o início.

O painel gerencial NUNCA soma indicadores por servidor individual — só
agregados institucionais (por mês, município, tipo de violência etc.),
seguindo a mesma cautela do restante do módulo.
"""
from sirio_core import *  # noqa: F401,F403
from sirio_vd_core import *  # noqa: F401,F403
from datetime import timedelta

VD_EVENTO_LABEL = {
    "criacao_caso": "Caso criado",
    "atualizacao_caso": "Caso atualizado",
    "mudanca_situacao": "Situação do caso alterada",
    "vinculo_pessoa": "Pessoa vinculada ao caso",
    "desvinculo_pessoa": "Pessoa desvinculada do caso",
    "vinculo_ocorrencia": "Ocorrência vinculada",
    "desvinculo_ocorrencia": "Ocorrência desvinculada",
    "caracterizacao_violencia": "Violência caracterizada",
    "atualizacao_dados_especificos": "Dados específicos atualizados",
    "fonar_aplicado": "FONAR aplicado",
    "avaliacao_profissional": "Avaliação profissional registrada",
    "medida_protetiva_criada": "Medida protetiva criada",
    "medida_protetiva_atualizada": "Medida protetiva atualizada",
    "item_medida_adicionado": "Item de medida adicionado",
    "item_medida_removido": "Item de medida removido",
    "descumprimento_registrado": "Descumprimento registrado",
    "diligencia_criada": "Diligência criada",
    "diligencia_atualizada": "Diligência atualizada",
    "encaminhamento_criado": "Encaminhamento criado",
    "encaminhamento_atualizado": "Encaminhamento atualizado",
    "acompanhamento_registrado": "Acompanhamento registrado",
    "acompanhamento_atualizado": "Acompanhamento atualizado",
}
VD_EVENTOS_CRITICOS = {"descumprimento_registrado"}


def pagina_linha_tempo(usuario, csrf, caso, eventos, nomes_usuarios):
    itens = ""
    for ev in eventos:
        critico = " critico" if ev["tipo_evento"] in VD_EVENTOS_CRITICOS else ""
        rotulo = VD_EVENTO_LABEL.get(ev["tipo_evento"], ev["tipo_evento"])
        quando = fmt_data(ev["timestamp"]) if ":" in str(ev["timestamp"] or "") else e(ev["timestamp"])
        responsavel = nomes_usuarios.get(ev["usuario_id"], "—")
        itens += f"""<li class="{critico.strip()}">
          <div class="quando">{quando} · {e(responsavel)}</div>
          <div class="descr"><strong>{e(rotulo)}</strong> — {e(ev['descricao']) or ''}</div>
        </li>"""
    corpo_lista = (f'<ul class="timeline">{itens}</ul>' if eventos
                   else '<div class="vazio">Nenhum evento registrado ainda neste caso.</div>')

    corpo = f"""
    <div class="cab"><h1>Linha do tempo — Caso #{caso['id']}</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <p class="suave">Reúne, em ordem cronológica, tudo o que já aconteceu neste caso — criação,
    vínculos, aplicações do FONAR, medidas protetivas, diligências, encaminhamentos e
    acompanhamentos. Eventos em vermelho marcam possíveis descumprimentos.</p>
    {corpo_lista}"""
    return pagina(f"Linha do tempo — Caso #{caso['id']}", corpo, usuario)


# ----------------------------------------------------------------------------
# Painel operacional
# ----------------------------------------------------------------------------

def calcula_painel_operacional():
    con = conexao()
    hoje = agora()[:10]
    sete_dias_atras = (datetime.strptime(hoje, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    trinta_dias_atras = (datetime.strptime(hoje, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    def buscar(sql, args=()):
        return con.execute(sql, args).fetchall()

    filas = {}
    filas["casos_novos"] = buscar(
        "SELECT id, numero_reds, criado_em FROM vd_casos WHERE criado_em >= ? "
        "AND situacao NOT IN ('cancelado') ORDER BY criado_em DESC",
        (sete_dias_atras,))
    filas["aguardando_providencia"] = buscar(
        "SELECT id, numero_reds FROM vd_casos WHERE situacao='aguardando_providencia' ORDER BY id DESC")
    filas["fonar_pendente"] = buscar(
        "SELECT cp.caso_id AS id, c.numero_reds, p.nome FROM vd_caso_pessoas cp "
        "JOIN vd_casos c ON c.id = cp.caso_id JOIN pessoas p ON p.id = cp.pessoa_id "
        "WHERE cp.papel='mulher_atendida' AND cp.id NOT IN (SELECT DISTINCT caso_pessoa_id FROM vd_fonar_aplicacoes) "
        "AND c.situacao NOT IN ('encerrado','cancelado') ORDER BY c.id DESC")
    filas["avaliacao_pendente"] = buscar(
        "SELECT id, numero_reds FROM vd_casos WHERE id NOT IN "
        "(SELECT DISTINCT caso_id FROM vd_avaliacoes_profissionais) AND situacao NOT IN ('encerrado','cancelado') "
        "ORDER BY id DESC")
    filas["medidas_aguardando_decisao"] = buscar(
        "SELECT mp.id, mp.caso_id, c.numero_reds FROM vd_medidas_protetivas mp "
        "JOIN vd_casos c ON c.id = mp.caso_id "
        "WHERE mp.situacao IN ('solicitada','enviada','aguardando_decisao') "
        "AND c.situacao NOT IN ('cancelado') ORDER BY mp.id DESC")
    filas["medidas_aguardando_intimacao"] = buscar(
        "SELECT mp.id, mp.caso_id, c.numero_reds FROM vd_medidas_protetivas mp "
        "JOIN vd_casos c ON c.id = mp.caso_id "
        "WHERE (mp.situacao='pendente_intimacao' OR (mp.situacao IN ('deferida','vigente') "
        "AND mp.data_intimacao_autor IS NULL)) AND c.situacao NOT IN ('cancelado') ORDER BY mp.id DESC")
    marcas_situacao = ",".join("?" for _ in VD_SITUACOES_DILIGENCIA_ABERTAS)
    filas["diligencias_vencidas"] = buscar(
        f"SELECT dl.id, dl.caso_id, c.numero_reds, dl.descricao, dl.prazo FROM vd_diligencias dl "
        f"JOIN vd_casos c ON c.id = dl.caso_id "
        f"WHERE dl.prazo IS NOT NULL AND dl.prazo < ? AND dl.situacao IN ({marcas_situacao}) "
        f"AND c.situacao NOT IN ('cancelado') ORDER BY dl.prazo", [hoje] + list(VD_SITUACOES_DILIGENCIA_ABERTAS))
    filas["acompanhamentos_vencidos"] = buscar(
        "SELECT ac.id, ac.caso_id, c.numero_reds, ac.data_prevista FROM vd_contatos_acompanhamento ac "
        "JOIN vd_casos c ON c.id = ac.caso_id "
        "WHERE ac.data_prevista IS NOT NULL AND ac.data_prevista <= ? AND ac.data_realizada IS NULL "
        "AND c.situacao NOT IN ('cancelado') ORDER BY ac.data_prevista", (hoje,))
    filas["descumprimentos_abertos"] = buscar(
        "SELECT dc.id, mp.caso_id, c.numero_reds, dc.data_hora FROM vd_descumprimentos dc "
        "JOIN vd_medidas_protetivas mp ON mp.id = dc.medida_id JOIN vd_casos c ON c.id = mp.caso_id "
        "WHERE (dc.situacao_apuracao IS NULL OR dc.situacao_apuracao IN ('registrado','em_apuracao')) "
        "AND c.situacao NOT IN ('cancelado') ORDER BY dc.id DESC")
    filas["sem_responsavel"] = buscar(
        "SELECT id, numero_reds FROM vd_casos WHERE servidor_responsavel_id IS NULL "
        "AND situacao NOT IN ('encerrado','cancelado') ORDER BY id DESC")
    filas["sem_atualizacao"] = buscar(
        "SELECT id, numero_reds, COALESCE(atualizado_em, criado_em) AS ultima FROM vd_casos "
        "WHERE COALESCE(atualizado_em, criado_em) < ? AND situacao NOT IN ('encerrado','cancelado') ORDER BY ultima",
        (trinta_dias_atras,))
    con.close()
    return filas


def pagina_painel_operacional(usuario, csrf, filas):
    def bloco(titulo, itens, rotulo_vazio, fmt_item):
        linhas = "".join(fmt_item(it) for it in itens) if itens else f'<p class="suave">{rotulo_vazio}</p>'
        return f"""<div class="cartao"><h2>{e(titulo)} ({len(itens)})</h2>{linhas}</div>"""

    def link_caso(cid, texto):
        return f'<p style="margin:.25rem 0"><a class="nomelink" href="/vd/{cid}">{e(texto)}</a></p>'

    blocos = ""
    blocos += bloco("Casos novos (últimos 7 dias)", filas["casos_novos"], "Nenhum caso novo.",
                    lambda c: link_caso(c["id"], f"#{c['id']} — {c['numero_reds'] or 'sem REDS'}"))
    blocos += bloco("Aguardando providência", filas["aguardando_providencia"], "Nenhum caso nesta situação.",
                    lambda c: link_caso(c["id"], f"#{c['id']} — {c['numero_reds'] or 'sem REDS'}"))
    blocos += bloco("FONAR pendente (mulher sem nenhuma aplicação)", filas["fonar_pendente"],
                    "Nenhuma pendência.", lambda c: link_caso(c["id"], f"#{c['id']} — {c['nome']}"))
    blocos += bloco("Avaliação profissional pendente", filas["avaliacao_pendente"], "Nenhuma pendência.",
                    lambda c: link_caso(c["id"], f"#{c['id']} — {c['numero_reds'] or 'sem REDS'}"))
    blocos += bloco("Medidas protetivas aguardando decisão", filas["medidas_aguardando_decisao"],
                    "Nenhuma pendência.", lambda m: link_caso(m["caso_id"], f"Caso #{m['caso_id']} — medida #{m['id']}"))
    blocos += bloco("Medidas aguardando intimação", filas["medidas_aguardando_intimacao"],
                    "Nenhuma pendência.", lambda m: link_caso(m["caso_id"], f"Caso #{m['caso_id']} — medida #{m['id']}"))
    blocos += bloco("Diligências vencidas", filas["diligencias_vencidas"], "Nenhuma diligência vencida.",
                    lambda dl: link_caso(dl["caso_id"], f"Caso #{dl['caso_id']} — {dl['descricao'][:60]} (prazo {dl['prazo']})"))
    blocos += bloco("Acompanhamentos vencidos", filas["acompanhamentos_vencidos"], "Nenhum acompanhamento vencido.",
                    lambda ac: link_caso(ac["caso_id"], f"Caso #{ac['caso_id']} — previsto para {ac['data_prevista']}"))
    blocos += bloco("Possíveis descumprimentos em aberto", filas["descumprimentos_abertos"],
                    "Nenhum descumprimento em aberto.", lambda dc: link_caso(dc["caso_id"], f"Caso #{dc['caso_id']}"))
    blocos += bloco("Casos sem responsável definido", filas["sem_responsavel"], "Todos os casos têm responsável.",
                    lambda c: link_caso(c["id"], f"#{c['id']} — {c['numero_reds'] or 'sem REDS'}"))
    blocos += bloco("Casos sem atualização há mais de 30 dias", filas["sem_atualizacao"],
                    "Nenhum caso parado.", lambda c: link_caso(c["id"], f"#{c['id']} — {c['numero_reds'] or 'sem REDS'}"))

    corpo = f"""
    <div class="cab"><h1>Painel operacional — Violência Doméstica</h1></div>
    <p class="suave"><a href="/vd">« Voltar aos casos</a> · <a href="/vd/painel-gerencial">Ver painel gerencial</a></p>
    <p class="suave">Filas de trabalho para triagem diária — cada bloco lista casos que merecem
    atenção agora. Não é uma fila automática de prioridade: a leitura é sempre da equipe.</p>
    <div class="cartoes">{blocos}</div>"""
    return pagina("Painel operacional", corpo, usuario)


# ----------------------------------------------------------------------------
# Painel gerencial e estatístico — SEMPRE agregado, NUNCA por servidor
# individual (decisão institucional já registrada desde o Onda 1).
# ----------------------------------------------------------------------------

def calcula_painel_gerencial(filtros):
    con = conexao()
    # Cadastro cancelado é erro de digitação, não caso real: não pode entrar em
    # nenhum indicador, senão a estatística da unidade sai inflada.
    where = "WHERE situacao NOT IN ({})".format(",".join("?" for _ in VD_SITUACOES_OCULTAS))
    args = list(VD_SITUACOES_OCULTAS)
    if filtros.get("municipio"):
        where += " AND municipio LIKE ?"; args.append(f"%{filtros['municipio']}%")
    if filtros.get("data_de"):
        where += " AND date(criado_em) >= ?"; args.append(filtros["data_de"])
    if filtros.get("data_ate"):
        where += " AND date(criado_em) <= ?"; args.append(filtros["data_ate"])

    ind = {}
    ind["total_casos"] = con.execute(f"SELECT COUNT(*) FROM vd_casos {where}", args).fetchone()[0]
    ind["por_situacao"] = con.execute(
        f"SELECT situacao, COUNT(*) c FROM vd_casos {where} GROUP BY situacao ORDER BY c DESC", args).fetchall()
    ind["por_mes"] = con.execute(
        f"SELECT substr(criado_em,1,7) AS mes, COUNT(*) c FROM vd_casos {where} "
        f"GROUP BY mes ORDER BY mes DESC LIMIT 12", args).fetchall()
    ind["por_municipio"] = con.execute(
        f"SELECT COALESCE(NULLIF(municipio,''),'Não informado') AS mun, COUNT(*) c FROM vd_casos {where} "
        f"GROUP BY mun ORDER BY c DESC LIMIT 10", args).fetchall()

    ids_casos = [r["id"] for r in con.execute(f"SELECT id FROM vd_casos {where}", args)]
    if ids_casos:
        marcas = ",".join("?" for _ in ids_casos)
        ind["formas_violencia"] = con.execute(
            f"SELECT tipo, COUNT(*) c FROM vd_caso_tipos_violencia WHERE caso_id IN ({marcas}) "
            f"GROUP BY tipo ORDER BY c DESC", ids_casos).fetchall()
        ind["reincidencia_mulheres"] = con.execute(
            "SELECT COUNT(*) FROM (SELECT pessoa_id FROM vd_caso_pessoas WHERE papel='mulher_atendida' "
            "GROUP BY pessoa_id HAVING COUNT(DISTINCT caso_id) > 1)").fetchone()[0]
        ind["medidas_total"] = con.execute(
            f"SELECT COUNT(*) FROM vd_medidas_protetivas WHERE caso_id IN ({marcas})", ids_casos).fetchone()[0]
        ind["medidas_por_situacao"] = con.execute(
            f"SELECT situacao, COUNT(*) c FROM vd_medidas_protetivas WHERE caso_id IN ({marcas}) "
            f"GROUP BY situacao ORDER BY c DESC", ids_casos).fetchall()
        ind["descumprimentos_total"] = con.execute(
            f"SELECT COUNT(*) FROM vd_descumprimentos dc "
            f"JOIN vd_medidas_protetivas mp ON mp.id = dc.medida_id WHERE mp.caso_id IN ({marcas})",
            ids_casos).fetchone()[0]
        ind["diligencias_total"] = con.execute(
            f"SELECT COUNT(*) FROM vd_diligencias WHERE caso_id IN ({marcas})", ids_casos).fetchone()[0]
        ind["diligencias_vencidas"] = con.execute(
            f"SELECT COUNT(*) FROM vd_diligencias WHERE caso_id IN ({marcas}) AND prazo < ? "
            f"AND situacao IN ({','.join('?' for _ in VD_SITUACOES_DILIGENCIA_ABERTAS)})",
            ids_casos + [agora()[:10]] + list(VD_SITUACOES_DILIGENCIA_ABERTAS)).fetchone()[0]
        ind["encaminhamentos_por_instituicao"] = con.execute(
            f"SELECT instituicao, COUNT(*) c FROM vd_encaminhamentos WHERE caso_id IN ({marcas}) "
            f"AND instituicao IS NOT NULL GROUP BY instituicao ORDER BY c DESC LIMIT 10", ids_casos).fetchall()
    else:
        for chave in ("formas_violencia", "medidas_por_situacao", "encaminhamentos_por_instituicao"):
            ind[chave] = []
        for chave in ("reincidencia_mulheres", "medidas_total", "descumprimentos_total",
                      "diligencias_total", "diligencias_vencidas"):
            ind[chave] = 0
    con.close()
    return ind


def pagina_painel_gerencial(usuario, csrf, filtros, ind):
    def tabela_contagem(linhas, rotulo_col, mapa_rotulo=None):
        if not linhas:
            return '<p class="suave">Sem dados no período/filtro selecionado.</p>'
        itens = ""
        for r in linhas:
            chave = r[0]
            rotulo = (mapa_rotulo or {}).get(chave, chave) if mapa_rotulo else chave
            itens += f"<tr><td>{e(rotulo)}</td><td>{r[1]}</td></tr>"
        return f'<table><thead><tr><th>{e(rotulo_col)}</th><th>Casos</th></tr></thead><tbody>{itens}</tbody></table>'

    corpo = f"""
    <div class="cab"><h1>Painel gerencial — Violência Doméstica</h1></div>
    <p class="suave"><a href="/vd">« Voltar aos casos</a> · <a href="/vd/painel">Ver painel operacional</a>
    · <a onclick="window.print()" href="#" style="cursor:pointer">Imprimir este painel</a></p>
    <p class="aviso">Indicadores sempre agregados — este painel nunca soma ou classifica por
    servidor individual, apenas por período, município, situação e tipo de violência.</p>
    <form method="get" action="/vd/painel-gerencial" class="painel" style="grid-template-columns:1fr 1fr 1fr auto">
      <input name="municipio" value="{e(filtros.get('municipio',''))}" placeholder="Filtrar por município">
      <input type="date" name="data_de" value="{e(filtros.get('data_de',''))}" placeholder="De">
      <input type="date" name="data_ate" value="{e(filtros.get('data_ate',''))}" placeholder="Até">
      <button class="botao">Filtrar</button>
    </form>
    <div class="cartoes">
      <div class="cartao"><h2>Total de casos</h2><p style="font-size:2rem;font-weight:700;margin:0">{ind['total_casos']}</p>
        <p class="suave">Mulheres com mais de um caso no sistema: {ind['reincidencia_mulheres']}</p></div>
      <div class="cartao"><h2>Casos por situação</h2>
        {tabela_contagem(ind['por_situacao'], 'Situação', VD_SITUACAO_LABEL)}</div>
      <div class="cartao"><h2>Casos por mês (últimos 12)</h2>{tabela_contagem(ind['por_mes'], 'Mês')}</div>
      <div class="cartao"><h2>Casos por município</h2>{tabela_contagem(ind['por_municipio'], 'Município')}</div>
      <div class="cartao"><h2>Formas de violência</h2>{tabela_contagem(ind['formas_violencia'], 'Forma')}</div>
      <div class="cartao"><h2>Medidas protetivas ({ind['medidas_total']})</h2>
        {tabela_contagem(ind['medidas_por_situacao'], 'Situação', VD_SITUACAO_MEDIDA_LABEL)}
        <p class="suave" style="margin-top:.5rem">Descumprimentos registrados: {ind['descumprimentos_total']}</p></div>
      <div class="cartao"><h2>Diligências</h2>
        <p>Total: {ind['diligencias_total']} · Vencidas: {ind['diligencias_vencidas']}</p></div>
      <div class="cartao"><h2>Encaminhamentos por instituição</h2>
        {tabela_contagem(ind['encaminhamentos_por_instituicao'], 'Instituição')}</div>
    </div>"""
    return pagina("Painel gerencial", corpo, usuario)


# ----------------------------------------------------------------------------
# Relatório individual do caso (impressão via navegador)
# ----------------------------------------------------------------------------

def pagina_relatorio_caso(usuario, caso, pessoas_vinculadas, tipos_violencia, marcadores,
                          medidas, fonar_resumo, diligencias, encaminhamentos, nomes_usuarios):
    marca_dagua = ""
    if caso["nivel_sigilo"] != "normal":
        marca_dagua = f'<div class="marca-dagua">{e(VD_SIGILO_LABEL.get(caso["nivel_sigilo"]).upper())}</div>'

    linhas_pessoas = "".join(
        f"<tr><td>{e(VD_PAPEL_LABEL.get(p['papel'], p['papel']))}</td><td>{e(p['nome'])}</td></tr>"
        for p in pessoas_vinculadas)
    bloco_pessoas = (f"<table><thead><tr><th>Papel</th><th>Nome</th></tr></thead>"
                     f"<tbody>{linhas_pessoas}</tbody></table>" if pessoas_vinculadas
                     else '<p class="suave">Nenhuma pessoa vinculada.</p>')

    bloco_violencia = (f"<p><strong>Formas de violência:</strong> {e(', '.join(tipos_violencia)) or 'não caracterizadas'}</p>"
                       f"<p><strong>Marcadores operacionais:</strong> {e(', '.join(marcadores)) or 'nenhum registrado'}</p>")

    linhas_medidas = "".join(
        f"<tr><td>#{m['id']}</td><td>{e(VD_SITUACAO_MEDIDA_LABEL.get(m['situacao'], m['situacao']))}</td>"
        f"<td>{e(m['numero_processo']) or '—'}</td>"
        f"<td>{'Sim' if m['tem_descumprimento_aberto'] else 'Não'}</td></tr>"
        for m in medidas)
    bloco_medidas = (f"<table><thead><tr><th>Nº</th><th>Situação</th><th>Processo</th>"
                     f"<th>Descumprimento em aberto</th></tr></thead><tbody>{linhas_medidas}</tbody></table>"
                     if medidas else '<p class="suave">Nenhuma medida protetiva registrada.</p>')

    linhas_fonar = "".join(
        f"<tr><td>{fmt_data(f['data_hora']) if ':' in str(f['data_hora'] or '') else e(f['data_hora'])}</td>"
        f"<td>{e(f['aplicador_nome']) or '—'}</td><td>{f['n_fatores']}</td></tr>"
        for f in fonar_resumo)
    bloco_fonar = (f"<table><thead><tr><th>Data</th><th>Aplicador</th><th>Fatores de atenção</th></tr></thead>"
                  f"<tbody>{linhas_fonar}</tbody></table>" if fonar_resumo
                  else '<p class="suave">Nenhuma aplicação do FONAR registrada.</p>')

    linhas_dilig = "".join(
        f"<tr><td>{e(dl['descricao'])}</td>"
        f"<td>{e(VD_SITUACAO_DILIGENCIA_LABEL.get(dl['situacao'], dl['situacao']))}</td>"
        f"<td>{e(dl['prazo']) or '—'}</td></tr>" for dl in diligencias)
    bloco_dilig = (f"<table><thead><tr><th>Descrição</th><th>Situação</th><th>Prazo</th></tr></thead>"
                  f"<tbody>{linhas_dilig}</tbody></table>" if diligencias
                  else '<p class="suave">Nenhuma diligência registrada.</p>')

    linhas_enc = "".join(
        f"<tr><td>{e(enc['instituicao']) or '—'}</td>"
        f"<td>{e(VD_SITUACAO_ENCAMINHAMENTO_LABEL.get(enc['situacao'], enc['situacao'])) or '—'}</td></tr>"
        for enc in encaminhamentos)
    bloco_enc = (f"<table><thead><tr><th>Instituição</th><th>Situação</th></tr></thead>"
                f"<tbody>{linhas_enc}</tbody></table>" if encaminhamentos
                else '<p class="suave">Nenhum encaminhamento registrado.</p>')

    agora_emissao = agora()

    corpo = f"""
    {marca_dagua}
    <div class="cabecalho-relatorio">
      <div><span class="sigla" style="color:var(--ouro)">SIRIO</span>
        <div class="suave">Relatório individual de caso — Módulo Violência Doméstica</div></div>
      <div style="text-align:right" class="suave">
        Emitido em {fmt_data(agora_emissao)}<br>Por: {e(usuario['nome'])}</div>
    </div>
    <div class="acoes" style="justify-content:flex-start;margin-bottom:1rem">
      <a class="botao fantasma" href="/vd/{caso['id']}">« Voltar ao caso</a>
      <a class="botao fantasma" href="#" onclick="window.print();return false;">Imprimir / salvar em PDF</a>
    </div>
    <h1>Caso #{caso['id']}{' — CONFIDENCIAL' if caso['nivel_sigilo'] != 'normal' else ''}</h1>
    <div class="cartao"><h2>Identificação</h2>
      {li_campo('REDS/BO', caso['numero_reds'])}{li_campo('Inquérito policial', caso['numero_inquerito'])}
      {li_campo('Processo judicial', caso['numero_processo_judicial'])}
      {li_campo('Medida protetiva', caso['numero_medida_protetiva'])}
      {li_campo('Município', caso['municipio'])}{li_campo('Situação', VD_SITUACAO_LABEL.get(caso['situacao']))}
      {li_campo('Nível de sigilo', VD_SIGILO_LABEL.get(caso['nivel_sigilo']))}
      {li_campo('Servidor responsável', nomes_usuarios.get(caso['servidor_responsavel_id'], '—'))}</div>
    <div class="cartao"><h2>Dados do fato</h2>
      {li_campo('Data/hora do fato', caso['data_hora_fato'])}{li_campo('Local do fato', caso['local_fato'])}
      {li_campo('Descrição', caso['descricao_fato'])}</div>
    <div class="cartao"><h2>Pessoas envolvidas</h2>{bloco_pessoas}</div>
    <div class="cartao"><h2>Caracterização da violência</h2>{bloco_violencia}</div>
    <div class="cartao"><h2>FONAR — aplicações</h2>{bloco_fonar}</div>
    <div class="cartao"><h2>Medidas protetivas</h2>{bloco_medidas}</div>
    <div class="cartao"><h2>Diligências</h2>{bloco_dilig}</div>
    <div class="cartao"><h2>Encaminhamentos</h2>{bloco_enc}</div>
    <div class="rodape-relatorio">
      <span>SIRIO — Sistema Interno de Registro de Investigados e Organizações · Versão {VERSAO}</span>
      <span>Documento {'SIGILOSO — uso restrito' if caso['nivel_sigilo'] != 'normal' else 'de uso interno'}.
      Emissão registrada na auditoria do sistema.</span>
    </div>"""
    return pagina(f"Relatório — Caso #{caso['id']}", corpo, usuario)
