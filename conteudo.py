"""
Base de conhecimento do Jornada FIV.
Textos resumidos do documento "Base de conhecimento — Jornada FIV", cada um com a sua fonte.
O site ORIENTA: não diagnostica e nunca sugere dose.
"""

# ---------------------------------------------------------------- fontes
F = {
    "asrm_art": ("ASRM — Reprodução assistida",
                 "https://www.reproductivefacts.org/news-and-publications/fact-sheets-and-infographics/assisted-reproductive-technologies-booklet"),
    "asrm_med": ("ASRM — Medicamentos",
                 "https://integration.reproductivefacts.org/globalassets/_rf/news-and-publications/bookletsfact-sheets/english-pdf/booklet_medications_for_inducing_ovulation.pdf"),
    "asrm_ohss": ("ASRM — Hiperestímulo ovariano",
                  "https://integration.reproductivefacts.org/news-and-publications/fact-sheets-and-infographics/ovarian-hyperstimulation-syndrome-ohss/"),
    "asrm_prog": ("ASRM — Progesterona",
                  "https://prod.reproductivefacts.org/globalassets/_rf/news-and-publications/bookletsfact-sheets/english-pdf/progesterone_supplementation_during_ivf_factsheet.pdf"),
    "nice": ("NICE CG156", "https://www.nice.org.uk/guidance/cg156/chapter/1-Guidance"),
    "nice_vida": ("NICE NG257", "https://www.nice.org.uk/guidance/NG257/chapter/advice-about-factors-that-can-affect-fertility"),
    "nhs": ("NHS — Riscos da FIV", "https://www.nhs.uk/conditions/ivf/risks/"),
    "hfea": ("HFEA — Riscos", "https://hfea.gov.uk/treatments/explore-all-treatments/risks-of-fertility-treatment/"),
    "eshre": ("ESHRE — Guia psicossocial",
              "https://www.eshre.eu/-/media/sitecore-files/Guidelines/Psychology/ESHRE-PSYCHOLOGY-GUIDELINE_Patient-version_15022016.pdf"),
    "cfm": ("Resolução CFM 2.320/2022", "https://ses.sp.bvs.br/wp-content/uploads/2022/09/U_RS-CFM-2320_010922.pdf"),
    "anvisa": ("Anvisa RDC 771/2022", "https://antigo.anvisa.gov.br/documents/10181/5141698/RDC_771_2022_.pdf"),
    "stj": ("STJ — Tema 1.067", "https://www.aasp.org.br/?p=31672"),
    "trf2": ("Parecer técnico TRF2", "https://static.trf2.jus.br/nas-internet/documento/comite-estadual-saude/pareceres/2024/parecer-1145-2024.pdf"),
    "tribuna": ("Tribuna de Minas (reportagem)",
                "https://tribunademinas.com.br/especiais/saude/21-07-2024/fertilizacao-in-vitro-sus.html?amp=1"),
}

# ---------------------------------------------------------------- etapas
# nome: (duração padrão em dias, resumo curto, "o que esperar", efeitos esperados, fontes)
ETAPA_SUS = "Encaminhamento pelo SUS"
ETAPAS = {
    ETAPA_SUS: (60, "UBS, ginecologista e centro de reprodução",
        "O acesso é pelo sistema de regulação: a UBS encaminha ao ginecologista, que encaminha a um centro de "
        "reprodução assistida. Há poucos centros gratuitos no país e a fila costuma ser longa, por isso vale "
        "começar o quanto antes.",
        [], ["trf2", "tribuna"]),
    "Exames e preparação": (28, "Exames dela, do parceiro e do casal",
        "Exames de sangue (incluindo sorologias exigidas pela Anvisa), avaliação da reserva ovariana e "
        "espermograma. É a hora de começar o ácido fólico, evitar álcool e cigarro e contar ao médico todos os "
        "remédios que você usa.",
        [], ["anvisa", "nice", "nice_vida"]),
    "Estimulação ovariana": (11, "Injeções diárias e ultrassons de controle",
        "Injeções diárias fazem vários folículos crescerem ao mesmo tempo, em geral por 8 a 14 dias. Ultrassons "
        "e exames de sangue acompanham a resposta e ajustam o tratamento. No fim, uma injeção de indução "
        "(\"gatilho\") amadurece os óvulos.",
        ["Mama sensível", "Barriga estufada", "Dor abdominal leve", "Mudança de humor",
         "Inchaço ou vermelhidão no local da injeção", "Inchaço leve"],
        ["asrm_art", "asrm_med"]),
    "Coleta dos óvulos": (2, "Procedimento curto, com sedação",
        "A coleta é feita 34 a 36 horas depois do gatilho, com uma agulha guiada por ultrassom e sedação. Dura "
        "menos de 30 minutos e você volta para casa no mesmo dia. A progesterona começa no dia da coleta ou no "
        "seguinte.",
        ["Cólica leve", "Sensação de peso na pelve", "Barriga estufada", "Inchaço leve", "Náusea leve"],
        ["asrm_art", "asrm_prog"]),
    "Fertilização e cultivo": (5, "Os embriões se desenvolvem no laboratório",
        "Os óvulos são fertilizados no laboratório (FIV clássica ou ICSI). A fertilização é confirmada no dia "
        "seguinte e os embriões podem chegar a blastocisto no 5º dia. Nesta fase, os sinais de hiperestímulo "
        "merecem atenção.",
        ["Sensação de peso na pelve", "Barriga estufada", "Inchaço leve"],
        ["asrm_art", "hfea"]),
    "Transferência do embrião": (1, "Procedimento rápido, sem anestesia",
        "Um cateter fino coloca o embrião no útero. Não precisa de anestesia e costuma ser indolor. No Brasil, "
        "até 2 embriões para mulheres de até 37 anos; embriões excedentes viáveis são congelados.",
        ["Cólica leve"],
        ["asrm_art", "cfm"]),
    "Espera pelo teste": (14, "A fase de maior ansiedade",
        "Mantenha a progesterona como prescrita. Não faça teste de farmácia antes da data: o hormônio do gatilho "
        "pode dar falso positivo por cerca de 10 dias. A ansiedade nesta fase é a maior de todo o tratamento, e "
        "pedir apoio faz parte do cuidado.",
        ["Mudança de humor", "Ansiedade", "Cólica leve", "Mama sensível"],
        ["asrm_med", "asrm_prog", "eshre"]),
}
ORDEM_ETAPAS = ["Exames e preparação", "Estimulação ovariana", "Coleta dos óvulos",
                "Fertilização e cultivo", "Transferência do embrião", "Espera pelo teste"]

