"""Comunicações de serviço: rotas autenticadas, rascunhos e exportação."""
import base64
import binascii
import io
import json
import re
from sirio_core import conexao, pagina, e, audita, agora

MAX_BODY = 24 * 1024 * 1024
CAMPOS = ('numero', 'unidade', 'destinatario', 'assunto', 'referencia', 'local_data', 'assinatura')
ROTULOS = ('Número', 'Unidade', 'Destinatário', 'Assunto', 'Referência / procedimento', 'Local e data', 'Assinatura / cargo / MASP')

def banco():
    con = conexao()
    con.execute('''CREATE TABLE IF NOT EXISTS comunicacoes_livres (
        id INTEGER PRIMARY KEY, dados TEXT NOT NULL, versao INTEGER NOT NULL DEFAULT 1,
        criado_por INTEGER NOT NULL, atualizado_em TEXT NOT NULL)''')
    con.commit()
    return con

def imagem(valor):
    from PIL import Image
    m = re.fullmatch(r'data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)', valor)
    if not m:
        raise ValueError('Use uma foto PNG ou JPEG.')
    try:
        bruto = base64.b64decode(m[2], validate=True)
        if len(bruto) > 5 * 1024 * 1024:
            raise ValueError('Cada foto pode ter até 5 MB.')
        with Image.open(io.BytesIO(bruto)) as im:
            if im.format not in ('PNG', 'JPEG') or im.width * im.height > 24000000:
                raise ValueError('Foto inválida ou maior que 24 megapixels.')
            im.verify()
    except (binascii.Error, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Não foi possível ler a foto.') from exc
    return bruto

def validar(d):
    if not isinstance(d, dict):
        raise ValueError('Documento inválido.')
    novo = {}
    for k in CAMPOS:
        v = d.get(k, '')
        if not isinstance(v, str) or len(v) > 4000:
            raise ValueError('Campo muito longo ou inválido.')
        novo[k] = v.strip()
    blocos = d.get('blocos', [])
    if not isinstance(blocos, list) or len(blocos) > 100:
        raise ValueError('Use no máximo 100 blocos por documento.')
    novo['blocos'] = []
    for b in blocos:
        if not isinstance(b, dict) or b.get('tipo') not in ('texto', 'foto'):
            raise ValueError('Bloco inválido.')
        limpos = {'tipo': b['tipo']}
        for k in ('titulo', 'texto', 'legenda'):
            v = b.get(k, '')
            if not isinstance(v, str) or len(v) > (100000 if k == 'texto' else 4000):
                raise ValueError('Texto muito longo ou inválido.')
            limpos[k] = v
        if b['tipo'] == 'foto':
            v = b.get('imagem', '')
            if not isinstance(v, str):
                raise ValueError('Foto inválida.')
            imagem(v)
            limpos['imagem'] = v
        novo['blocos'].append(limpos)
    return novo

def documento_html(d):
    h = '<h1>COMUNICAÇÃO DE SERVIÇO</h1>'
    for k, rotulo in zip(CAMPOS[:-1], ROTULOS[:-1]):
        if d.get(k):
            h += f'<p><b>{rotulo}:</b> {e(d[k])}</p>'
    for b in d['blocos']:
        if b.get('titulo'): h += '<h2>' + e(b['titulo']) + '</h2>'
        if b['tipo'] == 'texto': h += '<div class="texto">' + e(b['texto']) + '</div>'
        else:
            h += '<figure><img src="' + e(b['imagem']) + '"><figcaption>' + e(b['legenda']) + '</figcaption></figure>'
    if d.get('assinatura'): h += '<p class="assinatura texto">' + e(d['assinatura']) + '</p>'
    return h

def word(d):
    from docx import Document
    from docx.shared import Cm, Pt
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2)
    sec.left_margin = sec.right_margin = Cm(2.5)
    doc.styles['Normal'].font.name = 'Arial'
    doc.styles['Normal'].font.size = Pt(11)
    doc.add_heading('COMUNICAÇÃO DE SERVIÇO', 0)
    for k, rotulo in zip(CAMPOS[:-1], ROTULOS[:-1]):
        if d.get(k): doc.add_paragraph(rotulo + ': ' + d[k])
    for b in d['blocos']:
        if b.get('titulo'): doc.add_heading(b['titulo'], 1)
        if b['tipo'] == 'texto':
            for linha in b['texto'].split('\n'): doc.add_paragraph(linha)
        else:
            from PIL import Image
            raw = imagem(b['imagem'])
            with Image.open(io.BytesIO(raw)) as im: w, h = im.size
            largura = min(16, 20 * w / h)
            doc.add_picture(io.BytesIO(raw), width=Cm(largura))
            if b['legenda']: doc.add_paragraph(b['legenda'], 'Caption')
    if d.get('assinatura'): doc.add_paragraph(d['assinatura'])
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()

