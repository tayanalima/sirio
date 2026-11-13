"""Importação padronizada da planilha de resultados do Armazém SIDS."""
from sirio_core import *  # noqa: F401,F403
import base64
import zipfile
import xml.etree.ElementTree as ET

IMPORTACOES_SIDS_PENDENTES = {}
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _normaliza_cabecalho(valor):
    valor = unicodedata.normalize("NFD", str(valor or ""))
    sem_acentos = "".join("" if unicodedata.combining(c) else c for c in valor).lower()
    return " ".join(sem_acentos.split())


def _texto_xlsx(conteudo):
    """Lê XLSX do SIDS somente com a biblioteca padrão, sem depender do Excel."""
    with zipfile.ZipFile(io.BytesIO(conteudo)) as arq:
        shared = []
        if "xl/sharedStrings.xml" in arq.namelist():
            raiz = ET.fromstring(arq.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(_NS + "t")) for si in raiz.iter(_NS + "si")]
        nome_planilha = next((n for n in arq.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")), None)
        if not nome_planilha:
            raise ValueError("Não encontrei uma planilha de dados no arquivo.")
        raiz = ET.fromstring(arq.read(nome_planilha))
    linhas = []
    for row in raiz.iter(_NS + "row"):
        valores = {}
        for celula in row.iter(_NS + "c"):
            referencia = celula.get("r", "")
            letra = "".join(c for c in referencia if c.isalpha())
            indice = 0
            for c in letra: indice = indice * 26 + ord(c) - 64
            indice -= 1
            tipo = celula.get("t")
            v = celula.find(_NS + "v")
            texto = "" if v is None else (v.text or "")
            if tipo == "s" and texto.isdigit() and int(texto) < len(shared): texto = shared[int(texto)]
            elif tipo == "inlineStr": texto = "".join(t.text or "" for t in celula.iter(_NS + "t"))
            valores[indice] = texto
        if valores:
            linhas.append([valores.get(i, "") for i in range(max(valores) + 1)])
    return linhas


def _valor(linha, colunas, *nomes):
    for nome in nomes:
        idx = colunas.get(_normaliza_cabecalho(nome))
        if idx is not None and idx < len(linha):
            return str(linha[idx] or "").strip() or None
    return None


def _data_sids(valor):
    if not valor:
        return None
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
        try: return datetime.strptime(valor, formato).strftime("%Y-%m-%d")
        except ValueError: pass
    return None


def _numero(valor):
    try: return float(str(valor).replace(",", ".")) if valor not in (None, "") else None
    except ValueError: return None


def ler_planilha_sids(conteudo):
    linhas = _texto_xlsx(conteudo)
    if len(linhas) < 2:
        raise ValueError("A planilha não possui linhas de dados.")
    colunas = {_normaliza_cabecalho(v): i for i, v in enumerate(linhas[0])}
    # A exportação "Resultados" atual do Armazém SIDS traz os dados da
    # ocorrência, mas não necessariamente a qualificação dos envolvidos. A
    # versão detalhada traz as duas colunas abaixo. As duas são válidas: no
    # formato resumido o SIRIO importa somente as ocorrências.
    obrigatorias = ("numero da ocorrencia",)
    ausentes = [x for x in obrigatorias if x not in colunas]
    if ausentes:
        raise ValueError("Este arquivo não tem o padrão do Armazém SIDS (colunas obrigatórias ausentes).")
    registros = []
    for linha in linhas[1:]:
        reds = _valor(linha, colunas, "número da ocorrência", "numero da ocorrencia")
        if not reds:
            continue
        registros.append({
            "reds": reds, "tipo_crime": _valor(linha, colunas, "natureza principal", "natureza do delito"),
            "data_fato": _data_sids(_valor(linha, colunas, "data hora do fato")),
            "endereco_fato": _valor(linha, colunas, "endereço da ocorrência", "endereco da ocorrencia"),
            "cidade_fato": _valor(linha, colunas, "município do fato", "municipio do fato"),
            "bairro_fato": _valor(linha, colunas, "bairro do fato"),
            "lat_fato": _numero(_valor(linha, colunas, "latitude")), "lon_fato": _numero(_valor(linha, colunas, "longitude")),
            "historico": _valor(linha, colunas, "histórico", "historico"),
            "nome": _valor(linha, colunas, "nome do envolvido"), "tipo_envolvimento": _valor(linha, colunas, "tipo de envolvimento"),
            "rg": _valor(linha, colunas, "rg"), "cpf": _valor(linha, colunas, "cpf"),
            "data_nascimento": _data_sids(_valor(linha, colunas, "data de nascimento")),
            "nome_mae": _valor(linha, colunas, "nome mãe envolvido", "nome mae envolvido"),
            "endereco": _valor(linha, colunas, "endereço do envolvido", "endereco do envolvido"),
            "observacao": "Importado da planilha do Armazém SIDS.",
        })
    if not registros:
        raise ValueError("Não encontrei ocorrências válidas na planilha.")
    return registros


def pagina_importar_sids(usuario, csrf, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    corpo = f'''<div class="cab"><h1>Importar planilha do Armazém SIDS</h1></div>
    <p class="suave">Use a exportação “Resultados” do Armazém SIDS em formato XLSX. O SIRIO importa as ocorrências pelo REDS e, quando a planilha também trouxer envolvidos, os vincula automaticamente.</p>
    <form method="post" action="/importar-sids" enctype="multipart/form-data" class="grade"><input type="hidden" name="csrf" value="{e(csrf)}">
      <label class="span2">Arquivo XLSX<input type="file" name="arquivo" accept=".xlsx" required></label>
      <div class="acoes span2"><a class="botao fantasma" href="/importar">Voltar</a><button class="botao">Ler e conferir planilha</button></div>
    </form>{msg}'''
    return pagina("Importar Armazém SIDS", corpo, usuario)


def pagina_confirmar_sids(usuario, csrf, token, registros):
    reds = len({r["reds"] for r in registros})
    pessoas = len({(r["nome"] or "").upper() for r in registros if r["nome"]})
    amostra = "".join(f"<tr><td>{e(r['reds'])}</td><td>{e(r['tipo_crime']) or '—'}</td><td>{e(r['nome']) or '—'}</td><td>{e(r['tipo_envolvimento']) or '—'}</td></tr>" for r in registros[:20])
    rotulo_linhas = "linhas de envolvimento" if pessoas else "linhas de resultado"
    corpo = f'''<div class="cab"><h1>Conferir importação do Armazém SIDS</h1></div>
    <div class="cartoes"><div class="cartao"><h2>{reds}</h2><p>ocorrência(s) única(s)</p></div><div class="cartao"><h2>{pessoas}</h2><p>pessoa(s) identificada(s)</p></div><div class="cartao"><h2>{len(registros)}</h2><p>{rotulo_linhas}</p></div></div>
    <p class="aviso">A importação cria somente ocorrências ainda inexistentes no SIRIO. Quando houver envolvidos na planilha, evita duplicar pessoas por CPF, RG ou nome exato. Confira a amostra antes de confirmar.</p>
    <table><thead><tr><th>REDS</th><th>Natureza</th><th>Envolvido</th><th>Tipo de envolvimento</th></tr></thead><tbody>{amostra}</tbody></table>
    <form method="post" action="/importar-sids/confirmar"><input type="hidden" name="csrf" value="{e(csrf)}"><input type="hidden" name="token" value="{e(token)}"><div class="acoes"><a class="botao fantasma" href="/importar-sids">Cancelar</a><button class="botao">Importar {reds} ocorrência(s)</button></div></form>'''
    return pagina("Conferir importação SIDS", corpo, usuario)


def _encontra_pessoa_sids(con, item):
    cpf = re.sub(r"\D", "", item["cpf"] or "")
    if cpf:
        for p in con.execute("SELECT * FROM pessoas WHERE cpf IS NOT NULL AND cpf != ''"):
            if re.sub(r"\D", "", p["cpf"] or "") == cpf: return p
    if item["rg"]:
        p = con.execute("SELECT * FROM pessoas WHERE UPPER(TRIM(rg))=UPPER(TRIM(?))", (item["rg"],)).fetchone()
        if p: return p
    if item["nome"]:
        return con.execute("SELECT * FROM pessoas WHERE UPPER(TRIM(nome))=UPPER(TRIM(?))", (item["nome"],)).fetchone()
    return None


def importa_sids(registros, usuario_id):
    con = conexao(); pessoas_novas = ocorrencias_novas = 0; pessoas_por_linha = {}
    try:
        for i, item in enumerate(registros):
            if not item["nome"]: continue
            p = _encontra_pessoa_sids(con, item)
            if p: pessoas_por_linha[i] = p["id"]; continue
            cur = con.execute("INSERT INTO pessoas (nome, rg, cpf, data_nascimento, nome_mae, endereco, observacoes, status, criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (item["nome"], item["rg"], item["cpf"], item["data_nascimento"], item["nome_mae"], item["endereco"], item["observacao"], "em_verificacao", agora(), usuario_id))
            pessoas_por_linha[i] = cur.lastrowid; pessoas_novas += 1
            audita(con, usuario_id, "CREATE", cur.lastrowid, "origem", None, "Importado do Armazém SIDS")
        por_reds = {}
        for i, item in enumerate(registros): por_reds.setdefault(item["reds"], []).append((i, item))
        for reds, linhas in por_reds.items():
            if con.execute("SELECT 1 FROM ocorrencias WHERE numero_bo=?", (reds,)).fetchone(): continue
            _, base = linhas[0]; autor = next(((i, r) for i, r in linhas if any(x in (r["tipo_envolvimento"] or "").upper() for x in ("AUTOR", "SUSPEITO"))), (None, None))
            pid = pessoas_por_linha.get(autor[0]) if autor[0] is not None else None
            cur = con.execute("INSERT INTO ocorrencias (tipo_crime, numero_bo, data_fato, endereco_fato, cidade_fato, bairro_fato, lat_fato, lon_fato, pessoa_autor_id, nome_autor, observacoes, criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (base["tipo_crime"], reds, base["data_fato"], base["endereco_fato"], base["cidade_fato"], base["bairro_fato"], base["lat_fato"], base["lon_fato"], pid, autor[1]["nome"] if autor[1] else None, base["historico"], agora(), usuario_id))
            boletim = con.execute(
                "INSERT INTO boletins (reds, data_fato, historico, ocorrencia_id, criado_em, criado_por) VALUES (?,?,?,?,?,?)",
                (reds, base["data_fato"], base["historico"], cur.lastrowid, agora(), usuario_id))
            vinculados = set()
            for indice, linha_sids in linhas:
                pessoa_id = pessoas_por_linha.get(indice)
                if pessoa_id and pessoa_id not in vinculados:
                    con.execute("INSERT INTO boletim_pessoa (boletim_id, pessoa_id, tipo_envolvimento) VALUES (?,?,?)",
                                (boletim.lastrowid, pessoa_id, linha_sids["tipo_envolvimento"]))
                    vinculados.add(pessoa_id)
            ocorrencias_novas += 1; audita(con, usuario_id, "CREATE", None, "ocorrencia", None, f"Importada do Armazém SIDS: {reds}")
        con.commit()
    finally: con.close()
    return pessoas_novas, ocorrencias_novas