# ---------------------------------------------------------------- exames
EXAMES = {
    "Sorologias: HIV, hepatites B e C, sífilis": ("casal",
        "Triagem obrigatória pela Anvisa para quem vai usar os próprios óvulos e sêmen.", "anvisa"),
    "Sorologia HTLV I e II": ("parceiro", "Também obrigatória para uso do próprio sêmen.", "anvisa"),
    "Reserva ovariana (AMH, FSH e ultrassom)": ("ela",
        "Ajuda a prever quantos óvulos devem responder ao estímulo.", "nice"),
    "Espermograma": ("parceiro",
        "Avalia quantidade, movimento e forma dos espermatozoides; se alterado, costuma ser repetido.", "nice"),
    "Avaliação das trompas": ("ela",
        "Verifica obstrução; trompa dilatada com líquido costuma ser tratada antes da FIV.", "nice"),
    "Sorologia de rubéola": ("ela",
        "Se não houver imunidade, vacinar e evitar engravidar por pelo menos 1 mês.", "nice"),
    "Preventivo (citopatológico)": ("ela", "Deixar em dia evita atrasar o tratamento.", "nice"),
    "Clamídia": ("ela", "Rastrear antes de procedimentos no útero e tratar se positivo.", "nice"),
}

# ---------------------------------------------------------------- medicamentos
# classe: (para que serve, efeitos comuns, fonte)
CLASSES = {
    "Gonadotrofina (estímulo dos ovários)": (
        "Faz vários folículos crescerem ao mesmo tempo.",
        "Mama sensível, inchaço no local da injeção, barriga estufada, dor abdominal leve, oscilação de humor.",
        "asrm_med"),
    "Antagonista de GnRH": (
        "Impede a ovulação antes da hora da coleta.",
        "Efeitos parecidos com os do agonista: calorões e oscilação de humor.",
        "asrm_med"),
    "Agonista de GnRH": (
        "Desliga temporariamente o ciclo natural; também pode servir de gatilho.",
        "Calorões, oscilação de humor e secura vaginal, que passam após o uso.",
        "asrm_med"),
    "Gatilho (hCG)": (
        "Amadurece os óvulos; a coleta é marcada cerca de 36 horas depois.",
        "Pode dar falso positivo no teste de gravidez por cerca de 10 dias.",
        "asrm_med"),
    "Progesterona": (
        "Prepara e sustenta a parede do útero para receber o embrião.",
        "A fonte consultada não detalha efeitos; tire dúvidas com a sua clínica.",
        "asrm_prog"),
    "Indutor oral (clomifeno, letrozol)": (
        "Aumenta o FSH do próprio corpo; mais usado em tratamentos de baixa complexidade.",
        "Calorões, oscilação de humor, mama sensível, náusea. Dor de cabeça forte ou alteração na visão: avise o médico.",
        "asrm_med"),
    "Cabergolina": (
        "Baixa a prolactina e ajuda a prevenir o hiperestímulo.",
        "Nariz entupido, cansaço, dor de cabeça, náusea, tontura.",
        "asrm_med"),
    "Ácido fólico": (
        "Reduz o risco de defeitos do tubo neural do bebê.",
        "Usado antes da concepção até 12 semanas de gestação.",
        "nice"),
    "Outro": ("Pergunte à sua clínica para que serve este medicamento.", "", None),
}

