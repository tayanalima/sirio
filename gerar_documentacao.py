"""Gera os documentos de distribuição do SIRIO 4.0."""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "Documentacao"
AZUL = "2E74B5"
AZUL_ESCURO = "1F4D78"
CINZA = "555555"


def fonte(run, tamanho=11, cor="000000", negrito=False, italico=False):
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    run.font.size = Pt(tamanho)
    run.font.color.rgb = RGBColor.from_string(cor)
    run.bold, run.italic = negrito, italico


def borda_inferior(paragrafo, cor="D7DBE2"):
    p_pr = paragrafo._p.get_or_add_pPr()
    bordas = OxmlElement("w:pBdr")
    borda = OxmlElement("w:bottom")
    borda.set(qn("w:val"), "single")
    borda.set(qn("w:sz"), "8")
    borda.set(qn("w:space"), "6")
    borda.set(qn("w:color"), cor)
    bordas.append(borda)
    p_pr.append(bordas)


def configurar(doc, titulo_curto):
    secao = doc.sections[0]
    secao.top_margin = secao.bottom_margin = Inches(1)
    secao.left_margin = secao.right_margin = Inches(1)
    secao.header_distance = Inches(0.49)
    secao.footer_distance = Inches(0.49)

    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(11)
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25
    for nome, tamanho, cor, antes, depois in [
        ("Heading 1", 16, AZUL, 18, 10),
        ("Heading 2", 13, AZUL, 14, 7),
        ("Heading 3", 12, AZUL_ESCURO, 10, 5),
    ]:
        estilo = doc.styles[nome]
        estilo.font.name, estilo.font.size = "Calibri", Pt(tamanho)
        estilo.font.color.rgb = RGBColor.from_string(cor)
        estilo._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        estilo._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        estilo.paragraph_format.space_before = Pt(antes)
        estilo.paragraph_format.space_after = Pt(depois)

    cab = secao.header.paragraphs[0]
    cab.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = cab.add_run(f"SIRIO 4.0 | {titulo_curto}")
    fonte(r, 8.5, CINZA)
    borda_inferior(cab)
    rodape = secao.footer.paragraphs[0]
    rodape.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = rodape.add_run("SIRIO 4.0 | Tayana Borges de Lima | ")
    fonte(r, 8, CINZA)
    campo = OxmlElement("w:fldSimple")
    campo.set(qn("w:instr"), "PAGE")
    rodape._p.append(campo)


def titulo(doc, texto, subtitulo):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(22)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(texto)
    fonte(r, 26, AZUL_ESCURO, True)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(18)
    r = p.add_run(subtitulo)
    fonte(r, 12.5, CINZA, italico=True)
    borda_inferior(p, AZUL)


def metadata(doc, pares):
    tabela = doc.add_table(rows=len(pares), cols=2)
    tabela.alignment = WD_TABLE_ALIGNMENT.LEFT
    tabela.autofit = False
    for linha, (rotulo, valor) in zip(tabela.rows, pares):
        linha.cells[0].width, linha.cells[1].width = Inches(1.55), Inches(4.95)
        for celula in linha.cells:
            celula.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = linha.cells[0].paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        fonte(p.add_run(rotulo), 10, AZUL_ESCURO, True)
        p = linha.cells[1].paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        fonte(p.add_run(valor), 10)
    doc.add_paragraph()


def paragrafo(doc, texto, destaque=None):
    p = doc.add_paragraph()
    if destaque and destaque in texto:
        antes, depois = texto.split(destaque, 1)
        fonte(p.add_run(antes))
        fonte(p.add_run(destaque), negrito=True, cor=AZUL_ESCURO)
        fonte(p.add_run(depois))
    else:
        fonte(p.add_run(texto))
    return p


def lista(doc, itens, numerada=False):
    if numerada:
        return passos(doc, itens)
    for item in itens:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.25
        fonte(p.add_run(item))


