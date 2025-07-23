# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template, session, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS 
import time
import threading
from collections import defaultdict
import logging
import random
import string

logging.basicConfig(level=logging.DEBUG) 
logger = logging.getLogger(__name__)
werkzeug_logger = logging.getLogger('werkzeug') 
werkzeug_logger.setLevel(logging.INFO) 

try:
    import eventlet
    eventlet.monkey_patch() 
    ASYNC_MODE = 'eventlet'
    logger.info("Eventlet encontrado e monkey_patch() aplicado.")
except ImportError:
    logger.warning("Eventlet não encontrado. Usando async_mode='threading'.")
    ASYNC_MODE = 'threading'

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'bict_quiz_ufma_salas_super_secretas_eventlet_v13!' # Nova chave
socketio = SocketIO(app,
                    async_mode=ASYNC_MODE,
                    cors_allowed_origins="*",
                    logger=True,              
                    engineio_logger=True)     

logger.info(f"SocketIO inicializado com async_mode: {socketio.async_mode}")

# --- Definição das Questões ---
class QuizOption:
    def __init__(self, id: str, text: str): self.id = id; self.text = text
    def to_dict(self): return {"id": self.id, "text": self.text}

class QuizQuestion:
    def __init__(self, id: str, text: str, options: list[QuizOption], correct_option_id: str, skill_area: str, difficulty: str):
        self.id, self.text, self.options, self.correct_option_id, self.skill_area, self.difficulty = id, text, options, correct_option_id, skill_area, difficulty
    def to_dict(self):
        return {"id": self.id, "text": self.text, "options": [opt.to_dict() for opt in self.options],
                "correctOptionId": self.correct_option_id, "skillArea": self.skill_area, "difficulty": self.difficulty}

