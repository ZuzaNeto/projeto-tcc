# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template, session, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS # Importado, mas a configuração principal é no SocketIO
import time
import threading
from collections import defaultdict
import logging
import random
import string

# Configuração de logging
logging.basicConfig(level=logging.DEBUG) # DEBUG para mais detalhes
logger = logging.getLogger(__name__)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO) # Logs do servidor Flask (GET, POST, etc.)

# Tenta importar eventlet para verificar se está disponível
try:
    import eventlet
    eventlet.monkey_patch() # Necessário para que outras bibliotecas cooperem com eventlet
    ASYNC_MODE = 'eventlet'
    logger.info("Eventlet encontrado e monkey_patch() aplicado.")
except ImportError:
    logger.warning("Eventlet não encontrado. Usando async_mode='threading'. Isso pode ser menos estável para WebSockets.")
    ASYNC_MODE = 'threading'


# --- Configuração da Aplicação Flask ---
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'bict_quiz_ufma_salas_super_secretas_eventlet!'

# Configuração do SocketIO
socketio = SocketIO(app,
                    async_mode=ASYNC_MODE,
                    cors_allowed_origins="*",
                    logger=True,              # Ativa logs do python-socketio
                    engineio_logger=True)     # Ativa logs do python-engineio

logger.info(f"SocketIO inicializado com async_mode: {socketio.async_mode}")
if socketio.async_mode != 'eventlet' and ASYNC_MODE == 'eventlet':
    logger.error("Falha ao forçar async_mode='eventlet', mesmo com eventlet importado. Verifique a instalação.")


# --- Definição das Questões (mesma estrutura de antes) ---
class QuizOption:
    def __init__(self, id: str, text: str): self.id = id; self.text = text
    def to_dict(self): return {"id": self.id, "text": self.text}

class QuizQuestion:
    def __init__(self, id: str, text: str, options: list[QuizOption], correct_option_id: str, skill_area: str, difficulty: str):
        self.id, self.text, self.options, self.correct_option_id, self.skill_area, self.difficulty = id, text, options, correct_option_id, skill_area, difficulty
    def to_dict(self):
        return {"id": self.id, "text": self.text, "options": [opt.to_dict() for opt in self.options],
                "correctOptionId": self.correct_option_id, "skillArea": self.skill_area, "difficulty": self.difficulty}

new_quiz_questions_data = [
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
  {"id": "nq12","text": "Se você tem um conjunto de dados de medições e precisa encontrar o valor que ocorre com maior frequência, qual medida estatística você usaria?","options": [{"id": "nq12_opt1", "text": "Média Aritmética"},{"id": "nq12_opt2", "text": "Mediana"},{"id": "nq12_opt3", "text": "Moda"},{"id": "nq12_opt4", "text": "Desvio Padrão"}],"correctOptionId": "nq12_opt3","skillArea": "BICT - Estatística Básica","difficulty": "Fácil"}
]
new_quiz_questions = [QuizQuestion(q["id"], q["text"], [QuizOption(opt["id"], opt["text"]) for opt in q["options"]], q["correctOptionId"], q["skillArea"], q["difficulty"]) for q in new_quiz_questions_data]
TOTAL_QUESTIONS = len(new_quiz_questions)

# --- Gerenciamento de Salas ---
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

# --- Rotas HTTP ---
@app.route('/')
def index_page(): return render_template('index.html')

@app.route('/lobby') 
def lobby_page(): return render_template('lobby.html')

@app.route('/quiz')
def quiz_page(): return render_template('quiz.html')

@app.route('/results')
def results_page(): return render_template('results.html')

