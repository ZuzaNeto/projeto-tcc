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

# Configuração de logging
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
app.config['SECRET_KEY'] = 'bict_quiz_ufma_salas_super_secretas_eventlet_v10!' # Nova chave
socketio = SocketIO(app,
                    async_mode=ASYNC_MODE,
                    cors_allowed_origins="*",
                    logger=True,              
                    engineio_logger=True)     

logger.info(f"SocketIO inicializado com async_mode: {socketio.async_mode}")
if socketio.async_mode != 'eventlet' and ASYNC_MODE == 'eventlet':
    logger.error("Falha ao forçar async_mode='eventlet'.")

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

# --- Funções Auxiliares do Quiz (COPIE E COLE TODAS AS FUNÇÕES _ AUXILIARES DA VERSÃO flask_backend_v9_rejoin_debug AQUI) ---
# ... Elas já devem estar corretas e com logs.

# --- Eventos SocketIO ---
@socketio.on('connect')
def handle_connect():
    logger.info(f"Cliente CONECTADO: SID {request.sid}, Headers: {dict(request.headers)}")
    # O cliente agora DEVE enviar 'rejoin_room_check' se tiver dados de sala no sessionStorage

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    logger.info(f"Cliente DESCONECTADO: SID {sid}")
    with rooms_lock:
        room_pin_to_leave = None
        player_nickname_left = None
        is_host_leaving = False

        for pin, room_data in list(rooms_data.items()): 
            if sid in room_data["players"]:
                room_pin_to_leave = pin
                player_nickname_left = room_data["players"][sid]["nickname"]
                is_host_leaving = (sid == room_data.get("host_sid"))
                
                logger.debug(f"handle_disconnect: Jogador '{player_nickname_left}' (SID: {sid}) encontrado na sala {pin}.")
                del room_data["players"][sid]
                logger.info(f"Jogador '{player_nickname_left}' (SID: {sid}) removido da sala {pin}.")
                
                remaining_players_nicknames = [p["nickname"] for p in room_data["players"].values()]
                socketio.emit('player_left', {
                    "nickname": player_nickname_left, "sid": sid,
                    "remainingPlayers": remaining_players_nicknames,
                    "roomPin": room_pin_to_leave
                }, room=room_pin_to_leave) # Emite para a sala específica

                if is_host_leaving:
                    logger.info(f"Host (SID: {sid}) da sala {room_pin_to_leave} desconectou.")
                    if not room_data["players"]: 
                        logger.info(f"Sala {room_pin_to_leave} está vazia após saída do host. Removendo sala.")
                        if room_pin_to_leave in rooms_data: del rooms_data[room_pin_to_leave]
                    else: 
                        socketio.emit('host_left', {"roomPin": room_pin_to_leave, "message": "O líder da sala saiu."}, room=room_pin_to_leave)
                        room_data["host_sid"] = None 
                elif not room_data["players"]: 
                    logger.info(f"Sala {room_pin_to_leave} ficou vazia. Removendo sala.")
                    if room_pin_to_leave in rooms_data: del rooms_data[room_pin_to_leave]
                
                logger.info(f"handle_disconnect: Estado de rooms_data após processar SID {sid}: {list(rooms_data.keys())}")
                break 
        if not room_pin_to_leave:
            logger.debug(f"handle_disconnect: SID {sid} não encontrado em nenhuma sala.")


@socketio.on('create_room')
def handle_create_room(data):
    # ... (mesma lógica de antes, com logs)
    sid = request.sid
    nickname = data.get('nickname', f'Host_{sid[:4]}').strip()[:25]
    logger.info(f"handle_create_room: Recebido de SID {sid} para nickname {nickname}")
    
    room_pin = generate_room_pin()
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
        join_room(room_pin) # Adiciona o SID do criador à sala SocketIO
        session['current_room_pin'] = room_pin 
        session['is_host'] = True
        logger.info(f"Sala {room_pin} criada e host '{nickname}' (SID: {sid}) adicionado. rooms_data agora: {list(rooms_data.keys())}")
    
    logger.info(f"handle_create_room: Emitindo 'room_created' para SID {sid} para sala {room_pin}")
    emit('room_created', {"roomPin": room_pin, "nickname": nickname, "sid": sid, "isHost": True,
                           "players": [nickname]}, room=sid) # Envia só para o criador
    logger.info(f"handle_create_room: Evento 'room_created' emitido para sala {room_pin}.")


