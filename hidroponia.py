"""Estimativas e diagnósticos iniciais para sistemas hidropónicos."""

import math


CULTURAS = {
    'alface': {
        'nome': 'Alface',
        'espacamento_planta_m': 0.25,
        'espacamento_linha_m': 0.25,
        'ec': {
            'muda': (0.8, 1.2),
            'vegetativo': (1.2, 1.8),
            'frutificacao': (1.2, 1.8),
        },
        'receita_g_l': {
            'nitrato_calcio': 0.75,
            'nitrato_potassio': 0.35,
            'fosfato_monopotassico': 0.12,
            'sulfato_magnesio': 0.40,
            'micronutrientes': 0.02,
        },
        'agua_l_planta_dia': 0.25,
    },
    'tomate': {
        'nome': 'Tomate',
        'espacamento_planta_m': 0.40,
        'espacamento_linha_m': 0.80,
        'ec': {
            'muda': (0.8, 1.2),
            'vegetativo': (2.0, 3.0),
            'frutificacao': (2.0, 3.5),
        },
        'receita_g_l': {
            'nitrato_calcio': 0.95,
            'nitrato_potassio': 0.45,
            'fosfato_monopotassico': 0.20,
            'sulfato_magnesio': 0.50,
            'micronutrientes': 0.03,
        },
        'agua_l_planta_dia': 1.50,
    },
    'morango': {
        'nome': 'Morango',
        'espacamento_planta_m': 0.25,
        'espacamento_linha_m': 0.30,
        'ec': {
            'muda': (0.8, 1.2),
            'vegetativo': (1.2, 1.8),
            'frutificacao': (1.4, 2.0),
        },
        'receita_g_l': {
            'nitrato_calcio': 0.75,
            'nitrato_potassio': 0.32,
            'fosfato_monopotassico': 0.15,
            'sulfato_magnesio': 0.40,
            'micronutrientes': 0.03,
        },
        'agua_l_planta_dia': 0.50,
    },
}

FASES = {'muda', 'vegetativo', 'frutificacao'}
SISTEMAS = {'nft', 'substrato', 'dwc'}
SINTOMAS = {
    'raizes_escuras': (
        'Raízes escuras ou com mau cheiro',
        'Pode indicar pouco oxigénio, água demasiado quente ou doença radicular; a aparência sozinha não confirma Pythium.',
        'Verifique a temperatura e o funcionamento da bomba/aeração. Isole plantas muito afetadas, remova tecido morto e higienize reservatório e linhas com produto adequado, seguindo o rótulo.',
    ),
    'folhas_velhas_amarelas': (
        'Folhas mais velhas amarelas',
        'Pode ser falta de azoto, pH fora da faixa ou absorção bloqueada.',
        'Meça pH e CE antes de adicionar nutrientes. Corrija gradualmente conforme a receita da cultura e remova folhas já mortas.',
    ),
    'pontas_amarelas_queimadas': (
        'Pontas amarelas ou queimadas',
        'Pode ser CE elevada, acumulação de sais, calor ou dano nas raízes.',
        'Meça a CE e a temperatura. Se a CE estiver acima da meta, dilua parcialmente com água limpa e volte a medir; não acrescente adubo sem confirmar.',
    ),
    'folhas_novas_amarelas': (
        'Folhas novas amarelas',
        'Pode estar relacionado com pH alto, deficiência de ferro ou outro bloqueio de micronutrientes.',
        'Confirme o pH e mantenha-o na faixa recomendada. Verifique a composição do micronutriente usado antes de corrigir a solução.',
    ),
    'manchas_furos': (
        'Manchas ou furos nas folhas',
        'Pode resultar de pragas, doença ou dano físico; a fotografia/sintoma não permite confirmar sozinho.',
        'Isole a planta, examine a parte inferior das folhas e higienize ferramentas. Use controlo integrado adequado à cultura e siga o rótulo de qualquer produto.',
    ),
    'murcha': (
        'Planta murcha apesar de haver água',
        'Pode ser interrupção do fluxo, falta de oxigénio, calor na zona radicular ou raízes danificadas.',
        'Confirme imediatamente o caudal, a bomba e a temperatura da água. Em DWC, mantenha a bomba de ar ligada continuamente.',
    ),
    'crescimento_lento': (
        'Crescimento lento ou folhas pequenas',
        'Pode resultar de luz insuficiente, CE/pH inadequados, temperatura ou falta de circulação.',
        'Meça pH, CE e temperatura; verifique a luz e o caudal. Ajuste apenas um fator de cada vez e observe a resposta.',
    ),
}

