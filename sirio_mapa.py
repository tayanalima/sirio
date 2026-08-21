"""Módulo SIRIO — Mapa geográfico das ocorrências.
Importa a infraestrutura compartilhada de sirio_core.py.
"""
from sirio_core import *  # noqa: F401,F403


def calcula_pontos_mapa():
    """Monta a lista de pontos geográficos (fato/autor/vítima/testemunha) a partir
    das ocorrências cadastradas. Usada tanto pelo endpoint JSON do mapa quanto
    pela lista de dados renderizada pelo servidor (que não depende de JavaScript)."""
    con = conexao()
    ocorrencias = con.execute("SELECT * FROM ocorrencias").fetchall()
    testemunhas_todas = con.execute("SELECT * FROM ocorrencia_testemunhas").fetchall()
    materiais_todos = con.execute(
        "SELECT ocorrencia_id, categoria, objeto FROM materiais_apreendidos "
        "WHERE ocorrencia_id IS NOT NULL").fetchall()
    con.close()
    testemunhas_por_ocorrencia = {}
    for t in testemunhas_todas:
        testemunhas_por_ocorrencia.setdefault(t["ocorrencia_id"], []).append(t)
    materiais_por_ocorrencia = {}
    for m in materiais_todos:
        materiais_por_ocorrencia.setdefault(m["ocorrencia_id"], []).append(
            m["objeto"] or m["categoria"] or "item")
    pontos = []
    for o in ocorrencias:
        materiais_desc = materiais_por_ocorrencia.get(o["id"], [])
        # "origem", "link" e "grupo" existem para que o mapa possa exibir, lado
        # a lado, ocorrências registradas e denúncias ainda em verificação.
        comum = {"origem": "ocorrencia", "verificacao_id": None,
                 "grupo": f"oc-{o['id']}", "link": f"/ocorrencias/{o['id']}"}
        if o["lat_fato"] and o["lon_fato"]:
            pontos.append({**comum, "tipo_ponto": "fato", "ocorrencia_id": o["id"],
                "tipo_crime": o["tipo_crime"], "nome": None, "nome_autor": o["nome_autor"],
                "endereco": o["endereco_fato"], "data_fato": o["data_fato"],
                "cidade": o["cidade_fato"], "bairro": o["bairro_fato"],
                "materiais": materiais_desc,
                "lat": o["lat_fato"], "lon": o["lon_fato"]})
        if o["lat_autor"] and o["lon_autor"]:
            pontos.append({**comum, "tipo_ponto": "autor", "ocorrencia_id": o["id"],
                "tipo_crime": o["tipo_crime"], "nome": o["nome_autor"], "nome_autor": o["nome_autor"],
                "endereco": o["endereco_autor"], "data_fato": o["data_fato"],
                "cidade": None, "bairro": None, "materiais": [],
                "lat": o["lat_autor"], "lon": o["lon_autor"]})
        if o["lat_vitima"] and o["lon_vitima"]:
            pontos.append({**comum, "tipo_ponto": "vitima", "ocorrencia_id": o["id"],
                "tipo_crime": o["tipo_crime"], "nome": o["nome_vitima"], "nome_autor": o["nome_autor"],
                "endereco": o["endereco_vitima"], "data_fato": o["data_fato"],
                "cidade": None, "bairro": None, "materiais": [],
                "lat": o["lat_vitima"], "lon": o["lon_vitima"]})
        for t in testemunhas_por_ocorrencia.get(o["id"], []):
            if t["lat"] and t["lon"]:
                pontos.append({**comum, "tipo_ponto": "testemunha", "ocorrencia_id": o["id"],
                    "tipo_crime": o["tipo_crime"], "nome": t["nome"], "nome_autor": o["nome_autor"],
                    "endereco": t["endereco"], "data_fato": o["data_fato"],
                    "cidade": None, "bairro": None, "materiais": [],
                    "lat": t["lat"], "lon": t["lon"]})
    # As verificações de denúncia entram aqui. O import fica dentro da função
    # para não criar dependência entre os módulos no momento da importação.
    try:
        from sirio_verificacoes import pontos_mapa_verificacoes
        pontos.extend(pontos_mapa_verificacoes())
    except (ImportError, sqlite3.OperationalError):
        pass  # banco antigo, sem a tabela: o mapa segue só com as ocorrências

    return pontos, len(ocorrencias)