def passos(doc, itens):
    """Lista numerada com o número escrito no próprio texto.

    O estilo "List Number" do Word continua a contagem ao longo de todo o
    documento: a segunda lista do manual começava em 6, e a terceira em 10.
    Numerando à mão, cada seção recomeça do 1.
    """
    for i, item in enumerate(itens, start=1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Inches(0.3)
        pf.first_line_indent = Inches(-0.3)
        pf.space_after = Pt(4)
        pf.line_spacing = 1.25
        pf.tab_stops.add_tab_stop(Inches(0.3))
        fonte(p.add_run(f"{i}.\t"), negrito=True)
        fonte(p.add_run(item))


# ----------------------------------------------------------------------------
# Conteúdo do Manual de utilização
# ----------------------------------------------------------------------------
#
# Definido em UM só lugar. O .docx e o .pdf são gerados a partir desta lista,
# porque antes o mesmo texto existia duplicado nas duas funções e os dois
# arquivos saíam diferentes com o tempo.
#
# Cada seção é (título, texto de abertura ou None, itens, numerada).

MANUAL_METADATA = [
    ("Versão", "4.0"),
    ("Autora", "Tayana Borges de Lima"),
    ("Contato", "tayanablima@gmail.com | (31) 99968-6006"),
    ("Licença", "MIT - consulte o arquivo LICENSE"),
    ("Requisito", "Python 3.10 ou mais novo"),
    ("Atualizado em", date.today().strftime("%d/%m/%Y")),
]

MANUAL_ABERTURA = ("Uso restrito. O SIRIO deve ser utilizado somente por pessoas autorizadas "
                   "e de acordo com as normas institucionais e a legislação aplicável.")

SECOES_MANUAL = [
    ("1. Primeira utilização", None, [
        "Instale o Python 3.10 ou mais novo, marcando Add Python to PATH. Se o computador tiver uma versão antiga, o SIRIO avisa na tela ao abrir e não roda.",
        "Mantenha todos os arquivos do pacote na mesma pasta.",
        "Execute Iniciar SIRIO.bat para uso apenas neste computador.",
        "Na primeira abertura, crie o usuário administrador e guarde a senha em local seguro.",
        "Para acesso pela rede da unidade, execute Gerar Certificado HTTPS.bat uma única vez no computador servidor e depois Iniciar SIRIO (Rede da Unidade).bat.",
        "Nos computadores clientes, instale o arquivo certificados\\sirio-certificado.cer como certificado raiz confiável antes do primeiro acesso HTTPS. O passo a passo completo está no Manual de instalação e acesso em rede.",
    ], True),

    ("2. Perfis de acesso", None, [
        "Consulta: visualiza registros, ocorrências, materiais e mapas. Não cadastra, edita nem exclui.",
        "Analista: tudo do Consulta, e ainda cadastra e edita registros, ocorrências, materiais e casos de Violência Doméstica.",
        "Administrador: tudo do Analista, e ainda administra usuários, configurações, backups e exclusões.",
        "A trilha de auditoria de cada registro é visível somente ao Administrador. Ela mostra quem consultou e quem alterou cada campo.",
    ], False),

    ("3. Usuários", "Somente o Administrador acessa a aba Usuários.", [
        "Para criar: preencha nome, login, senha e perfil.",
        "Para corrigir: os campos Nome, Login e Perfil da tabela Cadastrados são editáveis. Altere e clique em Salvar na própria linha. Não é preciso criar um segundo cadastro quando o perfil de alguém muda.",
        "Toda alteração fica registrada na auditoria, com o valor anterior e o novo.",
        "Ao mudar o perfil de alguém que está com o sistema aberto, a sessão dela é encerrada para que a nova permissão valha na hora.",
        "O sistema impede alterar o perfil ou desativar o último administrador ativo, para a unidade não ficar sem acesso administrativo.",
        "Para trocar a senha de outra pessoa, use Resetar Senha.bat no computador principal. A senha não é editável por esta tela.",
    ], True),

    ("4. Segurança de acesso", None, [
        "Após 5 tentativas de senha erradas seguidas, aquele login fica bloqueado por 15 minutos naquele computador.",
        "Tentativas fracassadas ficam registradas: na auditoria quando o login existe, e no arquivo registro_de_acesso.txt em todos os casos, com data, login tentado e origem.",
        "A sessão encerra sozinha após 30 minutos sem uso, e sempre após 12 horas. Isso protege computador compartilhado da unidade.",
        "Desativar um usuário derruba na hora as sessões abertas em nome dele.",
        "Nunca compartilhe login ou senha. Cada pessoa responde pelo que é feito com o seu acesso.",
    ], False),

    ("5. Cadastro de pessoas", None, [
        "Abra a aba Registros e selecione Novo cadastro.",
        "Preencha a identificação e os dados investigativos disponíveis; evite informações sem fonte ou sem indicação de confiabilidade.",
        "O sistema recusa data inválida, data de nascimento no futuro e quantidade de filhos que não seja um número. Se aparecer mensagem em vermelho, corrija o campo indicado.",
        "Anexe fotografias somente quando houver autorização e pertinência operacional.",
        "Use o status do registro para preservar histórico sem apagar informações necessárias. Arquivar é quase sempre melhor do que excluir.",
    ], True),

    ("6. Excluir um registro de pessoa", "Somente o Administrador pode excluir, e a ação não pode ser desfeita.", [
        "A exclusão apaga junto tudo que depende da pessoa: fotografias, inclusive os arquivos gravados na pasta fotos, biqueiras, vínculos com boletins, posição no diagrama de vínculos e os dados dela em casos de Violência Doméstica, incluindo FONAR e ficha específica.",
        "Materiais apreendidos não são apagados: são prova ligada a uma ocorrência. Eles apenas deixam de apontar para a pessoa.",
        "A trilha de auditoria é preservada de propósito, com o nome da pessoa registrado no momento da exclusão.",
        "Prefira Arquivar quando o objetivo for apenas tirar o registro de circulação.",
    ], False),

    ("7. Ocorrências, coordenadas e mapa", None, [
        "Cadastre o local do fato, autor, vítima e testemunhas conforme as informações disponíveis.",
        "Use Localizar coordenadas pelo endereço. A busca sugere locais semelhantes; confira a opção antes de salvar.",
        "Coordenada fora do intervalo válido é recusada, para não quebrar o mapa.",
        "A aba Mapa mostra apenas pontos que possuam latitude e longitude cadastradas.",
        "O diagrama de vínculos permite visualizar organizações e também vítimas por autor, com base nas ocorrências existentes no SIRIO.",
    ], True),

    ("8. Violência Doméstica: caso cadastrado por engano",
     "Na tela do caso existem duas opções, e elas servem para coisas diferentes.", [
        "Cancelar cadastro (Analista e Administrador): para caso criado errado — duplicado, teste, dados trocados, REDS incorreto. O sistema pede o motivo. O caso sai das listagens e deixa de contar nos painéis, mas nada é apagado: para trazer de volta, basta alterar a situação.",
        "Excluir (somente Administrador): apaga o caso e tudo que depende dele — relato da mulher, ficha específica, FONAR e respostas, avaliações profissionais, medidas protetivas com itens e descumprimentos, diligências, encaminhamentos, acompanhamentos, anexos e linha do tempo. Não pode ser desfeito e fica registrado na auditoria.",
        "Na dúvida, cancele. Cancelar resolve o problema da tela sem perder nada, e a exclusão continua disponível depois.",
        "Cancelado não é a mesma coisa que Encerrado. Encerrado é desfecho de caso real e continua nas estatísticas; Cancelado é registro que nunca deveria ter existido, e fica fora delas.",
    ], False),

    ("9. Importação e dados", None, [
        "Importe BO/REDS ou CSV apenas após revisar o conteúdo extraído.",
        "Antes de confirmar, valide nomes, datas, endereços e vínculos sugeridos.",
        "O sistema pode identificar possíveis cadastros existentes; confira antes de criar registros duplicados.",
    ], False),

    ("10. Backup", None, [
        "Faça backup regular pelo menu Configurações ou por Fazer Backup.bat.",
        "O backup contém o banco de dados e a pasta de fotos. A cópia do banco usa o mecanismo do próprio SQLite, então sai íntegra mesmo com o sistema aberto e em uso.",
        "A pasta certificados não entra no backup: ela contém a chave privada do HTTPS, que não deve sair do computador principal. Se o certificado se perder, gere outro com Gerar Certificado HTTPS.bat.",
        "O backup contém dados sensíveis de investigação e as fotografias cadastradas. Proteja a pasta backups e as mídias com o mesmo cuidado que o banco de dados.",
        "Guarde uma cópia fora do computador principal, em mídia aprovada.",
    ], False),

    ("11. Segurança geral", None, [
        "Não exponha o SIRIO à internet. O uso em rede é destinado apenas à rede interna autorizada.",
        "Nunca compartilhe logins, senhas ou a chave privada do certificado HTTPS.",
        "Bloqueie a sessão do Windows ao se ausentar e mantenha o disco do servidor criptografado quando possível.",
        "Nunca insira dados reais em testes ou demonstrações.",
        "Para entregar o SIRIO a outra unidade, use Preparar Pacote para Outra Unidade.bat. Ele monta um arquivo .zip sem banco, sem fotos, sem backups e sem a chave privada. Nunca copie a pasta em uso.",
    ], False),

    ("12. Suporte e observações",
     "Para suporte, dúvidas ou adaptações, entre em contato com Tayana Borges de Lima: "
     "tayanablima@gmail.com | (31) 99968-6006. Este manual complementa o arquivo LEIA-ME.txt "
     "e o Manual de instalação e acesso em rede, ambos fornecidos com o sistema.", [], False),
]


def manual():
    doc = Document()
    configurar(doc, "Manual de utilização")
    titulo(doc, "Manual de utilização", "Sistema Interno de Registro de Investigados e Organizações")
    metadata(doc, MANUAL_METADATA)
    paragrafo(doc, MANUAL_ABERTURA, "Uso restrito.")
    for cabecalho, texto, itens, numerada in SECOES_MANUAL:
        doc.add_heading(cabecalho, level=1)
        if texto:
            paragrafo(doc, texto)
        if itens:
            lista(doc, itens, numerada=numerada)
    return doc


def declaracao_ia():
    doc = Document()
    configurar(doc, "Declaração de uso de IA")
    titulo(doc, "Declaração de uso de IA", "Transparência sobre ferramentas de apoio ao desenvolvimento do SIRIO 4.0")
    metadata(doc, [
        ("Sistema", "SIRIO - versão 4.0"),
        ("Responsável", "Tayana Borges de Lima"),
        ("Contato", "tayanablima@gmail.com | (31) 99968-6006"),
        ("Data", date.today().strftime("%d/%m/%Y")),
    ])
    paragrafo(doc, "Esta declaração informa, de forma transparente, o uso de ferramentas de inteligência artificial generativa como apoio durante o desenvolvimento do SIRIO.")
    doc.add_heading("1. Ferramentas utilizadas", level=1)
    lista(doc, [
        "ChatGPT, da OpenAI.",
        "Claude, da Anthropic.",
    ])
    doc.add_heading("2. Finalidade do uso", level=1)
    paragrafo(doc, "As ferramentas foram utilizadas como apoio à elaboração, análise e revisão de código, sugestões de estrutura, documentação, testes e melhoria de textos. O uso de IA não substituiu a análise, as decisões técnicas, a validação ou a responsabilidade da autora.")
    doc.add_heading("3. Responsabilidade humana", level=1)
    lista(doc, [
        "A autora revisa e valida as alterações incorporadas ao projeto.",
        "A autora é responsável pelas decisões de arquitetura, segurança, operação e distribuição do software.",
        "As ferramentas de IA não são autoras, titulares de direitos autorais nem responsáveis pelo uso do SIRIO.",
        "A operação do sistema deve observar as normas institucionais, a legislação aplicável e a proteção de dados pessoais e sensíveis.",
    ])
    doc.add_heading("4. Proteção de informações", level=1)
    paragrafo(doc, "Dados reais, sigilosos ou sensíveis não devem ser enviados a serviços de IA sem autorização formal, fundamento legal e avaliação institucional de segurança. Em testes e demonstrações, devem ser utilizados dados fictícios ou adequadamente anonimizados.")
    doc.add_heading("5. Licença e autoria", level=1)
    paragrafo(doc, "O SIRIO é distribuído sob a Licença MIT. A autoria declarada do projeto é de Tayana Borges de Lima. A presente declaração busca registrar com clareza o uso de IA como ferramenta de apoio, preservando a responsabilidade e a autoria humana sobre o projeto.")
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(26)
    fonte(p.add_run("Tayana Borges de Lima"), 11, AZUL_ESCURO, True)
    p = doc.add_paragraph()
    fonte(p.add_run("Autora e responsável pelo projeto"), 10, CINZA)
    return doc


def estilos_pdf():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Title"], fontName="Helvetica-Bold", fontSize=24,
            leading=29, textColor=colors.HexColor("#1F4D78"), spaceAfter=6),
        "subtitulo": ParagraphStyle("subtitulo", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=12,
            leading=16, textColor=colors.HexColor("#555555"), spaceAfter=16),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16,
            leading=20, textColor=colors.HexColor("#2E74B5"), spaceBefore=16, spaceAfter=8),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=10.5,
            leading=14, spaceAfter=6),
        "meta": ParagraphStyle("meta", parent=base["BodyText"], fontName="Helvetica", fontSize=9.5,
            leading=13, spaceAfter=0),
        "footer": ParagraphStyle("footer", parent=base["Normal"], alignment=TA_CENTER,
            fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#555555")),
    }


