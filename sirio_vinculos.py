"""Módulo SIRIO — Diagrama de vínculos.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403


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


def pagina_vinculos(usuario, csrf, filtro_org="", modo="organizacoes", filtro_autor=""):
    import math
    pode_editar = usuario["perfil"] in ("admin", "analista")
    modo = "vitimas_por_autor" if modo == "vitimas_por_autor" else "organizacoes"
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
            f'{filtro}{pagina_vitimas_por_autor(usuario, filtro_autor)}')
        return pagina("Diagrama de vítimas por autor", corpo, usuario)

    con = conexao()
    pessoas = con.execute(
        "SELECT id, nome, alcunha, cargo_orcrim, organizacao, status FROM pessoas"
        " WHERE organizacao IS NOT NULL AND TRIM(organizacao) != '' ORDER BY nome").fetchall()
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

        linhas, nos = "", ""
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
        org_l = max(110, len(g["nome"]) * 9 + 30)
        svgs += (
            f'<div class="cartao"><div class="cab" style="margin-bottom:.5rem">'
            f'<h2 style="margin:0">{e(g["nome"])} — {n} integrante(s)</h2>'
            + (f'<button type="button" class="botao mini fantasma" '
               f'onclick="reorganizarDiagrama(\'{js_attr(g["chave"])}\', this)">Reorganizar automaticamente</button>'
               if pode_editar else '') +
            f'</div>'
            f'<p class="suave" style="margin-top:0">Arraste os nomes ou a organização para reorganizar o diagrama.</p>'
            f'<svg viewBox="0 0 {largura} {altura}" class="v-svg" role="img" '
            f'aria-label="Diagrama de vínculos: {e(g["nome"])}">'
            f'{linhas}'
            f'<g id="org-{gi}" class="v-no v-org-grupo" data-tipo="org" data-org-chave="{e(g["chave"])}" '
            f'data-x="{cx_org:.0f}" data-y="{cy_org:.0f}" transform="translate({cx_org:.0f},{cy_org:.0f})">'
            f'<rect class="v-org" x="{-org_l // 2}" y="-19" rx="8" width="{org_l}" height="38"/>'
            f'<text x="0" y="5" class="v-orgnome">{e(g["nome"])}</text></g>'
            f'{nos}</svg></div>')

    if not com_vinculo:
        svgs = ('<div class="vazio">Nenhum vínculo identificado ainda. O diagrama é gerado '
                'automaticamente quando dois ou mais registros possuem a mesma organização '
                'criminosa cadastrada.</div>')

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
        '<input type="hidden" name="modo" value="organizacoes">'
        f'<select name="org"><option value="">Todas as organizações</option>{opcoes(todas, filtro_org)}</select>'
        '<button class="botao">Filtrar</button></form>')

    corpo = (
        '<div class="cab"><div><h1>Diagrama de vínculos</h1>'
        '<p class="suave">Gerado automaticamente: registros com a mesma organização criminosa '
        'são conectados entre si. Clique em um integrante para abrir o registro; arraste para '
        'reorganizar (a posição fica salva).</p></div></div>'
        '<p><a class="botao fantasma" href="/vinculos?modo=vitimas_por_autor">Ver vítimas por autor</a></p>'
        f'{filtro}{svgs}{lista_isolados}'
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
