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

# --- Configuração da Aplicação Flask ---
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'bict_quiz_ufma_salas_super_secretas!'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    logger=True,
                    engineio_logger=True,
                    async_mode=None) # Deixa o SocketIO escolher (eventlet preferido)

logger.info(f"SocketIO async_mode selecionado: {socketio.async_mode}")

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
rooms_data = {} # room_pin: {"host_sid": str, "players": {sid: {"nickname": str, "score": int, "answers": {}}}, "game_state": {...}}
rooms_lock = threading.Lock() # Lock para proteger o acesso a rooms_data

def generate_room_pin(length=5):
    """ Gera um PIN alfanumérico único para a sala. """
    while True:
        pin = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        with rooms_lock:
            if pin not in rooms_data:
                return pin

def get_room_or_emit_error(room_pin, sid_to_emit_to=None):
    """ Helper para buscar uma sala; emite erro se não encontrada. """
    sid_to_emit_to = sid_to_emit_to or request.sid
    with rooms_lock:
        room = rooms_data.get(room_pin)
    if not room:
        logger.warning(f"Tentativa de acesso à sala inexistente: {room_pin} por SID {sid_to_emit_to}")
        emit('room_error', {'message': f"Sala com PIN {room_pin} não encontrada."}, room=sid_to_emit_to)
        return None
    return room

# --- Rotas HTTP ---
@app.route('/')
def index_page(): return render_template('index.html')

@app.route('/lobby') # Nova rota para a tela de lobby/espera
def lobby_page(): return render_template('lobby.html')

@app.route('/quiz')
def quiz_page(): return render_template('quiz.html')

@app.route('/results')
def results_page(): return render_template('results.html')

# --- Funções Auxiliares do Quiz (Adaptadas para Salas) ---
def _reset_room_quiz_state(room_pin):
    # Chamada de dentro de um contexto com rooms_lock
    room = rooms_data.get(room_pin)
    if not room: return

    room["game_state"] = {
        "current_question_index": -1,
        "quiz_active": False,
        "question_start_time": None,
        "time_per_question": 20,
        "question_timer_thread": None,
    }
    # Reseta scores e respostas dos jogadores da sala
    for player_sid in room["players"]:
        room["players"][player_sid]["score"] = 0
        room["players"][player_sid]["answers"] = {}
        if "answered_current_question" in room["players"][player_sid]:
            del room["players"][player_sid]["answered_current_question"]
    logger.info(f"Estado do quiz resetado para a sala {room_pin}.")


def _get_current_question_for_room(room_pin):
    # Chamada de dentro de um contexto com rooms_lock
    room = rooms_data.get(room_pin)
    if not room or not room["game_state"]["quiz_active"]: return None
    idx = room["game_state"]["current_question_index"]
    if 0 <= idx < TOTAL_QUESTIONS:
        return new_quiz_questions[idx]
    return None

def _advance_question_for_room(room_pin):
    # Chamada de dentro de um contexto com rooms_lock
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
        for player_sid in room["players"]: # Limpa flag de resposta
            if "answered_current_question" in room["players"][player_sid]:
                del room["players"][player_sid]["answered_current_question"]
        
        payload = {"question": current_q.to_dict(), "questionNumber": idx + 1,
                   "totalQuestions": TOTAL_QUESTIONS, "timeLimit": room["game_state"]["time_per_question"]}
        socketio.emit('new_question', payload, room=room_pin)
        _start_question_timer_for_room(room_pin)
    else:
        logger.info(f"Sala {room_pin}: Fim das perguntas. Finalizando quiz.")
        _end_quiz_for_room(room_pin)


def _question_timer_logic_for_room(room_pin):
    room = get_room_or_emit_error(room_pin) # Verifica se a sala ainda existe
    if not room: 
        logger.warning(f"[Timer Sala {room_pin}] Sala não existe mais. Timer encerrando.")
        return

    question_index_at_start = room["game_state"]["current_question_index"]
    time_to_wait = room["game_state"]["time_per_question"]
    logger.info(f"[Timer Sala {room_pin} - Q{question_index_at_start + 1}] Esperando {time_to_wait}s.")
    socketio.sleep(time_to_wait + 0.5)

    with rooms_lock: # Adquire lock para verificar/modificar estado da sala
        room = rooms_data.get(room_pin) # Re-obtém a sala dentro do lock
        if not room:
            logger.warning(f"[Timer Sala {room_pin} - Q{question_index_at_start + 1}] Sala desapareceu. Timer encerrando.")
            return

        gs = room["game_state"]
        if gs["quiz_active"] and gs["current_question_index"] == question_index_at_start:
            logger.info(f"[Timer Sala {room_pin} - Q{question_index_at_start + 1}] Tempo esgotado.")
            current_q_obj = _get_current_question_for_room(room_pin) # Já está dentro do lock
            if current_q_obj:
                 socketio.emit('time_up', {'questionId': current_q_obj.id, 'roomPin': room_pin}, room=room_pin)
            _advance_question_for_room(room_pin)
        else:
            logger.info(f"[Timer Sala {room_pin} - Q{question_index_at_start + 1}] Quiz inativo ou pergunta já avançou. Timer encerrando.")


