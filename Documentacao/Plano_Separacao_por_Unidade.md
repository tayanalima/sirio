# Plano — separação de dados por unidade

> **SITUAÇÃO: ARQUIVADO EM 17/08/2026. NÃO IMPLEMENTAR.**
>
> A ideia de servidor central foi descartada pela autora: rodar na intranet da
> Polícia Civil exigiria autorizações institucionais que não se justificam para
> o porte da ferramenta.
>
> O modelo adotado é **uma instalação independente por unidade**, cada uma na
> própria rede local. A separação de dados entre unidades passa a ser física —
> bancos diferentes, em computadores diferentes, em redes diferentes — e não
> depende de código nenhum.
>
> Este documento fica guardado apenas como registro da análise, caso a questão
> volte no futuro. Nada aqui deve ser implementado sem uma nova decisão.

**Data:** 17 de agosto de 2026
**Objetivo:** permitir servidor central atendendo várias unidades, com os dados de
cada unidade visíveis apenas a ela.
**Decisão adotada:** tudo restrito por unidade — tanto o cadastro de investigados
quanto os casos de Violência Doméstica.

---

## Por que não são 164 alterações

A varredura encontrou 164 consultas nas tabelas de dados. Alterar uma a uma seria
demorado e, pior, frágil: bastaria esquecer uma para abrir um vazamento silencioso.

A maior parte dessas tabelas é **filha** de outra. `vd_medidas_protetivas` pertence a
um `vd_caso`; `biqueiras` pertence a uma `pessoa`. Se o pai já está restrito, a filha
fica restrita junto — desde que ninguém consiga chegar nela por um caminho lateral.

O caminho lateral existe e é o ponto crítico: rotas como `/vd/medidas/<id>/editar`
recebem o id direto na URL. Sem verificação, alguém da unidade A digita um id qualquer
e alcança a medida protetiva da unidade B. Isso vale para todas as rotas que carregam
registro por id.

Por isso o desenho abaixo concentra a proteção em dois lugares, em vez de espalhá-la
por 164 consultas.

---

## Desenho

### 1. Unidade no cadastro de usuário

Nova coluna `usuarios.unidade`. Cada pessoa pertence a uma unidade. O campo passa a
ser obrigatório na criação e editável na tela de Usuários, que já existe.

### 2. Unidade nas quatro tabelas-raiz

| Tabela | Situação |
|---|---|
| `pessoas` | nova coluna `unidade` |
| `ocorrencias` | nova coluna `unidade` |
| `materiais_apreendidos` | nova coluna `unidade` |
| `vd_casos` | já tem `unidade_responsavel` (texto livre) — vira campo controlado |

As demais tabelas não ganham coluna. Elas são alcançadas pelo pai.

O valor é gravado automaticamente a partir da unidade de quem cadastrou. Não é campo
digitável — campo digitável seria preenchido errado e viraria vazamento.

### 3. Filtro nas listagens

As telas de listagem e busca (registros, ocorrências, materiais, mapa, vínculos,
painel VD, painel gerencial, exportação CSV) passam a filtrar pela unidade do usuário
logado. São aproximadamente doze pontos.

### 4. Guarda única para acesso por id

Uma função, aplicada em toda rota que carrega registro por id:

```
def exige_mesma_unidade(registro, usuario):
    """Devolve 404 se o registro não pertence à unidade do usuário."""
```

Responde 404, e não 403, de propósito: 403 confirmaria que o registro existe em outra
unidade. O 404 não revela nada.

É este item que fecha o acesso lateral. Sem ele, os outros três não adiantam.

### 5. Migração dos bancos existentes

Ao abrir uma versão nova sobre um banco antigo:

1. as colunas são criadas;
2. todos os registros existentes recebem a unidade informada uma única vez, numa tela
   de configuração inicial;
3. todos os usuários existentes recebem essa mesma unidade;
4. enquanto a unidade não for definida, o sistema não abre — em vez de abrir com os
   dados sem dono.

Isso corrige, de passagem, o problema B3 da revisão técnica: as migrações hoje só
cobrem `pessoas` e `ocorrencias`.

---

## O que precisa ser decidido antes

### Quem cria o administrador de cada unidade?

Num servidor central, se todo administrador enxerga apenas a própria unidade, alguém
precisa criar o primeiro administrador de cada uma. Três caminhos:

**A. Perfil "Administrador geral".** Gerencia unidades e usuários de todas elas, mas
não abre registro nem caso. É o mais prático para operar.

**B. Sem perfil global.** Cada administrador de unidade é criado por linha de comando
no servidor, como já acontece hoje com `Resetar Senha.bat`. Mais seguro, mais
trabalhoso, exige acesso físico ou remoto ao servidor a cada unidade nova.

**C. Administrador geral com acesso total.** Simples de implementar e o mais frágil:
uma conta comprometida expõe todas as unidades.

### Uma ressalva honesta sobre a opção A

Um administrador geral que cria e edita usuários pode, a qualquer momento, criar para
si um usuário na unidade que quiser e entrar por ele. A restrição "não vê registro nem
caso" é um controle de conveniência, não uma barreira real.

Tornar essa barreira real exige registrar na auditoria toda criação e alteração de
usuário feita pelo administrador geral, e revisar essa trilha periodicamente. Ou seja:
o controle é por rastreabilidade e responsabilização, não por impedimento técnico.
Isso precisa estar claro para quem assinar a decisão.

---

## Ordem de execução

1. Coluna `unidade` em `usuarios`, com migração e tela de configuração inicial.
2. Coluna `unidade` nas quatro tabelas-raiz, preenchida automaticamente.
3. Guarda `exige_mesma_unidade` aplicada a todas as rotas que carregam por id.
4. Filtro por unidade nas listagens.
5. Bateria de testes de isolamento: usuário da unidade A tentando alcançar, por id
   direto, cada tipo de registro da unidade B.
6. Atualização do LEIA-ME e do Manual de Instalação em Rede.

O item 5 não é formalidade. É ele que comprova que a separação funciona, e é o que
eu levaria para a chefia como evidência.

---

## Antes de distribuir

A revisão técnica de 17/08 levantou dez itens. Três deles ficam mais graves num
servidor central, porque o alcance deixa de ser uma unidade:

- **A3 — login sem limite de tentativas.** Num servidor central, alcança todas as
  unidades. Deveria ser corrigido antes da distribuição.
- **M4 — sessão que não expira.** Computador compartilhado em unidade distante,
  sessão aberta indefinidamente.
- **A2 — exclusão sem cascata.** Órfãos passam a atravessar unidades, e um registro
  órfão não tem unidade a que responder.