RECEITA_FATORES_FASE = {
    'muda': 0.50,
    'vegetativo': 1.00,
    'frutificacao': 1.15,
}


def _numero(dados, campo, nome, minimo, maximo, obrigatorio=False):
    valor = dados.get(campo)
    if valor in (None, ''):
        if obrigatorio:
            raise ValueError(f'Preencha o campo {nome}.')
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f'O valor de {nome} é inválido.')
    if not math.isfinite(numero) or numero < minimo or numero > maximo:
        raise ValueError(f'{nome} deve estar entre {minimo:g} e {maximo:g}.')
    return numero


def calcular_hidroponia(dados):
    """Calcula dimensões estimadas, receita inicial, irrigação e diagnóstico."""
    if not isinstance(dados, dict):
        raise ValueError('Envie os dados da hidroponia em formato válido.')

    cultura_id = str(dados.get('cultura', 'alface')).strip().lower()
    sistema = str(dados.get('sistema', 'nft')).strip().lower()
    fase = str(dados.get('fase', 'vegetativo')).strip().lower()
    if cultura_id not in CULTURAS:
        raise ValueError('Escolha alface, tomate ou morango.')
    if sistema not in SISTEMAS:
        raise ValueError('Escolha NFT, substrato ou DWC.')
    if fase not in FASES:
        raise ValueError('Escolha uma fase de crescimento válida.')

    cultura = CULTURAS[cultura_id]
    area = _numero(dados, 'area_m2', 'área disponível (m²)', 0.5, 10000, True)
    volume = _numero(dados, 'volume_l', 'volume do reservatório (L)', 1, 100000, True)
    temperatura_ar = _numero(dados, 'temperatura_ar', 'temperatura ambiente (°C)', 0, 55)
    ph = _numero(dados, 'ph', 'pH', 0, 14)
    temperatura_agua = _numero(dados, 'temperatura_agua', 'temperatura da água (°C)', 0, 55)
    leitura = _numero(dados, 'leitura_nutrientes', 'leitura CE/TDS', 0, 10000)

    # A disposição é uma estimativa para um terreno aproximadamente quadrado.
    lado_estimado = math.sqrt(area)
    largura_bancada = 1.2
    corredor = 0.6
    bancadas = max(1, math.floor(lado_estimado / (largura_bancada + corredor)))
    linhas_por_bancada = max(
        1, math.floor(largura_bancada / cultura['espacamento_linha_m'])
    )
    linhas_total = bancadas * linhas_por_bancada
    plantas_por_linha = max(
        1, math.floor(lado_estimado / cultura['espacamento_planta_m']) + 1
    )
    plantas = linhas_total * plantas_por_linha

    if sistema == 'nft':
        canais = linhas_total
        caudal_por_canal = 1.5
        caudal_total = canais * caudal_por_canal
        inclinacao = 2.5
        diferenca_altura = lado_estimado * inclinacao
        tabela_programacao = [{
            'periodo': 'Dia e noite',
            'funcionamento': 'Bomba de solução ligada continuamente',
            'temporizador': '24 horas por dia',
        }]
        bomba = (
            f'NFT: circulação contínua 24 horas. Caudal inicial de cerca de '
            f'{caudal_por_canal:.1f} L/min por canal; para {canais} canais, '
            f'aprox. {caudal_total:.1f} L/min no total. Inclinação recomendada '
            f'{inclinacao:.1f}% (2–4%); ao longo de {lado_estimado:.1f} m, '
            f'a diferença de altura estimada é {diferenca_altura:.1f} cm. '
            'Instale filtro e tenha bomba/energia de reserva.'
        )
        geometria = {
            'canais_ou_linhas': canais,
            'linhas_por_bancada': linhas_por_bancada,
            'inclinacao_percentual': inclinacao,
            'diferenca_altura_cm': round(diferenca_altura, 1),
            'caudal_l_min_por_canal': caudal_por_canal,
            'caudal_total_l_min': round(caudal_total, 1),
        }
    elif sistema == 'dwc':
        canais = linhas_total
        tabela_programacao = [{
            'periodo': 'Dia e noite',
            'funcionamento': 'Aerador/bomba de ar ligado continuamente',
            'temporizador': '24 horas por dia',
        }]
        geometria = {
            'canais_ou_linhas': canais,
            'linhas_por_bancada': linhas_por_bancada,
            'inclinacao_percentual': None,
            'diferenca_altura_cm': None,
            'caudal_l_min_por_canal': None,
            'caudal_total_l_min': None,
        }
        bomba = (
            'DWC: mantenha a bomba de ar/aerador ligada continuamente, '
            '24 horas por dia. Ajuste a quantidade de pedras difusoras ao '
            'volume e à densidade de plantas; mantenha as raízes oxigenadas.'
        )
    else:
        ciclos = 4 if (temperatura_ar or 25) < 30 else 7
        if fase == 'frutificacao':
            ciclos += 1
        tabela_programacao = [
            {
                'periodo': 'Durante o dia',
                'funcionamento': f'{ciclos} ciclos curtos; ajustar pela drenagem do substrato',
                'temporizador': 'A duração depende do caudal dos gotejadores',
            },
            {
                'periodo': 'Noite',
                'funcionamento': 'Sem rotina fixa; verificar humidade antes de irrigar',
                'temporizador': 'Evitar encharcamento',
            },
        ]
        geometria = {
            'canais_ou_linhas': linhas_total,
            'linhas_por_bancada': linhas_por_bancada,
            'inclinacao_percentual': None,
            'diferenca_altura_cm': None,
            'caudal_l_min_por_canal': None,
            'caudal_total_l_min': None,
        }
        bomba = (
            f'Substrato: ponto de partida de {ciclos} ciclos curtos de gota '
            'durante o dia, com drenagem livre. Em dias muito quentes, observe '
            'o substrato e aumente gradualmente; não deixe as raízes encharcadas '
            'nem secarem. O tempo de cada pulso depende do caudal dos gotejadores.'
        )

    faixa_ec = cultura['ec'][fase]
    ec_alvo = (faixa_ec[0] + faixa_ec[1]) / 2
    receita_fator = RECEITA_FATORES_FASE[fase]
    receita_completa = {
        nome: round(taxa * volume * receita_fator, 2)
        for nome, taxa in cultura['receita_g_l'].items()
    }
    receita_correcao = {nome: round(gramas * 0.25, 2) for nome, gramas in receita_completa.items()}

    ec_medido = None
    if leitura is not None:
        unidade = str(dados.get('unidade_leitura', 'ec')).lower()
        if unidade == 'tds':
            fator_tds = str(dados.get('fator_tds', '500'))
            if fator_tds not in {'500', '700'}:
                raise ValueError('Escolha a escala TDS 500 ou 700.')
            ec_medido = leitura / float(fator_tds)
        elif unidade == 'ec':
            ec_medido = leitura
        else:
            raise ValueError('Escolha CE (mS/cm) ou TDS (ppm).')
        if ec_medido < faixa_ec[0]:
            estado_ec = (
                f'CE abaixo da faixa {faixa_ec[0]:.1f}–{faixa_ec[1]:.1f} mS/cm. '
                'Confirme primeiro o volume do tanque. Se a leitura continuar baixa, '
                'adicione no máximo ¼ da receita inicial indicada, misture e volte '
                'a medir antes de acrescentar mais.'
            )
        elif ec_medido > faixa_ec[1]:
            fracao_troca = max(0, min(1, 1 - ec_alvo / ec_medido))
            litros_diluir = volume * fracao_troca
            estado_ec = (
                f'CE acima da faixa {faixa_ec[0]:.1f}–{faixa_ec[1]:.1f} mS/cm. '
                f'Para aproximar do centro da faixa, substitua gradualmente cerca de '
                f'{litros_diluir:.1f} L da solução por água limpa (aprox. '
                f'{fracao_troca * 100:.0f}% do volume medido) e volte a medir. '
                'Não despeje este volume por cima do tanque cheio.'
            )
        else:
            estado_ec = (
                f'CE dentro da faixa inicial de {faixa_ec[0]:.1f}–'
                f'{faixa_ec[1]:.1f} mS/cm para {cultura["nome"].lower()} '
                f'na fase selecionada. Continue a medir diariamente.'
            )
    else:
        estado_ec = (
            f'Faixa inicial de CE para esta cultura/fase: '
            f'{faixa_ec[0]:.1f}–{faixa_ec[1]:.1f} mS/cm. '
            'Use um medidor calibrado antes de corrigir a solução.'
        )

    if ph is None:
        estado_ph = 'Meça diariamente; a faixa inicial recomendada para a maioria das culturas é pH 5,5–6,5.'
    elif ph > 6.5:
        estado_ph = (
            f'pH {ph:.2f}, acima da faixa 5,5–6,5. Use pH Minus apenas conforme '
            'o rótulo do fabricante, em pequenas adições, misturando e medindo '
            'novamente. A dose não pode ser calculada só pelo pH: depende da alcalinidade da água.'
        )
    elif ph < 5.5:
        estado_ph = (
            f'pH {ph:.2f}, abaixo da faixa 5,5–6,5. Use pH Plus apenas conforme '
            'o rótulo do fabricante, em pequenas adições, misturando e medindo novamente.'
        )
    else:
        estado_ph = f'pH {ph:.2f}, dentro da faixa inicial recomendada de 5,5–6,5.'

    if temperatura_agua is None:
        estado_temperatura = 'Meça a temperatura do reservatório; a faixa recomendada é aproximadamente 18–24 °C.'
    elif temperatura_agua > 28:
        estado_temperatura = (
            f'Água a {temperatura_agua:.1f} °C: alerta alto. O oxigénio dissolvido '
            'pode diminuir. Sombreie/insule o reservatório, aumente a aeração e '
            'confirme a circulação continuamente.'
        )
    elif temperatura_agua > 24:
        estado_temperatura = (
            f'Água a {temperatura_agua:.1f} °C: acima da faixa ideal aproximada '
            'de 18–24 °C. Sombreie o reservatório e acompanhe a oxigenação.'
        )
    elif temperatura_agua < 18:
        estado_temperatura = (
            f'Água a {temperatura_agua:.1f} °C: abaixo da faixa ideal aproximada '
            'de 18–24 °C; acompanhe o crescimento e evite mudanças bruscas.'
        )
    else:
        estado_temperatura = f'Água a {temperatura_agua:.1f} °C, dentro da faixa aproximada de 18–24 °C.'

    sintoma_id = str(dados.get('sintoma', '')).strip().lower()
    if sintoma_id in SINTOMAS:
        sintoma_titulo, sintoma_causa, sintoma_acao = SINTOMAS[sintoma_id]
        diagnostico = {
            'sintoma': sintoma_titulo,
            'possivel_causa': sintoma_causa,
            'acao': sintoma_acao,
        }
    else:
        diagnostico = {
            'sintoma': 'Sem sintoma selecionado',
            'possivel_causa': 'Selecione um sintoma para receber uma orientação inicial.',
            'acao': 'Meça pH, CE e temperatura da água diariamente e inspecione raízes e folhas.',
        }

    consumo_base = plantas * cultura['agua_l_planta_dia']
    fator_clima = 1.25 if (temperatura_ar or 25) >= 30 else 1.0
    if fase == 'muda':
        fator_clima *= 0.6
    elif fase == 'frutificacao':
        fator_clima *= 1.2
    reposicao_diaria = round(consumo_base * fator_clima, 1)

    return {
        'cultura': cultura['nome'],
        'sistema': sistema.upper(),
        'fase': fase,
        'dimensionamento': {
            'area_m2': area,
            'formato_estimado': f'{lado_estimado:.1f} m × {lado_estimado:.1f} m',
            'bancadas': bancadas,
            'linhas_por_bancada': linhas_por_bancada,
            'plantas_por_linha': plantas_por_linha,
            'plantas_estimadas': plantas,
            'espacamento_planta_cm': round(cultura['espacamento_planta_m'] * 100),
            'espacamento_linha_cm': round(cultura['espacamento_linha_m'] * 100),
            **geometria,
        },
        'nutrientes': {
            'volume_l': volume,
            'faixa_ec_min': faixa_ec[0],
            'faixa_ec_max': faixa_ec[1],
            'ec_alvo': round(ec_alvo, 2),
            'receita_inicial_g': receita_completa,
            'dose_correcao_parcial_g': receita_correcao,
            'nota': (
                'Receita inicial estimada para sais puros, não uma prescrição universal. '
                'A composição dos fertilizantes comerciais varia. Dissolva cada sal '
                'separadamente em água; não misture concentrados de cálcio e fosfato/sulfato. '
                'Confirme no rótulo do produto, pH e CE; adicione gradualmente.'
            ),
            'estado_ec': estado_ec,
        },
        'irrigacao': {
            'programacao': bomba,
            'programacao_tabela': tabela_programacao,
            'reposicao_estimada_l_dia': reposicao_diaria,
            'nota_reposicao': (
                'Estimativa de consumo, não substitui a leitura do nível do reservatório. '
                'Complete primeiro com água até ao volume de referência, volte a medir '
                'CE e pH e só então corrija nutrientes.'
            ),
        },
        'monitorizacao': {
            'estado_ph': estado_ph,
            'estado_temperatura': estado_temperatura,
            'estado_ec': estado_ec,
        },
        'diagnostico': diagnostico,
        'aviso': (
            'Os resultados são pontos de partida. Variedade, qualidade da água, '
            'concentração dos sais, clima e equipamento alteram as necessidades. '
            'Confirme com um técnico agrário local antes de usar produtos corretivos.'
        ),
    }