def editor(usuario, csrf, item=None):
    d = json.loads(item['dados']) if item else {'blocos': []}
    payload = json.dumps(d, ensure_ascii=False).replace('<', '\\u003c')
    campos = ''.join(f'<label>{r}<input name="{k}" value="{e(d.get(k, ""))}"></label>' for k, r in zip(CAMPOS, ROTULOS))
    corpo = '''<h1>Comunicação de serviço</h1><p>Títulos, textos e campos do cabeçalho são opcionais. Adicione fotos entre os textos e use as setas para ordenar.</p>
<a href="/comunicacoes">Voltar à lista</a><form id="editor">''' + campos + '''<div id="blocos"></div>
<button type="button" id="texto">Adicionar texto / capítulo</button>
<label>Adicionar fotos (PNG ou JPEG, até 5 MB cada)<input type="file" id="fotos" accept="image/png,image/jpeg" multiple></label>
<button id="salvar">Salvar comunicação</button><p role="status" id="status"></p></form>
<style>#editor label{display:block;margin:12px 0}#editor input,#editor textarea{width:100%}.bloco{border:1px solid #bbb;padding:16px;margin:16px 0}.bloco img{max-width:320px;max-height:240px}textarea{min-height:140px}</style>
<script>const inicial=''' + payload + ';let id=' + str(item['id'] if item else 0) + ';let versao=' + str(item['versao'] if item else 0) + ';const csrf=' + json.dumps(csrf) + ''';
let blocos=inicial.blocos||[];let alterado=false;const area=document.getElementById('blocos');
function elemento(tag,texto){const x=document.createElement(tag);if(texto)x.textContent=texto;return x;}
function desenhar(){area.replaceChildren();blocos.forEach((b,i)=>{const box=elemento('section');box.className='bloco';
const titulo=elemento('input');titulo.placeholder='Título opcional';titulo.value=b.titulo||'';titulo.oninput=()=>{b.titulo=titulo.value;alterado=true};box.append(titulo);
if(b.tipo==='texto'){const t=elemento('textarea');t.placeholder='Conteúdo opcional';t.value=b.texto||'';t.oninput=()=>{b.texto=t.value;alterado=true};box.append(t)}else{const img=elemento('img');img.src=b.imagem;img.alt=b.legenda||'Foto da comunicação';const l=elemento('input');l.placeholder='Legenda opcional';l.value=b.legenda||'';l.oninput=()=>{b.legenda=l.value;alterado=true};box.append(img,l)}
[['↑',-1],['↓',1],['Remover',0]].forEach(([nome,delta])=>{const bt=elemento('button',nome);bt.type='button';bt.disabled=delta!==0&&(i+delta<0||i+delta>=blocos.length);bt.onclick=()=>{if(delta){[blocos[i],blocos[i+delta]]=[blocos[i+delta],blocos[i]]}else{if(!confirm('Remover este bloco?'))return;blocos.splice(i,1)}alterado=true;desenhar()};box.append(bt)});area.append(box)})}
document.getElementById('texto').onclick=()=>{blocos.push({tipo:'texto',titulo:'',texto:''});alterado=true;desenhar()};
document.getElementById('fotos').onchange=async ev=>{try{for(const f of ev.target.files){if(!['image/png','image/jpeg'].includes(f.type)||f.size>5*1024*1024)throw Error('Use PNG ou JPEG de até 5 MB.');const url=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result);r.onerror=no;r.readAsDataURL(f)});blocos.push({tipo:'foto',imagem:url,legenda:''});alterado=true;desenhar()}}catch(err){alert(err.message)}ev.target.value=''};
document.getElementById('editor').addEventListener('input',()=>alterado=true);
window.addEventListener('beforeunload',ev=>{if(alterado){ev.preventDefault();ev.returnValue=''}});
document.getElementById('editor').onsubmit=async ev=>{ev.preventDefault();const bt=document.getElementById('salvar'),st=document.getElementById('status');bt.disabled=true;st.textContent='Salvando…';try{const dados=Object.fromEntries(new FormData(ev.target));dados.blocos=blocos;const res=await fetch('/comunicacoes/salvar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf,id,versao,dados})});const r=await res.json();if(!res.ok)throw Error(r.erro||'Falha ao salvar');alterado=false;location.href='/comunicacoes/'+r.id}catch(err){st.textContent=err.message}finally{bt.disabled=false}};desenhar();</script>'''
    return pagina('Comunicação de serviço', corpo, usuario)

