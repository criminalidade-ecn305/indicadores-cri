"""Etapa 1: baixa os microdados do DataSUS e os converte em .dbf.

Uso: python 01_download.py [pasta_de_dados]

Baixa, por FTP público do DataSUS:
  SIM, declarações de óbito, dados finais: /dissemin/publicos/SIM/CID10/DORES/DOBR{ano}.dbc
  POPSVS, população por município, sexo e idade: /dissemin/publicos/IBGE/POPSVS/POPSBR{aa}.zip
Grava em <pasta>/brutos/ e converte para <pasta>/dbf/. O .dbc é um .dbf comprimido em formato próprio
do DataSUS; a descompressão usa o pacote datasus-dbc. O registro de cada arquivo (tamanho, MD5 e data)
fica em <pasta>/brutos/registro_download.csv. Arquivos já baixados e íntegros não são baixados de novo.
"""
import csv
import datetime as dt
import ftplib
import hashlib
import os
import time
import zipfile

import datasus_dbc

from comum import ANOS, pasta_dados

SERVIDOR = 'ftp.datasus.gov.br'
ARQUIVOS = ([f'/dissemin/publicos/SIM/CID10/DORES/DOBR{a}.dbc' for a in ANOS] +
            [f'/dissemin/publicos/IBGE/POPSVS/POPSBR{a % 100:02d}.zip' for a in ANOS])


def conectar():
    ftp = ftplib.FTP(SERVIDOR, timeout=120)
    ftp.login()
    ftp.voidcmd('TYPE I')
    return ftp


def baixar(caminho_remoto, destino, tentativas=60):
    """Baixa com retomada (comando REST): o servidor do DataSUS costuma derrubar conexões longas."""
    ftp = conectar()
    tamanho = ftp.size(caminho_remoto)
    ftp.quit()
    for t in range(1, tentativas + 1):
        feito = os.path.getsize(destino) if os.path.exists(destino) else 0
        if feito == tamanho:
            return tamanho
        try:
            ftp = conectar()
            with open(destino, 'ab') as f:
                ftp.retrbinary(f'RETR {caminho_remoto}', f.write, blocksize=1 << 16, rest=feito or None)
            ftp.quit()
        except (ftplib.all_errors) as e:
            print(f'    tentativa {t}: {os.path.getsize(destino):,} de {tamanho:,} bytes ({type(e).__name__}); retomando')
            time.sleep(3)
    raise RuntimeError(f'não foi possível baixar {caminho_remoto}')


def md5(caminho):
    h = hashlib.md5()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()


def main():
    base = pasta_dados()
    brutos, dbf = os.path.join(base, 'brutos'), os.path.join(base, 'dbf')
    os.makedirs(brutos, exist_ok=True)
    os.makedirs(dbf, exist_ok=True)
    registro = []
    for remoto in ARQUIVOS:
        nome = remoto.rsplit('/', 1)[1]
        local = os.path.join(brutos, nome)
        print(f'{nome}: baixando de {SERVIDOR}')
        n = baixar(remoto, local)
        registro.append({'arquivo': nome, 'origem': f'ftp://{SERVIDOR}{remoto}', 'bytes': n, 'md5': md5(local),
                         'data': dt.date.today().isoformat()})
        if nome.endswith('.dbc'):
            saida = os.path.join(dbf, nome[:-4] + '.dbf')
            if not os.path.exists(saida):
                print(f'{nome}: descomprimindo')
                datasus_dbc.decompress(local, saida)
        else:
            with zipfile.ZipFile(local) as z:
                internos = [i for i in z.namelist() if i.lower().endswith('.dbf')]
                assert len(internos) == 1, internos
                saida = os.path.join(dbf, nome[:-4] + '.dbf')
                if not os.path.exists(saida):
                    with open(saida, 'wb') as f:
                        f.write(z.read(internos[0]))
        print(f'{nome}: ok ({n:,} bytes)')
    with open(os.path.join(brutos, 'registro_download.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(registro[0]))
        w.writeheader()
        w.writerows(registro)
    print('Etapa 1 concluída.')


if __name__ == '__main__':
    main()