# --- Funções Auxiliares do Quiz (Adaptadas para Salas) ---
# ... (COLE AQUI AS FUNÇÕES: _reset_room_quiz_state, _get_current_question_for_room, 
#      _advance_question_for_room, _question_timer_logic_for_room, 
#      _start_question_timer_for_room, _calculate_recommendation_for_room, 
#      _end_quiz_for_room, _start_quiz_logic DA VERSÃO ANTERIOR - flask_backend_v6_rooms)
# --- Funções Auxiliares do Quiz (Adaptadas para Salas) ---
def _start_quiz_logic(room_pin): 
    room = rooms_data.get(room_pin)
    if not room:
        logger.error(f"_start_quiz_logic chamada para sala inexistente: {room_pin}")
        return

    logger.info(f"Sala {room_pin}: Dentro de _start_quiz_logic: Iniciando lógica do quiz.")
    room["game_state"]["current_question_index"] = -1
    room["game_state"]["quiz_active"] = True
    room["game_state"]["question_start_time"] = None
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
    _advance_question_for_room(room_pin)


def _reset_room_quiz_state(room_pin):
    room = rooms_data.get(room_pin)
    if not room: return

    room["game_state"] = {
        "current_question_index": -1, "quiz_active": False, "question_start_time": None,
        "time_per_question": 20, "question_timer_thread": None,
    }
    for player_sid in room["players"]:
        room["players"][player_sid]["score"] = 0
        room["players"][player_sid]["answers"] = {}
        if "answered_current_question" in room["players"][player_sid]:
            del room["players"][player_sid]["answered_current_question"]
    logger.info(f"Estado do quiz resetado para a sala {room_pin}.")


def _get_current_question_for_room(room_pin):
    room = rooms_data.get(room_pin)
    if not room or not room["game_state"]["quiz_active"]: return None
    idx = room["game_state"]["current_question_index"]
    if 0 <= idx < TOTAL_QUESTIONS:
        return new_quiz_questions[idx]
    return None

def _advance_question_for_room(room_pin):
    room = rooms_data.get(room_pin)
    if not room or not room["game_state"]["quiz_active"]:
        logger.debug(f"Advance Q para sala {room_pin}: Quiz não ativo.")
        return

    room["game_state"]["current_question_index"] += 1
    idx = room["game_state"]["current_question_index"]

    if idx < TOTAL_QUESTIONS:
        current_q = new_quiz_questions[idx]
        logger.info(f"Sala {room_pin}: Avançando para P{idx + 1} - {current_q.text[:30]}...")
        room["game_state"]["question_start_time"] = time.time()
        for player_sid in room["players"]: 
            if "answered_current_question" in room["players"][player_sid]:
                del room["players"][player_sid]["answered_current_question"]
        
        payload = {"question": current_q.to_dict(), "questionNumber": idx + 1,
                   "totalQuestions": TOTAL_QUESTIONS, "timeLimit": room["game_state"]["time_per_question"]}
        socketio.emit('new_question', payload, room=room_pin)
        _start_question_timer_for_room(room_pin)
    else:
        logger.info(f"Sala {room_pin}: Fim das perguntas. Finalizando quiz.")
        _end_quiz_for_room(room_pin)


