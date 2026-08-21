"""Módulo SIRIO — Login, primeira configuração e gestão de usuários.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403


def pagina_login(erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    corpo = f"""
    <form method="post" action="/login" class="login-cx">
      <div><div class="sigla" style="color:var(--ouro)">SIRIO</div>
      <div class="suave">Sistema Interno de Registro de Investigados e Organizações</div><div class="suave" style="font-size:.7rem;margin-top:.2rem">Versão {VERSAO}</div></div>
      <p class="aviso">Acesso restrito a usuários autorizados. Todas as ações são auditadas
      e o usuário responde pelo uso indevido das informações.</p>
      <label>Login<input name="username" autocomplete="username" required autofocus></label>
      <label>Senha<input type="password" name="senha" autocomplete="current-password" required></label>
      {msg}
      <button class="botao">Entrar</button>
    </form>"""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Entrar — SIRIO</title>
<style>{CSS}</style></head><body>{FAIXA}<div class="login-fundo">{corpo}</div></body></html>"""


def pagina_setup(erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    corpo = f"""
    <form method="post" action="/setup" class="login-cx">
      <div><div class="sigla" style="color:var(--ouro)">SIRIO</div>
      <div class="suave">Primeira utilização — criar o administrador</div></div>
      <p class="aviso">Este será o usuário com controle total do sistema (criar outros usuários,
      exportar dados, excluir registros). Guarde a senha em local seguro: não há recuperação automática.</p>
      <label>Nome completo<input name="nome" required autofocus></label>
      <label>Login<input name="username" required></label>
      <label>Senha (mínimo 8 caracteres)<input type="password" name="senha" minlength="8" required></label>
      <label>Repita a senha<input type="password" name="senha2" minlength="8" required></label>
      {msg}
      <button class="botao">Criar administrador e entrar</button>
    </form>"""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Configuração — SIRIO</title>
<style>{CSS}</style></head><body>{FAIXA}<div class="login-fundo">{corpo}</div></body></html>"""


def pagina_alterar_senha(usuario, csrf, erro="", ok=""):
    msg = (f'<p class="erro">{e(erro)}</p>' if erro else "") + (f'<p class="ok">{e(ok)}</p>' if ok else "")
    corpo = f"""
    <div class="cab"><h1>Alterar minha senha</h1></div>
    <div class="cartao" style="max-width:560px">
      <p class="suave">Para sua segurança, informe a senha atual antes de definir uma nova.</p>
      <form method="post" action="/minha-senha" class="grade">
        <input type="hidden" name="csrf" value="{e(csrf)}">
        <label class="span2">Senha atual<input type="password" name="senha_atual" autocomplete="current-password" required autofocus></label>
        <label>Nova senha (mínimo 8 caracteres)<input type="password" name="nova_senha" autocomplete="new-password" minlength="8" required></label>
        <label>Repita a nova senha<input type="password" name="nova_senha2" autocomplete="new-password" minlength="8" required></label>
        <div class="acoes span2"><button class="botao">Alterar senha</button><a class="botao fantasma" href="/">Cancelar</a></div>
      </form>{msg}
    </div>"""
    return pagina("Alterar minha senha", corpo, usuario)


def pagina_usuarios(usuario, csrf, lista, erro="", ok=""):
    msg = (f'<p class="erro">{e(erro)}</p>' if erro else "") + (f'<p class="ok">{e(ok)}</p>' if ok else "")
    # Cada linha da tabela é editável: nome, login e perfil podem ser corrigidos
    # sem precisar criar um segundo cadastro para a mesma pessoa. Os campos usam
    # o atributo HTML "form" porque não é permitido aninhar formulários em HTML.
    linhas = ""
    for u in lista:
        fid = f"fu{u['id']}"
        botao = ""
        if u["id"] != usuario["id"]:
            rotulo = "Desativar" if u["ativo"] else "Reativar"
            botao = f"""<form method="post" action="/usuarios/{u['id']}/ativo" style="display:inline">
              <input type="hidden" name="csrf" value="{e(csrf)}">
              <button class="botao mini fantasma">{rotulo}</button></form>"""
        eu = ' <span class="suave">(você)</span>' if u["id"] == usuario["id"] else ""
        linhas += f"""<tr>
          <td><form id="{fid}" method="post" action="/usuarios/{u['id']}/editar"></form>
              <input form="{fid}" type="hidden" name="csrf" value="{e(csrf)}">
              <input form="{fid}" name="nome" value="{e(u['nome'])}" required>{eu}</td>
          <td><input form="{fid}" name="username" value="{e(u['username'])}" required></td>
          <td><select form="{fid}" name="perfil">{opcoes(PERFIS, u['perfil'])}</select></td>
          <td>{'Ativo' if u['ativo'] else 'Desativado'}</td>
          <td><button form="{fid}" class="botao mini">Salvar</button> {botao}</td></tr>"""

    corpo = f"""
    <div class="cab"><h1>Usuários</h1></div>
    <div class="cartao"><h2>Novo usuário</h2>
      <form method="post" action="/usuarios" class="grade">
        <input type="hidden" name="csrf" value="{e(csrf)}">
        <label>Nome completo<input name="nome" required></label>
        <label>Login<input name="username" required></label>
        <label>Senha (mínimo 8 caracteres)<input type="password" name="senha" minlength="8" required></label>
        <label>Perfil<select name="perfil">{opcoes(PERFIS, 'consulta')}</select></label>
        <div class="acoes span2"><button class="botao">Criar usuário</button></div>
      </form>{msg}</div>
    <div class="cartao"><h2>Cadastrados</h2>
      <p class="suave">Altere o nome, o login ou o perfil direto na tabela e clique em
      <strong>Salvar</strong>. Toda alteração fica registrada na auditoria. O sistema não
      permite deixar a unidade sem nenhum administrador ativo.</p>
      <table><thead><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Situação</th><th></th></tr></thead>
      <tbody>{linhas}</tbody></table></div>"""
    return pagina("Usuários", corpo, usuario)