def _start_question_timer_for_room(room_pin):
    # Chamada de dentro de um contexto com rooms_lock
    room = rooms_data.get(room_pin)
    if not room: return

    if room["game_state"].get("question_timer_thread") and room["game_state"]["question_timer_thread"].is_alive():
        logger.warning(f"Sala {room_pin}: Timer já existe para Q{room['game_state']['current_question_index']+1}.")
        return
    
    logger.info(f"Sala {room_pin}: Iniciando timer para Q{room['game_state']['current_question_index'] + 1}.")
    room["game_state"]["question_timer_thread"] = socketio.start_background_task(
        target=_question_timer_logic_for_room, room_pin=room_pin
    )

def _calculate_recommendation_for_room(player_answers): # Mesma lógica de antes
    if not player_answers: return "Nenhuma resposta registrada."
    correct_skill_counts = defaultdict(int)
    for q_id, answer_data in player_answers.items():
        if answer_data.get('is_correct'):
            skill = answer_data.get('skill')
            if skill: correct_skill_counts[skill] += 1
    if not correct_skill_counts: return "Nenhum acerto para sugerir área."
    best_skill_area = max(correct_skill_counts, key=correct_skill_counts.get)
    # ... (resto da lógica de recomendação e course_suggestions como antes) ...
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
        "Conhecimentos Gerais": "Qualquer área!"
    }
    suggestion_text = f"Você se destacou em '{best_skill_area}'. "
    suggestion_text += f"Cursos como {course_suggestions.get(best_skill_area, 'áreas relacionadas')} podem ser interessantes."
    sorted_correct_skills = sorted(correct_skill_counts.items(), key=lambda item: item[1], reverse=True)
    top_skills_info = "; ".join([f"{s[0]}: {s[1]} acerto(s)" for s in sorted_correct_skills[:3]])
    return f"{suggestion_text} Suas áreas de destaque: {top_skills_info}."


def _end_quiz_for_room(room_pin):
    # Chamada de dentro de um contexto com rooms_lock
    room = rooms_data.get(room_pin)
    if not room: return

    if not room["game_state"]["quiz_active"] and room["game_state"]["current_question_index"] < TOTAL_QUESTIONS -1 :
        logger.info(f"Sala {room_pin}: end_quiz chamada, mas quiz não estava ativo ou já terminou/resetou.")
        # return # Não retorna para garantir que os resultados sejam enviados se o quiz foi interrompido.

    room["game_state"]["quiz_active"] = False
    logger.info(f"Sala {room_pin}: Quiz finalizado. Calculando resultados...")
    results = []
    for sid, player_data in room["players"].items():
        recommendation = _calculate_recommendation_for_room(player_data.get("answers", {}))
        results.append({"nickname": player_data["nickname"], "score": player_data["score"],
                        "recommendation": recommendation, "sid": sid})
    results.sort(key=lambda p: p["score"], reverse=True)
    socketio.emit('quiz_ended', {"results": results, "roomPin": room_pin}, room=room_pin)
    logger.info(f"Sala {room_pin}: Resultados enviados.")
    # Não reseta a sala aqui, o host pode querer ver os resultados ou reiniciar.
    # A sala será limpa se todos saírem ou após um tempo de inatividade (não implementado).

