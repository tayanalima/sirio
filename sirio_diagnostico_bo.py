"""Mostra como o texto de um BO chega ao SIRIO, para ajustar a extração.

O PDF do BO não guarda o layout visual: ao extrair o texto, rótulos e valores
saem em ordem imprevisível, e essa ordem muda de uma seção para outra. Este
diagnóstico imprime as linhas em volta de cada rótulo de endereço, com o número
da linha, para que dê para ver exatamente onde está cada valor.

Os nomes de pessoas são mascarados. Logradouros, números e bairros aparecem,
porque é justamente deles que se trata.

Uso: dois cliques em "Diagnosticar BO.bat" e escolha o arquivo PDF.
"""
import os
import re
import sys

from pypdf import PdfReader


ROTULOS = ("ENDEREÇO (AV", "LOCAL (AV", "NÚMERO", "BAIRRO", "MUNICÍPIO", "COMPLEMENTO")
JANELA = 4  # linhas mostradas antes e depois de cada rótulo


def mascara_nomes(linha, nomes):
    """Troca nomes de pessoas por XXX, preservando o resto da linha."""
    saida = linha
    for nome in nomes:
        for parte in nome.split():
            if len(parte) > 2:
                saida = re.sub(rf"\b{re.escape(parte)}\b", "X" * len(parte), saida,
                               flags=re.IGNORECASE)
    return saida


def coleta_nomes(texto):
    """Nomes que aparecem logo após os rótulos de qualificação, para mascarar."""
    nomes = set()
    linhas = texto.split("\n")
    for k, l in enumerate(linhas):
        u = l.strip().upper()
        if u.startswith(("NOME", "PAI", "MÃE", "MAE", "APELIDO")):
            for j in (k - 1, k + 1):
                if 0 <= j < len(linhas):
                    cand = linhas[j].strip()
                    if cand and len(cand) > 5 and not cand.isdigit():
                        nomes.add(cand)
    return nomes


def main():
    if len(sys.argv) > 1:
        caminho = sys.argv[1]
    else:
        caminho = input("Arraste o PDF do BO para esta janela e tecle ENTER:\n> ").strip().strip('"')
    if not os.path.isfile(caminho):
        print("Arquivo nao encontrado.")
        return 1

    texto = "\n".join((p.extract_text() or "") for p in PdfReader(caminho).pages)
    linhas = texto.split("\n")
    nomes = coleta_nomes(texto)

    i = texto.find("DADOS DA OCORRÊNCIA")
    j = texto.find("QUALIFICAÇÃO DOS ENVOLVIDOS")
    linha_i = texto[:i].count("\n") if i >= 0 else -1
    linha_j = texto[:j].count("\n") if j >= 0 else -1

    print()
    print("=" * 70)
    print(" DIAGNOSTICO DE LEITURA DO BO")
    print("=" * 70)
    print(f" Arquivo: {os.path.basename(caminho)}")
    print(f" Total de linhas extraidas: {len(linhas)}")
    print(f" Secao DADOS DA OCORRENCIA comeca na linha: {linha_i}")
    print(f" Secao QUALIFICACAO DOS ENVOLVIDOS na linha: {linha_j}")
    print(" Nomes de pessoas aparecem mascarados como XXXX.")
    print("=" * 70)

    achou = False
    for k, l in enumerate(linhas):
        u = l.strip().upper()
        if not any(u.startswith(r) for r in ROTULOS):
            continue
        achou = True
        secao = "LOCAL DO FATO" if (linha_i >= 0 and linha_i <= k < (linha_j if linha_j > 0 else len(linhas))) \
            else "ENVOLVIDO / OUTRA"
        print()
        print(f"--- rotulo {l.strip()!r} na linha {k}  [secao: {secao}] ---")
        for j2 in range(max(0, k - JANELA), min(len(linhas), k + JANELA + 1)):
            marca = ">>" if j2 == k else "  "
            conteudo = mascara_nomes(linhas[j2].rstrip(), nomes)
            print(f" {marca} {j2:4}: {conteudo!r}")

    if not achou:
        print()
        print(" Nenhum rotulo de endereco encontrado. O layout deste BO e diferente")
        print(" do previsto. Envie as primeiras 60 linhas abaixo:")
        for k, l in enumerate(linhas[:60]):
            print(f"  {k:4}: {mascara_nomes(l.rstrip(), nomes)!r}")

    print()
    print("=" * 70)
    print(" Copie TUDO acima e envie para analise.")
    print(" Confira antes se algo sensivel escapou da mascara.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
