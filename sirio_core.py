"""Módulo SIRIO — infraestrutura compartilhada (banco, sessão, HTML, constantes,
auditoria). Usada por todos os outros módulos do sistema via `from sirio_core import *`.
"""
import csv
import email
import email.policy
import hashlib
import html
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
import unicodedata
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Importação de BO (PDF) é opcional: só ativa se a biblioteca pypdf estiver instalada.
# O sistema funciona normalmente sem ela.
try:
    from pypdf import PdfReader
    PDF_DISPONIVEL = True
except ImportError:
    PDF_DISPONIVEL = False

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------

VERSAO = "4.0"
PORTA = int(os.environ.get("SIRIO_PORTA", "8377"))
PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_DB = os.path.join(PASTA, "sirio.db")
PASTA_FOTOS = os.path.join(PASTA, "fotos")
# Anexos do módulo de Violência Doméstica. A tabela vd_anexos já existe, mas
# ainda não há tela de upload. A constante fica definida para que a exclusão em
# cascata funcione desde já, sem precisar de tratamento especial depois.
PASTA_VD_ANEXOS = os.path.join(PASTA, "anexos_vd")

# Geocodificação é executada pelo navegador para não expor uma chave de API no
# servidor. Photon é a busca principal porque oferece tolerância a erros de
# digitação; Nominatim fica como contingência. Ambos recebem somente o endereço
# informado quando o usuário aciona o botão de localização.
SCRIPT_GEOCODIFICADOR = """
<script>
function descricaoGeocodificacao(props) {
  return [props.name, props.housenumber, props.street, props.district,
    props.city, props.state, props.postcode].filter(Boolean).join(', ');
}

function pontuacaoSemelhanca(endereco, props) {
  var normalizar = function(texto) {
    return (texto || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9 ]/g, ' ');
  };
  var termos = normalizar(endereco).split(/\\s+/).filter(function(termo) {
    return termo.length > 1;
  });
  var candidato = normalizar(descricaoGeocodificacao(props));
  return termos.reduce(function(total, termo) {
    return total + (candidato.includes(termo) ? 1 : 0);
  }, 0);
}

async function geocodificar(idEnd, idLat, idLon, idBairro, idCidade) {
  var campoEndereco = document.getElementById(idEnd);
  var endereco = campoEndereco.value.trim();
  if (!endereco) { alert('Digite um endereço primeiro.'); return; }

  // Bairro e cidade entram na busca como contexto. Sem eles, um logradouro
  // comum ("Rua Princesa Isabel") casa com qualquer cidade do Brasil, e o
  // resultado pode cair a centenas de quilômetros do lugar certo.
  var contexto = [];
  [idBairro, idCidade].forEach(function(id) {
    if (!id) return;
    var campo = document.getElementById(id);
    if (campo && campo.value.trim()) contexto.push(campo.value.trim());
  });
  var consulta = [endereco].concat(contexto).join(', ');

  try {
    // Photon faz busca aproximada e limita os resultados ao Brasil.
    var url = 'https://photon.komoot.io/api/?limit=5&countrycode=BR&q=' +
      encodeURIComponent(consulta);
    var resp = await fetch(url);
    if (!resp.ok) throw new Error('Photon indisponível');
    var dados = await resp.json();
    var opcoes = (dados.features || []).filter(function(item) {
      return item.geometry && item.geometry.coordinates && item.geometry.coordinates.length >= 2;
    });
    opcoes.sort(function(a, b) {
      return pontuacaoSemelhanca(consulta, b.properties || {}) -
        pontuacaoSemelhanca(consulta, a.properties || {});
    });

    if (opcoes.length) {
      var indice = 0;
      if (opcoes.length > 1) {
        var lista = opcoes.map(function(item, i) {
          return (i + 1) + '. ' + (descricaoGeocodificacao(item.properties || {}) || 'Local sem descrição');
        }).join('\\n');
        var escolha = prompt('Foram encontrados locais semelhantes. Escolha o número para confirmar:\\n\\n' + lista, '1');
        if (escolha === null) return;
        indice = Number(escolha) - 1;
        if (!Number.isInteger(indice) || !opcoes[indice]) {
          alert('Escolha inválida. As coordenadas não foram alteradas.');
          return;
        }
      }
      var coordenadas = opcoes[indice].geometry.coordinates;
      document.getElementById(idLat).value = coordenadas[1];
      document.getElementById(idLon).value = coordenadas[0];
      return;
    }

    // Contingência para locais ainda não indexados pelo Photon.
    var fallback = await fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=br&q=' +
      encodeURIComponent(consulta));
    var resultados = fallback.ok ? await fallback.json() : [];
    if (resultados && resultados.length) {
      document.getElementById(idLat).value = resultados[0].lat;
      document.getElementById(idLon).value = resultados[0].lon;
      alert('Localização aproximada encontrada. Confira o endereço antes de salvar.');
    } else {
      alert('Nenhum endereço semelhante foi encontrado. Confira a grafia ou informe as coordenadas manualmente.');
    }
  } catch (err) {
    alert('Não foi possível buscar automaticamente. Verifique a internet ou informe as coordenadas manualmente.');
  }
}
</script>"""

# Imagens aceitas: extensão -> (content-type, assinatura dos primeiros bytes)
TIPOS_IMAGEM = {
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG",)),
    ".gif": ("image/gif", (b"GIF8",)),
    ".webp": ("image/webp", (b"RIFF",)),
}
TAMANHO_MAX_FOTO = 10 * 1024 * 1024  # 10 MB por arquivo

STATUS = [
    ("ativo", "Ativo"),
    ("em_verificacao", "Em verificação"),
    ("inativo", "Inativo"),
    ("arquivado", "Arquivado"),
]
STATUS_LABEL = dict(STATUS)

PERFIS = [
    ("consulta", "Consulta — apenas visualiza"),
    ("analista", "Analista — cadastra e edita"),
    ("admin", "Administrador — controle total"),
]
PERFIL_LABEL = {"admin": "Administrador", "analista": "Analista", "consulta": "Consulta"}

# Campos editáveis da pessoa: (nome_no_banco, rótulo na tela)
CAMPOS_PESSOA = [
    ("nome", "Nome completo"),
    ("alcunha", "Alcunha / apelido"),
    ("rg", "RG"),
    ("cpf", "CPF"),
    ("data_nascimento", "Data de nascimento"),
    ("nome_mae", "Nome da mãe"),
    ("nome_pai", "Nome do pai"),
    ("qtd_filhos", "Quantidade de filhos"),
    ("nomes_filhos", "Nome dos filhos"),
    ("nome_companheira", "Esposa / companheira"),
    ("organizacao", "Organização criminosa"),
    ("cargo_orcrim", "Cargo / função na organização"),
    ("preso", "Está preso(a)"),
    ("data_ultima_prisao", "Data da última prisão"),
    ("crime_prisao", "Crime da prisão"),
    ("fonte_informacao", "Fonte da informação"),
    ("grau_confiabilidade", "Grau de confiabilidade"),
    ("observacoes", "Observações adicionais"),
    ("endereco", "Último endereço conhecido"),
    ("status", "Status do registro"),
]
ROTULO = dict(CAMPOS_PESSOA)