# Questões do Desafio 1 (já existentes + acrescentei 6 novas)
challenge_1_questions_data = [
  {"id": "nq1","text": "Se um algoritmo é uma sequência finita de instruções para resolver um problema, qual das seguintes opções MELHOR descreve uma característica essencial de um bom algoritmo?","options": [{"id": "nq1_opt1", "text": "Ser escrito na linguagem de programação mais recente."}, {"id": "nq1_opt2", "text": "Ser o mais curto possível, mesmo que difícil de entender."}, {"id": "nq1_opt3", "text": "Ser eficiente em termos de tempo e recursos, e ser claro."}, {"id": "nq1_opt4", "text": "Funcionar apenas para um conjunto específico de dados de entrada."}],"correctOptionId": "nq1_opt3","skillArea": "BICT - Lógica de Programação","difficulty": "Fácil"},
  {"id": "nq2","text": "No contexto de redes de computadores, o que significa a sigla 'IP' em 'Endereço IP'?","options": [{"id": "nq2_opt1", "text": "Internal Protocol"}, {"id": "nq2_opt2", "text": "Internet Protocol"}, {"id": "nq2_opt3", "text": "Instruction Pointer"}, {"id": "nq2_opt4", "text": "Immediate Power"}],"correctOptionId": "nq2_opt2","skillArea": "BICT - Redes de Computadores","difficulty": "Fácil"},
  {"id": "nq3","text": "Qual o resultado da expressão lógica: (VERDADEIRO OU FALSO) E (NÃO FALSO)?","options": [{"id": "nq3_opt1", "text": "VERDADEIRO"}, {"id": "nq3_opt2", "text": "FALSO"}, {"id": "nq3_opt3", "text": "Depende"}, {"id": "nq3_opt4", "text": "Inválido"}],"correctOptionId": "nq3_opt1","skillArea": "BICT - Matemática Discreta","difficulty": "Fácil"},
  {"id": "nq4","text": "Em Engenharia de Computação, qual componente de um computador é responsável por executar a maioria das instruções e cálculos?","options": [{"id": "nq4_opt1", "text": "Memória RAM"}, {"id": "nq4_opt2", "text": "Disco Rígido (HD/SSD)"}, {"id": "nq4_opt3", "text": "Unidade Central de Processamento (CPU)"}, {"id": "nq4_opt4", "text": "Placa de Vídeo (GPU)"}],"correctOptionId": "nq4_opt3","skillArea": "Eng. Computação - Arquitetura de Computadores","difficulty": "Fácil"},
  {"id": "nq5","text": "Um engenheiro civil está projetando uma viga para uma ponte. Qual dos seguintes materiais é comumente escolhido por sua alta resistência à compressão?","options": [{"id": "nq5_opt1", "text": "Madeira Leve"}, {"id": "nq5_opt2", "text": "Borracha Vulcanizada"}, {"id": "nq5_opt3", "text": "Concreto Armado"}, {"id": "nq5_opt4", "text": "Plástico PVC"}],"correctOptionId": "nq5_opt3","skillArea": "Eng. Civil - Materiais de Construção","difficulty": "Médio"},
  {"id": "nq6","text": "Qual lei da termodinâmica afirma que a energia não pode ser criada nem destruída, apenas transformada de uma forma para outra?","options": [{"id": "nq6_opt1", "text": "Lei Zero"}, {"id": "nq6_opt2", "text": "Primeira Lei"}, {"id": "nq6_opt3", "text": "Segunda Lei"}, {"id": "nq6_opt4", "text": "Terceira Lei"}],"correctOptionId": "nq6_opt2","skillArea": "Eng. Mecânica - Termodinâmica","difficulty": "Médio"},
  {"id": "nq7","text": "Um carro de Fórmula 1 utiliza um aerofólio traseiro para gerar 'downforce'. Este efeito está mais relacionado a qual princípio da física?","options": [{"id": "nq7_opt1", "text": "Efeito Doppler"}, {"id": "nq7_opt2", "text": "Princípio de Arquimedes"}, {"id": "nq7_opt3", "text": "Princípio de Bernoulli (relacionado à diferença de pressão)"}, {"id": "nq7_opt4", "text": "Lei da Gravitação Universal"}],"correctOptionId": "nq7_opt3","skillArea": "Eng. Aeroespacial - Aerodinâmica","difficulty": "Médio"},
  {"id": "nq8","text": "Qual das seguintes ações é uma medida fundamental na Engenharia Ambiental para mitigar o impacto de resíduos sólidos urbanos?","options": [{"id": "nq8_opt1", "text": "Aumentar a capacidade dos aterros sanitários existentes."},{"id": "nq8_opt2", "text": "Incentivar o consumo descartável para facilitar a coleta."},{"id": "nq8_opt3", "text": "Implementar programas de coleta seletiva e reciclagem."},{"id": "nq8_opt4", "text": "Queimar todos os resíduos a céu aberto para reduzir volume."}],"correctOptionId": "nq8_opt3","skillArea": "Eng. Ambiental - Gestão de Resíduos","difficulty": "Fácil"},
  {"id": "nq9","text": "Em Engenharia de Transportes, o planejamento de um sistema de semáforos em um cruzamento visa principalmente:","options": [{"id": "nq9_opt1", "text": "Aumentar a velocidade média dos veículos na via."},{"id": "nq9_opt2", "text": "Priorizar exclusivamente o fluxo de transporte público."},{"id": "nq9_opt3", "text": "Otimizar o fluxo de veículos e a segurança de pedestres."},{"id": "nq9_opt4", "text": "Reduzir o número de faixas de rolamento."}],"correctOptionId": "nq9_opt3","skillArea": "Eng. Transportes - Engenharia de Tráfego","difficulty": "Médio"},
  {"id": "nq10","text": "Se um terreno retangular tem 20 metros de frente e 30 metros de profundidade, qual é a sua área total?","options": [{"id": "nq10_opt1", "text": "50 m²"},{"id": "nq10_opt2", "text": "100 m²"},{"id": "nq10_opt3", "text": "600 m²"},{"id": "nq10_opt4", "text": "500 m²"}],"correctOptionId": "nq10_opt3","skillArea": "Cálculo Básico - Geometria","difficulty": "Fácil"},
  {"id": "nq11","text": "Um projeto requer que uma peça metálica se expanda no máximo 0.05mm com o calor. O engenheiro precisa calcular a variação de temperatura permitida. Qual conceito físico é fundamental aqui?","options": [{"id": "nq11_opt1", "text": "Resistência Elétrica"},{"id": "nq11_opt2", "text": "Dilatação Térmica"},{"id": "nq11_opt3", "text": "Capacitância"},{"id": "nq11_opt4", "text": "Momento de Inércia"}],"correctOptionId": "nq11_opt2","skillArea": "Física Aplicada - Termologia","difficulty": "Médio"},
  {"id": "nq12","text": "Se você tem um conjunto de dados de medições e precisa encontrar o valor que ocorre com maior frequência, qual medida estatística você usaria?","options": [{"id": "nq12_opt1", "text": "Média Aritmética"},{"id": "nq12_opt2", "text": "Mediana"},{"id": "nq12_opt3", "text": "Moda"},{"id": "nq12_opt4", "text": "Desvio Padrão"}],"correctOptionId": "nq12_opt3","skillArea": "BICT - Estatística Básica","difficulty": "Fácil"},
  # Novas perguntas para o Desafio 1
  {"id": "nq13_comp", "text": "Em ciência da computação, qual das seguintes estruturas de dados é mais eficiente para acessar elementos por índice, mas menos eficiente para inserções ou remoções no meio da sequência?", "options": [{"id": "nq13_comp_opt1", "text": "Lista Encadeada"}, {"id": "nq13_comp_opt2", "text": "Árvore Binária"}, {"id": "nq13_comp_opt3", "text": "Array (Vetor)"}, {"id": "nq13_comp_opt4", "text": "Fila"}], "correctOptionId": "nq13_comp_opt3", "skillArea": "Eng. Computação - Estruturas de Dados", "difficulty": "Médio"},
  {"id": "nq14_civil", "text": "No dimensionamento de estruturas de concreto armado, qual a principal função das barras de aço (armadura) inseridas no concreto?", "options": [{"id": "nq14_civil_opt1", "text": "Aumentar o peso da estrutura"}, {"id": "nq14_civil_opt2", "text": "Resistir aos esforços de tração"}, {"id": "nq14_civil_opt3", "text": "Melhorar o isolamento térmico"}, {"id": "nq14_civil_opt4", "text": "Acelerar a secagem do concreto"}], "correctOptionId": "nq14_civil_opt2", "skillArea": "Eng. Civil - Concreto Armado", "difficulty": "Médio"},
  {"id": "nq15_mec", "text": "Qual das seguintes leis da Termodinâmica estabelece que a entropia de um sistema isolado nunca diminui com o tempo, tendendo a um máximo?", "options": [{"id": "nq15_mec_opt1", "text": "Lei Zero da Termodinâmica"}, {"id": "nq15_mec_opt2", "text": "Primeira Lei da Termodinâmica"}, {"id": "nq15_mec_opt3", "text": "Segunda Lei da Termodinâmica"}, {"id": "nq15_mec_opt4", "text": "Terceira Lei da Termodinâmica"}], "correctOptionId": "nq15_mec_opt3", "skillArea": "Eng. Mecânica - Termodinâmica", "difficulty": "Médio"},
  {"id": "nq16_aero", "text": "Para que um objeto permaneça em órbita estável ao redor da Terra, qual força deve estar em equilíbrio com a força centrífuga gerada pelo movimento do objeto?", "options": [{"id": "nq16_aero_opt1", "text": "Força de arrasto atmosférico"}, {"id": "nq16_aero_opt2", "text": "Força de atrito"}, {"id": "nq16_aero_opt3", "text": "Força gravitacional"}, {"id": "nq16_aero_opt4", "text": "Força de sustentação"}], "correctOptionId": "nq16_aero_opt3", "skillArea": "Eng. Aeroespacial - Mecânica Orbital", "difficulty": "Médio"},
  {"id": "nq17_amb", "text": "Qual o principal objetivo do tratamento de esgoto sanitário em uma Estação de Tratamento de Esgoto (ETE) antes do descarte no ambiente?", "options": [{"id": "nq17_amb_opt1", "text": "Aumentar a quantidade de água disponível"}, {"id": "nq17_amb_opt2", "text": "Remover poluentes e patógenos para proteger a saúde pública e os ecossistemas"}, {"id": "nq17_amb_opt3", "text": "Produzir energia elétrica"}, {"id": "nq17_amb_opt4", "text": "Gerar fertilizantes para a agricultura"}], "correctOptionId": "nq17_amb_opt2", "skillArea": "Eng. Ambiental - Saneamento Básico", "difficulty": "Médio"},
  {"id": "nq18_trans", "text": "No planejamento de transportes, o que representa o conceito de 'capacidade de uma via'?", "options": [{"id": "nq18_trans_opt1", "text": "A velocidade máxima permitida na via"}, {"id": "nq18_trans_opt2", "text": "O número máximo de veículos que podem passar por um ponto da via em um determinado período"}, {"id": "nq18_trans_opt3", "text": "O comprimento total da via"}, {"id": "nq18_trans_opt4", "text": "A largura da via em metros"}], "correctOptionId": "nq18_trans_opt2", "skillArea": "Eng. Transportes - Engenharia de Tráfego", "difficulty": "Médio"}
]

