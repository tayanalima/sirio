"""Gera o Manual de instalação e acesso em rede do SIRIO.

Reaproveita as funções de estilo de gerar_documentacao.py para que o
documento saia visualmente idêntico aos demais manuais do sistema.
"""
from datetime import date

from docx import Document
from docx.shared import Inches, Pt

from gerar_documentacao import SAIDA, configurar, titulo, metadata, paragrafo, lista, fonte


PORTA = "8377"


def h1(doc, texto):
    doc.add_paragraph(texto, style="Heading 1")


def h2(doc, texto):
    doc.add_paragraph(texto, style="Heading 2")


def passos(doc, itens):
    """Lista numerada com o número escrito no próprio texto.

    O estilo "List Number" do Word continua a contagem ao longo de todo o
    documento, o que fazia a lista da seção 6 começar em 7. Numerando à mão,
    cada seção recomeça do 1.
    """
    for i, item in enumerate(itens, start=1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Inches(0.3)
        pf.first_line_indent = Inches(-0.3)
        pf.space_after = Pt(4)
        pf.line_spacing = 1.25
        # A tabulação leva o texto até a margem do recuo, para que a segunda
        # linha do item fique alinhada com a primeira e não com o número.
        pf.tab_stops.add_tab_stop(Inches(0.3))
        fonte(p.add_run(f"{i}.\t"), negrito=True)
        fonte(p.add_run(item))


def manual_rede():
    doc = Document()
    configurar(doc, "Instalação em rede")
    titulo(doc, "SIRIO", "Manual de instalação e acesso em rede")
    metadata(doc, [
        ("Assunto", "Computador principal, certificado HTTPS e computadores clientes"),
        ("Versão", "2.0"),
        ("Data", date.today().strftime("%d/%m/%Y")),
        ("Requisito", "Python 3.10 ou mais novo"),
        ("Endereço", f"https://<IP-do-principal>:{PORTA}"),
    ])

    # ------------------------------------------------------------------ 1
    h1(doc, "1. Como a instalação em rede funciona")
    paragrafo(doc,
        "O SIRIO guarda o banco de dados e as fotos no computador onde está instalado. "
        "Em rede, esse equipamento passa a ser o computador principal (servidor). Os demais "
        "computadores apenas abrem o navegador e acessam o endereço HTTPS desse computador.")
    paragrafo(doc,
        "Os computadores clientes não recebem o SIRIO. Não instalam Python, não recebem a "
        "pasta do sistema e não executam nenhum arquivo .bat. Eles precisam apenas de um "
        "navegador atualizado e do certificado instalado uma única vez.",
        destaque="Os computadores clientes não recebem o SIRIO.")

    h2(doc, "1.1. Três coisas que não são transferíveis")
    paragrafo(doc, "Entender isto evita a maior parte dos problemas de instalação:")
    lista(doc, [
        "O certificado HTTPS vale para o nome e o endereço IP de um computador específico. "
        "Não funciona em outro computador nem depois que o IP muda.",
        "A chave privada (certificados\\sirio-chave-privada.pem) nunca sai do computador "
        "principal. Copiá-la para outro lugar compromete a segurança da conexão.",
        "O banco de dados (sirio.db) pertence à unidade que o criou. Não se copia banco de "
        "uma unidade para outra: cada instalação começa vazia e cria o próprio administrador.",
    ])

    # ------------------------------------------------------------------ 2
    h1(doc, "2. Antes de iniciar")
    h2(doc, "2.1. Escolha o computador principal")
    lista(doc, [
        "Escolha um computador que fique disponível durante o expediente, tenha acesso à rede "
        "da unidade e não seja desligado enquanto outras pessoas estiverem usando o SIRIO.",
        "Instale a pasta completa do SIRIO apenas nesse computador.",
        "Use uma pasta permanente, por exemplo C:\\SIRIO. Não mova a pasta depois de começar "
        "a usar o sistema.",
        "Confirme que há espaço em disco para banco de dados, fotos e backups.",
        "Se houver registros em outra cópia do SIRIO, não apague nem copie o arquivo sirio.db "
        "por cima. Faça backup e peça orientação antes de consolidar dados.",
    ])

    h2(doc, "2.2. Peça um IP fixo antes de começar")
    paragrafo(doc,
        "Este passo economiza muito retrabalho. O certificado HTTPS é criado para o IP que o "
        "computador principal tem no momento da geração. Se a rede entregar outro IP depois de "
        "um reinício, todos os clientes voltam a mostrar aviso de segurança e o certificado "
        "precisa ser gerado e reinstalado em cada máquina.",
        destaque="Este passo economiza muito retrabalho.")
    paragrafo(doc,
        "Solicite à equipe de TI uma reserva de DHCP ou um IP fixo para o computador principal, "
        "e só então gere o certificado.")

    # ------------------------------------------------------------------ 3
    h1(doc, "3. Preparar o computador principal")
    passos(doc, [
        "Instale o Python. Baixe em python.org/downloads e, durante a instalação, marque a "
        "opção Add Python to PATH. O SIRIO exige a versão 3.10 ou mais nova; se o computador "
        "tiver uma versão antiga, o sistema avisa na tela ao abrir e não roda.",
        "Coloque a pasta do SIRIO no local definitivo. Mantenha todos os arquivos juntos, "
        "inclusive as pastas fotos, Icones e Documentacao.",
        "Faça um backup inicial. Execute Fazer Backup.bat e guarde a cópia em local seguro.",
        "Crie o certificado HTTPS. Execute Gerar Certificado HTTPS.bat uma única vez neste "
        "computador. É necessária conexão com a internet apenas nesta etapa, para instalar o "
        "componente de geração.",
        "Libere a porta no firewall. Veja a seção 4.",
        "Inicie em modo rede. Execute Iniciar SIRIO (Rede da Unidade).bat. A janela preta "
        "informa o endereço de acesso e deve permanecer aberta enquanto o sistema estiver em uso.",
    ])
    paragrafo(doc,
        "Atenção: Iniciar SIRIO.bat (sem “Rede da Unidade”) abre o sistema apenas para o "
        "próprio computador. Os clientes não conseguem acessar por ele.",
        destaque="Atenção:")

    # ------------------------------------------------------------------ 4
    h1(doc, "4. Liberar a porta no firewall do Windows")
    paragrafo(doc,
        "Na primeira execução em modo rede, o Windows normalmente pergunta se deseja permitir "
        "o Python na rede. Marque apenas Redes privadas e confirme.")
    paragrafo(doc,
        "Se a pergunta não aparecer, ou se ela foi recusada por engano, a liberação precisa ser "
        "feita manualmente. Abra o Prompt de Comando como administrador no computador principal "
        "e execute o comando abaixo, em uma única linha:")
    paragrafo(doc,
        f'netsh advfirewall firewall add rule name="SIRIO" dir=in action=allow '
        f'protocol=TCP localport={PORTA} profile=private')
    paragrafo(doc,
        "O comando libera a porta apenas no perfil de rede privada. Nunca libere no perfil "
        "público.")

    # ------------------------------------------------------------------ 5
    h1(doc, "5. Identificar e anotar o endereço do servidor")
    paragrafo(doc,
        "Ao iniciar em modo rede, anote o endereço exibido na janela preta. Ele tem este formato:")
    paragrafo(doc, f"https://192.168.1.25:{PORTA}")
    lista(doc, [
        f"O número 192.168.1.25 é somente um exemplo. Use exatamente o endereço mostrado no seu "
        f"computador principal. A porta, no entanto, é sempre {PORTA}.",
        "Se precisar identificar o IP manualmente, abra o Prompt de Comando, digite ipconfig e "
        "procure por Endereço IPv4 do adaptador conectado à rede.",
        f"Digite o endereço completo no navegador do cliente, incluindo https:// e :{PORTA}.",
        "Se o endereço mudar, releia a seção 7: o certificado também precisa ser refeito.",
    ])

    # ------------------------------------------------------------------ 6
    h1(doc, "6. Instalar o certificado nos computadores clientes")
    paragrafo(doc,
        "O certificado permite que o navegador reconheça a conexão HTTPS interna do SIRIO. Ele "
        "precisa ser instalado uma única vez em cada computador cliente.")
    passos(doc, [
        "Localize o certificado no principal. Abra a pasta do SIRIO e procure por "
        "certificados\\sirio-certificado.cer.",
        "Copie apenas esse arquivo para o cliente. Use pasta de rede, pen drive autorizado ou "
        "outro meio seguro. Nunca copie sirio-chave-privada.pem, e não é necessário copiar a "
        "pasta do SIRIO.",
        "Abra o arquivo no cliente. Dê dois cliques em sirio-certificado.cer e selecione "
        "Instalar Certificado.",
        "Escolha o local correto. Quando solicitado, escolha Computador Local. O Windows vai "
        "pedir permissão de administrador; informe a credencial autorizada ou chame a TI.",
        "Escolha o repositório. Selecione Colocar todos os certificados no repositório a seguir "
        "e escolha Autoridades de Certificação Raiz Confiáveis.",
        "Conclua e reinicie o navegador. Finalize o assistente, feche todas as janelas do "
        "navegador e abra novamente antes de acessar o SIRIO.",
    ])

    h2(doc, "6.1. Se a unidade usa Firefox")
    paragrafo(doc,
        "O Firefox não usa o repositório de certificados do Windows. Instalar o certificado "
        "como descrito acima não resolve para ele. No Firefox, acesse Configurações, procure por "
        "Certificados, clique em Ver certificados, aba Autoridades, e use Importar para "
        "selecionar o arquivo sirio-certificado.cer. Marque a opção de confiar para "
        "identificar sites.",
        destaque="O Firefox não usa o repositório de certificados do Windows.")
    paragrafo(doc,
        "Chrome e Edge usam o repositório do Windows e funcionam com o procedimento da seção 6.")

    # ------------------------------------------------------------------ 7
    h1(doc, "7. Quando o certificado precisa ser refeito")
    paragrafo(doc, "Gere um novo certificado somente quando:")
    lista(doc, [
        "o nome do computador principal mudou;",
        "o endereço IP do computador principal mudou;",
        "o SIRIO passou a rodar em outro computador;",
        "o certificado venceu — a validade é de três anos.",
    ])
    paragrafo(doc,
        "Execute Gerar Certificado HTTPS.bat novamente. Como já existe um certificado, ele "
        "pergunta se deve substituir; responda S. Uma cópia do certificado antigo é guardada "
        "automaticamente em certificados\\anterior_<data>.")
    paragrafo(doc,
        "Depois de gerar, o arquivo sirio-certificado.cer precisa ser instalado novamente em "
        "cada computador cliente. Enquanto isso não for feito, os clientes voltam a mostrar "
        "aviso de segurança. O certificado antigo deixa de valer no momento em que o novo é "
        "gerado.",
        destaque="precisa ser instalado novamente em cada computador cliente")

    # ------------------------------------------------------------------ 8
    h1(doc, "8. Acessar o SIRIO nos computadores clientes")
    passos(doc, [
        "Abra um navegador atualizado.",
        f"Digite o endereço do principal. Exemplo: https://192.168.1.25:{PORTA}. Não abra "
        "nenhum arquivo .bat do SIRIO no computador cliente.",
        "Faça login. Cada pessoa deve usar o próprio login e senha. Não compartilhe credenciais.",
        "Teste um registro. Crie ou consulte um registro de teste e confirme, no computador "
        "principal, que a mesma informação aparece. Use apenas dados fictícios no teste e "
        "remova o registro depois.",
    ])

    # ------------------------------------------------------------------ 9
    h1(doc, "9. Entregar o SIRIO a outra unidade")
    paragrafo(doc,
        "Nunca copie a pasta do SIRIO em uso para outra unidade. Ela contém o banco com "
        "registros reais, as fotografias cadastradas, os backups e a chave privada do HTTPS "
        "deste servidor.",
        destaque="Nunca copie a pasta do SIRIO em uso para outra unidade.")
    paragrafo(doc,
        "Execute Preparar Pacote para Outra Unidade.bat. Ele cria, ao lado da pasta do SIRIO, "
        "um arquivo SIRIO_para_distribuir_<data>.zip contendo apenas o programa e a "
        "documentação. Ao final, o próprio script confere o pacote e avisa se algo sensível "
        "escapou.")
    paragrafo(doc,
        "O pacote é um arquivo .zip de propósito. Uma pasta solta ao lado da instalação em uso "
        "teria atalhos com exatamente os mesmos nomes — Resetar Senha.bat, Iniciar SIRIO.bat — "
        "e é fácil executar o da pasta errada sem perceber, alterando a instalação que não se "
        "queria mexer.",
        destaque="O pacote é um arquivo .zip de propósito.")
    paragrafo(doc, "Ficam de fora do pacote, por segurança:")
    lista(doc, [
        "sirio.db — banco com registros reais;",
        "fotos\\ — fotografias e tatuagens cadastradas;",
        "backups\\ — cópias do banco e das fotos;",
        "certificados\\ — inclui a chave privada deste servidor;",
        "__pycache__\\ — arquivos temporários do Python.",
    ])
    paragrafo(doc, "A unidade que recebe o pacote executa, na ordem:")
    passos(doc, [
        "instala o Python 3.10 ou mais novo, marcando Add Python to PATH;",
        "coloca a pasta no local definitivo;",
        "solicita IP fixo à TI;",
        "executa Gerar Certificado HTTPS.bat no computador principal dela;",
        "libera a porta no firewall;",
        "executa Iniciar SIRIO (Rede da Unidade).bat e cria o próprio administrador;",
        "instala o certificado nos clientes dela, conforme a seção 6.",
    ])
    paragrafo(doc,
        "Cada unidade fica com banco, usuários e certificado próprios. Os dados de uma unidade "
        "não aparecem na outra.")

    # ----------------------------------------------------------------- 10
    h1(doc, "10. Operação segura e backups")
    lista(doc, [
        "Use o backup pelo menu Configurações ou execute Fazer Backup.bat regularmente no "
        "computador principal.",
        "Guarde cópias de backup fora do computador principal, em mídia aprovada e protegida. A "
        "pasta backups\\ contém dados sensíveis e fotografias: proteja-a com o mesmo cuidado do "
        "banco de dados.",
        "Não exponha o endereço do SIRIO à internet. O uso previsto é exclusivamente na "
        "intranet autorizada. Redirecionamento de porta no roteador e túneis estão proibidos.",
        "Mantenha o computador principal protegido por senha, antivírus e atualizações do "
        "Windows conforme as regras da unidade.",
        "Ao trocar a senha, use a opção Alterar senha dentro do SIRIO. Em caso de esquecimento, "
        "use Resetar Senha.bat no computador principal.",
        "A trilha de auditoria de cada registro é visível somente ao perfil Administrador.",
    ])

    # ----------------------------------------------------------------- 11
    h1(doc, "11. Solução de problemas")

    h2(doc, "O endereço não abre no cliente")
    paragrafo(doc,
        f"Confirme que a janela preta do SIRIO continua aberta no computador principal e que ele "
        f"foi iniciado por Iniciar SIRIO (Rede da Unidade).bat, não pelo atalho comum. Confira se "
        f"o endereço foi digitado completo, com https:// e :{PORTA}.")

    h2(doc, "O cliente vê aviso de segurança")
    paragrafo(doc,
        "O certificado não está instalado naquele computador, ou foi refeito no servidor e não "
        "reinstalado no cliente. Reveja as seções 6 e 7. Se a unidade usa Firefox, veja a "
        "seção 6.1.")

    h2(doc, "O aviso diz que o certificado é de outro endereço")
    paragrafo(doc,
        "O IP do computador principal mudou depois que o certificado foi criado. Gere um novo "
        "certificado (seção 7), reinstale nos clientes e peça um IP fixo à TI para não repetir.")

    h2(doc, "Funciona no principal, mas não no cliente")
    paragrafo(doc,
        "Os computadores podem estar em redes ou VLANs diferentes, ou o firewall do Windows está "
        "bloqueando a porta. Aplique a liberação da seção 4 e, se persistir, solicite à TI a "
        "liberação de acesso interno ao computador principal.")

    h2(doc, "Registros aparecem diferentes em cada computador")
    paragrafo(doc,
        "Provavelmente foi aberta outra cópia local do SIRIO em um cliente. Pare de usar a cópia "
        "do cliente e acesse somente o endereço do computador principal. Não substitua arquivos "
        "sirio.db sem backup e sem orientação.")

    h2(doc, "O gerador de certificado não faz nada")
    paragrafo(doc,
        "Se já existe certificado, o gerador pergunta antes de substituir. Responda S para "
        "confirmar. Se responder N, nada é alterado — o certificado atual continua valendo.")

    # ----------------------------------------------------------------- 12
    h1(doc, "12. Checklist final de implantação")
    lista(doc, [
        "Apenas uma cópia principal do SIRIO está em uso.",
        "O computador principal tem IP fixo ou reserva de DHCP.",
        "O Python instalado é 3.10 ou mais novo.",
        "O certificado foi gerado no computador principal, depois do IP fixo.",
        f"A porta {PORTA} está liberada no firewall, apenas no perfil de rede privada.",
        "O SIRIO está aberto por Iniciar SIRIO (Rede da Unidade).bat.",
        "O endereço HTTPS do principal foi anotado e testado.",
        "O certificado foi instalado em cada computador cliente autorizado.",
        "Nos clientes com Firefox, o certificado foi importado também no navegador.",
        "Cada cliente acessa pelo navegador, sem executar cópia local do SIRIO.",
        "A chave privada permanece somente no computador principal.",
        "Um backup foi criado e guardado em local seguro e protegido.",
    ])

    SAIDA.mkdir(exist_ok=True)
    caminho = SAIDA / "Manual_Instalacao_em_Rede_SIRIO.docx"
    doc.save(caminho)
    return caminho


if __name__ == "__main__":
    print("Manual gerado:", manual_rede())