# --- Eventos SocketIO ---
@socketio.on('connect')
def handle_connect():
    logger.info(f"Cliente CONECTADO: SID {request.sid}")
    # Jogador não entra em nenhuma sala específica ao conectar, apenas estabelece a conexão.
    # Ele precisará enviar 'create_room' ou 'join_room_pin'.

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    logger.info(f"Cliente DESCONECTADO: SID {sid}")
    with rooms_lock:
        room_pin_to_leave = None
        player_nickname_left = None
        # Encontra a sala da qual o jogador está saindo
        for pin, room_data in rooms_data.items():
            if sid in room_data["players"]:
                room_pin_to_leave = pin
                player_nickname_left = room_data["players"][sid]["nickname"]
                del room_data["players"][sid]
                logger.info(f"Jogador '{player_nickname_left}' (SID: {sid}) removido da sala {pin}.")
                break
        
        if room_pin_to_leave:
            room = rooms_data.get(room_pin_to_leave) # Re-get room data
            if room: # Se a sala ainda existe
                # Notifica outros jogadores na sala
                remaining_players_nicknames = [p["nickname"] for p in room["players"].values()]
                socketio.emit('player_left', {
                    "nickname": player_nickname_left, "sid": sid,
                    "remainingPlayers": remaining_players_nicknames,
                    "roomPin": room_pin_to_leave
                }, room=room_pin_to_leave)

                # Se o host saiu, podemos designar um novo host ou encerrar a sala (lógica complexa, simplificar por agora)
                if sid == room["host_sid"]:
                    logger.info(f"Host (SID: {sid}) da sala {room_pin_to_leave} desconectou.")
                    if not room["players"]: # Se não há mais jogadores
                        logger.info(f"Sala {room_pin_to_leave} está vazia após saída do host. Removendo sala.")
                        del rooms_data[room_pin_to_leave]
                    else:
                        # Poderia emitir uma mensagem de que o host saiu.
                        # Por simplicidade, a sala continua mas sem host ativo para iniciar um novo quiz.
                        socketio.emit('host_left', {"roomPin": room_pin_to_leave, "message": "O líder da sala saiu."}, room=room_pin_to_leave)
                        room["host_sid"] = None # Marca que não há host

                elif not room["players"]: # Se não era o host, mas a sala ficou vazia
                    logger.info(f"Sala {room_pin_to_leave} ficou vazia. Removendo sala.")
                    del rooms_data[room_pin_to_leave]


@socketio.on('create_room')
def handle_create_room(data):
    sid = request.sid
    nickname = data.get('nickname', f'Host_{sid[:4]}').strip()[:25]
    with rooms_lock:
        room_pin = generate_room_pin()
        rooms_data[room_pin] = {
            "host_sid": sid,
            "players": {sid: {"nickname": nickname, "score": 0, "answers": {}}},
            "game_state": { # Estado inicial do jogo para a nova sala
                "current_question_index": -1,
                "quiz_active": False,
                "question_start_time": None,
                "time_per_question": 20,
                "question_timer_thread": None,
            }
        }
        join_room(room_pin) # Host entra na sua própria sala SocketIO
        session['current_room_pin'] = room_pin # Guarda na sessão do host
        session['is_host'] = True

    logger.info(f"Sala {room_pin} criada pelo host '{nickname}' (SID: {sid}).")
    emit('room_created', {"roomPin": room_pin, "nickname": nickname, "sid": sid, "isHost": True,
                           "players": [nickname]}, room=sid)


@socketio.on('join_room_pin')
def handle_join_room_pin(data):
    sid = request.sid
    nickname = data.get('nickname', f'Jogador_{sid[:4]}').strip()[:25]
    room_pin = data.get('roomPin', '').upper()

    with rooms_lock:
        room = rooms_data.get(room_pin)
        if not room:
            logger.warning(f"Tentativa de join na sala {room_pin} por '{nickname}', mas sala não existe.")
            emit('room_join_error', {"message": f"Sala com PIN '{room_pin}' não encontrada."}, room=sid)
            return
        
        if sid in room["players"]: # Jogador já está na sala (talvez reconectando ou bug)
            room["players"][sid]["nickname"] = nickname # Atualiza nickname
            logger.info(f"Jogador '{nickname}' (SID {sid}) já estava na sala {room_pin}. Nickname atualizado.")
        else:
            room["players"][sid] = {"nickname": nickname, "score": 0, "answers": {}}
            logger.info(f"Jogador '{nickname}' (SID {sid}) entrou na sala {room_pin}.")

        join_room(room_pin) # Jogador entra na sala SocketIO
        session['current_room_pin'] = room_pin
        session['is_host'] = (sid == room["host_sid"])

        current_players_nicknames = [p_data["nickname"] for p_data in room["players"].values()]
        
        # Confirmação para quem entrou
        emit('room_joined', {
            "roomPin": room_pin, "nickname": nickname, "sid": sid, 
            "isHost": session['is_host'], "players": current_players_nicknames,
            "quizActive": room["game_state"]["quiz_active"] # Informa se o quiz já começou
        }, room=sid)
        
        # Notifica os outros na sala (incluindo o host)
        socketio.emit('player_joined_room', {
            "nickname": nickname, "sid": sid, "roomPin": room_pin,
            "players": current_players_nicknames
        }, room=room_pin, include_self=False)

        # Se o quiz já estiver ativo na sala, envia a pergunta atual para o jogador que acabou de entrar
        if room["game_state"]["quiz_active"]:
            current_q = _get_current_question_for_room(room_pin) # Já está no lock
            if current_q:
                q_idx = room["game_state"]["current_question_index"]
                payload = {"question": current_q.to_dict(), "questionNumber": q_idx + 1,
                           "totalQuestions": TOTAL_QUESTIONS, "timeLimit": room["game_state"]["time_per_question"]}
                emit('new_question', payload, room=sid) # Envia só para quem entrou