# Novas questões para o Desafio 2 (nível mais básico - calouros)
challenge_2_questions_data = [
    # Engenharia de Computação (3 perguntas)
    {"id": "c2_comp1", "text": "Qual é a principal função de um 'algoritmo' na programação de computadores?", "options": [{"id": "c2_comp1_opt1", "text": "Escrever textos"}, {"id": "c2_comp1_opt2", "text": "Resolver problemas passo a passo"}, {"id": "c2_comp1_opt3", "text": "Desenhar imagens"}, {"id": "c2_comp1_opt4", "text": "Tocar música"}], "correctOptionId": "c2_comp1_opt2", "skillArea": "Eng. Computação - Fundamentos de Programação", "difficulty": "Muito Fácil"},
    {"id": "c2_comp2", "text": "O que significa a sigla 'CPU' em um computador?", "options": [{"id": "c2_comp2_opt1", "text": "Central Power Unit"}, {"id": "c2_comp2_opt2", "text": "Computer Processing Utility"}, {"id": "c2_comp2_opt3", "text": "Central Processing Unit"}, {"id": "c2_comp2_opt4", "text": "Core Program Unit"}], "correctOptionId": "c2_comp2_opt3", "skillArea": "Eng. Computação - Hardware Básico", "difficulty": "Muito Fácil"},
    {"id": "c2_comp3", "text": "Qual das seguintes opções é um exemplo de linguagem de programação usada para criar páginas web interativas?", "options": [{"id": "c2_comp3_opt1", "text": "Microsoft Word"}, {"id": "c2_comp3_opt2", "text": "JavaScript"}, {"id": "c2_comp3_opt3", "text": "Adobe Photoshop"}, {"id": "c2_comp3_opt4", "text": "Excel"}], "correctOptionId": "c2_comp3_opt2", "skillArea": "Eng. Computação - Desenvolvimento Web", "difficulty": "Fácil"},

    # Engenharia Civil (3 perguntas)
    {"id": "c2_civil1", "text": "Qual o principal objetivo de uma 'fundação' em um edifício?", "options": [{"id": "c2_civil1_opt1", "text": "Decorar o exterior"}, {"id": "c2_civil1_opt2", "text": "Suportar o peso da estrutura e distribuí-lo no solo"}, {"id": "c2_civil1_opt3", "text": "Proteger contra raios"}, {"id": "c2_civil1_opt4", "text": "Armazenar água"}], "correctOptionId": "c2_civil1_opt2", "skillArea": "Eng. Civil - Estruturas Básicas", "difficulty": "Muito Fácil"},
    {"id": "c2_civil2", "text": "O que é o 'concreto' na construção civil?", "options": [{"id": "c2_civil2_opt1", "text": "Um tipo de madeira"}, {"id": "c2_civil2_opt2", "text": "Uma mistura de cimento, água, areia e brita"}, {"id": "c2_civil2_opt3", "text": "Uma chapa de metal"}, {"id": "c2_civil2_opt4", "text": "Um tipo de vidro"}], "correctOptionId": "c2_civil2_opt2", "skillArea": "Eng. Civil - Materiais de Construção", "difficulty": "Fácil"},
    {"id": "c2_civil3", "text": "Qual a importância de um engenheiro civil no planejamento de cidades?", "options": [{"id": "c2_civil3_opt1", "text": "Apenas projetar casas"}, {"id": "c2_civil3_opt2", "text": "Desenvolver infraestruturas como estradas, pontes e sistemas de saneamento"}, {"id": "c2_civil3_opt3", "text": "Cuidar do paisagismo"}, {"id": "c2_civil3_opt4", "text": "Gerenciar o tráfego de veículos"}], "correctOptionId": "c2_civil3_opt2", "skillArea": "Eng. Civil - Urbanismo e Infraestrutura", "difficulty": "Fácil"},

    # Engenharia Mecânica (3 perguntas)
    {"id": "c2_mec1", "text": "Qual o principal objetivo de um motor, como o de um carro?", "options": [{"id": "c2_mec1_opt1", "text": "Gerar eletricidade"}, {"id": "c2_mec1_opt2", "text": "Converter energia (química ou outra) em movimento"}, {"id": "c2_mec1_opt3", "text": "Purificar o ar"}, {"id": "c2_mec1_opt4", "text": "Aquecer o veículo"}], "correctOptionId": "c2_mec1_opt2", "skillArea": "Eng. Mecânica - Fundamentos de Máquinas", "difficulty": "Muito Fácil"},
    {"id": "c2_mec2", "text": "O que é uma 'engrenagem' e para que serve em um sistema mecânico?", "options": [{"id": "c2_mec2_opt1", "text": "Um tipo de parafuso"}, {"id": "c2_mec2_opt2", "text": "Uma roda dentada usada para transmitir movimento e força"}, {"id": "c2_mec2_opt3", "text": "Um sensor de temperatura"}, {"id": "c2_mec2_opt4", "text": "Um isolante elétrico"}], "correctOptionId": "c2_mec2_opt2", "skillArea": "Eng. Mecânica - Elementos de Máquinas", "difficulty": "Fácil"},
    {"id": "c2_mec3", "text": "Qual o conceito que estuda como o calor se transforma em outras formas de energia e vice-versa?", "options": [{"id": "c2_mec3_opt1", "text": "Eletricidade"}, {"id": "c2_mec3_opt2", "text": "Óptica"}, {"id": "c2_mec3_opt3", "text": "Termodinâmica"}, {"id": "c2_mec3_opt4", "text": "Acústica"}], "correctOptionId": "c2_mec3_opt3", "skillArea": "Eng. Mecânica - Termodinâmica", "difficulty": "Fácil"},

    # Engenharia Aeroespacial (3 perguntas)
    {"id": "c2_aero1", "text": "Qual princípio físico fundamental explica como as asas de um avião geram sustentação para voar?", "options": [{"id": "c2_aero1_opt1", "text": "Lei da Gravidade"}, {"id": "c2_aero1_opt2", "text": "Princípio de Bernoulli (diferença de pressão)"}, {"id": "c2_aero1_opt3", "text": "Lei de Ohm"}, {"id": "c2_aero1_opt4", "text": "Princípio da Conservação de Massa"}], "correctOptionId": "c2_aero1_opt2", "skillArea": "Eng. Aeroespacial - Aerodinâmica Básica", "difficulty": "Fácil"},
    {"id": "c2_aero2", "text": "Qual a principal diferença entre a propulsão de um avião a jato e a de um foguete?", "options": [{"id": "c2_aero2_opt1", "text": "Aviões usam rodas e foguetes não"}, {"id": "c2_aero2_opt2", "text": "Aviões precisam de ar para queimar combustível, foguetes carregam seu próprio oxidante"}, {"id": "c2_aero2_opt3", "text": "Aviões voam mais rápido"}, {"id": "c2_aero2_opt4", "text": "Foguetes são maiores"}], "correctOptionId": "c2_aero2_opt2", "skillArea": "Eng. Aeroespacial - Propulsão", "difficulty": "Médio"},
    {"id": "c2_aero3", "text": "Para que serve um satélite artificial em órbita da Terra?", "options": [{"id": "c2_aero3_opt1", "text": "Apenas para observar estrelas"}, {"id": "c2_aero3_opt2", "text": "Comunicações, previsão do tempo, navegação (GPS)"}, {"id": "c2_aero3_opt3", "text": "Coletar lixo espacial"}, {"id": "c2_aero3_opt4", "text": "Ajudar na agricultura"}], "correctOptionId": "c2_aero3_opt2", "skillArea": "Eng. Aeroespacial - Aplicações Espaciais", "difficulty": "Fácil"},

    # Engenharia Ambiental (3 perguntas)
    {"id": "c2_amb1", "text": "O que é 'reciclagem' e por que ela é importante para o meio ambiente?", "options": [{"id": "c2_amb1_opt1", "text": "Queimar lixo para produzir energia"}, {"id": "c2_amb1_opt2", "text": "Transformar materiais usados em novos produtos para reduzir o descarte"}, {"id": "c2_amb1_opt3", "text": "Jogar lixo em aterros"}, {"id": "c2_amb1_opt4", "text": "Usar mais produtos descartáveis"}], "correctOptionId": "c2_amb1_opt2", "skillArea": "Eng. Ambiental - Gestão de Resíduos", "difficulty": "Muito Fácil"},
    {"id": "c2_amb2", "text": "Qual o nome do fenômeno natural que mantém a Terra aquecida, mas que pode ser intensificado pela poluição, causando mudanças climáticas?", "options": [{"id": "c2_amb2_opt1", "text": "Chuva ácida"}, {"id": "c2_amb2_opt2", "text": "Efeito estufa"}, {"id": "c2_amb2_opt3", "text": "Camada de ozônio"}, {"id": "c2_amb2_opt4", "text": "Maré alta"}], "correctOptionId": "c2_amb2_opt2", "skillArea": "Eng. Ambiental - Clima e Poluição", "difficulty": "Fácil"},
    {"id": "c2_amb3", "text": "Qual das seguintes é uma fonte de energia considerada 'limpa' ou renovável?", "options": [{"id": "c2_amb3_opt1", "text": "Carvão mineral"}, {"id": "c2_amb3_opt2", "text": "Petróleo"}, {"id": "c2_amb3_opt3", "text": "Energia solar"}, {"id": "c2_amb3_opt4", "text": "Gás natural"}], "correctOptionId": "c2_amb3_opt3", "skillArea": "Eng. Ambiental - Energias Renováveis", "difficulty": "Muito Fácil"},

    # Engenharia de Transportes (3 perguntas)
    {"id": "c2_trans1", "text": "Qual o principal objetivo de um sistema de transporte público bem planejado em uma cidade?", "options": [{"id": "c2_trans1_opt1", "text": "Apenas transportar carros"}, {"id": "c2_trans1_opt2", "text": "Reduzir engarrafamentos e poluição, e oferecer mobilidade acessível"}, {"id": "c2_trans1_opt3", "text": "Construir mais estacionamentos"}, {"id": "c2_trans1_opt4", "text": "Aumentar o número de semáforos"}], "correctOptionId": "c2_trans1_opt2", "skillArea": "Eng. Transportes - Mobilidade Urbana", "difficulty": "Muito Fácil"},
    {"id": "c2_trans2", "text": "Por que é importante para um país ter uma boa rede de estradas e ferrovias?", "options": [{"id": "c2_trans2_opt1", "text": "Para que as pessoas possam passear de carro"}, {"id": "c2_trans2_opt2", "text": "Para facilitar o transporte de mercadorias e pessoas, impulsionando a economia"}, {"id": "c2_trans2_opt3", "text": "Para criar mais empregos para motoristas"}, {"id": "c2_trans2_opt4", "text": "Para que os veículos sejam mais rápidos"}], "correctOptionId": "c2_trans2_opt2", "skillArea": "Eng. Transportes - Infraestrutura", "difficulty": "Fácil"},
    {"id": "c2_trans3", "text": "O que é um 'plano de mobilidade urbana'?", "options": [{"id": "c2_trans3_opt1", "text": "Um mapa de ruas"}, {"id": "c2_trans3_opt2", "text": "Um documento que organiza como as pessoas e mercadorias se movem na cidade, buscando eficiência e sustentabilidade"}, {"id": "c2_trans3_opt3", "text": "Uma lista de empresas de ônibus"}, {"id": "c2_trans3_opt4", "text": "Um guia turístico"}], "correctOptionId": "c2_trans3_opt2", "skillArea": "Eng. Transportes - Planejamento Urbano", "difficulty": "Fácil"}
]