# Tipos de ponto exibidos no mapa (cor própria em cada um)
TIPOS_PONTO_MAPA = [
    ("fato", "Local do fato", "#8c2f2f"),
    ("vitima", "Residência da vítima", "#1e6b45"),
    ("autor", "Residência do autor", "#1F3864"),
    ("testemunha", "Residência de testemunha", "#8a6d1f"),
]

# ----------------------------------------------------------------------------
# Listas configuráveis pelo administrador (guardadas no banco, não mais fixas
# no código — o administrador cadastra/desativa opções direto pela aba
# "Configurações", sem precisar editar ou reiniciar o sistema).
CATEGORIAS_CONFIGURAVEIS = [
    ("tipo_crime", "Tipos de crime", "Usado ao cadastrar Ocorrências e para filtrar no Mapa."),
    ("categoria_material", "Categorias de material apreendido", "Usado na aba Materiais."),
    ("situacao_material", "Situações de material apreendido", "Usado na aba Materiais."),
    ("fonte_informacao", "Fontes de informação", "Usado no cadastro de pessoas (vínculo investigativo)."),
    ("grau_confiabilidade", "Graus de confiabilidade", "Usado no cadastro de pessoas (vínculo investigativo)."),
    ("vd_tipo_violencia", "Violência doméstica — Formas de violência", "Usado ao caracterizar um caso no módulo de Violência Doméstica."),
    ("vd_marcador_operacional", "Violência doméstica — Marcadores operacionais", "Usado ao caracterizar um caso no módulo de Violência Doméstica."),
    ("vd_tipo_medida_protetiva", "Violência doméstica — Tipos de medida protetiva", "Usado ao detalhar os itens de uma medida protetiva individualizada."),
    ("vd_tipo_diligencia", "Violência doméstica — Tipos de diligência", "Usado ao cadastrar diligências e providências de um caso."),
    ("vd_instituicao_encaminhamento", "Violência doméstica — Instituições da rede de proteção", "Usado ao encaminhar um caso para a rede de proteção."),
    ("canal_denuncia", "Verificação de denúncias — Canais de origem", "Por onde a denúncia chegou à unidade. Usado no módulo Verificação de denúncias."),
    ("orgao_origem_denuncia", "Verificação de denúncias — Órgãos de origem", "Quem encaminhou a denúncia. Usado no módulo Verificação de denúncias."),
]
ROTULO_CATEGORIA_CONFIGURAVEL = {c: r for c, r, _ in CATEGORIAS_CONFIGURAVEIS}

_SEED_OPCOES = {
    "grau_confiabilidade": [
        "Confirmada documentalmente",
        "Confirmada por diligência",
        "Informação de inteligência",
        "Informação de fonte humana",
        "Informação não confirmada",
        "Informação em verificação",
    ],
    "fonte_informacao": [
        "Boletim de ocorrência",
        "Relatório de investigação",
        "Diligência policial",
        "Fonte humana",
        "Consulta a banco de dados",
        "Interceptação autorizada judicialmente",
        "Documento apreendido",
        "Cooperação com outro órgão",
        "Outra fonte",
    ],
    "tipo_crime": [
        "Maria da Penha (violência doméstica)",
        "Tráfico de drogas",
        "Furto",
        "Roubo",
        "Homicídio",
        "Latrocínio",
        "Estupro / crime sexual",
        "Receptação",
        "Ameaça",
        "Lesão corporal",
        "Outro",
    ],
    "categoria_material": [
        "Telefone celular", "Arma de fogo", "Arma branca", "Droga",
        "Veículo", "Dinheiro", "Documento", "Outro",
    ],
    "situacao_material": [
        "Apreendido", "Restituído", "Encaminhado à perícia", "Destruído", "Outro",
    ],
    "vd_tipo_violencia": [
        "Física", "Psicológica", "Sexual", "Patrimonial", "Moral",
    ],
    "vd_marcador_operacional": [
        "Ameaça", "Ameaça de morte", "Lesão", "Estrangulamento", "Sufocamento",
        "Perseguição", "Vigilância", "Controle de telefone", "Controle de redes sociais",
        "Isolamento social", "Retenção de documentos", "Retenção de dinheiro",
        "Destruição de bens", "Dano patrimonial", "Invasão de dispositivo",
        "Exposição de intimidade", "Ameaça de divulgação de imagens íntimas",
        "Violência contra filhos", "Violência contra familiares", "Violência contra animais",
        "Conflito relacionado à guarda", "Conflito relacionado à pensão",
        "Expulsão da residência", "Privação de liberdade", "Violência durante a gravidez",
        "Violência após a separação", "Violência digital", "Outro",
    ],
    "vd_tipo_medida_protetiva": [
        "Afastamento do lar", "Proibição de aproximação", "Distância mínima",
        "Proibição de contato", "Restrição de contato por telefone",
        "Restrição de contato por mensagens", "Restrição de contato por redes sociais",
        "Proibição de frequentar determinados locais",
        "Suspensão ou restrição de porte de armas", "Entrega ou apreensão de arma",
        "Monitoração eletrônica", "Proteção patrimonial",
        "Restrições relacionadas aos filhos", "Acompanhamento por patrulha especializada",
        "Outra",
    ],
    "vd_tipo_diligencia": [
        "Oitiva de testemunha", "Oitiva da vítima", "Oitiva do suposto autor",
        "Perícia", "Busca e apreensão", "Requisição de documentos",
        "Diligência de endereço/localização", "Requisição de exame de corpo de delito",
        "Solicitação de dados a operadora/instituição financeira", "Outra",
    ],
    "canal_denuncia": [
        "Disque 100 (Ouvidoria Nacional de Direitos Humanos)",
        "Disque 180",
        "Disque 190",
        "WhatsApp da unidade",
        "Telefone da unidade",
        "Atendimento presencial",
        "E-mail institucional",
        "Ofício de outro órgão",
        "Delegacia Virtual",
        "Rede social",
        "Denúncia anônima",
        "Imprensa",
        "Outro",
    ],
    "orgao_origem_denuncia": [
        "Ouvidoria Nacional de Direitos Humanos (Disque 100)",
        "Ministério Público",
        "Poder Judiciário",
        "Defensoria Pública",
        "Conselho Tutelar",
        "Conselho Municipal do Idoso",
        "CRAS / CREAS",
        "Secretaria Municipal de Saúde",
        "Secretaria Municipal de Assistência Social",
        "Outra unidade policial",
        "Polícia Militar",
        "Ouvidoria da Polícia Civil",
        "Denúncia direta do cidadão",
        "Outro órgão",
    ],
    "vd_instituicao_encaminhamento": [
        "Assistência Social (CRAS/CREAS)", "Saúde", "Atendimento psicológico",
        "Defensoria Pública", "Ministério Público", "Poder Judiciário", "Abrigo",
        "Patrulha de Prevenção à Violência Doméstica", "Conselho Tutelar",
        "Programa municipal", "Programa de autonomia financeira",
        "Serviços de documentação", "Outro órgão",
    ],
}


