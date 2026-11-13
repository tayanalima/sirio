"""Módulo SIRIO — Diagrama de vínculos.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403
from sirio_veiculos import pagina_diagrama_placa
import zipfile
from xml.sax.saxutils import escape as xml_escape


def nome_curto(p):
    nome = (p["nome"] or "").strip()
    partes = nome.split()
    curto = " ".join(partes[:2]) if partes else nome
    if len(curto) > 20:
        curto = curto[:19] + "…"
    return curto


def biqueiras_curto(lista):
    """Texto compacto com os locais de biqueira de uma pessoa, para caber
    embaixo do nome no diagrama de vínculos."""
    if not lista:
        return ""
    texto = "Biqueiras: " + ", ".join(lista)
    if len(texto) > 30:
        texto = texto[:29] + "…"
    return texto


def _chave_nome(nome):
    return " ".join((nome or "").split()).casefold()


def _celula_xlsx(valor):
    texto = "".join(c for c in str(valor if valor is not None else "") if ord(c) >= 32 or c in "\t\n\r")
    return f'<c t="inlineStr"><is><t xml:space="preserve">{xml_escape(texto)}</t></is></c>'


def gera_xlsx_vinculos(cabecalhos, linhas):
    """Gera uma planilha XLSX simples e portátil para download pelo SIRIO."""
    todas = [cabecalhos] + linhas
    xml_linhas = []
    for i, linha in enumerate(todas, 1):
        celulas = "".join(_celula_xlsx(v) for v in linha)
        estilo = ' s="1"' if i == 1 else ""
        xml_linhas.append(f'<row r="{i}"{estilo}>{celulas}</row>')
    larguras = "".join(f'<col min="{i}" max="{i}" width="{min(55, max(14, len(str(h)) + 4))}" customWidth="1"/>'
                           for i, h in enumerate(cabecalhos, 1))
    planilha = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<cols>{larguras}</cols><sheetData>{"".join(xml_linhas)}</sheetData></worksheet>')
    estilos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2">'
        '<font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font>'
        '</fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Vínculos" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml', estilos); z.writestr('xl/worksheets/sheet1.xml', planilha)
    return saida.getvalue()


def dados_exportacao_vinculos(modo):
    con = conexao()
    if modo == "boletins":
        dados = con.execute("""SELECT bp.boletim_id, b.reds, p.id, p.nome, p.cpf
            FROM boletim_pessoa bp JOIN boletins b ON b.id=bp.boletim_id
            JOIN pessoas p ON p.id=bp.pessoa_id ORDER BY bp.boletim_id, p.nome""").fetchall()
        por_bo, pares = {}, {}
        for d in dados: por_bo.setdefault(d["boletim_id"], []).append(d)
        for membros in por_bo.values():
            for a in membros:
                for b in membros:
                    if a["id"] != b["id"]:
                        chave = (a["id"], b["id"]); pares.setdefault(chave, {"a": a, "b": b, "reds": set()})["reds"].add(a["reds"] or "")
        con.close()
        return (["Pessoa", "CPF", "Relacionado", "CPF relacionado", "Boletins compartilhados", "REDS compartilhados"],
                [[p["a"]["nome"], p["a"]["cpf"], p["b"]["nome"], p["b"]["cpf"], len(p["reds"]), ", ".join(sorted(x for x in p["reds"] if x))] for p in pares.values()])
    if modo == "cpf":
        dados = con.execute("SELECT cpf, nome, rg, cargo_orcrim FROM pessoas WHERE cpf IS NOT NULL AND TRIM(cpf) != '' ORDER BY cpf, nome").fetchall(); con.close()
        return (["CPF", "Pessoa", "RG", "Cargo/função"], [[d["cpf"], d["nome"], d["rg"], d["cargo_orcrim"]] for d in dados])
    if modo == "vitimas_por_autor":
        dados = con.execute("SELECT COALESCE(NULLIF(TRIM(o.nome_autor),''),p.nome) autor, o.nome_vitima, o.numero_bo, o.tipo_crime FROM ocorrencias o LEFT JOIN pessoas p ON p.id=o.pessoa_autor_id WHERE TRIM(COALESCE(o.nome_vitima,''))!=''").fetchall(); con.close()
        return (["Autor", "Vítima", "REDS", "Natureza"], [[d["autor"], d["nome_vitima"], d["numero_bo"], d["tipo_crime"]] for d in dados])
    dados = con.execute("SELECT organizacao, nome, cpf, cargo_orcrim, status FROM pessoas WHERE organizacao IS NOT NULL AND TRIM(organizacao) != '' ORDER BY organizacao, nome").fetchall(); con.close()
    return (["Organização criminosa", "Pessoa", "CPF", "Cargo/função", "Status"], [[d["organizacao"], d["nome"], d["cpf"], d["cargo_orcrim"], d["status"]] for d in dados])


def acoes_exportacao_vinculos(modo):
    return (f'<div class="acoes"><a class="botao fantasma" href="/vinculos/exportar.xlsx?modo={e(modo)}">Baixar dados em XLSX</a>'
            '<button type="button" class="botao fantasma" onclick="baixarDiagramaPNG()">Baixar imagem PNG (alta qualidade)</button></div>'
            + SCRIPT_EXPORTAR_IMAGEM_DIAGRAMA)


def pagina_vitimas_por_autor(usuario, filtro_autor=""):
    """Monta um diagrama com vítimas distintas por autor, conforme ocorrências registradas."""
    import math
    con = conexao()
    registros = con.execute("""
        SELECT o.id, o.pessoa_autor_id,
               COALESCE(NULLIF(TRIM(o.nome_autor), ''), p.nome) AS autor,
               TRIM(o.nome_vitima) AS vitima
        FROM ocorrencias o
        LEFT JOIN pessoas p ON p.id = o.pessoa_autor_id
        WHERE TRIM(COALESCE(o.nome_vitima, '')) != ''
          AND (TRIM(COALESCE(o.nome_autor, '')) != '' OR o.pessoa_autor_id IS NOT NULL)
        ORDER BY autor, o.id
    """).fetchall()
    con.close()

    autores = {}
    for registro in registros:
        autor = (registro["autor"] or "").strip()
        if filtro_autor and filtro_autor.casefold() not in autor.casefold():
            continue
        chave_autor = registro["pessoa_autor_id"] or _chave_nome(autor)
        grupo = autores.setdefault(chave_autor, {
            "nome": autor, "pessoa_id": registro["pessoa_autor_id"], "vitimas": {},
        })
        chave_vitima = _chave_nome(registro["vitima"])
        vitima = grupo["vitimas"].setdefault(chave_vitima, {"nome": registro["vitima"], "ocorrencias": 0})
        vitima["ocorrencias"] += 1

    cartoes = ""
    for grupo in sorted(autores.values(), key=lambda item: (-len(item["vitimas"]), item["nome"].casefold())):
        vitimas = sorted(grupo["vitimas"].values(), key=lambda item: item["nome"].casefold())
        n = len(vitimas)
        raio = max(140, 32 * n)
        cx, cy = raio + 150, raio + 90
        largura, altura = 2 * cx, 2 * cy + 30
        linhas, nos = "", ""
        for i, vitima in enumerate(vitimas):
            angulo = 2 * math.pi * i / n - math.pi / 2
            x, y = cx + raio * math.cos(angulo), cy + raio * math.sin(angulo)
            rotulo = nome_curto({"nome": vitima["nome"]})
            repeticao = f' ({vitima["ocorrencias"]} registros)' if vitima["ocorrencias"] > 1 else ""
            linhas += f'<line class="v-aresta" x1="{cx:.0f}" y1="{cy:.0f}" x2="{x:.0f}" y2="{y:.0f}"/>'
            nos += (f'<g class="v-no v-vitima" transform="translate({x:.0f},{y:.0f})">'
                    f'<title>{e(vitima["nome"])}{repeticao}</title><circle cx="0" cy="0" r="9"/>'
                    f'<text x="0" y="24" class="v-nome">{e(rotulo)}</text>'
                    f'<text x="0" y="38" class="v-cargo">Vítima{e(repeticao)}</text></g>')
        autor_nome = e(nome_curto({"nome": grupo["nome"]}))
        autor_no = (f'<a href="/pessoas/{grupo["pessoa_id"]}" class="v-no v-org-grupo" '
                    f'transform="translate({cx:.0f},{cy:.0f})">' if grupo["pessoa_id"] else
                    f'<g class="v-no v-org-grupo" transform="translate({cx:.0f},{cy:.0f})">')
        autor_fim = "</a>" if grupo["pessoa_id"] else "</g>"
        cartoes += (f'<div class="cartao"><h2>{e(grupo["nome"])} — {n} vítima(s) distinta(s)</h2>'
                    f'<p class="suave">Vínculos extraídos das ocorrências registradas no sistema.</p>'
                    f'<svg viewBox="0 0 {largura} {altura}" class="v-svg" role="img" '
                    f'aria-label="Vítimas registradas para {e(grupo["nome"])}">{linhas}{autor_no}'
                    f'<rect class="v-org" x="-72" y="-19" rx="8" width="144" height="38"/>'
                    f'<text x="0" y="5" class="v-orgnome">{autor_nome}</text>{autor_fim}{nos}</svg></div>')

    vazio = ('<div class="vazio">Nenhuma relação entre autor e vítima foi encontrada nas ocorrências '
             'registradas com os filtros informados.</div>')
    return cartoes or vazio


def pagina_vinculos_por_bo(usuario, filtro_pessoa=""):
    """Consolida coenvolvidos de todos os BOs: um nó por pessoa e uma aresta
    por relação distinta, com o total de boletins compartilhados."""
    import math
    con = conexao()
    linhas = con.execute("""
        SELECT bp.boletim_id, bp.tipo_envolvimento, p.id, p.nome, p.alcunha,
               p.cargo_orcrim, p.status, p.resumo_investigativo
        FROM boletim_pessoa bp JOIN pessoas p ON p.id=bp.pessoa_id
        ORDER BY bp.boletim_id, p.nome
    """).fetchall()
    con.close()
    por_bo, pessoas = {}, {}
    for linha in linhas:
        por_bo.setdefault(linha["boletim_id"], []).append(linha)
        pessoas[linha["id"]] = linha
    relacoes = {pid: {} for pid in pessoas}
    for boletim_id, membros in por_bo.items():
        ids = list({m["id"] for m in membros})
        for pid in ids:
            for outro in ids:
                if pid != outro:
                    relacoes[pid].setdefault(outro, set()).add(boletim_id)

    cartoes = ""
    for pessoa_id, relacionados in sorted(relacoes.items(), key=lambda x: (-len(x[1]), pessoas[x[0]]["nome"].casefold())):
        centro = pessoas[pessoa_id]
        if filtro_pessoa and filtro_pessoa.casefold() not in (centro["nome"] or "").casefold():
            continue
        itens = sorted(relacionados.items(), key=lambda x: pessoas[x[0]]["nome"].casefold())
        if not itens:
            continue
        n, raio = len(itens), max(150, 35 * len(itens))
        cx, cy = raio + 150, raio + 95
        largura, altura = 2 * cx, 2 * cy + 40
        arestas = nos = ""
        for i, (outro_id, boletins) in enumerate(itens):
            ang = 2 * math.pi * i / n - math.pi / 2
            x, y = cx + raio * math.cos(ang), cy + raio * math.sin(ang)
            outro = pessoas[outro_id]
            qtd = len(boletins)
            rotulo = f"{qtd} BO{'s' if qtd != 1 else ''} em comum"
            arestas += f'<line class="v-aresta" x1="{cx:.0f}" y1="{cy:.0f}" x2="{x:.0f}" y2="{y:.0f}"/>'
            nos += (f'<a href="/pessoas/{outro_id}" class="v-no" transform="translate({x:.0f},{y:.0f})">'
                    f'<title>{e(outro["nome"])} — {rotulo}</title><circle cx="0" cy="0" r="9"/>'
                    f'<text x="0" y="24" class="v-nome">{e(nome_curto(outro))}</text>'
                    f'<text x="0" y="38" class="v-cargo">{e(rotulo)}</text></a>')
        resumo = (f'<details><summary>Resumo de informações localizadas — {e(centro["nome"])}</summary>'
                  f'<div class="aviso" style="white-space:pre-wrap;margin-top:.5rem">{e(centro["resumo_investigativo"])}</div></details>'
                  if centro["resumo_investigativo"] else "")
        cartoes += (f'<div class="cartao"><h2>{e(centro["nome"])} — {n} relacionado(s) distinto(s)</h2>'
                    f'<p class="suave">Relações consolidadas de todos os Boletins de Ocorrência vinculados a esta pessoa.</p>'
                    f'<svg viewBox="0 0 {largura} {altura}" class="v-svg" role="img" aria-label="Vínculos por BO de {e(centro["nome"])}">{arestas}'
                    f'<a href="/pessoas/{pessoa_id}" class="v-no" transform="translate({cx:.0f},{cy:.0f})"><rect class="v-org" x="-72" y="-19" rx="8" width="144" height="38"/>'
                    f'<text x="0" y="5" class="v-orgnome">{e(nome_curto(centro))}</text></a>{nos}</svg>{resumo}</div>')
    return cartoes or '<div class="vazio">Nenhum vínculo entre pessoas foi encontrado nos boletins importados.</div>'


def pagina_vinculos(usuario, csrf, filtro_org="", modo="organizacoes", filtro_autor="", placa_id=""):
    import math
    pode_editar = usuario["perfil"] in ("admin", "analista")
    modo = modo if modo in ("vitimas_por_autor", "cpf", "boletins", "placas") else "organizacoes"
    if modo == "placas":
        con = conexao()
        placas = con.execute("""SELECT MIN(v.id) id, MIN(v.placa) placa, v.placa_normalizada, COUNT(*) total,
            GROUP_CONCAT(DISTINCT p.nome) envolvidos
            FROM veiculos v LEFT JOIN pessoas p ON p.id=v.pessoa_id
            WHERE v.placa_normalizada IS NOT NULL AND TRIM(v.placa_normalizada)!=''
            GROUP BY v.placa_normalizada ORDER BY total DESC, placa LIMIT 500""").fetchall()
        con.close()
        if placa_id.isdigit():
            return pagina_diagrama_placa(usuario, int(placa_id))
        linhas = "".join(f'''<tr><td><strong>{e(p['placa']) or e(p['placa_normalizada'])}</strong></td>
          <td>{p['total']}</td><td>{e(p['envolvidos']) or '—'}</td>
          <td><a class="botao fantasma" href="/vinculos?modo=placas&placa={p['id']}">Abrir diagrama</a></td></tr>''' for p in placas)
        tabela = (f'<table><thead><tr><th>Placa</th><th>Registros</th><th>Envolvidos diretos</th><th></th></tr></thead><tbody>{linhas}</tbody></table>'
                  if linhas else '<div class="vazio">Nenhuma placa foi cadastrada ou importada ainda.</div>')
        corpo = f'''<div class="cab"><div><h1>Diagrama de vínculos por placa</h1><p class="suave">Escolha uma placa. O diagrama reúne os vínculos diretos e os envolvidos nos BOs/REDS e ocorrências associadas.</p></div></div>
        <p><a class="botao fantasma" href="/vinculos?modo=organizacoes">Por organização</a> <a class="botao fantasma" href="/vinculos?modo=cpf">Por CPF</a> <a class="botao fantasma" href="/vinculos?modo=boletins">Por boletim de ocorrência</a> <a class="botao fantasma" href="/vinculos?modo=vitimas_por_autor">Vítimas por autor</a></p>{tabela}'''
        return pagina("Diagrama por placa", corpo, usuario)
    if modo == "vitimas_por_autor":
        filtro = (
            '<form method="get" action="/vinculos" class="painel" style="grid-template-columns:1fr auto">'
            '<input type="hidden" name="modo" value="vitimas_por_autor">'
            f'<input name="autor" value="{e(filtro_autor)}" placeholder="Filtrar por nome do autor">'
            '<button class="botao">Filtrar</button></form>')
        corpo = (
            '<div class="cab"><div><h1>Diagrama de vítimas por autor</h1>'
            '<p class="suave">Mostra vítimas distintas vinculadas a cada autor nas ocorrências registradas. '
            'O total não representa toda a vida do autor: apenas os registros existentes no SIRIO.</p></div></div>'
            '<p><a class="botao fantasma" href="/vinculos">Ver diagrama por organização</a></p>'
            f'{acoes_exportacao_vinculos("vitimas_por_autor")}{filtro}{pagina_vitimas_por_autor(usuario, filtro_autor)}')
        return pagina("Diagrama de vítimas por autor", corpo, usuario)

    if modo == "boletins":
        filtro = ('<form method="get" action="/vinculos" class="painel" style="grid-template-columns:1fr auto">'
                  '<input type="hidden" name="modo" value="boletins">'
                  f'<input name="autor" value="{e(filtro_autor)}" placeholder="Filtrar pelo nome da pessoa">'
                  '<button class="botao">Filtrar</button></form>')
        corpo = ('<div class="cab"><div><h1>Diagrama de vínculos por Boletim de Ocorrência</h1>'
                 '<p class="suave">Cada pessoa reúne todos os coenvolvidos distintos de todos os BOs importados. '
                 'O rótulo da linha indica quantos boletins foram compartilhados entre o par.</p></div></div>'
                 '<p><a class="botao fantasma" href="/vinculos?modo=organizacoes">Por organização</a> '
                 '<a class="botao fantasma" href="/vinculos?modo=cpf">Por CPF</a> '
                 '<a class="botao fantasma" href="/vinculos?modo=placas">Por placa</a> '
                 '<a class="botao fantasma" href="/vinculos?modo=vitimas_por_autor">Vítimas por autor</a></p>'
                 f'{acoes_exportacao_vinculos("boletins")}{filtro}{pagina_vinculos_por_bo(usuario, filtro_autor)}')
        return pagina("Diagrama por BO", corpo, usuario)

    con = conexao()
    if modo == "cpf":
        pessoas = con.execute(
            "SELECT id, nome, alcunha, cargo_orcrim, cpf AS organizacao, resumo_investigativo, status FROM pessoas"
            " WHERE cpf IS NOT NULL AND TRIM(cpf) != '' ORDER BY nome").fetchall()
        titulo_grupo, descricao_grupo = "CPF", "mesmo CPF cadastrado"
    else:
        pessoas = con.execute(
            "SELECT id, nome, alcunha, cargo_orcrim, organizacao, resumo_investigativo, status FROM pessoas"
            " WHERE organizacao IS NOT NULL AND TRIM(organizacao) != '' ORDER BY nome").fetchall()
        titulo_grupo, descricao_grupo = "Organização criminosa", "mesma organização criminosa"
    posicoes_raw = con.execute("SELECT organizacao_chave, pessoa_id, x, y FROM vinculo_posicoes").fetchall()
    biqueiras_raw = con.execute("SELECT pessoa_id, local, endereco FROM biqueiras ORDER BY id").fetchall()
    con.close()

    biqueiras_por_pessoa = {}
    for b in biqueiras_raw:
        rotulo = (b["local"] or b["endereco"] or "").strip()
        if rotulo:
            biqueiras_por_pessoa.setdefault(b["pessoa_id"], []).append(rotulo)

    posicoes = {}  # chave_org -> {"org": (x,y)} ou {pessoa_id: (x,y)}
    for pr in posicoes_raw:
        posicoes.setdefault(pr["organizacao_chave"], {})[pr["pessoa_id"] or "org"] = (pr["x"], pr["y"])

    # Agrupamento automático: mesma organização (ignora maiúsculas/espaços extras)
    grupos = {}
    for p in pessoas:
        limpo = " ".join(p["organizacao"].split())
        chave = limpo.lower()
        g = grupos.setdefault(chave, {"grafias": {}, "membros": [], "chave": chave})
        g["grafias"][limpo] = g["grafias"].get(limpo, 0) + 1
        g["membros"].append(p)
    for g in grupos.values():
        g["nome"] = max(g["grafias"], key=g["grafias"].get)
    ordenados = sorted(grupos.values(), key=lambda g: -len(g["membros"]))
    com_vinculo = [g for g in ordenados if len(g["membros"]) >= 2]
    isolados = [g for g in ordenados if len(g["membros"]) == 1]

    if filtro_org:
        com_vinculo = [g for g in com_vinculo + isolados
                       if g["nome"].lower() == filtro_org.lower()]
        isolados = []

    svgs = ""
    for gi, g in enumerate(com_vinculo):
        membros = g["membros"]
        n = len(membros)
        raio = max(130, int(19 * n))
        cx = raio + 130
        cy = raio + 70
        largura = 2 * cx
        altura = 2 * cy + 40
        pos_grupo = posicoes.get(g["chave"], {})
        cx_org, cy_org = pos_grupo.get("org", (cx, cy))

        linhas, nos, resumos = "", "", ""
        for i, m in enumerate(membros):
            ang = 2 * math.pi * i / n - math.pi / 2
            x_padrao = cx + raio * math.cos(ang)
            y_padrao = cy + raio * math.sin(ang)
            x, y = pos_grupo.get(m["id"], (x_padrao, y_padrao))
            id_membro = f"membro-{gi}-{m['id']}"
            id_linha = f"linha-{gi}-{m['id']}"
            linhas += (f'<line id="{id_linha}" class="v-aresta" data-org="org-{gi}" '
                      f'data-membro="{id_membro}" x1="{cx_org:.0f}" y1="{cy_org:.0f}" '
                      f'x2="{x:.0f}" y2="{y:.0f}"/>')
            cargo = e(m["cargo_orcrim"]) or ""
            alcunha = f'&#8220;{e(m["alcunha"])}&#8221;' if m["alcunha"] else ""
            sub = cargo or alcunha
            lista_biq = biqueiras_por_pessoa.get(m["id"], [])
            biq_txt = biqueiras_curto(lista_biq)
            linha_biq = f'<text x="0" y="52" class="v-biqueira">{e(biq_txt)}</text>' if biq_txt else ""
            apagado = " v-apagado" if m["status"] in ("inativo", "arquivado") else ""
            dica = (f'{e(m["nome"])} - {cargo or "cargo não informado"} '
                    f'({STATUS_LABEL.get(m["status"], m["status"])})'
                    + (f' - Biqueiras: {", ".join(lista_biq)}' if lista_biq else ''))
            nos += (f'<a href="/pessoas/{m["id"]}" id="{id_membro}" class="v-no{apagado}" '
                    f'data-tipo="membro" data-pessoa="{m["id"]}" data-org-chave="{e(g["chave"])}" '
                    f'data-x="{x:.0f}" data-y="{y:.0f}" transform="translate({x:.0f},{y:.0f})">'
                    f'<title>{dica}</title>'
                    f'<circle cx="0" cy="0" r="9"/>'
                    f'<text x="0" y="24" class="v-nome">{e(nome_curto(m))}</text>'
                    f'<text x="0" y="38" class="v-cargo">{sub}</text>{linha_biq}</a>')
            if m["resumo_investigativo"]:
                resumos += (f'<details><summary>{e(m["nome"])} — informações localizadas</summary>'
                            f'<div class="aviso" style="white-space:pre-wrap;margin-top:.5rem">{e(m["resumo_investigativo"])}</div></details>')
        org_l = max(110, len(g["nome"]) * 9 + 30)
        svgs += (
            f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
            f'<h2 style="margin:0">{e(g["nome"])} — {n} integrante(s)</h2>'
            + (f'<button type="button" class="botao mini fantasma" '
               f'onclick="reorganizarDiagrama(\'{js_attr(g["chave"])}\', this)">Reorganizar automaticamente</button>'
               if pode_editar else '') +
            f'</div>'
            f'<p class="suave" style="margin-top:0">Arraste os nomes ou a referência para reorganizar o diagrama.</p>'
            f'<svg viewBox="0 0 {largura} {altura}" class="v-svg" role="img" '
            f'aria-label="Diagrama de vínculos: {e(g["nome"])}">'
            f'{linhas}'
            f'<g id="org-{gi}" class="v-no v-org-grupo" data-tipo="org" data-org-chave="{e(g["chave"])}" '
            f'data-x="{cx_org:.0f}" data-y="{cy_org:.0f}" transform="translate({cx_org:.0f},{cy_org:.0f})">'
            f'<rect class="v-org" x="{-org_l // 2}" y="-19" rx="8" width="{org_l}" height="38"/>'
            f'<text x="0" y="5" class="v-orgnome">{e(g["nome"])}</text></g>'
            f'{nos}</svg>{("<div style=\"margin-top:.7rem\"><strong>Resumos dos vinculados</strong>" + resumos + "</div>") if resumos else ""}</div>')

    if not com_vinculo:
        svgs = ('<div class="vazio">Nenhum vínculo identificado ainda. O diagrama é gerado '
                f'automaticamente quando dois ou mais registros possuem a {descricao_grupo}.</div>')

    lista_isolados = ""
    if isolados and not filtro_org:
        itens = ""
        for g in isolados:
            m = g["membros"][0]
            itens += (f'<tr><td>{e(g["nome"])}</td>'
                      f'<td><a class="nomelink" href="/pessoas/{m["id"]}">{e(m["nome"])}</a></td>'
                      f'<td>{e(m["cargo_orcrim"]) or "—"}</td></tr>')
        lista_isolados = (
            '<div class="cartao"><h2>Organizações com apenas um registro (sem vínculo formado)</h2>'
            '<table><thead><tr><th>Organização</th><th>Registro</th><th>Cargo</th></tr></thead>'
            f'<tbody>{itens}</tbody></table></div>')

    todas = sorted({g["nome"] for g in ordenados}, key=str.lower)
    filtro = (
        '<form method="get" action="/vinculos" class="painel" '
        'style="grid-template-columns:1fr auto">'
        f'<input type="hidden" name="modo" value="{e(modo)}">'
        f'<select name="org"><option value="">Todos os {titulo_grupo}s</option>{opcoes(todas, filtro_org)}</select>'
        '<button class="botao">Filtrar</button></form>')

    corpo = (
        f'<div class="cab"><div><h1>Diagrama de vínculos por {e(titulo_grupo)}</h1>'
        f'<p class="suave">Gerado automaticamente: registros com a {descricao_grupo} '
        'são conectados entre si. Clique em um integrante para abrir o registro; arraste para '
        'reorganizar (a posição fica salva).</p></div></div>'
        + ('<p class="aviso">A coincidência de CPF normalmente indica registros duplicados da mesma pessoa; '
           'ela não prova vínculo entre pessoas diferentes. Use a opção Mesclar registros após conferência.</p>'
           if modo == "cpf" else '')
        + '<p><a class="botao fantasma" href="/vinculos?modo=organizacoes">Por organização</a> '
        '<a class="botao fantasma" href="/vinculos?modo=cpf">Por CPF</a> '
        '<a class="botao fantasma" href="/vinculos?modo=boletins">Por boletim de ocorrência</a> '
        '<a class="botao fantasma" href="/vinculos?modo=placas">Por placa</a> '
        '<a class="botao fantasma" href="/vinculos?modo=vitimas_por_autor">Vítimas por autor</a></p>'
        + f'{acoes_exportacao_vinculos(modo)}{filtro}{svgs}{lista_isolados}'
        + (f'<script>var CSRF_VINCULOS = "{e(csrf)}";</script>' + SCRIPT_ARRASTAR_VINCULOS
           if com_vinculo and pode_editar else ""))
    return pagina("Diagrama de vínculos", corpo, usuario)


SCRIPT_ARRASTAR_VINCULOS = """
<script>
function pontoSVG(svg, evento) {
  var pt = svg.createSVGPoint();
  pt.x = evento.clientX; pt.y = evento.clientY;
  var ctm = svg.getScreenCTM().inverse();
  return pt.matrixTransform(ctm);
}
function atualizarLinha(svg, idElemento) {
  Array.from(svg.querySelectorAll('line[data-org="' + idElemento + '"], line[data-membro="' + idElemento + '"]'))
    .forEach(function(linha) {
      var org = document.getElementById(linha.dataset.org);
      var membro = document.getElementById(linha.dataset.membro);
      if (org) { linha.setAttribute('x1', org.dataset.x); linha.setAttribute('y1', org.dataset.y); }
      if (membro) { linha.setAttribute('x2', membro.dataset.x); linha.setAttribute('y2', membro.dataset.y); }
    });
}
async function salvarPosicao(grupo) {
  var corpo = {
    csrf: CSRF_VINCULOS,
    organizacao_chave: grupo.dataset.orgChave,
    tipo: grupo.dataset.tipo,
    pessoa_id: grupo.dataset.pessoa || null,
    x: grupo.dataset.x, y: grupo.dataset.y,
  };
  try {
    await fetch('/vinculos/posicao', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(corpo)
    });
  } catch (err) { /* sem internet ou erro de rede: a posição fica só nesta visualização */ }
}
async function reorganizarDiagrama(chave, botao) {
  if (!confirm('Voltar este diagrama para o arranjo automático?')) return;
  try {
    await fetch('/vinculos/reorganizar', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({csrf: CSRF_VINCULOS, organizacao_chave: chave})
    });
    location.reload();
  } catch (err) { alert('Não foi possível reorganizar agora.'); }
}
document.querySelectorAll('.v-svg').forEach(function(svg) {
  var arrastando = null;
  svg.querySelectorAll('.v-no').forEach(function(grupo) {
    grupo.style.cursor = 'grab';
    grupo.addEventListener('mousedown', function(ev) {
      ev.preventDefault();
      var p0 = pontoSVG(svg, ev);
      arrastando = {
        grupo: grupo, startX: p0.x, startY: p0.y,
        origX: parseFloat(grupo.dataset.x), origY: parseFloat(grupo.dataset.y), moveu: false,
      };
    });
  });
  svg.addEventListener('mousemove', function(ev) {
    if (!arrastando) return;
    var p = pontoSVG(svg, ev);
    var dx = p.x - arrastando.startX, dy = p.y - arrastando.startY;
    if (Math.abs(dx) + Math.abs(dy) > 3) arrastando.moveu = true;
    var nx = arrastando.origX + dx, ny = arrastando.origY + dy;
    arrastando.grupo.setAttribute('transform', 'translate(' + nx + ',' + ny + ')');
    arrastando.grupo.dataset.x = nx; arrastando.grupo.dataset.y = ny;
    atualizarLinha(svg, arrastando.grupo.id);
  });
  function soltar() {
    if (!arrastando) return;
    if (arrastando.moveu) {
      salvarPosicao(arrastando.grupo);
      var g = arrastando.grupo;
      g.dataset.suprimirClique = '1';
      setTimeout(function() { delete g.dataset.suprimirClique; }, 50);
    }
    arrastando = null;
  }
  svg.addEventListener('mouseup', soltar);
  svg.addEventListener('mouseleave', soltar);
  svg.querySelectorAll('.v-no').forEach(function(grupo) {
    grupo.addEventListener('click', function(ev) {
      if (grupo.dataset.suprimirClique) ev.preventDefault();
    });
  });
});
</script>"""


SCRIPT_EXPORTAR_IMAGEM_DIAGRAMA = """
<script>
async function baixarDiagramaPNG() {
  var diagramas = Array.from(document.querySelectorAll('.v-svg'));
  if (!diagramas.length) { alert('Não há diagrama para exportar.'); return; }
  for (var i = 0; i < diagramas.length; i++) {
    var svg = diagramas[i].cloneNode(true), caixa = diagramas[i].viewBox.baseVal;
    svg.setAttribute('width', caixa.width); svg.setAttribute('height', caixa.height);
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    var fonte = '<style>text{font-family:Arial,sans-serif}.v-aresta{stroke:#cfc8ba;stroke-width:1.5}.v-org{fill:#22303a;stroke:#c9a85c;stroke-width:2}.v-orgnome{fill:#c9a85c;font-weight:700;font-size:14px;text-anchor:middle}.v-no circle{fill:#fff;stroke:#c9a85c;stroke-width:2.5}.v-nome{fill:#22303a;font-size:12.5px;font-weight:600;text-anchor:middle}.v-cargo{fill:#59636b;font-size:11px;text-anchor:middle}</style>';
    var blob = new Blob([fonte + new XMLSerializer().serializeToString(svg)], {type:'image/svg+xml;charset=utf-8'});
    var url = URL.createObjectURL(blob), img = new Image();
    await new Promise(function(resolve) { img.onload = resolve; img.src = url; });
    var escala = 4, canvas = document.createElement('canvas'); canvas.width = caixa.width * escala; canvas.height = caixa.height * escala;
    var ctx = canvas.getContext('2d'); ctx.fillStyle = '#ffffff'; ctx.fillRect(0,0,canvas.width,canvas.height); ctx.drawImage(img,0,0,canvas.width,canvas.height); URL.revokeObjectURL(url);
    var a = document.createElement('a'); a.download = 'diagrama-vinculos-' + (i + 1) + '-alta-qualidade.png'; a.href = canvas.toDataURL('image/png'); a.click();
  }
}
</script>"""