# Converte os dados das questões em objetos QuizQuestion
challenge_1_questions = [QuizQuestion(q["id"], q["text"], [QuizOption(opt["id"], opt["text"]) for opt in q["options"]], q["correctOptionId"], q["skillArea"], q["difficulty"]) for q in challenge_1_questions_data]
challenge_2_questions = [QuizQuestion(q["id"], q["text"], [QuizOption(opt["id"], opt["text"]) for opt in q["options"]], q["correctOptionId"], q["skillArea"], q["difficulty"]) for q in challenge_2_questions_data]

# Dicionário para armazenar todos os conjuntos de questões
ALL_CHALLENGES = {
    "desafio1": challenge_1_questions,
    "desafio2": challenge_2_questions
}

# TOTAL_QUESTIONS será dinâmico, dependendo do desafio escolhido para a sala
# Não defini TOTAL_QUESTIONS aqui globalmente, ele será obtido da sala

rooms_data = {} 
rooms_lock = threading.Lock()

def generate_room_pin(length=5):
    logger.debug("generate_room_pin: Iniciando geração de PIN.")
    while True:
        pin = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        with rooms_lock: 
            if pin not in rooms_data:
                logger.debug(f"generate_room_pin: PIN gerado e único: {pin}")
                return pin

@app.route('/')
def index_page(): return render_template('index.html')
@app.route('/lobby') 
def lobby_page(): return render_template('lobby.html')
@app.route('/quiz')
def quiz_page(): return render_template('quiz.html')
@app.route('/results')
def results_page(): return render_template('results.html')

# --- Funções Auxiliares do Quiz ---
def _start_quiz_logic(room_pin): 
    # Esta função assume que rooms_lock já foi adquirido
    room = rooms_data.get(room_pin)
    if not room:
        logger.error(f"_start_quiz_logic chamada para sala inexistente: {room_pin}")
        return

    # Obter o conjunto de questões para o desafio da sala
    current_challenge_questions = ALL_CHALLENGES.get(room["challenge_type"], challenge_1_questions)
    total_questions_for_room = len(current_challenge_questions)

    logger.info(f"Sala {room_pin}: Dentro de _start_quiz_logic: Iniciando lógica do quiz para desafio '{room['challenge_type']}'.")
    room["game_state"]["current_question_index"] = -1
    room["game_state"]["quiz_active"] = True
    room["game_state"]["question_start_time"] = None
    room["game_state"]["total_questions_in_challenge"] = total_questions_for_room # Armazena o total de questões para a sala
    
    if room["game_state"].get("question_timer_thread") and room["game_state"]["question_timer_thread"].is_alive():
        logger.debug(f"Sala {room_pin}: _start_quiz_logic: Timer anterior ainda ativo (será ignorado).")
    room["game_state"]["question_timer_thread"] = None
    for p_data in room["players"].values(): 
        p_data["score"] = 0
        p_data["answers"] = {}
        if "answered_current_question" in p_data:
            del p_data["answered_current_question"]
    
    logger.info(f"Sala {room_pin}: _start_quiz_logic: Emitindo 'quiz_started'.")
    socketio.emit('quiz_started', {"message": "O quiz vai começar!", "roomPin": room_pin}, room=room_pin)
    _advance_question_for_room(room_pin) # Esta também assume lock


