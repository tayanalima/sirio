"""Módulo SIRIO — Importação de Boletim de Ocorrência (PDF) e CSV.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403
from sirio_vd_core import *  # noqa: F401,F403

_BO_CEP = re.compile(r"\d{5}-?\d{3}")

_BO_DESCARTAR = {"XXXX", "XXXXX", "IGNORADO", "NAO SE APLICA", "NÃO SE APLICA",
                 "NÃO", "NAO", "INFORMAÇÃO DESCONHECIDA", "SEM LESOES APARENTES",
                 "BRASIL", "MG", "NÚMERO", "COMPLEMENTO", "KM", "BAIRRO",
                 "MUNICÍPIO", "PAÍS", "CEP", "UF"}

_BO_ROTULOS = (
    "SEXO", "TIPO ENVOLVIMENTO", "TIPO DE PESSOA", "COD. NATUREZA", "TENTADO / CONSUMADO",
    "DESCRIÇÃO NATUREZA", "NOME COMPLETO", "APELIDOS", "NACIONALIDADE", "DATA NASCIMENTO",
    "NATURALIDADE / UF", "IDENTIDADE DE GÊNERO", "IDADE APARENTE", "GRAU DA LESÃO",
    "ESTADO CIVIL", "ORIENTAÇÃO SEXUAL", "OCUPAÇÃO ATUAL", "COR / RAÇA", "MÃE", "PAI",
    "TIPO DO DOCUMENTO DE IDENTIFICAÇÃO", "NÚMERO DOCUMENTO IDENTIDADE", "ÓRGÃO EXPEDIDOR",
    "UF", "CPF / CNPJ", "ESCOLARIDADE", "PESSOA EM SITUAÇÃO DE RUA?",
    "ENDEREÇO (AV., RUA, ETC)", "NÚMERO", "COMPLEMENTO", "KM", "BAIRRO", "MUNICÍPIO",
    "PAÍS", "CEP",
)


def _bo_limpa(s):
    if not s:
        return None
    s = " ".join(s.split())
    return s if s and s.upper() not in _BO_DESCARTAR else None


def _bo_eh_rotulo(linha):
    u = linha.strip().upper()
    return any(u == r or u.startswith(r) for r in _BO_ROTULOS)


def _bo_valor_depois(linhas, rotulo):
    for i, l in enumerate(linhas):
        if l.strip().upper().startswith(rotulo.upper()):
            for j in range(i + 1, min(i + 3, len(linhas))):
                if _bo_eh_rotulo(linhas[j]):
                    break
                v = _bo_limpa(linhas[j])
                if v:
                    return v
    return None


def _bo_valor_coluna(linhas, rotulo):
    """Para rótulos que a extração de texto do PDF junta na mesma linha com
    outro campo vizinho (ex.: uma linha só "SEXO   TIPO ENVOLVIMENTO", com o
    valor de cada um colado na linha seguinte, também lado a lado — "MASCULINO
    AUTOR"), localiza a posição (coluna) do rótulo procurado e lê o valor na
    mesma posição da linha de baixo, em vez de assumir que o valor ocupa a
    linha inteira."""
    rotulo_upper = rotulo.upper()
    for i, l in enumerate(linhas):
        if rotulo_upper in l.upper():
            segmentos_rotulo = [s.strip() for s in re.split(r"\s{2,}", l) if s.strip()]
            idx = next((k for k, seg in enumerate(segmentos_rotulo) if rotulo_upper in seg.upper()), None)
            if idx is None or i + 1 >= len(linhas):
                continue
            segmentos_valor = [s.strip() for s in re.split(r"\s{2,}", linhas[i + 1]) if s.strip()]
            if idx < len(segmentos_valor):
                v = _bo_limpa(segmentos_valor[idx])
                if v:
                    return v
    return None


def _bo_data_iso(d):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


_BO_IGNORAR_BAIRRO = {"CEP", "KM", "UF", "PAÍS", "COMPLEMENTO", "NÚMERO", "BRASIL"}


def _bo_endereco_estruturado(corpo):
    """Devolve dict {rua, numero, bairro, cidade} lendo um bloco de endereço do BO.
    O texto extraído do PDF mistura rótulos e valores fora de ordem visual e a
    ordem muda conforme a seção: no bloco do envolvido o valor da rua vem ANTES
    do rótulo "ENDEREÇO (AV..."; no bloco do topo (local do fato) vem DEPOIS do
    rótulo "LOCAL (AV...". Tratamos os dois casos."""
    linhas = corpo.split("\n")
    rua = numero = bairro = cidade = None
    for k, l in enumerate(linhas):
        u = l.strip().upper()
        if u.startswith("ENDEREÇO (AV") and k > 0:
            rua = _bo_limpa(linhas[k - 1])
        elif u.startswith("LOCAL (AV") and k + 1 < len(linhas):
            rua = _bo_limpa(linhas[k + 1])
        elif u.startswith("NÚMERO") and k + 1 < len(linhas):
            v = _bo_limpa(linhas[k + 1])
            if v and v.isdigit():
                numero = v
        if "BAIRRO" in u and bairro is None:
            for j in range(k - 1, max(k - 5, -1), -1):
                cand = linhas[j].strip()
                if not cand or cand.upper() in _BO_IGNORAR_BAIRRO:
                    continue
                segs = [s.strip() for s in re.split(r"\s{2,}", cand) if s.strip()]
                segs = [s for s in segs if _bo_limpa(s) and s.upper() not in _BO_IGNORAR_BAIRRO]
                # CEP e número puro não são bairro. Sem isto, o CEP que fica
                # perto do rótulo acaba gravado no campo de bairro.
                segs = [s for s in segs if not _BO_CEP.fullmatch(s) and not s.isdigit()]
                if segs:
                    bairro = segs[-1]
                    break
        if "MUNICÍPIO" in u and k + 1 < len(linhas) and cidade is None:
            segs = [s.strip() for s in re.split(r"\s{2,}", linhas[k + 1]) if s.strip()]
            segs = [s for s in segs if _bo_limpa(s)]
            if segs:
                cidade = segs[0]
    return {"rua": rua, "numero": numero, "bairro": bairro, "cidade": cidade}


def _bo_numero_texto(numero):
    """Devolve 'nº 123', ou None quando não há número utilizável.

    O BO preenche 0 quando o imóvel não tem numeração (povoado, zona rural).
    Gravar 'nº 0' passa a impressão de que o número é conhecido."""
    if not numero:
        return None
    if str(numero).strip() in ("0", "00", "000"):
        return None
    return f"nº {numero}"


def _bo_endereco(corpo):
    """Endereço completo, para campos de texto livre (pessoa, autor, vítima),
    que não têm colunas separadas de bairro e cidade."""
    d = _bo_endereco_estruturado(corpo)
    partes = [x for x in [d["rua"], _bo_numero_texto(d["numero"]),
                          d["bairro"], d["cidade"]] if x]
    return ", ".join(partes) if partes else None


def _bo_endereco_sem_bairro_cidade(endereco, bairro, cidade):
    """Tira bairro e cidade de um endereço já montado.

    Usado quando o endereço do fato vem por sugestão do endereço do envolvido,
    que é texto completo. A ocorrência tem colunas próprias para bairro e cidade,
    então deixá-los na linha de endereço duplicaria a informação na tela."""
    if not endereco:
        return endereco
    partes = [p.strip() for p in endereco.split(",") if p.strip()]
    descartar = {x.strip().upper() for x in (bairro, cidade) if x}
    mantidas = [p for p in partes if p.upper() not in descartar]
    return ", ".join(mantidas) if mantidas else endereco


def _bo_historico(texto):
    """Extrai o parágrafo de histórico da ocorrência, entre o título da seção
    e o início da seção de Perícia Técnica (ou fim do documento)."""
    m = re.search(r"HISTÓRICO DA OCORRÊNCIA\s*/?\s*ATIVIDADE\d*\s*\n(.*?)(?=Perícia Técnica|$)",
                  texto, re.S)
    if not m:
        return None
    linhas = [l.strip() for l in m.group(1).split("\n")]
    linhas = [l for l in linhas if l and l.upper() not in ("6", "*")]
    return "\n".join(linhas) if linhas else None


def _bo_local_fato(texto, fallback_bairro=None, fallback_cidade=None, fallback_endereco=None):
    """Extrai local do fato e data do fato a partir da seção
    'DADOS DA OCORRÊNCIA / ATIVIDADE' (topo do BO, antes dos envolvidos).
    Quando bairro/cidade não são encontrados nessa seção (layout mais denso e
    sujeito a ruído), usamos como sugestão o endereço já identificado do autor —
    sempre editável na tela de conferência, nunca gravado sem revisão."""
    i = texto.find("DADOS DA OCORRÊNCIA")
    j = texto.find("QUALIFICAÇÃO DOS ENVOLVIDOS")
    if i < 0:
        endereco_d = {"rua": None, "bairro": None, "cidade": None}
    else:
        bloco = texto[i:j if j > i else i + 3000]
        endereco_d = _bo_endereco_estruturado(bloco)
    bairro = endereco_d["bairro"] or fallback_bairro
    cidade = endereco_d["cidade"] or fallback_cidade
    rua = endereco_d["rua"]
    if rua:
        # A ocorrência tem colunas próprias para bairro e cidade. Repeti-los aqui
        # fazia a informação aparecer duas vezes na tela de conferência. O campo
        # de endereço do fato leva apenas logradouro e número.
        partes = [x for x in [rua, _bo_numero_texto(endereco_d["numero"])] if x]
        endereco = ", ".join(partes)
    else:
        endereco = _bo_endereco_sem_bairro_cidade(fallback_endereco, bairro, cidade)
    bloco_datas = texto[i:j if (i >= 0 and j > i) else (i + 3000 if i >= 0 else len(texto))]
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", bloco_datas) if i >= 0 else []
    data_fato = _bo_data_iso(datas[0]) if datas else None
    return {"endereco": endereco, "cidade": cidade, "bairro": bairro, "data_fato": data_fato}


def _bo_materiais(texto):
    """Extrai os itens da seção 'MATERIAIS E ARMAS BRANCAS' (materiais apreendidos)."""
    def valor_linha_seguinte(linhas, rotulo):
        """Só olha a linha imediatamente seguinte ao rótulo — a lista de rótulos
        conhecidos da seção de envolvidos não cobre os rótulos desta seção, então
        não reaproveitamos _bo_valor_depois aqui (ele erraria o ponto de parada)."""
        for k, l in enumerate(linhas):
            if l.strip().upper().startswith(rotulo):
                if k + 1 < len(linhas):
                    v = linhas[k + 1].strip()
                    segs = [s.strip() for s in re.split(r"\s{2,}", v) if s.strip()]
                    segs = [s for s in segs if _bo_limpa(s)]
                    return segs[0] if segs else None
                return None
        return None

    partes = re.findall(
        r"MATERIAL\s+(\d+)\n(.*?)(?=MATERIAL\s+\d+\n|HISTÓRICO DA OCORRÊNCIA|$)", texto, re.S)
    materiais = []
    for num, corpo in partes:
        linhas = corpo.split("\n")
        envolv_nr = situacao = quantidade = None
        for l in linhas:
            m = re.match(r"\s*(\d+)\s+([A-ZÇÃÕÉÁÍÓÚ]+)\s+(\d+)\s*$", l)
            if m:
                envolv_nr, situacao, quantidade = m.group(1), m.group(2).title(), m.group(3)
                break
        objeto = valor_linha_seguinte(linhas, "OBJETO")
        cor = valor_linha_seguinte(linhas, "COR")
        info = None
        for k, l in enumerate(linhas):
            if l.strip().upper().startswith("INFORMAÇÕES COMPLEMENTARES"):
                resto = [x.strip() for x in linhas[k + 1:] if _bo_limpa(x)]
                info = " ".join(resto) if resto else None
                break
        marca = modelo = None
        for k, l in enumerate(linhas):
            if "MARCA" in l.upper() and "MODELO" in l.upper() and k + 1 < len(linhas):
                valores = [v for v in re.split(r"\s{2,}", linhas[k + 1].strip()) if v]
                valores = [v for v in valores if _bo_limpa(v)]
                # ordem do rótulo é "SÉRIE / IDENTIFICAÇÃO  MODELO  MARCA"
                if len(valores) >= 3:
                    modelo, marca = valores[-2], valores[-1]
                break
        materiais.append({
            "envolv_nr": envolv_nr, "situacao": situacao, "quantidade": quantidade or "1",
            "objeto": objeto, "marca": marca, "modelo": modelo, "cor": cor,
            "observacoes": info,
        })
    return materiais


def _bo_veiculos(texto):
    """Extrai veículos da seção própria do REDS, para conferência antes da gravação."""
    inicio = re.search(r"VE[IÍ]CULOS?(?:\s+ENVOLVIDOS)?", texto, re.I)
    if not inicio:
        return []
    trecho = texto[inicio.start():]
    trecho = re.split(r"\n(?:MATERIAIS E ARMAS|HISTÓRICO DA OCORRÊNCIA|PERÍCIA TÉCNICA)", trecho,
                       maxsplit=1, flags=re.I)[0]
    partes = re.findall(r"VE[IÍ]CULO\s+(\d+)\s*\n(.*?)(?=\nVE[IÍ]CULO\s+\d+\s*\n|$)", trecho, re.S | re.I)
    if not partes:
        partes = [("", trecho)]

    def valor(linhas, *rotulos):
        for i, linha in enumerate(linhas):
            u = linha.strip().upper()
            if any(u.startswith(r) for r in rotulos):
                for rotulo in rotulos:
                    if not u.startswith(rotulo):
                        continue
                    resto = linha.strip()[len(rotulo):].strip(" :.-")
                    if resto and resto.upper() not in _BO_DESCARTAR:
                        return resto
                for proxima in linhas[i + 1:i + 3]:
                    v = _bo_limpa(proxima)
                    if v:
                        return v
        return None

    veiculos = []
    for numero, corpo in partes:
        linhas = corpo.split("\n")
        placa = valor(linhas, "PLACA")
        if placa:
            placa = re.sub(r"[^A-Z0-9]", "", placa.upper())
        marca_modelo = valor(linhas, "MARCA / MODELO", "MARCA/MODELO")
        if marca_modelo:
            pedacos = re.split(r"\s*/\s*|\s{2,}", marca_modelo, maxsplit=1)
            marca, modelo = pedacos[0], (pedacos[1] if len(pedacos) > 1 else None)
        else:
            marca = valor(linhas, "MARCA")
            modelo = valor(linhas, "MODELO")
        veiculo = {
            "envolv_nr": valor(linhas, "ENVOLVIDO") or numero,
            "placa": placa, "marca": marca, "modelo": modelo,
            "tipo": valor(linhas, "TIPO VEÍCULO", "TIPO DE VEÍCULO", "ESPÉCIE"),
            "cor": valor(linhas, "COR"),
            "ano_fabricacao": valor(linhas, "ANO FABRICAÇÃO", "ANO DE FABRICAÇÃO"),
            "ano_modelo": valor(linhas, "ANO MODELO", "ANO DO MODELO"),
            "municipio_placa": valor(linhas, "MUNICÍPIO EMPLACAMENTO", "MUNICIPIO EMPLACAMENTO", "MUNICÍPIO"),
            "uf_placa": valor(linhas, "UF EMPLACAMENTO", "UF"),
            "situacao": valor(linhas, "SITUAÇÃO", "SITUACAO"),
            "observacoes": valor(linhas, "INFORMAÇÕES COMPLEMENTARES", "INFORMACOES COMPLEMENTARES"),
        }
        if any(veiculo[k] for k in ("placa", "marca", "modelo", "tipo")):
            veiculos.append(veiculo)
    return veiculos


def _bo_envolvido(corpo):
    linhas = corpo.split("\n")
    def cd(r):
        return _bo_valor_depois(linhas, r)
    nome = cd("NOME COMPLETO")
    if not nome:
        return None
    # RG: número que aparece imediatamente antes do rótulo do documento
    rg = None
    for i, l in enumerate(linhas):
        if l.strip().upper().startswith("NÚMERO DOCUMENTO IDENTIDADE"):
            for j in range(i - 1, max(i - 3, -1), -1):
                v = _bo_limpa(linhas[j])
                if v and re.fullmatch(r"\d[\d.\-]*", v):
                    rg = v
                    break
            break
    cpf = cd("CPF / CNPJ")
    if cpf:
        cpf = re.sub(r"\D", "", cpf) or None
    # Tipo de envolvimento: usa a designação exata como está escrita no REDS
    # (campo "TIPO ENVOLVIMENTO", ex.: "VÍTIMA DE AÇÃO CRIMINAL / CÍVEL"),
    # em vez de generalizar tudo que não é Autor/Testemunha como "Envolvido".
    # "Autor" e "Testemunha" são normalizados para esses valores exatos (sem
    # o texto extra que às vezes vem junto, ex. "TESTEMUNHA DA AÇÃO DOS
    # POLICIAIS/BOMBEIROS") porque o resto do sistema já depende desses dois
    # valores para decidir quem é o autor da ocorrência.
    tipo_reds = _bo_valor_coluna(linhas, "TIPO ENVOLVIMENTO")
    if tipo_reds:
        tipo_upper = tipo_reds.upper()
        if "AUTOR" in tipo_upper:
            tipo = "Autor"
        elif "TESTEMUNHA" in tipo_upper:
            tipo = "Testemunha"
        else:
            tipo = tipo_reds  # ex.: "VÍTIMA DE AÇÃO CRIMINAL / CÍVEL", verbatim
    else:
        # Reserva: BOs com layout diferente, onde o campo não foi encontrado.
        tipo = "Autor" if re.search(r"\bAUTOR\b", corpo[:160]) else (
            "Testemunha" if "TESTEMUNHA" in corpo[:160] else "Envolvido")
    return {
        "nome": nome,
        "alcunha": cd("APELIDOS"),
        "data_nascimento": _bo_data_iso(cd("DATA NASCIMENTO")),
        "nome_mae": cd("MÃE"),
        "nome_pai": cd("PAI"),
        "cpf": cpf,
        "rg": rg,
        "endereco": _bo_endereco(corpo),
        "tipo_envolvimento": tipo,
    }


def encontra_pessoa_existente(cpf=None, rg=None, nome=None):
    """Procura um cadastro já existente para o mesmo indivíduo, nesta ordem de
    prioridade: CPF, depois RG, depois nome (exato). Usada na importação de BO
    para evitar duplicar quem já está no sistema."""
    con = conexao()
    pessoa = None
    if cpf:
        cpf_limpo = re.sub(r"\D", "", cpf)
        if cpf_limpo:
            for p in con.execute("SELECT id, nome, cpf FROM pessoas WHERE cpf IS NOT NULL AND cpf != ''"):
                if re.sub(r"\D", "", p["cpf"] or "") == cpf_limpo:
                    pessoa = p
                    break
    if not pessoa and rg:
        rg_limpo = re.sub(r"[^0-9A-Za-z]", "", rg).upper()
        if rg_limpo:
            for p in con.execute("SELECT id, nome, rg FROM pessoas WHERE rg IS NOT NULL AND rg != ''"):
                if re.sub(r"[^0-9A-Za-z]", "", (p["rg"] or "")).upper() == rg_limpo:
                    pessoa = p
                    break
    if not pessoa and nome:
        pessoa = con.execute(
            "SELECT id, nome FROM pessoas WHERE TRIM(UPPER(nome))=?", (nome.strip().upper(),)).fetchone()
    con.close()
    return dict(pessoa) if pessoa else None


def parse_bo_pdf(caminho_pdf):
    """Lê um BO do SISP/PCMG e devolve um dicionário com:
    reds, envolvidos, historico, local_fato (endereço/cidade/bairro/data) e materiais apreendidos."""
    reader = PdfReader(caminho_pdf)
    texto = "\n".join((p.extract_text() or "") for p in reader.pages)
    reds_m = re.search(r"(20\d{2}-\d+-\d+)", texto)
    reds = reds_m.group(1) if reds_m else None
    partes = re.findall(
        r"ENVOLVIDO (\d+)\n(.*?)(?=\nENVOLVIDO \d+\n|MATERIAIS E ARMAS|HISTÓRICO|$)",
        texto, re.S)
    blocos = {}
    for num, corpo in partes:
        blocos.setdefault(num, "")
        blocos[num] += "\n" + corpo
    envolvidos = []
    for num in sorted(blocos, key=int):
        e = _bo_envolvido(blocos[num])
        if e:
            envolvidos.append(e)

    # Fallback: quando a seção de local do fato não traz bairro/cidade com
    # clareza, usamos o endereço já identificado do autor como sugestão inicial.
    autor = next((e for e in envolvidos if e["tipo_envolvimento"] == "Autor"), None)
    fb_bairro = fb_cidade = fb_endereco = None
    if autor and autor.get("endereco"):
        fb_endereco = autor["endereco"]
        pedacos = fb_endereco.split(", ")
        if len(pedacos) >= 2:
            fb_bairro = pedacos[-2] if len(pedacos) >= 3 else None
            fb_cidade = pedacos[-1]

    return {
        "reds": reds,
        "envolvidos": envolvidos,
        "historico": _bo_historico(texto),
        "local_fato": _bo_local_fato(texto, fb_bairro, fb_cidade, fb_endereco),
        "materiais": _bo_materiais(texto),
        "veiculos": _bo_veiculos(texto),
        "diagnostico": _bo_diagnostico(texto),
    }


def _bo_diagnostico(texto):
    """Mapa das linhas em volta de cada rótulo de endereço, com nomes mascarados.

    O PDF do BO não preserva o layout visual: ao extrair o texto, rótulo e valor
    saem em ordem imprevisível, e essa ordem muda de uma seção para outra. Este
    mapa mostra onde cada valor realmente caiu, para ajustar a leitura sem
    depender de suposição."""
    rotulos = ("ENDEREÇO (AV", "LOCAL (AV", "NÚMERO", "BAIRRO", "MUNICÍPIO",
               "COMPLEMENTO", "CEP")
    linhas = texto.split("\n")

    # Nomes de pessoas viram XXXX: o mapa serve para ver estrutura, não conteúdo.
    nomes = set()
    for k, l in enumerate(linhas):
        if l.strip().upper().startswith(("NOME", "PAI", "MÃE", "MAE", "APELIDO")):
            for j in (k - 1, k + 1):
                if 0 <= j < len(linhas):
                    cand = linhas[j].strip()
                    if cand and len(cand) > 5 and not cand.replace("/", "").isdigit():
                        nomes.add(cand)

    def mascara(linha):
        saida = linha
        for nome in nomes:
            for parte in nome.split():
                if len(parte) > 2:
                    saida = re.sub(rf"\b{re.escape(parte)}\b", "X" * len(parte),
                                   saida, flags=re.IGNORECASE)
        return saida

    i = texto.find("DADOS DA OCORRÊNCIA")
    j = texto.find("QUALIFICAÇÃO DOS ENVOLVIDOS")
    linha_i = texto[:i].count("\n") if i >= 0 else -1
    linha_j = texto[:j].count("\n") if j >= 0 else -1

    saida = [f"total de linhas: {len(linhas)} | secao do fato: {linha_i} | envolvidos: {linha_j}"]
    for k, l in enumerate(linhas):
        u = l.strip().upper()
        if not any(u.startswith(r) for r in rotulos):
            continue
        secao = ("FATO" if linha_i >= 0 and linha_i <= k < (linha_j if linha_j > 0 else len(linhas))
                 else "ENVOLVIDO")
        saida.append("")
        saida.append(f"--- {l.strip()!r} na linha {k} [{secao}] ---")
        for j2 in range(max(0, k - 4), min(len(linhas), k + 5)):
            marca = ">>" if j2 == k else "  "
            saida.append(f"{marca} {j2:4}: {mascara(linhas[j2].rstrip())!r}")
    return "\n".join(saida)


def parse_csv_pessoas(conteudo_bytes):
    """Lê um CSV no mesmo formato da exportação do SIRIO (separador ';').
    Devolve (lista_de_registros, lista_de_avisos)."""
    texto = conteudo_bytes.decode("utf-8-sig", errors="replace")
    primeira = texto.splitlines()[0] if texto.strip() else ""
    sep = ";" if primeira.count(";") >= primeira.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=sep)
    campos_validos = {c for c, _ in CAMPOS_PESSOA}
    registros, avisos = [], []
    for n, linha in enumerate(leitor, start=2):
        linha = {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
        nome = linha.get("nome") or ""
        if not nome:
            avisos.append(f"Linha {n} ignorada: sem o campo 'nome'.")
            continue
        reg = {}
        for c in campos_validos:
            val = linha.get(c) or None
            reg[c] = val
        if reg.get("status") not in STATUS_LABEL:
            reg["status"] = "em_verificacao"
        if reg.get("grau_confiabilidade") and reg["grau_confiabilidade"] not in lista_ativa("grau_confiabilidade"):
            reg["grau_confiabilidade"] = None
        if reg.get("fonte_informacao") and reg["fonte_informacao"] not in lista_ativa("fonte_informacao"):
            reg["fonte_informacao"] = None
        registros.append(reg)
    return registros, avisos


def pagina_importar_upload(usuario, csrf, erro=""):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    corpo = f"""
    <div class="cab"><h1>Importar de Boletim de Ocorrência</h1></div>
    <div class="cartao">
      <p class="suave">Envie o PDF de um BO do SISP/PCMG. O sistema lê os envolvidos
      e mostra os dados extraídos para você conferir e escolher quem cadastrar —
      nada é salvo automaticamente.</p>
      <form method="post" action="/importar" enctype="multipart/form-data" class="grade">
        <input type="hidden" name="csrf" value="{e(csrf)}">
        <label class="span2">Arquivo PDF do BO
          <input type="file" name="bo" accept=".pdf,application/pdf" required></label>
        <div class="acoes span2"><button class="botao">Ler boletim</button></div>
      </form>
      <p class="suave">Tem uma exportação em Excel? <a href="/importar-sids">Importar planilha do Armazém SIDS</a>.</p>{msg}
    </div>
    <div class="cartao">
      <p class="aviso">A leitura automática é um apoio: confira sempre os dados na tela
      seguinte antes de salvar. Campos de vínculo (organização, cargo, fonte e
      confiabilidade) não vêm do BO e devem ser preenchidos pela análise.</p>
    </div>"""
    return pagina("Importar BO", corpo, usuario)


def _categoria_sugerida(objeto):
    if not objeto:
        return "Outro"
    o = objeto.upper()
    if "TELEFONE" in o or "CELULAR" in o:
        return "Telefone celular"
    if any(x in o for x in ("REVOLVER", "REVÓLVER", "PISTOLA", "ARMA DE FOGO", "ESPINGARDA")):
        return "Arma de fogo"
    if any(x in o for x in ("FACA", "ARMA BRANCA", "CANIVETE")):
        return "Arma branca"
    if any(x in o for x in ("DROGA", "COCAINA", "COCAÍNA", "MACONHA", "CRACK", "ENTORPECENTE")):
        return "Droga"
    if any(x in o for x in ("VEICULO", "VEÍCULO", "CARRO", "MOTO")):
        return "Veículo"
    if "DINHEIRO" in o or "CÉDULA" in o or "CEDULA" in o:
        return "Dinheiro"
    if "DOCUMENTO" in o:
        return "Documento"
    return "Outro"


def pagina_importar_revisao(usuario, csrf, reds, envolvidos, historico=None, local_fato=None,
                            materiais=None, diagnostico=None, veiculos=None):
    if not envolvidos:
        corpo = ('<div class="cab"><h1>Importar de Boletim de Ocorrência</h1></div>'
                 '<div class="vazio">Não foi possível identificar envolvidos neste PDF. '
                 'Verifique se é um BO do SISP/PCMG.</div>'
                 '<div class="acoes"><a class="botao fantasma" href="/importar">Tentar outro arquivo</a></div>')
        return pagina("Importar BO", corpo, usuario)

    local_fato = local_fato or {}
    materiais = materiais or []
    veiculos = veiculos or []

    # Mapa de como o texto do BO foi lido. Fica recolhido: só interessa quando
    # algum campo vem errado e é preciso ajustar a leitura.
    bloco_diagnostico = ""
    if diagnostico:
        bloco_diagnostico = f"""
    <details style="margin-top:.8rem">
      <summary class="suave" style="cursor:pointer">Algum campo veio errado? Ver como este BO foi lido</summary>
      <p class="suave" style="margin:.5rem 0">Mostra onde cada valor caiu no texto extraído do PDF.
      Nomes de pessoas aparecem mascarados. Selecione tudo e copie para enviar a quem der suporte.</p>
      <textarea readonly rows="18" style="width:100%;font-family:monospace;font-size:.78rem"
        onclick="this.select()">{e(diagnostico)}</textarea>
    </details>"""

    cabecalho = f'<p class="suave">BO/REDS <strong>{e(reds) or "não identificado"}</strong> · '
    cabecalho += f'{len(envolvidos)} envolvido(s) encontrado(s). Marque quem deseja cadastrar e ajuste o necessário.</p>'

    blocos = ""
    for i, p in enumerate(envolvidos):
        marcado = "checked" if p.get("tipo_envolvimento") == "Autor" else ""
        tipo_pill = f'<span class="pill p-em_verificacao">{e(p["tipo_envolvimento"])}</span>'
        def inp(campo, rotulo, classe=""):
            return (f'<label class="{classe}">{rotulo}'
                    f'<input name="{campo}_{i}" value="{e(p.get(campo)) or ""}"></label>')
        match = p.get("match")
        aviso_match = ""
        if match:
            aviso_match = f"""
            <div class="aviso" style="margin:.5rem 0">
              <strong>Possível cadastro já existente:</strong>
              <a href="/pessoas/{match['id']}" target="_blank">{e(match['nome'])} (#{match['id']})</a>.
              Escolha o que fazer:
              <div style="margin-top:.4rem;display:flex;gap:1rem;flex-wrap:wrap">
                <label style="flex-direction:row;gap:.4rem;align-items:center">
                  <input type="radio" name="modo_{i}" value="existente" checked style="width:auto">
                  Incluir estes dados no registro existente (#{match['id']})</label>
                <label style="flex-direction:row;gap:.4rem;align-items:center">
                  <input type="radio" name="modo_{i}" value="novo" style="width:auto">
                  Cadastrar como registro novo mesmo assim</label>
              </div>
              <input type="hidden" name="match_pessoa_id_{i}" value="{match['id']}">
            </div>"""
        sugestao_papel_vd = vd_sugestao_papel(p.get("tipo_envolvimento"))
        campo_papel_vd = f"""
            <div class="grade vd-papel-campo" style="display:none;margin-top:.6rem">
              <label class="span2">Papel desta pessoa no caso de Violência Doméstica
                <select name="papel_vd_{i}"><option value="">Não se aplica / não vincular a este papel</option>
                {opcoes(VD_PAPEIS, sugestao_papel_vd)}</select></label>
            </div>"""
        blocos += f"""
        <fieldset>
          <legend>
            <label style="flex-direction:row;gap:.5rem;align-items:center;text-transform:none;font-size:.9rem">
              <input type="checkbox" name="incluir_{i}" value="1" {marcado} style="width:auto">
              Cadastrar este envolvido</label> {tipo_pill}
          </legend>
          <input type="hidden" name="tipo_envolvimento_{i}" value="{e(p.get('tipo_envolvimento')) or ''}">
          {aviso_match}
          <div class="grade">
            {inp('nome', 'Nome completo', 'span2')}
            {inp('alcunha', 'Alcunha')}
            {inp('cpf', 'CPF')}
            {inp('rg', 'RG')}
            {inp('data_nascimento', 'Data de nascimento (AAAA-MM-DD)')}
            {inp('nome_mae', 'Nome da mãe', 'span2')}
            {inp('nome_pai', 'Nome do pai', 'span2')}
            {inp('endereco', 'Endereço', 'span2')}
          </div>
          {campo_papel_vd}
        </fieldset>"""

    bloco_historico = ""
    if historico:
        bloco_historico = f"""
        <fieldset><legend>Histórico do BO</legend>
          <p class="suave">Este texto ficará disponível na aba "Boletins de Ocorrência" de cada
          envolvido marcado para cadastro (não é mais colado na observação). Pode editar antes de salvar.</p>
          <textarea name="historico" rows="6" style="width:100%">{e(historico)}</textarea>
        </fieldset>"""

    bloco_ocorrencia = f"""
    <fieldset><legend>
      <label style="flex-direction:row;gap:.5rem;align-items:center;text-transform:none;font-size:.9rem">
        <input type="checkbox" name="criar_ocorrencia" value="1" checked style="width:auto">
        Criar ocorrência a partir deste BO (aba Ocorrências / Mapa)</label>
    </legend>
    <div class="grade">
      <label>Tipo de crime<select name="oc_tipo_crime"><option value="">Selecionar…</option>{opcoes(lista_ativa('tipo_crime'), "")}</select></label>
      <label>Data do fato<input type="date" name="oc_data_fato" value="{e(local_fato.get('data_fato'))}"></label>
      <label class="span2">Endereço do fato<input name="oc_endereco_fato" id="oc_end_fato"
        value="{e(local_fato.get('endereco'))}"></label>
      <label>Bairro<input name="oc_bairro_fato" id="oc_bairro_fato" value="{e(local_fato.get('bairro'))}"></label>
      <label>Cidade<input name="oc_cidade_fato" id="oc_cidade_fato" value="{e(local_fato.get('cidade'))}"></label>
      <label>Latitude<input name="oc_lat_fato" id="oc_lat_fato"></label>
      <label>Longitude<input name="oc_lon_fato" id="oc_lon_fato"></label>
      <div class="acoes span2" style="justify-content:flex-start">
        <button type="button" class="botao fantasma mini"
          onclick="geocodificar('oc_end_fato','oc_lat_fato','oc_lon_fato','oc_bairro_fato','oc_cidade_fato')">Localizar coordenadas pelo endereço</button>
      </div>
    </div>
    <p class="suave">O autor marcado acima (se houver) é vinculado automaticamente como autor da ocorrência.
    Endereço/bairro/cidade foram sugeridos a partir do BO — confira antes de salvar.
    Ao localizar coordenadas, confira se o ponto encontrado fica mesmo na cidade informada.</p>
    {bloco_diagnostico}
    </fieldset>

    <fieldset>
      <legend>
        <label style="flex-direction:row;gap:.5rem;align-items:center;text-transform:none;font-size:.9rem">
          <input type="checkbox" name="criar_caso_vd" id="chk_caso_vd" value="1" style="width:auto"
            onchange="alternarCamposVD(this.checked)">
          Este boletim é um caso de Violência Doméstica e Familiar contra a Mulher</label>
      </legend>
      <p class="suave">Ao marcar esta opção, o sistema cria automaticamente um caso no módulo
      "Violência Doméstica" (aba própria), já vinculado à ocorrência criada acima e usando o
      mesmo tipo de crime/artigo informado ali. Para cada envolvido marcado para cadastro abaixo,
      escolha também o papel dele nesse caso — o campo aparece dentro de cada envolvido assim que
      esta caixa é marcada.</p>
    </fieldset>"""

    bloco_materiais = ""
    if materiais:
        itens_mat = ""
        for j, m in enumerate(materiais):
            envolv_nr = m.get("envolv_nr")
            idx_pessoa = int(envolv_nr) - 1 if envolv_nr and envolv_nr.isdigit() else None
            nome_pessoa = (envolvidos[idx_pessoa]["nome"] if idx_pessoa is not None
                           and 0 <= idx_pessoa < len(envolvidos) else None)
            categoria_sug = _categoria_sugerida(m.get("objeto"))
            itens_mat += f"""
            <fieldset>
              <legend>
                <label style="flex-direction:row;gap:.5rem;align-items:center;text-transform:none;font-size:.9rem">
                  <input type="checkbox" name="mat_incluir_{j}" value="1" checked style="width:auto">
                  Cadastrar este material</label>
                {f'<span class="pill p-em_verificacao">Apreendido com {e(nome_pessoa)}</span>' if nome_pessoa else ''}
              </legend>
              <input type="hidden" name="mat_envolv_{j}" value="{e(envolv_nr) or ''}">
              <div class="grade">
                <label>Categoria<select name="mat_categoria_{j}">{opcoes(lista_ativa('categoria_material'), categoria_sug)}</select></label>
                <label class="span2">Objeto<input name="mat_objeto_{j}" value="{e(m.get('objeto'))}"></label>
                <label>Quantidade<input name="mat_quantidade_{j}" value="{e(m.get('quantidade')) or '1'}"></label>
                <label>Situação<select name="mat_situacao_{j}">{opcoes(lista_ativa('situacao_material'), m.get('situacao') or 'Apreendido')}</select></label>
                <label>Marca<input name="mat_marca_{j}" value="{e(m.get('marca'))}"></label>
                <label>Modelo<input name="mat_modelo_{j}" value="{e(m.get('modelo'))}"></label>
                <label>Cor<input name="mat_cor_{j}" value="{e(m.get('cor'))}"></label>
                <label class="span2">Observações (nº de lacre/invólucro, se houver)
                  <input name="mat_observacoes_{j}" value="{e(m.get('observacoes'))}"></label>
              </div>
            </fieldset>"""
        bloco_materiais = f"""
        <fieldset><legend>Materiais apreendidos encontrados no BO</legend>
          <p class="suave">{len(materiais)} item(ns) encontrado(s). Desmarque o que não deve ser cadastrado.</p>
          {itens_mat}
        </fieldset>"""

    bloco_veiculos = ""
    if veiculos:
        itens_veic = ""
        for j, v in enumerate(veiculos):
            itens_veic += f"""
            <fieldset><legend><label style="flex-direction:row;gap:.5rem;align-items:center;text-transform:none;font-size:.9rem">
              <input type="checkbox" name="vei_incluir_{j}" value="1" checked style="width:auto">Cadastrar este veículo</label></legend>
              <input type="hidden" name="vei_envolv_{j}" value="{e(v.get('envolv_nr')) or ''}">
              <div class="grade">
                <label>Placa<input name="vei_placa_{j}" value="{e(v.get('placa'))}"></label><label>Tipo<input name="vei_tipo_{j}" value="{e(v.get('tipo'))}"></label>
                <label>Marca<input name="vei_marca_{j}" value="{e(v.get('marca'))}"></label><label>Modelo<input name="vei_modelo_{j}" value="{e(v.get('modelo'))}"></label>
                <label>Cor<input name="vei_cor_{j}" value="{e(v.get('cor'))}"></label><label>Ano fabricação<input name="vei_ano_fabricacao_{j}" value="{e(v.get('ano_fabricacao'))}"></label>
                <label>Ano modelo<input name="vei_ano_modelo_{j}" value="{e(v.get('ano_modelo'))}"></label><label>Município de emplacamento<input name="vei_municipio_placa_{j}" value="{e(v.get('municipio_placa'))}"></label>
                <label>UF<input name="vei_uf_placa_{j}" value="{e(v.get('uf_placa'))}"></label><label>Situação<input name="vei_situacao_{j}" value="{e(v.get('situacao'))}"></label>
                <label class="span2">Observações<input name="vei_observacoes_{j}" value="{e(v.get('observacoes'))}"></label>
              </div></fieldset>"""
        bloco_veiculos = f"""<fieldset><legend>Veículos encontrados no BO</legend>
          <p class="suave">{len(veiculos)} veículo(s) encontrado(s). Eles ficarão disponíveis na aba Veículos.</p>{itens_veic}</fieldset>"""

    corpo = f"""
    <div class="cab"><h1>Conferir e cadastrar</h1></div>
    {cabecalho}
    <form method="post" action="/importar/salvar">
      <input type="hidden" name="csrf" value="{e(csrf)}">
      <input type="hidden" name="total" value="{len(envolvidos)}">
      <input type="hidden" name="total_materiais" value="{len(materiais)}">
      <input type="hidden" name="total_veiculos" value="{len(veiculos)}">
      <input type="hidden" name="reds" value="{e(reds) or ''}">
      <fieldset><legend>Vínculo investigativo (aplicado a todos os marcados)</legend>
        <div class="grade">
          <label>Organização criminosa<input name="org_comum" placeholder="Preencher pela análise"></label>
          <label>Cargo / função na organização<input name="cargo_comum" placeholder="Preencher pela análise"></label>
          <label>Fonte da informação
            <select name="fonte_comum"><option value="">Selecionar…</option>{opcoes(lista_ativa('fonte_informacao'), 'Boletim de ocorrência')}</select></label>
          <label>Grau de confiabilidade
            <select name="grau_comum"><option value="">Selecionar…</option>{opcoes(lista_ativa('grau_confiabilidade'), '')}</select></label>
          <label>Status inicial
            <select name="status_comum">{opcoes(STATUS, 'em_verificacao')}</select></label>
        </div>
        <p class="suave">A observação de cada registro receberá a referência ao BO/REDS
        {'; o histórico completo fica na aba "Boletins de Ocorrência" dentro do registro de cada envolvido' if historico else ''}.</p>
      </fieldset>
      {bloco_historico}
      {bloco_ocorrencia}
      {blocos}
      {bloco_materiais}
      {bloco_veiculos}
      <div class="acoes">
        <a class="botao fantasma" href="/importar">Cancelar</a>
        <button class="botao">Cadastrar os marcados</button>
      </div>
    </form>
    <script>
    function alternarCamposVD(mostrar) {{
      document.querySelectorAll('.vd-papel-campo').forEach(function(el) {{
        el.style.display = mostrar ? 'grid' : 'none';
      }});
    }}
    </script>
    {SCRIPT_GEOCODIFICADOR}"""
    return pagina("Conferir importação", corpo, usuario)


def pagina_importar_csv(usuario, csrf, erro="", resumo=None):
    msg = f'<p class="erro">{e(erro)}</p>' if erro else ""
    if resumo:
        msg += f'<p class="sucesso">{e(resumo)}</p>'
    colunas = ", ".join(c for c, _ in CAMPOS_PESSOA)
    corpo = f"""
    <div class="cab"><h1>Importar registros de CSV</h1></div>
    <div class="cartao">
      <p class="suave">Envie um arquivo CSV no mesmo formato gerado por "Exportar CSV"
      (separador ponto-e-vírgula). Cada linha vira um registro. As colunas de
      controle (id, datas) são ignoradas — o sistema gera essas informações.</p>
      <form method="post" action="/importar-csv" enctype="multipart/form-data" class="grade">
        <input type="hidden" name="csrf" value="{e(csrf)}">
        <label class="span2">Arquivo CSV
          <input type="file" name="csv" accept=".csv,text/csv" required></label>
        <div class="acoes span2"><button class="botao">Importar registros</button></div>
      </form>{msg}
    </div>
    <div class="cartao">
      <h2>Formato esperado</h2>
      <p class="suave">A primeira linha deve conter os nomes das colunas. A coluna
      <strong>nome</strong> é obrigatória; as demais são opcionais. Colunas reconhecidas:</p>
      <p class="mono" style="max-width:none">{e(colunas)}</p>
      <p class="aviso">Dica: para gerar um modelo, use "Exportar CSV", abra no Excel,
      apague as linhas de exemplo e preencha as suas. Confira os dados antes de importar —
      a importação cria novos registros e fica registrada na auditoria.</p>
    </div>"""
    return pagina("Importar CSV", corpo, usuario)
