"""Correção pontual: tira bairro e cidade da linha de endereço das ocorrências.

Necessário apenas uma vez, para as ocorrências importadas de BO antes da
correção do importador. A ocorrência tem colunas próprias para bairro e cidade;
até então elas eram repetidas dentro do campo de endereço do fato, e a
informação aparecia duas vezes na tela.

Nada é perdido: bairro e cidade continuam nos campos deles. O script faz backup
antes de alterar, mostra o que vai mudar e pede confirmação.

Executar por "Corrigir Enderecos Importados.bat", na pasta do SIRIO.
"""
import os
import sys

from sirio_core import PASTA, ARQ_DB, agora, audita, conexao, copia_banco_consistente


def endereco_limpo(endereco, bairro, cidade):
    """Devolve o endereço sem os pedaços que repetem bairro ou cidade."""
    if not endereco:
        return endereco
    partes = [p.strip() for p in endereco.split(",") if p.strip()]
    descartar = {x.strip().upper() for x in (bairro, cidade) if x}
    mantidas = [p for p in partes if p.upper() not in descartar]
    return ", ".join(mantidas) if mantidas else endereco


def levanta(con):
    alvos = []
    for r in con.execute("SELECT id, endereco_fato, bairro_fato, cidade_fato FROM ocorrencias "
                         "WHERE endereco_fato IS NOT NULL AND endereco_fato <> ''"):
        novo = endereco_limpo(r["endereco_fato"], r["bairro_fato"], r["cidade_fato"])
        if novo and novo != r["endereco_fato"]:
            alvos.append((r["id"], r["endereco_fato"], novo))
    return alvos


def escolhe_responsavel(con):
    """A auditoria exige um usuário. Quem autoriza a correção assume o registro."""
    admins = con.execute(
        "SELECT id, nome, username FROM usuarios WHERE perfil='admin' AND ativo=1 ORDER BY nome"
    ).fetchall()
    if not admins:
        print(" Nenhum administrador ativo encontrado. Nada foi alterado.")
        return None
    if len(admins) == 1:
        print(f" Responsavel pela correcao: {admins[0]['nome']}")
        return admins[0]["id"]
    print(" Administradores:")
    for u in admins:
        print(f"   [{u['id']}] {u['nome']} (login: {u['username']})")
    try:
        escolha = int(input(" Digite o numero (ID) de quem autoriza a correcao: ").strip())
    except (ValueError, KeyboardInterrupt):
        print(" Entrada invalida. Nada foi alterado.")
        return None
    if escolha not in [u["id"] for u in admins]:
        print(" ID nao corresponde a um administrador ativo. Nada foi alterado.")
        return None
    return escolha


def main():
    print("=" * 66)
    print(" SIRIO - Corrigir enderecos importados de BO")
    print("=" * 66)
    print(f" Pasta: {PASTA}")
    print(f" Banco: {ARQ_DB}")
    if not os.path.isfile(ARQ_DB):
        print("\n Nao existe banco de dados nesta pasta.")
        print(" Se voce queria corrigir o SIRIO que ja usa, feche esta janela e")
        print(" execute o atalho a partir da pasta correta.")
        return 1
    print("=" * 66)
    print()

    con = conexao()
    alvos = levanta(con)
    if not alvos:
        con.close()
        print(" Nenhuma ocorrencia precisa de correcao. Nada a fazer.")
        return 0

    print(f" {len(alvos)} ocorrencia(s) com bairro/cidade repetidos na linha de endereco:")
    print()
    for oid, antes, depois in alvos:
        print(f"   #{oid}")
        print(f"      antes : {antes}")
        print(f"      depois: {depois}")
    print()
    print(" Bairro e cidade continuam gravados nos campos proprios da ocorrencia.")
    print(" O numero da casa NAO pode ser recuperado nestas: ele nunca foi")
    print(" extraido na importacao. Novas importacoes ja trazem o numero.")
    print()

    resposta = input(" Aplicar a correcao? (S/N): ").strip().lower()
    if resposta != "s":
        con.close()
        print("\n Nada foi alterado.")
        return 0

    responsavel = escolhe_responsavel(con)
    if responsavel is None:
        con.close()
        return 1

    print()
    print(" Criando backup antes de alterar...")
    selo = agora().replace(":", "-").replace(" ", "_")
    destino = os.path.join(PASTA, "backups", f"{selo}_antes_correcao_enderecos")
    os.makedirs(destino, exist_ok=True)
    if not copia_banco_consistente(os.path.join(destino, "sirio.db")):
        con.close()
        print(" Nao foi possivel criar o backup. Nada foi alterado.")
        return 1
    print(f" Backup em: backups\\{os.path.basename(destino)}")

    try:
        for oid, antes, depois in alvos:
            con.execute("UPDATE ocorrencias SET endereco_fato=?, atualizado_em=?, atualizado_por=?"
                        " WHERE id=?", (depois, agora(), responsavel, oid))
            audita(con, responsavel, "UPDATE", None, "ocorrencia.endereco_fato", antes, depois)
        audita(con, responsavel, "UPDATE", None, "correcao_em_lote",
               f"{len(alvos)} ocorrencia(s)",
               "bairro e cidade removidos da linha de endereco (duplicavam os campos proprios)")
        con.commit()
    except Exception as err:
        con.rollback()
        con.close()
        print()
        print(f" ERRO ao gravar: {err}")
        print(" Nada foi alterado. O backup acima continua disponivel.")
        return 1

    restantes = levanta(con)
    con.close()
    print()
    print("=" * 66)
    print(f" {len(alvos)} ocorrencia(s) corrigida(s).")
    print(f" Ainda com duplicacao: {len(restantes)}")
    print(" Cada alteracao ficou registrada na trilha de auditoria.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
