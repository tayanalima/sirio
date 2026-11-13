"""Execute na pasta completa do SIRIO. Cria backups antes de integrar."""
from pathlib import Path
from datetime import datetime
import ast
import shutil


def preparar(pasta):
    principal=pasta/'sirio.py'
    core=pasta/'sirio_core.py'
    if not principal.exists() or not core.exists():
        raise RuntimeError('Copie os arquivos deste pacote para a pasta completa do SIRIO (com sirio.py e sirio_core.py).')
    alteracoes=[]
    texto=principal.read_text(encoding='utf-8-sig')
    if 'from sirio_comunicacoes import atender as atender_comunicacoes' not in texto:
        alvo='from sirio_core import *'
        if alvo not in texto: raise RuntimeError('Versão do SIRIO não reconhecida: importação.')
        texto=texto.replace(alvo,'from sirio_comunicacoes import atender as atender_comunicacoes\n'+alvo,1)
        alvo='        usuario, csrf = sessao\n'
        if texto.count(alvo)!=2: raise RuntimeError('Versão do SIRIO não reconhecida: autenticação.')
        for metodo in ('GET','POST'):
            pos=texto.index('    def do_'+metodo+'(')
            fim=texto.index(alvo,pos)+len(alvo)
            texto=texto[:fim]+f'\n        if atender_comunicacoes(self, "{metodo}", usuario, csrf):\n            return\n'+texto[fim:]
        ast.parse(texto)
        alteracoes.append((principal,texto))
    texto=core.read_text(encoding='utf-8-sig')
    if 'href="/comunicacoes"' not in texto:
        alvo='<a href="/investigacoes">Investigações</a>'
        if alvo not in texto: raise RuntimeError('Versão do SIRIO não reconhecida: menu.')
        texto=texto.replace(alvo,alvo+'<a href="/comunicacoes">Comunicações de serviço</a>',1)
        ast.parse(texto)
        alteracoes.append((core,texto))
    if not alteracoes: return 'O módulo já está integrado.'
    backup=pasta/('backup_antes_comunicacoes_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir()
    for arquivo,_ in alteracoes: shutil.copy2(arquivo,backup/arquivo.name)
    try:
        for arquivo,conteudo in alteracoes: arquivo.write_text(conteudo,encoding='utf-8')
    except Exception:
        for arquivo,_ in alteracoes: shutil.copy2(backup/arquivo.name,arquivo)
        raise
    return 'Módulo integrado. Backup dos arquivos anteriores: '+str(backup)

if __name__=='__main__':
    try: print(preparar(Path(__file__).resolve().parent))
    except Exception as exc:
        print('Instalação interrompida: '+str(exc))
        raise SystemExit(1)
