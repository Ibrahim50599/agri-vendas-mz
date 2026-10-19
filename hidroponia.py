"""Cálculos hidropónicos baseados em medições do agricultor e referências técnicas."""

import math


FONTES = [
    {
        'nome': 'Oklahoma State University Extension — CE e pH por cultura',
        'url': 'https://extension.okstate.edu/fact-sheets/electrical-conductivity-and-ph-guide-for-hydroponics',
    },
    {
        'nome': 'Virginia Cooperative Extension — canais NFT, espaçamento e vazão',
        'url': 'https://pubs.ext.vt.edu/SPES/spes-463/spes-463.html',
    },
    {
        'nome': 'Oregon State University Extension — inclinação mínima de canais NFT',
        'url': 'https://extension.oregonstate.edu/catalog/pub/em-9457-hydro-hints-nutrient-film-technique',
    },
    {
        'nome': 'University of Missouri Extension — qualidade da água, alcalinidade, pH, CE e oxigénio',
        'url': 'https://extension.missouri.edu/publications/g6984',
    },
    {
        'nome': 'Penn State Extension — dose de fertilizante depende da receita e do grau do produto',
        'url': 'https://extension.psu.edu/hydroponics-systems-nutrient-solution-programs-and-recipes',
    },
    {
        'nome': 'Penn State Extension — cálculo de concentrações de nutrientes',
        'url': 'https://extension.psu.edu/hydroponics-systems-calculating-nutrient-solution-concentrations-using-the-two-basic-equations',
    },
]

CULTURAS = {
    'alface': {
        'nome': 'Alface',
        'espacamento_nft_cm_referencia': 20.32,
        'ec_min': 1.2,
        'ec_max': 1.8,
        'ph_min': 6.0,
        'ph_max': 7.0,
        'ph_nota': 'A tabela da Oklahoma State indica pH 6,0–7,0 para alface.',
    },
    'tomate': {
        'nome': 'Tomate',
        'espacamento_nft_cm_referencia': None,
        'ec_min': 2.0,
        'ec_max': 4.0,
        'ph_min': 6.0,
        'ph_max': 6.5,
        'ph_nota': 'A tabela da Oklahoma State indica pH 6,0–6,5 para tomate.',
    },
    'morango': {
        'nome': 'Morango',
        'espacamento_nft_cm_referencia': None,
        'ec_min': 1.8,
        'ec_max': 2.2,
        'ph_min': 5.5,
        'ph_max': 6.5,
        'ph_nota': 'A Oklahoma State indica pH próximo de 6,0; a faixa 5,5–6,5 é a regra geral da University of Missouri.',
    },
}

SISTEMAS = {'nft', 'substrato', 'dwc'}
FASES = {'muda', 'vegetativo', 'frutificacao'}

