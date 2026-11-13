# Indicadores de criminalidade CRI-001 e CRI-002

Código, planilhas e plataforma dos indicadores descritos nas notas metodológicas:

- **CRI-001**: taxa de homicídio de mulheres de 15 a 64 anos, bruta e padronizada por idade, Brasil e UFs, 2022-2024;
- **CRI-002**: anos potenciais de vida produtiva perdidos por homicídio (APVP), valorados pelo PIB per capita nacional de 2024.

Fontes: Sistema de Informações sobre Mortalidade (SIM) e estimativas populacionais POPSVS, do Ministério da Saúde (DataSUS); PIB e PIB per capita de 2024, das Contas Nacionais Trimestrais do IBGE.

## Estrutura

```
├── README.md
├── LICENSE              licença MIT (código)
├── LICENCA-DADOS.md     licença CC BY 4.0 (dados derivados e planilhas)
├── requirements.txt
├── scripts/
│   ├── comum.py         constantes e regras comuns (anos, UFs, faixas, APVP, leitura de .dbf)
│   ├── 01_download.py   baixa os microdados do DataSUS e os converte em .dbf
│   ├── 02_bases.py      seleciona os homicídios e monta as bases agregadas
│   ├── 03_resultados.py calcula os indicadores em pandas e os números citados nas notas
│   ├── 04_planilhas.py  atualiza as abas de base das planilhas do Excel
│   ├── 05_plataforma.py grava os dados na plataforma
│   └── 06_conferencia.py confere planilhas, cálculo em pandas e plataforma entre si
├── planilhas/           cálculo dos indicadores em fórmulas do Excel (SOMASES sobre as abas de base)
├── plataforma/          plataforma interativa em um único arquivo HTML
└── dados/               criada pelos scripts; não versionada
```

O cálculo dos indicadores fica nas planilhas, em fórmulas visíveis, para que qualquer número possa ser auditado no próprio Excel. Os scripts preparam os dados, que o Excel não consegue abrir diretamente: cada ano do SIM tem cerca de 1,5 milhão de declarações de óbito, acima do limite de linhas de uma planilha, em formato .dbc. A etapa 3 refaz todo o cálculo em pandas, de forma independente, e a etapa 6 confere se os dois caminhos chegam aos mesmos valores.

## Como rodar

Requisitos: Python 3.12 e as bibliotecas de `requirements.txt`. A etapa 6 recalcula as planilhas pelo Excel quando elas ainda não têm os valores calculados, o que exige Windows com Excel e o pacote pywin32; nos demais casos, basta abrir e salvar as planilhas no Excel antes da etapa 6.

```
git clone https://github.com/criminalidade-ecn305/indicadores-cri.git
cd indicadores-cri
python -m venv .venv
.venv\Scripts\activate            (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
cd scripts
python 01_download.py ..\dados
python 02_bases.py ..\dados
python 03_resultados.py ..\dados
python 04_planilhas.py ..\dados
python 05_plataforma.py ..\dados
python 06_conferencia.py ..\dados
```

No Linux e no macOS, use barras normais nos caminhos (`../dados`). É preciso ter cerca de 3 GB livres em disco.

Cada script recebe como argumento a pasta de dados (padrão: `dados/`, na raiz do repositório). A etapa 1 grava os arquivos baixados em `dados/brutos/`, com o registro de tamanho, MD5 e data em `registro_download.csv`, e os arquivos convertidos em `dados/dbf/`. A etapa 2 grava as bases em `dados/bases/`, e a etapa 3, os resultados em `dados/resultados/`. As etapas 4 e 5 alteram os arquivos de `planilhas/` e `plataforma/` só quando os dados mudam.

Tempo e espaço: os seis arquivos baixados somam cerca de 400 MB, e os convertidos, 2,2 GB. O download depende do servidor do DataSUS: em 12 e 13/11/2026 levou de 40 minutos a algumas horas, com quedas de conexão. As etapas 2 a 6 levam cerca de um minuto, mais o recálculo das planilhas no Excel, quando necessário.

## Como saber se deu certo

A última linha da etapa 6 deve ser `Conferência concluída: tudo confere.` Além disso, o arquivo `dados/resultados/resumo_das_notas.txt` deve trazer, entre outros, estes valores:

| Valor | Esperado |
|---|---|
| Homicídios no SIM, total (2022-2024) | 134746 |
| CRI-001 Brasil 2022-2024: taxa bruta | 4.52 |
| CRI-001 Brasil 2022-2024: taxa padronizada | 4.54 |
| CRI-002 Brasil, APVP por ano (todos) | 1419000 |
| CRI-002 Brasil, perda por ano (R$ bilhões) | 78.4 |

Os arquivos do SIM e da POPSVS podem ser atualizados pelo DataSUS; nesse caso, o MD5 em `dados/brutos/registro_download.csv` muda, e os valores podem mudar também. Os arquivos usados nas notas tinham estes MD5: DOBR2022.dbc `5f3c6aec311686ffaf649b394ca0e1e3`, DOBR2023.dbc `1b53fc0778279a49a7579e480d67cac4`, DOBR2024.dbc `f82dcda9e6a911ccb1dc1cfe4b3c4f66`, POPSBR22.zip `75352a6d4610d3d4332a5d1a79fa3aea`, POPSBR23.zip `940d0a30877afa49770f5bf6838619cb`, POPSBR24.zip `0a3bcd3f7d7f4b75d39f318c243122f9`.

## Arquivos baixados

| Arquivo | Origem |
|---|---|
| DOBR2022.dbc, DOBR2023.dbc, DOBR2024.dbc | ftp://ftp.datasus.gov.br/dissemin/publicos/SIM/CID10/DORES/ |
| POPSBR22.zip, POPSBR23.zip, POPSBR24.zip | ftp://ftp.datasus.gov.br/dissemin/publicos/IBGE/POPSVS/ |

O .dbc é uma tabela .dbf comprimida em formato próprio do DataSUS; a etapa 1 a descomprime com o pacote datasus-dbc. O servidor do DataSUS costuma derrubar conexões longas; a etapa 1 retoma o download do ponto em que parou.

## Para incluir um novo ano

Acrescente o ano em `ANOS`, no arquivo `scripts/comum.py`, e atualize o PIB per capita se o ano-base da moeda mudar. As planilhas e a plataforma têm os anos 2022 a 2024 fixos nas abas de resultado e precisam de ajuste próprio.

## Licença e citação

Código sob a licença MIT; dados derivados e planilhas sob a licença CC BY 4.0. Para citar, use a sugestão de citação das notas metodológicas CRI-001 e CRI-002 (Cedeplar/UFMG, 2026).
