"""Módulo SIRIO — Registro de verificação de denúncias.

Guarda cada denúncia que chega à unidade (Disque 100, WhatsApp, presencial,
ofício de outro órgão etc.), o relatório de averiguação inicial da servidora e
o registro do boletim de ocorrência, quando houver. A partir desse registro o
sistema monta a Comunicação de Serviço em Word, já com o timbre da unidade.

Importa a infraestrutura compartilhada de sirio_core.py.
"""
import re
import zipfile
from sirio_core import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Situações do acompanhamento

SITUACOES_VERIFICACAO = [
    ("em_verificacao", "Em verificação"),
    ("aguardando_terceiros", "Aguardando resposta de outro órgão"),
    ("concluida", "Concluída"),
    ("arquivada", "Arquivada"),
]
SITUACAO_VERIFICACAO_LABEL = dict(SITUACOES_VERIFICACAO)

OPCOES_BO = ["", "Sim", "Não", "Não se aplica", "Em registro"]
TIPOS_ENVOLVIMENTO_VERIFICACAO = {
    "vitima": "Vítima",
    "autor_investigado": "Autor / investigado",
}

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

MIGRACOES_VERIFICACOES = [
    ("usuarios", "cargo", "TEXT"),
    ("usuarios", "masp", "TEXT"),
    # Endereços e coordenadas dos envolvidos e do local do fato. Ficam aqui
    # também (e não só no CREATE TABLE) para que bancos criados antes desta
    # versão ganhem as colunas sem perder nada.
    ("verificacoes", "endereco_vitima", "TEXT"),
    ("verificacoes", "lat_vitima", "REAL"),
    ("verificacoes", "lon_vitima", "REAL"),
    ("verificacoes", "endereco_autor", "TEXT"),
    ("verificacoes", "lat_autor", "REAL"),
    ("verificacoes", "lon_autor", "REAL"),
    ("verificacoes", "lat_fato", "REAL"),
    ("verificacoes", "lon_fato", "REAL"),
    ("verificacoes", "rg_vitima", "TEXT"),
    ("verificacoes", "cpf_vitima", "TEXT"),
    ("verificacoes", "rg_autor", "TEXT"),
    ("verificacoes", "cpf_autor", "TEXT"),
]