def pagina_mapa(usuario):
    pontos, total_ocorrencias = calcula_pontos_mapa()

    aviso_dados = ""
    if total_ocorrencias == 0:
        aviso_dados = ('<div class="vazio">Nenhuma ocorrência cadastrada ainda. '
                       'Cadastre em <a href="/ocorrencias/nova">Ocorrências</a> ou registre uma '
                       '<a href="/verificacoes/nova">verificação de denúncia</a> com coordenadas '
                       'para ver pontos aqui.</div>')
    elif not pontos:
        aviso_dados = (f'<div class="vazio">Você tem {total_ocorrencias} ocorrência(s) cadastrada(s), mas '
                       'nenhuma tem coordenadas (latitude/longitude) ainda. Abra uma ocorrência, clique em '
                       '"Editar" e use o botão "Localizar coordenadas pelo endereço" — ou preencha a '
                       'latitude/longitude manualmente, se souber.</div>')

    linhas_tabela = ""
    rotulo_ponto = dict((t, r) for t, r, _ in TIPOS_PONTO_MAPA)
    for p in pontos:
        materiais_txt = ", ".join(p["materiais"]) if p.get("materiais") else "—"
        linhas_tabela += f"""<tr>
          <td>{e(rotulo_ponto.get(p['tipo_ponto'], p['tipo_ponto']))}</td>
          <td>{e(p.get('tipo_crime')) or '—'}</td>
          <td>{e(p.get('nome')) or e(p.get('nome_autor')) or '—'}</td>
          <td>{e(p.get('endereco')) or '—'}</td>
          <td>{e(p.get('bairro')) or '—'}</td>
          <td>{e(p.get('cidade')) or '—'}</td>
          <td class="mono">{p['lat']:.5f}, {p['lon']:.5f}</td>
          <td>{materiais_txt}</td>
          <td>{'Verificação' if p.get('origem') == 'verificacao' else 'Ocorrência'}</td>
          <td><a class="nomelink" href="{e(p.get('link') or '#')}">Abrir</a></td></tr>"""
    tabela_dados = ""
    if pontos:
        tabela_dados = f"""
        <div class="cartao"><h2>Lista de pontos ({len(pontos)})</h2>
        <p class="suave">Esta lista é gerada diretamente pelo sistema e sempre aparece,
        mesmo que o mapa visual abaixo não carregue por bloqueio de rede.</p>
        <table><thead><tr><th>Tipo</th><th>Crime</th><th>Nome</th><th>Endereço</th>
        <th>Bairro</th><th>Cidade</th><th>Coordenadas</th><th>Materiais</th><th>Origem</th><th></th></tr></thead>
        <tbody>{linhas_tabela}</tbody></table></div>"""

    cores_js = ", ".join(f'"{t}": "{c}"' for t, _, c in TIPOS_PONTO_MAPA)
    rotulos_js = ", ".join(f'"{t}": "{r}"' for t, r, _ in TIPOS_PONTO_MAPA)
    checkboxes = "".join(
        f'<label style="flex-direction:row;gap:.4rem;align-items:center">'
        f'<input type="checkbox" class="chk-tipo" value="{t}" checked style="width:auto">{r}</label>'
        for t, r, _ in TIPOS_PONTO_MAPA)
    corpo = f"""
    <div class="cab"><h1>Mapa</h1></div>
    <p class="suave">Exibe local do fato, residência da vítima, do autor e de testemunhas, a partir das
    ocorrências cadastradas e das verificações de denúncia com coordenadas preenchidas. Use os filtros
    para focar num tipo de crime ou isolar um autor e visualizar a correlação entre a residência dele e
    os locais dos fatos. Os pontos vindos de uma denúncia ainda em verificação aparecem com o miolo
    claro e a borda tracejada.</p>
    {aviso_dados}
    <div class="painel" style="grid-template-columns:1fr 1fr 1fr 1fr auto">
      <select id="filtro_tipo_crime"><option value="">Tipo de crime: todos</option>{opcoes(lista_ativa('tipo_crime'), "")}</select>
      <input id="filtro_autor" placeholder="Filtrar/correlacionar por autor (nome)">
      <select id="filtro_origem">
        <option value="">Origem: ocorrências e verificações</option>
        <option value="ocorrencia">Somente ocorrências registradas</option>
        <option value="verificacao">Somente verificações de denúncia</option>
      </select>
      <label style="flex-direction:row;gap:.4rem;align-items:center">
        <input type="checkbox" id="chk_calor" style="width:auto">Mostrar mancha de calor (estatística)</label>
      <button class="botao" onclick="aplicarFiltros()">Aplicar</button>
      <div class="larga" style="display:flex;gap:1rem;flex-wrap:wrap">{checkboxes}
        <label style="flex-direction:row;gap:.4rem;align-items:center">
          <input type="checkbox" id="chk_so_material" style="width:auto">Somente ocorrências com material apreendido</label>
      </div>
    </div>
    <div id="mapa" style="height:560px;border:1px solid var(--linha);border-radius:8px;background:#eee"></div>
    <p class="suave" id="contagem" style="margin-top:.5rem">Carregando mapa…</p>
    {tabela_dados}

    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
    (function() {{
      var CORES = {{{cores_js}}};
      var ROTULOS = {{{rotulos_js}}};
      var elContagem = document.getElementById('contagem');

      if (typeof L === 'undefined') {{
        elContagem.textContent = '';
        var aviso = document.createElement('p');
        aviso.className = 'erro';
        aviso.innerHTML = 'O mapa visual não carregou — provavelmente o antivírus, firewall ou proxy ' +
          'desta rede está bloqueando o serviço usado para desenhar o mapa (unpkg.com). ' +
          'Use a "Lista de pontos" abaixo, que mostra os mesmos dados sem depender disso.';
        document.getElementById('mapa').replaceWith(aviso);
        return;
      }}

      var mapa = L.map('mapa').setView([-22.4267, -45.4581], 12);
      var camadaTiles = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19, attribution: '&copy; OpenStreetMap'
      }}).addTo(mapa);
      var errosDeTile = 0;
      camadaTiles.on('tileerror', function() {{
        errosDeTile++;
        if (errosDeTile === 6) {{
          var aviso = document.createElement('p');
          aviso.className = 'erro';
          aviso.style.marginTop = '.5rem';
          aviso.innerHTML = 'O mapa de fundo (ruas) não carregou — provavelmente o antivírus, ' +
            'firewall ou proxy desta rede está bloqueando o serviço de mapas. Os pontos abaixo ' +
            'continuam funcionando normalmente, só sem o fundo com as ruas.';
          document.getElementById('mapa').insertAdjacentElement('afterend', aviso);
        }}
      }});
      var camadaMarcadores = L.layerGroup().addTo(mapa);
      var camadaCalor = null;
      var camadaLinhas = L.layerGroup().addTo(mapa);
      var TODOS_PONTOS = [];

      fetch('/mapa/dados.json').then(function(r) {{ return r.json(); }}).then(function(pontos) {{
        TODOS_PONTOS = pontos;
        window.aplicarFiltros();
      }}).catch(function(err) {{
        elContagem.textContent = 'Não foi possível carregar os pontos do mapa. Veja a lista abaixo.';
      }});

      window.aplicarFiltros = function aplicarFiltros() {{
        try {{
          var tipoCrime = document.getElementById('filtro_tipo_crime').value;
          var autor = document.getElementById('filtro_autor').value.trim().toLowerCase();
          var origem = document.getElementById('filtro_origem').value;
          var tiposAtivos = Array.from(document.querySelectorAll('.chk-tipo:checked')).map(c => c.value);
          var mostrarCalor = document.getElementById('chk_calor').checked;
          var soMaterial = document.getElementById('chk_so_material').checked;

          camadaMarcadores.clearLayers();
          camadaLinhas.clearLayers();
          if (camadaCalor) {{ mapa.removeLayer(camadaCalor); camadaCalor = null; }}

          var ocorrenciasComMaterial = new Set(
            TODOS_PONTOS.filter(p => p.materiais && p.materiais.length).map(p => p.ocorrencia_id)
          );

          var filtrados = TODOS_PONTOS.filter(function(p) {{
            if (tipoCrime && p.tipo_crime !== tipoCrime) return false;
            if (!tiposAtivos.includes(p.tipo_ponto)) return false;
            if (autor && !(p.nome_autor || '').toLowerCase().includes(autor)) return false;
            if (origem && (p.origem || 'ocorrencia') !== origem) return false;
            if (soMaterial && !ocorrenciasComMaterial.has(p.ocorrencia_id)) return false;
            return true;
          }});

          filtrados.forEach(function(p) {{
            var cor = CORES[p.tipo_ponto] || '#333';
            // Verificação em apuração aparece com o miolo claro e borda
            // tracejada, para não se confundir com ocorrência já registrada.
            var ehVerificacao = p.origem === 'verificacao';
            var marcador = L.circleMarker([p.lat, p.lon], {{
              radius: 7, color: cor, fillColor: cor,
              fillOpacity: ehVerificacao ? 0.15 : 0.85, weight: 2,
              dashArray: ehVerificacao ? '3 3' : null
            }});
            marcador.bindPopup(
              '<strong>' + (ROTULOS[p.tipo_ponto] || p.tipo_ponto) + '</strong><br>' +
              (p.tipo_crime ? 'Crime: ' + p.tipo_crime + '<br>' : '') +
              (p.nome ? 'Nome: ' + p.nome + '<br>' : '') +
              (p.endereco ? 'Endereço: ' + p.endereco + '<br>' : '') +
              (p.bairro || p.cidade ? 'Bairro/cidade: ' + [p.bairro, p.cidade].filter(Boolean).join(' — ') + '<br>' : '') +
              (p.data_fato ? 'Data do fato: ' + p.data_fato + '<br>' : '') +
              (p.materiais && p.materiais.length ? 'Materiais apreendidos: ' + p.materiais.join(', ') + '<br>' : '') +
              (ehVerificacao ? '<em>Denúncia em verificação</em><br>' : '') +
              '<a href="' + (p.link || '#') + '">' +
              (ehVerificacao ? 'Abrir verificação' : 'Abrir ocorrência') + '</a>'
            );
            camadaMarcadores.addLayer(marcador);
          }});

          if (autor) {{
            var porOcorrencia = {{}};
            filtrados.forEach(function(p) {{
              if (!(p.nome_autor || '').toLowerCase().includes(autor)) return;
              var chave = p.grupo || ('oc-' + p.ocorrencia_id);
              porOcorrencia[chave] = porOcorrencia[chave] || {{}};
              porOcorrencia[chave][p.tipo_ponto] = p;
            }});
            Object.values(porOcorrencia).forEach(function(grupo) {{
              if (grupo.autor && grupo.fato) {{
                L.polyline([[grupo.autor.lat, grupo.autor.lon], [grupo.fato.lat, grupo.fato.lon]], {{
                  color: '#9a7b2d', weight: 2, dashArray: '6 4'
                }}).addTo(camadaLinhas);
              }}
            }});
          }}

          if (mostrarCalor && filtrados.length) {{
            var pontosCalor = filtrados.map(function(p) {{ return [p.lat, p.lon, 0.6]; }});
            camadaCalor = L.heatLayer(pontosCalor, {{ radius: 28, blur: 20 }}).addTo(mapa);
          }}

          elContagem.textContent = filtrados.length + ' ponto(s) exibido(s) de ' + TODOS_PONTOS.length + ' no total.';
        }} catch (err) {{
          elContagem.textContent = 'O mapa encontrou um problema ao desenhar os pontos. Veja a lista abaixo.';
        }}
      }};
    }})();
    </script>"""
    return pagina("Mapa", corpo, usuario)