def _reset_room_quiz_state(room_pin):
    # Esta função assume que rooms_lock já foi adquirido
    room = rooms_data.get(room_pin)
    if not room: 
        logger.error(f"_reset_room_quiz_state chamada para sala inexistente: {room_pin}")
        return

    room["game_state"] = {
        "current_question_index": -1, "quiz_active": False, "question_start_time": None,
        "time_per_question": 20, "question_timer_thread": None,
        "total_questions_in_challenge": 0 # Será atualizado em _start_quiz_logic
    }
    for player_sid_key in list(room["players"].keys()): 
        player_data = room["players"].get(player_sid_key)
        if player_data:
            player_data["score"] = 0
            player_data["answers"] = {}
            if "answered_current_question" in player_data:
                del player_data["answered_current_question"]
    logger.info(f"Estado do quiz resetado para a sala {room_pin}.")


def _get_current_question_for_room(room_pin):
    # Esta função assume que rooms_lock já foi adquirido
    room = rooms_data.get(room_pin)
    if not room or not room["game_state"]["quiz_active"]: return None
    
    idx = room["game_state"]["current_question_index"]
    challenge_type = room.get("challenge_type", "desafio1") # Pega o tipo de desafio da sala
    current_challenge_questions = ALL_CHALLENGES.get(challenge_type, challenge_1_questions) # Pega as questões corretas
    
    if 0 <= idx < len(current_challenge_questions):
        return current_challenge_questions[idx]
    return None

def _advance_question_for_room(room_pin):
    # Esta função assume que rooms_lock já foi adquirido
    room = rooms_data.get(room_pin)
    if not room or not room["game_state"]["quiz_active"]:
        logger.debug(f"Advance Q para sala {room_pin}: Quiz não ativo.")
        return

    room["game_state"]["current_question_index"] += 1
    idx = room["game_state"]["current_question_index"]
    
    total_questions_for_room = room["game_state"]["total_questions_in_challenge"] # Usa o total armazenado na sala
    current_challenge_questions = ALL_CHALLENGES.get(room["challenge_type"], challenge_1_questions) # Pega as questões corretas

    if idx < total_questions_for_room:
        current_q = current_challenge_questions[idx]
        logger.info(f"Sala {room_pin}: Avançando para P{idx + 1} - {current_q.text[:30]}...")
        room["game_state"]["question_start_time"] = time.time()
        for player_sid_key in list(room["players"].keys()): 
            player_data = room["players"].get(player_sid_key)
            if player_data and "answered_current_question" in player_data:
                del player_data["answered_current_question"]
        
        payload = {"question": current_q.to_dict(), "questionNumber": idx + 1,
                   "totalQuestions": total_questions_for_room, "timeLimit": room["game_state"]["time_per_question"]}
        socketio.emit('new_question', payload, room=room_pin)
        _start_question_timer_for_room(room_pin) # Esta também assume lock
    else:
        logger.info(f"Sala {room_pin}: Fim das perguntas. Finalizando quiz.")
        _end_quiz_for_room(room_pin) # Esta também assume lock


def _question_timer_logic_for_room(room_pin_arg): 
    logger.debug(f"[Timer Sala {room_pin_arg}] Thread iniciada.")
    initial_question_index = -1 
    time_to_wait = 20 

    with rooms_lock: 
        room = rooms_data.get(room_pin_arg) 
        if not room: 
            logger.warning(f"[Timer Sala {room_pin_arg}] Sala não existe mais no início da thread. Timer encerrando.")
            return
        initial_question_index = room["game_state"]["current_question_index"]
        time_to_wait = room["game_state"]["time_per_question"]
    
    logger.info(f"[Timer Sala {room_pin_arg} - Q{initial_question_index + 1}] Esperando {time_to_wait}s.")
    socketio.sleep(time_to_wait + 0.5) 

    with rooms_lock: 
        room = rooms_data.get(room_pin_arg) 
        if not room:
            logger.warning(f"[Timer Sala {room_pin_arg} - Q{initial_question_index + 1}] Sala desapareceu após sleep. Timer encerrando.")
            return

        gs = room["game_state"]
        logger.debug(f"[Timer Sala {room_pin_arg} - Q{initial_question_index + 1}] Acordou. Estado: quiz_active={gs['quiz_active']}, current_q_idx={gs['current_question_index']}, q_idx_start={initial_question_index}")
        if gs["quiz_active"] and gs["current_question_index"] == initial_question_index:
            logger.info(f"[Timer Sala {room_pin_arg} - Q{initial_question_index + 1}] Tempo esgotado. Avançando.")
            current_q_obj = _get_current_question_for_room(room_pin_arg) 
            if current_q_obj:
                 socketio.emit('time_up', {'questionId': current_q_obj.id, 'roomPin': room_pin_arg}, room=room_pin_arg)
            _advance_question_for_room(room_pin_arg)
        else:
            logger.info(f"[Timer Sala {room_pin_arg} - Q{initial_question_index + 1}] Condição não atendida para avançar. Timer encerrando sem ação.")


def _start_question_timer_for_room(room_pin):
    # Esta função assume que rooms_lock já foi adquirido
    room = rooms_data.get(room_pin)
    if not room: return

    if room["game_state"].get("question_timer_thread") and room["game_state"]["question_timer_thread"].is_alive():
        logger.warning(f"Sala {room_pin}: Timer já existe para Q{room['game_state']['current_question_index']+1}.")
        return
    
    logger.info(f"Sala {room_pin}: Iniciando timer para Q{room['game_state']['current_question_index'] + 1}.")
    room["game_state"]["question_timer_thread"] = socketio.start_background_task(
        target=_question_timer_logic_for_room, room_pin_arg=room_pin 
    )

    #parte inteligente do sistema, mas não é tão robusta