def _question_timer_logic_for_room(room_pin_arg): # Renomeado para evitar conflito com a variável room_pin local
    # Este timer roda em uma thread separada, precisa obter o lock ao acessar rooms_data
    logger.debug(f"[Timer Sala {room_pin_arg}] Thread iniciada.")
    with rooms_lock:
        room = rooms_data.get(room_pin_arg) 
        if not room: 
            logger.warning(f"[Timer Sala {room_pin_arg}] Sala não existe mais no início da thread. Timer encerrando.")
            return
        question_index_at_start = room["game_state"]["current_question_index"]
        time_to_wait = room["game_state"]["time_per_question"]
    
    logger.info(f"[Timer Sala {room_pin_arg} - Q{question_index_at_start + 1}] Esperando {time_to_wait}s.")
    socketio.sleep(time_to_wait + 0.5) # Dá uma pequena margem

    with rooms_lock: 
        room = rooms_data.get(room_pin_arg) # Re-obtém a sala dentro do lock
        if not room:
            logger.warning(f"[Timer Sala {room_pin_arg} - Q{question_index_at_start + 1}] Sala desapareceu após sleep. Timer encerrando.")
            return

        gs = room["game_state"]
        logger.debug(f"[Timer Sala {room_pin_arg} - Q{question_index_at_start + 1}] Acordou. Estado: quiz_active={gs['quiz_active']}, current_q_idx={gs['current_question_index']}, q_idx_start={question_index_at_start}")
        if gs["quiz_active"] and gs["current_question_index"] == question_index_at_start:
            logger.info(f"[Timer Sala {room_pin_arg} - Q{question_index_at_start + 1}] Tempo esgotado. Avançando.")
            current_q_obj = _get_current_question_for_room(room_pin_arg) # Já está no lock
            if current_q_obj:
                 socketio.emit('time_up', {'questionId': current_q_obj.id, 'roomPin': room_pin_arg}, room=room_pin_arg)
            _advance_question_for_room(room_pin_arg)
        else:
            logger.info(f"[Timer Sala {room_pin_arg} - Q{question_index_at_start + 1}] Condição não atendida para avançar. Timer encerrando sem ação.")


def _start_question_timer_for_room(room_pin):
    # Chamada de dentro de um contexto com rooms_lock
    room = rooms_data.get(room_pin)
    if not room: return

    # Cancela timer anterior se existir e estiver vivo (melhor prática)
    if room["game_state"].get("question_timer_thread") and room["game_state"]["question_timer_thread"].is_alive():
        logger.debug(f"Sala {room_pin}: Timer anterior para Q{room['game_state']['current_question_index']} ainda ativo. Tentando cancelar (não implementado diretamente, mas a lógica do timer deve impedir sobreposição).")
        # Em eventlet, não há um método join() ou cancel() direto para greenlets de start_background_task
        # A lógica dentro de _question_timer_logic_for_room deve garantir que timers antigos não interfiram.
        # Apenas resetamos a referência para permitir um novo.
        room["game_state"]["question_timer_thread"] = None 
    
    logger.info(f"Sala {room_pin}: Iniciando timer para Q{room['game_state']['current_question_index'] + 1}.")
    room["game_state"]["question_timer_thread"] = socketio.start_background_task(
        target=_question_timer_logic_for_room, room_pin_arg=room_pin 
    )

def _calculate_recommendation_for_room(player_answers):
    if not player_answers: return "Nenhuma resposta registrada."
    correct_skill_counts = defaultdict(int)
    for q_id, answer_data in player_answers.items():
        if answer_data.get('is_correct'):
            skill = answer_data.get('skill')
            if skill: correct_skill_counts[skill] += 1
    if not correct_skill_counts: return "Nenhum acerto para sugerir área."
    best_skill_area = max(correct_skill_counts, key=correct_skill_counts.get)
    course_suggestions = {
        "BICT - Lógica de Programação": "Engenharia de Computação, Ciência da Computação",
        "BICT - Redes de Computadores": "Engenharia de Computação", "BICT - Matemática Discreta": "Engenharia de Computação",
        "Eng. Computação - Arquitetura de Computadores": "Engenharia de Computação",
        "Eng. Civil - Materiais de Construção": "Engenharia Civil",
        "Eng. Mecânica - Termodinâmica": "Engenharia Mecânica, Eng. Aeroespacial",
        "Eng. Aeroespacial - Aerodinâmica": "Engenharia Aeroespacial",
        "Eng. Ambiental - Gestão de Resíduos": "Engenharia Ambiental",
        "Eng. Transportes - Engenharia de Tráfego": "Engenharia de Transportes",
        "Cálculo Básico - Geometria": "Todas as Engenharias",
        "Física Aplicada - Termologia": "Eng. Mecânica, Eng. Materiais",
        "BICT - Estatística Básica": "Todas as Engenharias", "Conhecimentos Gerais": "Qualquer área!"
    }
    suggestion_text = f"Você se destacou em '{best_skill_area}'. "
    suggestion_text += f"Cursos como {course_suggestions.get(best_skill_area, 'áreas relacionadas')} podem ser interessantes."
    sorted_correct_skills = sorted(correct_skill_counts.items(), key=lambda item: item[1], reverse=True)
    top_skills_info = "; ".join([f"{s[0]}: {s[1]} acerto(s)" for s in sorted_correct_skills[:3]])
    return f"{suggestion_text} Suas áreas de destaque: {top_skills_info}."


