"""Módulo SIRIO — pesquisa, cadastro e vínculo de veículos."""
from sirio_core import *  # noqa: F401,F403


def normaliza_placa(placa):
    return re.sub(r"[^A-Z0-9]", "", (placa or "").upper())


def _nome_curto(pessoa):
    partes = (pessoa["nome"] or "").strip().split()
    nome = " ".join(partes[:2])
    return nome[:19] + "…" if len(nome) > 20 else nome


def _opcoes(con, campo):
    return [r[0] for r in con.execute(
        f"SELECT DISTINCT {campo} FROM veiculos WHERE {campo} IS NOT NULL AND {campo}!='' ORDER BY {campo}")]


def pagina_veiculos_lista(usuario, csrf, filtros):
    con = conexao()
    sql = ("SELECT v.*, o.tipo_crime ocorrencia_tipo, o.numero_bo, p.nome pessoa_nome, b.reds boletim_reds "
           "FROM veiculos v LEFT JOIN ocorrencias o ON o.id=v.ocorrencia_id "
           "LEFT JOIN pessoas p ON p.id=v.pessoa_id LEFT JOIN boletins b ON b.id=v.boletim_id WHERE 1=1")
    args, busca = [], (filtros.get("q") or "").strip()
    if busca:
        placa = normaliza_placa(busca)
        termo = f"%{busca}%"
        sql += " AND (v.placa_normalizada LIKE ? OR v.renavam LIKE ? OR v.marca LIKE ? OR v.modelo LIKE ? OR v.cor LIKE ? OR p.nome LIKE ?)"
        args.extend([f"%{placa}%", termo, termo, termo, termo, termo])
    for campo in ("tipo", "cor", "municipio_placa"):
        if filtros.get(campo):
            sql += f" AND v.{campo}=?"; args.append(filtros[campo])
    sql += " ORDER BY v.id DESC LIMIT 500"
    registros = con.execute(sql, args).fetchall()
    tipos, cores, municipios = _opcoes(con, "tipo"), _opcoes(con, "cor"), _opcoes(con, "municipio_placa")
    con.close()
    linhas = ""
    for v in registros:
        bo = v["boletim_reds"] or v["numero_bo"] or "—"
        descricao = " / ".join(x for x in (v["marca"], v["modelo"]) if x) or "—"
        pessoa = f'<a class="nomelink" href="/pessoas/{v["pessoa_id"]}">{e(v["pessoa_nome"])}</a>' if v["pessoa_id"] else "—"
        linhas += f'''<tr><td><a class="nomelink" href="/veiculos/{v['id']}"><strong>{e(v['placa']) or 'Sem placa'}</strong></a></td>
        <td>{e(descricao)}</td><td>{e(v['tipo']) or '—'}</td><td>{e(v['cor']) or '—'}</td>
        <td>{e(v['ano_modelo'] or v['ano_fabricacao']) or '—'}</td><td>{e(v['municipio_placa']) or '—'}</td><td>{e(bo)}</td><td>{pessoa}</td></tr>'''
    tabela = f'<table><thead><tr><th>Placa</th><th>Marca / modelo</th><th>Tipo</th><th>Cor</th><th>Ano</th><th>Município</th><th>BO/REDS</th><th>Envolvido</th></tr></thead><tbody>{linhas}</tbody></table>' if linhas else '<div class="vazio">Nenhum veículo encontrado.</div>'
    def opts(valores, nome):
        return "".join(f'<option value="{e(x)}" {"selected" if filtros.get(nome)==x else ""}>{e(x)}</option>' for x in valores)
    corpo = f'''<div class="cab"><h1>Veículos</h1><a class="botao" href="/veiculos/novo">+ Cadastrar veículo</a></div>
    <p class="suave">Pesquise por placa (com ou sem hífen), RENAVAM, marca, modelo, cor ou pessoa vinculada.</p>
    <form method="get" action="/veiculos" class="painel" style="grid-template-columns:2fr 1fr 1fr 1fr auto">
    <input name="q" value="{e(busca)}" placeholder="Placa, RENAVAM, marca, modelo ou envolvido">
    <select name="tipo"><option value="">Tipo: todos</option>{opts(tipos, 'tipo')}</select>
    <select name="cor"><option value="">Cor: todas</option>{opts(cores, 'cor')}</select>
    <select name="municipio_placa"><option value="">Município: todos</option>{opts(municipios, 'municipio_placa')}</select>
    <button class="botao">Pesquisar</button></form>{tabela}'''
    return pagina("Veículos", corpo, usuario)


