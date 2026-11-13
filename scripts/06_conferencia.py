"""Etapa 6: confere as saídas entre si.

Uso: python 06_conferencia.py [pasta_de_dados] [--plataforma-ref arquivo.html]

1. As abas de base das planilhas são idênticas às bases da etapa 2.
2. Os valores das fórmulas do Excel (abas Por UF, Faixa etária, Local, Meio e Porte) são iguais aos calculados
   em pandas na etapa 3. As planilhas precisam ter os valores calculados: se tiverem sido gravadas pela etapa 4
   e ainda não abertas no Excel, o script recalcula uma cópia pelo próprio Excel (Windows, pacote pywin32).
3. A aba "Valores ausentes" e a "Validação Atlas" batem com as contagens dos microdados.
4. Opcional: os cubos da plataforma são iguais aos de outro arquivo da plataforma (--plataforma-ref).
Termina com código 1 se alguma conferência falhar.
"""
import json
import math
import os
import shutil
import sys
import tempfile

import openpyxl
import pandas as pd

from comum import pasta_dados

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
I1 = 'Indicador 1 - Violência letal contra mulheres.xlsx'
I2 = 'Indicador 2 - Anos de vida produtiva perdidos.xlsx'
BC = 'Base e conferência.xlsx'
ABAS_BASE = {'Base homicídios': 'base_homicidios.csv', 'Base população': 'base_populacao.csv',
             'Base idade exata': 'base_idade_exata.csv'}
COMPARAR = [  # (planilha, aba, resultado da etapa 3, chaves)
    (I1, 'Por UF', 'cri001_por_uf', ['Período', 'UF']),
    (I1, 'Faixa etária', 'cri001_faixa_etaria', ['Período', 'UF', 'Código faixa']),
    (I1, 'Local', 'cri001_local', ['Período', 'UF', 'Código']),
    (I1, 'Meio', 'cri001_meio', ['Período', 'UF', 'Código']),
    (I1, 'Porte do município', 'cri001_porte', ['Período', 'UF', 'Código porte']),
    (I2, 'Por UF', 'cri002_por_uf', ['Período', 'Código sexo', 'UF']),
    (I2, 'Faixa etária', 'cri002_faixa_etaria', ['Período', 'Código sexo', 'UF', 'Código faixa']),
]
falhas = []


def aba(wb, nome, linha_cab=1):
    linhas = list(wb[nome].iter_rows(min_row=linha_cab, values_only=True))
    return pd.DataFrame(linhas[1:], columns=linhas[0])


def com_valores(caminho):
    """Abre a planilha com os valores calculados; se não houver, recalcula uma cópia no Excel."""
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    ws = wb['Por UF'] if 'Por UF' in wb.sheetnames else wb[wb.sheetnames[1]]
    if any(v is not None for v in next(ws.iter_rows(min_row=3, max_row=3, values_only=True))[6:]):
        return wb
    import win32com.client as win32
    tmp = os.path.join(tempfile.mkdtemp(), os.path.basename(caminho))
    shutil.copy2(caminho, tmp)
    xl = win32.DispatchEx('Excel.Application')
    xl.Visible = xl.DisplayAlerts = False
    try:
        w = xl.Workbooks.Open(tmp)
        xl.CalculateFull()
        w.Save()
        w.Close(False)
    finally:
        xl.Quit()
    print(f'  ({os.path.basename(caminho)} recalculada numa cópia pelo Excel)')
    return openpyxl.load_workbook(tmp, data_only=True, read_only=True)


def compara(res, wb_df, chaves, rotulo):
    a = res.copy()
    b = wb_df.copy()
    for c in chaves:
        a[c] = a[c].astype(str)
        b[c] = b[c].astype(str)
    m = a.merge(b, on=chaves, how='outer', suffixes=('_py', '_xl'), indicator=True)
    sem_par = int((m._merge != 'both').sum())
    m = m[m._merge == 'both']
    cols = [c for c in res.columns if c not in chaves and c in wb_df.columns]
    dif = 0
    for c in cols:
        for x, y in zip(m[c + '_py'], m[c + '_xl']):
            vazio_x = x is None or (isinstance(x, float) and math.isnan(x)) or x == ''
            vazio_y = y is None or y == ''
            if vazio_x and vazio_y:
                continue
            if isinstance(y, (int, float)) and not vazio_x and not isinstance(x, str):
                ok = math.isclose(float(x), float(y), rel_tol=1e-9, abs_tol=1e-9)
            else:
                ok = str(x) == str(y)
            if not ok:
                dif += 1
                if dif <= 3:
                    print(f'    diferença em {c}: python {x!r}, excel {y!r}')
    estado = 'ok' if dif == 0 and sem_par == 0 else 'FALHOU'
    if estado != 'ok':
        falhas.append(rotulo)
    print(f'  {rotulo}: {len(m):,} linhas x {len(cols)} colunas; sem par: {sem_par}; diferenças: {dif} [{estado}]')