# ---------------------------------------------------------------- sintomas
SINTOMAS_COMUNS = ["Mama sensível", "Barriga estufada", "Dor abdominal leve", "Inchaço leve",
                   "Mudança de humor", "Ansiedade", "Náusea leve", "Cólica leve",
                   "Sensação de peso na pelve", "Inchaço ou vermelhidão no local da injeção",
                   "Dor de cabeça", "Cansaço"]
ALERTA_CLINICA = ["Dor e inchaço forte na barriga", "Vômito que não passa", "Ganho de peso rápido (mais de 1,4 kg em 2 dias)",
                  "Urinando menos que o normal", "Sensação de desmaio", "Sangramento vaginal",
                  "Dor de um lado só na parte baixa da barriga", "Dor ao evacuar ou urinar",
                  "Dor de cabeça forte ou alteração na visão"]
ALERTA_EMERGENCIA = ["Falta de ar", "Dor no peito ou na parte de cima das costas", "Dor na ponta do ombro",
                     "Muita sede e urina muito reduzida", "Perna inchada, vermelha ou dolorida",
                     "Dormência no rosto ou fraqueza súbita", "Tosse com sangue"]
FONTES_ALERTA = ["nhs", "asrm_ohss", "hfea"]

# ---------------------------------------------------------------- caminhos
CAMINHOS = {
    "SUS": ("Pelo SUS", [
        "Procure a UBS e peça avaliação ginecológica; o acesso aos centros é pelo sistema de regulação.",
        "Há poucos centros de FIV gratuitos no país e a fila costuma ser longa (cerca de 2 anos, segundo reportagem de 2024).",
        "Muitos centros atendem mulheres até 35 anos: entre na fila o quanto antes.",
    ], ["trf2", "tribuna"]),
    "convenio": ("Pelo convênio", [
        "O STJ decidiu que o plano só é obrigado a pagar a FIV se o contrato prever expressamente.",
        "Confira no contrato o que é coberto: consultas, exames, medicação e procedimentos.",
        "Peça por escrito o que será pago à parte.",
    ], ["stj"]),
    "particular": ("Particular", [
        "Compare clínicas e peça orçamento completo, por escrito.",
        "Pergunte se medicação, congelamento de embriões e novas transferências estão incluídos.",
        "Pelas regras do CFM, embriões excedentes viáveis são congelados; o casal define por escrito o destino deles.",
    ], ["cfm"]),
}


def fontes(chaves):
    """Converte chaves de fonte em lista de (título, url)."""
    return [F[c] for c in chaves if c in F]


# ---------------------------------------------------------------- apoio emocional
# O que é comum sentir em cada etapa (ESHRE, guia psicossocial para pacientes; ASRM para efeitos das medicações).
EMOCIONAL = {
    ETAPA_SUS: ("A espera pela vaga pode trazer frustração e sensação de que o tempo está passando. "
                "Conversar sobre isso com a parceria e com pessoas de confiança ajuda.", ["eshre"]),
    "Exames e preparação": ("Antes do tratamento, estresse e tristeza são comuns, e as mulheres costumam "
                            "relatar mais esses sentimentos que os homens. Isso não é fraqueza: é uma resposta "
                            "natural a um momento difícil.", ["eshre"]),
    "Estimulação ovariana": ("Muitas pacientes se sentem otimistas nesta fase. As medicações hormonais podem "
                             "causar oscilações de humor: se você estiver mais sensível, isso pode ter relação "
                             "com o tratamento.", ["eshre", "asrm_med"]),
    "Coleta dos óvulos": ("A ansiedade costuma aumentar antes de procedimentos como a coleta, e o cansaço "
                          "físico também é comum. Ter alguém por perto nesse dia faz diferença.", ["eshre"]),
    "Fertilização e cultivo": ("Esperar notícias do laboratório pode ser angustiante. Informação clara sobre "
                               "cada etapa ajuda a diminuir a ansiedade.", ["eshre"]),
    "Transferência do embrião": ("A ansiedade costuma aumentar antes da transferência. Muitas mulheres também "
                                 "relatam se sentir mais próximas da parceria nesta fase.", ["eshre"]),
    "Espera pelo teste": ("Esta é a fase em que a ansiedade e o estresse chegam ao ponto mais alto de todo o "
                          "tratamento. Cuidar de si e pedir apoio faz parte do processo.", ["eshre"]),
}
EMOCIONAL_PARCERIA = ("A parceria também sente: os homens tendem a se mostrar firmes para apoiar, mas podem se "
                      "sentir mais isolados. Envolver os dois em cada etapa ajuda o casal.", ["eshre"])
HUMORES = {1: "Muito difícil", 2: "Difícil", 3: "Neutro", 4: "Bem", 5: "Muito bem"}
