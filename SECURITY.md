# Segurança e proteção de dados

O SIRIO trata **dados pessoais sensíveis de investigação criminal**. Este
documento reúne o que precisa ser observado por quem instala, usa ou contribui
com o projeto.

## O repositório não contém dados

Este repositório traz **apenas o código-fonte**. Ele nunca deve receber:

- o banco de dados (`sirio.db` ou qualquer arquivo `.db`);
- fotografias e anexos de pessoas ou de casos;
- backups, que contêm banco e fotos;
- certificados HTTPS, em especial a **chave privada** de um servidor;
- documentos com timbre oficial preenchidos ou em branco;
- prints de tela com dados reais.

O `.gitignore` já bloqueia esses itens. Antes do primeiro `git push`, confira
com `git status` e `git ls-files` o que está de fato sendo enviado.

Se algo sensível for enviado por engano, **apagar o arquivo num commit novo não
resolve**: o conteúdo continua no histórico. Nesse caso, o repositório precisa
ser reescrito (`git filter-repo`) ou apagado e recriado, e qualquer credencial
exposta precisa ser trocada.

## Modelo de documento

`modelos/comunicacao_servico.docx` é um **modelo em branco, sem timbre**. Cada
unidade deve abrir o arquivo no Word e substituir o cabeçalho pelo timbre
próprio. Modelos com brasão e identificação de unidade real **não devem ser
publicados** — um documento oficial em branco disponível publicamente facilita
falsificação.

## Como o sistema se protege

- **Acesso local.** Por padrão o servidor escuta apenas em `127.0.0.1`. O modo
  rede (`Iniciar SIRIO (Rede da Unidade).bat`) abre o acesso à rede local da
  unidade — nunca à internet.
- **HTTPS obrigatório.** O sistema não sobe sem certificado. Cada instalação
  gera o seu; certificados não são transferíveis entre computadores.
- **Senhas** guardadas com PBKDF2 e sal aleatório, nunca em texto puro.
- **Bloqueio por tentativas** após sucessivas falhas de login, por usuário e IP.
- **Proteção contra CSRF** em todas as operações de gravação.
- **Trilha de auditoria**: cada acesso, criação, alteração e exclusão fica
  registrado com usuário, data e hora.
- **Perfis de acesso**: consulta, analista e administrador.

## Responsabilidade de quem usa

O SIRIO é uma ferramenta de apoio. Ele não substitui os sistemas oficiais nem a
decisão da autoridade policial. Use somente em equipamento funcional, com
autorização da chefia da unidade, observando a legislação aplicável — inclusive
a Lei Geral de Proteção de Dados e as normas do órgão.

**Nunca insira dados reais em testes, demonstrações ou capturas de tela.**

## Como comunicar uma falha de segurança

Falhas de segurança **não devem ser abertas como issue pública**. Use o canal
privado de comunicação de vulnerabilidades do GitHub (aba *Security* →
*Report a vulnerability*) descrevendo o problema, como reproduzi-lo e o impacto
possível. Não inclua dados reais no relato.
