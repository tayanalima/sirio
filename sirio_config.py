"""Módulo SIRIO — Configurações administrativas.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403


def pagina_configuracoes(usuario, csrf, erro="", ok=""):
    con = conexao()
    total_pessoas = con.execute("SELECT COUNT(*) FROM pessoas").fetchone()[0]
    total_ocorrencias = con.execute("SELECT COUNT(*) FROM ocorrencias").fetchone()[0]
    total_materiais = con.execute("SELECT COUNT(*) FROM materiais_apreendidos").fetchone()[0]
    total_usuarios = con.execute("SELECT COUNT(*) FROM usuarios WHERE ativo=1").fetchone()[0]
    opcoes_por_categoria = {}
    for categoria, _, _ in CATEGORIAS_CONFIGURAVEIS:
        opcoes_por_categoria[categoria] = con.execute(
            "SELECT * FROM opcoes_configuraveis WHERE categoria=? ORDER BY ativo DESC, id", (categoria,)
        ).fetchall()
    con.close()

    msg = (f'<p class="erro">{e(erro)}</p>' if erro else "") + (f'<p class="ok">{e(ok)}</p>' if ok else "")

    painel_geral = f"""
    <div class="cartao"><h2>Painel geral</h2>
      <div class="grade">
        {li_campo('Pessoas cadastradas', total_pessoas)}
        {li_campo('Ocorrências cadastradas', total_ocorrencias)}
        {li_campo('Materiais apreendidos', total_materiais)}
        {li_campo('Usuários ativos', total_usuarios)}
      </div></div>"""

    bloco_backup = f"""
    <div class="cartao"><h2>Backup</h2>
      <p class="suave">Cria uma cópia do banco de dados, das fotos e do certificado HTTPS na pasta "backups", sem
      precisar fechar o sistema nem rodar o arquivo .bat. Guarde também uma cópia fora deste
      computador de vez em quando (pen drive, por exemplo).</p>
      <form method="post" action="/configuracoes/backup">
        <input type="hidden" name="csrf" value="{e(csrf)}">
        <button class="botao">Criar backup agora</button>
      </form></div>"""

    blocos_categorias = ""
    for categoria, rotulo, descricao in CATEGORIAS_CONFIGURAVEIS:
        itens = opcoes_por_categoria[categoria]
        linhas = ""
        for op in itens:
            if op["ativo"]:
                botao = f"""<form method="post" action="/opcoes/{op['id']}/ativo" style="display:inline">
                  <input type="hidden" name="csrf" value="{e(csrf)}">
                  <button class="botao mini fantasma">Desativar</button></form>"""
                estilo = ""
            else:
                botao = f"""<form method="post" action="/opcoes/{op['id']}/ativo" style="display:inline">
                  <input type="hidden" name="csrf" value="{e(csrf)}">
                  <button class="botao mini fantasma">Reativar</button></form>"""
                estilo = ' style="opacity:.5"'
            linhas += f"""<tr{estilo}><td>{e(op['valor'])}</td>
              <td>{'Ativa' if op['ativo'] else 'Desativada'}</td><td>{botao}</td></tr>"""
        tabela_opcoes = (f"""<table><thead><tr><th>Opção</th><th>Situação</th><th></th></tr></thead>
            <tbody>{linhas}</tbody></table>""" if itens else '<p class="suave">Nenhuma opção cadastrada ainda.</p>')

        blocos_categorias += f"""
        <div class="cartao"><h2>{e(rotulo)}</h2>
          <p class="suave">{e(descricao)}</p>
          {tabela_opcoes}
          <form method="post" action="/configuracoes/adicionar" class="grade" style="margin-top:.8rem">
            <input type="hidden" name="csrf" value="{e(csrf)}">
            <input type="hidden" name="categoria" value="{e(categoria)}">
            <label class="span2">Nova opção<input name="valor" placeholder="Digite e clique em Adicionar" required></label>
            <div class="acoes span2" style="justify-content:flex-start">
              <button class="botao fantasma">Adicionar a "{e(rotulo)}"</button></div>
          </form></div>"""

    corpo = f"""
    <div class="cab"><h1>Configurações</h1></div>
    <p class="suave">Ajustes que só o administrador vê. Opções desativadas continuam
    aparecendo em registros antigos que já as usavam, mas somem das listas de novos
    cadastros — nada é apagado, então nenhum histórico se perde.</p>
    {msg}
    {painel_geral}
    {bloco_backup}
    {blocos_categorias}"""
    return pagina("Configurações", corpo, usuario)