def cabecalho_rodape(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D7DBE2"))
    canvas.line(doc.leftMargin, letter[1] - 0.62 * inch, letter[0] - doc.rightMargin, letter[1] - 0.62 * inch)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(letter[0] - doc.rightMargin, letter[1] - 0.48 * inch, "SIRIO 4.0")
    canvas.drawCentredString(letter[0] / 2, 0.48 * inch, f"SIRIO 4.0 | Tayana Borges de Lima | Página {doc.page}")
    canvas.restoreState()


def lista_pdf(itens, estilos, numerada=False):
    estilo = ParagraphStyle("lista", parent=estilos["body"], leftIndent=20, firstLineIndent=-11,
        bulletIndent=0, spaceAfter=4)
    # Antes o parâmetro era ignorado: o .docx saía numerado e o .pdf com
    # marcadores, para o mesmo conteúdo.
    if numerada:
        return [Paragraph(item, estilo, bulletText=f"{i}.")
                for i, item in enumerate(itens, start=1)]
    return [Paragraph(item, estilo, bulletText="•") for item in itens]


def pdf_documento(nome, titulo_texto, subtitulo, metadados, secoes, assinatura=None, usar_tabela_metadata=True):
    estilos = estilos_pdf()
    arquivo = SAIDA / nome
    doc = SimpleDocTemplate(str(arquivo), pagesize=letter, leftMargin=inch, rightMargin=inch,
        topMargin=0.86 * inch, bottomMargin=0.78 * inch)
    historia = [Paragraph(titulo_texto, estilos["titulo"]), Paragraph(subtitulo, estilos["subtitulo"])]
    if usar_tabela_metadata:
        dados = [[Paragraph(f"<b>{k}</b>", estilos["meta"]), Paragraph(v, estilos["meta"])] for k, v in metadados]
        tabela = Table(dados, colWidths=[1.55 * inch, 4.95 * inch])
        tabela.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DBE2")),
        ]))
        historia += [tabela, Spacer(1, 14)]
    else:
        for rotulo, valor in metadados:
            historia.append(Paragraph(f"<b>{rotulo}:</b> {valor}", estilos["meta"]))
        historia.append(Spacer(1, 14))
    for cab, texto, itens, numerada in secoes:
        historia.append(Paragraph(cab, estilos["h1"]))
        if texto:
            historia.append(Paragraph(texto, estilos["body"]))
        if itens:
            historia.extend(lista_pdf(itens, estilos, numerada))
    if assinatura:
        historia += [Spacer(1, 20), Paragraph(f"<b>{assinatura[0]}</b>", estilos["body"]),
                     Paragraph(assinatura[1], estilos["meta"])]
    doc.build(historia, onFirstPage=cabecalho_rodape, onLaterPages=cabecalho_rodape)