def _end_quiz_for_room(room_pin):
    # Não precisa de lock aqui se for chamada de um contexto que já tem o lock (como _advance_question_for_room)
    # Mas se puder ser chamada de fora, precisaria do with rooms_lock:
    room = rooms_data.get(room_pin)
    if not room: return

    gs = room["game_state"]
    if not gs["quiz_active"] and gs["current_question_index"] < TOTAL_QUESTIONS -1 :
         logger.info(f"Sala {room_pin}: _end_quiz_for_room chamada, mas quiz já inativo ou não completou. Estado: {gs}")
         # return # Não retorna para permitir que o host veja resultados parciais se o quiz for interrompido

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
        for pin, room_data in list(rooms_data.items()): 
            if sid in room_data["players"]:
                room_pin_to_leave = pin
                player_nickname_left = room_data["players"][sid]["nickname"]
                del room_data["players"][sid]
                logger.info(f"Jogador '{player_nickname_left}' (SID: {sid}) removido da sala {pin}.")
                
                remaining_players_nicknames = [p["nickname"] for p in room_data["players"].values()]
                socketio.emit('player_left', {
                    "nickname": player_nickname_left, "sid": sid,
                    "remainingPlayers": remaining_players_nicknames,
                    "roomPin": room_pin_to_leave
                }, room=room_pin_to_leave)

                if sid == room_data["host_sid"]:
                    logger.info(f"Host (SID: {sid}) da sala {room_pin_to_leave} desconectou.")
                    if not room_data["players"]:
                        logger.info(f"Sala {room_pin_to_leave} está vazia após saída do host. Removendo sala.")
                        del rooms_data[room_pin_to_leave]
                    else:
                        socketio.emit('host_left', {"roomPin": room_pin_to_leave, "message": "O líder da sala saiu."}, room=room_pin_to_leave)
                        room_data["host_sid"] = None 
                elif not room_data["players"]:
                    logger.info(f"Sala {room_pin_to_leave} ficou vazia. Removendo sala.")
                    del rooms_data[room_pin_to_leave]
                break 

@socketio.on('create_room')
def handle_create_room(data):
    sid = request.sid
    nickname = data.get('nickname', f'Host_{sid[:4]}').strip()[:25]
    logger.info(f"handle_create_room: Recebido de SID {sid} para nickname {nickname}")
    
    room_pin = generate_room_pin() # Geração de PIN fora do lock principal
    logger.info(f"handle_create_room: PIN gerado {room_pin}")

    with rooms_lock:
        logger.debug(f"handle_create_room: Lock adquirido para sala {room_pin}")
        rooms_data[room_pin] = {
            "host_sid": sid,
            "players": {sid: {"nickname": nickname, "score": 0, "answers": {}}},
            "game_state": {
                "current_question_index": -1, "quiz_active": False, "question_start_time": None,
                "time_per_question": 20, "question_timer_thread": None,
            }
        }
        join_room(room_pin) 
        session['current_room_pin'] = room_pin 
        session['is_host'] = True
        logger.info(f"Sala {room_pin} criada e host '{nickname}' (SID: {sid}) adicionado.")
    
    logger.info(f"handle_create_room: Emitindo 'room_created' para SID {sid} para sala {room_pin}")
    emit('room_created', {"roomPin": room_pin, "nickname": nickname, "sid": sid, "isHost": True,
                           "players": [nickname]}, room=sid)
    logger.info(f"handle_create_room: Evento 'room_created' emitido para sala {room_pin}.")


