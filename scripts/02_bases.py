"""Etapa 2: lê os microdados convertidos e monta as bases agregadas usadas nas planilhas e na plataforma.

Uso: python 02_bases.py [pasta_de_dados]

Entrada: <pasta>/dbf/DOBR{ano}.dbf e <pasta>/dbf/POPSBR{aa}.dbf (etapa 1).
Saída em <pasta>/bases/:
  homicidios_microdados.csv  um registro por homicídio (134.746 em 2022-2024), com os campos já codificados
  base_homicidios.csv        aba "Base homicídios": ano, uf, porte, sexo, faixa, local, meio, interv_legal, homicidios, apvp
  base_populacao.csv         aba "Base população": ano, uf, porte, sexo, faixa, populacao
  base_idade_exata.csv       aba "Base idade exata": ano, uf, sexo, idade, interv_legal, homicidios
  populacao_idade.csv        população por ano, UF, porte, sexo e idade simples (denominadores da plataforma)
  valores_ausentes.json      campos sem informação, por ano e sexo
  contagens_sim.json         óbitos, homicídios e mortes de intenção indeterminada (Y10-Y34) por ano, no SIM inteiro
"""
import json
import os

import numpy as np
import pandas as pd

from comum import ANOS, CAPITAIS, IDADE_IGNORADA, UF, apvp_de, faixa_de, idade_em_anos, ler_dbf, pasta_dados

CHAVES = ['ano', 'uf', 'porte', 'sexo', 'faixa', 'local', 'meio', 'interv_legal']


def ler_populacao(pasta):
    partes = []
    for a in ANOS:
        p = ler_dbf(os.path.join(pasta, 'dbf', f'POPSBR{a % 100:02d}.dbf'), ['COD_MUN', 'ANO', 'SEXO', 'IDADE', 'POP'])
        partes.append(pd.DataFrame({'mun': p['COD_MUN'], 'ano': p['ANO'].astype(int), 'sexo': p['SEXO'],
                                    'idade': p['IDADE'].astype(int), 'pop': p['POP'].astype(np.int64)}))
    pop = pd.concat(partes, ignore_index=True)
    assert set(pop.ano) == set(ANOS), set(pop.ano)
    assert set(pop.sexo) <= {'1', '2'}, set(pop.sexo)
    return pop


def porte(m6, pop_mun_2024):
    """0 capital (DF inteiro), 1 interior 100 mil+, 2 interior 20-100 mil, 3 interior <20 mil, 4 município ignorado."""
    pm = m6.map(pop_mun_2024)
    return np.select([m6.str.endswith('0000'), m6.str[:2].eq('53') | m6.isin(CAPITAIS), pm >= 100000, pm >= 20000],
                     [4, 0, 1, 2], 3)


def ler_homicidios(pasta):
    """Seleciona os homicídios (CID-10 X85-Y09, Y35-Y36) e conta, no SIM inteiro, óbitos e mortes de intenção indeterminada."""
    partes, contagens = [], {'obitos': {}, 'homicidios': {}, 'indeterminados': {}}
    for a in ANOS:
        o = ler_dbf(os.path.join(pasta, 'dbf', f'DOBR{a}.dbf'),
                    ['CAUSABAS', 'SEXO', 'IDADE', 'CODMUNRES', 'LOCOCOR', 'ESC2010'])
        c3 = np.array([c[:3] for c in o['CAUSABAS']])
        hom = ((c3 >= 'X85') & (c3 <= 'Y09')) | (c3 == 'Y35') | (c3 == 'Y36')
        indet = (c3 >= 'Y10') & (c3 <= 'Y34')
        d = pd.DataFrame({k: v[hom] for k, v in o.items()})
        d.insert(0, 'ano', a)
        contagens['obitos'][a] = int(len(c3))
        contagens['homicidios'][a] = int(hom.sum())
        contagens['indeterminados'][a] = int(indet.sum())
        print(f'  SIM {a}: {len(c3):,} óbitos, {hom.sum():,} homicídios, {indet.sum():,} de intenção indeterminada')
        partes.append(d)
    return pd.concat(partes, ignore_index=True), contagens


