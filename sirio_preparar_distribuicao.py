"""Monta uma cópia limpa do SIRIO para entregar a outra unidade.

O que este script NUNCA copia, por segurança:

  sirio.db                    banco com dados reais de investigação
  fotos\\                      fotografias e tatuagens cadastradas
  backups\\                    cópias do banco e das fotos
  certificados\\               inclui a chave privada do HTTPS deste servidor
  __pycache__\\                arquivos temporários do Python

Cada unidade precisa gerar o próprio certificado e criar o próprio
administrador na primeira execução. Certificado e banco não são
transferíveis entre computadores.
"""
from datetime import datetime
from pathlib import Path
import shutil
import sys


PASTA = Path(__file__).resolve().parent

# Pastas que jamais entram no pacote.
PASTAS_PROIBIDAS = {"fotos", "backups", "certificados", "__pycache__", ".git"}

# Arquivos que jamais entram no pacote (comparação sem diferenciar maiúsculas).
ARQUIVOS_PROIBIDOS = {"sirio.db", "sirio.db-journal", "sirio.db-wal", "sirio.db-shm"}

# Extensões que jamais entram no pacote.
#
# Qualquer .db fica de fora, não só o sirio.db: bancos de teste com nome
# improvisado (_t1.db, copia.db, teste.db) costumam sobrar na pasta e contêm
# os mesmos registros reais do banco principal.
SUFIXOS_PROIBIDOS = {".pem", ".cer", ".pfx", ".key", ".pyc", ".log",
                     ".db", ".sqlite", ".sqlite3"}
SUFIXOS_BANCO = {".db", ".sqlite", ".sqlite3"}
SUFIXOS_CERTIFICADO = {".pem", ".cer", ".pfx", ".key"}


def proibido(caminho: Path) -> str:
    """Devolve o motivo da exclusão, ou "" se o item pode ser copiado."""
    nome = caminho.name.lower()
    sufixo = caminho.suffix.lower()
    if nome in ARQUIVOS_PROIBIDOS or sufixo in SUFIXOS_BANCO:
        return "banco de dados com registros reais"
    # sirio.db-journal, _t1.db-journal, copia.db-wal e afins
    if ".db-" in nome or nome.endswith(("-journal", "-wal", "-shm")):
        return "arquivo de apoio do banco de dados"
    if sufixo in SUFIXOS_CERTIFICADO:
        return "certificado ou chave privada"
    if sufixo in SUFIXOS_PROIBIDOS:
        return "arquivo temporário"
    return ""


def copia_limpa(origem: Path, destino: Path, excluidos: list) -> int:
    copiados = 0
    for item in sorted(origem.iterdir()):
        if item.is_dir():
            if item.name in PASTAS_PROIBIDAS:
                excluidos.append((item.name + "\\", "pasta com dados locais desta unidade"))
                continue
            sub = destino / item.name
            sub.mkdir(parents=True, exist_ok=True)
            copiados += copia_limpa(item, sub, excluidos)
            continue
        motivo = proibido(item)
        if motivo:
            excluidos.append((item.name, motivo))
            continue
        shutil.copy2(item, destino / item.name)
        copiados += 1
    return copiados


def confere(destino: Path) -> list:
    """Última verificação: procura qualquer coisa sensível que tenha escapado."""
    problemas = []
    for item in destino.rglob("*"):
        if item.is_dir():
            continue
        if item.name.lower() in ARQUIVOS_PROIBIDOS or item.suffix.lower() in SUFIXOS_PROIBIDOS:
            problemas.append(str(item.relative_to(destino)))
    return problemas


def main():
    selo = datetime.now().strftime("%Y-%m-%d")
    # O pacote é montado numa pasta temporária e entregue como um único .zip.
    # Deixar uma pasta solta ao lado da instalação em uso é pedir para alguém
    # clicar no atalho errado: os dois conjuntos de .bat têm nomes idênticos.
    destino = PASTA.parent / f".sirio_pacote_temporario_{selo}"
    zip_final = PASTA.parent / f"SIRIO_para_distribuir_{selo}.zip"

    print("=" * 62)
    print(" SIRIO - Preparar pacote para outra unidade")
    print("=" * 62)
    print(f" Origem : {PASTA}")
    print(f" Pacote : {zip_final}")
    print()

    if zip_final.exists():
        resposta = input(" O pacote de hoje já existe. Refazer? (S/N): ").strip().lower()
        if resposta != "s":
            print("\n Nada foi alterado.")
            return 1
        zip_final.unlink()
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    excluidos = []
    copiados = copia_limpa(PASTA, destino, excluidos)

    print(f" {copiados} arquivo(s) copiado(s).")
    print()
    print(" DEIXADO DE FORA (permanece somente neste computador):")
    for nome, motivo in sorted(set(excluidos)):
        print(f"   - {nome:32} {motivo}")

    problemas = confere(destino)
    print()
    if problemas:
        print(" !! ATENÇÃO: itens sensíveis foram encontrados no pacote:")
        for p in problemas:
            print(f"      {p}")
        print(" !! NÃO distribua este pacote. Avise o responsável técnico.")
        return 1

    print(" Verificação final: nenhum dado sensível no pacote. OK.")

    shutil.make_archive(str(zip_final.with_suffix("")), "zip", root_dir=destino)
    shutil.rmtree(destino)
    print()
    print(f" Pacote pronto: {zip_final.name}")
    print(f" Local: {zip_final.parent}")
    print()
    print(" O pacote é um arquivo .zip de propósito: uma pasta solta ao lado")
    print(" da instalação em uso teria atalhos com os mesmos nomes, e é fácil")
    print(" executar o da pasta errada sem perceber.")
    print()
    print("=" * 62)
    print(" O QUE A UNIDADE QUE RECEBER PRECISA FAZER")
    print("=" * 62)
    print(" 1. Instalar o Python 3.10 ou mais novo, marcando")
    print('    "Add Python to PATH".')
    print(" 2. Colocar a pasta no local definitivo (ex.: C:\\SIRIO).")
    print(' 3. Executar "Gerar Certificado HTTPS.bat" uma vez,')
    print("    no computador principal daquela unidade.")
    print(' 4. Executar "Iniciar SIRIO (Rede da Unidade).bat" e criar')
    print("    o administrador na primeira tela.")
    print(" 5. Instalar o certificado nos computadores clientes,")
    print("    conforme a seção 6 do Manual de Instalação em Rede.")
    print()
    print(" O banco começa vazio, de propósito. Nenhum registro desta")
    print(" unidade acompanha o pacote.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
