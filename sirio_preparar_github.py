"""Monta uma cópia segura do código-fonte do SIRIO para publicação no GitHub.

O pacote nunca inclui o banco de dados, fotografias, backups, certificados ou
arquivos temporários. Ao final, cria um relatório de conferência com tudo o que
foi incluído e o que foi deixado de fora.
"""
from datetime import datetime
from pathlib import Path
import shutil
import sys


PASTA = Path(__file__).resolve().parent
PASTAS_PROIBIDAS = {"fotos", "backups", "certificados", "__pycache__", ".git", "pacotes_github"}
ARQUIVOS_PROIBIDOS = {
    "sirio.db", "sirio.db-journal", "sirio.db-wal", "sirio.db-shm",
    ".bo_tmp_420d1634163d411a.pdf",
}
SUFIXOS_PROIBIDOS = {
    ".db", ".sqlite", ".sqlite3", ".pem", ".cer", ".pfx", ".key", ".pyc", ".log",
}


def motivo_exclusao(caminho: Path) -> str:
    """Devolve o motivo para não publicar o arquivo, ou vazio se for seguro."""
    nome = caminho.name.lower()
    sufixo = caminho.suffix.lower()
    if nome in ARQUIVOS_PROIBIDOS or sufixo in {".db", ".sqlite", ".sqlite3"}:
        return "banco de dados ou cópia que pode conter dados pessoais"
    if ".db-" in nome or nome.endswith(("-journal", "-wal", "-shm")):
        return "arquivo auxiliar do banco de dados"
    if sufixo in {".pem", ".cer", ".pfx", ".key"}:
        return "certificado ou chave privada"
    if sufixo in {".pyc", ".log"} or nome.startswith(".bo_tmp_"):
        return "arquivo temporário"
    return ""


def copiar_publicavel(origem: Path, destino: Path, incluidos: list[str], excluidos: list[tuple[str, str]]):
    for item in sorted(origem.iterdir(), key=lambda p: p.name.lower()):
        relativo = item.relative_to(PASTA)
        if item.is_dir():
            if item.name.lower() in PASTAS_PROIBIDAS:
                excluidos.append((str(relativo) + "\\", "pasta que pode conter dados pessoais ou de ambiente"))
                continue
            subdestino = destino / item.name
            subdestino.mkdir(parents=True, exist_ok=True)
            copiar_publicavel(item, subdestino, incluidos, excluidos)
            continue
        motivo = motivo_exclusao(item)
        if motivo:
            excluidos.append((str(relativo), motivo))
            continue
        shutil.copy2(item, destino / item.name)
        incluidos.append(str(relativo))


def conferir(destino: Path) -> list[str]:
    """Última barreira: nenhum dado sensível pode ter chegado ao pacote."""
    problemas = []
    for item in destino.rglob("*"):
        partes = {p.lower() for p in item.relative_to(destino).parts}
        if partes & PASTAS_PROIBIDAS:
            problemas.append(str(item.relative_to(destino)))
            continue
        if item.is_file() and motivo_exclusao(item):
            problemas.append(str(item.relative_to(destino)))
    return problemas


def escrever_relatorio(destino: Path, incluidos: list[str], excluidos: list[tuple[str, str]], selo: str):
    linhas = [
        "RELATÓRIO DE PREPARAÇÃO PARA GITHUB — SIRIO",
        f"Data: {selo}",
        "",
        "Este pacote foi filtrado para não incluir banco de dados, fotos pessoais, backups ou certificados.",
        "Revise o conteúdo antes de publicar, especialmente documentos adicionados no futuro.",
        "",
        f"ARQUIVOS INCLUÍDOS ({len(incluidos)})",
        *[f"  + {nome}" for nome in sorted(incluidos, key=str.lower)],
        "",
        f"ITENS EXCLUÍDOS ({len(excluidos)})",
        *[f"  - {nome}: {motivo}" for nome, motivo in sorted(excluidos, key=lambda x: x[0].lower())],
        "",
        "Resultado: pacote de código preparado para revisão e envio ao GitHub.",
    ]
    (destino / "RELATORIO_PACOTE_GITHUB.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main():
    selo = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pasta_pacotes = PASTA / "Pacotes_GitHub"
    pasta_pacotes.mkdir(exist_ok=True)
    temporario = PASTA.parent / f".sirio_github_temporario_{selo}"
    zip_final = pasta_pacotes / f"SIRIO_para_GitHub_{selo}.zip"
    if temporario.exists() or zip_final.exists():
        print("Já existe um pacote com este identificador. Execute novamente em alguns segundos.")
        return 1
    temporario.mkdir(parents=True)
    incluidos, excluidos = [], []
    try:
        copiar_publicavel(PASTA, temporario, incluidos, excluidos)
        problemas = conferir(temporario)
        if problemas:
            print("ERRO: itens sensíveis foram encontrados na cópia. O pacote não foi criado:")
            for problema in problemas:
                print(" -", problema)
            return 1
        escrever_relatorio(temporario, incluidos, excluidos, selo)
        shutil.make_archive(str(zip_final.with_suffix("")), "zip", root_dir=temporario)
    finally:
        if temporario.exists():
            shutil.rmtree(temporario)
    print("Pacote pronto para revisão e envio ao GitHub:")
    print(zip_final)
    print("O arquivo RELATORIO_PACOTE_GITHUB.txt está dentro do .zip.")
    print("Nenhum banco, fotografia pessoal, backup ou certificado foi incluído.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
