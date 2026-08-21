"""Módulo SIRIO — Violência Doméstica: Diligências, Encaminhamentos e
Acompanhamento/Contato Seguro (Onda 4).

Como em todo o módulo, "lembrete" e "alerta" aqui significam sempre uma
marcação bem visível dentro do próprio sistema (selo, cor, texto) — o SIRIO
não envia e-mail nem notificação por fora dele, então isso só ajuda quem
efetivamente abrir o caso ou a listagem.
"""
from sirio_core import *  # noqa: F401,F403
from sirio_vd_core import *  # noqa: F401,F403


def diligencia_vencida(dilig):
    if not dilig["prazo"] or dilig["situacao"] not in VD_SITUACOES_DILIGENCIA_ABERTAS:
        return False
    return dilig["prazo"] < agora()[:10]


# ----------------------------------------------------------------------------
# Diligências
# ----------------------------------------------------------------------------

def pagina_diligencia_nova(usuario, csrf, caso, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    con.close()
    opcoes_usuarios = '<option value="">Sem responsável definido</option>' + "".join(
        f'<option value="{u["id"]}">{e(u["nome"])}</option>' for u in usuarios)

    corpo = f"""
    <div class="cab"><h1>Nova diligência</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <form method="post" action="/vd/{caso['id']}/diligencias/nova">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Diligência</legend><div class="grade">
        <label class="span2">Descrição<textarea name="descricao" rows="2" required></textarea></label>
        <label>Tipo<select name="tipo"><option value="">Selecionar…</option>{opcoes(lista_ativa('vd_tipo_diligencia'), '')}</select></label>
        <label>Prioridade<select name="prioridade">{opcoes(VD_PRIORIDADES_DILIGENCIA, 'media')}</select></label>
        <label>Responsável<select name="responsavel_id">{opcoes_usuarios}</select></label>
        <label>Unidade responsável<input name="unidade_responsavel"></label>
        <label>Prazo<input type="date" name="prazo"></label>
      </div></fieldset>
      <fieldset><legend>Observações</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="2"></textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar diligência</button>
      </div>
    </form>"""
    return pagina("Nova diligência", corpo, usuario)


def pagina_diligencia_editar(usuario, csrf, dilig, caso, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    con.close()
    opcoes_usuarios = '<option value="">Sem responsável definido</option>' + "".join(
        f'<option value="{u["id"]}"{" selected" if u["id"]==dilig["responsavel_id"] else ""}>{e(u["nome"])}</option>'
        for u in usuarios)

    def v(nome):
        return e(dilig[nome]) if dilig[nome] else ""

    corpo = f"""
    <div class="cab"><h1>Editar diligência #{dilig['id']}</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <form method="post" action="/vd/diligencias/{dilig['id']}/editar">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Diligência</legend><div class="grade">
        <label class="span2">Descrição<textarea name="descricao" rows="2" required>{v('descricao')}</textarea></label>
        <label>Tipo<select name="tipo">{opcoes(lista_ativa_com_atual('vd_tipo_diligencia', dilig['tipo']), dilig['tipo'])}</select></label>
        <label>Prioridade<select name="prioridade">{opcoes(VD_PRIORIDADES_DILIGENCIA, dilig['prioridade'])}</select></label>
        <label>Responsável<select name="responsavel_id">{opcoes_usuarios}</select></label>
        <label>Unidade responsável<input name="unidade_responsavel" value="{v('unidade_responsavel')}"></label>
        <label>Prazo<input type="date" name="prazo" value="{v('prazo')}"></label>
        <label>Situação<select name="situacao">{opcoes(VD_SITUACOES_DILIGENCIA, dilig['situacao'])}</select></label>
        <label>Data de conclusão<input type="date" name="data_conclusao" value="{v('data_conclusao')}"></label>
      </div></fieldset>
      <fieldset><legend>Resultado</legend><div class="grade">
        <label class="span2">Resultado<textarea name="resultado" rows="2">{v('resultado')}</textarea></label>
        <label class="span2">Observações<textarea name="observacoes" rows="2">{v('observacoes')}</textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar alterações</button>
      </div>
    </form>"""
    return pagina("Editar diligência", corpo, usuario)


def cartao_diligencias(diligencias, caso_id, pode_editar):
    botao_novo = f'<a class="botao fantasma" href="/vd/{caso_id}/diligencias/nova">Nova diligência</a>' if pode_editar else ""
    if not diligencias:
        return (f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
                f'<h2 style="margin:0">Diligências</h2>{botao_novo}</div>'
                f'<p class="suave">Nenhuma diligência cadastrada ainda.</p></div>')
    linhas = ""
    for dl in diligencias:
        vencida = diligencia_vencida(dl)
        selo_prazo = ' <span class="selo s-preso">Vencida</span>' if vencida else ""
        editar = f'<a href="/vd/diligencias/{dl["id"]}/editar">Editar</a>' if pode_editar else ""
        linhas += f"""<tr>
          <td>{e(dl['descricao'])}</td>
          <td>{e(dl['tipo']) or '—'}</td>
          <td>{e(VD_PRIORIDADE_DILIGENCIA_LABEL.get(dl['prioridade'], dl['prioridade'])) or '—'}</td>
          <td>{e(dl['prazo']) or '—'}{selo_prazo}</td>
          <td><span class="pill p-em_verificacao">{e(VD_SITUACAO_DILIGENCIA_LABEL.get(dl['situacao'], dl['situacao']))}</span></td>
          <td>{editar}</td></tr>"""
    tabela = f"""<table><thead><tr><th>Descrição</th><th>Tipo</th><th>Prioridade</th>
        <th>Prazo</th><th>Situação</th><th></th></tr></thead><tbody>{linhas}</tbody></table>"""
    return (f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
            f'<h2 style="margin:0">Diligências ({len(diligencias)})</h2>{botao_novo}</div>{tabela}</div>')


# ----------------------------------------------------------------------------
# Encaminhamentos à rede de proteção
# ----------------------------------------------------------------------------

def pagina_encaminhamento_novo(usuario, csrf, caso, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    con.close()
    opcoes_usuarios = '<option value="">Sem responsável definido</option>' + "".join(
        f'<option value="{u["id"]}"{" selected" if u["id"]==usuario["id"] else ""}>{e(u["nome"])}</option>'
        for u in usuarios)

    corpo = f"""
    <div class="cab"><h1>Novo encaminhamento</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <p class="aviso">Encaminhe apenas as informações necessárias para a finalidade — evite expor à
    rede de proteção dados do caso que não sejam pertinentes ao serviço solicitado.</p>
    <form method="post" action="/vd/{caso['id']}/encaminhamentos/novo">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Encaminhamento</legend><div class="grade">
        <label>Instituição<select name="instituicao">{opcoes(lista_ativa('vd_instituicao_encaminhamento'), '')}</select></label>
        <label>Serviço<input name="servico"></label>
        <label>Profissional ou setor<input name="profissional_setor"></label>
        <label>Data<input type="date" name="data"></label>
        <label class="span2">Motivo<textarea name="motivo" rows="2"></textarea></label>
        <label>Documento enviado?<select name="documento_enviado">{opcoes_sim_nao("")}</select></label>
        <label>Responsável<select name="responsavel_id">{opcoes_usuarios}</select></label>
      </div></fieldset>
      <fieldset><legend>Observações</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="2"></textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar encaminhamento</button>
      </div>
      <p class="suave" style="text-align:right;margin-top:.3rem">Confirmação de recebimento e
      retorno da instituição são preenchidos depois, editando este encaminhamento.</p>
    </form>"""
    return pagina("Novo encaminhamento", corpo, usuario)


def pagina_encaminhamento_editar(usuario, csrf, enc, caso, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome):
        return e(enc[nome]) if enc[nome] else ""

    corpo = f"""
    <div class="cab"><h1>Editar encaminhamento #{enc['id']}</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <form method="post" action="/vd/encaminhamentos/{enc['id']}/editar">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Encaminhamento</legend><div class="grade">
        <label>Instituição<select name="instituicao">{opcoes(lista_ativa_com_atual('vd_instituicao_encaminhamento', enc['instituicao']), enc['instituicao'])}</select></label>
        <label>Serviço<input name="servico" value="{v('servico')}"></label>
        <label>Profissional ou setor<input name="profissional_setor" value="{v('profissional_setor')}"></label>
        <label>Data<input type="date" name="data" value="{v('data')}"></label>
        <label class="span2">Motivo<textarea name="motivo" rows="2">{v('motivo')}</textarea></label>
        <label>Documento enviado?<select name="documento_enviado">{opcoes_sim_nao(enc['documento_enviado'])}</select></label>
        <label>Situação<select name="situacao">{opcoes(VD_SITUACOES_ENCAMINHAMENTO, enc['situacao'])}</select></label>
      </div></fieldset>
      <fieldset><legend>Retorno da instituição</legend><div class="grade">
        <label>Confirmação de recebimento?<select name="confirmacao_recebimento">{opcoes_sim_nao(enc['confirmacao_recebimento'])}</select></label>
        <label class="span2">Retorno recebido<textarea name="retorno_recebido" rows="2">{v('retorno_recebido')}</textarea></label>
      </div></fieldset>
      <fieldset><legend>Observações</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="2">{v('observacoes')}</textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar alterações</button>
      </div>
    </form>"""
    return pagina("Editar encaminhamento", corpo, usuario)


def cartao_encaminhamentos(encaminhamentos, caso_id, pode_editar):
    botao_novo = f'<a class="botao fantasma" href="/vd/{caso_id}/encaminhamentos/novo">Novo encaminhamento</a>' if pode_editar else ""
    if not encaminhamentos:
        return (f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
                f'<h2 style="margin:0">Encaminhamentos</h2>{botao_novo}</div>'
                f'<p class="suave">Nenhum encaminhamento registrado ainda.</p></div>')
    linhas = ""
    for enc in encaminhamentos:
        editar = f'<a href="/vd/encaminhamentos/{enc["id"]}/editar">Editar</a>' if pode_editar else ""
        linhas += f"""<tr>
          <td>{e(enc['instituicao']) or '—'}</td><td>{e(enc['servico']) or '—'}</td>
          <td>{e(enc['data']) or '—'}</td>
          <td><span class="pill p-em_verificacao">{e(VD_SITUACAO_ENCAMINHAMENTO_LABEL.get(enc['situacao'], enc['situacao'])) or '—'}</span></td>
          <td>{editar}</td></tr>"""
    tabela = f"""<table><thead><tr><th>Instituição</th><th>Serviço</th><th>Data</th>
        <th>Situação</th><th></th></tr></thead><tbody>{linhas}</tbody></table>"""
    return (f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
            f'<h2 style="margin:0">Encaminhamentos ({len(encaminhamentos)})</h2>{botao_novo}</div>{tabela}</div>')


# ----------------------------------------------------------------------------
# Acompanhamento e contato seguro
# ----------------------------------------------------------------------------

def _bloco_lembrete_contato_seguro(dados_mulher):
    """Antes de mostrar telefone ou permitir contato, exibe as restrições de
    contato seguro já registradas para a mulher atendida (se houver)."""
    if not dados_mulher:
        return ('<p class="aviso">Nenhum dado de contato seguro foi preenchido para esta pessoa ainda '
               '(seção "Dados específicos" do caso). Confirme com cautela antes de ligar ou enviar mensagem.</p>')
    avisos = []
    if dados_mulher["telefone_controlado_agressor"] == "sim":
        avisos.append('<strong>O telefone foi indicado como controlado/acessado pelo suposto agressor.</strong>')
    if dados_mulher["autoriza_ligacao"] == "nao":
        avisos.append("A mulher NÃO autorizou contato por ligação.")
    if dados_mulher["autoriza_mensagem"] == "nao":
        avisos.append("A mulher NÃO autorizou contato por mensagem.")
    partes = [
        f"Telefone seguro: {e(dados_mulher['telefone_seguro']) or 'não informado'}",
        f"Forma mais segura de contato: {e(dados_mulher['forma_contato_segura']) or 'não informada'}",
        f"Melhor horário: {e(dados_mulher['melhor_horario_contato']) or 'não informado'}",
    ]
    if dados_mulher["palavras_proibidas_mensagem"]:
        partes.append(f"Não usar em mensagens: {e(dados_mulher['palavras_proibidas_mensagem'])}")
    classe = "erro" if avisos else "aviso"
    texto_avisos = (" ".join(avisos) + " ") if avisos else ""
    return f'<div class="{classe}"><strong>Antes de ligar ou enviar mensagem:</strong> {texto_avisos}{" · ".join(partes)}</div>'


def pagina_acompanhamento_novo(usuario, csrf, caso, dados_mulher, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    con.close()
    opcoes_usuarios = "".join(
        f'<option value="{u["id"]}"{" selected" if u["id"]==usuario["id"] else ""}>{e(u["nome"])}</option>'
        for u in usuarios)

    corpo = f"""
    <div class="cab"><h1>Novo acompanhamento</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    {_bloco_lembrete_contato_seguro(dados_mulher)}
    <form method="post" action="/vd/{caso['id']}/acompanhamentos/novo">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Contato</legend><div class="grade">
        <label>Data prevista<input type="date" name="data_prevista"></label>
        <label>Data realizada (se já ocorreu)<input type="date" name="data_realizada"></label>
        <label>Responsável<select name="responsavel_id">{opcoes_usuarios}</select></label>
        <label>Meio de contato<input name="meio_contato" placeholder="Ex.: telefone, visita, presencial na unidade"></label>
        <label>Contato seguro confirmado?<select name="contato_seguro_confirmado">{opcoes_sim_nao("")}</select></label>
      </div></fieldset>
      <fieldset><legend>Resultado</legend><div class="grade">
        <label class="span2">Resultado do contato<textarea name="resultado" rows="2"></textarea></label>
        <label class="span2">Situação atual informada pela mulher<textarea name="situacao_atual_informada" rows="2"></textarea></label>
        <label class="span2">Novos fatos relatados<textarea name="novos_fatos" rows="2"></textarea></label>
        <label>Descumprimento relatado?<select name="descumprimento_relatado">{opcoes_sim_nao("")}</select></label>
        <label>Necessita nova providência?<select name="necessita_providencia">{opcoes_sim_nao("")}</select></label>
        <label>Necessita reavaliação (FONAR)?<select name="necessita_reavaliacao">{opcoes_sim_nao("")}</select></label>
      </div></fieldset>
      <fieldset><legend>Observações</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="2"></textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar acompanhamento</button>
      </div>
    </form>"""
    return pagina("Novo acompanhamento", corpo, usuario)


def pagina_acompanhamento_editar(usuario, csrf, contato, caso, dados_mulher, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome):
        return e(contato[nome]) if contato[nome] else ""

    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    con.close()
    opcoes_usuarios = "".join(
        f'<option value="{u["id"]}"{" selected" if u["id"]==contato["responsavel_id"] else ""}>{e(u["nome"])}</option>'
        for u in usuarios)

    corpo = f"""
    <div class="cab"><h1>Editar acompanhamento #{contato['id']}</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    {_bloco_lembrete_contato_seguro(dados_mulher)}
    <form method="post" action="/vd/acompanhamentos/{contato['id']}/editar">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Contato</legend><div class="grade">
        <label>Data prevista<input type="date" name="data_prevista" value="{v('data_prevista')}"></label>
        <label>Data realizada<input type="date" name="data_realizada" value="{v('data_realizada')}"></label>
        <label>Responsável<select name="responsavel_id">{opcoes_usuarios}</select></label>
        <label>Meio de contato<input name="meio_contato" value="{v('meio_contato')}"></label>
        <label>Contato seguro confirmado?<select name="contato_seguro_confirmado">{opcoes_sim_nao(contato['contato_seguro_confirmado'])}</select></label>
      </div></fieldset>
      <fieldset><legend>Resultado</legend><div class="grade">
        <label class="span2">Resultado do contato<textarea name="resultado" rows="2">{v('resultado')}</textarea></label>
        <label class="span2">Situação atual informada pela mulher<textarea name="situacao_atual_informada" rows="2">{v('situacao_atual_informada')}</textarea></label>
        <label class="span2">Novos fatos relatados<textarea name="novos_fatos" rows="2">{v('novos_fatos')}</textarea></label>
        <label>Descumprimento relatado?<select name="descumprimento_relatado">{opcoes_sim_nao(contato['descumprimento_relatado'])}</select></label>
        <label>Necessita nova providência?<select name="necessita_providencia">{opcoes_sim_nao(contato['necessita_providencia'])}</select></label>
        <label>Necessita reavaliação (FONAR)?<select name="necessita_reavaliacao">{opcoes_sim_nao(contato['necessita_reavaliacao'])}</select></label>
      </div></fieldset>
      <fieldset><legend>Observações</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="2">{v('observacoes')}</textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar alterações</button>
      </div>
    </form>"""
    return pagina("Editar acompanhamento", corpo, usuario)


def cartao_acompanhamentos(contatos, caso_id, pode_editar):
    botao_novo = f'<a class="botao fantasma" href="/vd/{caso_id}/acompanhamentos/novo">Novo acompanhamento</a>' if pode_editar else ""
    if not contatos:
        return (f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
                f'<h2 style="margin:0">Acompanhamento e contato</h2>{botao_novo}</div>'
                f'<p class="suave">Nenhum acompanhamento registrado ainda.</p></div>')
    hoje = agora()[:10]
    linhas = ""
    for c in contatos:
        pendente = bool(c["data_prevista"] and not c["data_realizada"] and c["data_prevista"] <= hoje)
        selo = ' <span class="selo s-preso">Pendente</span>' if pendente else ""
        editar = f'<a href="/vd/acompanhamentos/{c["id"]}/editar">Editar</a>' if pode_editar else ""
        linhas += f"""<tr>
          <td>{e(c['data_prevista']) or '—'}{selo}</td>
          <td>{e(c['data_realizada']) or '—'}</td>
          <td>{e(c['meio_contato']) or '—'}</td>
          <td>{'Sim' if c['descumprimento_relatado']=='sim' else ('Não' if c['descumprimento_relatado']=='nao' else '—')}</td>
          <td>{editar}</td></tr>"""
    tabela = f"""<table><thead><tr><th>Data prevista</th><th>Data realizada</th>
        <th>Meio</th><th>Descumprimento relatado</th><th></th></tr></thead><tbody>{linhas}</tbody></table>"""
    return (f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
            f'<h2 style="margin:0">Acompanhamento e contato ({len(contatos)})</h2>{botao_novo}</div>{tabela}</div>')