def _calculate_recommendation_for_room(player_answers):
    if not player_answers: return "Nenhuma resposta registrada."
    correct_skill_counts = defaultdict(int)
    for q_id, answer_data in player_answers.items():
        if answer_data.get('is_correct'):
            skill = answer_data.get('skill')
            if skill: correct_skill_counts[skill] += 1
    if not correct_skill_counts: return "Nenhum acerto para sugerir área."
    best_skill_area = max(correct_skill_counts, key=correct_skill_counts.get)
    
    # Mapeamento de áreas de habilidade para sugestões de curso, essa é a parte inteligente do sistema, mas não é tão robusta
    # quanto um modelo de IA real.
    course_suggestions = {
        "BICT - Lógica de Programação": "Engenharia de Computação, Ciência da Computação",
        "BICT - Redes de Computadores": "Engenharia de Computação", 
        "BICT - Matemática Discreta": "Engenharia de Computação",
        "Eng. Computação - Arquitetura de Computadores": "Engenharia de Computação",
        "Eng. Civil - Materiais de Construção": "Engenharia Civil",
        "Eng. Mecânica - Termodinâmica": "Engenharia Mecânica, Eng. Aeroespacial",
        "Eng. Aeroespacial - Aerodinâmica": "Engenharia Aeroespacial",
        "Eng. Ambiental - Gestão de Resíduos": "Engenharia Ambiental",
        "Eng. Transportes - Engenharia de Tráfego": "Engenharia de Transportes",
        "Cálculo Básico - Geometria": "Todas as Engenharias",
        "Física Aplicada - Termologia": "Eng. Mecânica, Eng. Materiais",
        "BICT - Estatística Básica": "Todas as Engenharias", 
        "Conhecimentos Gerais": "Qualquer área!",
        # Novas áreas de habilidade para o Desafio 2
        "Eng. Computação - Fundamentos de Programação": "Engenharia de Computação, Ciência da Computação",
        "Eng. Computação - Hardware Básico": "Engenharia de Computação",
        "Eng. Computação - Desenvolvimento Web": "Engenharia de Computação, Sistemas de Informação",
        "Eng. Civil - Estruturas Básicas": "Engenharia Civil",
        "Eng. Civil - Urbanismo e Infraestrutura": "Engenharia Civil",
        "Eng. Mecânica - Fundamentos de Máquinas": "Engenharia Mecânica, Eng. de Produção",
        "Eng. Mecânica - Elementos de Máquinas": "Engenharia Mecânica",
        "Eng. Aeroespacial - Aerodinâmica Básica": "Engenharia Aeroespacial",
        "Eng. Aeroespacial - Propulsão": "Engenharia Aeroespacial",
        "Eng. Aeroespacial - Aplicações Espaciais": "Engenharia Aeroespacial",
        "Eng. Ambiental - Clima e Poluição": "Engenharia Ambiental",
        "Eng. Ambiental - Energias Renováveis": "Engenharia Ambiental, Eng. de Energia",
        "Eng. Transportes - Mobilidade Urbana": "Engenharia de Transportes, Eng. Civil",
        "Eng. Transportes - Infraestrutura": "Engenharia de Transportes, Eng. Civil",
        "Eng. Transportes - Planejamento Urbano": "Engenharia de Transportes, Eng. Civil",
        # Novas áreas de habilidade para o Desafio 1 (perguntas avançadas)
        "Eng. Computação - Estruturas de Dados": "Engenharia de Computação, Ciência da Computação",
        "Eng. Civil - Concreto Armado": "Engenharia Civil",
        "Eng. Aeroespacial - Mecânica Orbital": "Engenharia Aeroespacial",
        "Eng. Ambiental - Saneamento Básico": "Engenharia Ambiental",
    }
    
    suggestion_text = f"Você se destacou em '{best_skill_area}'. "
    suggestion_text += f"Cursos como {course_suggestions.get(best_skill_area, 'áreas relacionadas')} podem ser interessantes."
    sorted_correct_skills = sorted(correct_skill_counts.items(), key=lambda item: item[1], reverse=True)
    top_skills_info = "; ".join([f"{s[0]}: {s[1]} acerto(s)" for s in sorted_correct_skills[:3]])
    return f"{suggestion_text} Suas áreas de destaque: {top_skills_info}."


def _end_quiz_for_room(room_pin):
    # Esta função assume que rooms_lock já foi adquirido
    room = rooms_data.get(room_pin)
    if not room: return

    # Obter o total de questões para a sala específica
    total_questions_for_room = room["game_state"]["total_questions_in_challenge"]

    gs = room["game_state"]
    if not gs["quiz_active"] and gs["current_question_index"] < (total_questions_for_room - 1) : 
         logger.info(f"Sala {room_pin}: _end_quiz_for_room chamada, mas quiz já inativo ou não completou todas as perguntas. Estado: {gs}")

    gs["quiz_active"] = False 
    logger.info(f"Sala {room_pin}: Quiz finalizado. Calculando resultados...")
    results = []
    for sid, player_data in room["players"].items():
        recommendation = _calculate_recommendation_for_room(player_data.get("answers", {}))
        results.append({"nickname": player_data["nickname"], "score": player_data["score"],
                        "recommendation": recommendation, "sid": sid})
    results.sort(key=lambda p: p["score"], reverse=True)
    socketio.emit('quiz_ended', {"results": results, "roomPin": room_pin}, room=room_pin)
    logger.info(f"Sala {room_pin}: Resultados enviados.")

# --- Eventos SocketIO ---
@socketio.on('connect')
def handle_connect():
    logger.info(f"Cliente CONECTADO: SID {request.sid}, Headers: {dict(request.headers)}")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    logger.info(f"Cliente DESCONECTADO: SID {sid}")
    with rooms_lock:
        room_pin_to_leave = None
        player_nickname_left = None
        is_host_leaving = False

        for pin, room_data in list(rooms_data.items()): 
            if sid in room_data.get("players", {}): 
                room_pin_to_leave = pin
                player_nickname_left = room_data["players"][sid]["nickname"]
                is_host_leaving = (sid == room_data.get("host_sid"))
                
                logger.debug(f"handle_disconnect: Jogador '{player_nickname_left}' (SID: {sid}) encontrado na sala {pin}.")
                
                if is_host_leaving:
                    logger.info(f"Host (SID: {sid}) da sala {room_pin_to_leave} desconectou. Marcando host_sid como None.")
                    room_data["host_sid_disconnected_temp"] = sid 
                    room_data["host_sid"] = None 
                    socketio.emit('host_left', {"roomPin": room_pin_to_leave, "message": "O líder da sala parece ter desconectado. Aguardando reconexão..."}, room=room_pin_to_leave)
                else:
                    del room_data["players"][sid]
                    logger.info(f"Jogador '{player_nickname_left}' (SID: {sid}) removido da sala {pin}.")
                    remaining_players_nicknames = [p["nickname"] for p in room_data["players"].values()]
                    socketio.emit('player_left', {
                        "nickname": player_nickname_left, "sid": sid,
                        "remainingPlayers": remaining_players_nicknames,
                        "roomPin": room_pin_to_leave
                    }, room=room_pin_to_leave)

                if not room_data.get("players") and room_data.get("host_sid") is None :
                    logger.info(f"Sala {room_pin_to_leave} está vazia e sem host. Removendo sala.")
                    if room_pin_to_leave in rooms_data: del rooms_data[room_pin_to_leave]
                
                logger.info(f"handle_disconnect: Estado de rooms_data após processar SID {sid}: {list(rooms_data.keys())}")
                break 
        if not room_pin_to_leave:
            logger.debug(f"handle_disconnect: SID {sid} não encontrado em nenhuma sala ativa.")


