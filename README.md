# SIRIO

**Sistema Interno de Registro de Investigados e Organizações** — versão 4.0

Ferramenta de apoio ao trabalho de investigação em unidade de polícia
judiciária. Roda no próprio computador da unidade, sem internet e sem
depender de servidor externo: um duplo clique liga o sistema e abre o
navegador.

> **USO RESTRITO.** O SIRIO trata dados pessoais sensíveis de investigação.
> Leia o [SECURITY.md](SECURITY.md) antes de instalar. Nunca insira dados reais
> em testes ou demonstrações.

## O que ele faz

| Módulo | Para quê |
|---|---|
| **Registros** | Cadastro de pessoas: qualificação, filiação, vínculo criminal, situação prisional, fonte e confiabilidade da informação, endereço e fotografias. Busca em todo o cadastro, ignorando acentos. |
| **Diagrama de vínculos** | Desenha a organização e as ligações entre as pessoas cadastradas, com posicionamento salvo. |
| **Ocorrências** | Local do fato, autor, vítima e testemunhas, cada um com endereço e coordenadas. |
| **Materiais apreendidos** | Objeto, quantidade, lacre, situação e vínculo com ocorrência e pessoa. |
| **Mapa** | Plota fatos, residências e denúncias em apuração; filtra por crime, origem e autor; mancha de calor e correlação entre a casa do autor e os locais dos fatos. |
| **Violência Doméstica** | Registro e acompanhamento de casos, dados protetivos da mulher e do autor, medidas protetivas e descumprimentos, encaminhamentos à rede, diligências e avaliação profissional. O sistema **não** calcula pontuação de risco — a conclusão é sempre do profissional. |
| **Verificação de denúncias** | Denúncias recebidas (Disque 100, WhatsApp, presencial, ofício), relatório de averiguação inicial, registro do boletim de ocorrência e **geração da Comunicação de Serviço em Word**. |
| **Importar BO** | Lê um boletim de ocorrência em PDF e sugere o cadastro dos envolvidos (recurso opcional). |

Além disso: perfis de acesso, trilha de auditoria, listas configuráveis pelo
administrador, importação e exportação em CSV, backup em um clique e mesclagem
de registros duplicados.

## Instalação

**Requisito:** Python 3.10 ou mais novo, com a opção *Add Python to PATH*
marcada na instalação. Nada além disso — o sistema usa apenas a biblioteca
padrão.

1. Baixe ou clone este repositório para uma pasta do computador da unidade.
2. Dê dois cliques em **`Gerar Certificado HTTPS.bat`**. O sistema não sobe sem
   certificado, e cada computador precisa gerar o seu.
3. Dê dois cliques em **`Iniciar SIRIO.bat`**. O navegador abre em
   `https://localhost:8377`.
4. Na primeira vez, o sistema pede a criação do usuário administrador.
5. Abra `modelos/comunicacao_servico.docx` no Word e **substitua o cabeçalho
   pelo timbre da sua unidade** — o modelo vem em branco de propósito.

O aviso de certificado no navegador é esperado: o certificado é gerado
localmente, para uso interno. O LEIA-ME explica como instalá-lo nas máquinas da
rede da unidade.

### Recurso opcional

`Ativar Importacao de BO.bat` instala a biblioteca de leitura de PDF necessária
para o módulo *Importar BO*. Sem ela, o resto do sistema funciona normalmente.

## Arquivos úteis

| Arquivo | Para quê |
|---|---|
| `Iniciar SIRIO.bat` | Liga o sistema neste computador |
| `Iniciar SIRIO (Rede da Unidade).bat` | Liga permitindo acesso pelos computadores da rede local |
| `Fazer Backup.bat` | Cópia de segurança do banco, das fotos e do certificado |
| `Resetar Senha.bat` | Emergência: redefine a senha de um usuário |
| `Preparar Pacote para Outra Unidade.bat` | Monta uma cópia limpa, sem dados, para entregar a outra unidade |

## Documentação

- **[LEIA-ME.txt](LEIA-ME.txt)** — manual de operação completo, em linguagem
  direta, seção por seção.
- **[SECURITY.md](SECURITY.md)** — proteção de dados, o que nunca versionar e
  como comunicar uma falha.
- `gerar_documentacao.py` e `gerar_manual_rede.py` geram os manuais em Word e
  PDF na pasta `Documentacao/`. Esses arquivos não são versionados: são
  resultado, não fonte.

## Como o código está organizado

Python puro, sem framework: um servidor HTTP da biblioteca padrão, SQLite como
banco e HTML gerado no servidor. Não há build, não há dependência a instalar.

```
sirio.py              servidor e rotas
sirio_core.py         infraestrutura compartilhada: banco, sessões,
                      validação, CSS e trechos de JavaScript reaproveitados
sirio_pessoas.py      Registros, fotos e mesclagem
sirio_ocorrencias.py  Ocorrências
sirio_materiais.py    Materiais apreendidos
sirio_mapa.py         Mapa
sirio_vinculos.py     Diagrama de vínculos
sirio_verificacoes.py Verificação de denúncias e geração do Word
sirio_vd_*.py         Violência Doméstica (casos, FONAR, protetivas,
                      gestão e painéis)
sirio_importar.py     Importação de boletim de ocorrência em PDF
sirio_usuarios.py     Usuários e senhas
sirio_config.py       Configurações do administrador
```

As tabelas são criadas na inicialização e as colunas novas entram por migração
automática — bancos antigos são atualizados sem perder nada.

## Licença

[MIT](LICENSE). Copyright © 2026 Tayana Borges de Lima. Veja o
[NOTICE.md](NOTICE.md).