def lista_ativa(categoria):
    """Devolve as opções ATIVAS de uma categoria configurável, na ordem de cadastro.
    Usada em todos os formulários/filtros no lugar das antigas listas fixas."""
    con = conexao()
    linhas = con.execute(
        "SELECT valor FROM opcoes_configuraveis WHERE categoria=? AND ativo=1 ORDER BY id", (categoria,)
    ).fetchall()
    con.close()
    return [r["valor"] for r in linhas]


def lista_ativa_com_atual(categoria, valor_atual):
    """Como lista_ativa, mas garante que o valor já gravado no registro apareça como
    opção mesmo se foi desativado depois em Configurações — evita que o valor mude
    silenciosamente ao abrir a tela (edição ou mesclagem) só porque a opção sumiu da lista."""
    lista = lista_ativa(categoria)
    if valor_atual and valor_atual not in lista:
        lista = lista + [(valor_atual, f"{valor_atual} (desativada)")]
    return lista


# ----------------------------------------------------------------------------
# Banco de dados (SQLite — já vem com o Python)
# ----------------------------------------------------------------------------

def sem_acento(texto):
    """Devolve o texto em minúsculas e sem acentuação, para comparação.

    Serve para a busca não depender de o usuário digitar "José" ou "jose":
    ambas as formas encontram o mesmo registro. É registrada no SQLite como a
    função sirio_norm() e usada nas cláusulas LIKE."""
    if texto is None:
        return ""
    normalizado = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in normalizado if not unicodedata.combining(c)).lower()