@socketio.on('create_room')
def handle_create_room(data):
    sid = request.sid
    nickname = data.get('nickname', f'Host_{sid[:4]}').strip()[:25]
    challenge_type = data.get('challengeType', 'desafio1') # Novo: tipo de desafio
    logger.info(f"handle_create_room: Recebido de SID {sid} para nickname {nickname}, desafio {challenge_type}")
    
    room_pin = generate_room_pin()
    logger.info(f"handle_create_room: PIN gerado {room_pin}")

    with rooms_lock:
        logger.debug(f"handle_create_room: Lock adquirido para sala {room_pin}")
        rooms_data[room_pin] = {
            "host_sid": sid,
            "host_nickname_on_creation": nickname, 
            "players": {sid: {"nickname": nickname, "score": 0, "answers": {}}},
            "game_state": {
                "current_question_index": -1, "quiz_active": False, "question_start_time": None,
                "time_per_question": 20, "question_timer_thread": None,
                "total_questions_in_challenge": len(ALL_CHALLENGES.get(challenge_type, challenge_1_questions)) # Define o total de questões
            },
            "challenge_type": challenge_type # Armazena o tipo de desafio
        }
        join_room(room_pin) 
        session['current_room_pin'] = room_pin 
        session['is_host'] = True
        logger.info(f"Sala {room_pin} criada com host '{nickname}' (SID: {sid}), desafio '{challenge_type}'. Chaves de rooms_data: {list(rooms_data.keys())}")
    
    emit('room_created', {"roomPin": room_pin, "nickname": nickname, "sid": sid, "isHost": True,
                           "players": [nickname], "challengeType": challenge_type}, room=sid) # Envia o tipo de desafio de volta
    logger.info(f"handle_create_room: Evento 'room_created' emitido para sala {room_pin}.")


@socketio.on('join_room_pin')
def handle_join_room_pin(data):
    sid = request.sid
    nickname = data.get('nickname', f'Jogador_{sid[:4]}').strip()[:25]
    room_pin = data.get('roomPin', '').upper()
    logger.info(f"handle_join_room_pin: Recebido de SID {sid} para nickname {nickname}, sala {room_pin}")
    logger.debug(f"handle_join_room_pin: Salas existentes: {list(rooms_data.keys())}")

    with rooms_lock:
        logger.debug(f"handle_join_room_pin: Lock adquirido para sala {room_pin}")
        room = rooms_data.get(room_pin)
        if not room:
            logger.warning(f"Tentativa de join na sala {room_pin} por '{nickname}', mas sala não existe.")
            emit('room_join_error', {"message": f"Sala com PIN '{room_pin}' não encontrada."}, room=sid)
            return
        
        room["players"][sid] = {"nickname": nickname, "score": 0, "answers": {}} 
        
        logger.info(f"Jogador '{nickname}' (SID {sid}) entrou/atualizou na sala {room_pin}.")
        join_room(room_pin) 
        session['current_room_pin'] = room_pin
        session['is_host'] = (sid == room.get("host_sid")) 

        current_players_nicknames = [p_data["nickname"] for p_data in room["players"].values()]
        
        emit('room_joined', {
            "roomPin": room_pin, "nickname": nickname, "sid": sid, 
            "isHost": session['is_host'], "players": current_players_nicknames,
            "quizActive": room["game_state"]["quiz_active"],
            "challengeType": room.get("challenge_type", "desafio1") # Envia o tipo de desafio da sala
        }, room=sid)
        
        socketio.emit('player_joined_room', {
            "nickname": nickname, "sid": sid, "roomPin": room_pin,
            "players": current_players_nicknames
        }, room=room_pin, include_self=False) 

        if room["game_state"]["quiz_active"]:
            logger.info(f"handle_join_room_pin: Quiz já ativo na sala {room_pin}. Enviando pergunta atual para {nickname}.")
            current_q = _get_current_question_for_room(room_pin) 
            if current_q:
                q_idx = room["game_state"]["current_question_index"]
                total_questions_for_room = room["game_state"]["total_questions_in_challenge"]
                payload = {"question": current_q.to_dict(), "questionNumber": q_idx + 1,
                           "totalQuestions": total_questions_for_room, "timeLimit": room["game_state"]["time_per_question"]}
                emit('new_question', payload, room=sid)
        logger.debug(f"handle_join_room_pin: Lock liberado para sala {room_pin}")

@socketio.on('rejoin_room_check') 
def handle_rejoin_room_check(data):
    sid = request.sid 
    room_pin = data.get('roomPin', '').upper()
    nickname_from_client = data.get('nickname') 
    logger.info(f"handle_rejoin_room_check: SID {sid} tentando re-entrar na sala '{room_pin}' como '{nickname_from_client}'.")
    logger.debug(f"handle_rejoin_room_check: Salas existentes ANTES do lock: {list(rooms_data.keys())}")

    with rooms_lock:
        logger.debug(f"handle_rejoin_room_check: Salas existentes DENTRO do lock: {list(rooms_data.keys())}")
        room = rooms_data.get(room_pin)
        if not room:
            logger.warning(f"handle_rejoin_room_check: Sala '{room_pin}' NÃO encontrada para SID {sid}. Informando cliente.")
            emit('room_not_found_on_rejoin', {"roomPin": room_pin, "message": f"A sala {room_pin} não existe mais."}, room=sid)
            return

        is_confirmed_host = False
        player_data_to_use = {"nickname": nickname_from_client, "score": 0, "answers": {}} 

        if room.get("host_sid") is None and room.get("host_nickname_on_creation") == nickname_from_client:
            logger.info(f"handle_rejoin_room_check: Host '{nickname_from_client}' (novo SID: {sid}) reconectando à sala órfã '{room_pin}'.")
            room["host_sid"] = sid 
            is_confirmed_host = True
            old_host_sid_temp = room.pop("host_sid_disconnected_temp", None)
            if old_host_sid_temp and old_host_sid_temp in room["players"] and old_host_sid_temp != sid:
                logger.info(f"handle_rejoin_room_check: Removendo entrada antiga do host (SID: {old_host_sid_temp}) da lista de players.")
                del room["players"][old_host_sid_temp]
        elif room.get("host_sid") == sid: 
            is_confirmed_host = True
            logger.info(f"handle_rejoin_room_check: SID {sid} já é o host da sala '{room_pin}'.")
        
        if sid not in room["players"]:
            room["players"][sid] = player_data_to_use
            logger.info(f"handle_rejoin_room_check: Jogador '{nickname_from_client}' (SID {sid}) adicionado à sala '{room_pin}'.")
        else: 
            room["players"][sid]["nickname"] = nickname_from_client 
            logger.info(f"handle_rejoin_room_check: Jogador '{nickname_from_client}' (SID {sid}) já estava na sala, nickname atualizado.")
        
        if "host_sid_disconnected_temp" in room and room.get("host_sid") == sid : # Limpa se o host atual é o que reconectou
            del room["host_sid_disconnected_temp"]
        
        join_room(room_pin) 
        session['current_room_pin'] = room_pin
        session['is_host'] = is_confirmed_host
        
        current_players_nicknames = [p_data["nickname"] for p_data in room["players"].values()]
        logger.info(f"handle_rejoin_room_check: SID {sid} ('{nickname_from_client}') re-processado para sala '{room_pin}'. É host: {session['is_host']}")

        emit('room_joined', { 
            "roomPin": room_pin, "nickname": nickname_from_client, "sid": sid, 
            "isHost": session['is_host'], "players": current_players_nicknames,
            "quizActive": room["game_state"]["quiz_active"],
            "challengeType": room.get("challenge_type", "desafio1") # Envia o tipo de desafio da sala
        }, room=sid)
        
        socketio.emit('player_joined_room', { 
            "nickname": nickname_from_client, "sid": sid, "roomPin": room_pin,
            "players": current_players_nicknames
        }, room=room_pin, include_self=False)

        if room["game_state"]["quiz_active"]:
            logger.info(f"handle_rejoin_room_check: Quiz ativo na sala {room_pin}. Enviando pergunta atual para {nickname_from_client}.")
            current_q = _get_current_question_for_room(room_pin) 
            if current_q:
                q_idx = room["game_state"]["current_question_index"]
                total_questions_for_room = room["game_state"]["total_questions_in_challenge"]
                payload = {"question": current_q.to_dict(), "questionNumber": q_idx + 1,
                           "totalQuestions": total_questions_for_room, "timeLimit": room["game_state"]["time_per_question"]}
                emit('new_question', payload, room=sid)


