"""Etapa 3: calcula os indicadores CRI-001 e CRI-002 diretamente em pandas, a partir das bases da etapa 2.

Uso: python 03_resultados.py [pasta_de_dados]

O cálculo é independente das planilhas: serve para conferir as fórmulas do Excel (etapa 6) e gera os números
citados nas notas metodológicas (testes de sensibilidade, contagens por etapa, resultados por UF e sexo).
Saída em <pasta>/resultados/: um CSV por tabela e resumo_das_notas.txt.
"""
import json
import os

import numpy as np
import pandas as pd

from comum import ANOS, IDADE_IGNORADA, LIMITE_APVP, PIB_2024, PIB_PER_CAPITA_2024, UFS, pasta_dados

PERIODOS = [(str(a), a, a) for a in ANOS] + [('Média 2022-2024', ANOS[0], ANOS[-1])]
RECORTE = range(1, 11)  # faixas 15-19 a 60-64
TERRITORIOS = [('BR', 'Brasil', 'Brasil')] + [(s, n, r) for _, s, n, r in UFS]
SEXOS = [('Mulheres', 'F'), ('Homens', 'M'), ('Todos', '*')]
# população-padrão da OMS (AHMAD et al., 2001), faixas de 15-19 a 60-64
OMS = np.array([8.47, 8.22, 7.93, 7.61, 7.15, 6.59, 6.04, 5.37, 4.55, 3.72])


def recorte_periodo(df, a0, a1, uf):
    x = df[(df.ano >= a0) & (df.ano <= a1)]
    return x if uf == 'BR' else x[x.uf == uf]


def tx(num, den):
    return num / den * 100000 if den else np.nan


def pesos_brasil_2022(bp, sexo):
    p = bp[(bp.ano == 2022) & (bp.sexo == sexo) & bp.faixa.isin(RECORTE)].groupby('faixa').populacao.sum()
    return (p / p.sum()).reindex(RECORTE).to_numpy()


def taxas_por_faixa(bh, bp, a0, a1, uf, sexo):
    h = recorte_periodo(bh, a0, a1, uf)
    p = recorte_periodo(bp, a0, a1, uf)
    hf = h[h.sexo == sexo].groupby('faixa').homicidios.sum().reindex(range(12), fill_value=0)
    pf = p[p.sexo == sexo].groupby('faixa').populacao.sum().reindex(range(12), fill_value=0)
    t = np.where(pf > 0, hf / pf.replace(0, np.nan) * 100000, 0.0)
    return hf, pf, pd.Series(t, index=range(12))