def atender(handler, metodo, usuario, csrf):
    caminho = handler.caminho()
    if not (caminho == '/comunicacoes' or caminho.startswith('/comunicacoes/')): return False
    def erro(msg, status=400):
        handler.responde_json({'erro': msg}, status)
        return True
    pode = usuario['perfil'] in ('admin', 'analista')
    if metodo == 'POST':
        if caminho != '/comunicacoes/salvar': return erro('Rota não encontrada.',404)
        if not pode: return erro('Perfil sem permissão para editar.',403)
        try:
            n = int(handler.headers.get('Content-Length', '0'))
            if n <= 0 or n > MAX_BODY: return erro('Documento maior que 24 MB ou envio vazio.',413)
            corpo = json.loads(handler.rfile.read(n))
            if not isinstance(corpo,dict) or not isinstance(corpo.get('csrf'),str) or not handler.csrf_ok(corpo,csrf): return erro('Sessão expirada. Reabra a página.',403)
            d = validar(corpo.get('dados'))
            ident, versao = int(corpo.get('id',0)), int(corpo.get('versao',0))
        except ImportError: return erro('Instale Pillow usando Instalar Modulo.bat.',503)
        except (ValueError, TypeError, UnicodeError) as exc: return erro(str(exc))
        con = banco()
        try:
            texto = json.dumps(d, ensure_ascii=False)
            if ident:
                cur=con.execute('UPDATE comunicacoes_livres SET dados=?,versao=versao+1,atualizado_em=? WHERE id=? AND versao=?',(texto,agora(),ident,versao))
                if not cur.rowcount: return erro('Este documento foi alterado em outra janela. Copie seu texto antes de reabrir.',409)
            else:
                ident=con.execute('INSERT INTO comunicacoes_livres(dados,criado_por,atualizado_em) VALUES(?,?,?)',(texto,usuario['id'],agora())).lastrowid
            audita(con,usuario['id'],'UPDATE' if corpo.get('id') else 'CREATE',None,'comunicacao_livre',None,str(ident))
            con.commit()
        finally: con.close()
        handler.responde_json({'id':ident})
        return True
    if caminho == '/comunicacoes/nova':
        if not pode: return erro('Perfil sem permissão para editar.',403)
        handler.responde_html(editor(usuario,csrf));return True
    con = banco()
    try:
        if caminho == '/comunicacoes':
            itens=con.execute('SELECT * FROM comunicacoes_livres ORDER BY id DESC').fetchall()
            h='<h1>Comunicações de serviço</h1>' + ('<p><a href="/comunicacoes/nova">Nova comunicação</a></p>' if pode else '')
            for it in itens:
                d=json.loads(it['dados'])
                h+=f'<p><a href="/comunicacoes/{it["id"]}">{e(d.get("numero") or "Sem número")} — {e(d.get("assunto") or "Sem assunto")}</a> · {e(it["atualizado_em"])}</p>'
            handler.responde_html(pagina('Comunicações',h if itens else h+'<p>Nenhuma comunicação salva.</p>',usuario));return True
        m=re.fullmatch(r'/comunicacoes/(\d+)(/editar|/imprimir|/documento.docx)?',caminho)
        it=con.execute('SELECT * FROM comunicacoes_livres WHERE id=?',(int(m[1]),)).fetchone() if m else None
    finally: con.close()
    if it is None: return erro('Comunicação não encontrada.',404)
    acao=m[2] or ''
    if acao == '/editar':
        if not pode: return erro('Perfil sem permissão para editar.',403)
        handler.responde_html(editor(usuario,csrf,it));return True
    d=json.loads(it['dados'])
    if acao == '/documento.docx':
        try: raw=word(d)
        except ImportError: return erro('Instale python-docx e Pillow usando Instalar Modulo.bat.',503)
        handler.send_response(200)
        handler.send_header('Content-Type','application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        handler.send_header('Content-Disposition',f'attachment; filename="comunicacao_{it["id"]}.docx"')
        handler.send_header('Content-Length',str(len(raw)))
        handler.send_header('Cache-Control','no-store')
        handler.end_headers();handler.wfile.write(raw);return True
    barra=f'<div class="acoes"><a href="/comunicacoes">Voltar</a> · <a href="/comunicacoes/{it["id"]}/documento.docx">Baixar Word</a> · <button onclick="window.print()">Imprimir / salvar em PDF</button>'
    if pode: barra+=f' · <a href="/comunicacoes/{it["id"]}/editar">Editar</a>'
    css='<style>.texto{white-space:pre-wrap;overflow-wrap:anywhere}figure{text-align:center;break-inside:avoid}figure img{max-width:100%;max-height:22cm}figcaption{font-size:10pt}.assinatura{margin-top:3em;text-align:center}h2{break-after:avoid}@page{size:A4;margin:2cm 2.5cm}@media print{.topo,.acoes{display:none!important}body,main.conteudo{background:white!important;color:black!important;margin:0!important;padding:0!important;max-width:none!important}h1{font-size:16pt}h2{font-size:13pt}}</style>'
    handler.responde_html(pagina('Comunicação de serviço',css+barra+'</div>'+documento_html(d),usuario));return True