@socketio.on('start_quiz_for_room')
def handle_start_quiz_for_room(data):
    sid = request.sid
    room_pin = data.get('roomPin', '').upper()
    
    with rooms_lock:
        room = rooms_data.get(room_pin)
        if not room:
            emit('room_error', {"message": "Sala não encontrada."}, room=sid)
            return
        if room["host_sid"] != sid:
            emit('room_error', {"message": "Apenas o líder da sala pode iniciar o quiz."}, room=sid)
            return
        if room["game_state"]["quiz_active"]:
            emit('room_error', {"message": "O quiz nesta sala já está em andamento."}, room=sid)
            return
        if not room["players"]:
            emit('room_error', {"message": "Não há jogadores na sala para iniciar."}, room=sid)
            return

        logger.info(f"Host {sid} iniciando quiz para sala {room_pin}.")
        _reset_room_quiz_state(room_pin) # Garante que o estado do quiz da sala está limpo
        # A função _start_quiz_logic será chamada dentro de _reset_room_quiz_state ou similar
        # Vamos chamar diretamente _start_quiz_logic que já faz o necessário
        # _start_quiz_logic já está definida para ser chamada com lock
        room["game_state"]["current_question_index"] = -1
        room["game_state"]["quiz_active"] = True
        room["game_state"]["question_start_time"] = None
        if room["game_state"]["question_timer_thread"] and room["game_state"]["question_timer_thread"].is_alive():
            pass 
        room["game_state"]["question_timer_thread"] = None
        for p_data in room["players"].values(): 
            p_data["score"] = 0
            p_data["answers"] = {}
            if "answered_current_question" in p_data:
                del p_data["answered_current_question"]
        
        logger.info(f"_start_quiz_logic para sala {room_pin}: Emitindo 'quiz_started'.")
        socketio.emit('quiz_started', {"message": "O quiz vai começar!", "roomPin": room_pin}, room=room_pin)
        _advance_question_for_room(room_pin)


@socketio.on('submit_answer')
def handle_submit_answer(data):
    sid = request.sid
    room_pin = data.get('roomPin', '').upper()
    question_id = data.get('questionId')
    selected_option_id = data.get('selectedOptionId')

    with rooms_lock:
        room = rooms_data.get(room_pin)
        if not room or sid not in room["players"]:
            logger.warning(f"Resposta de {sid} para sala {room_pin} ignorada: sala/jogador desconhecido.")
            emit('answer_ack', {"success": False, "error": "Sala ou jogador não reconhecido."}, room=sid)
            return
        
        gs = room["game_state"]
        player = room["players"][sid]

        if not gs["quiz_active"]:
            logger.warning(f"Resposta de {player['nickname']} para sala {room_pin} ignorada: quiz inativo.")
            emit('answer_ack', {"success": False, "error": "O quiz nesta sala não está ativo."}, room=sid)
            return
        
        current_q = _get_current_question_for_room(room_pin) # Já está no lock

        if not current_q or current_q.id != question_id:
            logger.warning(f"Resposta de {player['nickname']} para QID {question_id} na sala {room_pin}, mas Q atual é {current_q.id if current_q else 'N/A'}.")
            emit('answer_ack', {"success": False, "error": "Resposta para pergunta incorreta ou antiga."}, room=sid)
            return
        if player.get("answered_current_question"):
            logger.warning(f"{player['nickname']} já respondeu à pergunta {question_id} na sala {room_pin}.")
            emit('answer_ack', {"success": False, "error": "Você já respondeu a esta pergunta."}, room=sid)
            return

        is_correct = (selected_option_id == current_q.correct_option_id)
        points_earned = 0
        if is_correct:
            base_points = 100
            time_taken = time.time() - gs.get("question_start_time", time.time())
            time_limit = gs["time_per_question"]
            bonus_percentage = max(0, (time_limit - time_taken) / time_limit if time_limit > 0 else 0)
            max_bonus_points = 50
            bonus_points = int(max_bonus_points * bonus_percentage)
            points_earned = base_points + bonus_points
            player["score"] += points_earned
        
        player["answers"][current_q.id] = {
            "answer_id": selected_option_id, "is_correct": is_correct,
            "skill": current_q.skill_area, "points_earned": points_earned
        }
        player["answered_current_question"] = True
        logger.info(f"Sala {room_pin}: '{player['nickname']}' respondeu Q'{current_q.id}': {'Correto' if is_correct else 'Errado'}. Pts: {points_earned}. Total: {player['score']}")
        
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


# --- Inicialização ---
if __name__ == '__main__':
    logger.info("Iniciando servidor Flask-SocketIO para Quiz Vocacional com Salas...")
    socketio.run(app, debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5001))