@socketio.on('start_quiz_for_room')
def handle_start_quiz_for_room(data):
    sid = request.sid
    room_pin = data.get('roomPin', '').upper()
    logger.info(f"handle_start_quiz_for_room: Recebido de SID {sid} para sala '{room_pin}'")
    logger.debug(f"handle_start_quiz_for_room: Salas existentes no momento da chamada: {list(rooms_data.keys())}")
    
    with rooms_lock:
        logger.debug(f"handle_start_quiz_for_room: Lock adquirido para sala '{room_pin}'")
        room = rooms_data.get(room_pin)
        if not room:
            logger.error(f"handle_start_quiz_for_room: Sala '{room_pin}' NÃO ENCONTRADA para SID {sid}.")
            emit('room_error', {"message": f"Sala '{room_pin}' não encontrada."}, room=sid); return
        
        logger.info(f"handle_start_quiz_for_room: Sala '{room_pin}' encontrada. Host SID da sala: {room.get('host_sid')}, Requisitante SID: {sid}")
        if room.get("host_sid") != sid: 
            logger.warning(f"handle_start_quiz_for_room: SID {sid} tentou iniciar quiz para sala '{room_pin}', mas não é o host ({room.get('host_sid')}).")
            emit('room_error', {"message": "Apenas o líder pode iniciar."}, room=sid); return
        if room["game_state"]["quiz_active"]:
            logger.info(f"handle_start_quiz_for_room: Quiz na sala '{room_pin}' já está ativo.")
            emit('room_error', {"message": "Quiz já em andamento."}, room=sid); return
        if not room.get("players"): 
            logger.warning(f"handle_start_quiz_for_room: Host {sid} tentou iniciar quiz para sala '{room_pin}' sem jogadores.")
            emit('room_error', {"message": "Não há jogadores na sala para iniciar."}, room=sid); return

        logger.info(f"Host {sid} iniciando quiz para sala {room_pin}.")
        _reset_room_quiz_state(room_pin) 
        _start_quiz_logic(room_pin) 
        logger.debug(f"handle_start_quiz_for_room: Lock liberado para sala {room_pin}")


@socketio.on('submit_answer')
def handle_submit_answer(data):
    sid = request.sid
    room_pin = data.get('roomPin', '').upper()
    question_id = data.get('questionId')
    selected_option_id = data.get('selectedOptionId')
    logger.info(f"handle_submit_answer: Recebido de SID {sid} para sala {room_pin}, QID {question_id}")

    with rooms_lock:
        logger.debug(f"handle_submit_answer: Lock adquirido para sala {room_pin}")
        room = rooms_data.get(room_pin)
        if not room or sid not in room["players"]:
            emit('answer_ack', {"success": False, "error": "Sala/jogador não reconhecido."}, room=sid); return
        
        gs = room["game_state"]
        player = room["players"][sid]

        if not gs["quiz_active"]:
            emit('answer_ack', {"success": False, "error": "Quiz não está ativo."}, room=sid); return
        
        current_q = _get_current_question_for_room(room_pin)

        if not current_q or current_q.id != question_id:
            emit('answer_ack', {"success": False, "error": "Resposta para pergunta errada."}, room=sid); return
        if player.get("answered_current_question"):
            emit('answer_ack', {"success": False, "error": "Você já respondeu."}, room=sid); return

        is_correct = (selected_option_id == current_q.correct_option_id)
        points_earned = 0
        if is_correct:
            base_points = 100; time_taken = time.time() - gs.get("question_start_time", time.time()) 
            time_limit = gs["time_per_question"]
            bonus_percentage = max(0, (time_limit - time_taken) / time_limit if time_limit > 0 else 0)
            max_bonus_points = 50; bonus_points = int(max_bonus_points * bonus_percentage)
            points_earned = base_points + bonus_points
            player["score"] += points_earned
        
        player["answers"][current_q.id] = {
            "answer_id": selected_option_id, "is_correct": is_correct,
            "skill": current_q.skill_area, "points_earned": points_earned
        }
        player["answered_current_question"] = True
        logger.info(f"Sala {room_pin}: '{player['nickname']}' Q'{current_q.id}': {'Ok' if is_correct else 'X'}. Pts:{points_earned}. Total:{player['score']}")
        
        emit('answer_feedback', {
            "questionId": current_q.id, "selectedOptionId": selected_option_id,
            "correctOptionId": current_q.correct_option_id, "isCorrect": is_correct,
            "pointsEarned": points_earned, "currentScore": player["score"], "roomPin": room_pin
        }, room=sid)
        
        scores_overview = sorted(
            [{"nickname": p_data["nickname"], "score": p_data["score"]} for p_data in room["players"].values()],
            key=lambda x: x["score"], reverse=True
        )
        socketio.emit('scores_update', {"scores": scores_overview[:10], "roomPin": room_pin}, room=room_pin)

        all_answered = all(p_data.get("answered_current_question") for p_data in room["players"].values() if p_data)
        if all_answered and len(room["players"]) > 0 :
            logger.info(f"Sala {room_pin}: Todos os {len(room['players'])} jogadores responderam. Avançando...")
            _advance_question_for_room(room_pin)
        logger.debug(f"handle_submit_answer: Lock liberado para sala {room_pin}")

# --- Inicialização ---
if __name__ == '__main__':
    logger.info(f"--- Iniciando servidor Flask-SocketIO (PID: {os.getpid()}) ---")
    logger.info(f"--- Usando async_mode: {socketio.async_mode} ---")
    socketio.run(app, debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5001))