@socketio.on('join_room_pin')
def handle_join_room_pin(data):
    # ... (mesma lógica de antes, com logs)
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
        
        # Adiciona ou atualiza jogador
        room["players"][sid] = {"nickname": nickname, "score": 0, "answers": {}} # Sempre reseta score/answers ao entrar/re-entrar
        
        logger.info(f"Jogador '{nickname}' (SID {sid}) entrou/atualizou na sala {room_pin}.")
        join_room(room_pin) 
        session['current_room_pin'] = room_pin
        session['is_host'] = (sid == room.get("host_sid")) 

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
        }, room=room_pin, include_self=False) # Notifica outros jogadores

        if room["game_state"]["quiz_active"]:
            logger.info(f"handle_join_room_pin: Quiz já ativo na sala {room_pin}. Enviando pergunta atual para {nickname}.")
            current_q = _get_current_question_for_room(room_pin) # _get_current_question_for_room já tem lock implícito
            if current_q:
                q_idx = room["game_state"]["current_question_index"]
                payload = {"question": current_q.to_dict(), "questionNumber": q_idx + 1,
                           "totalQuestions": TOTAL_QUESTIONS, "timeLimit": room["game_state"]["time_per_question"]}
                emit('new_question', payload, room=sid)
        logger.debug(f"handle_join_room_pin: Lock liberado para sala {room_pin}")

