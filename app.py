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
app.config['SECRET_KEY'] = 'bict_quiz_ufma_salas_super_secretas_eventlet_v12!'
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

new_quiz_questions_data = [
  {"id": "nq1","text": "Se um algoritmo é uma sequência finita de instruções para resolver um problema, qual das seguintes opções MELHOR descreve uma característica essencial de um bom algoritmo?","options": [{"id": "nq1_opt1", "text": "Ser escrito na linguagem de programação mais recente."}, {"id": "nq1_opt2", "text": "Ser o mais curto possível, mesmo que difícil de entender."}, {"id": "nq1_opt3", "text": "Ser eficiente em termos de tempo e recursos, e ser claro."}, {"id": "nq1_opt4", "text": "Funcionar apenas para um conjunto específico de dados de entrada."}],"correctOptionId": "nq1_opt3","skillArea": "BICT - Lógica de Programação","difficulty": "Fácil"},
  {"id": "nq2","text": "No contexto de redes de computadores, o que significa a sigla 'IP' em 'Endereço IP'?","options": [{"id": "nq2_opt1", "text": "Internal Protocol"}, {"id": "nq2_opt2", "text": "Internet Protocol"}, {"id": "nq2_opt3", "text": "Instruction Pointer"}, {"id": "nq2_opt4", "text": "Immediate Power"}],"correctOptionId": "nq2_opt2","skillArea": "BICT - Redes de Computadores","difficulty": "Fácil"},
  # Cole o restante das questões aqui para garantir que não está vazio
  {"id": "nq3","text": "Qual o resultado da expressão lógica: (VERDADEIRO OU FALSO) E (NÃO FALSO)?","options": [{"id": "nq3_opt1", "text": "VERDADEIRO"}, {"id": "nq3_opt2", "text": "FALSO"}, {"id": "nq3_opt3", "text": "Depende"}, {"id": "nq3_opt4", "text": "Inválido"}],"correctOptionId": "nq3_opt1","skillArea": "BICT - Matemática Discreta","difficulty": "Fácil"},
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

# --- Funções Auxiliares do Quiz ---
# ... (COPIE E COLE TODAS AS FUNÇÕES _ AUXILIARES DA VERSÃO flask_backend_v11_host_rejoin AQUI) ...
# Certifique-se que _start_quiz_logic, _reset_room_quiz_state, etc., estão corretas.

# --- Eventos SocketIO ---
@socketio.on('connect')
def handle_connect():
    logger.info(f"Cliente CONECTADO: SID {request.sid}, Headers: {dict(request.headers)}")
    # O cliente agora DEVE enviar 'rejoin_room_check' se tiver dados de sala no sessionStorage
    # ao carregar as páginas /lobby ou /quiz.

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
                # Não remove o jogador da lista de players imediatamente se for o host e a sala estiver ativa
                # Apenas marca o host_sid como None se ele desconectar.
                # Se não for o host, remove o jogador.
                
                if is_host_leaving:
                    logger.info(f"Host (SID: {sid}) da sala {room_pin_to_leave} desconectou. Marcando host_sid como None, mas mantendo jogador na lista por enquanto.")
                    room_data["host_sid_disconnected_temp"] = sid # Guarda o SID do host que desconectou
                    room_data["host_sid"] = None # Permite que o host reconecte e reassuma
                    # Não remove o host da lista de players aqui, para que ele possa ser encontrado pelo nickname no rejoin
                    socketio.emit('host_left', {"roomPin": room_pin_to_leave, "message": "O líder da sala parece ter desconectado. Aguardando reconexão..."}, room=room_pin_to_leave)
                else:
                    # Se não for o host, remove o jogador normalmente
                    del room_data["players"][sid]
                    logger.info(f"Jogador '{player_nickname_left}' (SID: {sid}) removido da sala {pin}.")
                    remaining_players_nicknames = [p["nickname"] for p in room_data["players"].values()]
                    socketio.emit('player_left', {
                        "nickname": player_nickname_left, "sid": sid,
                        "remainingPlayers": remaining_players_nicknames,
                        "roomPin": room_pin_to_leave
                    }, room=room_pin_to_leave)

                # Se a sala ficar completamente vazia (sem nenhum jogador na lista 'players')
                if not room_data["players"]:
                    logger.info(f"Sala {room_pin_to_leave} está vazia. Removendo sala.")
                    if room_pin_to_leave in rooms_data: del rooms_data[room_pin_to_leave]
                
                logger.info(f"handle_disconnect: Estado de rooms_data após processar SID {sid}: {list(rooms_data.keys())}")
                break 
        if not room_pin_to_leave:
            logger.debug(f"handle_disconnect: SID {sid} não encontrado em nenhuma sala ativa.")


@socketio.on('create_room')
def handle_create_room(data):
    sid = request.sid
    nickname = data.get('nickname', f'Host_{sid[:4]}').strip()[:25]
    logger.info(f"handle_create_room: Recebido de SID {sid} para nickname {nickname}")
    
    room_pin = generate_room_pin()
    logger.info(f"handle_create_room: PIN gerado {room_pin}")

    with rooms_lock:
        logger.debug(f"handle_create_room: Lock adquirido para sala {room_pin}")
        rooms_data[room_pin] = {
            "host_sid": sid,
            "host_nickname_on_creation": nickname, # Armazena o nickname do host original
            "players": {sid: {"nickname": nickname, "score": 0, "answers": {}}},
            "game_state": {
                "current_question_index": -1, "quiz_active": False, "question_start_time": None,
                "time_per_question": 20, "question_timer_thread": None,
            }
        }
        join_room(room_pin) 
        session['current_room_pin'] = room_pin 
        session['is_host'] = True
        logger.info(f"Sala {room_pin} criada com host '{nickname}' (SID: {sid}). Chaves de rooms_data: {list(rooms_data.keys())}")
    
    emit('room_created', {"roomPin": room_pin, "nickname": nickname, "sid": sid, "isHost": True,
                           "players": [nickname]}, room=sid)
    logger.info(f"handle_create_room: Evento 'room_created' emitido para sala {room_pin}.")


@socketio.on('join_room_pin')
def handle_join_room_pin(data):
    # ... (lógica como antes, mas garanta que o jogador é adicionado a room["players"][sid])
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
        
        room["players"][sid] = {"nickname": nickname, "score": 0, "answers": {}} # Adiciona/atualiza jogador
        
        logger.info(f"Jogador '{nickname}' (SID {sid}) entrou/atualizou na sala {room_pin}.")
        join_room(room_pin) 
        session['current_room_pin'] = room_pin
        session['is_host'] = (sid == room.get("host_sid")) 

        current_players_nicknames = [p_data["nickname"] for p_data in room["players"].values()]
        
        emit('room_joined', {
            "roomPin": room_pin, "nickname": nickname, "sid": sid, 
            "isHost": session['is_host'], "players": current_players_nicknames,
            "quizActive": room["game_state"]["quiz_active"] 
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
                payload = {"question": current_q.to_dict(), "questionNumber": q_idx + 1,
                           "totalQuestions": TOTAL_QUESTIONS, "timeLimit": room["game_state"]["time_per_question"]}
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

        # Sala existe. Lógica para re-adicionar/atualizar o jogador.
        is_confirmed_host = False
        player_data_to_use = {"nickname": nickname_from_client, "score": 0, "answers": {}} 

        # Se o host_sid da sala está None (host desconectou) E o nickname bate com o host original
        if room.get("host_sid") is None and room.get("host_nickname_on_creation") == nickname_from_client:
            logger.info(f"handle_rejoin_room_check: Host '{nickname_from_client}' reconectando à sala órfã '{room_pin}'. Atualizando host_sid para {sid}.")
            room["host_sid"] = sid
            is_confirmed_host = True
            # Mantém os dados do jogador se já existiam com outro SID (pouco provável para host, mas seguro)
            for old_s, p_data in list(room["players"].items()):
                if p_data["nickname"] == nickname_from_client and old_s == room.get("host_sid_disconnected_temp"):
                    player_data_to_use = p_data.copy()
                    if old_s != sid: del room["players"][old_s] # Remove entrada antiga do host
                    break
        elif room.get("host_sid") == sid: # Se o SID atual já é o host (ex: refresh sem mudança de SID)
            is_confirmed_host = True
            logger.info(f"handle_rejoin_room_check: SID {sid} já é o host da sala '{room_pin}'.")
            if sid in room["players"]: # Apenas atualiza o nickname se necessário
                 room["players"][sid]["nickname"] = nickname_from_client
            else: # Adiciona se por algum motivo não estava
                 room["players"][sid] = player_data_to_use

        # Adiciona/atualiza o jogador com o SID atual
        if sid not in room["players"]:
            room["players"][sid] = player_data_to_use
            logger.info(f"handle_rejoin_room_check: Jogador '{nickname_from_client}' (SID {sid}) adicionado à sala '{room_pin}'.")
        else: # Se já existe com este SID, apenas garante que o nickname está atualizado
            room["players"][sid]["nickname"] = nickname_from_client

        if "host_sid_disconnected_temp" in room: # Limpa o SID temporário do host
            del room["host_sid_disconnected_temp"]
        
        join_room(room_pin) 
        session['current_room_pin'] = room_pin
        session['is_host'] = is_confirmed_host
        
        current_players_nicknames = [p_data["nickname"] for p_data in room["players"].values()]
        logger.info(f"handle_rejoin_room_check: SID {sid} ('{nickname_from_client}') re-processado para sala '{room_pin}'. É host: {session['is_host']}")

        emit('room_joined', { 
            "roomPin": room_pin, "nickname": nickname_from_client, "sid": sid, 
            "isHost": session['is_host'], "players": current_players_nicknames,
            "quizActive": room["game_state"]["quiz_active"] 
        }, room=sid)
        
        socketio.emit('player_joined_room', { 
            "nickname": nickname_from_client, "sid": sid, "roomPin": room_pin,
            "players": current_players_nicknames
        }, room=room_pin, include_self=False)

        if room["game_state"]["quiz_active"]:
            # ... (lógica para enviar pergunta atual)
            pass


@socketio.on('start_quiz_for_room')
def handle_start_quiz_for_room(data):
    # ... (mesma lógica de antes, com logs detalhados)
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
    # ... (mesma lógica de antes, com logs detalhados)
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