def cri001(bh, bp):
    w = {s: pesos_brasil_2022(bp, s) for s in 'FM'}
    uf_rows, faixa_rows, local_rows, meio_rows, porte_rows = [], [], [], [], []
    for per, a0, a1 in PERIODOS:
        n_anos = a1 - a0 + 1
        for uf, nome, reg in TERRITORIOS:
            h = recorte_periodo(bh, a0, a1, uf)
            p = recorte_periodo(bp, a0, a1, uf)
            hr, pr = h[h.faixa.isin(RECORTE)], p[p.faixa.isin(RECORTE)]
            HF, PF = hr[hr.sexo == 'F'].homicidios.sum(), pr[pr.sexo == 'F'].populacao.sum()
            HM, PM = hr[hr.sexo == 'M'].homicidios.sum(), pr[pr.sexo == 'M'].populacao.sum()
            HFsil = hr[(hr.sexo == 'F') & (hr.interv_legal == 0)].homicidios.sum()
            fx = {}
            for s in 'FM':
                hf, pf, t = taxas_por_faixa(bh, bp, a0, a1, uf, s)
                fx[s] = (hf, pf, t)
            padF = float((fx['F'][2].loc[list(RECORTE)].to_numpy() * w['F']).sum())
            padM = float((fx['M'][2].loc[list(RECORTE)].to_numpy() * w['M']).sum())
            uf_rows.append({'Período': per, 'UF': uf, 'Homicídios de mulheres no período': HF,
                            'Homicídios de mulheres por ano': HF / n_anos, 'População feminina (soma do período)': PF,
                            'Taxa bruta mulheres (por 100 mil)': tx(HF, PF), 'Taxa padronizada mulheres': padF,
                            'Menos de 20 casos': 'Sim' if HF < 20 else 'Não',
                            'Homicídios de mulheres sem intervenção legal': HFsil,
                            'Taxa mulheres sem intervenção legal': tx(HFsil, PF),
                            'Homicídios de homens no período': HM, 'População masculina (soma do período)': PM,
                            'Taxa bruta homens (por 100 mil)': tx(HM, PM), 'Taxa padronizada homens': padM,
                            'Razão taxa homens / taxa mulheres': tx(HM, PM) / tx(HF, PF) if HF else np.nan,
                            'Mulheres entre as vítimas (%)': HF / (HF + HM) * 100 if HF + HM else np.nan})
            for k in range(12):
                faixa_rows.append({'Período': per, 'UF': uf, 'Código faixa': k,
                                   'Homicídios de mulheres': fx['F'][0][k], 'População feminina': fx['F'][1][k],
                                   'Taxa mulheres (por 100 mil)': tx(fx['F'][0][k], fx['F'][1][k]),
                                   'Homicídios de homens': fx['M'][0][k], 'População masculina': fx['M'][1][k],
                                   'Taxa homens (por 100 mil)': tx(fx['M'][0][k], fx['M'][1][k])})
            hrF = hr[hr.sexo == 'F']
            for col, destino in (('local', local_rows), ('meio', meio_rows)):
                for k in range(4):
                    n = hrF[hrF[col] == k].homicidios.sum()
                    destino.append({'Período': per, 'UF': uf, 'Código': k, 'Homicídios de mulheres': n,
                                    '% do total do território': n / HF * 100 if HF else np.nan,
                                    'População feminina (soma do período)': PF, 'Taxa por 100 mil mulheres': tx(n, PF)})
            for k in range(4):
                hk = hr[hr.porte == k]
                pk = pr[pr.porte == k]
                a, b = hk[hk.sexo == 'F'].homicidios.sum(), pk[pk.sexo == 'F'].populacao.sum()
                c, d = hk[hk.sexo == 'M'].homicidios.sum(), pk[pk.sexo == 'M'].populacao.sum()
                porte_rows.append({'Período': per, 'UF': uf, 'Código porte': k, 'Homicídios de mulheres': a,
                                   'População feminina': b, 'Taxa mulheres (por 100 mil)': tx(a, b),
                                   'Homicídios de homens': c, 'População masculina': d,
                                   'Taxa homens (por 100 mil)': tx(c, d)})
    uf = pd.DataFrame(uf_rows)
    ufs = uf.UF != 'BR'
    uf['Posição (taxa bruta mulheres)'] = np.nan
    for per in uf.Período.unique():
        m = ufs & (uf.Período == per)
        uf.loc[m, 'Posição (taxa bruta mulheres)'] = uf.loc[m, 'Taxa bruta mulheres (por 100 mil)'].rank(
            ascending=False, method='min')
    return {'cri001_por_uf': uf, 'cri001_faixa_etaria': pd.DataFrame(faixa_rows),
            'cri001_local': pd.DataFrame(local_rows), 'cri001_meio': pd.DataFrame(meio_rows),
            'cri001_porte': pd.DataFrame(porte_rows)}