def _campo(nome, rotulo, dados, tipo="text"):
    return f'<label>{rotulo}<input type="{tipo}" name="{nome}" value="{e(dados.get(nome, "") or "")}"></label>'


def pagina_veiculo_form(usuario, csrf, dados=None, vid=None, erro=None):
    dados = dados or {}
    con = conexao()
    pessoas = con.execute("SELECT id,nome FROM pessoas ORDER BY nome LIMIT 3000").fetchall()
    ocorrencias = con.execute("SELECT id,numero_bo,tipo_crime FROM ocorrencias ORDER BY id DESC LIMIT 1000").fetchall()
    con.close()
    op_pessoas = '<option value="">Não vincular pessoa</option>' + "".join(f'<option value="{p["id"]}" {"selected" if str(dados.get("pessoa_id") or "")==str(p["id"]) else ""}>{e(p["nome"])} (#{p["id"]})</option>' for p in pessoas)
    op_oc = '<option value="">Não vincular ocorrência</option>' + "".join(f'<option value="{o["id"]}" {"selected" if str(dados.get("ocorrencia_id") or "")==str(o["id"]) else ""}>#{o["id"]} — {e(o["numero_bo"] or o["tipo_crime"] or "Ocorrência")}</option>' for o in ocorrencias)
    acao = f'/veiculos/{vid}/editar' if vid else '/veiculos/novo'
    corpo = f'''<div class="cab"><h1>{'Editar veículo' if vid else 'Cadastrar veículo'}</h1><a class="botao secundario" href="{'/veiculos/'+str(vid) if vid else '/veiculos'}">Voltar</a></div>
    {f'<p class="erro">{e(erro)}</p>' if erro else ''}
    <form method="post" action="{acao}" class="formulario"><input type="hidden" name="csrf" value="{csrf}">
    <h2>Identificação</h2><div class="grade">{_campo('placa','Placa',dados)} {_campo('renavam','RENAVAM',dados)} {_campo('tipo','Tipo',dados)} {_campo('marca','Marca',dados)} {_campo('modelo','Modelo',dados)} {_campo('cor','Cor',dados)} {_campo('ano_fabricacao','Ano de fabricação',dados)} {_campo('ano_modelo','Ano/modelo',dados)} {_campo('municipio_placa','Município de emplacamento',dados)} {_campo('uf_placa','UF',dados)}</div>
    <h2>Vínculos no SIRIO</h2><div class="grade"><label>Pessoa cadastrada<select name="pessoa_id">{op_pessoas}</select></label><label>Ocorrência cadastrada<select name="ocorrencia_id">{op_oc}</select></label>{_campo('situacao','Situação',dados)}</div>
    <label>Observações / resumo de localização<textarea name="observacoes" rows="5">{e(dados.get('observacoes') or '')}</textarea></label>
    <div class="acoes"><button class="botao">Salvar veículo</button></div></form>'''
    return pagina("Veículo", corpo, usuario)