def inicia_banco_verificacoes():
    con = conexao()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS verificacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        protocolo TEXT,
        canal_origem TEXT,
        orgao_origem TEXT,
        data_denuncia TEXT,
        data_fato TEXT,
        tipo_denuncia TEXT,
        municipio TEXT,
        local_fato TEXT,
        lat_fato REAL, lon_fato REAL,
        resumo_denuncia TEXT,
        nome_vitima TEXT, pessoa_vitima_id INTEGER, rg_vitima TEXT, cpf_vitima TEXT,
        endereco_vitima TEXT, lat_vitima REAL, lon_vitima REAL,
        nome_autor TEXT, pessoa_autor_id INTEGER, rg_autor TEXT, cpf_autor TEXT,
        endereco_autor TEXT, lat_autor REAL, lon_autor REAL,
        vinculo_autor_vitima TEXT,
        numero_os TEXT, numero_pcnet TEXT,
        requisicao TEXT,
        bo_registrado TEXT,
        numero_bo TEXT,
        ocorrencia_id INTEGER,
        relatorio_averiguacao TEXT,
        diligencias_pendentes TEXT,
        conclusao TEXT,
        situacao TEXT NOT NULL DEFAULT 'em_verificacao',
        numero_comunicacao TEXT,
        data_comunicacao TEXT,
        destinatario TEXT,
        assinante_nome TEXT, assinante_cargo TEXT, assinante_masp TEXT,
        observacoes TEXT,
        criado_em TEXT, criado_por INTEGER,
        atualizado_em TEXT, atualizado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS verificacao_equipe (
        verificacao_id INTEGER NOT NULL,
        usuario_id INTEGER NOT NULL,
        nome TEXT NOT NULL,
        cargo TEXT,
        masp TEXT,
        PRIMARY KEY (verificacao_id, usuario_id)
    );
    CREATE TABLE IF NOT EXISTS verificacao_fotos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        verificacao_id INTEGER NOT NULL,
        legenda TEXT,
        arquivo TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS verificacao_envolvidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        verificacao_id INTEGER NOT NULL,
        pessoa_id INTEGER,
        nome TEXT NOT NULL,
        tipo_envolvimento TEXT NOT NULL,
        rg TEXT,
        cpf TEXT,
        criado_em TEXT NOT NULL,
        criado_por INTEGER,
        UNIQUE (verificacao_id, tipo_envolvimento)
    );
    """)
    aplica_migracoes(con, MIGRACOES_VERIFICACOES)
    # Registros anteriores à tabela de envolvidos também passam a ter os dois
    # vínculos consultáveis, sem exigir que sejam abertos e salvos novamente.
    for v in con.execute("SELECT * FROM verificacoes"):
        for tipo, coluna_nome, coluna_pessoa, coluna_rg, coluna_cpf in (
            ("vitima", "nome_vitima", "pessoa_vitima_id", "rg_vitima", "cpf_vitima"),
            ("autor_investigado", "nome_autor", "pessoa_autor_id", "rg_autor", "cpf_autor"),
        ):
            if v[coluna_nome]:
                con.execute(
                    "INSERT OR IGNORE INTO verificacao_envolvidos (verificacao_id, pessoa_id, nome, tipo_envolvimento, rg, cpf, criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?)",
                    (v["id"], v[coluna_pessoa], v[coluna_nome], tipo, v[coluna_rg], v[coluna_cpf],
                     v["criado_em"] or agora(), v["criado_por"]))
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Apoio

def _id_ou_none(valor):
    """Converte o campo escondido do autocompletar em id inteiro (ou None)."""
    try:
        return int(str(valor).strip()) if str(valor).strip() else None
    except (ValueError, TypeError):
        return None


def _coord_ou_none(valor):
    """Aceita vírgula ou ponto decimal e devolve float (ou None)."""
    try:
        texto = str(valor).strip().replace(",", ".")
        return float(texto) if texto else None
    except (ValueError, TypeError):
        return None


def fmt_coord(lat, lon):
    if lat in (None, "") or lon in (None, ""):
        return ""
    try:
        return f"{float(lat):.5f}, {float(lon):.5f}"
    except (ValueError, TypeError):
        return f"{lat}, {lon}"


def pill_situacao_verificacao(situacao):
    classe = {"em_verificacao": "em_verificacao", "aguardando_terceiros": "em_verificacao",
              "concluida": "ativo", "arquivada": "arquivado"}.get(situacao, "inativo")
    return (f'<span class="pill p-{classe}">'
            f'{e(SITUACAO_VERIFICACAO_LABEL.get(situacao, situacao))}</span>')


def proximo_numero_comunicacao():
    """Sugere o próximo número no formato 001/ANO, olhando o que já foi usado
    neste ano. É só sugestão — a servidora pode digitar outro número."""
    ano = datetime.now().year
    con = conexao()
    usados = con.execute(
        "SELECT numero_comunicacao FROM verificacoes WHERE numero_comunicacao LIKE ?",
        (f"%/{ano}",)).fetchall()
    con.close()
    maior = 0
    for linha in usados:
        m = re.match(r"\s*(\d+)\s*/", linha["numero_comunicacao"] or "")
        if m:
            maior = max(maior, int(m.group(1)))
    return f"{maior + 1:03d}/{ano}"


def fmt_dia(iso):
    """2026-07-19 -> 19/07/2026. Aceita também data com hora e devolve só o dia."""
    if not iso:
        return ""
    try:
        return datetime.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(iso)


def data_por_extenso(iso):
    """2026-08-17 -> 'Aos 17 de agosto de 2026.'"""
    try:
        d = datetime.strptime((iso or "")[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        d = datetime.now()
    return f"Aos {d.day:02d} de {MESES[d.month - 1]} de {d.year}."


def _qualificacao_pessoa(con, pessoa_id, nome_livre, endereco="", lat=None, lon=None, rg="", cpf=""):
    """Monta a lista de dados de qualificação. Usa o cadastro de pessoas quando
    a vítima/autor está vinculada; senão devolve o nome digitado. O endereço da
    própria verificação tem preferência sobre o do cadastro (é o endereço
    apurado agora); as coordenadas entram logo abaixo dele."""
    itens = []
    endereco_cadastro = ""
    if pessoa_id:
        p = con.execute("SELECT * FROM pessoas WHERE id=?", (pessoa_id,)).fetchone()
        if p:
            filiacao = " e ".join([x for x in (p["nome_mae"], p["nome_pai"]) if x])
            endereco_cadastro = p["endereco"] or ""
            itens = [
                ("Nome", p["nome"]),
                ("Alcunha", p["alcunha"]),
                ("RG", rg or p["rg"]),
                ("CPF", cpf or p["cpf"]),
                ("Data de nascimento", fmt_dia(p["data_nascimento"])),
                ("Filiação", filiacao),
                ("Cônjuge/companheira(o)", p["nome_companheira"]),
            ]
    if not itens:
        itens = [("Nome", nome_livre), ("RG", rg), ("CPF", cpf)]
    itens.append(("Endereço", endereco or endereco_cadastro))
    itens.append(("Coordenadas geográficas", fmt_coord(lat, lon)))
    return itens


# ---------------------------------------------------------------------------
# Geração da Comunicação de Serviço em Word (.docx)
#
# Não usa biblioteca externa: abre o modelo timbrado (modelos/
# comunicacao_servico.docx), que já traz cabeçalho com o brasão, rodapé,
# margens e estilos, e injeta o corpo do documento no lugar da marca
# <!--CORPO-->. Assim o Word abre o arquivo exatamente como os documentos
# que a unidade já usa.

ARQ_MODELO_COMUNICACAO = os.path.join(PASTA, "modelos", "comunicacao_servico.docx")


def modelo_comunicacao_disponivel():
    return os.path.exists(ARQ_MODELO_COMUNICACAO)


def _x(texto):
    return (str(texto if texto is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _run(texto, negrito=False, sz=24):
    b = "<w:b/><w:bCs/>" if negrito else ""
    tam = f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>' if sz else ""
    return ('<w:r><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:cstheme="minorHAnsi"/>'
            f'{b}<w:color w:val="000000"/>{tam}</w:rPr>'
            f'<w:t xml:space="preserve">{_x(texto)}</w:t></w:r>')


def _par(runs, estilo=None, jc="both", recuo=False, numerado=False):
    ppr = "<w:pPr>"
    if estilo:
        ppr += f'<w:pStyle w:val="{estilo}"/>'
    if numerado:
        ppr += ('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="10"/></w:numPr>'
                '<w:ind w:left="720" w:hanging="360" w:firstLine="0"/>')
    ppr += '<w:spacing w:line="360" w:lineRule="auto"/>'
    if recuo and not numerado:
        ppr += '<w:ind w:firstLine="708"/>'
    ppr += f'<w:jc w:val="{jc}"/></w:pPr>'
    return "<w:p>" + ppr + "".join(runs) + "</w:p>"


def _linha_cabecalho(rotulo, valor, valor_negrito=False):
    return _par([_run(f"{rotulo}: "), _run(valor, negrito=valor_negrito)], jc="both")


def _texto_em_paragrafos(texto, estilo="ComunicaodeServio"):
    """Cada linha (ou bloco separado por linha em branco) vira um parágrafo."""
    saida = ""
    for bloco in re.split(r"\n\s*\n|\n", (texto or "").strip()):
        bloco = bloco.strip()
        if bloco:
            saida += _par([_run(bloco)], estilo=estilo, recuo=True)
    return saida


def _lista_numerada(texto):
    saida = ""
    for linha in (texto or "").splitlines():
        linha = linha.strip().lstrip("-•*").strip()
        linha = re.sub(r"^\d+[\.\)]\s*", "", linha)
        if linha:
            saida += _par([_run(linha)], estilo="ComunicaodeServio", numerado=True)
    return saida


def _tamanho_imagem(conteudo):
    """Devolve (largura, altura) em pixels para manter a proporção no Word."""
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n") and len(conteudo) >= 24:
        return int.from_bytes(conteudo[16:20], "big"), int.from_bytes(conteudo[20:24], "big")
    if conteudo.startswith((b"GIF87a", b"GIF89a")) and len(conteudo) >= 10:
        return int.from_bytes(conteudo[6:8], "little"), int.from_bytes(conteudo[8:10], "little")
    if conteudo.startswith(b"\xff\xd8"):
        pos = 2
        while pos + 9 < len(conteudo):
            if conteudo[pos] != 0xff:
                pos += 1
                continue
            marcador = conteudo[pos + 1]
            tamanho = int.from_bytes(conteudo[pos + 2:pos + 4], "big")
            if marcador in range(0xc0, 0xc4) and tamanho >= 7:
                return int.from_bytes(conteudo[pos + 7:pos + 9], "big"), int.from_bytes(conteudo[pos + 5:pos + 7], "big")
            pos += 2 + tamanho
    # WEBP e formatos futuros ainda são incorporados; este tamanho neutro evita
    # que uma imagem sem cabeçalho reconhecido quebre a Comunicação.
    return 4, 3


def _imagem_no_word(rid, indice, legenda, largura_px, altura_px):
    proporcao = max(largura_px, 1) / max(altura_px, 1)
    largura = 5_700_000
    altura = min(int(largura / proporcao), 4_300_000)
    if altura < 1:
        altura = 4_300_000
    desenho = f'''<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{largura}" cy="{altura}"/><wp:docPr id="{1000 + indice}" name="Foto {indice}" descr="{_x(legenda or 'Registro fotográfico da averiguação')}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="{indice}" name="Foto {indice}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{largura}" cy="{altura}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''
    return desenho + _par([_run(legenda or f"Foto {indice}", sz=20)], jc="center")


def corpo_comunicacao_xml(v, con, fotos=()):
    """Monta o XML do corpo da Comunicação de Serviço a partir de um registro."""
    xml = ""

    # --- cabeçalho de identificação -----------------------------------
    xml += _linha_cabecalho("Assunto", "Comunicação (faz)")
    xml += _linha_cabecalho("Serviço", "do Agente desta Delegacia de Polícia.")
    xml += _par([_run("Data: "), _run(data_por_extenso(v["data_comunicacao"] or agora()[:10]))], jc="both")
    if v["numero_pcnet"]:
        xml += _linha_cabecalho("PCNET", v["numero_pcnet"], True)
    if v["numero_os"]:
        xml += _linha_cabecalho("OS", v["numero_os"], True)
    if v["numero_bo"]:
        xml += _linha_cabecalho("REDS", v["numero_bo"], True)
    if v["protocolo"]:
        xml += _linha_cabecalho("Protocolo de atendimento", v["protocolo"], True)
    if v["canal_origem"]:
        xml += _linha_cabecalho("Canal de origem da denúncia", v["canal_origem"])
    xml += _linha_cabecalho("Vítima", (v["nome_vitima"] or "Não identificada").upper())
    xml += _linha_cabecalho("Investigados", (v["nome_autor"] or "Não identificado").upper())
    if v["data_fato"]:
        xml += _linha_cabecalho("Data do Fato", fmt_dia(v["data_fato"]))
    if v["requisicao"]:
        xml += _linha_cabecalho("REQ", v["requisicao"])

    # --- título --------------------------------------------------------
    numero = v["numero_comunicacao"] or ""
    xml += _par([_run(f"Comunicação n° IPT - {numero}.", sz=28)],
                estilo="Ttulo1", jc="center")

    # --- abertura ------------------------------------------------------
    xml += _par([_run((v["destinatario"] or "Senhora Delegada") + ",")], jc="both")
    xml += _par([_run("Cumprindo determinação de Vossa Excelência, devidamente orientada "
                      "pela chefia imediata, no sentido de empreender diligências a fim de "
                      "apurar os fatos noticiados, temos a relatar o que abaixo segue.")],
                estilo="Standard", recuo=True)

    # --- dos fatos -----------------------------------------------------
    xml += _par([_run("Dos fatos.", sz=None)], estilo="Ttulo2", jc="left")
    if v["resumo_denuncia"]:
        xml += _texto_em_paragrafos(v["resumo_denuncia"], estilo="Standard")
    origem = []
    if v["canal_origem"]:
        origem.append(f"recebida por meio de {v['canal_origem']}")
    if v["orgao_origem"]:
        origem.append(f"encaminhada por {v['orgao_origem']}")
    if v["protocolo"]:
        origem.append(f"registrada sob o protocolo de atendimento n° {v['protocolo']}")
    if origem:
        xml += _par([_run("A denúncia foi " + ", ".join(origem) + ".")],
                    estilo="Standard", recuo=True)
    if v["local_fato"] or v["lat_fato"]:
        local = v["local_fato"] or "não descrito"
        if v["municipio"]:
            local += f", em {v['municipio']}"
        coord = fmt_coord(v["lat_fato"], v["lon_fato"])
        if coord:
            local += f" (coordenadas geográficas {coord})"
        xml += _par([_run(f"Os fatos teriam ocorrido em {local}.")],
                    estilo="Standard", recuo=True)

    # --- qualificações --------------------------------------------------
    xml += _par([_run("Qualificações dos envolvidos.", sz=None)], estilo="Ttulo2", jc="left")

    xml += _par([_run("Vítima:", sz=None)], estilo="Ttulo3", jc="left")
    for rotulo, valor in _qualificacao_pessoa(con, v["pessoa_vitima_id"], v["nome_vitima"],
                                              v["endereco_vitima"], v["lat_vitima"], v["lon_vitima"],
                                              v["rg_vitima"], v["cpf_vitima"]):
        xml += _par([_run(f"{rotulo}: "), _run(valor or "")], estilo="Standard")

    xml += _par([_run("Investigado:", sz=None)], estilo="Ttulo3", jc="left")
    for rotulo, valor in _qualificacao_pessoa(con, v["pessoa_autor_id"], v["nome_autor"],
                                              v["endereco_autor"], v["lat_autor"], v["lon_autor"],
                                              v["rg_autor"], v["cpf_autor"]):
        xml += _par([_run(f"{rotulo}: "), _run(valor or "")], estilo="Standard")
    if v["vinculo_autor_vitima"]:
        xml += _par([_run("Vínculo com a vítima: "), _run(v["vinculo_autor_vitima"])],
                    estilo="Standard")

    # --- boletim de ocorrência ------------------------------------------
    xml += _par([_run("Do registro de ocorrência.", sz=None)], estilo="Ttulo2", jc="left")
    if (v["bo_registrado"] or "").lower().startswith("sim") and v["numero_bo"]:
        frase = (f"Os fatos encontram-se registrados no boletim de ocorrência n° "
                 f"{v['numero_bo']}, que instrui o presente procedimento de verificação.")
    elif (v["bo_registrado"] or "").lower().startswith("sim"):
        frase = ("Os fatos encontram-se registrados em boletim de ocorrência, cujo número "
                 "será juntado ao presente procedimento.")
    elif (v["bo_registrado"] or "").lower().startswith("em registro"):
        frase = ("O registro do boletim de ocorrência referente aos fatos encontra-se "
                 "em andamento nesta unidade.")
    elif (v["bo_registrado"] or "").lower().startswith("não se aplica"):
        frase = ("Não se aplica ao caso, nesta fase, o registro de boletim de ocorrência.")
    else:
        frase = ("Até o presente momento não foi localizado registro de boletim de "
                 "ocorrência referente aos fatos ora noticiados.")
    xml += _par([_run(frase)], estilo="Standard", recuo=True)

    # --- diligências realizadas ------------------------------------------
    xml += _par([_run("Das diligências realizadas.", sz=None)], estilo="Ttulo2", jc="left")
    if v["relatorio_averiguacao"]:
        xml += _texto_em_paragrafos(v["relatorio_averiguacao"])
    else:
        xml += _par([_run("Sem diligências registradas até o momento.")],
                    estilo="ComunicaodeServio", recuo=True)

    # --- diligências pendentes -------------------------------------------
    if v["diligencias_pendentes"]:
        xml += _par([_run("Das diligências pendentes.", sz=None)], estilo="Ttulo2", jc="left")
        xml += _par([_run("Para o prosseguimento da apuração, entende-se pertinente:")],
                    estilo="ComunicaodeServio", recuo=True)
        xml += _lista_numerada(v["diligencias_pendentes"])

    # --- conclusão --------------------------------------------------------
    if v["conclusao"]:
        xml += _par([_run("Da conclusão.", sz=None)], estilo="Ttulo2", jc="left")
        xml += _texto_em_paragrafos(v["conclusao"])

    # --- registro fotográfico --------------------------------------------
    if fotos:
        xml += _par([_run("Registro fotográfico.", sz=None)], estilo="Ttulo2", jc="left")
        for indice, foto in enumerate(fotos, 1):
            xml += _imagem_no_word(f"rIdSirioFoto{indice}", indice, foto["legenda"],
                                   foto["largura"], foto["altura"])

    # --- fecho ------------------------------------------------------------
    xml += _par([_run("Face ao exposto, e no aguardo de novas determinações, deixa-se esta "
                      "à apreciação de Vossa Excelência.")],
                estilo="ComunicaodeServio", recuo=True)
    xml += _par([_run("")], jc="center")
    xml += _par([_run("_____________________________________")], jc="center")
    xml += _par([_run(v["assinante_nome"] or "")], jc="center")
    xml += _par([_run(v["assinante_cargo"] or "Investigador de Polícia")], jc="center")
    if v["assinante_masp"]:
        xml += _par([_run("MASP: " + v["assinante_masp"])], jc="center")
    equipe = con.execute(
        "SELECT nome, cargo, masp FROM verificacao_equipe WHERE verificacao_id=? ORDER BY nome COLLATE NOCASE",
        (v["id"],)).fetchall()
    for membro in equipe:
        xml += _par([_run("")], jc="center")
        xml += _par([_run("_____________________________________")], jc="center")
        xml += _par([_run(membro["nome"])], jc="center")
        xml += _par([_run(membro["cargo"] or "Investigador de Polícia")], jc="center")
        if membro["masp"]:
            xml += _par([_run("MASP: " + membro["masp"])], jc="center")
    return xml


def gera_comunicacao_docx(v):
    """Devolve os bytes do .docx da Comunicação de Serviço."""
    if not modelo_comunicacao_disponivel():
        raise FileNotFoundError(ARQ_MODELO_COMUNICACAO)
    con = conexao()
    try:
        fotos = []
        for foto in con.execute("SELECT arquivo, legenda FROM verificacao_fotos WHERE verificacao_id=? ORDER BY id", (v["id"],)):
            caminho = os.path.join(PASTA_FOTOS, foto["arquivo"])
            if not os.path.isfile(caminho):
                continue
            with open(caminho, "rb") as arq:
                conteudo = arq.read()
            ext = os.path.splitext(foto["arquivo"])[1].lower()
            if ext not in TIPOS_IMAGEM or not any(conteudo.startswith(s) for s in TIPOS_IMAGEM[ext][1]):
                continue
            largura, altura = _tamanho_imagem(conteudo)
            fotos.append({"arquivo": foto["arquivo"], "legenda": foto["legenda"], "conteudo": conteudo,
                          "ext": ext, "largura": largura, "altura": altura})
        corpo = corpo_comunicacao_xml(v, con, fotos)
    finally:
        con.close()

    saida = io.BytesIO()
    with zipfile.ZipFile(ARQ_MODELO_COMUNICACAO) as zin:
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                dados = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    texto = dados.decode("utf-8").replace("<!--CORPO-->", corpo)
                    if fotos:
                        texto = texto.replace('<w:document ', '<w:document xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" ', 1)
                    dados = texto.encode("utf-8")
                elif item.filename == "word/_rels/document.xml.rels" and fotos:
                    texto = dados.decode("utf-8")
                    relacoes = "".join(
                        f'<Relationship Id="rIdSirioFoto{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/sirio_verificacao_{v["id"]}_{i}{foto["ext"]}"/>'
                        for i, foto in enumerate(fotos, 1))
                    dados = texto.replace("</Relationships>", relacoes + "</Relationships>").encode("utf-8")
                elif item.filename == "[Content_Types].xml" and fotos:
                    texto = dados.decode("utf-8")
                    tipos = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                             ".gif": "image/gif", ".webp": "image/webp"}
                    for ext in {foto["ext"] for foto in fotos}:
                        extensao = ext[1:]
                        if f'Extension="{extensao}"' not in texto:
                            texto = texto.replace("</Types>", f'<Default Extension="{extensao}" ContentType="{tipos[ext]}"/></Types>')
                    dados = texto.encode("utf-8")
                zout.writestr(item, dados)
            for i, foto in enumerate(fotos, 1):
                zout.writestr(f"word/media/sirio_verificacao_{v['id']}_{i}{foto['ext']}", foto["conteudo"])
    return saida.getvalue()


def nome_arquivo_comunicacao(v):
    numero = (v["numero_comunicacao"] or str(v["id"])).replace("/", "_")
    return f"Comunicacao_de_servico_{numero}.docx"


# ---------------------------------------------------------------------------
# Telas

def pagina_verificacoes_lista(usuario, csrf, filtros):
    con = conexao()
    sql = "SELECT * FROM verificacoes WHERE 1=1"
    args = []
    if filtros.get("situacao"):
        sql += " AND situacao = ?"
        args.append(filtros["situacao"])
    if filtros.get("canal"):
        sql += " AND canal_origem = ?"
        args.append(filtros["canal"])
    if filtros.get("bo"):
        sql += " AND IFNULL(bo_registrado,'') = ?"
        args.append(filtros["bo"])
    if filtros.get("busca"):
        sql += (" AND (nome_vitima LIKE ? OR nome_autor LIKE ? OR protocolo LIKE ?"
                " OR numero_bo LIKE ? OR numero_os LIKE ? OR numero_comunicacao LIKE ?)")
        alvo = f"%{filtros['busca']}%"
        args += [alvo] * 6
    sql += " ORDER BY id DESC LIMIT 500"
    registros = con.execute(sql, args).fetchall()
    totais = {chave: con.execute("SELECT COUNT(*) FROM verificacoes WHERE situacao=?",
                                 (chave,)).fetchone()[0]
              for chave, _ in SITUACOES_VERIFICACAO}
    con.close()

    pode_editar = usuario["perfil"] in ("admin", "analista")
    botao_novo = ('<a class="botao" href="/verificacoes/nova">Nova verificação</a>'
                  if pode_editar else "")

    linhas = ""
    for v in registros:
        bo = e(v["numero_bo"]) or ("—" if (v["bo_registrado"] or "") in ("", "Não") else "—")
        selo_bo = ""
        if (v["bo_registrado"] or "") == "Não":
            selo_bo = '<span class="selo s-baixa">Sem BO</span>'
        elif v["numero_bo"]:
            selo_bo = f'<span class="mono">{e(v["numero_bo"])}</span>'
        elif v["bo_registrado"]:
            selo_bo = f'<span class="selo s-media">{e(v["bo_registrado"])}</span>'
        else:
            selo_bo = "—"
        linhas += f"""<tr>
          <td class="num-col"><a class="nomelink" href="/verificacoes/{v['id']}">#{v['id']}</a></td>
          <td class="mono">{e(v['protocolo']) or '—'}</td>
          <td>{e(v['canal_origem']) or '—'}</td>
          <td><a class="nomelink" href="/verificacoes/{v['id']}">{e(v['nome_vitima']) or 'Vítima não identificada'}</a></td>
          <td>{e(v['nome_autor']) or '—'}</td>
          <td>{selo_bo}</td>
          <td class="nowrap-col">{e(fmt_dia(v['data_denuncia'])) or '—'}</td>
          <td>{pill_situacao_verificacao(v['situacao'])}</td>
          <td class="nowrap-col">{e(v['numero_comunicacao']) or '—'}</td></tr>"""

    tabela = (f"""<div class="tabela-rolavel"><table>
        <thead><tr><th>Nº</th><th>Protocolo</th><th>Canal</th><th>Vítima</th><th>Autor</th>
        <th>Boletim de ocorrência</th><th>Denúncia em</th><th>Situação</th><th>Comunicação</th>
        </tr></thead><tbody>{linhas}</tbody></table></div>"""
        if registros else
        '<div class="vazio">Nenhuma verificação encontrada com esse filtro.</div>')

    cartoes_totais = "".join(
        f'<div class="li-campo"><span class="rot">{e(rotulo)}</span>'
        f'<span class="val">{totais[chave]}</span></div>'
        for chave, rotulo in SITUACOES_VERIFICACAO)

    aviso_modelo = ""
    if not modelo_comunicacao_disponivel():
        aviso_modelo = ('<p class="erro">O modelo timbrado da Comunicação de Serviço não foi '
                        'encontrado na pasta "modelos". Sem ele o sistema continua guardando os '
                        'registros normalmente, mas não consegue gerar o documento em Word.</p>')

    corpo = f"""
    <div class="cab"><h1>Verificação de denúncias</h1>{botao_novo}</div>
    <p class="suave">Cada denúncia que chega à unidade — Disque 100, WhatsApp, presencial,
    ofício de outro órgão — vira um registro aqui, com o seu relatório de averiguação inicial.
    Do registro sai a Comunicação de Serviço em Word, já timbrada e pronta para assinar.</p>
    {aviso_modelo}
    <div class="cartao"><h2>Panorama</h2><div class="grade">{cartoes_totais}</div></div>
    <form method="get" action="/verificacoes" class="painel" style="grid-template-columns:repeat(4,1fr) auto">
      <select name="situacao"><option value="">Situação: todas</option>
        {opcoes(SITUACOES_VERIFICACAO, filtros.get('situacao',''))}</select>
      <select name="canal"><option value="">Canal: todos</option>
        {opcoes(lista_ativa('canal_denuncia'), filtros.get('canal',''))}</select>
      <select name="bo"><option value="">Boletim: todos</option>
        {opcoes([o for o in OPCOES_BO if o], filtros.get('bo',''))}</select>
      <input name="busca" placeholder="Vítima, autor, protocolo, BO, OS…"
        value="{e(filtros.get('busca',''))}">
      <button class="botao">Filtrar</button>
    </form>
    {tabela}"""
    return pagina("Verificação de denúncias", corpo, usuario)


def pagina_verificacao_form(usuario, csrf, dados=None, verificacao_id=None, erro=""):
    dados = dados or {}
    novo = verificacao_id is None
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""

    def v(nome, padrao=""):
        valor = dados.get(nome)
        return padrao if valor in (None, "") else valor

    con = conexao()
    pessoas = con.execute("SELECT id, nome, endereco, rg, cpf FROM pessoas ORDER BY nome").fetchall()
    ocorrencias = con.execute(
        "SELECT id, tipo_crime, numero_bo, data_fato FROM ocorrencias ORDER BY id DESC LIMIT 300"
    ).fetchall()
    eu = con.execute("SELECT nome, cargo, masp FROM usuarios WHERE id=?",
                     (usuario["id"],)).fetchone()
    equipe_atual = set()
    if verificacao_id:
        equipe_atual = {str(r["usuario_id"]) for r in con.execute(
            "SELECT usuario_id FROM verificacao_equipe WHERE verificacao_id=?", (verificacao_id,))}
    equipe_ids = dados.get("equipe_ids", equipe_atual)
    if isinstance(equipe_ids, str):
        equipe_ids = {equipe_ids}
    else:
        equipe_ids = {str(x) for x in (equipe_ids or [])}
    usuarios_equipe = con.execute(
        "SELECT id, nome, cargo, masp FROM usuarios WHERE ativo=1 AND id<>? ORDER BY nome COLLATE NOCASE",
        (usuario["id"],)).fetchall()
    con.close()

    dl_pessoas = "".join(
        f'<option value="{e(p["nome"])}" data-id="{p["id"]}" '
        f'data-endereco="{e(p["endereco"] or "")}" data-rg="{e(p["rg"] or "")}" '
        f'data-cpf="{e(p["cpf"] or "")}">' for p in pessoas)
    dl_ocorrencias = "".join(
        f'<option value="{e(o["numero_bo"] or o["tipo_crime"] or "Ocorrência")} — '
        f'{e(fmt_dia(o["data_fato"])) or "sem data"} (#{o["id"]})" data-id="{o["id"]}">'
        for o in ocorrencias)
    opcoes_equipe = "".join(
        f'<label class="opcao"><input type="checkbox" name="equipe_ids" value="{u["id"]}"'
        f'{" checked" if str(u["id"]) in equipe_ids else ""}> '
        f'{e(u["nome"])}{(" — " + e(u["cargo"])) if u["cargo"] else ""}'
        f'{(" (MASP: " + e(u["masp"]) + ")") if u["masp"] else ""}</label>'
        for u in usuarios_equipe)

    nome_vitima_atual = v("nome_vitima")
    nome_autor_atual = v("nome_autor")
    if dados.get("pessoa_vitima_id") and not nome_vitima_atual:
        nome_vitima_atual = next((p["nome"] for p in pessoas
                                  if str(p["id"]) == str(dados["pessoa_vitima_id"])), "")

    hoje = agora()[:10]
    corpo = f"""
    <div class="cab"><h1>{'Nova verificação de denúncia' if novo else f'Editar verificação #{verificacao_id}'}</h1></div>
    <datalist id="dl_pessoas">{dl_pessoas}</datalist>
    <datalist id="dl_ocorrencias">{dl_ocorrencias}</datalist>
    <form method="post" action="{'/verificacoes/nova' if novo else f'/verificacoes/{verificacao_id}/editar'}">
      <input type="hidden" name="csrf" value="{e(csrf)}">

      <fieldset><legend>Origem da denúncia</legend><div class="grade">
        <label>Protocolo de atendimento
          <input name="protocolo" value="{e(v('protocolo'))}" placeholder="Ex.: 4771361"></label>
        <label>Canal de origem
          <select name="canal_origem"><option value="">— não informado —</option>{opcoes(lista_ativa_com_atual('canal_denuncia', v('canal_origem')), v('canal_origem'))}</select></label>
        <label>Órgão de origem / encaminhamento
          <select name="orgao_origem"><option value="">— não informado —</option>{opcoes(lista_ativa_com_atual('orgao_origem_denuncia', v('orgao_origem')), v('orgao_origem'))}</select></label>
        <label>Data da denúncia
          <input type="date" name="data_denuncia" value="{e(v('data_denuncia', hoje))}"></label>
        <label>Data do fato
          <input type="date" name="data_fato" value="{e(v('data_fato'))}"></label>
        <label>Natureza / tipo
          <select name="tipo_denuncia"><option value="">— não informado —</option>{opcoes(lista_ativa_com_atual('tipo_crime', v('tipo_denuncia')), v('tipo_denuncia'))}</select></label>
        <label>Município
          <input name="municipio" id="municipio_verif" value="{e(v('municipio'))}" placeholder="Ex.: Itajubá"></label>
        <label>Local do fato (endereço, se souber)
          <input name="local_fato" id="end_fato" value="{e(v('local_fato'))}"
            placeholder="Ex.: Rua José Paes, 52 — Jardim das Colinas"></label>
        <label>Latitude do local do fato
          <input name="lat_fato" id="lat_fato" value="{e(v('lat_fato'))}" placeholder="Ex.: -22.4267"></label>
        <label>Longitude do local do fato
          <input name="lon_fato" id="lon_fato" value="{e(v('lon_fato'))}" placeholder="Ex.: -45.4581"></label>
        <div class="acoes span2" style="justify-content:flex-start">
          <button type="button" class="botao fantasma mini"
            onclick="geocodificar('end_fato','lat_fato','lon_fato','municipio_verif')">
            Localizar coordenadas pelo endereço</button>
        </div>
        <label class="span2">Resumo da denúncia (vai para "Dos fatos" na comunicação)
          <textarea name="resumo_denuncia" rows="4"
            placeholder="Trata-se de apuração de…">{e(v('resumo_denuncia'))}</textarea></label>
      </div></fieldset>

      <fieldset><legend>Vítima</legend><div class="grade">
        <label class="span2">Nome da vítima
          <input list="dl_pessoas" name="nome_vitima" id="ver_vitima_nome"
            value="{e(nome_vitima_atual)}" placeholder="Digite o nome — se já estiver cadastrada, o sistema traz a qualificação e o endereço"></label>
        <input type="hidden" name="pessoa_vitima_id" id="ver_vitima_id" value="{e(v('pessoa_vitima_id'))}">
        <label>RG da vítima
          <input name="rg_vitima" id="rg_vitima" value="{e(v('rg_vitima'))}" placeholder="Documento relacionado (opcional)"></label>
        <label>CPF da vítima
          <input name="cpf_vitima" id="cpf_vitima" value="{e(v('cpf_vitima'))}" placeholder="Documento relacionado (opcional)"></label>
        <label class="span2">Endereço da vítima
          <input name="endereco_vitima" id="end_vitima" value="{e(v('endereco_vitima'))}"
            placeholder="Rua, número, bairro, cidade"></label>
        <label>Latitude
          <input name="lat_vitima" id="lat_vitima" value="{e(v('lat_vitima'))}" placeholder="Ex.: -22.4267"></label>
        <label>Longitude
          <input name="lon_vitima" id="lon_vitima" value="{e(v('lon_vitima'))}" placeholder="Ex.: -45.4581"></label>
        <div class="acoes span2" style="justify-content:flex-start">
          <button type="button" class="botao fantasma mini"
            onclick="geocodificar('end_vitima','lat_vitima','lon_vitima','municipio_verif')">
            Localizar coordenadas pelo endereço</button>
        </div>
      </div></fieldset>

      <fieldset><legend>Autor / investigado</legend><div class="grade">
        <label class="span2">Nome do autor / investigado
          <input list="dl_pessoas" name="nome_autor" id="ver_autor_nome"
            value="{e(nome_autor_atual)}" placeholder="Digite o nome"></label>
        <input type="hidden" name="pessoa_autor_id" id="ver_autor_id" value="{e(v('pessoa_autor_id'))}">
        <label>RG do autor / investigado
          <input name="rg_autor" id="rg_autor" value="{e(v('rg_autor'))}" placeholder="Documento relacionado (opcional)"></label>
        <label>CPF do autor / investigado
          <input name="cpf_autor" id="cpf_autor" value="{e(v('cpf_autor'))}" placeholder="Documento relacionado (opcional)"></label>
        <label class="span2">Endereço do autor
          <input name="endereco_autor" id="end_autor" value="{e(v('endereco_autor'))}"
            placeholder="Rua, número, bairro, cidade"></label>
        <label>Latitude
          <input name="lat_autor" id="lat_autor" value="{e(v('lat_autor'))}" placeholder="Ex.: -22.4267"></label>
        <label>Longitude
          <input name="lon_autor" id="lon_autor" value="{e(v('lon_autor'))}" placeholder="Ex.: -45.4581"></label>
        <div class="acoes span2" style="justify-content:flex-start">
          <button type="button" class="botao fantasma mini"
            onclick="geocodificar('end_autor','lat_autor','lon_autor','municipio_verif')">
            Localizar coordenadas pelo endereço</button>
        </div>
        <label class="span2">Vínculo do autor com a vítima
          <input name="vinculo_autor_vitima" value="{e(v('vinculo_autor_vitima'))}"
            placeholder="Ex.: filho, companheiro, vizinho, cuidador"></label>
      </div>
      <p class="suave">Com as coordenadas preenchidas, os pontos da vítima, do autor e do local
      do fato aparecem no <a href="/mapa">Mapa</a>, junto com as ocorrências.</p></fieldset>

      <fieldset><legend>Boletim de ocorrência</legend><div class="grade">
        <label>Foi registrado boletim de ocorrência?
          <select name="bo_registrado">{opcoes(OPCOES_BO, v('bo_registrado'))}</select></label>
        <label>Número do boletim (REDS)
          <input name="numero_bo" value="{e(v('numero_bo'))}" placeholder="Ex.: 2026-033379256-001"></label>
        <label class="span2">Ocorrência já cadastrada no SIRIO (opcional)
          <input list="dl_ocorrencias" id="ver_oc_nome" placeholder="Digite para localizar"
            value="">
          <input type="hidden" name="ocorrencia_id" id="ver_oc_id" value="{e(v('ocorrencia_id'))}"></label>
      </div></fieldset>

      <fieldset><legend>Averiguação</legend><div class="grade">
        <div class="span2"><span class="rot">Equipe de averiguação (opcional)</span>
          <p class="suave">Marque quem participou com você. Os integrantes selecionados também
          constarão como assinantes na Comunicação de Serviço.</p>
          <div class="opcoes-multiplas">{opcoes_equipe or '<span class="suave">Não há outros usuários ativos cadastrados.</span>'}</div>
        </div>
        <label class="span2">Relatório de averiguação inicial
          <textarea name="relatorio_averiguacao" rows="14"
            placeholder="Escreva livremente. Cada parágrafo separado por uma linha em branco vira um parágrafo na comunicação, sob o título 'Das diligências realizadas'.">{e(v('relatorio_averiguacao'))}</textarea></label>
        <label class="span2">Diligências pendentes / sugestões (uma por linha — viram lista numerada)
          <textarea name="diligencias_pendentes" rows="6">{e(v('diligencias_pendentes'))}</textarea></label>
        <label class="span2">Conclusão (opcional)
          <textarea name="conclusao" rows="4">{e(v('conclusao'))}</textarea></label>
        <label>Situação
          <select name="situacao">{opcoes(SITUACOES_VERIFICACAO, v('situacao', 'em_verificacao'))}</select></label>
        <label>Observações internas
          <input name="observacoes" value="{e(v('observacoes'))}"></label>
      </div></fieldset>

      <fieldset><legend>Dados da Comunicação de Serviço</legend><div class="grade">
        <label>Nº da comunicação
          <input name="numero_comunicacao" value="{e(v('numero_comunicacao', proximo_numero_comunicacao() if novo else ''))}"></label>
        <label>Data da comunicação
          <input type="date" name="data_comunicacao" value="{e(v('data_comunicacao', hoje))}"></label>
        <label>Nº da OS
          <input name="numero_os" value="{e(v('numero_os'))}"></label>
        <label>PCNET
          <input name="numero_pcnet" value="{e(v('numero_pcnet'))}"></label>
        <label class="span2">REQ — o que foi requisitado pela autoridade
          <textarea name="requisicao" rows="2">{e(v('requisicao'))}</textarea></label>
        <label>Destinatário
          <input name="destinatario" value="{e(v('destinatario', 'Senhora Delegada'))}"></label>
        <label>Quem assina
          <input name="assinante_nome" value="{e(v('assinante_nome', eu['nome'] if eu else usuario['nome']))}"></label>
        <label>Cargo
          <input name="assinante_cargo" value="{e(v('assinante_cargo', (eu['cargo'] if eu and eu['cargo'] else 'Investigador de Polícia')))}"></label>
        <label>MASP
          <input name="assinante_masp" value="{e(v('assinante_masp', (eu['masp'] if eu and eu['masp'] else '')))}"></label>
      </div>
      <p class="suave">O cargo e o MASP ficam guardados no seu usuário e já vêm preenchidos
      nas próximas verificações.</p></fieldset>

      {msg}
      <div class="acoes">
        <a class="botao fantasma" href="{'/verificacoes' if novo else f'/verificacoes/{verificacao_id}'}">Cancelar</a>
        <button class="botao">{'Salvar verificação' if novo else 'Salvar alterações'}</button>
      </div>
    </form>
    <script>
    // Ao escolher alguém já cadastrado, guarda o id e — se o campo de endereço
    // ainda estiver vazio — traz o endereço do cadastro. Nunca sobrescreve o
    // que a servidora já digitou: o endereço apurado agora tem precedência.
    function ligaAutocompletar(campoNome, campoId, listaId, campoEndereco, campoRg, campoCpf) {{
      var campo = document.getElementById(campoNome);
      if (!campo) return;
      campo.addEventListener('input', function() {{
        var opt = document.querySelector('#' + listaId + ' option[value="' +
          this.value.replace(/"/g, '\\\\"') + '"]');
        document.getElementById(campoId).value = opt ? opt.getAttribute('data-id') : '';
        if (opt && campoEndereco) {{
          var destino = document.getElementById(campoEndereco);
          var doCadastro = opt.getAttribute('data-endereco') || '';
          if (destino && !destino.value.trim() && doCadastro) destino.value = doCadastro;
        }}
        var rg = document.getElementById(campoRg);
        var cpf = document.getElementById(campoCpf);
        if (opt && rg && !rg.value.trim()) rg.value = opt.getAttribute('data-rg') || '';
        if (opt && cpf && !cpf.value.trim()) cpf.value = opt.getAttribute('data-cpf') || '';
      }});
    }}
    ligaAutocompletar('ver_vitima_nome', 'ver_vitima_id', 'dl_pessoas', 'end_vitima', 'rg_vitima', 'cpf_vitima');
    ligaAutocompletar('ver_autor_nome', 'ver_autor_id', 'dl_pessoas', 'end_autor', 'rg_autor', 'cpf_autor');
    ligaAutocompletar('ver_oc_nome', 'ver_oc_id', 'dl_ocorrencias');
    </script>
    {SCRIPT_GEOCODIFICADOR}"""
    return pagina("Nova verificação" if novo else "Editar verificação", corpo, usuario)


def galeria_fotos_verificacao(usuario, csrf, verificacao_id, fotos):
    itens = "".join(
        f'<figure class="foto"><a href="/fotos/{e(f["arquivo"])}" target="_blank" rel="noopener">'
        f'<img src="/fotos/{e(f["arquivo"])}" alt="Foto da averiguação" loading="lazy"></a>'
        f'<figcaption>{e(f["legenda"]) or ""}'
        + (f'<form method="post" action="/verificacoes/fotos/{f["id"]}/excluir" '
           f'onsubmit="return confirm(\'Excluir esta foto?\')"><input type="hidden" name="csrf" value="{e(csrf)}">'
           f'<button class="botao perigo mini">Excluir</button></form>'
           if usuario["perfil"] in ("admin", "analista") else "")
        + '</figcaption></figure>' for f in fotos)
    envio = ""
    if usuario["perfil"] in ("admin", "analista"):
        envio = (f'<form method="post" action="/verificacoes/{verificacao_id}/fotos" enctype="multipart/form-data" '
                 f'class="grade" style="margin-top:1rem"><input type="hidden" name="csrf" value="{e(csrf)}">'
                 '<label>Legenda (opcional)<input name="legenda" placeholder="Ex.: fachada do imóvel"></label>'
                 '<label class="span2">Adicionar fotos (opcional — JPG, PNG, WEBP ou GIF; até 10 MB cada)'
                 '<input type="file" name="imagem" accept=".jpg,.jpeg,.png,.webp,.gif,image/*" multiple required></label>'
                 '<div class="acoes span2"><button class="botao">Enviar fotos</button></div></form>')
    return f'<div class="cartao"><h2>Fotos da averiguação</h2>{("<div class=\"galeria\">" + itens + "</div>") if itens else "<p class=\"suave\">Nenhuma foto anexada.</p>"}{envio}</div>'


def pagina_verificacao_detalhe(usuario, csrf, v, vitima, autor, ocorrencia, nomes_usuarios, equipe, fotos, envolvidos):
    pode_editar = usuario["perfil"] in ("admin", "analista")

    def bloco(rotulo, texto):
        if not texto:
            return ""
        return (f'<div class="cartao"><h2>{e(rotulo)}</h2>'
                f'<div class="li-campo"><span class="val">{e(texto)}</span></div></div>')

    link_vitima = (f'<a class="nomelink" href="/pessoas/{vitima["id"]}">{e(vitima["nome"])}</a>'
                   if vitima else (e(v["nome_vitima"]) or "—"))
    link_autor = (f'<a class="nomelink" href="/pessoas/{autor["id"]}">{e(autor["nome"])}</a>'
                  if autor else (e(v["nome_autor"]) or "—"))
    link_oc = (f'<a class="nomelink" href="/ocorrencias/{ocorrencia["id"]}">'
               f'{e(ocorrencia["numero_bo"] or ocorrencia["tipo_crime"] or "Ver ocorrência")}</a>'
               if ocorrencia else "")

    acoes = ""
    if pode_editar:
        acoes += f'<a class="botao fantasma" href="/verificacoes/{v["id"]}/editar">Editar</a>'
    if modelo_comunicacao_disponivel():
        acoes += (f'<a class="botao" href="/verificacoes/{v["id"]}/comunicacao.docx">'
                  f'Gerar Comunicação de Serviço (Word)</a>')
    if usuario["perfil"] == "admin":
        acoes += f"""<form method="post" action="/verificacoes/{v['id']}/excluir"
          onsubmit="return confirm('Excluir definitivamente esta verificação?')" style="display:inline">
          <input type="hidden" name="csrf" value="{e(csrf)}">
          <button class="botao perigo">Excluir</button></form>"""

    criado_por = nomes_usuarios.get(v["criado_por"], "—")
    tem_ponto = any((v["lat_fato"], v["lat_vitima"], v["lat_autor"]))
    link_mapa = ('  ·  <a href="/mapa">Ver os pontos desta verificação no Mapa</a>'
                 if tem_ponto else "")
    corpo = f"""
    <div class="cab"><h1>Verificação #{v['id']}</h1><div class="acoes">{acoes}</div></div>
    <p class="suave">{pill_situacao_verificacao(v['situacao'])}
      &nbsp;·&nbsp; registrada por {e(criado_por)} em {e(fmt_dia(v['criado_em'][:10] if v['criado_em'] else ''))}</p>

    <div class="cartoes">
      <div class="cartao"><h2>Origem da denúncia</h2><div class="grade">
        {li_campo('Protocolo de atendimento', v['protocolo'])}
        {li_campo('Canal de origem', v['canal_origem'])}
        {li_campo('Órgão de origem', v['orgao_origem'])}
        {li_campo('Data da denúncia', fmt_dia(v['data_denuncia']))}
        {li_campo('Data do fato', fmt_dia(v['data_fato']))}
        {li_campo('Natureza', v['tipo_denuncia'])}
        {li_campo('Município', v['municipio'])}
        {li_campo('Local do fato', v['local_fato'])}
        {li_campo('Coordenadas do local do fato', fmt_coord(v['lat_fato'], v['lon_fato']))}
      </div></div>
      <div class="cartao"><h2>Envolvidos</h2><div class="grade">
        <div class="li-campo"><span class="rot">Vítima</span><span class="val">{link_vitima}</span></div>
        <div class="li-campo"><span class="rot">Autor / investigado</span><span class="val">{link_autor}</span></div>
        {li_campo('Endereço da vítima', v['endereco_vitima'])}
        {li_campo('Endereço do autor', v['endereco_autor'])}
        {li_campo('RG da vítima', v['rg_vitima'])}
        {li_campo('CPF da vítima', v['cpf_vitima'])}
        {li_campo('RG do autor / investigado', v['rg_autor'])}
        {li_campo('CPF do autor / investigado', v['cpf_autor'])}
        {li_campo('Coordenadas da vítima', fmt_coord(v['lat_vitima'], v['lon_vitima']))}
        {li_campo('Coordenadas do autor', fmt_coord(v['lat_autor'], v['lon_autor']))}
        {li_campo('Vínculo com a vítima', v['vinculo_autor_vitima'])}
      </div></div>
    </div>

    <div class="cartao"><h2>Boletim de ocorrência</h2><div class="grade">
      {li_campo('Foi registrado?', v['bo_registrado'])}
      {li_campo('Número (REDS)', v['numero_bo'])}
      {'<div class="li-campo"><span class="rot">Ocorrência no SIRIO</span><span class="val">' + link_oc + '</span></div>' if link_oc else ''}
    </div></div>

    {bloco('Resumo da denúncia', v['resumo_denuncia'])}
    {bloco('Relatório de averiguação inicial', v['relatorio_averiguacao'])}
    {bloco('Diligências pendentes / sugestões', v['diligencias_pendentes'])}
    {bloco('Conclusão', v['conclusao'])}
    {bloco('Observações internas', v['observacoes'])}
    <div class="cartao"><h2>Equipe de averiguação</h2><div class="grade">
      {''.join(li_campo('Integrante / também assina', m['nome'] + ((' — ' + m['cargo']) if m['cargo'] else '') + ((' · MASP: ' + m['masp']) if m['masp'] else '')) for m in equipe) or '<p class="suave">A averiguação foi realizada sem integrantes adicionais registrados.</p>'}
    </div></div>
    <div class="cartao"><h2>Pessoas e tipo de envolvimento</h2><div class="grade">
      {''.join(li_campo(TIPOS_ENVOLVIMENTO_VERIFICACAO.get(p['tipo_envolvimento'], p['tipo_envolvimento']), p['nome'] + ((' · RG: ' + p['rg']) if p['rg'] else '') + ((' · CPF: ' + p['cpf']) if p['cpf'] else '')) for p in envolvidos) or '<p class="suave">Nenhuma pessoa relacionada foi registrada.</p>'}
    </div></div>

    <div class="cartao"><h2>Comunicação de Serviço</h2><div class="grade">
      {li_campo('Número', v['numero_comunicacao'])}
      {li_campo('Data', fmt_dia(v['data_comunicacao']))}
      {li_campo('OS', v['numero_os'])}
      {li_campo('PCNET', v['numero_pcnet'])}
      {li_campo('Destinatário', v['destinatario'])}
      {li_campo('Assina', (v['assinante_nome'] or '') + ((' — ' + v['assinante_cargo']) if v['assinante_cargo'] else ''))}
      {li_campo('MASP', v['assinante_masp'])}
      {li_campo('REQ', v['requisicao'])}
    </div></div>

    {galeria_fotos_verificacao(usuario, csrf, v['id'], fotos)}

    <p><a href="/verificacoes">← Voltar para a lista</a>{link_mapa}</p>"""
    return pagina(f"Verificação #{v['id']}", corpo, usuario)


# ---------------------------------------------------------------------------
# Pontos para o Mapa
#
# Devolve os pontos das verificações no mesmo formato usado pelas ocorrências,
# com "origem" para o mapa saber distinguir uma denúncia em apuração de uma
# ocorrência já registrada, e "grupo" para ligar autor e local do fato da mesma
# verificação sem colidir com os identificadores das ocorrências.

def pontos_mapa_verificacoes():
    con = conexao()
    registros = con.execute(
        "SELECT * FROM verificacoes WHERE lat_fato IS NOT NULL OR lat_vitima IS NOT NULL "
        "OR lat_autor IS NOT NULL").fetchall()
    con.close()

    pontos = []
    for v in registros:
        base = {
            "origem": "verificacao",
            "ocorrencia_id": None,
            "verificacao_id": v["id"],
            "grupo": f"vf-{v['id']}",
            "link": f"/verificacoes/{v['id']}",
            "tipo_crime": v["tipo_denuncia"],
            "nome_autor": v["nome_autor"],
            "data_fato": fmt_dia(v["data_fato"]),
            "materiais": [],
            "bairro": None,
            "cidade": v["municipio"],
        }
        if v["lat_fato"] and v["lon_fato"]:
            pontos.append({**base, "tipo_ponto": "fato", "nome": None,
                           "endereco": v["local_fato"],
                           "lat": v["lat_fato"], "lon": v["lon_fato"]})
        if v["lat_vitima"] and v["lon_vitima"]:
            pontos.append({**base, "tipo_ponto": "vitima", "nome": v["nome_vitima"],
                           "endereco": v["endereco_vitima"], "cidade": None,
                           "lat": v["lat_vitima"], "lon": v["lon_vitima"]})
        if v["lat_autor"] and v["lon_autor"]:
            pontos.append({**base, "tipo_ponto": "autor", "nome": v["nome_autor"],
                           "endereco": v["endereco_autor"], "cidade": None,
                           "lat": v["lat_autor"], "lon": v["lon_autor"]})
    return pontos


# ---------------------------------------------------------------------------
# Gravação

CAMPOS_VERIFICACAO = [
    "protocolo", "canal_origem", "orgao_origem", "data_denuncia", "data_fato",
    "tipo_denuncia", "municipio", "local_fato", "resumo_denuncia",
    "nome_vitima", "pessoa_vitima_id", "rg_vitima", "cpf_vitima", "endereco_vitima", "lat_vitima", "lon_vitima",
    "nome_autor", "pessoa_autor_id", "rg_autor", "cpf_autor", "endereco_autor", "lat_autor", "lon_autor",
    "lat_fato", "lon_fato", "vinculo_autor_vitima", "numero_os", "numero_pcnet", "requisicao",
    "bo_registrado", "numero_bo", "ocorrencia_id", "relatorio_averiguacao",
    "diligencias_pendentes", "conclusao", "situacao", "numero_comunicacao",
    "data_comunicacao", "destinatario", "assinante_nome", "assinante_cargo",
    "assinante_masp", "observacoes",
]


def valida_verificacao(d):
    if not (d.get("nome_vitima") or "").strip() and not (d.get("nome_autor") or "").strip():
        return "Informe ao menos o nome da vítima ou o nome do autor."
    for rotulo, campo in (("Data da denúncia", "data_denuncia"),
                          ("Data do fato", "data_fato"),
                          ("Data da comunicação", "data_comunicacao")):
        erro = valida_data(d.get(campo), rotulo)
        if erro:
            return erro
    for rotulo, campo in (("Resumo da denúncia", "resumo_denuncia"),
                          ("Relatório de averiguação", "relatorio_averiguacao"),
                          ("Diligências pendentes", "diligencias_pendentes"),
                          ("Conclusão", "conclusao")):
        erro = valida_tamanho(d.get(campo), rotulo, 20000)
        if erro:
            return erro
    for rotulo, campo in (("RG da vítima", "rg_vitima"), ("CPF da vítima", "cpf_vitima"),
                          ("RG do autor / investigado", "rg_autor"), ("CPF do autor / investigado", "cpf_autor")):
        erro = valida_tamanho(d.get(campo), rotulo, 100)
        if erro:
            return erro
    for rotulo, campo, limite in (("Latitude da vítima", "lat_vitima", 90),
                                  ("Longitude da vítima", "lon_vitima", 180),
                                  ("Latitude do autor", "lat_autor", 90),
                                  ("Longitude do autor", "lon_autor", 180),
                                  ("Latitude do local do fato", "lat_fato", 90),
                                  ("Longitude do local do fato", "lon_fato", 180)):
        erro = valida_coordenada(d.get(campo), rotulo, limite)
        if erro:
            return erro
    if d.get("situacao") and d["situacao"] not in SITUACAO_VERIFICACAO_LABEL:
        return "Situação inválida."
    return ""


def valores_verificacao(d):
    valores = {c: (d.get(c) or "").strip() for c in CAMPOS_VERIFICACAO}
    valores["pessoa_vitima_id"] = _id_ou_none(d.get("pessoa_vitima_id"))
    valores["pessoa_autor_id"] = _id_ou_none(d.get("pessoa_autor_id"))
    valores["ocorrencia_id"] = _id_ou_none(d.get("ocorrencia_id"))
    for campo in ("lat_vitima", "lon_vitima", "lat_autor", "lon_autor", "lat_fato", "lon_fato"):
        valores[campo] = _coord_ou_none(d.get(campo))
    valores["situacao"] = valores["situacao"] or "em_verificacao"
    return valores


def salva_assinatura_no_usuario(con, usuario_id, cargo, masp):
    if cargo or masp:
        con.execute("UPDATE usuarios SET cargo=?, masp=? WHERE id=?",
                    (cargo or None, masp or None, usuario_id))


def salva_equipe_verificacao(con, verificacao_id, equipe_ids, usuario_responsavel_id):
    """Guarda uma cópia dos dados de assinatura para preservar o documento histórico."""
    ids = []
    for valor in equipe_ids or []:
        ident = _id_ou_none(valor)
        if ident and ident != usuario_responsavel_id and ident not in ids:
            ids.append(ident)
    con.execute("DELETE FROM verificacao_equipe WHERE verificacao_id=?", (verificacao_id,))
    if not ids:
        return
    marcas = ",".join("?" for _ in ids)
    usuarios = con.execute(
        f"SELECT id, nome, cargo, masp FROM usuarios WHERE ativo=1 AND id IN ({marcas})", ids).fetchall()
    con.executemany(
        "INSERT INTO verificacao_equipe (verificacao_id, usuario_id, nome, cargo, masp) VALUES (?,?,?,?,?)",
        [(verificacao_id, u["id"], u["nome"], u["cargo"], u["masp"]) for u in usuarios])


def salva_envolvidos_verificacao(con, verificacao_id, valores, usuario_id):
    """Mantém um registro próprio de cada pessoa e de seu tipo de envolvimento."""
    con.execute("DELETE FROM verificacao_envolvidos WHERE verificacao_id=?", (verificacao_id,))
    envolvidos = [
        ("vitima", valores["pessoa_vitima_id"], valores["nome_vitima"], valores["rg_vitima"], valores["cpf_vitima"]),
        ("autor_investigado", valores["pessoa_autor_id"], valores["nome_autor"], valores["rg_autor"], valores["cpf_autor"]),
    ]
    con.executemany(
        "INSERT INTO verificacao_envolvidos (verificacao_id, pessoa_id, nome, tipo_envolvimento, rg, cpf, criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?)",
        [(verificacao_id, pessoa_id, nome, tipo, rg or None, cpf or None, agora(), usuario_id)
         for tipo, pessoa_id, nome, rg, cpf in envolvidos if nome])