def main():
    args = sys.argv[1:]
    ref = None
    if '--plataforma-ref' in args:
        k = args.index('--plataforma-ref')
        ref = args[k + 1]
        del args[k:k + 2]
    sys.argv = [sys.argv[0]] + args
    pasta = pasta_dados()
    bases, res = os.path.join(pasta, 'bases'), os.path.join(pasta, 'resultados')
    plan = os.path.join(RAIZ, 'planilhas')

    print('1. Abas de base das planilhas x bases da etapa 2')
    csv = {a: pd.read_csv(os.path.join(bases, f)) for a, f in ABAS_BASE.items()}
    for nome in (I1, I2, BC):
        wb = openpyxl.load_workbook(os.path.join(plan, nome), read_only=True)
        for a, df in csv.items():
            x = aba(wb, a)
            igual = list(x.columns) == list(df.columns) and len(x) == len(df) and all(
                (x[c].astype(str).to_numpy() == df[c].astype(str).to_numpy()).all() for c in df.columns)
            if not igual:
                falhas.append(f'{nome} / {a}')
            print(f'  {nome} / {a}: {len(df):,} linhas [{"ok" if igual else "FALHOU"}]')

    print('2. Fórmulas do Excel x cálculo em pandas (etapa 3)')
    wbs = {n: com_valores(os.path.join(plan, n)) for n in (I1, I2)}
    for nome, a, arq, chaves in COMPARAR:
        r = pd.read_csv(os.path.join(res, arq + '.csv'))
        compara(r, aba(wbs[nome], a), chaves, f'{nome[:11]} / {a}')

    print('3. Valores ausentes e totais x microdados')
    with open(os.path.join(bases, 'valores_ausentes.json'), encoding='utf-8') as f:
        miss = json.load(f)
    with open(os.path.join(bases, 'contagens_sim.json'), encoding='utf-8') as f:
        cont = json.load(f)
    wb = com_valores(os.path.join(plan, BC))
    va = {r[0]: r for r in wb['Valores ausentes'].iter_rows(min_row=3, values_only=True) if r[0]}
    campos = {'Sexo ignorado': 'sexo', 'Idade ignorada': 'idade', 'Município de residência ignorado (UF conhecida)': 'mun',
              'Local do óbito ignorado (LOCOCOR 9 ou vazio)': 'local', 'Meio não especificado (CID Y09)': 'meio',
              'Escolaridade ignorada (ESC2010 9 ou vazio)': 'esc', 'Total de homicídios': 'total'}
    erros = 0
    for rot, k in campos.items():
        esperado = [miss['todos'][p][k] for p in ('2022', '2023', '2024', '2022-2024')]
        esperado_m = miss['mulheres']['2022-2024'][k]
        linha = va[rot]
        obtido_m = linha[9]
        if list(linha[1:5]) != esperado or obtido_m != esperado_m:
            erros += 1
            print(f'    {rot}: planilha {linha[1:5]} / {obtido_m}, microdados {esperado} / {esperado_m}')
    # colunas: ano, nossa base, Atlas, diferença, mulheres (nossa base), mulheres (Atlas), diferença,
    # base por idade exata, diferença
    for r in wb['Validação Atlas'].iter_rows(min_row=2, values_only=True):
        if r[0] is None:
            continue
        a = str(int(r[0]))
        if (r[1] != cont['homicidios'][a] or r[4] != miss['mulheres'][a]['total'] or r[7] != cont['homicidios'][a]
                or any(r[i] != 0 for i in (3, 6, 8))):
            erros += 1
            print(f'    Validação Atlas {a}: {list(r)}')
    if erros:
        falhas.append('Valores ausentes / Validação Atlas')
    print(f'  Valores ausentes e Validação Atlas: {erros} diferenças [{"ok" if not erros else "FALHOU"}]')

    if ref:
        print('4. Cubos da plataforma x plataforma de referência')
        def dados(arq):
            with open(arq, encoding='utf-8') as f:
                for l in f:
                    if l.startswith('const DADOS = '):
                        return json.loads(l[len('const DADOS = '):].rstrip().rstrip(';'))
        a, b = dados(os.path.join(RAIZ, 'plataforma', 'plataforma_criminalidade.html')), dados(ref)
        for k in ('ufs', 'h', 'p', 'miss', 'topoUF'):
            ok = a[k] == b[k]
            if not ok:
                falhas.append(f'plataforma / {k}')
            print(f'  {k}: [{"ok" if ok else "FALHOU"}]')
        for k in ('pibpc', 'pib'):
            ok = a['val'][k] == b['val'][k]
            if not ok:
                falhas.append(f'plataforma / val.{k}')
            print(f'  val.{k}: [{"ok" if ok else "FALHOU"}]')

    print('Conferência concluída: ' + ('tudo confere.' if not falhas else f'FALHAS em {falhas}'))
    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    main()