def gerar_pdfs():
    hoje = date.today().strftime("%d/%m/%Y")
    # Mesmo conteúdo do .docx, vindo de SECOES_MANUAL — sem texto duplicado.
    pdf_documento("Manual_de_Utilizacao_SIRIO_4.0.pdf", "Manual de utilização",
        "Sistema Interno de Registro de Investigados e Organizações",
        MANUAL_METADATA,
        [("Uso restrito", MANUAL_ABERTURA, [], False)] + SECOES_MANUAL)
    pdf_documento("Declaracao_de_Uso_de_IA_SIRIO_4.0.pdf", "Declaração de uso de IA",
        "Transparência sobre ferramentas de apoio ao desenvolvimento do SIRIO 4.0", [
            ("Sistema", "SIRIO - versão 4.0"), ("Responsável", "Tayana Borges de Lima"),
            ("Contato", "tayanablima@gmail.com | (31) 99968-6006"), ("Data", hoje),
        ], [
            ("1. Ferramentas utilizadas", None, ["ChatGPT, da OpenAI.", "Claude, da Anthropic."], False),
            ("2. Finalidade do uso", "As ferramentas foram utilizadas como apoio à elaboração, análise e revisão de código, sugestões de estrutura, documentação, testes e melhoria de textos. O uso de IA não substituiu a análise, as decisões técnicas, a validação ou a responsabilidade da autora.", [], False),
            ("3. Responsabilidade humana", None, ["A autora revisa e valida as alterações incorporadas ao projeto.", "A autora é responsável pelas decisões de arquitetura, segurança, operação e distribuição do software.", "As ferramentas de IA não são autoras, titulares de direitos autorais nem responsáveis pelo uso do SIRIO.", "A operação do sistema deve observar as normas institucionais, a legislação aplicável e a proteção de dados pessoais e sensíveis."], False),
            ("4. Proteção de informações", "Dados reais, sigilosos ou sensíveis não devem ser enviados a serviços de IA sem autorização formal, fundamento legal e avaliação institucional de segurança. Em testes e demonstrações, devem ser utilizados dados fictícios ou adequadamente anonimizados.", [], False),
            ("5. Licença e autoria", "O SIRIO é distribuído sob a Licença MIT. A autoria declarada do projeto é de Tayana Borges de Lima. Esta declaração registra o uso de IA como ferramenta de apoio, preservando a responsabilidade e a autoria humana sobre o projeto.", [], False),
        ], usar_tabela_metadata=False)


def main():
    SAIDA.mkdir(exist_ok=True)
    manual().save(SAIDA / "Manual_de_Utilizacao_SIRIO_4.0.docx")
    declaracao_ia().save(SAIDA / "Declaracao_de_Uso_de_IA_SIRIO_4.0.docx")
    gerar_pdfs()
    print(f"Documentos criados em {SAIDA}")


if __name__ == "__main__":
    main()