def conexao():
    con = sqlite3.connect(ARQ_DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # Disponível em qualquer consulta como sirio_norm(coluna).
    con.create_function("sirio_norm", 1, sem_acento)
    return con


# ----------------------------------------------------------------------------
# Migrações de banco
# ----------------------------------------------------------------------------
#
# Bancos criados em versões antigas ganham aqui as colunas que ainda não têm.
# Cada entrada é (tabela, coluna, tipo) e só roda se a coluna faltar — bancos
# já atualizados não sofrem alteração nenhuma.
#
# Para adicionar coluna nova em QUALQUER tabela, basta acrescentar a linha
# correspondente aqui. Antes, só pessoas e ocorrencias eram cobertas, e uma
# coluna nova em tabela vd_* nunca chegava aos bancos já em uso.

MIGRACOES = [
    ("pessoas", "cargo_orcrim", "TEXT"),
    ("pessoas", "preso", "TEXT"),
    ("pessoas", "data_ultima_prisao", "TEXT"),
    ("pessoas", "crime_prisao", "TEXT"),
    ("pessoas", "data_atualizacao_status_prisional", "TEXT"),
    ("ocorrencias", "cidade_fato", "TEXT"),
    ("ocorrencias", "bairro_fato", "TEXT"),
]


def aplica_migracoes(con, migracoes):
    """Acrescenta colunas que faltam. Devolve a lista do que foi alterado."""
    aplicadas = []
    existentes = {t[0] for t in
                  con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    cache = {}
    for tabela, coluna, tipo in migracoes:
        if tabela not in existentes:
            continue  # a tabela é criada pelo CREATE TABLE, já com a coluna
        if tabela not in cache:
            cache[tabela] = {r[1] for r in con.execute(f"PRAGMA table_info({tabela})")}
        if coluna in cache[tabela]:
            continue
        con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        cache[tabela].add(coluna)
        aplicadas.append(f"{tabela}.{coluna}")
    return aplicadas


def inicia_banco():
    con = conexao()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        perfil TEXT NOT NULL DEFAULT 'consulta',
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS pessoas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        alcunha TEXT, rg TEXT, cpf TEXT, data_nascimento TEXT,
        nome_mae TEXT, nome_pai TEXT, qtd_filhos TEXT,
        nomes_filhos TEXT, nome_companheira TEXT,
        organizacao TEXT, cargo_orcrim TEXT,
        preso TEXT, data_ultima_prisao TEXT, crime_prisao TEXT,
        data_atualizacao_status_prisional TEXT,
        fonte_informacao TEXT, grau_confiabilidade TEXT,
        observacoes TEXT, endereco TEXT,
        status TEXT NOT NULL DEFAULT 'em_verificacao',
        criado_em TEXT, criado_por INTEGER,
        atualizado_em TEXT, atualizado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        usuario_id INTEGER NOT NULL,
        acao TEXT NOT NULL,
        pessoa_id INTEGER,
        campo TEXT, valor_anterior TEXT, valor_novo TEXT
    );
    CREATE TABLE IF NOT EXISTS fotos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pessoa_id INTEGER NOT NULL,
        tipo TEXT NOT NULL DEFAULT 'fotografia',
        legenda TEXT,
        arquivo TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS ocorrencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_crime TEXT,
        numero_bo TEXT,
        data_fato TEXT,
        endereco_fato TEXT, lat_fato REAL, lon_fato REAL,
        cidade_fato TEXT, bairro_fato TEXT,
        pessoa_autor_id INTEGER,
        nome_autor TEXT, endereco_autor TEXT, lat_autor REAL, lon_autor REAL,
        nome_vitima TEXT, endereco_vitima TEXT, lat_vitima REAL, lon_vitima REAL,
        observacoes TEXT,
        criado_em TEXT, criado_por INTEGER,
        atualizado_em TEXT, atualizado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS ocorrencia_testemunhas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ocorrencia_id INTEGER NOT NULL,
        nome TEXT, endereco TEXT, lat REAL, lon REAL
    );
    CREATE TABLE IF NOT EXISTS materiais_apreendidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ocorrencia_id INTEGER,
        pessoa_id INTEGER,
        categoria TEXT,
        objeto TEXT,
        quantidade TEXT,
        marca TEXT, modelo TEXT, cor TEXT,
        situacao TEXT,
        numero_lacre TEXT,
        cidade TEXT, bairro TEXT,
        observacoes TEXT,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS boletins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reds TEXT,
        data_fato TEXT,
        historico TEXT,
        ocorrencia_id INTEGER,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS boletim_pessoa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        boletim_id INTEGER NOT NULL,
        pessoa_id INTEGER NOT NULL,
        tipo_envolvimento TEXT
    );
    CREATE TABLE IF NOT EXISTS opcoes_configuraveis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT NOT NULL,
        valor TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT, criado_por INTEGER
    );
    CREATE TABLE IF NOT EXISTS vinculo_posicoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organizacao_chave TEXT NOT NULL,
        pessoa_id INTEGER,
        x REAL NOT NULL,
        y REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS biqueiras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pessoa_id INTEGER NOT NULL,
        local TEXT,
        endereco TEXT, bairro TEXT, cidade TEXT,
        lat REAL, lon REAL,
        observacoes TEXT,
        criado_em TEXT, criado_por INTEGER
    );
    """)
    # Migração defensiva: bancos criados em versões bem antigas (antes de
    # cargo_orcrim, situação prisional, cidade/bairro do fato etc. existirem)
    # ganham as colunas que ainda não têm. Bancos já atualizados não sofrem
    # nenhuma alteração aqui — cada ALTER só roda se a coluna ainda não existe.
    aplica_migracoes(con, MIGRACOES)
    # Semente das listas configuráveis: só roda a primeira vez que cada
    # categoria aparece vazia (banco novo, ou upgrade de versão anterior que
    # ainda usava listas fixas no código). Depois disso, o administrador é
    # quem manda nessas opções pela aba Configurações.
    for categoria, _, _ in CATEGORIAS_CONFIGURAVEIS:
        existe = con.execute(
            "SELECT 1 FROM opcoes_configuraveis WHERE categoria=? LIMIT 1", (categoria,)).fetchone()
        if not existe:
            for valor in _SEED_OPCOES.get(categoria, []):
                con.execute(
                    "INSERT INTO opcoes_configuraveis (categoria, valor, ativo, criado_em) VALUES (?,?,1,?)",
                    (categoria, valor, agora()))
    con.commit()
    con.close()
    os.makedirs(PASTA_FOTOS, exist_ok=True)


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _num_ou_none(v):
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------------
# Validação de entrada
# ----------------------------------------------------------------------------
#
# Sem isto o sistema aceitava data_nascimento = "banana", qtd_filhos = "dois" e
# coordenada 999. Dado inválido não dá erro na hora: ele contamina relatório,
# quebra o mapa e só aparece meses depois, quando limpar é trabalho manual.

TAMANHO_MAX_TEXTO = 5000
TAMANHO_MAX_NOME = 200
ANO_MINIMO = 1900


def valida_data(valor, rotulo, obrigatoria_passado=False):
    """Devolve mensagem de erro, ou "" se a data estiver boa. Vazio é aceito."""
    if not valor:
        return ""
    try:
        data = datetime.strptime(valor, "%Y-%m-%d")
    except ValueError:
        return f"{rotulo}: data inválida. Use o seletor de data do formulário."
    if data.year < ANO_MINIMO:
        return f"{rotulo}: ano anterior a {ANO_MINIMO}. Confira o que foi digitado."
    if obrigatoria_passado and data.date() > datetime.now().date():
        return f"{rotulo}: a data está no futuro."
    return ""


def valida_inteiro(valor, rotulo, minimo=0, maximo=200):
    if not valor:
        return ""
    try:
        n = int(str(valor).strip())
    except (ValueError, TypeError):
        return f"{rotulo}: informe um número inteiro."
    if n < minimo:
        return f"{rotulo}: não pode ser negativo."
    if n > maximo:
        return f"{rotulo}: valor acima do razoável ({maximo})."
    return ""


def valida_coordenada(valor, rotulo, limite):
    """Latitude vai de -90 a 90; longitude, de -180 a 180."""
    if not valor:
        return ""
    n = _num_ou_none(valor)
    if n is None:
        return f"{rotulo}: informe um número (use ponto ou vírgula decimal)."
    if not -limite <= n <= limite:
        return f"{rotulo}: fora do intervalo válido (-{limite} a {limite})."
    return ""


def valida_tamanho(valor, rotulo, maximo=TAMANHO_MAX_TEXTO):
    if valor and len(valor) > maximo:
        return f"{rotulo}: texto longo demais (máximo {maximo} caracteres)."
    return ""


def valida_pessoa(d):
    """Devolve a primeira mensagem de erro encontrada, ou "" se estiver tudo bem."""
    verificacoes = [
        valida_tamanho(d.get("nome"), "Nome completo", TAMANHO_MAX_NOME),
        valida_tamanho(d.get("alcunha"), "Alcunha", TAMANHO_MAX_NOME),
        valida_data(d.get("data_nascimento"), "Data de nascimento", obrigatoria_passado=True),
        valida_data(d.get("data_ultima_prisao"), "Data da última prisão", obrigatoria_passado=True),
        valida_inteiro(d.get("qtd_filhos"), "Quantidade de filhos", 0, 50),
        valida_tamanho(d.get("observacoes"), "Observações"),
        valida_tamanho(d.get("endereco"), "Endereço"),
    ]
    return next((m for m in verificacoes if m), "")


def valida_ocorrencia(d):
    verificacoes = [
        valida_data(d.get("data_fato"), "Data do fato", obrigatoria_passado=True),
        valida_coordenada(d.get("lat_fato"), "Latitude do fato", 90),
        valida_coordenada(d.get("lon_fato"), "Longitude do fato", 180),
        valida_coordenada(d.get("lat_autor"), "Latitude do autor", 90),
        valida_coordenada(d.get("lon_autor"), "Longitude do autor", 180),
        valida_coordenada(d.get("lat_vitima"), "Latitude da vítima", 90),
        valida_coordenada(d.get("lon_vitima"), "Longitude da vítima", 180),
        valida_tamanho(d.get("observacoes"), "Observações"),
    ]
    return next((m for m in verificacoes if m), "")


def fmt_data(iso):
    if not iso:
        return "—"
    try:
        return datetime.strptime(iso, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


# ----------------------------------------------------------------------------
# Senhas (PBKDF2 — algoritmo seguro da biblioteca padrão)
# ----------------------------------------------------------------------------

def hash_senha(senha: str) -> str:
    sal = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), 200_000)
    return f"pbkdf2${sal}${h.hex()}"


def verifica_senha(senha: str, guardado: str) -> bool:
    try:
        _, sal, h = guardado.split("$")
        novo = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), 200_000)
        return secrets.compare_digest(novo.hex(), h)
    except (ValueError, AttributeError):
        return False


# ----------------------------------------------------------------------------
# Sessões (em memória: ao reiniciar o programa, todos fazem login de novo)
# ----------------------------------------------------------------------------

SESSOES = {}  # token -> {"usuario_id", "csrf", "criada_em", "ultimo_acesso"}

# Em computador compartilhado de unidade, sessão aberta é sessão de outra pessoa.
MINUTOS_INATIVIDADE = int(os.environ.get("SIRIO_MINUTOS_INATIVIDADE", "30"))
HORAS_SESSAO_MAXIMA = int(os.environ.get("SIRIO_HORAS_SESSAO", "12"))


def cria_sessao(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    agora_ts = time.time()
    SESSOES[token] = {
        "usuario_id": usuario_id,
        "csrf": secrets.token_urlsafe(24),
        "criada_em": agora_ts,
        "ultimo_acesso": agora_ts,
    }
    return token


def encerra_sessao(token):
    SESSOES.pop(token, None)


def encerra_sessoes_do_usuario(usuario_id, exceto=None):
    """Derruba as sessões abertas de uma pessoa (mudança de perfil, desativação)."""
    for tk, dados in list(SESSOES.items()):
        if dados["usuario_id"] == usuario_id and tk != exceto:
            SESSOES.pop(tk, None)


def sessao_expirada(dados) -> bool:
    agora_ts = time.time()
    if agora_ts - dados["ultimo_acesso"] > MINUTOS_INATIVIDADE * 60:
        return True
    if agora_ts - dados["criada_em"] > HORAS_SESSAO_MAXIMA * 3600:
        return True
    return False


def usuario_da_sessao(token):
    dados = SESSOES.get(token)
    if not dados:
        return None
    if sessao_expirada(dados):
        SESSOES.pop(token, None)
        return None
    con = conexao()
    u = con.execute("SELECT * FROM usuarios WHERE id=? AND ativo=1",
                    (dados["usuario_id"],)).fetchone()
    con.close()
    if u is None:
        # Usuário desativado no meio da sessão: o acesso cai na hora.
        SESSOES.pop(token, None)
        return None
    dados["ultimo_acesso"] = time.time()
    return u


# ----------------------------------------------------------------------------
# Proteção contra tentativa repetida de senha
# ----------------------------------------------------------------------------

# Sem isso, um login pode ser testado dezenas de vezes por segundo. No modo
# "Rede da Unidade" isso fica exposto a toda a rede interna.
MAX_TENTATIVAS = int(os.environ.get("SIRIO_MAX_TENTATIVAS", "5"))
MINUTOS_BLOQUEIO = int(os.environ.get("SIRIO_MINUTOS_BLOQUEIO", "15"))

_TENTATIVAS = {}  # chave -> [quantidade, momento_da_ultima_falha]


def _chave_tentativa(username, ip):
    return f"{(username or '').strip().lower()}|{ip or ''}"


def bloqueio_restante(username, ip) -> int:
    """Minutos que faltam para liberar. Zero significa liberado."""
    registro = _TENTATIVAS.get(_chave_tentativa(username, ip))
    if not registro or registro[0] < MAX_TENTATIVAS:
        return 0
    decorrido = time.time() - registro[1]
    if decorrido >= MINUTOS_BLOQUEIO * 60:
        _TENTATIVAS.pop(_chave_tentativa(username, ip), None)
        return 0
    return max(1, int((MINUTOS_BLOQUEIO * 60 - decorrido) / 60) + 1)


def registra_falha(username, ip):
    chave = _chave_tentativa(username, ip)
    registro = _TENTATIVAS.get(chave)
    if registro and time.time() - registro[1] < MINUTOS_BLOQUEIO * 60:
        registro[0] += 1
        registro[1] = time.time()
    else:
        _TENTATIVAS[chave] = [1, time.time()]
    return _TENTATIVAS[chave][0]


def limpa_tentativas(username, ip):
    _TENTATIVAS.pop(_chave_tentativa(username, ip), None)


ARQ_REGISTRO_ACESSO = os.path.join(PASTA, "registro_de_acesso.txt")


def registra_login_falho(username, ip, falhas, maximo, usuario_id=None):
    """Anota a tentativa fracassada, sem nunca deixar o login cair por causa disso.

    Vai para a auditoria quando o login existe (há usuario_id para registrar) e
    sempre para o arquivo de acesso, que é onde ficam também as tentativas com
    login inexistente — justamente as mais indicativas de varredura.
    """
    linha = (f"{agora()}  LOGIN FALHOU  login informado: {username!r}  "
             f"origem: {ip}  tentativa {falhas} de {maximo}\n")
    try:
        with open(ARQ_REGISTRO_ACESSO, "a", encoding="utf-8") as f:
            f.write(linha)
    except OSError:
        pass
    if usuario_id is None:
        return
    try:
        con = conexao()
        audita(con, usuario_id, "LOGIN_FALHA", None, "login", username,
               f"tentativa {falhas} de {maximo} — origem {ip}")
        con.commit()
        con.close()
    except sqlite3.Error:
        # Registrar a falha nunca pode impedir alguém de usar a tela de login.
        pass


# ----------------------------------------------------------------------------
# Auditoria
# ----------------------------------------------------------------------------

def copia_banco_consistente(destino):
    """Copia o banco de forma íntegra, mesmo com o sistema aberto e em uso.

    Copiar o arquivo direto pode capturar uma gravação pela metade. A API de
    backup do SQLite resolve isso, mas ela exige um sistema de arquivos que
    aceite as operações de bloqueio que o SQLite usa — em pasta de rede ou
    pendurada em pendrive isso às vezes falha com "disk I/O error".

    Por isso a cópia é montada primeiro em pasta temporária local, onde a API
    funciona, e só depois movida para o destino final. Assim vale nos dois
    mundos: a cópia sai consistente e o destino pode ser qualquer lugar.
    """
    if not os.path.isfile(ARQ_DB):
        return False
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            temporario = tmp.name
        origem = sqlite3.connect(ARQ_DB)
        copia = sqlite3.connect(temporario)
        try:
            with copia:
                origem.backup(copia)
        finally:
            copia.close()
            origem.close()
        shutil.copy2(temporario, destino)
        return True
    finally:
        if temporario and os.path.exists(temporario):
            try:
                os.remove(temporario)
            except OSError:
                pass


def exclui_pessoa_em_cascata(con, pid):
    """Apaga a pessoa e tudo que depende dela, na mesma transação.

    O banco não declara chaves estrangeiras, então a cascata é feita aqui. Sem
    isso, excluir uma pessoa deixa fotos no disco e linhas apontando para um
    registro que não existe mais.

    A trilha de auditoria é preservada de propósito: ela guarda o nome da pessoa
    no momento da exclusão e é a prova de que a exclusão aconteceu.

    Devolve a lista de arquivos de foto que precisam ser apagados do disco.
    """
    arquivos = [f["arquivo"] for f in
                con.execute("SELECT arquivo FROM fotos WHERE pessoa_id=?", (pid,))]

    # Vínculos do módulo de Violência Doméstica: a ficha específica e o FONAR
    # pendem de vd_caso_pessoas, então são apagados antes dele.
    cps = [r["id"] for r in
           con.execute("SELECT id FROM vd_caso_pessoas WHERE pessoa_id=?", (pid,))]
    for cpid in cps:
        aplicacoes = [r["id"] for r in con.execute(
            "SELECT id FROM vd_fonar_aplicacoes WHERE caso_pessoa_id=?", (cpid,))]
        for aid in aplicacoes:
            con.execute("DELETE FROM vd_fonar_respostas WHERE aplicacao_id=?", (aid,))
        con.execute("DELETE FROM vd_fonar_aplicacoes WHERE caso_pessoa_id=?", (cpid,))
        con.execute("DELETE FROM vd_dados_mulher WHERE caso_pessoa_id=?", (cpid,))
        con.execute("DELETE FROM vd_dados_autor WHERE caso_pessoa_id=?", (cpid,))
    con.execute("DELETE FROM vd_caso_pessoas WHERE pessoa_id=?", (pid,))

    con.execute("DELETE FROM fotos WHERE pessoa_id=?", (pid,))
    con.execute("DELETE FROM biqueiras WHERE pessoa_id=?", (pid,))
    con.execute("DELETE FROM boletim_pessoa WHERE pessoa_id=?", (pid,))
    con.execute("DELETE FROM vinculo_posicoes WHERE pessoa_id=?", (pid,))

    # Material apreendido é prova ligada a uma ocorrência: o registro permanece,
    # apenas deixa de apontar para a pessoa excluída. Mesmo critério já usado na
    # exclusão de ocorrência.
    con.execute("UPDATE materiais_apreendidos SET pessoa_id=NULL WHERE pessoa_id=?", (pid,))
    con.execute("UPDATE ocorrencias SET pessoa_autor_id=NULL WHERE pessoa_autor_id=?", (pid,))

    con.execute("DELETE FROM pessoas WHERE id=?", (pid,))
    return arquivos


def audita(con, usuario_id, acao, pessoa_id=None, campo=None, anterior=None, novo=None):
    con.execute(
        "INSERT INTO auditoria (timestamp, usuario_id, acao, pessoa_id, campo, valor_anterior, valor_novo)"
        " VALUES (?,?,?,?,?,?,?)",
        (agora(), usuario_id, acao, pessoa_id, campo,
         None if anterior is None else str(anterior),
         None if novo is None else str(novo)),
    )


# ----------------------------------------------------------------------------
# HTML — aparência institucional
# ----------------------------------------------------------------------------

def e(v):
    """Escapa texto para HTML com segurança (nunca exibir dado cru)."""
    return html.escape(str(v)) if v not in (None, "") else ""


def js_attr(v):
    """Escapa um valor para uso seguro dentro de um literal JS de aspas simples
    embutido num atributo HTML (ex.: onclick="funcao('...')"). Evita que aspas
    simples, barras invertidas ou quebras de linha no dado quebrem o script."""
    s = str(v or "")
    s = s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
    return e(s)


CSS = """
:root{--tinta:#1c2128;--tinta2:#4b5563;--papel:#f4f3ef;--branco:#fff;--linha:#ddd9d0;
--ouro:#9a7b2d;--ouro2:#c9a85c;--perigo:#8c2f2f;--alta:#1e6b45;--media:#8a6d1f;--baixa:#6b7280}
*{box-sizing:border-box}
body{margin:0;font-family:"Segoe UI",system-ui,sans-serif;background:var(--papel);color:var(--tinta)}
a{color:var(--ouro)}
h1{font-size:1.4rem;margin:0}
h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:var(--tinta2);margin:0 0 .7rem}
.faixa{background:var(--tinta);color:#e8e2d4;font-size:.72rem;letter-spacing:.04em;text-align:center;
padding:.35rem 1rem;border-bottom:2px solid var(--ouro)}
.topo{background:var(--tinta);color:#d8d4ca;display:flex;align-items:center;gap:1.4rem;
padding:.6rem 1.4rem;flex-wrap:wrap}
.sigla{font-size:1.25rem;font-weight:700;letter-spacing:.16em;color:var(--ouro2);text-decoration:none}
.topo nav{display:flex;gap:.3rem;flex-wrap:wrap}
.topo nav a{color:#d8d4ca;text-decoration:none;padding:.4rem .7rem;border-radius:6px;font-size:.88rem}
.topo nav a:hover{background:rgba(255,255,255,.08)}
.quem{margin-left:auto;font-size:.78rem;text-align:right}
.quem strong{color:#fff;display:block}
.conteudo{max-width:1050px;margin:0 auto;padding:1.6rem 1.2rem}
.botao{font:inherit;font-size:.88rem;padding:.5rem 1rem;border-radius:6px;border:1px solid transparent;
cursor:pointer;text-decoration:none;display:inline-block;background:var(--ouro);color:#fff}
.botao:hover{background:#856823}
.botao.fantasma{background:transparent;border-color:var(--linha);color:inherit}
.botao.fantasma:hover{border-color:var(--ouro)}
.botao.perigo{background:transparent;border-color:var(--perigo);color:var(--perigo)}
.botao.perigo:hover{background:var(--perigo);color:#fff}
.botao.mini{padding:.25rem .6rem;font-size:.78rem}
label{display:flex;flex-direction:column;gap:.3rem;font-size:.82rem;color:var(--tinta2)}
input,select,textarea{font:inherit;font-size:.92rem;color:var(--tinta);padding:.5rem .6rem;
border:1px solid var(--linha);border-radius:6px;background:#fff;width:100%}
input:focus,select:focus,textarea:focus,.botao:focus-visible,a:focus-visible{
outline:2px solid var(--ouro);outline-offset:1px}
fieldset{border:1px solid var(--linha);border-radius:8px;background:#fff;padding:1rem 1.2rem 1.2rem;margin:0 0 1rem}
legend{font-size:.76rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--ouro);padding:0 .4rem}
.grade{display:grid;grid-template-columns:1fr 1fr;gap:.9rem 1.2rem}
.span2{grid-column:span 2}
.acoes{display:flex;gap:.6rem;justify-content:flex-end;align-items:center;margin-top:.6rem;flex-wrap:wrap}
.cab{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin-bottom:1.2rem;flex-wrap:wrap}
.painel{background:#fff;border:1px solid var(--linha);border-radius:8px;padding:.9rem;margin-bottom:1.2rem;
display:grid;grid-template-columns:repeat(3,1fr) auto;gap:.6rem}
.painel .larga{grid-column:1/-1}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--linha);border-radius:8px;overflow:hidden}
.tabela-rolavel{overflow-x:auto;border:1px solid var(--linha);border-radius:8px;background:#fff;margin-bottom:1.2rem;
-webkit-overflow-scrolling:touch}
.colunas-moveis thead th{cursor:grab;user-select:none;position:relative}
.colunas-moveis thead th:active{cursor:grabbing}
/* A "pega" só aparece quando o mouse passa por cima: em coluna estreita ela
   ficaria em cima do próprio título. */
.colunas-moveis thead th::after{content:"⠿";position:absolute;right:.3rem;top:50%;transform:translateY(-50%);
opacity:0;font-size:.8rem;letter-spacing:-1px;transition:opacity .15s;pointer-events:none}
.colunas-moveis thead th:hover::after{opacity:.5}
.colunas-moveis thead th:hover{background:#e7e3d8}
.colunas-moveis thead th.arrastando{opacity:.45}
.colunas-moveis thead th.alvo-solta{outline:2px dashed var(--ouro);outline-offset:-3px}
/* Rolagem vertical com o cabeçalho grudado no topo: em lista longa, a gente
   perde de vista o nome da coluna bem na hora de conferir um dado.
   Estas regras vêm DEPOIS das de .colunas-moveis de propósito: as duas têm o
   mesmo peso, e aqui o position:sticky precisa vencer o position:relative. */
.tabela-alta{max-height:68vh;overflow-y:auto}
/* a regra geral de table usa overflow:hidden (canto arredondado) e
   border-collapse:collapse — as duas coisas atrapalham o cabeçalho grudado. */
.tabela-alta table{overflow:visible;border-collapse:separate;border-spacing:0}
.tabela-alta thead th{position:sticky;top:0;z-index:3;box-shadow:inset 0 -1px 0 var(--linha)}
.barra-tabela{display:flex;justify-content:space-between;align-items:center;gap:.6rem;flex-wrap:wrap;
margin-bottom:.4rem}
.tabela-rolavel table{border:none;border-radius:0;margin-bottom:0}
.tab-registros{min-width:1280px;table-layout:fixed}
.tab-registros th,.tab-registros td{word-wrap:break-word;overflow-wrap:break-word}
.tab-registros col.c-nome{width:20%}
.tab-registros col.c-alcunha{width:6%}
.tab-registros col.c-cpf{width:8%}
.tab-registros col.c-org{width:10%}
.tab-registros col.c-cargo{width:9%}
.tab-registros col.c-crime{width:13%}
.tab-registros col.c-oc{width:6%}
.tab-registros col.c-mat{width:6%}
.tab-registros col.c-conf{width:12%}
.tab-registros col.c-preso{width:6%}
.tab-registros col.c-status{width:4%}
.num-col{white-space:nowrap;text-align:center}
.nowrap-col{white-space:nowrap}
th{text-align:left;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--tinta2);
background:#efede7;padding:.55rem .7rem}
td{padding:.55rem .7rem;border-top:1px solid var(--linha);font-size:.88rem;vertical-align:top}
.mono{font-family:Consolas,monospace;font-size:.74rem;overflow-wrap:anywhere;max-width:220px}
.nomelink{font-weight:600;color:var(--tinta);text-decoration:none}
.nomelink:hover{color:var(--ouro);text-decoration:underline}
.selo{display:inline-block;font-size:.72rem;font-weight:600;padding:.16rem .55rem;border-radius:999px;
border:1px solid currentColor}
.s-alta{color:var(--alta)}.s-media{color:var(--media)}.s-baixa{color:var(--baixa)}
.s-vazio{color:#9ca3af;border-style:dashed}
.s-alcunha{color:var(--tinta2);border-style:dotted;font-style:italic}
.s-preso{background:var(--perigo);color:#fff;border-color:var(--perigo);font-weight:700}
.s-solto{color:var(--alta);border-style:dashed}
.pill{display:inline-block;font-size:.72rem;font-weight:600;padding:.16rem .55rem;border-radius:4px}
.p-ativo{background:#e3efe8;color:var(--alta)}
.p-em_verificacao{background:#f3ecd9;color:var(--media)}
.p-inativo{background:#ececec;color:var(--baixa)}
.p-arquivado{background:#e9e4f2;color:#5b4a82}
.p-CREATE{background:#e3efe8;color:var(--alta)}
.p-fotografia{background:#e7edf4;color:#2d4f7c}
.p-tatuagem{background:#efe7f4;color:#5b3a7c}
.p-FOTO_ADD{background:#e7edf4;color:#2d4f7c}
.p-FOTO_DEL{background:#f4e3e3;color:var(--perigo)}
.p-UPDATE,.p-STATUS{background:#f3ecd9;color:var(--media)}
.p-DELETE{background:#f4e3e3;color:var(--perigo)}
.p-MERGE{background:#e9e4f2;color:#5b4a82}
.p-BACKUP{background:#e3efe8;color:var(--alta)}
.p-VIEW,.p-LOGIN,.p-EXPORT{background:#ececec;color:var(--baixa)}
.cartoes{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem}
.cartao{background:#fff;border:1px solid var(--linha);border-radius:8px;padding:1rem 1.2rem;margin-bottom:1rem}
.cartoes .cartao{margin-bottom:0}
.li-campo{display:flex;flex-direction:column;padding:.32rem 0;border-bottom:1px dashed var(--linha)}
.li-campo:last-child{border-bottom:none}
.li-campo .rot{font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;color:var(--tinta2)}
.li-campo .val{font-size:.92rem;white-space:pre-wrap}
.selos{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.4rem}
.erro{color:var(--perigo);background:#f7eaea;border:1px solid #e3c8c8;border-radius:6px;padding:.55rem .8rem;font-size:.85rem}
.ok{color:var(--alta);background:#e8f2ec;border:1px solid #c6dccf;border-radius:6px;padding:.55rem .8rem;font-size:.85rem}
.suave{color:var(--tinta2);font-size:.84rem}
.vazio{background:#fff;border:1px dashed var(--linha);border-radius:8px;padding:2rem;text-align:center;color:var(--tinta2)}
.login-fundo{min-height:100vh;display:grid;place-items:center;background:var(--tinta);padding:1rem}
.login-cx{background:#fff;border-radius:10px;padding:2rem;width:100%;max-width:420px;display:flex;
flex-direction:column;gap:1rem;border-top:4px solid var(--ouro)}
.aviso{font-size:.74rem;color:var(--tinta2);background:var(--papel);border-left:3px solid var(--ouro);
padding:.6rem .75rem;margin:0;line-height:1.45}
.galeria{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:1rem}
.foto{margin:0;display:flex;flex-direction:column;gap:.4rem}
.foto img{width:100%;height:200px;object-fit:cover;border:1px solid var(--linha);border-radius:8px;background:#eee;cursor:zoom-in}
.foto figcaption{font-size:.76rem;color:var(--tinta2);line-height:1.4}
.cartao-retrato{display:flex;flex-direction:column;align-items:center;text-align:center}
.retrato{width:100%;max-height:340px;object-fit:contain;border:1px solid var(--linha);border-radius:8px;background:#f6f5f1;cursor:zoom-in}
.v-svg{width:100%;height:auto;display:block}
.v-aresta{stroke:#cfc8ba;stroke-width:1.5}
.v-org{fill:var(--tinta);stroke:var(--ouro);stroke-width:2}
.v-orgnome{fill:#c9a85c;font-weight:700;font-size:14px;text-anchor:middle;letter-spacing:.06em}
.v-no{text-decoration:none;cursor:grab}
.v-no:active{cursor:grabbing}
.v-no circle{fill:#fff;stroke:var(--ouro);stroke-width:2.5}
.v-no:hover circle{fill:var(--ouro)}
.v-org-grupo{cursor:grab}
.v-org-grupo:active{cursor:grabbing}
.v-nome{fill:var(--tinta);font-size:12.5px;font-weight:600;text-anchor:middle}
.v-cargo{fill:var(--tinta2);font-size:11px;font-style:italic;text-anchor:middle}
.v-biqueira{fill:#8c2f2f;font-size:9.5px;text-anchor:middle}
.v-apagado{opacity:.45}
@media(prefers-reduced-motion:no-preference){.botao,.topo nav a,input,select,textarea{
transition:background .15s,border-color .15s,color .15s}}
@media(max-width:820px){.grade,.cartoes{grid-template-columns:1fr}.span2{grid-column:span 1}
.painel{grid-template-columns:1fr}.quem{margin-left:0;text-align:left}}
.cabecalho-relatorio{border-bottom:2px solid var(--ouro);margin-bottom:1.2rem;padding-bottom:.7rem;
display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;flex-wrap:wrap}
.cabecalho-relatorio .sigla{font-size:1.4rem}
.rodape-relatorio{margin-top:2rem;padding-top:.6rem;border-top:1px solid var(--linha);
font-size:.72rem;color:var(--tinta2);display:flex;justify-content:space-between;flex-wrap:wrap;gap:.4rem}
.marca-dagua{position:fixed;top:38%;left:8%;font-size:4.2rem;font-weight:700;color:rgba(140,47,47,.13);
transform:rotate(-28deg);z-index:0;pointer-events:none;letter-spacing:.1em}
.timeline{list-style:none;padding:0;margin:0;border-left:2px solid var(--linha)}
.timeline li{position:relative;padding:.15rem 0 1.1rem 1.3rem}
.timeline li::before{content:"";position:absolute;left:-6px;top:.3rem;width:10px;height:10px;
border-radius:50%;background:var(--ouro);border:2px solid #fff;box-shadow:0 0 0 1px var(--linha)}
.timeline li.critico::before{background:var(--perigo)}
.timeline .quando{font-size:.72rem;color:var(--tinta2)}
.timeline .descr{font-size:.9rem;margin-top:.1rem}
@media print{
  .faixa,.topo,.acoes,form,.botao,.painel{display:none !important}
  body{background:#fff}
  .conteudo{max-width:none;padding:0}
  .cartao,table{border:1px solid #999;box-shadow:none;break-inside:avoid;background:#fff}
  a{color:inherit;text-decoration:none}
  .marca-dagua{display:block}
}
"""


# ----------------------------------------------------------------------------
# Colunas que a pessoa pode arrastar para reordenar
# ----------------------------------------------------------------------------
#
# Cada usuário tem seu jeito de ler a tabela: quem trabalha com organização
# criminosa quer "Organização" perto do nome; quem cuida de apreensões quer
# "Materiais". A ordem escolhida fica guardada no navegador daquele computador
# (localStorage), por tabela — não vai para o banco nem afeta outros usuários.

SCRIPT_COLUNAS_MOVEIS = """
<script>
window.ativarColunasMoveis = function(idTabela) {
  var tabela = document.getElementById(idTabela);
  if (!tabela || !tabela.tHead || !tabela.tHead.rows.length) return;
  var chave = 'sirio-colunas-' + idTabela;
  var cabecalho = tabela.tHead.rows[0];
  var total = cabecalho.cells.length;

  Array.prototype.forEach.call(cabecalho.cells, function(th, i) {
    th.dataset.colOriginal = String(i);
    th.setAttribute('draggable', 'true');
    th.title = (th.title ? th.title + ' — ' : '') + 'Arraste para mover esta coluna de lugar';
  });

  function faixas() {
    var lista = [];
    var grupo = tabela.querySelector('colgroup');
    if (grupo) lista.push(grupo);
    lista.push(cabecalho);
    Array.prototype.forEach.call(tabela.tBodies, function(corpo) {
      Array.prototype.forEach.call(corpo.rows, function(linha) { lista.push(linha); });
    });
    return lista;
  }

  function mover(de, para) {
    if (de === para) return;
    faixas().forEach(function(faixa) {
      var itens = Array.prototype.slice.call(faixa.children);
      if (itens.length !== total) return;   // linha fora do padrão: não mexe
      var alvo = itens[de];
      if (para > de) faixa.insertBefore(alvo, itens[para].nextSibling);
      else faixa.insertBefore(alvo, itens[para]);
    });
  }

  function ordemAtual() {
    return Array.prototype.map.call(cabecalho.cells, function(th) {
      return Number(th.dataset.colOriginal);
    });
  }

  function guardar() {
    try { localStorage.setItem(chave, JSON.stringify(ordemAtual())); } catch (e) {}
  }

  function aplicar(ordem) {
    if (!Array.isArray(ordem) || ordem.length !== total) return;
    ordem.forEach(function(original, destino) {
      var atual = ordemAtual().indexOf(original);
      if (atual !== -1) mover(atual, destino);
    });
  }

  try {
    var salva = JSON.parse(localStorage.getItem(chave) || 'null');
    if (salva) aplicar(salva);
  } catch (e) {}

  var arrastada = null;
  Array.prototype.forEach.call(cabecalho.cells, function(th) {
    th.addEventListener('dragstart', function(ev) {
      arrastada = th;
      th.classList.add('arrastando');
      ev.dataTransfer.effectAllowed = 'move';
      try { ev.dataTransfer.setData('text/plain', th.dataset.colOriginal); } catch (e) {}
    });
    th.addEventListener('dragend', function() {
      th.classList.remove('arrastando');
      Array.prototype.forEach.call(cabecalho.cells, function(c) { c.classList.remove('alvo-solta'); });
      arrastada = null;
    });
    th.addEventListener('dragover', function(ev) {
      if (!arrastada || arrastada === th) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'move';
      th.classList.add('alvo-solta');
    });
    th.addEventListener('dragleave', function() { th.classList.remove('alvo-solta'); });
    th.addEventListener('drop', function(ev) {
      ev.preventDefault();
      th.classList.remove('alvo-solta');
      if (!arrastada || arrastada === th) return;
      var celulas = Array.prototype.slice.call(cabecalho.cells);
      mover(celulas.indexOf(arrastada), celulas.indexOf(th));
      guardar();
    });
  });

  var botao = document.querySelector('[data-restaura-colunas="' + idTabela + '"]');
  if (botao) botao.addEventListener('click', function() {
    try { localStorage.removeItem(chave); } catch (e) {}
    var ordem = [];
    for (var i = 0; i < total; i++) ordem.push(i);
    aplicar(ordem);
  });
};
</script>
"""

FAIXA = ('<div class="faixa">USO RESTRITO — Informações sensíveis de investigação. '
         'Todo acesso é registrado e auditado. O usuário responde pelo uso indevido dos dados.</div>')


def pagina(titulo, corpo, usuario=None):
    topo = ""
    if usuario is not None:
        links = ('<a href="/">Registros</a><a href="/vinculos">Diagrama de vínculos</a>'
                 '<a href="/ocorrencias">Ocorrências</a><a href="/materiais">Materiais</a>'
                 '<a href="/mapa">Mapa</a><a href="/vd">Violência Doméstica</a>'
                 '<a href="/verificacoes">Verificação de denúncias</a>')
        if usuario["perfil"] in ("admin", "analista"):
            links += '<a href="/pessoas/nova">Novo cadastro</a>'
            if PDF_DISPONIVEL:
                links += '<a href="/importar">Importar BO</a>'
        if usuario["perfil"] == "admin":
            links += '<a href="/usuarios">Usuários</a><a href="/configuracoes">Configurações</a>'
        links += '<a href="/minha-senha">Alterar senha</a>'
        topo = f"""
        <header class="topo">
          <a class="sigla" href="/">SIRIO</a>
          <nav>{links}</nav>
          <div class="quem"><strong>{e(usuario["nome"])}</strong>{PERFIL_LABEL[usuario["perfil"]]}
            &nbsp;·&nbsp;<a href="/sair" style="color:#c9a85c">Encerrar sessão</a></div>
        </header>"""
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{e(titulo)} — SIRIO</title><style>{CSS}</style></head>
<body>{FAIXA}{topo}<main class="conteudo">{corpo}</main></body></html>"""


def selo_grau(grau):
    if not grau:
        return '<span class="selo s-vazio">Confiabilidade não informada</span>'
    cls = "s-baixa"
    if grau.startswith("Confirmada"):
        cls = "s-alta"
    elif "inteligência" in grau or "fonte humana" in grau:
        cls = "s-media"
    return f'<span class="selo {cls}">{e(grau)}</span>'


def pill_status(st):
    return f'<span class="pill p-{e(st)}">{e(STATUS_LABEL.get(st, st))}</span>'


def opcoes(lista, selecionado):
    out = ""
    for item in lista:
        valor, rotulo = item if isinstance(item, tuple) else (item, item)
        sel = " selected" if valor == (selecionado or "") else ""
        out += f'<option value="{e(valor)}"{sel}>{e(rotulo)}</option>'
    return out


def li_campo(rotulo, valor):
    return (f'<div class="li-campo"><span class="rot">{e(rotulo)}</span>'
            f'<span class="val">{e(valor) or "—"}</span></div>')
