#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIRIO — Sistema Interno de Registro de Investigados e Organizações

Arquivo principal: monta o servidor HTTP e o roteamento (rotas), importando
as páginas e a lógica de cada tema dos módulos ao lado. Organizado por temas
para ficar mais fácil de localizar e alterar cada parte:

  sirio_core.py         infraestrutura compartilhada (banco, sessão, HTML,
                         constantes, auditoria) — usada por todos os outros
  sirio_usuarios.py      login, primeira configuração, gestão de usuários
  sirio_pessoas.py       registros (cadastro de pessoas), fotos, mesclagem
  sirio_ocorrencias.py   ocorrências e testemunhas
  sirio_materiais.py     materiais apreendidos
  sirio_mapa.py          mapa geográfico
  sirio_vinculos.py      diagrama de vínculos
  sirio_importar.py      importação de Boletim de Ocorrência (PDF) e CSV
  sirio_config.py        configurações administrativas

Módulo de Violência Doméstica (todos com prefixo sirio_vd_):
  sirio_vd_core.py       infraestrutura do módulo (tabelas, constantes,
                         linha do tempo, permissões)
  sirio_vd_casos.py      cadastro e ficha do caso, pessoas vinculadas
  sirio_vd_fonar.py      formulário FONAR de avaliação de risco
  sirio_vd_protetivas.py medidas protetivas, itens e descumprimentos
  sirio_vd_gestao.py     diligências, encaminhamentos e acompanhamento
  sirio_vd_painel.py     painel operacional e painel gerencial

USO RESTRITO — ferramenta interna de apoio à análise policial.
Todo acesso é autenticado e auditado. Use apenas dados fictícios em testes.