SINTOMAS = {
    'raizes_escuras': (
        'Raízes escuras ou com mau cheiro',
        'Pode estar associado a baixo oxigénio dissolvido, aquecimento, fluxo interrompido ou doença radicular. A cor, sozinha, não confirma Pythium.',
        'Meça o oxigénio dissolvido, confira o caudal/aeração e a temperatura. Isole plantas afetadas e higienize o circuito segundo a orientação do fabricante do produto de limpeza.',
    ),
    'folhas_velhas_amarelas': (
        'Folhas mais velhas amarelas',
        'Pode ser falta de azoto, pH fora da faixa ou desequilíbrio/absorção bloqueada.',
        'Confirme a água, pH e CE e compare a receita e o rótulo dos fertilizantes antes de corrigir. Não adicione um sal isolado sem identificar a causa.',
    ),
    'pontas_amarelas_queimadas': (
        'Pontas amarelas ou queimadas',
        'Pode estar associado a CE elevada, salinidade, calor ou transporte insuficiente de cálcio.',
        'Meça CE, pH e temperatura. Verifique circulação de ar, humidade e fluxo de água antes de alterar a solução.',
    ),
    'folhas_novas_amarelas': (
        'Folhas novas amarelas',
        'Pode estar associado a pH alto e menor disponibilidade de ferro ou de outros micronutrientes.',
        'Meça pH e confira a análise da água e a composição do fertilizante. Ajuste apenas com base na receita/rótulo e volte a medir.',
    ),
    'manchas_furos': (
        'Manchas ou furos nas folhas',
        'Pode resultar de pragas, doença ou dano físico; este sintoma isolado não confirma a causa.',
        'Isole a planta, examine os dois lados das folhas e higienize ferramentas. Use controlo integrado adequado à cultura; siga o rótulo dos produtos.',
    ),
    'murcha': (
        'Planta murcha apesar de haver água',
        'Pode ser interrupção do fluxo, baixo oxigénio, calor ou raízes danificadas.',
        'Confirme imediatamente bomba, caudal e aeração. Em DWC mantenha a aeração ligada continuamente e, se possível, meça o oxigénio dissolvido.',
    ),
    'crescimento_lento': (
        'Crescimento lento ou folhas pequenas',
        'Pode estar relacionado com luz, clima, pH, nutrientes ou circulação.',
        'Registe pH, CE, temperatura e oxigénio dissolvido; confira o fluxo e a luz. Altere um fator de cada vez e acompanhe a resposta.',
    ),
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


def _calcular_produtos_rotulo(dados, volume_l):
    produtos = dados.get('produtos_rotulo') or []
    if not isinstance(produtos, list) or len(produtos) > 4:
        raise ValueError('Informe no máximo quatro produtos conforme o rótulo.')

    doses = []
    for indice, produto in enumerate(produtos, start=1):
        if not isinstance(produto, dict):
            raise ValueError('Os dados dos produtos do rótulo são inválidos.')
        dose_rotulo = _numero(
            produto,
            'dose_rotulo',
            f'dose do produto {indice} no rótulo',
            0,
            100000,
            True,
        )
        volume_rotulo_l = _numero(
            produto,
            'volume_rotulo_l',
            f'volume de referência do rótulo do produto {indice} (L)',
            0.001,
            100000,
            True,
        )
        nome = str(produto.get('nome', '')).strip()[:80] or f'Produto {indice}'
        unidade = str(produto.get('unidade', 'g')).strip().lower()
        if unidade not in {'g', 'ml'}:
            raise ValueError('A unidade da dose do rótulo deve ser g ou mL.')
        if dose_rotulo is None or volume_rotulo_l is None:
            continue
        doses.append({
            'nome': nome,
            'unidade': unidade,
            'dose_rotulo': dose_rotulo,
            'volume_rotulo_l': volume_rotulo_l,
            'dose_calculada': round(dose_rotulo * volume_l / volume_rotulo_l, 4),
        })
    return doses


def calcular_hidroponia(dados):
    """Calcula apenas a partir de dimensões, medições e doses informadas."""
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
    comprimento = _numero(dados, 'comprimento_m', 'comprimento da área (m)', 0.5, 1000, True)
    largura = _numero(dados, 'largura_m', 'largura da área (m)', 0.5, 1000, True)
    volume = _numero(dados, 'volume_l', 'volume de trabalho do reservatório (L)', 1, 100000, True)
    largura_bancada = _numero(dados, 'largura_bancada_m', 'largura da bancada (m)', 0.2, 20, True)
    corredor = _numero(dados, 'corredor_m', 'largura do corredor (m)', 0, 20, True)
    espacamento_planta_cm = _numero(
        dados, 'espacamento_planta_cm', 'espaçamento entre plantas (cm)', 1, 500, True
    )
    espacamento_linha_cm = _numero(
        dados, 'espacamento_linha_cm', 'espaçamento entre linhas (cm)', 1, 500, True
    )
    temperatura_ar = _numero(dados, 'temperatura_ar', 'temperatura ambiente (°C)', -5, 55)
    ph = _numero(dados, 'ph', 'pH da solução', 0, 14)
    temperatura_agua = _numero(dados, 'temperatura_agua', 'temperatura da solução (°C)', 0, 55)
    oxigenio = _numero(dados, 'oxigenio_dissolvido', 'oxigénio dissolvido (mg/L)', 0, 30)
    leitura = _numero(dados, 'leitura_nutrientes', 'leitura CE/TDS da solução', 0, 10000)
    ec_agua_fonte = _numero(dados, 'ec_agua_fonte', 'CE da água de origem (mS/cm)', 0, 100)
    alcalinidade = _numero(dados, 'alcalinidade_ppm', 'alcalinidade (ppm CaCO₃)', 0, 10000)

    if largura_bancada > largura:
        raise ValueError('A largura da bancada não pode ser maior que a largura disponível.')
    if sistema == 'nft' and comprimento < 0.5:
        raise ValueError('O comprimento é demasiado curto para estimar canais NFT.')

    area = comprimento * largura
    espacamento_planta_m = espacamento_planta_cm / 100
    espacamento_linha_m = espacamento_linha_cm / 100
    bancadas = math.floor((largura + corredor) / (largura_bancada + corredor))
    linhas_por_bancada = math.floor(largura_bancada / espacamento_linha_m)
    if bancadas < 1:
        raise ValueError(
            'Com estas medidas não cabe uma bancada e um corredor. Ajuste a largura, bancada ou corredor.'
        )
    if linhas_por_bancada < 1:
        raise ValueError(
            'O espaçamento entre linhas é maior que a largura útil da bancada.'
        )

    linhas = bancadas * linhas_por_bancada
    comprimento_canal = None
    segmentos_por_linha = 1
    if sistema == 'nft':
        comprimento_canal = _numero(
            dados, 'comprimento_canal_m', 'comprimento real do canal NFT (m)', 0.5, 3.66, True
        )
        if comprimento_canal > comprimento:
            raise ValueError(
                'O canal NFT não pode ser mais comprido que o espaço disponível. '
                'Use canais menores ou aumente o comprimento da área.'
            )
        # Canal standard descrito pela Virginia Cooperative Extension: 4–12 ft.
        segmentos_por_linha = math.floor(comprimento / comprimento_canal)
        plantas_por_canal = math.floor(comprimento_canal / espacamento_planta_m) + 1
        canais = linhas * segmentos_por_linha
        plantas = canais * plantas_por_canal
        comprimento_utilizado = segmentos_por_linha * comprimento_canal
    else:
        plantas_por_linha = math.floor(comprimento / espacamento_planta_m) + 1
        canais = linhas
        plantas = linhas * plantas_por_linha
        comprimento_utilizado = comprimento

    if sistema == 'nft':
        # Virginia Cooperative Extension: 3–5 US gal/h de solução em cada canal.
        caudal_minimo_por_canal_l_h = 3 * 3.785411784
        caudal_maximo_por_canal_l_h = 5 * 3.785411784
        inclinacao_minima_pct = 2.0  # OSU Extension: mínimo 2%.
        queda_minima_cm = comprimento_canal * inclinacao_minima_pct
        programacao = (
            'Bomba de solução em funcionamento contínuo, 24 horas por dia. '
            'Dimensione pela vazão real na altura de elevação do sistema e pela perda '
            'nas tubagens; mantenha uma bomba ou fonte de energia de reserva.'
        )
        tabela_programacao = [{
            'periodo': 'Dia e noite',
            'funcionamento': 'Bomba de solução ligada continuamente',
            'temporizador': '24 horas/dia; não usar ciclos de desligamento em NFT',
        }]
        detalhes_fluxo = {
            'caudal_minimo_l_h_canal': round(caudal_minimo_por_canal_l_h, 1),
            'caudal_maximo_l_h_canal': round(caudal_maximo_por_canal_l_h, 1),
            'caudal_minimo_total_l_h': round(caudal_minimo_por_canal_l_h * canais, 1),
            'caudal_maximo_total_l_h': round(caudal_maximo_por_canal_l_h * canais, 1),
            'inclinacao_minima_percentual': inclinacao_minima_pct,
            'queda_minima_cm_canal': round(queda_minima_cm, 1),
            'comprimento_canal_m': comprimento_canal,
        }
    elif sistema == 'dwc':
        programacao = (
            'Manter a bomba de ar/aeração ligada continuamente, 24 horas por dia. '
            'A dimensão do aerador depende da sua capacidade e da geometria do tanque; '
            'confirme oxigénio dissolvido com medidor.'
        )
        tabela_programacao = [{
            'periodo': 'Dia e noite',
            'funcionamento': 'Aerador ligado continuamente',
            'temporizador': '24 horas/dia',
        }]
        detalhes_fluxo = {
            'caudal_minimo_l_h_canal': None,
            'caudal_maximo_l_h_canal': None,
            'caudal_minimo_total_l_h': None,
            'caudal_maximo_total_l_h': None,
            'inclinacao_minima_percentual': None,
            'queda_minima_cm_canal': None,
            'comprimento_canal_m': None,
        }
    else:
        vazao_emissor = _numero(
            dados, 'vazao_emissor_l_h', 'vazão medida do gotejador (L/h)', 0.001, 10000
        )
        volume_por_planta_ciclo = _numero(
            dados, 'volume_por_planta_ciclo_l',
            'volume alvo por planta em cada ciclo (L)', 0.001, 1000
        )
        ciclos = _numero(dados, 'ciclos_dia', 'ciclos de irrigação por dia', 1, 100)
        if vazao_emissor is not None and volume_por_planta_ciclo is not None:
            minutos = volume_por_planta_ciclo / vazao_emissor * 60
            programacao = (
                f'Com a vazão medida de {vazao_emissor:g} L/h e o volume definido '
                f'de {volume_por_planta_ciclo:g} L por planta/ciclo, o temporizador '
                f'deve funcionar {minutos:.1f} minutos por ciclo.'
            )
            tabela_programacao = [{
                'periodo': 'Cada ciclo',
                'funcionamento': f'{volume_por_planta_ciclo:g} L por planta; {ciclos:g} ciclo(s)/dia' if ciclos else f'{volume_por_planta_ciclo:g} L por planta',
                'temporizador': f'{minutos:.1f} minutos, calculado com a vazão informada',
            }]
            if ciclos is not None:
                programacao += f' Total diário configurado: {ciclos:g} ciclo(s); confirme o teor de água/drenagem do substrato.'
        else:
            programacao = (
                'Não é possível determinar minutos ou ciclos reais sem medir a vazão '
                'do gotejador e definir o volume de água por planta/ciclo. Meça a vazão '
                'com recipiente e cronómetro; calibre os ciclos pela humidade e drenagem do substrato.'
            )
            tabela_programacao = [{
                'periodo': 'A calibrar',
                'funcionamento': 'Registar vazão real e volume por planta',
                'temporizador': 'Sem minutos estimados sem estas medições',
            }]
        detalhes_fluxo = {
            'caudal_minimo_l_h_canal': None,
            'caudal_maximo_l_h_canal': None,
            'caudal_minimo_total_l_h': None,
            'caudal_maximo_total_l_h': None,
            'inclinacao_minima_percentual': None,
            'queda_minima_cm_canal': None,
            'comprimento_canal_m': None,
            'vazao_emissor_l_h': vazao_emissor,
            'volume_por_planta_ciclo_l': volume_por_planta_ciclo,
            'minutos_por_ciclo': round(volume_por_planta_ciclo / vazao_emissor * 60, 1)
            if vazao_emissor is not None and volume_por_planta_ciclo is not None else None,
            'ciclos_dia': ciclos,
        }

    faixa_ec = (cultura['ec_min'], cultura['ec_max'])
    ec_alvo = (faixa_ec[0] + faixa_ec[1]) / 2
    if leitura is not None:
        unidade = str(dados.get('unidade_leitura', 'ec')).lower()
        if unidade == 'tds':
            fator_tds = str(dados.get('fator_tds', '500'))
            if fator_tds not in {'500', '700'}:
                raise ValueError('Escolha a escala TDS 500 ou 700 do seu medidor.')
            ec_medido = leitura / float(fator_tds)
        elif unidade == 'ec':
            ec_medido = leitura
        else:
            raise ValueError('Escolha CE (mS/cm) ou TDS (ppm).')

        if ec_medido < faixa_ec[0]:
            estado_ec = (
                f'CE medida {ec_medido:.2f} mS/cm, abaixo da faixa publicada '
                f'{faixa_ec[0]:.1f}–{faixa_ec[1]:.1f}. CE não revela quais nutrientes '
                'estão em falta; não é possível converter esta diferença em gramas '
                'de sais com segurança. Confira água e rótulo da mistura completa, '
                'adicione em passos conforme o fabricante e volte a medir.'
            )
        elif ec_medido > faixa_ec[1]:
            if ec_agua_fonte is None:
                estado_ec = (
                    f'CE medida {ec_medido:.2f} mS/cm, acima da faixa publicada '
                    f'{faixa_ec[0]:.1f}–{faixa_ec[1]:.1f}. Para calcular uma diluição '
                    'é necessário medir primeiro a CE da água limpa de reposição.'
                )
            elif ec_agua_fonte >= ec_alvo:
                estado_ec = (
                    f'CE medida {ec_medido:.2f} mS/cm, acima da faixa. A CE da água '
                    f'de reposição ({ec_agua_fonte:.2f}) não é inferior ao alvo '
                    f'{ec_alvo:.2f}; não há diluição calculável com essa água. '
                    'Consulte análise de água e um técnico antes de trocar a fonte.'
                )
            else:
                fracao_troca = (ec_medido - ec_alvo) / (ec_medido - ec_agua_fonte)
                litros_troca = volume * fracao_troca
                estado_ec = (
                    f'CE acima da faixa publicada. Mistura linear aproximada para o '
                    f'alvo central: substituir cerca de {litros_troca:.1f} L da solução '
                    f'por água com CE medida de {ec_agua_fonte:.2f} mS/cm. Faça a troca '
                    'gradualmente e volte a medir; a CE é uma aproximação da soma de iões, '
                    'não uma análise individual dos nutrientes.'
                )
        else:
            estado_ec = (
                f'CE medida {ec_medido:.2f} mS/cm, dentro da faixa publicada '
                f'{faixa_ec[0]:.1f}–{faixa_ec[1]:.1f} para {cultura["nome"].lower()}. '
                'Isto não confirma o equilíbrio de cada nutriente; use também a análise da água.'
            )
    else:
        estado_ec = (
            f'Faixa de CE publicada para {cultura["nome"].lower()}: '
            f'{faixa_ec[0]:.1f}–{faixa_ec[1]:.1f} mS/cm. Insira uma leitura do medidor calibrado.'
        )

    if ph is None:
        estado_ph = (
            f'Faixa de pH de referência para {cultura["nome"].lower()}: '
            f'{cultura["ph_min"]:.1f}–{cultura["ph_max"]:.1f}. Meça com instrumento calibrado.'
        )
    elif ph < cultura['ph_min']:
        estado_ph = (
            f'pH medido {ph:.2f}, abaixo da referência {cultura["ph_min"]:.1f}–'
            f'{cultura["ph_max"]:.1f}. A dose de corretor depende da alcalinidade '
            'e da concentração do produto; não pode ser determinada apenas pelo pH. '
            'Siga o rótulo, ajuste em pequenas etapas e volte a medir.'
        )
    elif ph > cultura['ph_max']:
        estado_ph = (
            f'pH medido {ph:.2f}, acima da referência {cultura["ph_min"]:.1f}–'
            f'{cultura["ph_max"]:.1f}. A dose de corretor depende da alcalinidade '
            'e da concentração do produto; não pode ser determinada apenas pelo pH. '
            'Siga o rótulo, ajuste em pequenas etapas e volte a medir.'
        )
    else:
        estado_ph = (
            f'pH medido {ph:.2f}, dentro da referência publicada '
            f'{cultura["ph_min"]:.1f}–{cultura["ph_max"]:.1f}. '
            f'{cultura["ph_nota"]}'
        )

    if alcalinidade is None:
        estado_alcalinidade = (
            'Alcalinidade não informada. Peça análise da água em ppm equivalente CaCO₃; '
            'o pH sozinho não determina a alcalinidade nem a dose de ácido.'
        )
    elif alcalinidade > 160:
        estado_alcalinidade = (
            f'Alcalinidade {alcalinidade:.1f} ppm CaCO₃, acima da faixa de referência '
            '40–160 ppm. A água pode exigir mais gestão do pH; use análise de laboratório '
            'e orientação técnica para corrigir.'
        )
    elif alcalinidade < 40:
        estado_alcalinidade = (
            f'Alcalinidade {alcalinidade:.1f} ppm CaCO₃, abaixo da faixa de referência '
            '40–160 ppm. A água pode ter pouca capacidade tampão e o pH variar rapidamente.'
        )
    else:
        estado_alcalinidade = (
            f'Alcalinidade {alcalinidade:.1f} ppm CaCO₃, dentro da faixa de referência '
            '40–160 ppm.'
        )

    if ec_agua_fonte is None:
        estado_agua_fonte = (
            'CE da água de origem não informada. A University of Missouri recomenda '
            'analisar pH, CE, alcalinidade e elementos minerais da água antes de formular a solução.'
        )
    elif ec_agua_fonte > 0.8:
        estado_agua_fonte = (
            f'CE da água de origem {ec_agua_fonte:.2f} mS/cm, acima da faixa de referência '
            'de água de origem 0,2–0,8 mS/cm. Solicite análise dos iões antes de acrescentar adubo.'
        )
    elif ec_agua_fonte < 0.2:
        estado_agua_fonte = (
            f'CE da água de origem {ec_agua_fonte:.2f} mS/cm, abaixo da faixa de referência '
            '0,2–0,8 mS/cm. Isso não é necessariamente um problema; confirme os minerais numa análise.'
        )
    else:
        estado_agua_fonte = (
            f'CE da água de origem {ec_agua_fonte:.2f} mS/cm, dentro da faixa de referência '
            '0,2–0,8 mS/cm. A CE não identifica cada mineral.'
        )

    if oxigenio is None:
        estado_oxigenio = (
            'Oxigénio dissolvido não medido. A University of Missouri recomenda mais de '
            '6 mg/L; a temperatura da água, sozinha, não revela a concentração de oxigénio.'
        )
    elif oxigenio < 6:
        estado_oxigenio = (
            f'Oxigénio dissolvido {oxigenio:.2f} mg/L, abaixo da referência >6 mg/L. '
            'Verifique aeração, circulação e temperatura da solução.'
        )
    else:
        estado_oxigenio = (
            f'Oxigénio dissolvido {oxigenio:.2f} mg/L, acima da referência >6 mg/L. '
            'Continue a monitorizar, sobretudo em DWC e quando a água aquecer.'
        )

    if temperatura_agua is None:
        estado_temperatura = (
            'Temperatura da solução não medida. Registe-a junto com o oxigénio dissolvido; '
            'água mais quente consegue reter menos oxigénio.'
        )
    else:
        estado_temperatura = (
            f'Temperatura medida da solução: {temperatura_agua:.1f} °C. '
            'Não se aplica um limite universal a todas as culturas; interprete-a junto '
            'com o oxigénio dissolvido medido.'
        )

    sintoma_id = str(dados.get('sintoma', '')).strip().lower()
    if sintoma_id in SINTOMAS:
        titulo, causa, acao = SINTOMAS[sintoma_id]
        diagnostico = {'sintoma': titulo, 'possivel_causa': causa, 'acao': acao}
    else:
        diagnostico = {
            'sintoma': 'Sem sintoma selecionado',
            'possivel_causa': 'Selecione um sintoma para receber hipóteses iniciais; não é um diagnóstico laboratorial.',
            'acao': 'Registe pH, CE, temperatura e oxigénio dissolvido; examine raízes e folhas.',
        }

    produtos_rotulo = _calcular_produtos_rotulo(dados, volume)
    if produtos_rotulo:
        estado_dose = (
            'Quantidades escaladas matematicamente a partir da dose e do volume de referência '
            'introduzidos pelo agricultor; confirme no rótulo que o produto é adequado ao sistema '
            'e compare com a análise da água.'
        )
    else:
        estado_dose = (
            'Sem doses de rótulo informadas: não será apresentada receita em gramas. '
            'A formulação precisa depende da cultura, análise da água, formulação comercial e fase.'
        )

    if sistema == 'substrato' and temperatura_ar is not None:
        nota_clima = (
            f'Temperatura ambiente informada: {temperatura_ar:.1f} °C. '
            'O número de ciclos não é inferido só do clima/fase; calibre pela humidade, '
            'drenagem e volume medido por planta.'
        )
    else:
        nota_clima = (
            f'Temperatura ambiente informada: {temperatura_ar:.1f} °C; usada como contexto, '
            'não como substituto de medições do sistema.'
            if temperatura_ar is not None else
            'Temperatura ambiente não informada.'
        )

    return {
        'cultura': cultura['nome'],
        'sistema': sistema.upper(),
        'fase': fase,
        'dimensionamento': {
            'area_m2': round(area, 2),
            'comprimento_m': comprimento,
            'largura_m': largura,
            'bancadas': bancadas,
            'largura_bancada_m': largura_bancada,
            'corredor_m': corredor,
            'linhas_por_bancada': linhas_por_bancada,
            'linhas_total': linhas,
            'plantas_por_linha': plantas_por_canal if sistema == 'nft' else plantas_por_linha,
            'plantas_por_canal': plantas_por_canal if sistema == 'nft' else None,
            'canais_por_linha': segmentos_por_linha if sistema == 'nft' else None,
            'comprimento_utilizado_m': round(comprimento_utilizado, 2),
            'canais_ou_linhas': canais,
            'plantas_estimadas': plantas,
            'espacamento_planta_cm': espacamento_planta_cm,
            'espacamento_linha_cm': espacamento_linha_cm,
            **detalhes_fluxo,
        },
        'nutrientes': {
            'volume_l': volume,
            'faixa_ec_min': faixa_ec[0],
            'faixa_ec_max': faixa_ec[1],
            'faixa_ph_min': cultura['ph_min'],
            'faixa_ph_max': cultura['ph_max'],
            'produtos_rotulo': produtos_rotulo,
            'estado_dose': estado_dose,
            'estado_ec': estado_ec,
            'estado_ph': estado_ph,
            'estado_alcalinidade': estado_alcalinidade,
            'estado_agua_fonte': estado_agua_fonte,
            'nota': (
                'CE é uma medida agregada e não identifica nutrientes individuais. '
                'As doses calculadas são somente a escala matemática do rótulo informado; '
                'não são uma fórmula agronómica independente.'
            ),
        },
        'irrigacao': {
            'programacao': programacao,
            'programacao_tabela': tabela_programacao,
            'estado_oxigenio': estado_oxigenio,
            'estado_temperatura': estado_temperatura,
            'nota_reposicao': (
                'O consumo diário de água não é estimado a partir de uma média genérica. '
                'Meça o volume real reposto no reservatório ao longo de 24 horas.'
            ),
            'nota_clima': nota_clima,
        },
        'diagnostico': diagnostico,
        'fontes': FONTES,
        'aviso': (
            'Referências técnicas de extensão universitária são faixas de orientação, '
            'não uma validação para cada variedade, clima ou produto vendido em Moçambique. '
            'Para receita nutricional completa, faça análise laboratorial da água e use '
            'a composição e as instruções do fertilizante escolhido.'
        ),
    }
