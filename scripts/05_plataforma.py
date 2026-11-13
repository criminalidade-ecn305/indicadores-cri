"""Etapa 5: grava os dados da etapa 2 na plataforma (plataforma/plataforma_criminalidade.html).

Uso: python 05_plataforma.py [pasta_de_dados]

A plataforma é um único arquivo HTML que recalcula os recortes no navegador a partir de dois cubos embutidos na
linha "const DADOS = ...": homicídios por ano, UF, porte, sexo, idade exata, local, meio e intervenção legal (h) e
população por ano, UF, porte, sexo e idade simples (p). O script substitui os cubos, os valores ausentes, a lista
de UFs e os valores monetários. A malha das UFs (topoUF, IBGE, API de malhas) é um dado fixo e não é alterada.
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

from comum import ANOS, IDADE_IGNORADA, PIB_2024, PIB_PER_CAPITA_2024, UFS, pasta_dados

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HTML = os.path.join(RAIZ, 'plataforma', 'plataforma_criminalidade.html')
PREFIXO = 'const DADOS = '


def main():
    bases = os.path.join(pasta_dados(), 'bases')
    micro = pd.read_csv(os.path.join(bases, 'homicidios_microdados.csv'), usecols=[
        'ano', 'uf', 'porte', 'sexo', 'idade', 'local', 'meio', 'interv_legal'])
    pop = pd.read_csv(os.path.join(bases, 'populacao_idade.csv'))
    with open(os.path.join(bases, 'valores_ausentes.json'), encoding='utf-8') as f:
        miss = json.load(f)

    ufi = {s: i for i, (_, s, _, _) in enumerate(UFS)}
    sx = {'F': 0, 'M': 1, 'I': 2}
    idade = np.where(micro.idade == IDADE_IGNORADA, 101, np.minimum(micro.idade, 100))
    h = (micro.assign(ano=micro.ano - ANOS[0], uf=micro.uf.map(ufi), sexo=micro.sexo.map(sx), idade=idade)
         .groupby(['ano', 'uf', 'porte', 'sexo', 'idade', 'local', 'meio', 'interv_legal']).size()
         .reset_index(name='n').rename(columns={'interv_legal': 'il'}))
    p = (pop.assign(ano=pop.ano - ANOS[0], uf=pop.uf.map(ufi), sexo=pop.sexo.map(sx))
         .groupby(['ano', 'uf', 'porte', 'sexo', 'idade'])['pop'].sum().reset_index())

    with open(HTML, encoding='utf-8') as f:
        linhas = f.read().split('\n')
    i = [k for k, l in enumerate(linhas) if l.startswith(PREFIXO)]
    assert len(i) == 1, 'linha dos dados não encontrada'
    dados = json.loads(linhas[i[0]][len(PREFIXO):].rstrip().rstrip(';'))
    dados['ufs'] = [{'uf': s, 'cod': c, 'nome': n, 'reg': r} for c, s, n, r in UFS]
    dados['h'] = {c: h[c].astype(int).tolist() for c in h.columns}
    dados['p'] = {c: p[c].astype(int).tolist() for c in p.columns}
    dados['val'] = {'pibpc': PIB_PER_CAPITA_2024, 'pib': PIB_2024}
    dados['miss'] = miss
    dados['gerado'] = dt.date.today().strftime('%d/%m/%Y')
    linhas[i[0]] = PREFIXO + json.dumps(dados, ensure_ascii=False, separators=(',', ':')) + ';'
    with open(HTML, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(linhas))
    print(f'  cubo de homicídios: {len(h):,} combinações ({h.n.sum():,} óbitos); população: {len(p):,} combinações')
    print('Etapa 5 concluída.')


if __name__ == '__main__':
    main()