def main():
    pasta = pasta_dados()
    saida = os.path.join(pasta, 'bases')
    os.makedirs(saida, exist_ok=True)

    # população e porte dos municípios (população de 2024)
    pop = ler_populacao(pasta)
    pop['m6'] = pop.mun.str[:6]
    pop_mun_2024 = pop[pop.ano == 2024].groupby('m6')['pop'].sum()

    # homicídios: seleção e codificação
    d, contagens = ler_homicidios(pasta)
    with open(os.path.join(saida, 'contagens_sim.json'), 'w', encoding='utf-8') as f:
        json.dump(contagens, f, indent=1)
    d['uf'] = d.CODMUNRES.str[:2].map(UF)
    assert d.uf.notna().all(), 'há óbito sem UF de residência válida'
    d['sexo'] = d.SEXO.map({'1': 'M', '2': 'F'}).fillna('I')
    d['idade'] = d.IDADE.map(idade_em_anos)
    d['faixa'] = faixa_de(d.idade)
    d['local'] = d.LOCOCOR.map({'3': 0, '4': 1, '1': 2, '2': 2}).fillna(3).astype(int)
    c3, c4 = d.CAUSABAS.str[:3], d.CAUSABAS.str[:4]
    d['meio'] = np.select([c3.isin(['X93', 'X94', 'X95']) | (c4 == 'Y350'),
                           c3.eq('X99') | (c4 == 'Y354'),
                           c3.isin(['X91', 'Y00', 'Y04'])], [0, 1, 2], 3)
    d['interv_legal'] = c3.isin(['Y35', 'Y36']).astype(int)
    d['porte'] = porte(d.CODMUNRES.str[:6], pop_mun_2024)
    sem_pop = (d.porte == 3) & d.CODMUNRES.str[:6].map(pop_mun_2024).isna()
    assert not sem_pop.any(), f'{sem_pop.sum()} homicídios em municípios sem população'
    d['apvp'] = apvp_de(d.idade)
    d['esc_ignorada'] = (~d.ESC2010.isin(['0', '1', '2', '3', '4', '5'])).astype(int)
    d['cid'] = d.CAUSABAS
    d['lococor'] = d.LOCOCOR
    micro = d[['ano', 'uf', 'porte', 'sexo', 'idade', 'faixa', 'local', 'meio', 'interv_legal', 'apvp',
               'esc_ignorada', 'cid', 'lococor']]
    micro.to_csv(os.path.join(saida, 'homicidios_microdados.csv'), index=False)

    # aba "Base homicídios"
    bh = (micro.groupby(CHAVES, as_index=False)
          .agg(homicidios=('apvp', 'size'), apvp=('apvp', 'sum'))
          .sort_values(CHAVES))
    bh.to_csv(os.path.join(saida, 'base_homicidios.csv'), index=False)

    # aba "Base idade exata": idade 0 a 100 (100 = 100 ou mais) e 101 = ignorada
    ie = micro.assign(idade=np.where(micro.idade == IDADE_IGNORADA, 101, np.minimum(micro.idade, 100)))
    bi = (ie.groupby(['ano', 'uf', 'sexo', 'idade', 'interv_legal']).size()
          .reset_index(name='homicidios'))
    bi.to_csv(os.path.join(saida, 'base_idade_exata.csv'), index=False)

    # aba "Base população" e população por idade simples
    pop['uf'] = pop.mun.str[:2].map(UF)
    assert pop.uf.notna().all()
    pop['sexo'] = pop.sexo.map({'1': 'M', '2': 'F'})
    pop['porte'] = porte(pop.m6, pop_mun_2024)
    pop['faixa'] = faixa_de(pop.idade)
    bp = (pop.groupby(['ano', 'uf', 'porte', 'sexo', 'faixa'], as_index=False)['pop'].sum()
          .rename(columns={'pop': 'populacao'}))
    bp.to_csv(os.path.join(saida, 'base_populacao.csv'), index=False)
    pi = pop.groupby(['ano', 'uf', 'porte', 'sexo', 'idade'], as_index=False)['pop'].sum()
    pi.to_csv(os.path.join(saida, 'populacao_idade.csv'), index=False)

    # valores ausentes
    def ausentes(x):
        return {'total': len(x), 'sexo': int((x.sexo == 'I').sum()), 'idade': int((x.idade == IDADE_IGNORADA).sum()),
                'mun': int((x.porte == 4).sum()), 'local': int(x.lococor.isin(['9', '']).sum()),
                'meio': int((x.cid.str[:3] == 'Y09').sum()), 'esc': int(x.esc_ignorada.sum())}
    miss = {}
    for nome, x in (('todos', micro), ('mulheres', micro[micro.sexo == 'F'])):
        miss[nome] = {str(a): ausentes(x[x.ano == a]) for a in ANOS}
        miss[nome]['2022-2024'] = ausentes(x)
    e = micro.groupby('uf').esc_ignorada.mean() * 100
    miss['escUF'] = {'max': round(float(e.max()), 1), 'ufMax': e.idxmax(),
                     'min': round(float(e.min()), 1), 'ufMin': e.idxmin()}
    with open(os.path.join(saida, 'valores_ausentes.json'), 'w', encoding='utf-8') as f:
        json.dump(miss, f, ensure_ascii=False, indent=1)

    print(f'  homicídios: {len(micro):,}; base_homicidios: {len(bh):,} linhas; base_idade_exata: {len(bi):,}; '
          f'base_populacao: {len(bp):,}; populacao_idade: {len(pi):,}')
    print('Etapa 2 concluída.')


if __name__ == '__main__':
    main()
