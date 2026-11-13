"""Etapa 4: atualiza as abas de base das planilhas do Excel com as bases da etapa 2.

Uso: python 04_planilhas.py [pasta_de_dados] [--forcar]

As planilhas da pasta planilhas/ guardam o cálculo dos indicadores em fórmulas (SOMASES sobre as abas de base),
para que qualquer número possa ser auditado no próprio Excel. Este script compara cada aba de base com o CSV
correspondente e só a reescreve se houver diferença (ou com --forcar). Se o número de linhas mudar, os intervalos
das fórmulas que apontam para a aba são ajustados. As fórmulas são recalculadas ao abrir o arquivo no Excel.
"""
import os
import re
import sys

import openpyxl
import pandas as pd

from comum import pasta_dados

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PLANILHAS = ['Indicador 1 - Violência letal contra mulheres.xlsx',
             'Indicador 2 - Anos de vida produtiva perdidos.xlsx',
             'Base e conferência.xlsx']
ABAS = {'Base homicídios': 'base_homicidios.csv',
        'Base população': 'base_populacao.csv',
        'Base idade exata': 'base_idade_exata.csv'}


def aba_como_df(ws):
    linhas = list(ws.iter_rows(values_only=True))
    return pd.DataFrame(linhas[1:], columns=linhas[0])


def iguais(a, b):
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        return False
    return all((a[c].astype(str).to_numpy() == b[c].astype(str).to_numpy()).all() for c in a.columns)


def reescreve(wb, ws, df):
    antigo = ws.max_row
    ws.delete_rows(2, antigo)
    for r in df.itertuples(index=False):
        ws.append([v.item() if hasattr(v, 'item') else v for v in r])
    novo = len(df) + 1
    if novo != antigo:
        padrao = re.compile(r"('" + re.escape(ws.title) + r"'!\$[A-Z]+\$2:\$[A-Z]+\$)" + str(antigo) + r"\b")
        n = 0
        for outra in wb.worksheets:
            for linha in outra.iter_rows():
                for c in linha:
                    if isinstance(c.value, str) and c.value.startswith('=') and ws.title in c.value:
                        v2 = padrao.sub(lambda m: m.group(1) + str(novo), c.value)
                        if v2 != c.value:
                            c.value, n = v2, n + 1
        print(f'    intervalos ajustados de {antigo} para {novo} linhas em {n} fórmulas')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    forcar = '--forcar' in sys.argv
    sys.argv = [sys.argv[0]] + args
    bases = os.path.join(pasta_dados(), 'bases')
    csv = {aba: pd.read_csv(os.path.join(bases, arq)) for aba, arq in ABAS.items()}
    for nome in PLANILHAS:
        caminho = os.path.join(RAIZ, 'planilhas', nome)
        wb = openpyxl.load_workbook(caminho)
        mudou = False
        for aba, df in csv.items():
            if aba not in wb.sheetnames:
                continue
            atual = aba_como_df(wb[aba])
            if iguais(atual, df) and not forcar:
                print(f'{nome} / {aba}: igual à base nova ({len(df):,} linhas)')
                continue
            print(f'{nome} / {aba}: reescrevendo ({len(atual):,} -> {len(df):,} linhas)')
            reescreve(wb, wb[aba], df)
            mudou = True
        if mudou:
            wb.calculation.fullCalcOnLoad = True
            wb.save(caminho)
            print(f'{nome}: salva; as fórmulas são recalculadas ao abrir no Excel')
    print('Etapa 4 concluída.')


if __name__ == '__main__':
    main()