@socketio.on('join_room_pin')
def handle_join_room_pin(data):
    sid = request.sid
    nickname = data.get('nickname', f'Jogador_{sid[:4]}').strip()[:25]
    room_pin = data.get('roomPin', '').upper()
    logger.info(f"handle_join_room_pin: Recebido de SID {sid} para nickname {nickname}, sala {room_pin}")

    with rooms_lock:
        logger.debug(f"handle_join_room_pin: Lock adquirido para sala {room_pin}")
        room = rooms_data.get(room_pin)
        if not room:
            logger.warning(f"Tentativa de join na sala {room_pin} por '{nickname}', mas sala não existe.")
            emit('room_join_error', {"message": f"Sala com PIN '{room_pin}' não encontrada."}, room=sid)
            return
        
        if sid not in room["players"]:
            room["players"][sid] = {"nickname": nickname, "score": 0, "answers": {}}
        else: 
            room["players"][sid]["nickname"] = nickname
        
        logger.info(f"Jogador '{nickname}' (SID {sid}) entrou/atualizou na sala {room_pin}.")
        join_room(room_pin) 
        session['current_room_pin'] = room_pin
        session['is_host'] = (sid == room["host_sid"])

        current_players_nicknames = [p_data["nickname"] for p_data in room["players"].values()]
        
        logger.info(f"handle_join_room_pin: Emitindo 'room_joined' para SID {sid} para sala {room_pin}")
        emit('room_joined', {
            "roomPin": room_pin, "nickname": nickname, "sid": sid, 
            "isHost": session['is_host'], "players": current_players_nicknames,
            "quizActive": room["game_state"]["quiz_active"] 
        }, room=sid)
        
        logger.info(f"handle_join_room_pin: Emitindo 'player_joined_room' para sala {room_pin}")
        socketio.emit('player_joined_room', {
            "nickname": nickname, "sid": sid, "roomPin": room_pin,
            "players": current_players_nicknames
        }, room=room_pin, include_self=False)

        if room["game_state"]["quiz_active"]:
            logger.info(f"handle_join_room_pin: Quiz já ativo na sala {room_pin}. Enviando pergunta atual para {nickname}.")
            current_q = _get_current_question_for_room(room_pin) 
            if current_q:
                q_idx = room["game_state"]["current_question_index"]
                payload = {"question": current_q.to_dict(), "questionNumber": q_idx + 1,
                           "totalQuestions": TOTAL_QUESTIONS, "timeLimit": room["game_state"]["time_per_question"]}
                emit('new_question', payload, room=sid)
        logger.debug(f"handle_join_room_pin: Lock liberado para sala {room_pin}")


@socketio.on('start_quiz_for_room')
def handle_start_quiz_for_room(data):
    sid = request.sid
    room_pin = data.get('roomPin', '').upper()
    logger.info(f"handle_start_quiz_for_room: Recebido de SID {sid} para sala {room_pin}")
    
    with rooms_lock:
        logger.debug(f"handle_start_quiz_for_room: Lock adquirido para sala {room_pin}")
        room = rooms_data.get(room_pin)
        if not room:
            emit('room_error', {"message": "Sala não encontrada."}, room=sid); return
        if room["host_sid"] != sid:
            emit('room_error', {"message": "Apenas o líder pode iniciar."}, room=sid); return
        if room["game_state"]["quiz_active"]:
            emit('room_error', {"message": "Quiz já em andamento."}, room=sid); return
        if not room["players"]: # Verifica se há jogadores
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
    # Se estiver usando eventlet, socketio.run() já usa o servidor eventlet.
    # O debug=True do Flask pode causar problemas com eventlet em alguns casos (reinicializações duplas).
    # Para produção, debug=False e use um servidor WSGI como `gunicorn --worker-class eventlet -w 1 app:app`
    socketio.run(app, debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5001))