def pagina_veiculo_detalhe(usuario, csrf, v):
    titulo = e(v["placa"]) or "Veículo sem placa"
    campos = [("RENAVAM", v["renavam"]), ("Tipo", v["tipo"]), ("Marca", v["marca"]), ("Modelo", v["modelo"]), ("Cor", v["cor"]), ("Ano fabricação", v["ano_fabricacao"]), ("Ano modelo", v["ano_modelo"]), ("Emplacamento", " / ".join(x for x in (v["municipio_placa"], v["uf_placa"]) if x)), ("Situação", v["situacao"]), ("BO/REDS", v["boletim_reds"] or v["numero_bo"])]
    info = "".join(f'<div><strong>{rotulo}:</strong> {e(valor) or "—"}</div>' for rotulo, valor in campos)
    pessoa = f'<a class="nomelink" href="/pessoas/{v["pessoa_id"]}">{e(v["pessoa_nome"])}</a>' if v["pessoa_id"] else "Não vinculada"
    oc = f'<a class="nomelink" href="/ocorrencias/{v["ocorrencia_id"]}">{e(v["numero_bo"] or v["ocorrencia_tipo"] or "Ver ocorrência")}</a>' if v["ocorrencia_id"] else "Não vinculada"
    corpo = f'''<div class="cab"><h1>{titulo}</h1><div class="acoes"><a class="botao" href="/veiculos/{v['id']}/diagrama">Diagrama por placa</a><a class="botao" href="/veiculos/{v['id']}/editar">Editar</a><a class="botao secundario" href="/veiculos">Voltar</a></div></div>
    <div class="painel">{info}</div><h2>Vínculos</h2><div class="painel"><div><strong>Pessoa:</strong> {pessoa}</div><div><strong>Ocorrência:</strong> {oc}</div></div>
    <h2>Observações</h2><div class="painel">{e(v['observacoes']) or 'Sem observações.'}</div>'''
    return pagina("Veículo", corpo, usuario)


def valida_veiculo(dados):
    if not any((dados.get("placa"), dados.get("renavam"), dados.get("marca"), dados.get("modelo"))):
        return "Informe ao menos placa, RENAVAM, marca ou modelo para identificar o veículo."
    if dados.get("uf_placa") and len(dados["uf_placa"].strip()) != 2:
        return "A UF deve ter duas letras."
    return None


def valores_veiculo(dados):
    texto = lambda nome: (dados.get(nome) or "").strip() or None
    inteiro = lambda nome: int(dados[nome]) if (dados.get(nome) or "").isdigit() else None
    placa = texto("placa")
    return {"placa": placa, "placa_normalizada": normaliza_placa(placa) or None, "renavam": texto("renavam"), "marca": texto("marca"), "modelo": texto("modelo"), "tipo": texto("tipo"), "cor": texto("cor"), "ano_fabricacao": texto("ano_fabricacao"), "ano_modelo": texto("ano_modelo"), "municipio_placa": texto("municipio_placa"), "uf_placa": (texto("uf_placa") or "").upper() or None, "situacao": texto("situacao"), "observacoes": texto("observacoes"), "pessoa_id": inteiro("pessoa_id"), "ocorrencia_id": inteiro("ocorrencia_id")}


