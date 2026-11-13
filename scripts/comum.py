"""Constantes e funções usadas por mais de um script."""
import os
import struct
import sys

import numpy as np

ANOS = (2022, 2023, 2024)

# UF pelo código IBGE (dois primeiros dígitos do município)
UFS = [
    ('11', 'RO', 'Rondônia', 'Norte'), ('12', 'AC', 'Acre', 'Norte'), ('13', 'AM', 'Amazonas', 'Norte'),
    ('14', 'RR', 'Roraima', 'Norte'), ('15', 'PA', 'Pará', 'Norte'), ('16', 'AP', 'Amapá', 'Norte'),
    ('17', 'TO', 'Tocantins', 'Norte'), ('21', 'MA', 'Maranhão', 'Nordeste'), ('22', 'PI', 'Piauí', 'Nordeste'),
    ('23', 'CE', 'Ceará', 'Nordeste'), ('24', 'RN', 'Rio Grande do Norte', 'Nordeste'),
    ('25', 'PB', 'Paraíba', 'Nordeste'), ('26', 'PE', 'Pernambuco', 'Nordeste'), ('27', 'AL', 'Alagoas', 'Nordeste'),
    ('28', 'SE', 'Sergipe', 'Nordeste'), ('29', 'BA', 'Bahia', 'Nordeste'), ('31', 'MG', 'Minas Gerais', 'Sudeste'),
    ('32', 'ES', 'Espírito Santo', 'Sudeste'), ('33', 'RJ', 'Rio de Janeiro', 'Sudeste'),
    ('35', 'SP', 'São Paulo', 'Sudeste'), ('41', 'PR', 'Paraná', 'Sul'), ('42', 'SC', 'Santa Catarina', 'Sul'),
    ('43', 'RS', 'Rio Grande do Sul', 'Sul'), ('50', 'MS', 'Mato Grosso do Sul', 'Centro-Oeste'),
    ('51', 'MT', 'Mato Grosso', 'Centro-Oeste'), ('52', 'GO', 'Goiás', 'Centro-Oeste'),
    ('53', 'DF', 'Distrito Federal', 'Centro-Oeste'),
]
UF = {c: s for c, s, _, _ in UFS}

# capitais (código de 6 dígitos); o DF inteiro conta como capital
CAPITAIS = {'110020', '120040', '130260', '140010', '150140', '160030', '172100', '211130', '221100',
            '230440', '240810', '250750', '261160', '270430', '280030', '292740', '310620', '320530',
            '330455', '355030', '410690', '420540', '431490', '500270', '510340', '520870'}

# faixas etárias: 0 = 0-14, 1 = 15-19, ..., 10 = 60-64, 11 = 65 ou mais, 12 = ignorada
LIMITES_FAIXA = [-1, 14, 19, 24, 29, 34, 39, 44, 49, 54, 59, 64, 200]
IDADE_IGNORADA = 999

# valor de um ano de vida produtiva e PIB (IBGE, Contas Nacionais Trimestrais, 4º tri/2024)
PIB_PER_CAPITA_2024 = 55247.45
PIB_2024 = 11.7e12
LIMITE_APVP = 65


def pasta_dados():
    """Pasta de trabalho: 1º argumento da linha de comando ou ./dados."""
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'dados')
    return os.path.abspath(p)


def ler_dbf(caminho, colunas=None):
    """Lê uma tabela .dbf (dBase III) sem dependências externas. Devolve {coluna: array de bytes}."""
    with open(caminho, 'rb') as f:
        cab = f.read(32)
        n, tam_cab, tam_reg = struct.unpack('<IHH', cab[4:12])
        campos, pos = [], 1
        while True:
            d = f.read(32)
            if d[0] == 0x0D:
                break
            nome = d[:11].split(b'\0')[0].decode('latin-1')
            tam = d[16]
            campos.append((nome, pos, tam))
            pos += tam
    mm = np.memmap(caminho, dtype=np.uint8, mode='r', offset=tam_cab, shape=(n, tam_reg))
    vivos = mm[:, 0] != ord('*')  # registros apagados começam com '*'
    out = {}
    for nome, p, tam in campos:
        if colunas is None or nome in colunas:
            col = np.ascontiguousarray(mm[vivos, p:p + tam]).view(f'S{tam}').ravel()
            out[nome] = np.char.strip(col.astype(str))
    return out


def idade_em_anos(codigo):
    """Campo IDADE do SIM: 1º dígito = unidade (0-3 menos de 1 ano, 4 anos, 5 = 100 + anos); 999/vazio = ignorada."""
    if len(codigo) != 3 or not codigo.isdigit() or codigo == '999':
        return IDADE_IGNORADA
    u = int(codigo[0])
    if u <= 3:
        return 0
    if u == 4:
        return int(codigo[1:])
    if u == 5:
        return 100 + int(codigo[1:])
    return IDADE_IGNORADA


def faixa_de(idade):
    """Código da faixa etária a partir da idade em anos (vetorizado)."""
    idade = np.asarray(idade)
    f = np.searchsorted(LIMITES_FAIXA, np.minimum(idade, 200), side='left') - 1
    return np.where(idade == IDADE_IGNORADA, 12, f)


def apvp_de(idade):
    """Anos potenciais de vida produtiva perdidos por vítima: 65 - idade (15 a 64); 50 (0 a 14); 0 (65+ ou ignorada)."""
    idade = np.asarray(idade)
    return np.where(idade == IDADE_IGNORADA, 0,
                    np.where(idade < 15, LIMITE_APVP - 15, np.where(idade < LIMITE_APVP, LIMITE_APVP - idade, 0)))