Requisito: Python 3.10 ou superior.
Para executar:  python sirio.py   (ou dê dois cliques em "Iniciar SIRIO.bat")
O sistema abre no navegador em https://localhost:8377
Os dados ficam no arquivo sirio.db, nesta mesma pasta (faça backup dele!).
Todos os arquivos .py precisam estar juntos, na mesma pasta.
"""
import sys

# Verificação de versão ANTES de qualquer outro import do sistema, para que um
# Python antigo produza uma mensagem clara em vez de um erro incompreensível.
if sys.version_info < (3, 10):
    _v = ".".join(str(n) for n in sys.version_info[:3])
    print("=" * 62)
    print(" SIRIO — versao do Python incompativel")
    print("=" * 62)
    print(f" Este computador tem o Python {_v}.")
    print(" O SIRIO precisa do Python 3.10 ou mais novo.")
    print()
    print(" Como resolver:")
    print("   1. Baixe a versao atual em https://www.python.org/downloads/")
    print('   2. Na instalacao, marque a caixinha "Add Python to PATH".')
    print("   3. Reinicie o computador e abra o SIRIO novamente.")
    print("=" * 62)
    input(" Pressione ENTER para fechar...")
    sys.exit(1)

import threading
import webbrowser
import ssl

from sirio_core import *  # noqa: F401,F403
from sirio_core import _num_ou_none  # nomes com "_" não vêm no import *
from sirio_usuarios import *  # noqa: F401,F403
from sirio_pessoas import *  # noqa: F401,F403
from sirio_ocorrencias import *  # noqa: F401,F403
from sirio_materiais import *  # noqa: F401,F403
from sirio_mapa import *  # noqa: F401,F403
from sirio_vinculos import *  # noqa: F401,F403
from sirio_importar import *  # noqa: F401,F403
from sirio_config import *  # noqa: F401,F403
from sirio_vd_core import *  # noqa: F401,F403
from sirio_vd_casos import *  # noqa: F401,F403
from sirio_vd_fonar import *  # noqa: F401,F403
from sirio_vd_protetivas import *  # noqa: F401,F403
from sirio_vd_gestao import *  # noqa: F401,F403
from sirio_vd_painel import *  # noqa: F401,F403
from sirio_verificacoes import *  # noqa: F401,F403


class Servidor(BaseHTTPRequestHandler):

    # --- utilidades -----------------------------------------------------

    def log_message(self, formato, *args):
        pass  # silencia o log padrão (a auditoria fica no banco)

    def responde_html(self, conteudo, status=200, cookies=None):
        dados = conteudo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for c in (cookies or []):
            self.send_header("Set-Cookie", c)
        self.end_headers()
        self.wfile.write(dados)

    def redireciona(self, destino, cookies=None):
        self.send_response(303)
        self.send_header("Location", destino)
        for c in (cookies or []):
            self.send_header("Set-Cookie", c)
        self.end_headers()

    def token_sessao(self):
        bruto = self.headers.get("Cookie", "")
        for parte in bruto.split(";"):
            nome, _, valor = parte.strip().partition("=")
            if nome == "sirio_sessao":
                return valor
        return None

    def form(self):
        tamanho = int(self.headers.get("Content-Length", 0) or 0)
        corpo = self.rfile.read(tamanho).decode("utf-8") if tamanho else ""
        dados = urllib.parse.parse_qs(corpo, keep_blank_values=True)
        self._form_bruto = dados  # guardado para form_multi() reaproveitar sem reler o socket
        return {k: v[0].strip() for k, v in dados.items()}

    def form_multi(self, campo):
        """Devolve TODOS os valores de um campo repetido no formulário (ex.: vários
        checkboxes com o mesmo name="tipo"). Precisa ser chamado depois de form()."""
        return [v.strip() for v in getattr(self, "_form_bruto", {}).get(campo, [])]

    def form_json(self):
        """Lê um corpo JSON (usado pelas chamadas fetch() do diagrama de vínculos)."""
        tamanho = int(self.headers.get("Content-Length", 0) or 0)
        corpo = self.rfile.read(tamanho).decode("utf-8") if tamanho else "{}"
        try:
            return json.loads(corpo) or {}
        except (ValueError, TypeError):
            return {}

    def responde_json(self, dados, status=200):
        corpo = json.dumps(dados).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def form_multipart(self):
        """Lê um formulário com arquivos (multipart). Retorna (campos, arquivos)."""
        tamanho = int(self.headers.get("Content-Length", 0) or 0)
        corpo = self.rfile.read(tamanho) if tamanho else b""
        content_type = self.headers.get("Content-Type", "")
        if "boundary=" not in content_type:
            return None, []
        cabecalho_completo = (
            f"Content-Type: {content_type}\r\n\r\n").encode("utf-8") + corpo
        msg = email.message_from_bytes(cabecalho_completo, policy=email.policy.default)
        campos = {}
        arquivos = []
        if msg.is_multipart():
            for parte in msg.iter_parts():
                nome = parte.get_param("name", header="Content-Disposition")
                nome_arquivo = parte.get_filename()
                if nome_arquivo:
                    conteudo = parte.get_payload(decode=True)
                    if conteudo:
                        arquivos.append((nome_arquivo, conteudo))
                elif nome:
                    valor = parte.get_payload(decode=True)
                    if valor is not None:
                        campos[nome] = valor.decode("utf-8", errors="replace").strip()
        return campos, arquivos

    def query(self):
        qs = urllib.parse.urlsplit(self.path).query
        dados = urllib.parse.parse_qs(qs, keep_blank_values=True)
        return {k: v[0] for k, v in dados.items()}

    def caminho(self):
        return urllib.parse.urlsplit(self.path).path

    def csrf_ok(self, dados, csrf):
        return secrets.compare_digest(dados.get("csrf", ""), csrf)

    def exige_login(self):
        token = self.token_sessao()
        u = usuario_da_sessao(token) if token else None
        if not u:
            self.redireciona("/login")
            return None
        csrf = SESSOES[token]["csrf"]
        return u, csrf

    # --- GET ---------------------------------------------------------------

    def do_GET(self):
        caminho = self.caminho()

        con = conexao()
        existe_admin = con.execute("SELECT 1 FROM usuarios WHERE perfil='admin' LIMIT 1").fetchone()
        con.close()
        if not existe_admin and caminho != "/setup":
            return self.redireciona("/setup")

        if caminho == "/setup":
            if existe_admin:
                return self.redireciona("/login")
            return self.responde_html(pagina_setup())

        if caminho == "/login":
            token = self.token_sessao()
            if token and usuario_da_sessao(token):
                return self.redireciona("/")
            return self.responde_html(pagina_login())

        if caminho == "/sair":
            token = self.token_sessao()
            if token:
                SESSOES.pop(token, None)
            return self.redireciona("/login", cookies=["sirio_sessao=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"])

        sessao = self.exige_login()
        if not sessao:
            return
        usuario, csrf = sessao

        if caminho == "/":
            return self.responde_html(pagina_lista(usuario, self.query()))

        if caminho == "/vinculos":
            consulta = self.query()
            return self.responde_html(pagina_vinculos(
                usuario, csrf, consulta.get("org", ""), consulta.get("modo", "organizacoes"),
                consulta.get("autor", "")))

        if caminho == "/pessoas/nova":
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/")
            return self.responde_html(pagina_form(usuario, csrf))

        if caminho == "/pessoas/mesclar":
            if usuario["perfil"] != "admin":
                return self.redireciona("/")
            q = self.query()
            pa_id, pb_id = q.get("pessoa_a"), q.get("pessoa_b")
            if not pa_id or not pb_id:
                return self.responde_html(pagina_pessoas_mesclar_selecionar(usuario, csrf))
            if pa_id == pb_id:
                return self.responde_html(pagina_pessoas_mesclar_selecionar(usuario, csrf,
                    "Escolha dois registros diferentes."))
            con = conexao()
            pa = con.execute("SELECT * FROM pessoas WHERE id=?", (pa_id,)).fetchone()
            pb = con.execute("SELECT * FROM pessoas WHERE id=?", (pb_id,)).fetchone()
            con.close()
            if not pa or not pb:
                return self.responde_html(pagina_pessoas_mesclar_selecionar(usuario, csrf,
                    "Um dos registros não foi encontrado. Selecione novamente pela lista sugerida."))
            return self.responde_html(pagina_pessoas_mesclar_comparar(usuario, csrf, pa, pb))

        m = re.fullmatch(r"/pessoas/(\d+)/editar", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/")
            pid = int(m.group(1))
            con = conexao()
            p = con.execute("SELECT * FROM pessoas WHERE id=?", (pid,)).fetchone()
            fotos = con.execute("SELECT * FROM fotos WHERE pessoa_id=? ORDER BY id", (pid,)).fetchall()
            con.close()
            if not p:
                return self.responde_html(pagina("Não encontrada", '<p class="erro">Registro não encontrado.</p>', usuario), 404)
            return self.responde_html(pagina_form(usuario, csrf, dict(p), pid, fotos=fotos))

        m = re.fullmatch(r"/pessoas/(\d+)", caminho)
        if m:
            pid = int(m.group(1))
            con = conexao()
            p = con.execute("SELECT * FROM pessoas WHERE id=?", (pid,)).fetchone()
            if not p:
                con.close()
                return self.responde_html(pagina("Não encontrada", '<p class="erro">Registro não encontrado.</p>', usuario), 404)
            # A trilha de auditoria só é carregada para o Administrador — assim os
            # dados nem chegam à página quando o usuário não tem permissão de vê-los.
            trilha = con.execute(
                "SELECT * FROM auditoria WHERE pessoa_id=? ORDER BY id DESC LIMIT 200", (pid,)
            ).fetchall() if usuario["perfil"] == "admin" else []
            usuarios_ids = {a["usuario_id"] for a in trilha} | {p["criado_por"], p["atualizado_por"]}
            usuarios_ids.discard(None)
            nomes = {}
            if usuarios_ids:
                marcas = ",".join("?" for _ in usuarios_ids)
                for u in con.execute(f"SELECT id, nome FROM usuarios WHERE id IN ({marcas})", list(usuarios_ids)):
                    nomes[u["id"]] = u["nome"]
            fotos = con.execute("SELECT * FROM fotos WHERE pessoa_id=? ORDER BY id", (pid,)).fetchall()
            audita(con, usuario["id"], "VIEW", pid)
            con.commit()
            materiais_raw = con.execute(
                "SELECT m.*, o.tipo_crime AS oc_tipo FROM materiais_apreendidos m "
                "LEFT JOIN ocorrencias o ON o.id = m.ocorrencia_id "
                "WHERE m.pessoa_id=? ORDER BY m.id DESC", (pid,)).fetchall()
            boletins = con.execute(
                "SELECT b.*, bp.tipo_envolvimento FROM boletins b "
                "JOIN boletim_pessoa bp ON bp.boletim_id = b.id "
                "WHERE bp.pessoa_id=? ORDER BY b.id DESC", (pid,)).fetchall()
            biqueiras = con.execute(
                "SELECT * FROM biqueiras WHERE pessoa_id=? ORDER BY id DESC", (pid,)).fetchall()
            con.close()
            return self.responde_html(pagina_detalhe(usuario, csrf, p, trilha, nomes, fotos,
                                                      materiais_raw, boletins, biqueiras))

        if caminho == "/ocorrencias":
            q = self.query()
            return self.responde_html(pagina_ocorrencias_lista(
                usuario, csrf, q.get("tipo", ""), q.get("pessoa_autor_id", "")))

        if caminho == "/ocorrencias/nova":
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/ocorrencias")
            return self.responde_html(pagina_ocorrencia_form(usuario, csrf))

        m = re.fullmatch(r"/ocorrencias/(\d+)/editar", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/ocorrencias")
            oid = int(m.group(1))
            con = conexao()
            o = con.execute("SELECT * FROM ocorrencias WHERE id=?", (oid,)).fetchone()
            con.close()
            if not o:
                return self.responde_html(pagina("Não encontrada", '<p class="erro">Ocorrência não encontrada.</p>', usuario), 404)
            dados = dict(o)
            if o["pessoa_autor_id"]:
                con = conexao()
                pa = con.execute("SELECT nome FROM pessoas WHERE id=?", (o["pessoa_autor_id"],)).fetchone()
                con.close()
                dados["pessoa_autor_nome"] = pa["nome"] if pa else ""
            return self.responde_html(pagina_ocorrencia_form(usuario, csrf, dados, oid))

        m = re.fullmatch(r"/ocorrencias/(\d+)", caminho)
        if m:
            oid = int(m.group(1))
            con = conexao()
            o = con.execute("SELECT * FROM ocorrencias WHERE id=?", (oid,)).fetchone()
            if not o:
                con.close()
                return self.responde_html(pagina("Não encontrada", '<p class="erro">Ocorrência não encontrada.</p>', usuario), 404)
            testemunhas = con.execute(
                "SELECT * FROM ocorrencia_testemunhas WHERE ocorrencia_id=? ORDER BY id", (oid,)).fetchall()
            nome_autor_pessoa = None
            if o["pessoa_autor_id"]:
                pa = con.execute("SELECT nome FROM pessoas WHERE id=?", (o["pessoa_autor_id"],)).fetchone()
                nome_autor_pessoa = pa["nome"] if pa else None
            materiais = con.execute(
                "SELECT m.*, p.nome AS pessoa_nome FROM materiais_apreendidos m "
                "LEFT JOIN pessoas p ON p.id = m.pessoa_id "
                "WHERE m.ocorrencia_id=? ORDER BY m.id DESC", (oid,)).fetchall()
            pessoas = con.execute("SELECT id, nome FROM pessoas ORDER BY nome").fetchall()
            con.close()
            lista_pessoas_html = "".join(f'<option value="{e(p["nome"])}" data-id="{p["id"]}">' for p in pessoas)
            return self.responde_html(pagina_ocorrencia_detalhe(
                usuario, csrf, o, testemunhas, nome_autor_pessoa, materiais, lista_pessoas_html))

        if caminho == "/materiais":
            return self.responde_html(pagina_materiais_lista(usuario, csrf, self.query()))

        if caminho == "/materiais/novo":
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/materiais")
            return self.responde_html(pagina_material_form(usuario, csrf))

        if caminho == "/mapa":
            return self.responde_html(pagina_mapa(usuario))

        if caminho == "/mapa/dados.json":
            pontos, _ = calcula_pontos_mapa()
            corpo_json = json.dumps(pontos, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo_json)))
            self.end_headers()
            self.wfile.write(corpo_json)
            return

        if caminho == "/importar":
            if usuario["perfil"] not in ("admin", "analista") or not PDF_DISPONIVEL:
                return self.redireciona("/")
            return self.responde_html(pagina_importar_upload(usuario, csrf))

        m = re.fullmatch(r"/fotos/([0-9a-f]{32}\.(?:jpg|jpeg|png|gif|webp))", caminho)
        if m:
            arquivo = m.group(1)
            local = os.path.join(PASTA_FOTOS, arquivo)
            if not os.path.isfile(local):
                return self.responde_html(pagina("Não encontrada",
                    '<p class="erro">Imagem não encontrada.</p>', usuario), 404)
            ext = os.path.splitext(arquivo)[1].lower()
            with open(local, "rb") as f:
                dados = f.read()
            self.send_response(200)
            self.send_header("Content-Type", TIPOS_IMAGEM[ext][0])
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "private, max-age=300")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(dados)
            return

        if caminho == "/importar-csv":
            if usuario["perfil"] != "admin":
                return self.redireciona("/")
            q = self.query()
            return self.responde_html(pagina_importar_csv(usuario, csrf,
                erro=q.get("erro", ""), resumo=q.get("ok", "")))

        if caminho == "/vd":
            return self.responde_html(pagina_vd_lista(usuario, csrf, self.query()))

        if caminho == "/vd/painel":
            return self.responde_html(pagina_painel_operacional(usuario, csrf, calcula_painel_operacional()))

        if caminho == "/vd/painel-gerencial":
            return self.responde_html(pagina_painel_gerencial(usuario, csrf, self.query(),
                                                               calcula_painel_gerencial(self.query())))

        if caminho == "/vd/novo":
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            return self.responde_html(pagina_vd_form(usuario, csrf))

        m = re.fullmatch(r"/vd/(\d+)/editar", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            con.close()
            if not caso:
                return self.responde_html(pagina("Não encontrado", '<p class="erro">Caso não encontrado.</p>', usuario), 404)
            return self.responde_html(pagina_vd_form(usuario, csrf, dict(caso), cid))

        m = re.fullmatch(r"/vd/caso-pessoas/(\d+)/dados", caminho)
        if m:
            cpid = int(m.group(1))
            con = conexao()
            cp = con.execute("SELECT * FROM vd_caso_pessoas WHERE id=?", (cpid,)).fetchone()
            if not cp:
                con.close()
                return self.responde_html(pagina("Não encontrado", '<p class="erro">Vínculo não encontrado.</p>', usuario), 404)
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cp["caso_id"],)).fetchone()
            pessoa = con.execute("SELECT * FROM pessoas WHERE id=?", (cp["pessoa_id"],)).fetchone()
            tabela_extra = "vd_dados_mulher" if cp["papel"] == "mulher_atendida" else "vd_dados_autor"
            dados_extra = con.execute(
                f"SELECT * FROM {tabela_extra} WHERE caso_pessoa_id=?", (cpid,)).fetchone()
            con.close()
            if cp["papel"] not in ("mulher_atendida", "suposto_autor"):
                return self.redireciona(f"/vd/{cp['caso_id']}")
            return self.responde_html(pagina_vd_dados_papel(
                usuario, csrf, caso, cp, pessoa, dict(dados_extra) if dados_extra else {}))

        m = re.fullmatch(r"/vd/caso-pessoas/(\d+)/fonar/novo", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            cpid = int(m.group(1))
            con = conexao()
            cp = con.execute("SELECT * FROM vd_caso_pessoas WHERE id=?", (cpid,)).fetchone()
            if not cp or cp["papel"] != "mulher_atendida":
                con.close()
                return self.redireciona("/vd")
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cp["caso_id"],)).fetchone()
            pessoa = con.execute("SELECT * FROM pessoas WHERE id=?", (cp["pessoa_id"],)).fetchone()
            con.close()
            return self.responde_html(pagina_fonar_novo(usuario, csrf, caso, cp, pessoa))

        m = re.fullmatch(r"/vd/caso-pessoas/(\d+)/fonar", caminho)
        if m:
            cpid = int(m.group(1))
            con = conexao()
            cp = con.execute("SELECT * FROM vd_caso_pessoas WHERE id=?", (cpid,)).fetchone()
            if not cp or cp["papel"] != "mulher_atendida":
                con.close()
                return self.redireciona("/vd")
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cp["caso_id"],)).fetchone()
            pessoa = con.execute("SELECT * FROM pessoas WHERE id=?", (cp["pessoa_id"],)).fetchone()
            aplicacoes_raw = con.execute(
                "SELECT fa.*, u.nome AS aplicador_nome FROM vd_fonar_aplicacoes fa "
                "LEFT JOIN usuarios u ON u.id = fa.aplicador_id "
                "WHERE fa.caso_pessoa_id=? ORDER BY fa.id DESC", (cpid,)).fetchall()
            aplicacoes = []
            for ap in aplicacoes_raw:
                respostas = con.execute(
                    "SELECT pergunta_codigo, resposta FROM vd_fonar_respostas WHERE aplicacao_id=?",
                    (ap["id"],)).fetchall()
                respostas_dict = {r["pergunta_codigo"]: r["resposta"] for r in respostas}
                d = dict(ap)
                d["n_fatores"] = len(fonar_fatores_presentes(respostas_dict))
                aplicacoes.append(d)
            con.close()
            return self.responde_html(pagina_fonar_lista(usuario, csrf, caso, cp, pessoa, aplicacoes))

        m = re.fullmatch(r"/vd/fonar/(\d+)", caminho)
        if m:
            apid = int(m.group(1))
            con = conexao()
            aplicacao = con.execute("SELECT * FROM vd_fonar_aplicacoes WHERE id=?", (apid,)).fetchone()
            if not aplicacao:
                con.close()
                return self.responde_html(pagina("Não encontrado", '<p class="erro">Aplicação não encontrada.</p>', usuario), 404)
            cp = con.execute("SELECT * FROM vd_caso_pessoas WHERE id=?", (aplicacao["caso_pessoa_id"],)).fetchone()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cp["caso_id"],)).fetchone()
            pessoa = con.execute("SELECT * FROM pessoas WHERE id=?", (cp["pessoa_id"],)).fetchone()
            aplicador = con.execute("SELECT nome FROM usuarios WHERE id=?", (aplicacao["aplicador_id"],)).fetchone()
            respostas = con.execute(
                "SELECT * FROM vd_fonar_respostas WHERE aplicacao_id=?", (apid,)).fetchall()
            con.close()
            return self.responde_html(pagina_fonar_detalhe(
                usuario, csrf, aplicacao, respostas, caso, cp, pessoa,
                aplicador["nome"] if aplicador else "—"))

        m = re.fullmatch(r"/vd/(\d+)/avaliacao/nova", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            con.close()
            if not caso:
                return self.redireciona("/vd")
            return self.responde_html(pagina_avaliacao_nova(usuario, csrf, caso))

        m = re.fullmatch(r"/vd/(\d+)/medidas/nova", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            con.close()
            if not caso:
                return self.redireciona("/vd")
            return self.responde_html(pagina_medida_nova(usuario, csrf, caso))

        m = re.fullmatch(r"/vd/medidas/(\d+)/editar", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            mid = int(m.group(1))
            con = conexao()
            medida = con.execute("SELECT * FROM vd_medidas_protetivas WHERE id=?", (mid,)).fetchone()
            if not medida:
                con.close()
                return self.redireciona("/vd")
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (medida["caso_id"],)).fetchone()
            con.close()
            return self.responde_html(pagina_medida_editar(usuario, csrf, medida, caso))

        m = re.fullmatch(r"/vd/medidas/(\d+)/descumprimento/novo", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            mid = int(m.group(1))
            con = conexao()
            medida = con.execute("SELECT * FROM vd_medidas_protetivas WHERE id=?", (mid,)).fetchone()
            if not medida:
                con.close()
                return self.redireciona("/vd")
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (medida["caso_id"],)).fetchone()
            con.close()
            return self.responde_html(pagina_descumprimento_novo(usuario, csrf, medida, caso))

        m = re.fullmatch(r"/vd/medidas/(\d+)", caminho)
        if m:
            mid = int(m.group(1))
            con = conexao()
            medida = con.execute("SELECT * FROM vd_medidas_protetivas WHERE id=?", (mid,)).fetchone()
            if not medida:
                con.close()
                return self.responde_html(pagina("Não encontrada", '<p class="erro">Medida não encontrada.</p>', usuario), 404)
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (medida["caso_id"],)).fetchone()
            itens = con.execute(
                "SELECT * FROM vd_itens_medida_protetiva WHERE medida_id=? ORDER BY id", (mid,)).fetchall()
            descumprimentos = con.execute(
                "SELECT * FROM vd_descumprimentos WHERE medida_id=? ORDER BY id DESC", (mid,)).fetchall()
            usuarios_ids = {d["responsavel_id"] for d in descumprimentos}
            usuarios_ids.discard(None)
            nomes = {}
            if usuarios_ids:
                marcas = ",".join("?" for _ in usuarios_ids)
                for u in con.execute(f"SELECT id, nome FROM usuarios WHERE id IN ({marcas})", list(usuarios_ids)):
                    nomes[u["id"]] = u["nome"]
            con.close()
            return self.responde_html(pagina_medida_detalhe(
                usuario, csrf, medida, itens, descumprimentos, caso, nomes))

        m = re.fullmatch(r"/vd/(\d+)/diligencias/nova", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            con.close()
            if not caso:
                return self.redireciona("/vd")
            return self.responde_html(pagina_diligencia_nova(usuario, csrf, caso))

        m = re.fullmatch(r"/vd/diligencias/(\d+)/editar", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            did = int(m.group(1))
            con = conexao()
            dilig = con.execute("SELECT * FROM vd_diligencias WHERE id=?", (did,)).fetchone()
            if not dilig:
                con.close()
                return self.redireciona("/vd")
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (dilig["caso_id"],)).fetchone()
            con.close()
            return self.responde_html(pagina_diligencia_editar(usuario, csrf, dilig, caso))

        m = re.fullmatch(r"/vd/(\d+)/encaminhamentos/novo", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            con.close()
            if not caso:
                return self.redireciona("/vd")
            return self.responde_html(pagina_encaminhamento_novo(usuario, csrf, caso))

        m = re.fullmatch(r"/vd/encaminhamentos/(\d+)/editar", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            eid = int(m.group(1))
            con = conexao()
            enc = con.execute("SELECT * FROM vd_encaminhamentos WHERE id=?", (eid,)).fetchone()
            if not enc:
                con.close()
                return self.redireciona("/vd")
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (enc["caso_id"],)).fetchone()
            con.close()
            return self.responde_html(pagina_encaminhamento_editar(usuario, csrf, enc, caso))

        m = re.fullmatch(r"/vd/(\d+)/acompanhamentos/novo", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            mulher_cp = con.execute(
                "SELECT id FROM vd_caso_pessoas WHERE caso_id=? AND papel='mulher_atendida' LIMIT 1", (cid,)).fetchone()
            dados_mulher = None
            if mulher_cp:
                dados_mulher = con.execute(
                    "SELECT * FROM vd_dados_mulher WHERE caso_pessoa_id=?", (mulher_cp["id"],)).fetchone()
            con.close()
            return self.responde_html(pagina_acompanhamento_novo(usuario, csrf, caso, dados_mulher))

        m = re.fullmatch(r"/vd/acompanhamentos/(\d+)/editar", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/vd")
            aid = int(m.group(1))
            con = conexao()
            contato = con.execute("SELECT * FROM vd_contatos_acompanhamento WHERE id=?", (aid,)).fetchone()
            if not contato:
                con.close()
                return self.redireciona("/vd")
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (contato["caso_id"],)).fetchone()
            mulher_cp = con.execute(
                "SELECT id FROM vd_caso_pessoas WHERE caso_id=? AND papel='mulher_atendida' LIMIT 1",
                (contato["caso_id"],)).fetchone()
            dados_mulher = None
            if mulher_cp:
                dados_mulher = con.execute(
                    "SELECT * FROM vd_dados_mulher WHERE caso_pessoa_id=?", (mulher_cp["id"],)).fetchone()
            con.close()
            return self.responde_html(pagina_acompanhamento_editar(usuario, csrf, contato, caso, dados_mulher))

        m = re.fullmatch(r"/vd/(\d+)/linha-tempo", caminho)
        if m:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.responde_html(pagina("Não encontrado", '<p class="erro">Caso não encontrado.</p>', usuario), 404)
            eventos = con.execute(
                "SELECT * FROM vd_eventos_linha_tempo WHERE caso_id=? ORDER BY timestamp DESC, id DESC",
                (cid,)).fetchall()
            usuarios_ids = {ev["usuario_id"] for ev in eventos}
            usuarios_ids.discard(None)
            nomes = {}
            if usuarios_ids:
                marcas = ",".join("?" for _ in usuarios_ids)
                for u in con.execute(f"SELECT id, nome FROM usuarios WHERE id IN ({marcas})", list(usuarios_ids)):
                    nomes[u["id"]] = u["nome"]
            con.close()
            return self.responde_html(pagina_linha_tempo(usuario, csrf, caso, eventos, nomes))

        m = re.fullmatch(r"/vd/(\d+)/relatorio", caminho)
        if m:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.responde_html(pagina("Não encontrado", '<p class="erro">Caso não encontrado.</p>', usuario), 404)
            pessoas_vinculadas = con.execute(
                "SELECT cp.*, p.nome FROM vd_caso_pessoas cp JOIN pessoas p ON p.id = cp.pessoa_id "
                "WHERE cp.caso_id=? ORDER BY cp.id", (cid,)).fetchall()
            tipos_violencia = [r["tipo"] for r in con.execute(
                "SELECT tipo FROM vd_caso_tipos_violencia WHERE caso_id=?", (cid,)).fetchall()]
            marcadores = [r["marcador"] for r in con.execute(
                "SELECT marcador FROM vd_caso_marcadores WHERE caso_id=?", (cid,)).fetchall()]
            medidas_raw = con.execute(
                "SELECT * FROM vd_medidas_protetivas WHERE caso_id=? ORDER BY id DESC", (cid,)).fetchall()
            medidas = []
            for m2 in medidas_raw:
                aberto = con.execute(
                    "SELECT 1 FROM vd_descumprimentos WHERE medida_id=? AND "
                    "(situacao_apuracao IS NULL OR situacao_apuracao IN ('registrado','em_apuracao')) LIMIT 1",
                    (m2["id"],)).fetchone()
                dm = dict(m2)
                dm["tem_descumprimento_aberto"] = bool(aberto)
                medidas.append(dm)
            fonar_resumo = []
            for cp in pessoas_vinculadas:
                if cp["papel"] != "mulher_atendida":
                    continue
                aplicacoes = con.execute(
                    "SELECT fa.*, u.nome AS aplicador_nome FROM vd_fonar_aplicacoes fa "
                    "LEFT JOIN usuarios u ON u.id = fa.aplicador_id WHERE fa.caso_pessoa_id=?",
                    (cp["id"],)).fetchall()
                for ap in aplicacoes:
                    respostas = con.execute(
                        "SELECT pergunta_codigo, resposta FROM vd_fonar_respostas WHERE aplicacao_id=?",
                        (ap["id"],)).fetchall()
                    respostas_dict = {r["pergunta_codigo"]: r["resposta"] for r in respostas}
                    df = dict(ap)
                    df["n_fatores"] = len(fonar_fatores_presentes(respostas_dict))
                    fonar_resumo.append(df)
            diligencias = con.execute(
                "SELECT * FROM vd_diligencias WHERE caso_id=? ORDER BY id DESC", (cid,)).fetchall()
            encaminhamentos = con.execute(
                "SELECT * FROM vd_encaminhamentos WHERE caso_id=? ORDER BY id DESC", (cid,)).fetchall()
            usuarios_ids = {caso["servidor_responsavel_id"]}
            usuarios_ids.discard(None)
            nomes = {}
            if usuarios_ids:
                marcas = ",".join("?" for _ in usuarios_ids)
                for u in con.execute(f"SELECT id, nome FROM usuarios WHERE id IN ({marcas})", list(usuarios_ids)):
                    nomes[u["id"]] = u["nome"]
            audita(con, usuario["id"], "EXPORT", None, "vd_relatorio_caso", None,
                   f"Relatório do caso #{cid} emitido")
            vd_registra_evento(con, cid, "relatorio_emitido", "Relatório do caso emitido/impresso", usuario["id"])
            con.commit()
            con.close()
            return self.responde_html(pagina_relatorio_caso(
                usuario, caso, pessoas_vinculadas, tipos_violencia, marcadores, medidas,
                fonar_resumo, diligencias, encaminhamentos, nomes))

        m = re.fullmatch(r"/vd/(\d+)", caminho)
        if m:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.responde_html(pagina("Não encontrado", '<p class="erro">Caso não encontrado.</p>', usuario), 404)
            pessoas_vinculadas = con.execute(
                "SELECT cp.*, p.nome FROM vd_caso_pessoas cp JOIN pessoas p ON p.id = cp.pessoa_id "
                "WHERE cp.caso_id=? ORDER BY cp.id", (cid,)).fetchall()
            ocorrencias_vinculadas = con.execute(
                "SELECT o.*, vo.id AS vinculo_id FROM vd_caso_ocorrencias vo "
                "JOIN ocorrencias o ON o.id = vo.ocorrencia_id WHERE vo.caso_id=? ORDER BY vo.id", (cid,)).fetchall()
            tipos_violencia = [r["tipo"] for r in con.execute(
                "SELECT tipo FROM vd_caso_tipos_violencia WHERE caso_id=?", (cid,)).fetchall()]
            marcadores = [r["marcador"] for r in con.execute(
                "SELECT marcador FROM vd_caso_marcadores WHERE caso_id=?", (cid,)).fetchall()]
            avaliacoes = con.execute(
                "SELECT * FROM vd_avaliacoes_profissionais WHERE caso_id=? ORDER BY id DESC", (cid,)).fetchall()
            medidas_raw = con.execute(
                "SELECT * FROM vd_medidas_protetivas WHERE caso_id=? ORDER BY id DESC", (cid,)).fetchall()
            medidas = []
            for m in medidas_raw:
                aberto = con.execute(
                    "SELECT 1 FROM vd_descumprimentos WHERE medida_id=? AND "
                    "(situacao_apuracao IS NULL OR situacao_apuracao IN ('registrado','em_apuracao')) LIMIT 1",
                    (m["id"],)).fetchone()
                d = dict(m)
                d["tem_descumprimento_aberto"] = bool(aberto)
                medidas.append(d)
            diligencias = con.execute(
                "SELECT * FROM vd_diligencias WHERE caso_id=? ORDER BY id DESC", (cid,)).fetchall()
            encaminhamentos = con.execute(
                "SELECT * FROM vd_encaminhamentos WHERE caso_id=? ORDER BY id DESC", (cid,)).fetchall()
            acompanhamentos = con.execute(
                "SELECT * FROM vd_contatos_acompanhamento WHERE caso_id=? ORDER BY id DESC", (cid,)).fetchall()
            usuarios_ids = {caso["servidor_responsavel_id"], caso["criado_por"]}
            usuarios_ids |= {av["responsavel_id"] for av in avaliacoes}
            usuarios_ids |= {dl["responsavel_id"] for dl in diligencias}
            usuarios_ids |= {ac["responsavel_id"] for ac in acompanhamentos}
            usuarios_ids.discard(None)
            nomes = {}
            if usuarios_ids:
                marcas = ",".join("?" for _ in usuarios_ids)
                for u in con.execute(f"SELECT id, nome FROM usuarios WHERE id IN ({marcas})", list(usuarios_ids)):
                    nomes[u["id"]] = u["nome"]
            # Reincidência: quantos OUTROS casos no sistema envolvem a mesma mulher / o mesmo autor
            reincidencia = {"casos_mulher": 0, "casos_autor": 0}
            mulher = next((p for p in pessoas_vinculadas if p["papel"] == "mulher_atendida"), None)
            autor = next((p for p in pessoas_vinculadas if p["papel"] == "suposto_autor"), None)
            if mulher:
                reincidencia["casos_mulher"] = con.execute(
                    "SELECT COUNT(DISTINCT caso_id) FROM vd_caso_pessoas WHERE pessoa_id=? AND papel='mulher_atendida'",
                    (mulher["pessoa_id"],)).fetchone()[0]
            if autor:
                reincidencia["casos_autor"] = con.execute(
                    "SELECT COUNT(DISTINCT caso_id) FROM vd_caso_pessoas WHERE pessoa_id=? AND papel='suposto_autor'",
                    (autor["pessoa_id"],)).fetchone()[0]
            con.close()
            return self.responde_html(pagina_vd_detalhe(
                usuario, csrf, caso, pessoas_vinculadas, ocorrencias_vinculadas,
                tipos_violencia, marcadores, nomes, reincidencia, avaliacoes, medidas,
                diligencias, encaminhamentos, acompanhamentos))

        # --- Verificação de denúncias -------------------------------------
        if caminho == "/verificacoes":
            return self.responde_html(pagina_verificacoes_lista(usuario, csrf, self.query()))

        if caminho == "/verificacoes/nova":
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/verificacoes")
            return self.responde_html(pagina_verificacao_form(usuario, csrf))

        m = re.fullmatch(r"/verificacoes/(\d+)/editar", caminho)
        if m:
            if usuario["perfil"] not in ("admin", "analista"):
                return self.redireciona("/verificacoes")
            vid = int(m.group(1))
            con = conexao()
            v = con.execute("SELECT * FROM verificacoes WHERE id=?", (vid,)).fetchone()
            con.close()
            if not v:
                return self.responde_html(pagina("Não encontrada",
                    '<p class="erro">Verificação não encontrada.</p>', usuario), 404)
            return self.responde_html(pagina_verificacao_form(usuario, csrf, dict(v), vid))

        m = re.fullmatch(r"/verificacoes/(\d+)/comunicacao\.docx", caminho)
        if m:
            vid = int(m.group(1))
            con = conexao()
            v = con.execute("SELECT * FROM verificacoes WHERE id=?", (vid,)).fetchone()
            if v:
                audita(con, usuario["id"], "EXPORT", None, "verificacao",
                       None, f"Comunicação de Serviço da verificação #{vid}")
                con.commit()
            con.close()
            if not v:
                return self.responde_html(pagina("Não encontrada",
                    '<p class="erro">Verificação não encontrada.</p>', usuario), 404)
            try:
                dados = gera_comunicacao_docx(v)
            except FileNotFoundError:
                return self.responde_html(pagina("Modelo ausente",
                    '<p class="erro">O modelo timbrado não foi encontrado na pasta "modelos". '
                    'Copie o arquivo comunicacao_servico.docx para lá e tente de novo.</p>',
                    usuario), 500)
            nome = nome_arquivo_comunicacao(v)
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument"
                                             ".wordprocessingml.document")
            self.send_header("Content-Disposition", f'attachment; filename="{nome}"')
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)
            return

        m = re.fullmatch(r"/verificacoes/(\d+)", caminho)
        if m:
            vid = int(m.group(1))
            con = conexao()
            v = con.execute("SELECT * FROM verificacoes WHERE id=?", (vid,)).fetchone()
            if not v:
                con.close()
                return self.responde_html(pagina("Não encontrada",
                    '<p class="erro">Verificação não encontrada.</p>', usuario), 404)
            vitima = (con.execute("SELECT id, nome FROM pessoas WHERE id=?",
                                  (v["pessoa_vitima_id"],)).fetchone()
                      if v["pessoa_vitima_id"] else None)
            autor = (con.execute("SELECT id, nome FROM pessoas WHERE id=?",
                                 (v["pessoa_autor_id"],)).fetchone()
                     if v["pessoa_autor_id"] else None)
            ocorrencia = (con.execute("SELECT id, tipo_crime, numero_bo FROM ocorrencias WHERE id=?",
                                      (v["ocorrencia_id"],)).fetchone()
                          if v["ocorrencia_id"] else None)
            nomes_usuarios = {u["id"]: u["nome"] for u in
                              con.execute("SELECT id, nome FROM usuarios")}
            equipe = con.execute(
                "SELECT nome, cargo, masp FROM verificacao_equipe WHERE verificacao_id=? ORDER BY nome COLLATE NOCASE",
                (vid,)).fetchall()
            fotos = con.execute(
                "SELECT * FROM verificacao_fotos WHERE verificacao_id=? ORDER BY id", (vid,)).fetchall()
            envolvidos = con.execute(
                "SELECT * FROM verificacao_envolvidos WHERE verificacao_id=? ORDER BY id", (vid,)).fetchall()
            con.close()
            return self.responde_html(pagina_verificacao_detalhe(
                usuario, csrf, v, vitima, autor, ocorrencia, nomes_usuarios, equipe, fotos, envolvidos))

        if caminho == "/configuracoes":
            if usuario["perfil"] != "admin":
                return self.redireciona("/")
            q = self.query()
            return self.responde_html(pagina_configuracoes(usuario, csrf,
                erro=q.get("erro", ""), ok=q.get("ok", "")))

        if caminho == "/minha-senha":
            q = self.query()
            return self.responde_html(pagina_alterar_senha(
                usuario, csrf, erro=q.get("erro", ""), ok=q.get("ok", "")))

        if caminho == "/usuarios":
            if usuario["perfil"] != "admin":
                return self.redireciona("/")
            con = conexao()
            lista = con.execute("SELECT * FROM usuarios ORDER BY nome").fetchall()
            con.close()
            q = self.query()
            return self.responde_html(pagina_usuarios(usuario, csrf, lista,
                                                      erro=q.get("erro", ""), ok=q.get("ok", "")))

        if caminho == "/exportar.csv":
            if usuario["perfil"] != "admin":
                return self.redireciona("/")
            con = conexao()
            audita(con, usuario["id"], "EXPORT")
            con.commit()
            registros = con.execute("SELECT * FROM pessoas ORDER BY id").fetchall()
            con.close()
            buf = io.StringIO()
            colunas = ["id"] + [c for c, _ in CAMPOS_PESSOA] + ["criado_em", "atualizado_em"]
            w = csv.writer(buf, delimiter=";")
            w.writerow(colunas)
            for p in registros:
                w.writerow([p[c] if p[c] is not None else "" for c in colunas])
            dados = buf.getvalue().encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=registros.csv")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)
            return

        return self.responde_html(pagina("Não encontrada",
            '<p class="erro">Página não encontrada.</p>', usuario), 404)

    # --- POST ----------------------------------------------------------

    def do_POST(self):
        caminho = self.caminho()

        con = conexao()
        existe_admin = con.execute("SELECT 1 FROM usuarios WHERE perfil='admin' LIMIT 1").fetchone()
        con.close()

        if caminho == "/setup" and not existe_admin:
            d = self.form()
            if not d.get("nome") or not d.get("username") or not d.get("senha"):
                return self.responde_html(pagina_setup("Preencha todos os campos."))
            if d.get("senha") != d.get("senha2"):
                return self.responde_html(pagina_setup("As senhas não coincidem."))
            if len(d.get("senha", "")) < 8:
                return self.responde_html(pagina_setup("A senha precisa ter ao menos 8 caracteres."))
            inicia_banco()
            con = conexao()
            try:
                cur = con.execute(
                    "INSERT INTO usuarios (nome, username, senha_hash, perfil, ativo, criado_em)"
                    " VALUES (?,?,?,?,1,?)",
                    (d["nome"], d["username"], hash_senha(d["senha"]), "admin", agora()))
                uid = cur.lastrowid
                audita(con, uid, "CREATE", None, "usuario", None, f"admin: {d['username']}")
                con.commit()
            except sqlite3.IntegrityError:
                con.close()
                return self.responde_html(pagina_setup("Este login já existe."))
            con.close()
            token = cria_sessao(uid)
            return self.redireciona("/", cookies=[f"sirio_sessao={token}; Path=/; HttpOnly; Secure; SameSite=Lax"])

        if caminho == "/login":
            d = self.form()
            usuario_informado = d.get("username", "")
            ip = self.client_address[0] if self.client_address else ""

            restante = bloqueio_restante(usuario_informado, ip)
            if restante:
                return self.responde_html(pagina_login(
                    f"Muitas tentativas seguidas. Aguarde {restante} minuto(s) e tente novamente."))

            con = conexao()
            u = con.execute("SELECT * FROM usuarios WHERE username=? AND ativo=1",
                            (usuario_informado,)).fetchone()
            con.close()
            if not u or not verifica_senha(d.get("senha", ""), u["senha_hash"]):
                falhas = registra_falha(usuario_informado, ip)
                # A tentativa fracassada precisa ficar registrada: sem isso não há
                # como perceber um ataque olhando a trilha.
                #
                # A auditoria exige usuario_id e a coluna não aceita nulo. Quando o
                # login digitado não existe, não há id nenhum a registrar — por isso
                # esse caso vai para o arquivo de acesso, e não para a auditoria.
                registra_login_falho(usuario_informado, ip, falhas, MAX_TENTATIVAS,
                                     u["id"] if u else None)
                restantes = MAX_TENTATIVAS - falhas
                aviso = ("Login ou senha inválidos." if restantes > 2 else
                         f"Login ou senha inválidos. Faltam {max(0, restantes)} tentativa(s) "
                         f"antes do bloqueio temporário.")
                return self.responde_html(pagina_login(aviso))

            limpa_tentativas(usuario_informado, ip)
            token = cria_sessao(u["id"])
            con = conexao()
            audita(con, u["id"], "LOGIN")
            con.commit()
            con.close()
            return self.redireciona("/", cookies=[f"sirio_sessao={token}; Path=/; HttpOnly; Secure; SameSite=Lax"])

        sessao = self.exige_login()
        if not sessao:
            return
        usuario, csrf = sessao
        pode_editar = usuario["perfil"] in ("admin", "analista")

        if caminho == "/minha-senha":
            d = self.form()
            if not self.csrf_ok(d, csrf):
                return self.redireciona("/minha-senha?erro=" + urllib.parse.quote(
                    "Não foi possível validar a solicitação. Tente novamente."))
            if not verifica_senha(d.get("senha_atual", ""), usuario["senha_hash"]):
                return self.redireciona("/minha-senha?erro=" + urllib.parse.quote(
                    "A senha atual está incorreta."))
            nova_senha = d.get("nova_senha", "")
            if len(nova_senha) < 8:
                return self.redireciona("/minha-senha?erro=" + urllib.parse.quote(
                    "A nova senha precisa ter ao menos 8 caracteres."))
            if nova_senha != d.get("nova_senha2", ""):
                return self.redireciona("/minha-senha?erro=" + urllib.parse.quote(
                    "As novas senhas não coincidem."))
            if verifica_senha(nova_senha, usuario["senha_hash"]):
                return self.redireciona("/minha-senha?erro=" + urllib.parse.quote(
                    "A nova senha deve ser diferente da atual."))
            con = conexao()
            con.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (hash_senha(nova_senha), usuario["id"]))
            audita(con, usuario["id"], "UPDATE", None, "senha", None, "alterada pelo próprio usuário")
            con.commit()
            con.close()
            token_atual = self.token_sessao()
            for token, dados_sessao in list(SESSOES.items()):
                if dados_sessao["usuario_id"] == usuario["id"] and token != token_atual:
                    SESSOES.pop(token, None)
            return self.redireciona("/minha-senha?ok=" + urllib.parse.quote(
                "Senha alterada com sucesso."))

        if caminho == "/vinculos/posicao":
            corpo = self.form_json()
            if not pode_editar or not self.csrf_ok(corpo, csrf):
                return self.responde_json({"ok": False}, 403)
            chave = (corpo.get("organizacao_chave") or "").strip()
            tipo = corpo.get("tipo")
            pessoa_id = corpo.get("pessoa_id") or None
            try:
                x = float(corpo.get("x")); y = float(corpo.get("y"))
                pessoa_id = int(pessoa_id) if (tipo == "membro" and pessoa_id) else None
            except (TypeError, ValueError):
                return self.responde_json({"ok": False}, 400)
            if not chave or tipo not in ("org", "membro"):
                return self.responde_json({"ok": False}, 400)
            con = conexao()
            existente = con.execute(
                "SELECT id FROM vinculo_posicoes WHERE organizacao_chave=? AND "
                + ("pessoa_id=?" if pessoa_id else "pessoa_id IS NULL"),
                (chave, pessoa_id) if pessoa_id else (chave,)).fetchone()
            if existente:
                con.execute("UPDATE vinculo_posicoes SET x=?, y=? WHERE id=?", (x, y, existente["id"]))
            else:
                con.execute(
                    "INSERT INTO vinculo_posicoes (organizacao_chave, pessoa_id, x, y) VALUES (?,?,?,?)",
                    (chave, pessoa_id, x, y))
            con.commit()
            con.close()
            return self.responde_json({"ok": True})

        if caminho == "/vinculos/reorganizar":
            corpo = self.form_json()
            if not pode_editar or not self.csrf_ok(corpo, csrf):
                return self.responde_json({"ok": False}, 403)
            chave = (corpo.get("organizacao_chave") or "").strip()
            if not chave:
                return self.responde_json({"ok": False}, 400)
            con = conexao()
            con.execute("DELETE FROM vinculo_posicoes WHERE organizacao_chave=?", (chave,))
            con.commit()
            con.close()
            return self.responde_json({"ok": True})

        # Importação de CSV (multipart) — somente admin
        if caminho == "/importar-csv":
            if usuario["perfil"] != "admin":
                return self.redireciona("/")
            campos, arquivos = self.form_multipart()
            if campos is None or not self.csrf_ok(campos, csrf):
                return self.redireciona("/importar-csv?erro=" + urllib.parse.quote(
                    "Falha no envio ou sessão expirada. Tente novamente."))
            if not arquivos:
                return self.redireciona("/importar-csv?erro=" + urllib.parse.quote(
                    "Selecione um arquivo CSV."))
            nome_arq, conteudo = arquivos[0]
            registros, avisos = parse_csv_pessoas(conteudo)
            if not registros:
                return self.redireciona("/importar-csv?erro=" + urllib.parse.quote(
                    "Nenhum registro válido encontrado (confira se a coluna 'nome' existe)."))
            con = conexao()
            criados = 0
            for reg in registros:
                colunas = ", ".join(reg.keys())
                marcas = ", ".join("?" for _ in reg)
                cur = con.execute(
                    f"INSERT INTO pessoas ({colunas}, criado_em, criado_por) VALUES ({marcas}, ?, ?)",
                    list(reg.values()) + [agora(), usuario["id"]])
                audita(con, usuario["id"], "CREATE", cur.lastrowid, "origem", None, f"Importado de CSV ({nome_arq})")
                criados += 1
            con.commit()
            con.close()
            resumo = f"{criados} registro(s) importado(s)."
            if avisos:
                resumo += f" {len(avisos)} linha(s) ignorada(s)."
            return self.redireciona("/importar-csv?ok=" + urllib.parse.quote(resumo))

        # Upload de imagens (multipart) — tratado antes do parser genérico
        m = re.fullmatch(r"/pessoas/(\d+)/fotos", caminho)
        if m:
            pid = int(m.group(1))
            if not pode_editar:
                return self.redireciona(f"/pessoas/{pid}")
            campos, arquivos = self.form_multipart()
            if campos is None or not self.csrf_ok(campos, csrf):
                return self.redireciona(f"/pessoas/{pid}/editar")
            tipo = campos.get("tipo") if campos.get("tipo") in ("fotografia", "tatuagem") else "fotografia"
            legenda = campos.get("legenda") or None
            con = conexao()
            for nome_arq, conteudo in arquivos:
                if len(conteudo) > TAMANHO_MAX_FOTO:
                    continue
                ext = os.path.splitext(nome_arq)[1].lower()
                if ext not in TIPOS_IMAGEM:
                    continue
                _, assinaturas = TIPOS_IMAGEM[ext]
                if not any(conteudo.startswith(s) for s in assinaturas):
                    continue
                nome_salvo = secrets.token_hex(16) + ext
                with open(os.path.join(PASTA_FOTOS, nome_salvo), "wb") as f:
                    f.write(conteudo)
                cur = con.execute(
                    "INSERT INTO fotos (pessoa_id, tipo, legenda, arquivo, criado_em, criado_por)"
                    " VALUES (?,?,?,?,?,?)", (pid, tipo, legenda, nome_salvo, agora(), usuario["id"]))
                audita(con, usuario["id"], "FOTO_ADD", pid, "foto", None, tipo)
            con.commit()
            con.close()
            return self.redireciona(f"/pessoas/{pid}/editar")

        m = re.fullmatch(r"/fotos/(\d+)/excluir", caminho)
        if m and pode_editar:
            fid = int(m.group(1))
            con = conexao()
            f = con.execute("SELECT * FROM fotos WHERE id=?", (fid,)).fetchone()
            if f:
                audita(con, usuario["id"], "FOTO_DEL", f["pessoa_id"], "foto", f["tipo"], None)
                con.execute("DELETE FROM fotos WHERE id=?", (fid,))
                con.commit()
                try:
                    os.remove(os.path.join(PASTA_FOTOS, f["arquivo"]))
                except OSError:
                    pass
            pid = f["pessoa_id"] if f else None
            con.close()
            return self.redireciona(f"/pessoas/{pid}/editar" if pid else "/")

        # Upload do PDF do BO (multipart) — tratado antes do parser genérico
        if caminho == "/importar":
            if usuario["perfil"] not in ("admin", "analista") or not PDF_DISPONIVEL:
                return self.redireciona("/")
            campos, arquivos = self.form_multipart()
            if campos is None or not self.csrf_ok(campos, csrf):
                return self.responde_html(pagina_importar_upload(usuario, csrf,
                    "Falha no envio ou sessão expirada. Tente novamente."))
            if not arquivos:
                return self.responde_html(pagina_importar_upload(usuario, csrf,
                    "Selecione um arquivo PDF."))
            nome_arq, conteudo = arquivos[0]
            if not nome_arq.lower().endswith(".pdf") or not conteudo.startswith(b"%PDF"):
                return self.responde_html(pagina_importar_upload(usuario, csrf,
                    "O arquivo enviado não é um PDF válido."))
            tmp = os.path.join(PASTA, f".bo_tmp_{secrets.token_hex(8)}.pdf")
            try:
                with open(tmp, "wb") as f:
                    f.write(conteudo)
                resultado = parse_bo_pdf(tmp)
            except Exception:
                return self.responde_html(pagina_importar_upload(usuario, csrf,
                    "Não consegui ler este PDF. Verifique se é um BO do SISP/PCMG."))
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            for env in resultado["envolvidos"]:
                env["match"] = encontra_pessoa_existente(env.get("cpf"), env.get("rg"), env.get("nome"))
            return self.responde_html(pagina_importar_revisao(
                usuario, csrf, resultado["reds"], resultado["envolvidos"],
                resultado["historico"], resultado["local_fato"], resultado["materiais"],
                resultado.get("diagnostico")))

        # Fotos opcionais da averiguação. A verificação já precisa existir para
        # que cada imagem tenha um registro pai e possa ser excluída com segurança.
        m = re.fullmatch(r"/verificacoes/(\d+)/fotos", caminho)
        if m:
            vid = int(m.group(1))
            if not pode_editar:
                return self.redireciona(f"/verificacoes/{vid}")
            campos, arquivos = self.form_multipart()
            if campos is None or not self.csrf_ok(campos, csrf):
                return self.redireciona(f"/verificacoes/{vid}")
            con = conexao()
            existe = con.execute("SELECT 1 FROM verificacoes WHERE id=?", (vid,)).fetchone()
            if not existe:
                con.close()
                return self.redireciona("/verificacoes")
            legenda = campos.get("legenda") or None
            for nome_arq, conteudo in arquivos:
                if len(conteudo) > TAMANHO_MAX_FOTO:
                    continue
                ext = os.path.splitext(nome_arq)[1].lower()
                if ext not in TIPOS_IMAGEM or not any(conteudo.startswith(s) for s in TIPOS_IMAGEM[ext][1]):
                    continue
                nome_salvo = secrets.token_hex(16) + ext
                with open(os.path.join(PASTA_FOTOS, nome_salvo), "wb") as f:
                    f.write(conteudo)
                con.execute("INSERT INTO verificacao_fotos (verificacao_id, legenda, arquivo, criado_em, criado_por) VALUES (?,?,?,?,?)",
                            (vid, legenda, nome_salvo, agora(), usuario["id"]))
                audita(con, usuario["id"], "FOTO_ADD", None, "verificacao", None,
                       f"Foto adicionada à verificação #{vid}")
            con.commit()
            con.close()
            return self.redireciona(f"/verificacoes/{vid}")

        m = re.fullmatch(r"/verificacoes/fotos/(\d+)/excluir", caminho)
        if m and pode_editar:
            fid = int(m.group(1))
            campos = self.form()
            if not self.csrf_ok(campos, csrf):
                return self.redireciona("/verificacoes")
            con = conexao()
            foto = con.execute("SELECT * FROM verificacao_fotos WHERE id=?", (fid,)).fetchone()
            if foto:
                con.execute("DELETE FROM verificacao_fotos WHERE id=?", (fid,))
                audita(con, usuario["id"], "FOTO_DEL", None, "verificacao", foto["arquivo"],
                       f"Foto removida da verificação #{foto['verificacao_id']}")
                con.commit()
                try:
                    os.remove(os.path.join(PASTA_FOTOS, foto["arquivo"]))
                except OSError:
                    pass
            con.close()
            return self.redireciona(f"/verificacoes/{foto['verificacao_id']}" if foto else "/verificacoes")

        d = self.form()
        d["equipe_ids"] = self.form_multi("equipe_ids")

        # Verificação única de CSRF para todas as rotas daqui para baixo. As
        # rotas acima (upload de foto, importação, vínculos) leem o corpo de
        # forma própria e já conferem o token individualmente.
        if not self.csrf_ok(d, csrf):
            return self.responde_html(pagina(
                "Solicitação não validada",
                '<p class="erro">Não foi possível validar a solicitação. Isso costuma '
                'acontecer quando a página ficou aberta por muito tempo ou a sessão expirou.</p>'
                '<p>Volte, recarregue a página e refaça a operação.</p>'
                '<div class="acoes"><a class="botao" href="/">Voltar ao início</a></div>',
                usuario), 400)

        if caminho == "/pessoas/nova" and pode_editar:
            if not d.get("nome"):
                return self.responde_html(pagina_form(usuario, csrf, d, erro="Informe o nome completo."))
            erro = valida_pessoa(d)
            if erro:
                return self.responde_html(pagina_form(usuario, csrf, d, erro=erro))
            valores = {c: (d.get(c) or None) for c, _ in CAMPOS_PESSOA}
            valores["status"] = valores["status"] or "em_verificacao"
            valores["preso"] = valores["preso"] or "nao"
            con = conexao()
            colunas = ", ".join(valores.keys())
            marcas = ", ".join("?" for _ in valores)
            cur = con.execute(
                f"INSERT INTO pessoas ({colunas}, data_atualizacao_status_prisional, criado_em, criado_por)"
                f" VALUES ({marcas}, ?, ?, ?)",
                list(valores.values()) + [agora(), agora(), usuario["id"]])
            audita(con, usuario["id"], "CREATE", cur.lastrowid)
            con.commit()
            con.close()
            return self.redireciona(f"/pessoas/{cur.lastrowid}")

        m = re.fullmatch(r"/pessoas/(\d+)/editar", caminho)
        if m and pode_editar:
            pid = int(m.group(1))
            con = conexao()
            p = con.execute("SELECT * FROM pessoas WHERE id=?", (pid,)).fetchone()
            if not p:
                con.close()
                return self.redireciona("/")
            if not d.get("nome"):
                con.close()
                return self.responde_html(pagina_form(usuario, csrf, d, pid, erro="Informe o nome completo."))
            erro = valida_pessoa(d)
            if erro:
                con.close()
                return self.responde_html(pagina_form(usuario, csrf, d, pid, erro=erro))
            mudou = 0
            for c, _ in CAMPOS_PESSOA:
                novo = d.get(c) or None
                if c == "preso":
                    novo = novo or "nao"
                # status é NOT NULL no banco: sem este padrão, um envio sem o
                # campo gravaria NULL e derrubaria a conexão sem página de erro.
                if c == "status":
                    novo = novo if novo in STATUS_LABEL else (p["status"] or "em_verificacao")
                anterior = p[c]
                if (anterior or None) != (novo or None):
                    audita(con, usuario["id"], "UPDATE", pid, c, anterior, novo)
                    con.execute(f"UPDATE pessoas SET {c}=? WHERE id=?", (novo, pid))
                    mudou += 1
                    if c == "preso":
                        con.execute(
                            "UPDATE pessoas SET data_atualizacao_status_prisional=? WHERE id=?",
                            (agora(), pid))
                        audita(con, usuario["id"], "UPDATE", pid, "data_atualizacao_status_prisional",
                               p["data_atualizacao_status_prisional"], agora())
            if mudou:
                con.execute("UPDATE pessoas SET atualizado_em=?, atualizado_por=? WHERE id=?",
                            (agora(), usuario["id"], pid))
            con.commit()
            con.close()
            return self.redireciona(f"/pessoas/{pid}")

        m = re.fullmatch(r"/pessoas/(\d+)/status", caminho)
        if m and pode_editar:
            pid = int(m.group(1))
            novo = d.get("status")
            if novo in STATUS_LABEL:
                con = conexao()
                p = con.execute("SELECT status FROM pessoas WHERE id=?", (pid,)).fetchone()
                if p and p["status"] != novo:
                    audita(con, usuario["id"], "STATUS", pid, "status", p["status"], novo)
                    con.execute("UPDATE pessoas SET status=?, atualizado_em=?, atualizado_por=? WHERE id=?",
                               (novo, agora(), usuario["id"], pid))
                    con.commit()
                con.close()
            return self.redireciona(f"/pessoas/{pid}")

        m = re.fullmatch(r"/pessoas/(\d+)/excluir", caminho)
        if m and usuario["perfil"] == "admin":
            pid = int(m.group(1))
            con = conexao()
            p = con.execute("SELECT nome FROM pessoas WHERE id=?", (pid,)).fetchone()
            if p:
                audita(con, usuario["id"], "DELETE", pid, "pessoa", p["nome"], None)
                arquivos = exclui_pessoa_em_cascata(con, pid)
                con.commit()
                # Só depois do commit os arquivos saem do disco: se a transação
                # falhasse, as fotos continuariam correspondendo ao registro.
                for arquivo in arquivos:
                    try:
                        os.remove(os.path.join(PASTA_FOTOS, arquivo))
                    except OSError:
                        pass
            con.close()
            return self.redireciona("/")

        m = re.fullmatch(r"/pessoas/(\d+)/biqueiras", caminho)
        if m and pode_editar:
            pid = int(m.group(1))
            con = conexao()
            pessoa = con.execute("SELECT id FROM pessoas WHERE id=?", (pid,)).fetchone()
            if pessoa and (d.get("local") or d.get("endereco")):
                con.execute(
                    "INSERT INTO biqueiras (pessoa_id, local, endereco, bairro, cidade, lat, lon,"
                    " observacoes, criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (pid, d.get("local") or None, d.get("endereco") or None, d.get("bairro") or None,
                     d.get("cidade") or None, _num_ou_none(d.get("lat")), _num_ou_none(d.get("lon")),
                     d.get("observacoes") or None, agora(), usuario["id"]))
                audita(con, usuario["id"], "CREATE", pid, "biqueira", None, d.get("local") or d.get("endereco"))
                con.commit()
            con.close()
            return self.redireciona(f"/pessoas/{pid}")

        m = re.fullmatch(r"/biqueiras/(\d+)/excluir", caminho)
        if m and pode_editar:
            bid = int(m.group(1))
            con = conexao()
            b = con.execute("SELECT * FROM biqueiras WHERE id=?", (bid,)).fetchone()
            if b:
                audita(con, usuario["id"], "DELETE", b["pessoa_id"], "biqueira",
                       b["local"] or b["endereco"], None)
                con.execute("DELETE FROM biqueiras WHERE id=?", (bid,))
                con.commit()
            pid = b["pessoa_id"] if b else None
            con.close()
            return self.redireciona(f"/pessoas/{pid}" if pid else "/")

        if caminho == "/pessoas/mesclar/executar" and usuario["perfil"] == "admin":
            try:
                pa_id = int(d.get("pessoa_a_id", "0"))
                pb_id = int(d.get("pessoa_b_id", "0"))
            except ValueError:
                return self.redireciona("/pessoas/mesclar")
            if not pa_id or not pb_id or pa_id == pb_id:
                return self.redireciona("/pessoas/mesclar")
            con = conexao()
            pa = con.execute("SELECT * FROM pessoas WHERE id=?", (pa_id,)).fetchone()
            pb = con.execute("SELECT * FROM pessoas WHERE id=?", (pb_id,)).fetchone()
            if not pa or not pb:
                con.close()
                return self.redireciona("/pessoas/mesclar")

            valores_finais = {c: (d.get(c) or None) for c, _ in CAMPOS_PESSOA}
            valores_finais["status"] = valores_finais["status"] or "em_verificacao"
            valores_finais["preso"] = valores_finais["preso"] or "nao"
            if not valores_finais.get("nome"):
                con.close()
                return self.responde_html(pagina_pessoas_mesclar_comparar(usuario, csrf, pa, pb))

            for campo, _ in CAMPOS_PESSOA:
                anterior, novo = pa[campo], valores_finais[campo]
                if (anterior or None) != (novo or None):
                    audita(con, usuario["id"], "UPDATE", pa_id, campo, anterior, novo)
                    if campo == "preso":
                        audita(con, usuario["id"], "UPDATE", pa_id, "data_atualizacao_status_prisional",
                               pa["data_atualizacao_status_prisional"], agora())
            sets = ", ".join(f"{c}=?" for c, _ in CAMPOS_PESSOA)
            valores_sql = [valores_finais[c] for c, _ in CAMPOS_PESSOA]
            if (pa["preso"] or None) != (valores_finais["preso"] or None):
                sets += ", data_atualizacao_status_prisional=?"
                valores_sql.append(agora())
            con.execute(f"UPDATE pessoas SET {sets}, atualizado_em=?, atualizado_por=? WHERE id=?",
                       valores_sql + [agora(), usuario["id"], pa_id])

            con.execute("UPDATE fotos SET pessoa_id=? WHERE pessoa_id=?", (pa_id, pb_id))
            con.execute("UPDATE materiais_apreendidos SET pessoa_id=? WHERE pessoa_id=?", (pa_id, pb_id))
            con.execute("UPDATE ocorrencias SET pessoa_autor_id=? WHERE pessoa_autor_id=?", (pa_id, pb_id))
            con.execute("UPDATE boletim_pessoa SET pessoa_id=? WHERE pessoa_id=?", (pa_id, pb_id))
            duplicados = con.execute(
                "SELECT boletim_id, COUNT(*) c, MIN(id) manter FROM boletim_pessoa "
                "WHERE pessoa_id=? GROUP BY boletim_id HAVING c > 1", (pa_id,)).fetchall()
            for dup in duplicados:
                con.execute("DELETE FROM boletim_pessoa WHERE boletim_id=? AND pessoa_id=? AND id!=?",
                           (dup["boletim_id"], pa_id, dup["manter"]))
            con.execute("UPDATE auditoria SET pessoa_id=? WHERE pessoa_id=?", (pa_id, pb_id))
            con.execute("UPDATE biqueiras SET pessoa_id=? WHERE pessoa_id=?", (pa_id, pb_id))

            audita(con, usuario["id"], "MERGE", pa_id, "mesclagem",
                   f"Registro #{pb_id} ({pb['nome']})", f"Absorvido pelo registro #{pa_id}")
            con.execute("DELETE FROM pessoas WHERE id=?", (pb_id,))
            con.commit()
            con.close()
            return self.redireciona(f"/pessoas/{pa_id}")

        def _valores_ocorrencia(d):
            return {
                "tipo_crime": d.get("tipo_crime") or None,
                "numero_bo": d.get("numero_bo") or None,
                "data_fato": d.get("data_fato") or None,
                "endereco_fato": d.get("endereco_fato") or None,
                "cidade_fato": d.get("cidade_fato") or None,
                "bairro_fato": d.get("bairro_fato") or None,
                "lat_fato": _num_ou_none(d.get("lat_fato")),
                "lon_fato": _num_ou_none(d.get("lon_fato")),
                "pessoa_autor_id": int(d["pessoa_autor_id"]) if d.get("pessoa_autor_id", "").isdigit() else None,
                "nome_autor": d.get("nome_autor") or None,
                "endereco_autor": d.get("endereco_autor") or None,
                "lat_autor": _num_ou_none(d.get("lat_autor")),
                "lon_autor": _num_ou_none(d.get("lon_autor")),
                "nome_vitima": d.get("nome_vitima") or None,
                "endereco_vitima": d.get("endereco_vitima") or None,
                "lat_vitima": _num_ou_none(d.get("lat_vitima")),
                "lon_vitima": _num_ou_none(d.get("lon_vitima")),
                "observacoes": d.get("observacoes") or None,
            }

        if caminho == "/ocorrencias/nova" and pode_editar:
            erro = valida_ocorrencia(d)
            if erro:
                return self.responde_html(pagina_ocorrencia_form(usuario, csrf, d, erro=erro))
            valores = _valores_ocorrencia(d)
            con = conexao()
            colunas = ", ".join(valores.keys())
            marcas = ", ".join("?" for _ in valores)
            cur = con.execute(
                f"INSERT INTO ocorrencias ({colunas}, criado_em, criado_por) VALUES ({marcas}, ?, ?)",
                list(valores.values()) + [agora(), usuario["id"]])
            audita(con, usuario["id"], "CREATE", None, "ocorrencia", None, valores.get("tipo_crime"))
            con.commit()
            oid = cur.lastrowid
            con.close()
            return self.redireciona(f"/ocorrencias/{oid}")

        m = re.fullmatch(r"/ocorrencias/(\d+)/editar", caminho)
        if m and pode_editar:
            oid = int(m.group(1))
            con = conexao()
            o = con.execute("SELECT * FROM ocorrencias WHERE id=?", (oid,)).fetchone()
            if not o:
                con.close()
                return self.redireciona("/ocorrencias")
            erro = valida_ocorrencia(d)
            if erro:
                con.close()
                return self.responde_html(pagina_ocorrencia_form(usuario, csrf, d, oid, erro=erro))
            valores = _valores_ocorrencia(d)
            for c, novo in valores.items():
                anterior = o[c]
                if (anterior or None) != (novo or None):
                    audita(con, usuario["id"], "UPDATE", None, f"ocorrencia.{c}", anterior, novo)
            sets = ", ".join(f"{c}=?" for c in valores)
            con.execute(f"UPDATE ocorrencias SET {sets}, atualizado_em=?, atualizado_por=? WHERE id=?",
                       list(valores.values()) + [agora(), usuario["id"], oid])
            con.commit()
            con.close()
            return self.redireciona(f"/ocorrencias/{oid}")

        m = re.fullmatch(r"/ocorrencias/(\d+)/excluir", caminho)
        if m and usuario["perfil"] == "admin":
            oid = int(m.group(1))
            con = conexao()
            o = con.execute("SELECT tipo_crime FROM ocorrencias WHERE id=?", (oid,)).fetchone()
            if o:
                audita(con, usuario["id"], "DELETE", None, "ocorrencia", o["tipo_crime"], None)
                con.execute("DELETE FROM ocorrencia_testemunhas WHERE ocorrencia_id=?", (oid,))
                con.execute("UPDATE materiais_apreendidos SET ocorrencia_id=NULL WHERE ocorrencia_id=?", (oid,))
                con.execute("DELETE FROM ocorrencias WHERE id=?", (oid,))
                con.commit()
            con.close()
            return self.redireciona("/ocorrencias")

        m = re.fullmatch(r"/ocorrencias/(\d+)/testemunhas", caminho)
        if m and pode_editar:
            oid = int(m.group(1))
            if d.get("nome") or d.get("endereco"):
                con = conexao()
                con.execute(
                    "INSERT INTO ocorrencia_testemunhas (ocorrencia_id, nome, endereco, lat, lon)"
                    " VALUES (?,?,?,?,?)",
                    (oid, d.get("nome") or None, d.get("endereco") or None,
                     _num_ou_none(d.get("lat")), _num_ou_none(d.get("lon"))))
                audita(con, usuario["id"], "CREATE", None, "testemunha", None, d.get("nome"))
                con.commit()
                con.close()
            return self.redireciona(f"/ocorrencias/{oid}")

        m = re.fullmatch(r"/testemunhas/(\d+)/excluir", caminho)
        if m and pode_editar:
            tid = int(m.group(1))
            con = conexao()
            t = con.execute("SELECT * FROM ocorrencia_testemunhas WHERE id=?", (tid,)).fetchone()
            if t:
                audita(con, usuario["id"], "DELETE", None, "testemunha", t["nome"], None)
                con.execute("DELETE FROM ocorrencia_testemunhas WHERE id=?", (tid,))
                con.commit()
            oid = t["ocorrencia_id"] if t else None
            con.close()
            return self.redireciona(f"/ocorrencias/{oid}" if oid else "/ocorrencias")

        m = re.fullmatch(r"/ocorrencias/(\d+)/materiais", caminho)
        if m and pode_editar:
            oid = int(m.group(1))
            if d.get("objeto") or d.get("categoria"):
                pid = int(d["pessoa_id"]) if d.get("pessoa_id", "").isdigit() else None
                con = conexao()
                con.execute(
                    "INSERT INTO materiais_apreendidos (ocorrencia_id, pessoa_id, categoria, objeto,"
                    " quantidade, marca, modelo, cor, situacao, numero_lacre, observacoes,"
                    " criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (oid, pid, d.get("categoria") or None, d.get("objeto") or None,
                     d.get("quantidade") or "1", d.get("marca") or None, d.get("modelo") or None,
                     d.get("cor") or None, d.get("situacao") or "Apreendido", d.get("numero_lacre") or None,
                     d.get("observacoes") or None, agora(), usuario["id"]))
                audita(con, usuario["id"], "CREATE", pid, "material", None, d.get("objeto"))
                con.commit()
                con.close()
            return self.redireciona(f"/ocorrencias/{oid}")

        if caminho == "/materiais/novo" and pode_editar:
            if d.get("objeto") or d.get("categoria"):
                oid = int(d["ocorrencia_id"]) if d.get("ocorrencia_id", "").isdigit() else None
                pid = int(d["pessoa_id"]) if d.get("pessoa_id", "").isdigit() else None
                con = conexao()
                con.execute(
                    "INSERT INTO materiais_apreendidos (ocorrencia_id, pessoa_id, categoria, objeto,"
                    " quantidade, marca, modelo, cor, situacao, numero_lacre, cidade, bairro, observacoes,"
                    " criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (oid, pid, d.get("categoria") or None, d.get("objeto") or None,
                     d.get("quantidade") or "1", d.get("marca") or None, d.get("modelo") or None,
                     d.get("cor") or None, d.get("situacao") or "Apreendido", d.get("numero_lacre") or None,
                     d.get("cidade") or None, d.get("bairro") or None, d.get("observacoes") or None,
                     agora(), usuario["id"]))
                audita(con, usuario["id"], "CREATE", pid, "material", None, d.get("objeto"))
                con.commit()
                con.close()
            return self.redireciona("/materiais")

        m = re.fullmatch(r"/materiais/(\d+)/excluir", caminho)
        if m and pode_editar:
            mid = int(m.group(1))
            con = conexao()
            mat = con.execute("SELECT * FROM materiais_apreendidos WHERE id=?", (mid,)).fetchone()
            if mat:
                audita(con, usuario["id"], "DELETE", mat["pessoa_id"], "material", mat["objeto"], None)
                con.execute("DELETE FROM materiais_apreendidos WHERE id=?", (mid,))
                con.commit()
            oid = mat["ocorrencia_id"] if mat else None
            con.close()
            return self.redireciona(f"/ocorrencias/{oid}" if oid else "/materiais")

        if caminho == "/importar/salvar" and pode_editar:
            try:
                total = int(d.get("total", "0"))
            except ValueError:
                total = 0
            try:
                total_materiais = int(d.get("total_materiais", "0"))
            except ValueError:
                total_materiais = 0
            reds = (d.get("reds") or "").strip()
            org = d.get("org_comum") or None
            cargo = d.get("cargo_comum") or None
            fonte = d.get("fonte_comum") if d.get("fonte_comum") in lista_ativa('fonte_informacao') else None
            grau = d.get("grau_comum") if d.get("grau_comum") in lista_ativa('grau_confiabilidade') else None
            status = d.get("status_comum") if d.get("status_comum") in STATUS_LABEL else "em_verificacao"
            historico = (d.get("historico") or "").strip()
            ref_bo = f"Importado do BO/REDS {reds}." if reds else "Importado de BO."
            observacao_pessoa = ref_bo

            con = conexao()
            criados = []
            processados = []
            posicao_para_pessoa_id = {}
            autor_nome = autor_endereco = None
            autor_pessoa_id = None
            for i in range(total):
                tipo_env = d.get(f"tipo_envolvimento_{i}") or ""
                if tipo_env == "Autor":
                    autor_nome = d.get(f"nome_{i}") or None
                    autor_endereco = d.get(f"endereco_{i}") or None
                if d.get(f"incluir_{i}") != "1":
                    continue
                nome = (d.get(f"nome_{i}") or "").strip()
                if not nome:
                    continue

                usar_existente = d.get(f"modo_{i}") == "existente"
                match_id_str = d.get(f"match_pessoa_id_{i}") or ""
                if usar_existente and match_id_str.isdigit():
                    pid_existente = int(match_id_str)
                    existente = con.execute("SELECT * FROM pessoas WHERE id=?", (pid_existente,)).fetchone()
                    if existente:
                        candidatos = {
                            "alcunha": d.get(f"alcunha_{i}") or None,
                            "rg": d.get(f"rg_{i}") or None,
                            "cpf": d.get(f"cpf_{i}") or None,
                            "data_nascimento": d.get(f"data_nascimento_{i}") or None,
                            "nome_mae": d.get(f"nome_mae_{i}") or None,
                            "nome_pai": d.get(f"nome_pai_{i}") or None,
                            "endereco": d.get(f"endereco_{i}") or None,
                            "organizacao": org,
                            "cargo_orcrim": cargo,
                            "fonte_informacao": fonte,
                            "grau_confiabilidade": grau,
                        }
                        for campo, novo_valor in candidatos.items():
                            if novo_valor and not existente[campo]:
                                con.execute(f"UPDATE pessoas SET {campo}=? WHERE id=?", (novo_valor, pid_existente))
                                audita(con, usuario["id"], "UPDATE", pid_existente, campo, None, novo_valor)
                        obs_existente = existente["observacoes"] or ""
                        nova_obs = (obs_existente + ("\n" if obs_existente else "") + ref_bo)
                        con.execute("UPDATE pessoas SET observacoes=?, atualizado_em=?, atualizado_por=? WHERE id=?",
                                   (nova_obs, agora(), usuario["id"], pid_existente))
                        audita(con, usuario["id"], "UPDATE", pid_existente, "origem", None,
                               f"Dados incluídos a partir do {ref_bo}")
                        posicao_para_pessoa_id[i] = pid_existente
                        processados.append(pid_existente)
                        if tipo_env == "Autor":
                            autor_pessoa_id = pid_existente
                        continue

                valores = {
                    "nome": nome,
                    "alcunha": d.get(f"alcunha_{i}") or None,
                    "rg": d.get(f"rg_{i}") or None,
                    "cpf": d.get(f"cpf_{i}") or None,
                    "data_nascimento": d.get(f"data_nascimento_{i}") or None,
                    "nome_mae": d.get(f"nome_mae_{i}") or None,
                    "nome_pai": d.get(f"nome_pai_{i}") or None,
                    "endereco": d.get(f"endereco_{i}") or None,
                    "organizacao": org,
                    "cargo_orcrim": cargo,
                    "fonte_informacao": fonte,
                    "grau_confiabilidade": grau,
                    "observacoes": observacao_pessoa,
                    "status": status,
                }
                colunas = ", ".join(valores.keys())
                marcas = ", ".join("?" for _ in valores)
                cur = con.execute(
                    f"INSERT INTO pessoas ({colunas}, criado_em, criado_por) VALUES ({marcas}, ?, ?)",
                    list(valores.values()) + [agora(), usuario["id"]])
                audita(con, usuario["id"], "CREATE", cur.lastrowid, "origem", None, ref_bo)
                criados.append(cur.lastrowid)
                processados.append(cur.lastrowid)
                posicao_para_pessoa_id[i] = cur.lastrowid
                if tipo_env == "Autor":
                    autor_pessoa_id = cur.lastrowid

            ocorrencia_id = None
            if d.get("criar_ocorrencia") == "1":
                valores_oc = {
                    "tipo_crime": d.get("oc_tipo_crime") or None,
                    "numero_bo": reds or None,
                    "data_fato": d.get("oc_data_fato") or None,
                    "endereco_fato": d.get("oc_endereco_fato") or None,
                    "cidade_fato": d.get("oc_cidade_fato") or None,
                    "bairro_fato": d.get("oc_bairro_fato") or None,
                    "lat_fato": _num_ou_none(d.get("oc_lat_fato")),
                    "lon_fato": _num_ou_none(d.get("oc_lon_fato")),
                    "pessoa_autor_id": autor_pessoa_id,
                    "nome_autor": autor_nome,
                    "endereco_autor": autor_endereco,
                    "lat_autor": None, "lon_autor": None,
                    "nome_vitima": None, "endereco_vitima": None, "lat_vitima": None, "lon_vitima": None,
                    "observacoes": ref_bo,
                }
                colunas_oc = ", ".join(valores_oc.keys())
                marcas_oc = ", ".join("?" for _ in valores_oc)
                cur_oc = con.execute(
                    f"INSERT INTO ocorrencias ({colunas_oc}, criado_em, criado_por) VALUES ({marcas_oc}, ?, ?)",
                    list(valores_oc.values()) + [agora(), usuario["id"]])
                audita(con, usuario["id"], "CREATE", None, "ocorrencia", None,
                       f"Importada do BO/REDS {reds}" if reds else "Importada de BO")
                ocorrencia_id = cur_oc.lastrowid

            if historico or reds:
                cur_bol = con.execute(
                    "INSERT INTO boletins (reds, data_fato, historico, ocorrencia_id, criado_em, criado_por)"
                    " VALUES (?,?,?,?,?,?)",
                    (reds or None, d.get("oc_data_fato") or None, historico or None,
                     ocorrencia_id, agora(), usuario["id"]))
                boletim_id = cur_bol.lastrowid
                for i, pessoa_id in posicao_para_pessoa_id.items():
                    con.execute(
                        "INSERT INTO boletim_pessoa (boletim_id, pessoa_id, tipo_envolvimento) VALUES (?,?,?)",
                        (boletim_id, pessoa_id, d.get(f"tipo_envolvimento_{i}") or None))

            vd_caso_id = None
            if d.get("criar_caso_vd") == "1":
                observacao_vd = (f"Caso criado automaticamente a partir da importação do BO/REDS {reds}."
                                 if reds else "Caso criado automaticamente a partir da importação de um BO.")
                valores_vd = {
                    "numero_reds": reds or None,
                    "municipio": d.get("oc_cidade_fato") or None,
                    "local_fato": d.get("oc_endereco_fato") or None,
                    "data_hora_fato": d.get("oc_data_fato") or None,
                    "servidor_responsavel_id": usuario["id"],
                    "origem_demanda": "Boletim de Ocorrência",
                    "situacao": "atendimento_iniciado",
                    "observacoes": observacao_vd,
                }
                colunas_vd = ", ".join(valores_vd.keys())
                marcas_vd = ", ".join("?" for _ in valores_vd)
                cur_vd = con.execute(
                    f"INSERT INTO vd_casos ({colunas_vd}, criado_em, criado_por) VALUES ({marcas_vd}, ?, ?)",
                    list(valores_vd.values()) + [agora(), usuario["id"]])
                vd_caso_id = cur_vd.lastrowid
                audita(con, usuario["id"], "CREATE", None, "vd_caso", None,
                       f"Caso VD #{vd_caso_id} criado a partir do BO/REDS {reds}" if reds else f"Caso VD #{vd_caso_id}")
                vd_registra_evento(con, vd_caso_id, "criacao_caso",
                                   f"Caso criado automaticamente ao importar BO/REDS {reds}" if reds
                                   else "Caso criado automaticamente ao importar BO", usuario["id"])
                if ocorrencia_id:
                    con.execute(
                        "INSERT INTO vd_caso_ocorrencias (caso_id, ocorrencia_id, criado_em, criado_por)"
                        " VALUES (?,?,?,?)", (vd_caso_id, ocorrencia_id, agora(), usuario["id"]))
                    vd_registra_evento(con, vd_caso_id, "vinculo_ocorrencia",
                                       f"Ocorrência #{ocorrencia_id} vinculada automaticamente (mesmo BO)", usuario["id"])
                for i, pessoa_id in posicao_para_pessoa_id.items():
                    papel_vd = d.get(f"papel_vd_{i}") or ""
                    if papel_vd not in VD_PAPEL_LABEL:
                        continue
                    ja_existe = con.execute(
                        "SELECT 1 FROM vd_caso_pessoas WHERE caso_id=? AND pessoa_id=? AND papel=?",
                        (vd_caso_id, pessoa_id, papel_vd)).fetchone()
                    if ja_existe:
                        continue
                    con.execute(
                        "INSERT INTO vd_caso_pessoas (caso_id, pessoa_id, papel, criado_em, criado_por)"
                        " VALUES (?,?,?,?,?)", (vd_caso_id, pessoa_id, papel_vd, agora(), usuario["id"]))
                    nome_pessoa = con.execute("SELECT nome FROM pessoas WHERE id=?", (pessoa_id,)).fetchone()
                    vd_registra_evento(con, vd_caso_id, "vinculo_pessoa",
                                       f"{nome_pessoa['nome'] if nome_pessoa else 'Pessoa'} vinculado(a) "
                                       f"automaticamente como {VD_PAPEL_LABEL[papel_vd]} (importação de BO)",
                                       usuario["id"])

            materiais_criados = 0
            for j in range(total_materiais):
                if d.get(f"mat_incluir_{j}") != "1":
                    continue
                objeto = d.get(f"mat_objeto_{j}") or None
                if not objeto:
                    continue
                envolv_nr = d.get(f"mat_envolv_{j}") or ""
                idx_pessoa = int(envolv_nr) - 1 if envolv_nr.isdigit() else None
                pessoa_id_mat = posicao_para_pessoa_id.get(idx_pessoa) if idx_pessoa is not None else None
                con.execute(
                    "INSERT INTO materiais_apreendidos (ocorrencia_id, pessoa_id, categoria, objeto,"
                    " quantidade, situacao, marca, modelo, cor, observacoes, criado_em, criado_por)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ocorrencia_id, pessoa_id_mat, d.get(f"mat_categoria_{j}") or None, objeto,
                     d.get(f"mat_quantidade_{j}") or "1", d.get(f"mat_situacao_{j}") or "Apreendido",
                     d.get(f"mat_marca_{j}") or None, d.get(f"mat_modelo_{j}") or None,
                     d.get(f"mat_cor_{j}") or None, d.get(f"mat_observacoes_{j}") or None,
                     agora(), usuario["id"]))
                audita(con, usuario["id"], "CREATE", pessoa_id_mat, "material", None,
                       f"Importado do BO/REDS {reds}" if reds else "Importado de BO")
                materiais_criados += 1

            con.commit()
            con.close()
            if vd_caso_id:
                return self.redireciona(f"/vd/{vd_caso_id}")
            if ocorrencia_id:
                return self.redireciona(f"/ocorrencias/{ocorrencia_id}")
            if len(processados) == 1:
                return self.redireciona(f"/pessoas/{processados[0]}")
            return self.redireciona("/")

        if caminho == "/vd/novo" and pode_editar:
            valores = {
                "numero_reds": d.get("numero_reds") or None,
                "numero_inquerito": d.get("numero_inquerito") or None,
                "numero_outro_procedimento": d.get("numero_outro_procedimento") or None,
                "numero_processo_judicial": d.get("numero_processo_judicial") or None,
                "numero_medida_protetiva": d.get("numero_medida_protetiva") or None,
                "unidade_responsavel": d.get("unidade_responsavel") or None,
                "municipio": d.get("municipio") or None,
                "data_hora_atendimento": d.get("data_hora_atendimento") or None,
                "servidor_responsavel_id": int(d["servidor_responsavel_id"]) if d.get("servidor_responsavel_id", "").isdigit() else usuario["id"],
                "autoridade_responsavel": d.get("autoridade_responsavel") or None,
                "origem_demanda": d.get("origem_demanda") or None,
                "canal_atendimento": d.get("canal_atendimento") or None,
                "nivel_sigilo": d.get("nivel_sigilo") if d.get("nivel_sigilo") in VD_SIGILO_LABEL else "normal",
                "data_hora_fato": d.get("data_hora_fato") or None,
                "local_fato": d.get("local_fato") or None,
                "descricao_fato": d.get("descricao_fato") or None,
                "relato_mulher": d.get("relato_mulher") or None,
                "observacoes_servidor": d.get("observacoes_servidor") or None,
                "fonte_relato": d.get("fonte_relato") or None,
                "observacoes": d.get("observacoes") or None,
                "situacao": "rascunho",
            }
            con = conexao()
            colunas = ", ".join(valores.keys())
            marcas = ", ".join("?" for _ in valores)
            cur = con.execute(
                f"INSERT INTO vd_casos ({colunas}, criado_em, criado_por) VALUES ({marcas}, ?, ?)",
                list(valores.values()) + [agora(), usuario["id"]])
            cid = cur.lastrowid
            vd_registra_evento(con, cid, "criacao_caso", "Caso criado", usuario["id"])
            audita(con, usuario["id"], "CREATE", None, "vd_caso", None, f"Caso VD #{cid}")
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        m = re.fullmatch(r"/vd/(\d+)/editar", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            campos = ["numero_reds", "numero_inquerito", "numero_outro_procedimento",
                      "numero_processo_judicial", "numero_medida_protetiva",
                      "unidade_responsavel", "municipio", "data_hora_atendimento",
                      "autoridade_responsavel", "origem_demanda", "canal_atendimento",
                      "nivel_sigilo", "data_hora_fato", "local_fato", "descricao_fato",
                      "relato_mulher", "observacoes_servidor", "fonte_relato", "observacoes"]
            valores = {c: (d.get(c) or None) for c in campos}
            # nivel_sigilo é NOT NULL no banco. Se o campo não vier no envio,
            # gravar NULL derrubaria a conexão sem página de erro e a pessoa
            # perderia o que digitou.
            if valores["nivel_sigilo"] not in VD_SIGILO_LABEL:
                valores["nivel_sigilo"] = caso["nivel_sigilo"] or "normal"
            if d.get("servidor_responsavel_id", "").isdigit():
                valores["servidor_responsavel_id"] = int(d["servidor_responsavel_id"])
            mudou = 0
            for c, novo in valores.items():
                anterior = caso[c]
                if (anterior or None) != (novo or None):
                    audita(con, usuario["id"], "UPDATE", None, f"vd_caso.{c}", anterior, novo)
                    mudou += 1
            sets = ", ".join(f"{c}=?" for c in valores)
            con.execute(f"UPDATE vd_casos SET {sets}, atualizado_em=?, atualizado_por=? WHERE id=?",
                       list(valores.values()) + [agora(), usuario["id"], cid])
            if mudou:
                vd_registra_evento(con, cid, "atualizacao_caso", f"{mudou} campo(s) atualizado(s)", usuario["id"])
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        m = re.fullmatch(r"/vd/(\d+)/situacao", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            nova = d.get("situacao")
            if nova not in VD_SITUACAO_LABEL:
                return self.redireciona(f"/vd/{cid}")
            con = conexao()
            caso = con.execute("SELECT situacao FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            if nova == caso["situacao"]:
                con.close()
                return self.redireciona(f"/vd/{cid}")
            extra = {}
            if nova == "encerrado":
                if not d.get("motivo_encerramento", "").strip():
                    con.close()
                    return self.redireciona(f"/vd/{cid}")
                extra["motivo_encerramento"] = d["motivo_encerramento"].strip()
            if nova == "reaberto":
                if not d.get("motivo_reabertura", "").strip():
                    con.close()
                    return self.redireciona(f"/vd/{cid}")
                extra["motivo_reabertura"] = d["motivo_reabertura"].strip()
            sets = "situacao=?, atualizado_em=?, atualizado_por=?"
            valores_sql = [nova, agora(), usuario["id"]]
            for c, v in extra.items():
                sets += f", {c}=?"
                valores_sql.append(v)
            valores_sql.append(cid)
            con.execute(f"UPDATE vd_casos SET {sets} WHERE id=?", valores_sql)
            audita(con, usuario["id"], "STATUS", None, "vd_caso.situacao", caso["situacao"], nova)
            descricao_evento = f"Situação alterada para {VD_SITUACAO_LABEL.get(nova, nova)}"
            if extra:
                descricao_evento += f" — {list(extra.values())[0]}"
            vd_registra_evento(con, cid, "mudanca_situacao", descricao_evento, usuario["id"])
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        # Cancelar: para cadastro feito por engano. Sai das listagens e dos
        # painéis, mas nada é apagado — dá para reverter mudando a situação.
        m = re.fullmatch(r"/vd/(\d+)/cancelar", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            motivo = (d.get("motivo") or "").strip()
            if len(motivo) < 5:
                return self.redireciona(f"/vd/{cid}?erro=" + urllib.parse.quote(
                    "Informe o motivo do cancelamento (mínimo 5 caracteres)."))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            con.execute("UPDATE vd_casos SET situacao='cancelado', motivo_encerramento=?,"
                        " atualizado_em=?, atualizado_por=? WHERE id=?",
                        (motivo, agora(), usuario["id"], cid))
            audita(con, usuario["id"], "STATUS", None, "vd_caso.situacao",
                   caso["situacao"], f"cancelado — {motivo}")
            vd_registra_evento(con, cid, "mudanca_situacao",
                               f"Caso cancelado (cadastro incorreto) — {motivo}", usuario["id"])
            con.commit()
            con.close()
            return self.redireciona("/vd?ok=" + urllib.parse.quote(
                f"Caso #{cid} cancelado. Ele saiu das listagens, mas continua no banco "
                "e pode ser reativado alterando a situação."))

        # Excluir de vez: só Administrador. Apaga o caso e as quinze tabelas
        # que dependem dele, incluindo relato, FONAR e anexos em disco.
        m = re.fullmatch(r"/vd/(\d+)/excluir", caminho)
        if m and usuario["perfil"] == "admin":
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT * FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            identificacao = caso["numero_reds"] or caso["numero_inquerito"] or f"#{cid}"
            audita(con, usuario["id"], "DELETE", None, "vd_caso", identificacao, None)
            arquivos = exclui_caso_vd_em_cascata(con, cid)
            con.commit()
            con.close()
            for arquivo in arquivos:
                try:
                    os.remove(os.path.join(PASTA_VD_ANEXOS, arquivo))
                except OSError:
                    pass
            return self.redireciona("/vd?ok=" + urllib.parse.quote(
                f"Caso {identificacao} excluído definitivamente."))

        m = re.fullmatch(r"/vd/(\d+)/pessoas", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            pid = int(d["pessoa_id"]) if d.get("pessoa_id", "").isdigit() else None
            papel = d.get("papel")
            if not pid or papel not in VD_PAPEL_LABEL:
                return self.redireciona(f"/vd/{cid}")
            con = conexao()
            pessoa = con.execute("SELECT nome FROM pessoas WHERE id=?", (pid,)).fetchone()
            ja_existe = con.execute(
                "SELECT 1 FROM vd_caso_pessoas WHERE caso_id=? AND pessoa_id=? AND papel=?",
                (cid, pid, papel)).fetchone()
            if pessoa and not ja_existe:
                con.execute(
                    "INSERT INTO vd_caso_pessoas (caso_id, pessoa_id, papel, criado_em, criado_por)"
                    " VALUES (?,?,?,?,?)", (cid, pid, papel, agora(), usuario["id"]))
                vd_registra_evento(con, cid, "vinculo_pessoa",
                                   f"{pessoa['nome']} vinculado(a) como {VD_PAPEL_LABEL[papel]}", usuario["id"])
                audita(con, usuario["id"], "CREATE", pid, "vd_caso_pessoa", None,
                       f"Caso VD #{cid} — {VD_PAPEL_LABEL[papel]}")
                con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        m = re.fullmatch(r"/vd/caso-pessoas/(\d+)/excluir", caminho)
        if m and pode_editar:
            cpid = int(m.group(1))
            con = conexao()
            cp = con.execute("SELECT * FROM vd_caso_pessoas WHERE id=?", (cpid,)).fetchone()
            if cp:
                pessoa = con.execute("SELECT nome FROM pessoas WHERE id=?", (cp["pessoa_id"],)).fetchone()
                vd_registra_evento(con, cp["caso_id"], "desvinculo_pessoa",
                                   f"{pessoa['nome'] if pessoa else '(pessoa)'} desvinculado(a) "
                                   f"({VD_PAPEL_LABEL.get(cp['papel'], cp['papel'])})", usuario["id"])
                audita(con, usuario["id"], "DELETE", cp["pessoa_id"], "vd_caso_pessoa",
                       VD_PAPEL_LABEL.get(cp["papel"], cp["papel"]), None)
                con.execute("DELETE FROM vd_dados_mulher WHERE caso_pessoa_id=?", (cpid,))
                con.execute("DELETE FROM vd_dados_autor WHERE caso_pessoa_id=?", (cpid,))
                con.execute("DELETE FROM vd_caso_pessoas WHERE id=?", (cpid,))
                con.commit()
            cid = cp["caso_id"] if cp else None
            con.close()
            return self.redireciona(f"/vd/{cid}" if cid else "/vd")

        m = re.fullmatch(r"/vd/caso-pessoas/(\d+)/dados", caminho)
        if m and pode_editar:
            cpid = int(m.group(1))
            con = conexao()
            cp = con.execute("SELECT * FROM vd_caso_pessoas WHERE id=?", (cpid,)).fetchone()
            if not cp or cp["papel"] not in ("mulher_atendida", "suposto_autor"):
                con.close()
                return self.redireciona("/vd")
            tabela = "vd_dados_mulher" if cp["papel"] == "mulher_atendida" else "vd_dados_autor"
            if cp["papel"] == "mulher_atendida":
                campos = ["telefone_seguro", "telefone_alt_seguro", "autoriza_ligacao", "autoriza_mensagem",
                          "forma_contato_segura", "melhor_horario_contato", "palavras_proibidas_mensagem",
                          "telefone_controlado_agressor", "endereco_seguro", "pessoa_confianca_nome",
                          "pessoa_confianca_contato", "dependencia_economica", "gravidez", "puerperio",
                          "deficiencia", "dificuldade_locomocao", "necessidade_interprete",
                          "necessidade_atendimento_acessivel", "vinculo_rede_protecao",
                          "existe_local_seguro", "interesse_acolhimento", "percepcao_risco"]
            else:
                campos = ["relacionamento_mulher", "relacionamento_atual", "convivencia_atual",
                          "tempo_relacionamento", "filhos_em_comum", "veiculos", "acesso_arma_fogo",
                          "vinculo_forcas_seguranca", "uso_alcool", "uso_drogas", "historico_ameacas",
                          "historico_agressoes", "historico_perseguicao", "medidas_protetivas_anteriores",
                          "descumprimentos_anteriores", "outras_vitimas", "outras_ocorrencias",
                          "outros_procedimentos", "grau_verificacao", "observacoes"]
            valores = {c: (d.get(c) or None) for c in campos}
            existente = con.execute(f"SELECT id FROM {tabela} WHERE caso_pessoa_id=?", (cpid,)).fetchone()
            if existente:
                sets = ", ".join(f"{c}=?" for c in campos)
                con.execute(f"UPDATE {tabela} SET {sets}, atualizado_em=?, atualizado_por=? WHERE caso_pessoa_id=?",
                           list(valores.values()) + [agora(), usuario["id"], cpid])
            else:
                colunas = ", ".join(valores.keys())
                marcas = ", ".join("?" for _ in valores)
                con.execute(f"INSERT INTO {tabela} (caso_pessoa_id, {colunas}, atualizado_em, atualizado_por)"
                           f" VALUES (?,{marcas},?,?)",
                           [cpid] + list(valores.values()) + [agora(), usuario["id"]])
            vd_registra_evento(con, cp["caso_id"], "atualizacao_dados_especificos",
                               f"Dados de {VD_PAPEL_LABEL.get(cp['papel'])} atualizados", usuario["id"])
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cp['caso_id']}")

        m = re.fullmatch(r"/vd/caso-pessoas/(\d+)/fonar/novo", caminho)
        if m and pode_editar:
            cpid = int(m.group(1))
            con = conexao()
            cp = con.execute("SELECT * FROM vd_caso_pessoas WHERE id=?", (cpid,)).fetchone()
            if not cp or cp["papel"] != "mulher_atendida":
                con.close()
                return self.redireciona("/vd")
            aplicador_id = int(d["aplicador_id"]) if d.get("aplicador_id", "").isdigit() else usuario["id"]
            cur = con.execute(
                "INSERT INTO vd_fonar_aplicacoes (caso_pessoa_id, data_hora, aplicador_id,"
                " impossibilidade_responder, data_prevista_reavaliacao, criado_em, criado_por)"
                " VALUES (?,?,?,?,?,?,?)",
                (cpid, d.get("data_hora") or None, aplicador_id, d.get("impossibilidade_responder") or None,
                 d.get("data_prevista_reavaliacao") or None, agora(), usuario["id"]))
            aplicacao_id = cur.lastrowid
            total_respondidas = 0
            for codigo, bloco, texto, tipo, opcoes_lista in FONAR_PERGUNTAS:
                if tipo == "multipla":
                    valores_marcados = self.form_multi(f"resp_{codigo}")
                    resposta = FONAR_SEPARADOR_MULTIPLA.join(valores_marcados) if valores_marcados else None
                else:
                    resposta = d.get(f"resp_{codigo}") or None
                observacao = d.get(f"obs_{codigo}") or None
                if resposta or observacao:
                    con.execute(
                        "INSERT INTO vd_fonar_respostas (aplicacao_id, pergunta_codigo, resposta, observacao)"
                        " VALUES (?,?,?,?)", (aplicacao_id, codigo, resposta, observacao))
                    if resposta:
                        total_respondidas += 1
            pessoa = con.execute("SELECT nome FROM pessoas WHERE id=?", (cp["pessoa_id"],)).fetchone()
            audita(con, usuario["id"], "CREATE", cp["pessoa_id"], "vd_fonar", None,
                   f"FONAR aplicado ({total_respondidas} pergunta(s) respondida(s))")
            vd_registra_evento(con, cp["caso_id"], "fonar_aplicado",
                               f"FONAR aplicado a {pessoa['nome'] if pessoa else 'mulher atendida'} "
                               f"({total_respondidas} pergunta(s) respondida(s))", usuario["id"],
                               "vd_fonar_aplicacoes", aplicacao_id)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/fonar/{aplicacao_id}")

        m = re.fullmatch(r"/vd/(\d+)/avaliacao/nova", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT id FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            responsavel_id = int(d["responsavel_id"]) if d.get("responsavel_id", "").isdigit() else usuario["id"]
            campos = ["sintese", "fatores_risco", "fatores_protecao", "vulnerabilidades", "percepcao_mulher",
                      "criancas_expostas", "existe_arma", "risco_separacao", "providencias_imediatas",
                      "justificativa", "necessita_reavaliacao", "data_prevista_reavaliacao"]
            valores = {c: (d.get(c) or None) for c in campos}
            cur = con.execute(
                "INSERT INTO vd_avaliacoes_profissionais (caso_id, sintese, fatores_risco, fatores_protecao,"
                " vulnerabilidades, percepcao_mulher, criancas_expostas, existe_arma, risco_separacao,"
                " providencias_imediatas, justificativa, necessita_reavaliacao, data_prevista_reavaliacao,"
                " responsavel_id, data_hora, criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [cid] + list(valores.values()) + [responsavel_id, d.get("data_hora") or None, agora(), usuario["id"]])
            audita(con, usuario["id"], "CREATE", None, "vd_avaliacao_profissional", None,
                   f"Avaliação profissional registrada no caso #{cid}")
            vd_registra_evento(con, cid, "avaliacao_profissional",
                               "Avaliação profissional registrada", usuario["id"],
                               "vd_avaliacoes_profissionais", cur.lastrowid)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        m = re.fullmatch(r"/vd/(\d+)/medidas/nova", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT id FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            valores = {
                "data_solicitacao": d.get("data_solicitacao") or None,
                "autoridade_solicitante": d.get("autoridade_solicitante") or None,
                "numero_processo": d.get("numero_processo") or None,
                "orgao_judicial": d.get("orgao_judicial") or None,
                "situacao": d.get("situacao") if d.get("situacao") in VD_SITUACAO_MEDIDA_LABEL else "em_elaboracao",
                "observacoes": d.get("observacoes") or None,
            }
            colunas = ", ".join(valores.keys())
            marcas = ", ".join("?" for _ in valores)
            cur = con.execute(
                f"INSERT INTO vd_medidas_protetivas (caso_id, {colunas}, criado_em, criado_por)"
                f" VALUES (?,{marcas},?,?)", [cid] + list(valores.values()) + [agora(), usuario["id"]])
            medida_id = cur.lastrowid
            audita(con, usuario["id"], "CREATE", None, "vd_medida_protetiva", None,
                   f"Medida protetiva #{medida_id} criada no caso #{cid}")
            vd_registra_evento(con, cid, "medida_protetiva_criada",
                               f"Medida protetiva #{medida_id} registrada", usuario["id"],
                               "vd_medidas_protetivas", medida_id)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/medidas/{medida_id}")

        m = re.fullmatch(r"/vd/medidas/(\d+)/editar", caminho)
        if m and pode_editar:
            mid = int(m.group(1))
            con = conexao()
            medida = con.execute("SELECT * FROM vd_medidas_protetivas WHERE id=?", (mid,)).fetchone()
            if not medida:
                con.close()
                return self.redireciona("/vd")
            campos = ["data_solicitacao", "autoridade_solicitante", "numero_processo", "orgao_judicial",
                      "situacao", "data_decisao", "resultado", "data_ciencia_mulher", "data_intimacao_autor",
                      "responsavel_intimacao", "forma_intimacao", "vigencia", "data_revisao",
                      "data_encerramento", "observacoes"]
            valores = {c: (d.get(c) or None) for c in campos}
            if valores["situacao"] not in VD_SITUACAO_MEDIDA_LABEL:
                valores["situacao"] = medida["situacao"]
            mudou = 0
            for c, novo in valores.items():
                anterior = medida[c]
                if (anterior or None) != (novo or None):
                    audita(con, usuario["id"], "UPDATE", None, f"vd_medida.{c}", anterior, novo)
                    mudou += 1
            sets = ", ".join(f"{c}=?" for c in valores)
            con.execute(f"UPDATE vd_medidas_protetivas SET {sets}, atualizado_em=?, atualizado_por=? WHERE id=?",
                       list(valores.values()) + [agora(), usuario["id"], mid])
            if mudou:
                vd_registra_evento(con, medida["caso_id"], "medida_protetiva_atualizada",
                                   f"Medida protetiva #{mid}: {mudou} campo(s) atualizado(s)", usuario["id"],
                                   "vd_medidas_protetivas", mid)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/medidas/{mid}")

        m = re.fullmatch(r"/vd/medidas/(\d+)/itens", caminho)
        if m and pode_editar:
            mid = int(m.group(1))
            con = conexao()
            medida = con.execute("SELECT * FROM vd_medidas_protetivas WHERE id=?", (mid,)).fetchone()
            if not medida:
                con.close()
                return self.redireciona("/vd")
            tipo_medida = d.get("tipo_medida") or None
            if tipo_medida:
                con.execute(
                    "INSERT INTO vd_itens_medida_protetiva (medida_id, tipo_medida, situacao, data_inicial,"
                    " data_final, detalhes) VALUES (?,?,?,?,?,?)",
                    (mid, tipo_medida, d.get("situacao") or "vigente", d.get("data_inicial") or None,
                     d.get("data_final") or None, d.get("detalhes") or None))
                vd_registra_evento(con, medida["caso_id"], "item_medida_adicionado",
                                   f'Item "{tipo_medida}" adicionado à medida #{mid}', usuario["id"],
                                   "vd_medidas_protetivas", mid)
                con.commit()
            con.close()
            return self.redireciona(f"/vd/medidas/{mid}")

        m = re.fullmatch(r"/vd/itens-medida/(\d+)/excluir", caminho)
        if m and pode_editar:
            iid = int(m.group(1))
            con = conexao()
            item = con.execute("SELECT * FROM vd_itens_medida_protetiva WHERE id=?", (iid,)).fetchone()
            if item:
                medida_pai = con.execute(
                    "SELECT caso_id FROM vd_medidas_protetivas WHERE id=?", (item["medida_id"],)).fetchone()
                vd_registra_evento(con, medida_pai["caso_id"], "item_medida_removido",
                                   f'Item "{item["tipo_medida"]}" removido da medida #{item["medida_id"]}',
                                   usuario["id"], "vd_medidas_protetivas", item["medida_id"])
                con.execute("DELETE FROM vd_itens_medida_protetiva WHERE id=?", (iid,))
                con.commit()
            mid = item["medida_id"] if item else None
            con.close()
            return self.redireciona(f"/vd/medidas/{mid}" if mid else "/vd")

        m = re.fullmatch(r"/vd/medidas/(\d+)/descumprimento/novo", caminho)
        if m and pode_editar:
            mid = int(m.group(1))
            con = conexao()
            medida = con.execute("SELECT * FROM vd_medidas_protetivas WHERE id=?", (mid,)).fetchone()
            if not medida:
                con.close()
                return self.redireciona("/vd")
            responsavel_id = int(d["responsavel_id"]) if d.get("responsavel_id", "").isdigit() else usuario["id"]
            ocorrencia_id_desc = int(d["ocorrencia_id"]) if d.get("ocorrencia_id", "").isdigit() else None
            campos = ["data_hora", "local", "forma", "relato", "provas", "testemunhas", "contato_autor",
                      "meio_utilizado", "aproximacao_fisica", "ameaca", "agressao", "providencias",
                      "numero_procedimento", "houve_prisao", "situacao_apuracao"]
            valores = {c: (d.get(c) or None) for c in campos}
            cur = con.execute(
                "INSERT INTO vd_descumprimentos (medida_id, data_hora, local, forma, relato, provas,"
                " testemunhas, contato_autor, meio_utilizado, aproximacao_fisica, ameaca, agressao,"
                " providencias, numero_procedimento, houve_prisao, situacao_apuracao, ocorrencia_id,"
                " responsavel_id, criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [mid] + list(valores.values()) + [ocorrencia_id_desc, responsavel_id, agora(), usuario["id"]])
            audita(con, usuario["id"], "CREATE", None, "vd_descumprimento", None,
                   f"Descumprimento registrado na medida #{mid}")
            vd_registra_evento(con, medida["caso_id"], "descumprimento_registrado",
                               f"⚠ Possível descumprimento registrado na medida #{mid}", usuario["id"],
                               "vd_descumprimentos", cur.lastrowid)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/medidas/{mid}")

        m = re.fullmatch(r"/vd/(\d+)/diligencias/nova", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT id FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            if not d.get("descricao", "").strip():
                con.close()
                return self.redireciona(f"/vd/{cid}/diligencias/nova")
            responsavel_id = int(d["responsavel_id"]) if d.get("responsavel_id", "").isdigit() else None
            valores = {
                "descricao": d.get("descricao").strip(),
                "tipo": d.get("tipo") or None,
                "prioridade": d.get("prioridade") if d.get("prioridade") in VD_PRIORIDADE_DILIGENCIA_LABEL else "media",
                "responsavel_id": responsavel_id,
                "unidade_responsavel": d.get("unidade_responsavel") or None,
                "prazo": d.get("prazo") or None,
                "observacoes": d.get("observacoes") or None,
                "situacao": "pendente",
            }
            colunas = ", ".join(valores.keys())
            marcas = ", ".join("?" for _ in valores)
            cur = con.execute(
                f"INSERT INTO vd_diligencias (caso_id, {colunas}, criado_em, criado_por)"
                f" VALUES (?,{marcas},?,?)", [cid] + list(valores.values()) + [agora(), usuario["id"]])
            audita(con, usuario["id"], "CREATE", None, "vd_diligencia", None,
                   f"Diligência #{cur.lastrowid} criada no caso #{cid}")
            vd_registra_evento(con, cid, "diligencia_criada", f"Diligência registrada: {valores['descricao'][:80]}",
                               usuario["id"], "vd_diligencias", cur.lastrowid)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        m = re.fullmatch(r"/vd/diligencias/(\d+)/editar", caminho)
        if m and pode_editar:
            did = int(m.group(1))
            con = conexao()
            dilig = con.execute("SELECT * FROM vd_diligencias WHERE id=?", (did,)).fetchone()
            if not dilig:
                con.close()
                return self.redireciona("/vd")
            responsavel_id = int(d["responsavel_id"]) if d.get("responsavel_id", "").isdigit() else None
            campos_texto = ["descricao", "tipo", "unidade_responsavel", "prazo", "data_conclusao",
                            "resultado", "observacoes"]
            valores = {c: (d.get(c) or None) for c in campos_texto}
            valores["responsavel_id"] = responsavel_id
            valores["prioridade"] = d.get("prioridade") if d.get("prioridade") in VD_PRIORIDADE_DILIGENCIA_LABEL else dilig["prioridade"]
            valores["situacao"] = d.get("situacao") if d.get("situacao") in VD_SITUACAO_DILIGENCIA_LABEL else dilig["situacao"]
            mudou = 0
            for c, novo in valores.items():
                anterior = dilig[c]
                if (anterior or None) != (novo or None):
                    audita(con, usuario["id"], "UPDATE", None, f"vd_diligencia.{c}", anterior, novo)
                    mudou += 1
            sets = ", ".join(f"{c}=?" for c in valores)
            con.execute(f"UPDATE vd_diligencias SET {sets}, atualizado_em=?, atualizado_por=? WHERE id=?",
                       list(valores.values()) + [agora(), usuario["id"], did])
            if mudou:
                vd_registra_evento(con, dilig["caso_id"], "diligencia_atualizada",
                                   f"Diligência #{did}: {mudou} campo(s) atualizado(s)", usuario["id"],
                                   "vd_diligencias", did)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{dilig['caso_id']}")

        m = re.fullmatch(r"/vd/(\d+)/encaminhamentos/novo", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT id FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            responsavel_id = int(d["responsavel_id"]) if d.get("responsavel_id", "").isdigit() else usuario["id"]
            valores = {
                "instituicao": d.get("instituicao") or None,
                "servico": d.get("servico") or None,
                "profissional_setor": d.get("profissional_setor") or None,
                "motivo": d.get("motivo") or None,
                "data": d.get("data") or None,
                "documento_enviado": d.get("documento_enviado") or None,
                "observacoes": d.get("observacoes") or None,
                "situacao": "encaminhado",
            }
            colunas = ", ".join(valores.keys())
            marcas = ", ".join("?" for _ in valores)
            cur = con.execute(
                f"INSERT INTO vd_encaminhamentos (caso_id, {colunas}, responsavel_id, criado_em, criado_por)"
                f" VALUES (?,{marcas},?,?,?)",
                [cid] + list(valores.values()) + [responsavel_id, agora(), usuario["id"]])
            audita(con, usuario["id"], "CREATE", None, "vd_encaminhamento", None,
                   f"Encaminhamento #{cur.lastrowid} criado no caso #{cid}")
            vd_registra_evento(con, cid, "encaminhamento_criado",
                               f"Encaminhamento para {valores['instituicao'] or 'rede de proteção'} registrado",
                               usuario["id"], "vd_encaminhamentos", cur.lastrowid)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        m = re.fullmatch(r"/vd/encaminhamentos/(\d+)/editar", caminho)
        if m and pode_editar:
            eid = int(m.group(1))
            con = conexao()
            enc = con.execute("SELECT * FROM vd_encaminhamentos WHERE id=?", (eid,)).fetchone()
            if not enc:
                con.close()
                return self.redireciona("/vd")
            campos = ["instituicao", "servico", "profissional_setor", "motivo", "data",
                      "documento_enviado", "confirmacao_recebimento", "retorno_recebido",
                      "situacao", "observacoes"]
            valores = {c: (d.get(c) or None) for c in campos}
            mudou = 0
            for c, novo in valores.items():
                anterior = enc[c]
                if (anterior or None) != (novo or None):
                    audita(con, usuario["id"], "UPDATE", None, f"vd_encaminhamento.{c}", anterior, novo)
                    mudou += 1
            sets = ", ".join(f"{c}=?" for c in valores)
            con.execute(f"UPDATE vd_encaminhamentos SET {sets} WHERE id=?", list(valores.values()) + [eid])
            if mudou:
                vd_registra_evento(con, enc["caso_id"], "encaminhamento_atualizado",
                                   f"Encaminhamento #{eid}: {mudou} campo(s) atualizado(s)", usuario["id"],
                                   "vd_encaminhamentos", eid)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{enc['caso_id']}")

        m = re.fullmatch(r"/vd/(\d+)/acompanhamentos/novo", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            con = conexao()
            caso = con.execute("SELECT id FROM vd_casos WHERE id=?", (cid,)).fetchone()
            if not caso:
                con.close()
                return self.redireciona("/vd")
            responsavel_id = int(d["responsavel_id"]) if d.get("responsavel_id", "").isdigit() else usuario["id"]
            campos = ["data_prevista", "data_realizada", "meio_contato", "contato_seguro_confirmado",
                      "resultado", "situacao_atual_informada", "novos_fatos", "descumprimento_relatado",
                      "necessita_providencia", "necessita_reavaliacao", "observacoes"]
            valores = {c: (d.get(c) or None) for c in campos}
            colunas = ", ".join(valores.keys())
            marcas = ", ".join("?" for _ in valores)
            cur = con.execute(
                f"INSERT INTO vd_contatos_acompanhamento (caso_id, {colunas}, responsavel_id, criado_em, criado_por)"
                f" VALUES (?,{marcas},?,?,?)",
                [cid] + list(valores.values()) + [responsavel_id, agora(), usuario["id"]])
            audita(con, usuario["id"], "CREATE", None, "vd_acompanhamento", None,
                   f"Acompanhamento #{cur.lastrowid} registrado no caso #{cid}")
            descricao_evento = "Contato de acompanhamento registrado"
            if valores.get("descumprimento_relatado") == "sim":
                descricao_evento += " — ⚠ descumprimento relatado pela mulher"
            vd_registra_evento(con, cid, "acompanhamento_registrado", descricao_evento, usuario["id"],
                               "vd_contatos_acompanhamento", cur.lastrowid)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        m = re.fullmatch(r"/vd/acompanhamentos/(\d+)/editar", caminho)
        if m and pode_editar:
            aid = int(m.group(1))
            con = conexao()
            contato = con.execute("SELECT * FROM vd_contatos_acompanhamento WHERE id=?", (aid,)).fetchone()
            if not contato:
                con.close()
                return self.redireciona("/vd")
            responsavel_id = int(d["responsavel_id"]) if d.get("responsavel_id", "").isdigit() else contato["responsavel_id"]
            campos = ["data_prevista", "data_realizada", "meio_contato", "contato_seguro_confirmado",
                      "resultado", "situacao_atual_informada", "novos_fatos", "descumprimento_relatado",
                      "necessita_providencia", "necessita_reavaliacao", "observacoes"]
            valores = {c: (d.get(c) or None) for c in campos}
            mudou = 0
            for c, novo in valores.items():
                anterior = contato[c]
                if (anterior or None) != (novo or None):
                    audita(con, usuario["id"], "UPDATE", None, f"vd_acompanhamento.{c}", anterior, novo)
                    mudou += 1
            if responsavel_id != contato["responsavel_id"]:
                mudou += 1
            sets = ", ".join(f"{c}=?" for c in valores) + ", responsavel_id=?"
            con.execute(f"UPDATE vd_contatos_acompanhamento SET {sets} WHERE id=?",
                       list(valores.values()) + [responsavel_id, aid])
            if mudou:
                vd_registra_evento(con, contato["caso_id"], "acompanhamento_atualizado",
                                   f"Acompanhamento #{aid}: {mudou} campo(s) atualizado(s)", usuario["id"],
                                   "vd_contatos_acompanhamento", aid)
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{contato['caso_id']}")

        m = re.fullmatch(r"/vd/(\d+)/ocorrencias", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            oid = int(d["ocorrencia_id"]) if d.get("ocorrencia_id", "").isdigit() else None
            if oid:
                con = conexao()
                ja_existe = con.execute(
                    "SELECT 1 FROM vd_caso_ocorrencias WHERE caso_id=? AND ocorrencia_id=?",
                    (cid, oid)).fetchone()
                if not ja_existe:
                    con.execute(
                        "INSERT INTO vd_caso_ocorrencias (caso_id, ocorrencia_id, criado_em, criado_por)"
                        " VALUES (?,?,?,?)", (cid, oid, agora(), usuario["id"]))
                    vd_registra_evento(con, cid, "vinculo_ocorrencia",
                                       f"Ocorrência #{oid} vinculada", usuario["id"])
                    con.commit()
                con.close()
            return self.redireciona(f"/vd/{cid}")

        m = re.fullmatch(r"/vd/caso-ocorrencias/(\d+)/excluir", caminho)
        if m and pode_editar:
            vid = int(m.group(1))
            con = conexao()
            vo = con.execute("SELECT * FROM vd_caso_ocorrencias WHERE id=?", (vid,)).fetchone()
            if vo:
                vd_registra_evento(con, vo["caso_id"], "desvinculo_ocorrencia",
                                   f"Ocorrência #{vo['ocorrencia_id']} desvinculada", usuario["id"])
                con.execute("DELETE FROM vd_caso_ocorrencias WHERE id=?", (vid,))
                con.commit()
            cid = vo["caso_id"] if vo else None
            con.close()
            return self.redireciona(f"/vd/{cid}" if cid else "/vd")

        m = re.fullmatch(r"/vd/(\d+)/violencia", caminho)
        if m and pode_editar:
            cid = int(m.group(1))
            tipos = [t for t in self.form_multi("tipo") if t in lista_ativa("vd_tipo_violencia")]
            marcadores = [mk for mk in self.form_multi("marcador") if mk in lista_ativa("vd_marcador_operacional")]
            con = conexao()
            con.execute("DELETE FROM vd_caso_tipos_violencia WHERE caso_id=?", (cid,))
            con.execute("DELETE FROM vd_caso_marcadores WHERE caso_id=?", (cid,))
            for t in tipos:
                con.execute("INSERT INTO vd_caso_tipos_violencia (caso_id, tipo) VALUES (?,?)", (cid, t))
            for mk in marcadores:
                con.execute("INSERT INTO vd_caso_marcadores (caso_id, marcador) VALUES (?,?)", (cid, mk))
            vd_registra_evento(con, cid, "caracterizacao_violencia",
                               f"{len(tipos)} forma(s) de violência e {len(marcadores)} marcador(es) registrados",
                               usuario["id"])
            con.commit()
            con.close()
            return self.redireciona(f"/vd/{cid}")

        # --- Verificação de denúncias -------------------------------------
        # (o CSRF já foi conferido acima, na checagem única de do_POST, e o
        #  corpo do formulário já está lido em "d" — reler o socket travaria.)
        if caminho == "/verificacoes/nova" and pode_editar:
            erro = valida_verificacao(d)
            if erro:
                return self.responde_html(pagina_verificacao_form(usuario, csrf, d, None, erro))
            valores = valores_verificacao(d)
            colunas = list(valores.keys()) + ["criado_em", "criado_por",
                                              "atualizado_em", "atualizado_por"]
            args = list(valores.values()) + [agora(), usuario["id"], agora(), usuario["id"]]
            con = conexao()
            cur = con.execute(
                f"INSERT INTO verificacoes ({', '.join(colunas)}) "
                f"VALUES ({', '.join('?' * len(colunas))})", args)
            vid = cur.lastrowid
            salva_assinatura_no_usuario(con, usuario["id"], valores["assinante_cargo"],
                                        valores["assinante_masp"])
            salva_equipe_verificacao(con, vid, d.get("equipe_ids"), usuario["id"])
            salva_envolvidos_verificacao(con, vid, valores, usuario["id"])
            audita(con, usuario["id"], "CREATE", None, "verificacao", None,
                   f"Verificação de denúncia #{vid}")
            con.commit()
            con.close()
            return self.redireciona(f"/verificacoes/{vid}")

        m = re.fullmatch(r"/verificacoes/(\d+)/editar", caminho)
        if m and pode_editar:
            vid = int(m.group(1))
            erro = valida_verificacao(d)
            if erro:
                return self.responde_html(pagina_verificacao_form(usuario, csrf, d, vid, erro))
            valores = valores_verificacao(d)
            con = conexao()
            existe = con.execute("SELECT 1 FROM verificacoes WHERE id=?", (vid,)).fetchone()
            if not existe:
                con.close()
                return self.responde_html(pagina("Não encontrada",
                    '<p class="erro">Verificação não encontrada.</p>', usuario), 404)
            sets = ", ".join(f"{c}=?" for c in valores) + ", atualizado_em=?, atualizado_por=?"
            con.execute(f"UPDATE verificacoes SET {sets} WHERE id=?",
                        list(valores.values()) + [agora(), usuario["id"], vid])
            salva_assinatura_no_usuario(con, usuario["id"], valores["assinante_cargo"],
                                        valores["assinante_masp"])
            salva_equipe_verificacao(con, vid, d.get("equipe_ids"), usuario["id"])
            salva_envolvidos_verificacao(con, vid, valores, usuario["id"])
            audita(con, usuario["id"], "UPDATE", None, "verificacao", None,
                   f"Verificação de denúncia #{vid}")
            con.commit()
            con.close()
            return self.redireciona(f"/verificacoes/{vid}")

        m = re.fullmatch(r"/verificacoes/(\d+)/excluir", caminho)
        if m and usuario["perfil"] == "admin":
            vid = int(m.group(1))
            con = conexao()
            arquivos = [r["arquivo"] for r in con.execute(
                "SELECT arquivo FROM verificacao_fotos WHERE verificacao_id=?", (vid,))]
            con.execute("DELETE FROM verificacao_fotos WHERE verificacao_id=?", (vid,))
            con.execute("DELETE FROM verificacao_equipe WHERE verificacao_id=?", (vid,))
            con.execute("DELETE FROM verificacao_envolvidos WHERE verificacao_id=?", (vid,))
            con.execute("DELETE FROM verificacoes WHERE id=?", (vid,))
            audita(con, usuario["id"], "DELETE", None, "verificacao",
                   f"Verificação de denúncia #{vid}", None)
            con.commit()
            con.close()
            for arquivo in arquivos:
                try:
                    os.remove(os.path.join(PASTA_FOTOS, arquivo))
                except OSError:
                    pass
            return self.redireciona("/verificacoes")

        if caminho == "/configuracoes/adicionar" and usuario["perfil"] == "admin":
            categoria = d.get("categoria") or ""
            valor = (d.get("valor") or "").strip()
            categorias_validas = {c for c, _, _ in CATEGORIAS_CONFIGURAVEIS}
            if categoria not in categorias_validas or not valor:
                return self.redireciona("/configuracoes?erro=" + urllib.parse.quote(
                    "Preencha o valor da nova opção."))
            con = conexao()
            existe = con.execute(
                "SELECT 1 FROM opcoes_configuraveis WHERE categoria=? AND valor=? COLLATE NOCASE",
                (categoria, valor)).fetchone()
            if existe:
                con.close()
                return self.redireciona("/configuracoes?erro=" + urllib.parse.quote(
                    f'"{valor}" já existe nessa lista.'))
            con.execute(
                "INSERT INTO opcoes_configuraveis (categoria, valor, ativo, criado_em, criado_por)"
                " VALUES (?,?,1,?,?)", (categoria, valor, agora(), usuario["id"]))
            audita(con, usuario["id"], "CREATE", None, "opcao_configuravel", None, f"{categoria}: {valor}")
            con.commit()
            con.close()
            rotulo = ROTULO_CATEGORIA_CONFIGURAVEL.get(categoria, categoria)
            return self.redireciona("/configuracoes?ok=" + urllib.parse.quote(
                f'"{valor}" adicionado(a) a "{rotulo}".'))

        m = re.fullmatch(r"/opcoes/(\d+)/ativo", caminho)
        if m and usuario["perfil"] == "admin":
            oid = int(m.group(1))
            con = conexao()
            op = con.execute("SELECT * FROM opcoes_configuraveis WHERE id=?", (oid,)).fetchone()
            if op:
                novo_estado = 0 if op["ativo"] else 1
                con.execute("UPDATE opcoes_configuraveis SET ativo=? WHERE id=?", (novo_estado, oid))
                audita(con, usuario["id"], "UPDATE", None, "opcao_configuravel",
                       "ativa" if op["ativo"] else "desativada",
                       "desativada" if op["ativo"] else "ativa")
                con.commit()
            con.close()
            return self.redireciona("/configuracoes")

        if caminho == "/configuracoes/backup" and usuario["perfil"] == "admin":
            try:
                selo = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                pasta_destino = os.path.join(PASTA, "backups", selo)
                os.makedirs(pasta_destino, exist_ok=True)
                # Cópia consistente mesmo com o sistema em uso. Copiar o arquivo
                # direto podia gerar um backup corrompido se houvesse gravação em
                # andamento — e backup que não abre só se descobre no pior dia.
                copia_banco_consistente(os.path.join(pasta_destino, "sirio.db"))
                if os.path.isdir(PASTA_FOTOS):
                    shutil.copytree(PASTA_FOTOS, os.path.join(pasta_destino, "fotos"), dirs_exist_ok=True)
                # A pasta certificados NÃO entra no backup: ela contém a chave
                # privada do HTTPS, que não deve sair deste computador. Se o
                # certificado se perder, basta gerar outro pelo atalho próprio.
                con = conexao()
                audita(con, usuario["id"], "BACKUP", None, "backup", None, selo)
                con.commit()
                con.close()
                return self.redireciona("/configuracoes?ok=" + urllib.parse.quote(
                    f"Backup criado em backups/{selo}."))
            except Exception as err:
                return self.redireciona("/configuracoes?erro=" + urllib.parse.quote(
                    f"Não foi possível criar o backup: {err}"))

        if caminho == "/usuarios" and usuario["perfil"] == "admin":
            if not d.get("nome") or not d.get("username") or not d.get("senha"):
                return self.redireciona("/usuarios?erro=" + urllib.parse.quote("Preencha todos os campos."))
            con = conexao()
            try:
                cur = con.execute(
                    "INSERT INTO usuarios (nome, username, senha_hash, perfil, ativo, criado_em)"
                    " VALUES (?,?,?,?,1,?)",
                    (d["nome"], d["username"], hash_senha(d["senha"]),
                     d.get("perfil") if d.get("perfil") in PERFIL_LABEL else "consulta", agora()))
                audita(con, usuario["id"], "CREATE", None, "usuario", None, d["username"])
                con.commit()
            except sqlite3.IntegrityError:
                con.close()
                return self.redireciona("/usuarios?erro=" + urllib.parse.quote("Este login já existe."))
            con.close()
            return self.redireciona("/usuarios?ok=" + urllib.parse.quote("Usuário criado."))

        m = re.fullmatch(r"/usuarios/(\d+)/editar", caminho)
        if m and usuario["perfil"] == "admin":
            if not self.csrf_ok(d, csrf):
                return self.redireciona("/usuarios?erro=" + urllib.parse.quote(
                    "Não foi possível validar a solicitação. Tente novamente."))
            uid = int(m.group(1))
            nome = (d.get("nome") or "").strip()
            username = (d.get("username") or "").strip()
            perfil = d.get("perfil") if d.get("perfil") in PERFIL_LABEL else None
            if not nome or not username or not perfil:
                return self.redireciona("/usuarios?erro=" + urllib.parse.quote(
                    "Nome, login e perfil são obrigatórios."))
            if " " in username:
                return self.redireciona("/usuarios?erro=" + urllib.parse.quote(
                    "O login não pode conter espaços."))
            con = conexao()
            u = con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
            if not u:
                con.close()
                return self.redireciona("/usuarios?erro=" + urllib.parse.quote("Usuário não encontrado."))
            # Trava: a unidade nunca pode ficar sem administrador ativo.
            if u["perfil"] == "admin" and perfil != "admin":
                outros = con.execute(
                    "SELECT COUNT(*) FROM usuarios WHERE perfil='admin' AND ativo=1 AND id<>?",
                    (uid,)).fetchone()[0]
                if not outros:
                    con.close()
                    return self.redireciona("/usuarios?erro=" + urllib.parse.quote(
                        "Este é o único administrador ativo. Promova outra pessoa a "
                        "Administrador antes de alterar este perfil."))
            mudancas = []
            for campo, anterior, novo in (("nome", u["nome"], nome),
                                          ("username", u["username"], username),
                                          ("perfil", u["perfil"], perfil)):
                if anterior != novo:
                    mudancas.append((campo, anterior, novo))
            if not mudancas:
                con.close()
                return self.redireciona("/usuarios?ok=" + urllib.parse.quote("Nada foi alterado."))
            try:
                con.execute("UPDATE usuarios SET nome=?, username=?, perfil=? WHERE id=?",
                            (nome, username, perfil, uid))
            except sqlite3.IntegrityError:
                con.close()
                return self.redireciona("/usuarios?erro=" + urllib.parse.quote("Este login já existe."))
            for campo, anterior, novo in mudancas:
                audita(con, usuario["id"], "UPDATE", None, f"usuario.{campo}", anterior, novo)
            con.commit()
            con.close()
            # Se o perfil mudou, as sessões abertas dessa pessoa precisam cair para
            # que a nova permissão valha imediatamente, e não só no próximo login.
            if any(c == "perfil" for c, _, _ in mudancas):
                for token, dados_sessao in list(SESSOES.items()):
                    if dados_sessao["usuario_id"] == uid and token != self.token_sessao():
                        SESSOES.pop(token, None)
            return self.redireciona("/usuarios?ok=" + urllib.parse.quote("Usuário atualizado."))

        m = re.fullmatch(r"/usuarios/(\d+)/ativo", caminho)
        if m and usuario["perfil"] == "admin":
            uid = int(m.group(1))
            if uid != usuario["id"]:
                con = conexao()
                u = con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
                if u and u["ativo"] and u["perfil"] == "admin":
                    outros = con.execute(
                        "SELECT COUNT(*) FROM usuarios WHERE perfil='admin' AND ativo=1 AND id<>?",
                        (uid,)).fetchone()[0]
                    if not outros:
                        con.close()
                        return self.redireciona("/usuarios?erro=" + urllib.parse.quote(
                            "Este é o único administrador ativo e não pode ser desativado."))
                if u:
                    novo_estado = 0 if u["ativo"] else 1
                    con.execute("UPDATE usuarios SET ativo=? WHERE id=?", (novo_estado, uid))
                    audita(con, usuario["id"], "UPDATE", None, "usuario",
                           "ativo" if u["ativo"] else "inativo", "inativo" if u["ativo"] else "ativo")
                    con.commit()
                    # Desativar precisa derrubar as sessões abertas da pessoa; caso
                    # contrário ela continua usando o sistema até fechar o navegador.
                    if novo_estado == 0:
                        for token, dados_sessao in list(SESSOES.items()):
                            if dados_sessao["usuario_id"] == uid:
                                SESSOES.pop(token, None)
                con.close()
            return self.redireciona("/usuarios")

        return self.responde_html(pagina("Não encontrada",
            '<p class="erro">Ação não encontrada.</p>', usuario), 404)


# ----------------------------------------------------------------------------
# Inicialização
# ----------------------------------------------------------------------------

def ip_local():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def principal(modo_rede=False):
    inicia_banco()
    inicia_banco_vd()
    inicia_banco_verificacoes()
    endereco = "0.0.0.0" if modo_rede else "127.0.0.1"
    servidor = ThreadingHTTPServer((endereco, PORTA), Servidor)
    certificado = os.path.join(PASTA, "certificados", "sirio-certificado.pem")
    chave_privada = os.path.join(PASTA, "certificados", "sirio-chave-privada.pem")
    if not os.path.isfile(certificado) or not os.path.isfile(chave_privada):
        servidor.server_close()
        raise RuntimeError(
            "Certificado HTTPS não encontrado. Execute 'Gerar Certificado HTTPS.bat' "
            "neste computador para criar um novo."
        )
    contexto_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto_tls.minimum_version = ssl.TLSVersion.TLSv1_2
    contexto_tls.load_cert_chain(certificado, chave_privada)
    servidor.socket = contexto_tls.wrap_socket(servidor.socket, server_side=True)
    print("=" * 62)
    print("  SIRIO - Sistema Interno de Registro de Investigados")
    print(f"  Versao: {VERSAO}")
    print("=" * 62)
    print(f"  Neste computador:  https://localhost:{PORTA}")
    if modo_rede:
        print()
        print("  MODO REDE DA UNIDADE ATIVADO")
        print("  Outros computadores da unidade acessam pelo navegador em:")
        print(f"    https://{ip_local()}:{PORTA}")
        print("  Antes do primeiro acesso, instale o certificado público do SIRIO")
        print("  nos computadores clientes (veja o LEIA-ME, seção 13).")
    print()
    print(f"  Banco de dados:    {ARQ_DB}")
    print()
    print("  NAO FECHE ESTA JANELA enquanto estiver usando o sistema.")
    print("  Para encerrar: feche esta janela ou pressione Ctrl+C.")
    print("=" * 62)
    threading.Timer(1.0, lambda: webbrowser.open(f"https://localhost:{PORTA}")).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando o SIRIO...")
        servidor.shutdown()


def _confirma_pasta():
    """Mostra em qual instalação a operação vai mexer.

    Existe porque é fácil executar um atalho da pasta errada quando há mais de
    uma cópia do SIRIO no computador — e aí a senha é redefinida num banco que
    não é o que o sistema abre.
    """
    print("=" * 62)
    print(f" Pasta:  {PASTA}")
    print(f" Banco:  {ARQ_DB}")
    if not os.path.isfile(ARQ_DB):
        print()
        print(" ATENCAO: nao existe banco de dados nesta pasta.")
        print(" Esta provavelmente e uma copia nova, ainda sem uso.")
        print(" Se voce queria mexer no SIRIO que ja usa, feche esta janela")
        print(" e execute o atalho a partir da pasta correta.")
        print("=" * 62)
        return False
    con = conexao()
    n = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    p = con.execute("SELECT COUNT(*) FROM pessoas").fetchone()[0]
    con.close()
    print(f" Conteudo: {n} usuario(s), {p} registro(s) de pessoa")
    print("=" * 62)
    print()
    print(" Confira acima se e esta a instalacao que voce quer alterar.")
    return True


def resetar_senha():
    tem_banco = _confirma_pasta()
    if not tem_banco:
        return
    inicia_banco()
    con = conexao()
    usuarios = con.execute("SELECT id, nome, username, perfil FROM usuarios ORDER BY nome").fetchall()
    if not usuarios:
        print("Nenhum usuário cadastrado ainda.")
        con.close()
        return
    print("Usuários cadastrados:")
    for u in usuarios:
        print(f"  [{u['id']}] {u['nome']} (login: {u['username']}, perfil: {u['perfil']})")
    try:
        escolha = input("\nDigite o número (ID) do usuário para redefinir a senha: ").strip()
        uid = int(escolha)
    except (ValueError, KeyboardInterrupt):
        print("Cancelado.")
        con.close()
        return
    alvo = next((u for u in usuarios if u["id"] == uid), None)
    if not alvo:
        print("ID não encontrado.")
        con.close()
        return
    import getpass
    nova = getpass.getpass("Nova senha (mínimo 8 caracteres, não aparece na tela): ")
    if len(nova) < 8:
        print("Senha muito curta. Cancelado.")
        con.close()
        return
    confirmar = getpass.getpass("Repita a nova senha: ")
    if nova != confirmar:
        print("As senhas não coincidem. Cancelado.")
        con.close()
        return
    con.execute("UPDATE usuarios SET senha_hash=?, ativo=1 WHERE id=?", (hash_senha(nova), uid))
    audita(con, uid, "UPDATE", None, "senha", None, "redefinida via linha de comando")
    con.commit()
    con.close()
    print(f"\nSenha de '{alvo['nome']}' redefinida com sucesso.")


def backup_linha_de_comando():
    """Backup pelo atalho 'Fazer Backup.bat', com cópia consistente do banco."""
    if not os.path.isfile(ARQ_DB):
        print("Ainda nao existe banco de dados para copiar.")
        return
    selo = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destino = os.path.join(PASTA, "backups", selo)
    os.makedirs(destino, exist_ok=True)
    copia_banco_consistente(os.path.join(destino, "sirio.db"))
    if os.path.isdir(PASTA_FOTOS):
        shutil.copytree(PASTA_FOTOS, os.path.join(destino, "fotos"), dirs_exist_ok=True)
    # A trilha de auditoria exige um usuário, e aqui não há sessão: quem executa
    # está no console do servidor. Registrar em nome de alguém seria atribuição
    # falsa, então o backup pelo atalho fica anotado neste arquivo à parte.
    try:
        registro = os.path.join(PASTA, "backups", "registro_de_backups.txt")
        with open(registro, "a", encoding="utf-8") as f:
            f.write(f"{agora()}  backup {selo}  origem: atalho no computador principal\n")
    except OSError:
        pass
    print(f"Backup criado em: backups\\{selo}")
    print("Conteudo: banco de dados + fotografias.")
    print()
    print("A pasta 'certificados' NAO entra no backup: ela contem a chave")
    print("privada do HTTPS, que nao deve sair deste computador. Se o")
    print('certificado se perder, use "Gerar Certificado HTTPS.bat".')
    print()
    print("Esta copia contem dados sensiveis e fotografias. Guarde-a em")
    print("local protegido, fora deste computador.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "resetar-senha":
        resetar_senha()
    elif len(sys.argv) > 1 and sys.argv[1] == "backup":
        backup_linha_de_comando()
    elif len(sys.argv) > 1 and sys.argv[1] == "rede":
        principal(modo_rede=True)
    else:
        principal()