def cri002(bh, bp):
    uf_rows, faixa_rows = [], []
    for per, a0, a1 in PERIODOS:
        n_anos = a1 - a0 + 1
        for uf, nome, reg in TERRITORIOS:
            h = recorte_periodo(bh, a0, a1, uf)
            p = recorte_periodo(bp, a0, a1, uf)
            for sexo_nome, s in SEXOS:
                hs = h if s == '*' else h[h.sexo == s]
                ps = p if s == '*' else p[p.sexo == s]
                hr = hs[hs.faixa.isin(RECORTE)]
                V, A, POP = hr.homicidios.sum(), hr.apvp.sum(), ps.populacao.sum()
                uf_rows.append({'Período': per, 'Código sexo': s, 'UF': uf, 'Vítimas no recorte, período': V,
                                'Vítimas por ano': V / n_anos, 'APVP no período': A, 'APVP por ano': A / n_anos,
                                'População do sexo, todas as idades (soma do período)': POP,
                                'APVP por 100 mil habitantes': tx(A, POP), 'APVP médio por vítima': A / V if V else np.nan,
                                'Perda por ano (R$)': A / n_anos * PIB_PER_CAPITA_2024,
                                'Perda por habitante por ano (R$)': A * PIB_PER_CAPITA_2024 / POP,
                                'Perda por ano em % do PIB 2024': A / n_anos * PIB_PER_CAPITA_2024 / PIB_2024 * 100})
                if s == '*':
                    continue  # a aba "Faixa etária" da planilha traz só mulheres e homens, faixas 0-14 a 60-64
                g = hs.groupby('faixa')[['homicidios', 'apvp']].sum().reindex(range(11), fill_value=0)
                for k in range(11):
                    faixa_rows.append({'Período': per, 'Código sexo': s, 'UF': uf, 'Código faixa': k,
                                       'Vítimas no período': g.homicidios[k], 'APVP no período': g.apvp[k],
                                       'APVP por ano': g.apvp[k] / n_anos})
    uf = pd.DataFrame(uf_rows)
    uf['Posição (APVP por 100 mil)'] = np.nan
    for (per, s), _ in uf.groupby(['Período', 'Código sexo']):
        m = (uf.UF != 'BR') & (uf.Período == per) & (uf['Código sexo'] == s)
        uf.loc[m, 'Posição (APVP por 100 mil)'] = uf.loc[m, 'APVP por 100 mil habitantes'].rank(ascending=False, method='min')
    return {'cri002_por_uf': uf, 'cri002_faixa_etaria': pd.DataFrame(faixa_rows)}