def pagina_diagrama_placa(usuario, veiculo_id):
    """Mostra os envolvidos alcançados pela placa, por vínculo direto ou BO/ocorrência compartilhados."""
    import math
    con = conexao()
    base = con.execute("SELECT * FROM veiculos WHERE id=?", (veiculo_id,)).fetchone()
    if not base:
        con.close(); return None
    placa = base["placa_normalizada"] or normaliza_placa(base["placa"])
    if not placa:
        con.close()
        return pagina("Diagrama por placa", '<p class="erro">Este veículo não possui placa para gerar o diagrama.</p>', usuario)
    veiculos = con.execute("SELECT * FROM veiculos WHERE placa_normalizada=?", (placa,)).fetchall()
    pessoas, relacoes = {}, {}
    def incluir(pid, motivo):
        if not pid:
            return
        p = con.execute("SELECT id,nome,alcunha,cargo_orcrim,resumo_investigativo FROM pessoas WHERE id=?", (pid,)).fetchone()
        if p:
            pessoas[pid] = p; relacoes.setdefault(pid, set()).add(motivo)
    for v in veiculos:
        incluir(v["pessoa_id"], "vínculo direto com o veículo")
        if v["ocorrencia_id"]:
            oc = con.execute("SELECT pessoa_autor_id,numero_bo FROM ocorrencias WHERE id=?", (v["ocorrencia_id"],)).fetchone()
            if oc:
                incluir(oc["pessoa_autor_id"], f"autor na ocorrência {oc['numero_bo'] or '#'+str(v['ocorrencia_id'])}")
        if v["boletim_id"]:
            boletim = con.execute("SELECT reds FROM boletins WHERE id=?", (v["boletim_id"],)).fetchone()
            rotulo = (boletim["reds"] if boletim else None) or f"BO #{v['boletim_id']}"
            for bp in con.execute("SELECT pessoa_id FROM boletim_pessoa WHERE boletim_id=?", (v["boletim_id"],)).fetchall():
                incluir(bp["pessoa_id"], f"envolvido no BO/REDS {rotulo}")
    con.close()
    titulo = base["placa"] or placa
    if not pessoas:
        return pagina("Diagrama por placa", f'<div class="cab"><h1>Placa {e(titulo)}</h1><a class="botao secundario" href="/veiculos/{veiculo_id}">Voltar</a></div><div class="vazio">Nenhuma pessoa vinculada a esta placa foi localizada ainda.</div>', usuario)
    itens = sorted(pessoas.values(), key=lambda p: (p["nome"] or "").casefold())
    n, raio = len(itens), max(155, 42 * len(itens)); cx, cy = raio + 170, raio + 110
    linhas = nos = resumos = ""
    for i, p in enumerate(itens):
        ang = 2 * math.pi * i / n - math.pi / 2; x, y = cx + raio * math.cos(ang), cy + raio * math.sin(ang)
        motivo = "; ".join(sorted(relacoes[p["id"]])); curto = _nome_curto(p)
        linhas += f'<line class="v-aresta" x1="{cx:.0f}" y1="{cy:.0f}" x2="{x:.0f}" y2="{y:.0f}"/>'
        nos += f'''<a href="/pessoas/{p['id']}" class="v-no" transform="translate({x:.0f},{y:.0f})"><title>{e(p['nome'])} — {e(motivo)}</title><circle cx="0" cy="0" r="10"/><text x="0" y="25" class="v-nome">{e(curto)}</text><text x="0" y="39" class="v-cargo">{e(motivo[:46] + ('…' if len(motivo)>46 else ''))}</text></a>'''
        if p["resumo_investigativo"]:
            resumos += f'<details><summary>{e(p["nome"])} — resumo localizado</summary><div class="aviso" style="white-space:pre-wrap;margin-top:.5rem">{e(p["resumo_investigativo"])}</div></details>'
    svg = f'''<svg viewBox="0 0 {2*cx} {2*cy+45}" class="v-svg" role="img" aria-label="Vínculos da placa {e(titulo)}">{linhas}<g class="v-no" transform="translate({cx:.0f},{cy:.0f})"><rect class="v-org" x="-88" y="-22" rx="8" width="176" height="44"/><text x="0" y="5" class="v-orgnome">PLACA {e(titulo)}</text></g>{nos}</svg>'''
    corpo = f'''<div class="cab"><div><h1>Diagrama por placa: {e(titulo)}</h1><p class="suave">Inclui pessoas ligadas diretamente ao veículo e, indiretamente, os envolvidos nos mesmos BOs/REDS e autores das ocorrências associadas. Uma pessoa aparece uma única vez, mesmo com vários vínculos.</p></div><a class="botao secundario" href="/veiculos/{veiculo_id}">Voltar ao veículo</a></div><div class="cartao"><h2>{len(itens)} pessoa(s) relacionada(s)</h2>{svg}</div>{('<div class="cartao"><h2>Resumos dos vinculados</h2>'+resumos+'</div>') if resumos else ''}'''
    return pagina("Diagrama por placa", corpo, usuario)