@socketio.on('rejoin_room_check') 
def handle_rejoin_room_check(data):
    sid = request.sid
    room_pin = data.get('roomPin', '').upper()
    nickname = data.get('nickname') # Nickname que o cliente tinha
    logger.info(f"handle_rejoin_room_check: SID {sid} tentando re-entrar na sala '{room_pin}' como '{nickname}'.")
    logger.debug(f"handle_rejoin_room_check: Salas existentes ANTES do lock: {list(rooms_data.keys())}")

    with rooms_lock:
        logger.debug(f"handle_rejoin_room_check: Salas existentes DENTRO do lock: {list(rooms_data.keys())}")
        room = rooms_data.get(room_pin)
        if not room:
            logger.warning(f"handle_rejoin_room_check: Sala '{room_pin}' NÃO encontrada para SID {sid}. Informando cliente.")
            emit('room_not_found_on_rejoin', {"roomPin": room_pin, "message": f"A sala {room_pin} não existe mais ou foi encerrada."}, room=sid)
            return

        # Sala existe. Adicionar/atualizar jogador.
        # Remove qualquer entrada antiga com o mesmo nickname mas SID diferente (se houver)
        # Isso é para evitar duplicidade se o SID mudou mas o nickname é o mesmo.
        # No entanto, um jogador pode ter o mesmo nick que outro, então o SID é o identificador primário.
        # Se o SID já existe, apenas atualizamos o nickname.
        # Se o SID é novo, adicionamos como novo jogador.

        is_host_rejoining = (sid == room.get("host_sid")) # Verifica se o SID atual é o host conhecido
        
        # Se o jogador já está na lista com este SID, apenas atualiza o nickname
        if sid in room["players"]:
            room["players"][sid]["nickname"] = nickname
            logger.info(f"handle_rejoin_room_check: SID {sid} ('{nickname}') já estava na sala, nickname atualizado na sala '{room_pin}'.")
        else:
            # Se o SID é novo, adiciona o jogador.
            # Se o host_sid da sala é None (host anterior desconectou) e este é o primeiro a re-entrar,
            # ele pode se tornar o novo host. (Lógica simplificada por agora)
            room["players"][sid] = {"nickname": nickname, "score": 0, "answers": {}} 
            logger.info(f"handle_rejoin_room_check: Novo SID {sid} ('{nickname}') adicionado à sala '{room_pin}'.")
            if room.get("host_sid") is None and len(room["players"]) == 1: # Se tornou o único jogador e não havia host
                room["host_sid"] = sid
                is_host_rejoining = True
                logger.info(f"handle_rejoin_room_check: SID {sid} ('{nickname}') se tornou o novo host da sala órfã '{room_pin}'.")
        
        join_room(room_pin) # Garante que o SID atual está na sala SocketIO
        session['current_room_pin'] = room_pin
        session['is_host'] = (sid == room.get("host_sid")) # Confirma se é o host atual
        
        current_players_nicknames = [p_data["nickname"] for p_data in room["players"].values()]
        logger.info(f"handle_rejoin_room_check: SID {sid} ('{nickname}') re-processado para sala '{room_pin}'. É host: {session['is_host']}")

        emit('room_joined', { 
            "roomPin": room_pin, "nickname": nickname, "sid": sid, 
            "isHost": session['is_host'], "players": current_players_nicknames,
            "quizActive": room["game_state"]["quiz_active"] 
        }, room=sid)
        
        # Notifica outros jogadores APENAS se este SID era realmente novo na lista de SIDs da sala
        # (Evita spam se for apenas uma atualização de nickname para um SID existente)
        # Esta lógica pode ser refinada. Por agora, vamos sempre notificar.
        socketio.emit('player_joined_room', { 
            "nickname": nickname, "sid": sid, "roomPin": room_pin,
            "players": current_players_nicknames
        }, room=room_pin, include_self=False)

        if room["game_state"]["quiz_active"]:
            logger.info(f"handle_rejoin_room_check: Quiz ativo na sala {room_pin}. Enviando pergunta atual para {nickname}.")
            current_q = _get_current_question_for_room(room_pin) 
            if current_q:
                q_idx = room["game_state"]["current_question_index"]
                payload = {"question": current_q.to_dict(), "questionNumber": q_idx + 1,
                           "totalQuestions": TOTAL_QUESTIONS, "timeLimit": room["game_state"]["time_per_question"]}
                emit('new_question', payload, room=sid)


@socketio.on('start_quiz_for_room')
def handle_start_quiz_for_room(data):
    # ... (mesma lógica de antes, com logs)
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
        
        logger.info(f"handle_start_quiz_for_room: Sala '{room_pin}' encontrada. Host SID: {room.get('host_sid')}, Requisitante SID: {sid}")
        if room.get("host_sid") != sid: 
            logger.warning(f"handle_start_quiz_for_room: SID {sid} tentou iniciar quiz para sala '{room_pin}', mas não é o host ({room.get('host_sid')}).")
            emit('room_error', {"message": "Apenas o líder pode iniciar."}, room=sid); return
        if room["game_state"]["quiz_active"]:
            logger.info(f"handle_start_quiz_for_room: Quiz na sala '{room_pin}' já está ativo.")
            emit('room_error', {"message": "Quiz já em andamento."}, room=sid); return
        if not room.get("players"): # Verifica se a chave 'players' existe e não está vazia
            logger.warning(f"handle_start_quiz_for_room: Host {sid} tentou iniciar quiz para sala '{room_pin}' sem jogadores.")
            emit('room_error', {"message": "Não há jogadores na sala para iniciar."}, room=sid); return

        logger.info(f"Host {sid} iniciando quiz para sala {room_pin}.")
        _reset_room_quiz_state(room_pin) 
        _start_quiz_logic(room_pin) 
        logger.debug(f"handle_start_quiz_for_room: Lock liberado para sala {room_pin}")


@socketio.on('submit_answer')
def handle_submit_answer(data):
    # ... (mesma lógica de antes, com logs)
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