def resumo_das_notas(micro, bh, bp, r1, r2, contagens):
    """Números citados nas notas, recalculados a partir dos dados."""
    L = []
    def limpa(v):
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, np.floating):
            return float(v)
        if isinstance(v, (list, tuple)):
            return type(v)(limpa(x) for x in v)
        if isinstance(v, dict):
            return {limpa(k): limpa(x) for k, x in v.items()}
        return v

    def linha(texto, valor):
        L.append(f'{texto}: {limpa(valor)}')
    tri = r1['cri001_por_uf'][r1['cri001_por_uf'].Período == 'Média 2022-2024'].set_index('UF')
    u = tri.drop('BR')
    # CRI-001, Tabela 2
    m = micro
    linha('Homicídios no SIM por ano', m.groupby('ano').size().to_dict())
    linha('Homicídios no SIM, total', len(m))
    linha('Vítimas do sexo masculino', int((m.sexo == 'M').sum()))
    linha('Vítimas com sexo ignorado', int((m.sexo == 'I').sum()))
    f = m[m.sexo == 'F']
    linha('Mulheres com idade ignorada', int((f.idade == IDADE_IGNORADA).sum()))
    linha('Mulheres de 0 a 14 anos', int((f.idade < 15).sum()))
    fr = f[(f.idade >= 15) & (f.idade <= 64)]
    linha('Mulheres de 65 anos ou mais', int(((f.idade >= 65) & (f.idade != IDADE_IGNORADA)).sum()))
    linha('Mulheres de 15 a 64 anos', len(fr))
    linha('Parcela das vítimas mulheres de idade conhecida com 15 a 64 anos (%)',
          round(len(fr) / (f.idade != IDADE_IGNORADA).sum() * 100, 1))
    linha('Mulheres 15-64: no domicílio (%)', round((fr.local == 0).mean() * 100, 1))
    linha('Mulheres 15-64: arma de fogo (%)', round((fr.meio == 0).mean() * 100, 1))
    linha('Mulheres 15-64: intervenção legal (%)', round(fr.interv_legal.mean() * 100, 2))
    linha('Mulheres, todas as idades: idade ignorada (%)', round((f.idade == IDADE_IGNORADA).mean() * 100, 2))
    linha('Mulheres, todas as idades: local ignorado (%)', round(f.lococor.isin(['9', '']).mean() * 100, 2))
    linha('Mulheres, todas as idades: meio não especificado, Y09 (%)', round((f.cid.str[:3] == 'Y09').mean() * 100, 2))
    linha('Mulheres, todas as idades: escolaridade ignorada (%)', round(f.esc_ignorada.mean() * 100, 1))
    linha('Homicídios de mulheres, todas as idades, por ano', f.groupby('ano').size().to_dict())
    # CRI-001, taxas
    br = tri.loc['BR']
    linha('CRI-001 Brasil 2022-2024: óbitos', int(br['Homicídios de mulheres no período']))
    linha('CRI-001 Brasil 2022-2024: população', int(br['População feminina (soma do período)']))
    linha('CRI-001 Brasil 2022-2024: taxa bruta', round(br['Taxa bruta mulheres (por 100 mil)'], 2))
    linha('CRI-001 Brasil 2022-2024: taxa padronizada', round(br['Taxa padronizada mulheres'], 2))
    anos = r1['cri001_por_uf'][(r1['cri001_por_uf'].UF == 'BR') & (r1['cri001_por_uf'].Período != 'Média 2022-2024')]
    linha('CRI-001 Brasil, taxa bruta por ano', dict(zip(anos.Período, anos['Taxa bruta mulheres (por 100 mil)'].round(2))))
    linha('CRI-001 Acre 2022-2024: óbitos, bruta, padronizada',
          (int(u.loc['AC', 'Homicídios de mulheres no período']), round(u.loc['AC', 'Taxa bruta mulheres (por 100 mil)'], 2),
           round(u.loc['AC', 'Taxa padronizada mulheres'], 2)))
    w = pesos_brasil_2022(bp, 'F')
    linha('Pesos da população-padrão, Brasil 2022 (%)', [round(x * 100, 2) for x in w])
    rb = u['Taxa bruta mulheres (por 100 mil)'].rank(ascending=False)
    rp = u['Taxa padronizada mulheres'].rank(ascending=False)
    linha('Bruta x padronizada: correlação de postos', round(rb.corr(rp), 3))
    mud = (rb != rp)
    linha('Bruta x padronizada: UFs que mudam de posição; maior mudança',
          (int(mud.sum()), int((rb - rp).abs().max()), (rb - rp).abs().idxmax()))
    # padrão OMS
    wo = OMS / OMS.sum()
    def pad(uf, pesos):
        _, _, t = taxas_por_faixa(bh, bp, 2022, 2024, uf, 'F')
        return float((t.loc[list(RECORTE)].to_numpy() * pesos).sum())
    po = pd.Series({s: pad(s, wo) for s in u.index})
    linha('Padrão OMS: Brasil', round(pad('BR', wo), 2))
    ro = po.rank(ascending=False)
    linha('Padrão OMS x Brasil 2022: correlação de postos', round(ro.corr(rp), 3))
    linha('Padrão OMS x Brasil 2022: UFs que trocam de posição', sorted(ro[ro != rp].index))
    linha('Excluir intervenções legais: Brasil', round(br['Taxa mulheres sem intervenção legal'], 2))
    ign = int((f.idade == IDADE_IGNORADA).sum())
    linha('Redistribuir idade ignorada: Brasil',
          round(len(fr) * len(f) / (len(f) - ign) / br['População feminina (soma do período)'] * 100000, 2))
    dif = (u['Taxa padronizada mulheres'] - u['Taxa bruta mulheres (por 100 mil)'])
    linha('Diferença média absoluta padronizada - bruta', round(dif.abs().mean(), 2))
    linha('UFs com menos de 20 óbitos (ano isolado)',
          sorted(r1['cri001_por_uf'].query("UF != 'BR' and Período != 'Média 2022-2024' and `Menos de 20 casos` == 'Sim'").UF.unique()))
    linha('UFs com menos de 20 óbitos (triênio)', sorted(u[u['Menos de 20 casos'] == 'Sim'].index))
    # Atlas: todas as idades, 2024
    pf24 = bp[(bp.ano == 2024) & (bp.sexo == 'F')].populacao.sum()
    linha('Taxa de homicídio de mulheres 2024, todas as idades, POPSVS', round((f.ano == 2024).sum() / pf24 * 100000, 2))
    linha('Óbitos de intenção indeterminada (Y10-Y34), todos os óbitos, por ano', contagens['indeterminados'])

    # CRI-002
    linha('CRI-002 Tabela 2: idade ignorada; 0-14; 65+; restam',
          (int((m.idade == IDADE_IGNORADA).sum()), int((m.idade < 15).sum()),
           int(((m.idade >= 65) & (m.idade != IDADE_IGNORADA)).sum()),
           int(((m.idade >= 15) & (m.idade <= 64)).sum())))
    v = m[(m.idade >= 15) & (m.idade <= 64)]
    linha('CRI-002 vítimas 15-64 por sexo', v.groupby('sexo').size().to_dict())
    t2 = r2['cri002_por_uf']
    t2t = t2[(t2.Período == 'Média 2022-2024') & (t2.UF == 'BR')].set_index('Código sexo')
    for s in ('F', 'M', '*'):
        x = t2t.loc[s]
        linha(f'CRI-002 Brasil {s}: vítimas/ano, APVP/ano, anos/vítima, APVP/100 mil, perda (R$ bi)',
              (round(x['Vítimas por ano']), round(x['APVP por ano']), round(x['APVP médio por vítima'], 1),
               round(x['APVP por 100 mil habitantes'], 1), round(x['Perda por ano (R$)'] / 1e9, 1)))
    linha('CRI-002 perda em % do PIB', round(t2t.loc['*', 'Perda por ano em % do PIB 2024'], 2))
    an = t2[(t2.UF == 'BR') & (t2['Código sexo'] == '*') & (t2.Período != 'Média 2022-2024')]
    linha('CRI-002 APVP por ano', dict(zip(an.Período, an['APVP no período'])))
    ac = t2[(t2.Período == 'Média 2022-2024') & (t2.UF == 'AC') & (t2['Código sexo'] == '*')].iloc[0]
    linha('CRI-002 Acre: APVP/ano, população média, APVP/100 mil, perda (R$ mi)',
          (round(ac['APVP por ano']), round(ac['População do sexo, todas as idades (soma do período)'] / 3),
           round(ac['APVP por 100 mil habitantes'], 1), round(ac['Perda por ano (R$)'] / 1e6, 1)))
    linha('Uma vítima de 30 anos: anos e valor', (LIMITE_APVP - 30, round((LIMITE_APVP - 30) * PIB_PER_CAPITA_2024)))
    # sensibilidade do limite
    pop_tri = bp.groupby('uf').populacao.sum()
    base_rank = (v.assign(a=LIMITE_APVP - v.idade).groupby('uf').a.sum() / pop_tri).rank(ascending=False)
    for lim, sexo in ((60, None), (70, None), (62, 'F')):
        x = m[(m.idade >= 15) & (m.idade < lim)]
        ref = v
        if sexo:
            x, ref = x[x.sexo == sexo], v[v.sexo == sexo]
        tot = (lim - x.idade).sum() / 3
        ref_tot = (LIMITE_APVP - ref.idade).sum() / 3
        txt = f'Limite de {lim} anos' + (' (mulheres)' if sexo else '')
        extra = ''
        if not sexo:
            rk = (x.assign(a=lim - x.idade).groupby('uf').a.sum() / pop_tri).rank(ascending=False)
            extra = f'; UFs que mudam de posição: {int((rk != base_rank).sum())}, maior mudança {int((rk - base_rank).abs().max())}'
        linha(txt, f'{round(tot):,} anos por ano ({(tot / ref_tot - 1) * 100:+.1f}%){extra}')
    return '\n'.join(L)


def main():
    pasta = pasta_dados()
    bases = os.path.join(pasta, 'bases')
    saida = os.path.join(pasta, 'resultados')
    os.makedirs(saida, exist_ok=True)
    bh = pd.read_csv(os.path.join(bases, 'base_homicidios.csv'))
    bp = pd.read_csv(os.path.join(bases, 'base_populacao.csv'))
    micro = pd.read_csv(os.path.join(bases, 'homicidios_microdados.csv'), dtype={'lococor': str, 'cid': str},
                        keep_default_na=False)
    with open(os.path.join(bases, 'contagens_sim.json'), encoding='utf-8') as f:
        contagens = json.load(f)
    r1, r2 = cri001(bh, bp), cri002(bh, bp)
    for nome, df in {**r1, **r2}.items():
        df.to_csv(os.path.join(saida, nome + '.csv'), index=False)
    txt = resumo_das_notas(micro, bh, bp, r1, r2, contagens)
    with open(os.path.join(saida, 'resumo_das_notas.txt'), 'w', encoding='utf-8') as f:
        f.write(txt + '\n')
    print(txt)
    print('Etapa 3 concluída.')


if __name__ == '__main__':
    main()
