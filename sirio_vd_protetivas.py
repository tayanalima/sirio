"""Módulo SIRIO — Violência Doméstica: Medidas Protetivas e Descumprimentos (Onda 3).

Uma medida protetiva pode ter vários itens individualizados (afastamento do
lar, proibição de aproximação etc.), cada um com sua própria situação e
vigência — e vários registros de descumprimento ao longo do tempo, nenhum
deles apaga ou substitui os anteriores.

Ao registrar um possível descumprimento, o sistema:
  - deixa isso bem visível no caso (selo vermelho, tanto na listagem de
    casos quanto na tela do caso), já que não há aqui um mecanismo de
    e-mail ou notificação push — o "alerta" é sempre dentro do próprio
    sistema, para quem tiver acesso ao caso;
  - registra o evento na linha do tempo do caso.
"""
from sirio_core import *  # noqa: F401,F403
from sirio_vd_core import *  # noqa: F401,F403


def pagina_medida_nova(usuario, csrf, caso, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    corpo = f"""
    <div class="cab"><h1>Nova medida protetiva</h1></div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <form method="post" action="/vd/{caso['id']}/medidas/nova">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Solicitação</legend><div class="grade">
        <label>Data da solicitação<input type="date" name="data_solicitacao"></label>
        <label>Autoridade solicitante<input name="autoridade_solicitante"></label>
        <label>Número do processo<input name="numero_processo"></label>
        <label>Órgão judicial<input name="orgao_judicial"></label>
        <label>Situação inicial<select name="situacao">{opcoes(VD_SITUACOES_MEDIDA, "em_elaboracao")}</select></label>
      </div></fieldset>
      <fieldset><legend>Observações</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="3"></textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/{caso['id']}">Cancelar</a>
        <button class="botao">Salvar medida protetiva</button>
      </div>
      <p class="suave" style="text-align:right;margin-top:.3rem">Decisão, intimações, vigência e os
      itens individualizados (afastamento do lar, proibição de aproximação etc.) são preenchidos
      depois, na tela da própria medida.</p>
    </form>"""
    return pagina("Nova medida protetiva", corpo, usuario)


def pagina_medida_editar(usuario, csrf, medida, caso, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome):
        return e(medida[nome]) if medida[nome] else ""

    corpo = f"""
    <div class="cab"><h1>Editar medida protetiva #{medida['id']}</h1></div>
    <p class="suave"><a href="/vd/medidas/{medida['id']}">« Voltar à medida</a></p>
    <form method="post" action="/vd/medidas/{medida['id']}/editar">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>Solicitação</legend><div class="grade">
        <label>Data da solicitação<input type="date" name="data_solicitacao" value="{v('data_solicitacao')}"></label>
        <label>Autoridade solicitante<input name="autoridade_solicitante" value="{v('autoridade_solicitante')}"></label>
        <label>Número do processo<input name="numero_processo" value="{v('numero_processo')}"></label>
        <label>Órgão judicial<input name="orgao_judicial" value="{v('orgao_judicial')}"></label>
        <label>Situação<select name="situacao">{opcoes(VD_SITUACOES_MEDIDA, medida['situacao'])}</select></label>
      </div></fieldset>
      <fieldset><legend>Decisão</legend><div class="grade">
        <label>Data da decisão<input type="date" name="data_decisao" value="{v('data_decisao')}"></label>
        <label class="span2">Resultado<input name="resultado" value="{v('resultado')}"></label>
      </div></fieldset>
      <fieldset><legend>Intimações e vigência</legend><div class="grade">
        <label>Data de ciência da mulher<input type="date" name="data_ciencia_mulher" value="{v('data_ciencia_mulher')}"></label>
        <label>Data de intimação do autor<input type="date" name="data_intimacao_autor" value="{v('data_intimacao_autor')}"></label>
        <label>Responsável pela intimação<input name="responsavel_intimacao" value="{v('responsavel_intimacao')}"></label>
        <label>Forma de intimação<input name="forma_intimacao" value="{v('forma_intimacao')}"></label>
        <label>Vigência<input name="vigencia" value="{v('vigencia')}" placeholder="Ex.: 6 meses, a contar da intimação"></label>
        <label>Data de revisão<input type="date" name="data_revisao" value="{v('data_revisao')}"></label>
        <label>Data de encerramento<input type="date" name="data_encerramento" value="{v('data_encerramento')}"></label>
      </div></fieldset>
      <fieldset><legend>Observações</legend><div class="grade">
        <label class="span2"><textarea name="observacoes" rows="3">{v('observacoes')}</textarea></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/medidas/{medida['id']}">Cancelar</a>
        <button class="botao">Salvar alterações</button>
      </div>
    </form>"""
    return pagina("Editar medida protetiva", corpo, usuario)


def pagina_medida_detalhe(usuario, csrf, medida, itens, descumprimentos, caso, nomes_usuarios):
    pode_editar = usuario["perfil"] in ("admin", "analista")

    tem_descumprimento_aberto = any(
        d["situacao_apuracao"] in (None, "registrado", "em_apuracao") for d in descumprimentos)
    selo_descumprimento = ('<span class="selo s-preso">DESCUMPRIMENTO EM ABERTO</span>'
                           if tem_descumprimento_aberto else "")

    acoes = ""
    if pode_editar:
        acoes = f"""<div class="acoes" style="margin:0">
          <a class="botao fantasma" href="/vd/medidas/{medida['id']}/editar">Editar</a>
          <a class="botao perigo" href="/vd/medidas/{medida['id']}/descumprimento/novo">Registrar descumprimento</a>
        </div>"""

    # Itens individualizados
    linhas_itens = ""
    for it in itens:
        excluir_it = ""
        if pode_editar:
            excluir_it = f"""<form method="post" action="/vd/itens-medida/{it['id']}/excluir" style="display:inline"
              onsubmit="return confirm('Remover este item da medida?')">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao perigo mini">Remover</button></form>"""
        linhas_itens += f"""<tr>
          <td>{e(it['tipo_medida'])}</td>
          <td><span class="pill p-em_verificacao">{e(VD_SITUACAO_ITEM_LABEL.get(it['situacao'], it['situacao']))}</span></td>
          <td>{e(it['data_inicial']) or '—'}</td><td>{e(it['data_final']) or '—'}</td>
          <td>{e(it['detalhes']) or '—'}</td><td>{excluir_it}</td></tr>"""
    tabela_itens = (f"""<table><thead><tr><th>Medida</th><th>Situação</th><th>Início</th>
        <th>Fim</th><th>Detalhes</th><th></th></tr></thead>
        <tbody>{linhas_itens}</tbody></table>""" if itens
        else '<p class="suave">Nenhum item individualizado cadastrado ainda.</p>')
    form_item = ""
    if pode_editar:
        form_item = f"""
        <form method="post" action="/vd/medidas/{medida['id']}/itens" class="grade" style="margin-top:1rem">
          <input type="hidden" name="csrf" value="{e(csrf)}">
          <label>Tipo de medida<select name="tipo_medida">{opcoes(lista_ativa('vd_tipo_medida_protetiva'), '')}</select></label>
          <label>Situação<select name="situacao">{opcoes(VD_SITUACOES_ITEM_MEDIDA, 'vigente')}</select></label>
          <label>Data inicial<input type="date" name="data_inicial"></label>
          <label>Data final<input type="date" name="data_final"></label>
          <label class="span2">Detalhes<input name="detalhes" placeholder="Ex.: distância mínima de 300 metros"></label>
          <div class="acoes span2" style="justify-content:flex-start"><button class="botao fantasma">Adicionar item</button></div>
        </form>
        <p class="suave">Os tipos de medida são gerenciados pelo Administrador em Configurações
        ("Violência doméstica — Tipos de medida protetiva").</p>"""
    cartao_itens = f"""<div class="cartao"><h2>Itens individualizados</h2>{tabela_itens}{form_item}</div>"""

    # Descumprimentos
    itens_desc = ""
    for dc in descumprimentos:
        situacao_lbl = VD_SITUACAO_APURACAO_LABEL.get(dc["situacao_apuracao"], dc["situacao_apuracao"] or "Registrado")
        resumo = (f'{fmt_data(dc["data_hora"]) if ":" in str(dc["data_hora"] or "") else e(dc["data_hora"]) or "data não informada"} '
                 f'— {e(situacao_lbl)}')
        itens_desc += f"""<details style="margin-bottom:.6rem">
          <summary style="cursor:pointer;font-weight:600">{resumo}</summary>
          <div style="margin-top:.5rem">
            {li_campo('Local', dc['local'])}
            {li_campo('Forma do descumprimento', dc['forma'])}
            {li_campo('Relato', dc['relato'])}
            {li_campo('Provas apresentadas', dc['provas'])}
            {li_campo('Testemunhas', dc['testemunhas'])}
            {li_campo('Houve contato do suposto autor', 'Sim' if dc['contato_autor']=='sim' else ('Não' if dc['contato_autor']=='nao' else dc['contato_autor']))}
            {li_campo('Meio utilizado', dc['meio_utilizado'])}
            {li_campo('Aproximação física', 'Sim' if dc['aproximacao_fisica']=='sim' else ('Não' if dc['aproximacao_fisica']=='nao' else dc['aproximacao_fisica']))}
            {li_campo('Ameaça', 'Sim' if dc['ameaca']=='sim' else ('Não' if dc['ameaca']=='nao' else dc['ameaca']))}
            {li_campo('Agressão', 'Sim' if dc['agressao']=='sim' else ('Não' if dc['agressao']=='nao' else dc['agressao']))}
            {li_campo('Providências adotadas', dc['providencias'])}
            {li_campo('Número de procedimento relacionado', dc['numero_procedimento'])}
            {li_campo('Houve prisão', 'Sim' if dc['houve_prisao']=='sim' else ('Não' if dc['houve_prisao']=='nao' else dc['houve_prisao']))}
            {li_campo('Responsável pelo registro', nomes_usuarios.get(dc['responsavel_id'], '—'))}
            {li_campo('Situação da apuração', situacao_lbl)}
          </div>
        </details>"""
    cartao_descumprimentos = f"""<div class="cartao"><h2>Descumprimentos ({len(descumprimentos)})</h2>
      {itens_desc if descumprimentos else '<p class="suave">Nenhum descumprimento registrado — o que é uma boa notícia.</p>'}
      </div>"""

    corpo = f"""
    <div class="cab"><div><h1>Medida protetiva #{medida['id']}</h1>
      <div class="selos"><span class="pill p-em_verificacao">{e(VD_SITUACAO_MEDIDA_LABEL.get(medida['situacao'], medida['situacao']))}</span>{selo_descumprimento}</div></div>
      {acoes}</div>
    <p class="suave"><a href="/vd/{caso['id']}">« Voltar ao caso #{caso['id']}</a></p>
    <div class="cartoes">
      <div class="cartao"><h2>Solicitação</h2>
        {li_campo('Data da solicitação', medida['data_solicitacao'])}
        {li_campo('Autoridade solicitante', medida['autoridade_solicitante'])}
        {li_campo('Número do processo', medida['numero_processo'])}
        {li_campo('Órgão judicial', medida['orgao_judicial'])}</div>
      <div class="cartao"><h2>Decisão</h2>
        {li_campo('Data da decisão', medida['data_decisao'])}
        {li_campo('Resultado', medida['resultado'])}</div>
      <div class="cartao"><h2>Intimações e vigência</h2>
        {li_campo('Ciência da mulher', medida['data_ciencia_mulher'])}
        {li_campo('Intimação do autor', medida['data_intimacao_autor'])}
        {li_campo('Responsável pela intimação', medida['responsavel_intimacao'])}
        {li_campo('Forma de intimação', medida['forma_intimacao'])}
        {li_campo('Vigência', medida['vigencia'])}
        {li_campo('Data de revisão', medida['data_revisao'])}
        {li_campo('Data de encerramento', medida['data_encerramento'])}</div>
      <div class="cartao"><h2>Observações</h2>{li_campo('', medida['observacoes'])}</div>
    </div>
    {cartao_itens}
    {cartao_descumprimentos}"""
    return pagina(f"Medida protetiva #{medida['id']}", corpo, usuario)


def pagina_descumprimento_novo(usuario, csrf, medida, caso, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    con = conexao()
    usuarios = con.execute("SELECT id, nome FROM usuarios WHERE ativo=1 ORDER BY nome").fetchall()
    ocorrencias = con.execute("SELECT id, tipo_crime, data_fato FROM ocorrencias ORDER BY id DESC LIMIT 300").fetchall()
    con.close()
    opcoes_usuarios = "".join(
        f'<option value="{u["id"]}"{" selected" if u["id"]==usuario["id"] else ""}>{e(u["nome"])}</option>'
        for u in usuarios)
    dl_ocorrencias = "".join(
        f'<option value="{e(o["tipo_crime"] or "Ocorrência")} — {e(o["data_fato"]) or "sem data"} (#{o["id"]})" data-id="{o["id"]}">'
        for o in ocorrencias)

    corpo = f"""
    <div class="cab"><h1>Registrar descumprimento</h1></div>
    <p class="suave"><a href="/vd/medidas/{medida['id']}">« Voltar à medida #{medida['id']}</a></p>
    <p class="aviso">Ao salvar, este descumprimento fica visível de forma destacada na medida e no
    caso, e um evento é registrado na linha do tempo do caso — é a forma do SIRIO de "alertar" quem
    tem acesso a este caso, já que o sistema não envia e-mail nem notificação por fora dele.</p>
    <datalist id="dl_ocorrencias_desc">{dl_ocorrencias}</datalist>
    <form method="post" action="/vd/medidas/{medida['id']}/descumprimento/novo">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <fieldset><legend>O que aconteceu</legend><div class="grade">
        <label>Data e hora<input type="datetime-local" name="data_hora"></label>
        <label>Local<input name="local"></label>
        <label class="span2">Forma do descumprimento<input name="forma" placeholder="Ex.: ligação, aproximação, mensagem por terceiro"></label>
        <label class="span2">Relato<textarea name="relato" rows="3"></textarea></label>
        <label class="span2">Provas apresentadas<textarea name="provas" rows="2"></textarea></label>
        <label class="span2">Testemunhas<input name="testemunhas"></label>
      </div></fieldset>
      <fieldset><legend>Detalhes do contato</legend><div class="grade">
        <label>Houve contato do suposto autor?<select name="contato_autor">{opcoes_sim_nao("")}</select></label>
        <label>Meio utilizado<input name="meio_utilizado" placeholder="Ex.: telefone, presencial, redes sociais"></label>
        <label>Aproximação física?<select name="aproximacao_fisica">{opcoes_sim_nao("")}</select></label>
        <label>Ameaça?<select name="ameaca">{opcoes_sim_nao("")}</select></label>
        <label>Agressão?<select name="agressao">{opcoes_sim_nao("")}</select></label>
        <label>Houve prisão?<select name="houve_prisao">{opcoes_sim_nao("")}</select></label>
      </div></fieldset>
      <fieldset><legend>Providências e apuração</legend><div class="grade">
        <label class="span2">Providências adotadas<textarea name="providencias" rows="2"></textarea></label>
        <label class="span2">Ocorrência relacionada (se houver)
          <input list="dl_ocorrencias_desc" id="desc_oc_nome" placeholder="Digite para localizar">
          <input type="hidden" name="ocorrencia_id" id="desc_oc_id"></label>
        <label>Número de outro procedimento relacionado<input name="numero_procedimento"></label>
        <label>Responsável pelo registro<select name="responsavel_id">{opcoes_usuarios}</select></label>
        <label>Situação da apuração<select name="situacao_apuracao">{opcoes(VD_SITUACOES_APURACAO, "registrado")}</select></label>
      </div></fieldset>
      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="/vd/medidas/{medida['id']}">Cancelar</a>
        <button class="botao perigo">Registrar descumprimento</button>
      </div>
    </form>
    <script>
    document.getElementById('desc_oc_nome')?.addEventListener('input', function() {{
      var opt = document.querySelector('#dl_ocorrencias_desc option[value="' + this.value.replace(/"/g,'\\\\"') + '"]');
      document.getElementById('desc_oc_id').value = opt ? opt.getAttribute('data-id') : '';
    }});
    </script>"""
    return pagina("Registrar descumprimento", corpo, usuario)


def cartao_medidas_protetivas(medidas, caso_id, pode_editar):
    botao_nova = (f'<a class="botao fantasma" href="/vd/{caso_id}/medidas/nova">Nova medida protetiva</a>'
                 if pode_editar else "")
    if not medidas:
        return (f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
                f'<h2 style="margin:0">Medidas protetivas</h2>{botao_nova}</div>'
                f'<p class="suave">Nenhuma medida protetiva registrada ainda.</p></div>')
    linhas = ""
    for m in medidas:
        selo_desc = ' <span class="selo s-preso">Descumprimento</span>' if m["tem_descumprimento_aberto"] else ""
        linhas += f"""<tr>
          <td><a class="nomelink" href="/vd/medidas/{m['id']}">#{m['id']}</a></td>
          <td><span class="pill p-em_verificacao">{e(VD_SITUACAO_MEDIDA_LABEL.get(m['situacao'], m['situacao']))}</span>{selo_desc}</td>
          <td>{e(m['numero_processo']) or '—'}</td>
          <td>{e(m['data_solicitacao']) or '—'}</td></tr>"""
    tabela = f"""<table><thead><tr><th>Nº</th><th>Situação</th><th>Processo</th><th>Solicitada em</th></tr></thead>
        <tbody>{linhas}</tbody></table>"""
    return (f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
            f'<h2 style="margin:0">Medidas protetivas ({len(medidas)})</h2>{botao_nova}</div>{tabela}</div>')
