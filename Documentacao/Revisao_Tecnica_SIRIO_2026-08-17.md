# Revisão técnica do SIRIO

**Data:** 17 de agosto de 2026
**Escopo:** 18 módulos Python, 30 tabelas, 47 rotas GET e 53 rotas POST
**Método:** análise do código + sistema executado em cópia isolada, com testes de
permissão, entradas inválidas e exclusão. O banco de produção não foi alterado
em nenhum momento.

---

## Resumo

O SIRIO está bem construído nos pontos que mais importam: as permissões por
perfil funcionam de fato, não há injeção de SQL, não há XSS, as senhas usam
derivação forte e a auditoria registra o que precisa registrar. Os problemas
encontrados são de **robustez e ciclo de vida do dado** — não de arquitetura.

Nada aqui exige reescrever o sistema. São correções pontuais.

| Gravidade | Quantidade |
|---|---|
| Alta | 3 |
| Média | 4 |
| Baixa | 3 |

---

## Situação em 17/08/2026 (atualizado no fim do dia)

Nove dos dez itens foram corrigidos e testados em cópia isolada do sistema. O
banco de produção não foi alterado em nenhum momento.

| Item | Situação | Como foi verificado |
|---|---|---|
| A1 — queda por campo obrigatório ausente | **corrigido** | POST sem `status` e sem `nivel_sigilo`: valor anterior preservado, servidor não cai |
| A2 — exclusão sem cascata | **corrigido** | exclusão de pessoa com foto, biqueira, boletim, FONAR e endereço sigiloso: zero órfãos, arquivos apagados do disco |
| A3 — login sem limite | **corrigido** | 5 erros bloqueiam por 15 min; senha correta também é barrada durante o bloqueio; falhas registradas na auditoria |
| M1 — sem validação de entrada | **corrigido** | 8 entradas inválidas barradas com mensagem; valores válidos continuam passando |
| M2 — CSRF em 7 rotas de 51 | **corrigido** | verificação única após `d = self.form()`; criar e excluir sem token passam a ser recusados |
| M3 — chave privada no backup | **corrigido** | backup gerado não contém `certificados\`; busca por conteúdo da chave não encontra vestígio |
| M4 — sessão sem expiração | **corrigido** | 30 min de inatividade e 12 h no total; sessão sai da memória |
| B1 — material sem edição | **em aberto** | decisão da autora: não implementar por ora |
| B2 — backup do banco em uso | **corrigido** | passa a usar a API de backup do SQLite; `integrity_check` da cópia retorna `ok` |
| B3 — migrações incompletas | **corrigido** | banco antigo sem 7 colunas migrado automaticamente; coluna nova em tabela `vd_*` aplicada e não repetida |

Regressão conferida ao final: edição de pessoa, ocorrência e caso VD continuam
gravando; upload de foto continua funcionando com token e é recusado sem token;
os 20 módulos compilam; nenhuma exceção no servidor durante toda a bateria.

---

## Gravidade alta

### A1. Duas telas de edição quebram o servidor com campo faltando

Em `/pessoas/<id>/editar` e `/vd/<id>/editar`, o código monta o UPDATE assim:

```python
novo = d.get(c) or None
```

Se um campo obrigatório no banco (`pessoas.status`, `vd_casos.nivel_sigilo`) não
chegar no envio, o valor vira `NULL`, o SQLite recusa e a conexão cai **sem
página de erro**. A pessoa vê "não foi possível carregar a página" e perde o
que digitou. Reproduzido nos dois casos.

Pelo navegador isso não acontece no uso normal, porque o formulário sempre envia
o campo. Mas basta uma perda de conexão no meio do envio, um plugin de navegador
ou um campo renomeado no futuro para a tela inteira parar sem explicação.

**Correção:** aplicar valor padrão no servidor, como já é feito em
`/pessoas/nova` (`valores["status"] or "em_verificacao"`).

### A2. Excluir uma pessoa deixa rastros por todo o banco

`DELETE FROM pessoas WHERE id=?` apaga só a linha da pessoa. Nada em cascata.
As chaves estrangeiras não estão declaradas no schema — o `PRAGMA foreign_keys
= ON` existe no código, mas sem constraints declaradas ele não tem efeito.

Teste com uma pessoa real da base: **14 registros órfãos** em uma única
exclusão (1 em `boletim_pessoa`, 1 em `materiais_apreendidos`, 12 na
`auditoria`).

Pior: **os arquivos de foto continuam no disco.** A remoção de arquivo só
acontece na rota de excluir foto individual. Excluir a pessoa deixa as
fotografias e tatuagens dela em `fotos\`, fora de qualquer registro. Em dados
de investigação isso é um problema de retenção, não só de arrumação.

Hoje não há órfão nenhum na base — porque ninguém excluiu pessoa ainda. O
problema aparece na primeira exclusão.

**Correção:** apagar em cascata dentro da mesma transação, incluindo os arquivos
de foto, e preservar a auditoria de propósito (com o nome já registrado no
campo `valor_anterior`).

### A3. Login sem nenhum limite de tentativas

25 tentativas de senha errada foram processadas em 1,1 segundo, sem bloqueio,
sem atraso, sem registro de falha na auditoria. A auditoria grava `LOGIN` com
sucesso, mas **não grava tentativa fracassada** — não há como perceber um ataque
olhando a trilha.

No modo "Rede da Unidade" o sistema fica exposto a toda a rede interna. Uma
senha fraca de um perfil Consulta é suficiente para entrar.

**Correção:** atraso progressivo por login e por IP, bloqueio temporário após N
falhas, e registro das tentativas fracassadas na auditoria.

---

## Gravidade média

### M1. Nenhuma validação de data, número ou coordenada

Todos aceitos sem reclamar:

| Campo | Valor aceito |
|---|---|
| `data_nascimento` | `banana` |
| `data_nascimento` | `31/02/9999` |
| `qtd_filhos` | `dois` |
| `qtd_filhos` | `-5` |
| `lat_fato` / `lon_fato` | `999` / `999` |
| `nome` | 200.000 caracteres |

A coordenada 999 chega ao JSON do mapa e vai quebrar a exibição. Data inválida
em campo de nascimento contamina relatório e qualquer filtro por idade.

**Correção:** validar no servidor antes de gravar, devolvendo o formulário com
mensagem — o padrão já usado para "Informe o nome completo".

### M2. Verificação de CSRF em 7 rotas de 51

O token é gerado e enviado em todos os formulários, mas conferido em apenas
7 rotas. Ficam sem conferência 44 rotas que alteram dados, incluindo
`/pessoas/<id>/excluir`, `/ocorrencias/<id>/excluir` e `/configuracoes/backup`.

O risco prático hoje é baixo, porque o cookie de sessão usa
`SameSite=Lax`, e navegador atual não envia esse cookie em POST vindo de outro
site. A defesa existe — mas é de uma só camada, e depende inteiramente do
navegador. Foi por isso que o token foi criado.

**Correção:** conferir o token em toda rota que altera dados. Já está feito na
rota nova de edição de usuários.

### M3. O backup carrega a chave privada do HTTPS

`/configuracoes/backup` copia o banco, a pasta `fotos\` e também a pasta
`certificados\` — que contém `sirio-chave-privada.pem`.

O próprio LEIA-ME avisa, na seção 1, que "a chave privada não deve ser copiada
para computadores clientes". Mas o backup a leva junto, e backup normalmente vai
para pendrive ou pasta de rede. O backup também não tem senha nem cifragem, e
carrega dados sensíveis de investigação e fotografias.

**Correção:** manter fora do backup ou separar em dois destinos — dados de um
lado, certificado de outro — e documentar que a pasta `backups\` exige a mesma
proteção do banco.

### M4. Sessão não expira

A sessão guarda apenas `usuario_id` e `csrf`. Não há prazo de validade nem
expiração por inatividade. Uma sessão aberta vale até o servidor ser reiniciado.

Em computador compartilhado de unidade policial, quem senta na máquina depois
continua dentro do sistema com o perfil de quem estava antes.

**Correção:** prazo de inatividade (30 minutos, por exemplo) verificado a cada
requisição.

---

## Gravidade baixa

### B1. Material apreendido não pode ser editado

Não existe rota `/materiais/<id>/editar` nem botão na tela. Só criar e excluir.
Um lacre digitado errado exige apagar e recadastrar.

O LEIA-ME, na seção 3, afirma que o perfil Analista pode "cadastrar, editar e
alterar o status de registros, ocorrências, materiais e importações". A
documentação promete algo que nunca existiu no código.

### B2. Backup copiado com o banco em uso

O backup usa `shutil.copy2` no arquivo do banco enquanto o sistema está no ar, e
o `journal_mode` é `delete`. Se houver gravação em andamento no momento da
cópia, o arquivo copiado pode sair inconsistente — e um backup que não abre só
se descobre no dia em que ele é necessário.

**Correção:** usar a API de backup do próprio SQLite (`sqlite3.Connection.backup`),
que faz cópia consistente com o banco em uso.

### B3. Migrações cobrem só duas tabelas

O `ALTER TABLE` automático de `sirio_core.py` trata apenas `pessoas` e
`ocorrencias`. Adicionar coluna em qualquer tabela `vd_*` não chega aos bancos
já existentes: a unidade que já usa o sistema recebe a atualização e ela falha
sem aviso claro.

---

## O que foi verificado e está correto

- **Injeção de SQL:** não há. As f-strings em SQL montam apenas nomes de coluna
  vindos de listas fixas no código; os valores vão sempre parametrizados.
- **XSS:** bloqueado. `<script>alert(1)</script>` gravado no campo nome sai
  escapado como `&lt;script&gt;` na página.
- **Permissões por perfil:** testadas com usuário real de perfil Consulta. As
  cinco rotas de escrita tentadas responderam 404 e nada foi gravado.
- **Senhas:** PBKDF2-HMAC-SHA256 com 200.000 iterações e sal por usuário.
- **Cookie de sessão:** `HttpOnly`, `Secure`, `SameSite=Lax`.
- **Travessia de caminho** na rota de fotos: três variações testadas
  (`../`, `..%2F`, `....//`), todas negadas com 404.
- **Upload de foto:** valida extensão, assinatura de arquivo e tamanho máximo.
- **Schema:** as 30 tabelas do código conferem com as 30 do banco.
- **Integridade do banco atual:** `PRAGMA integrity_check` retorna `ok`, sem
  nenhum registro órfão.

---

## Ordem sugerida

1. **A1** — é a que atrapalha o trabalho hoje e a correção é pequena.
2. **A3** e **M4** — segurança de acesso; valem mais no modo Rede da Unidade.
3. **A2** — antes da primeira exclusão de pessoa, não depois.
4. **M1** — quanto mais tempo passa, mais dado ruim entra na base.
5. **M2**, **M3**, **B2** — reduzem dependência de uma só camada de proteção.
6. **B1**, **B3** — conveniência e manutenção.

Os itens A1, M1 e B1 são correções contidas, sem efeito em outras partes do
sistema. A2 e A3 mexem em comportamento e pedem teste com calma antes de ir
para a unidade.
