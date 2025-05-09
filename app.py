# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template, session, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import time
import threading
from collections import defaultdict
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuração da Aplicação Flask ---
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'bict_quiz_ufma_muito_secreto_v3!'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


# --- Definição das Novas Questões ---
class QuizOption:
    def __init__(self, id: str, text: str):
        self.id = id
        self.text = text
    def to_dict(self):
        return {"id": self.id, "text": self.text}

class QuizQuestion:
    def __init__(self, id: str, text: str, options: list[QuizOption], correct_option_id: str, skill_area: str, difficulty: str):
        self.id = id
        self.text = text
        self.options = options
        self.correct_option_id = correct_option_id
        self.skill_area = skill_area
        self.difficulty = difficulty
    def to_dict(self):
        return {
            "id": self.id, "text": self.text,
            "options": [opt.to_dict() for opt in self.options],
            "correctOptionId": self.correct_option_id,
            "skillArea": self.skill_area, "difficulty": self.difficulty
        }

new_quiz_questions_data = [
  {
    "id": "nq1",
    "text": "Se um algoritmo é uma sequência finita de instruções para resolver um problema, qual das seguintes opções MELHOR descreve uma característica essencial de um bom algoritmo?",
    "options": [
      { "id": "nq1_opt1", "text": "Ser escrito na linguagem de programação mais recente." },
      { "id": "nq1_opt2", "text": "Ser o mais curto possível, mesmo que difícil de entender." },
      { "id": "nq1_opt3", "text": "Ser eficiente em termos de tempo e recursos, e ser claro." },
      { "id": "nq1_opt4", "text": "Funcionar apenas para um conjunto específico de dados de entrada." }
    ],
    "correctOptionId": "nq1_opt3",
    "skillArea": "BICT - Lógica de Programação",
    "difficulty": "Fácil",
  },
  {
    "id": "nq2",
    "text": "No contexto de redes de computadores, o que significa a sigla 'IP' em 'Endereço IP'?",
    "options": [
      { "id": "nq2_opt1", "text": "Internal Protocol" },
      { "id": "nq2_opt2", "text": "Internet Protocol" },
      { "id": "nq2_opt3", "text": "Instruction Pointer" },
      { "id": "nq2_opt4", "text": "Immediate Power" }
    ],
    "correctOptionId": "nq2_opt2",
    "skillArea": "BICT - Redes de Computadores",
    "difficulty": "Fácil",
  },
  {
    "id": "nq3",
    "text": "Qual o resultado da expressão lógica: (VERDADEIRO OU FALSO) E (NÃO FALSO)?",
    "options": [
      { "id": "nq3_opt1", "text": "VERDADEIRO" },
      { "id": "nq3_opt2", "text": "FALSO" },
      { "id": "nq3_opt3", "text": "Depende" },
      { "id": "nq3_opt4", "text": "Inválido" }
    ],
    "correctOptionId": "nq3_opt1",
    "skillArea": "BICT - Matemática Discreta",
    "difficulty": "Fácil",
  },
  {
    "id": "nq4",
    "text": "Em Engenharia de Computação, qual componente de um computador é responsável por executar a maioria das instruções e cálculos?",
    "options": [
      { "id": "nq4_opt1", "text": "Memória RAM" },
      { "id": "nq4_opt2", "text": "Disco Rígido (HD/SSD)" },
      { "id": "nq4_opt3", "text": "Unidade Central de Processamento (CPU)" },
      { "id": "nq4_opt4", "text": "Placa de Vídeo (GPU)" }
    ],
    "correctOptionId": "nq4_opt3",
    "skillArea": "Eng. Computação - Arquitetura de Computadores",
    "difficulty": "Fácil",
  },
  {
    "id": "nq5",
    "text": "Um engenheiro civil está projetando uma viga para uma ponte. Qual dos seguintes materiais é comumente escolhido por sua alta resistência à compressão?",
    "options": [
      { "id": "nq5_opt1", "text": "Madeira Leve" },
      { "id": "nq5_opt2", "text": "Borracha Vulcanizada" },
      { "id": "nq5_opt3", "text": "Concreto Armado" },
      { "id": "nq5_opt4", "text": "Plástico PVC" }
    ],
    "correctOptionId": "nq5_opt3",
    "skillArea": "Eng. Civil - Materiais de Construção",
    "difficulty": "Médio",
  },
  {
    "id": "nq6",
    "text": "Qual lei da termodinâmica afirma que a energia não pode ser criada nem destruída, apenas transformada de uma forma para outra?",
    "options": [
      { "id": "nq6_opt1", "text": "Lei Zero" },
      { "id": "nq6_opt2", "text": "Primeira Lei" },
      { "id": "nq6_opt3", "text": "Segunda Lei" },
      { "id": "nq6_opt4", "text": "Terceira Lei" }
    ],
    "correctOptionId": "nq6_opt2",
    "skillArea": "Eng. Mecânica - Termodinâmica",
    "difficulty": "Médio",
  },
  {
    "id": "nq7",
    "text": "Um carro de Fórmula 1 utiliza um aerofólio traseiro para gerar 'downforce'. Este efeito está mais relacionado a qual princípio da física?",
    "options": [
      { "id": "nq7_opt1", "text": "Efeito Doppler" },
      { "id": "nq7_opt2", "text": "Princípio de Arquimedes" },
      { "id": "nq7_opt3", "text": "Princípio de Bernoulli (relacionado à diferença de pressão)" },
      { "id": "nq7_opt4", "text": "Lei da Gravitação Universal" }
    ],
    "correctOptionId": "nq7_opt3",
    "skillArea": "Eng. Aeroespacial - Aerodinâmica",
    "difficulty": "Médio",
  },
  {
    "id": "nq8",
    "text": "Qual das seguintes ações é uma medida fundamental na Engenharia Ambiental para mitigar o impacto de resíduos sólidos urbanos?",
    "options": [
      { "id": "nq8_opt1", "text": "Aumentar a capacidade dos aterros sanitários existentes." },
      { "id": "nq8_opt2", "text": "Incentivar o consumo descartável para facilitar a coleta." },
      { "id": "nq8_opt3", "text": "Implementar programas de coleta seletiva e reciclagem." },
      { "id": "nq8_opt4", "text": "Queimar todos os resíduos a céu aberto para reduzir volume." }
    ],
    "correctOptionId": "nq8_opt3",
    "skillArea": "Eng. Ambiental - Gestão de Resíduos",
    "difficulty": "Fácil",
  },
  {
    "id": "nq9",
    "text": "Em Engenharia de Transportes, o planejamento de um sistema de semáforos em um cruzamento visa principalmente:",
    "options":
    [
      { "id": "nq9_opt1", "text": "Aumentar a velocidade média dos veículos na via." },
      { "id": "nq9_opt2", "text": "Priorizar exclusivamente o fluxo de transporte público." },
      { "id": "nq9_opt3", "text": "Otimizar o fluxo de veículos e a segurança de pedestres." },
      { "id": "nq9_opt4", "text": "Reduzir o número de faixas de rolamento." }
    ],
    "correctOptionId": "nq9_opt3",
    "skillArea": "Eng. Transportes - Engenharia de Tráfego",
    "difficulty": "Médio",
  },
  {
    "id": "nq10",
    "text": "Se um terreno retangular tem 20 metros de frente e 30 metros de profundidade, qual é a sua área total?",
    "options": [
      { "id": "nq10_opt1", "text": "50 m²" },
      { "id": "nq10_opt2", "text": "100 m²" },
      { "id": "nq10_opt3", "text": "600 m²" },
      { "id": "nq10_opt4", "text": "500 m²" }
    ],
    "correctOptionId": "nq10_opt3",
    "skillArea": "Cálculo Básico - Geometria",
    "difficulty": "Fácil",
  },
  {
    "id": "nq11",
    "text": "Um projeto requer que uma peça metálica se expanda no máximo 0.05mm com o calor. O engenheiro precisa calcular a variação de temperatura permitida. Qual conceito físico é fundamental aqui?",
    "options": [
      { "id": "nq11_opt1", "text": "Resistência Elétrica" },
      { "id": "nq11_opt2", "text": "Dilatação Térmica" },
      { "id": "nq11_opt3", "text": "Capacitância" },
      { "id": "nq11_opt4", "text": "Momento de Inércia" }
    ],
    "correctOptionId": "nq11_opt2",
    "skillArea": "Física Aplicada - Termologia",
    "difficulty": "Médio",
  },
  {
    "id": "nq12",
    "text": "Se você tem um conjunto de dados de medições e precisa encontrar o valor que ocorre com maior frequência, qual medida estatística você usaria?",
    "options": [
      { "id": "nq12_opt1", "text": "Média Aritmética" },
      { "id": "nq12_opt2", "text": "Mediana" },
      { "id": "nq12_opt3", "text": "Moda" },
      { "id": "nq12_opt4", "text": "Desvio Padrão" }
    ],
    "correctOptionId": "nq12_opt3",
    "skillArea": "BICT - Estatística Básica",
    "difficulty": "Fácil",
  }
]

new_quiz_questions = []
for q_data in new_quiz_questions_data:
    options_obj = [QuizOption(opt["id"], opt["text"]) for opt in q_data["options"]]
    new_quiz_questions.append(
        QuizQuestion(
            id=q_data["id"], text=q_data["text"], options=options_obj,
            correct_option_id=q_data["correctOptionId"], skill_area=q_data["skillArea"],
            difficulty=q_data["difficulty"]
        )
    )
TOTAL_QUESTIONS = len(new_quiz_questions)

# --- Estado do Jogo ---
game_state = {
    "players": {},
    "current_question_index": -1,
    "quiz_active": False,
    "question_start_time": None,
    "time_per_question": 20,
    "question_timer_thread": None,
    "quiz_room": "main_quiz_room"
}
game_lock = threading.Lock()

# --- Rotas HTTP para servir os arquivos HTML ---
@app.route('/')
def index_page():
    logger.info("Tentando servir templates/index.html")
    return render_template('index.html')

@app.route('/quiz')
def quiz_page():
    logger.info("Servindo quiz.html")
    return render_template('quiz.html')

@app.route('/results')
def results_page():
    logger.info("Servindo results.html")
    return render_template('results.html')

# --- Funções Auxiliares do Quiz ---
def _start_quiz_logic():
    """ Lógica interna para iniciar o quiz, chamada de dentro de um lock. """
    game_state["current_question_index"] = -1
    game_state["quiz_active"] = True
    game_state["question_start_time"] = None
    if game_state["question_timer_thread"] and game_state["question_timer_thread"].is_alive():
        # A thread antiga deve se encerrar graciosamente
        pass
    game_state["question_timer_thread"] = None
    for p_data in game_state["players"].values(): # Limpa scores/respostas de quiz anterior
        p_data["score"] = 0
        p_data["answers"] = {}
        if "answered_current_question" in p_data:
            del p_data["answered_current_question"]
    
    socketio.emit('quiz_started', {"message": "O quiz vai começar!"}, room=game_state["quiz_room"])
    advance_question()

def reset_quiz_state():
    with game_lock:
        game_state["players"] = {} # Limpa jogadores também no reset completo
        game_state["current_question_index"] = -1
        game_state["quiz_active"] = False
        game_state["question_start_time"] = None
        game_state["question_timer_thread"] = None
        logger.info("Estado do quiz resetado.")

def get_current_question():
    with game_lock:
        idx = game_state["current_question_index"]
        if 0 <= idx < TOTAL_QUESTIONS:
            return new_quiz_questions[idx]
    return None

def advance_question():
    with game_lock:
        if not game_state["quiz_active"]: return
        game_state["current_question_index"] += 1
        idx = game_state["current_question_index"]
        if idx < TOTAL_QUESTIONS:
            current_q = new_quiz_questions[idx]
            logger.info(f"Avançando para a pergunta {idx + 1}: {current_q.text[:50]}...")
            game_state["question_start_time"] = time.time()
            for player_sid in game_state["players"]:
                if "answered_current_question" in game_state["players"][player_sid]:
                    del game_state["players"][player_sid]["answered_current_question"]
            payload = {
                "question": current_q.to_dict(), "questionNumber": idx + 1,
                "totalQuestions": TOTAL_QUESTIONS, "timeLimit": game_state["time_per_question"]
            }
            socketio.emit('new_question', payload, room=game_state["quiz_room"])
            start_question_timer_thread()
        else:
            logger.info("Fim das perguntas. Finalizando o quiz.")
            end_quiz()

def question_timer_logic():
    question_index_at_start = game_state["current_question_index"]
    time_to_wait = game_state["time_per_question"]
    logger.info(f"[Timer Q{question_index_at_start + 1}] Esperando {time_to_wait}s.")
    socketio.sleep(time_to_wait)
    with game_lock:
        if game_state["quiz_active"] and game_state["current_question_index"] == question_index_at_start:
            logger.info(f"[Timer Q{question_index_at_start + 1}] Tempo esgotado.")
            current_q_obj = get_current_question()
            if current_q_obj:
                 socketio.emit('time_up', {'questionId': current_q_obj.id}, room=game_state["quiz_room"])
            advance_question()
        else:
            logger.info(f"[Timer Q{question_index_at_start + 1}] Quiz inativo ou pergunta já avançou. Timer encerrando.")

def start_question_timer_thread():
    if game_state["question_timer_thread"] and game_state["question_timer_thread"].is_alive():
        logger.warning(f"Timer já existe para Q{game_state['current_question_index']+1}.")
        return
    logger.info(f"Iniciando thread do timer para Q{game_state['current_question_index'] + 1}.")
    game_state["question_timer_thread"] = socketio.start_background_task(target=question_timer_logic)

def calculate_recommendation(player_answers):
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

def end_quiz():
    with game_lock:
        game_state["quiz_active"] = False
        logger.info("Quiz finalizado. Calculando resultados...")
        results = []
        for sid, player_data in game_state["players"].items():
            recommendation = calculate_recommendation(player_data.get("answers", {}))
            results.append({
                "nickname": player_data["nickname"], "score": player_data["score"],
                "recommendation": recommendation, "sid": sid
            })
        results.sort(key=lambda p: p["score"], reverse=True)
        socketio.emit('quiz_ended', {"results": results}, room=game_state["quiz_room"])
        logger.info(f"Resultados enviados: {results}")

# --- Eventos SocketIO ---
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    logger.info(f"Cliente conectado: {sid}")
    join_room(game_state["quiz_room"])
    logger.info(f"Cliente {sid} adicionado à sala '{game_state['quiz_room']}'")
    with game_lock:
        if game_state["quiz_active"]:
            current_q = get_current_question()
            if current_q:
                payload = {
                    "question": current_q.to_dict(),
                    "questionNumber": game_state["current_question_index"] + 1,
                    "totalQuestions": TOTAL_QUESTIONS,
                    "timeLimit": game_state["time_per_question"],
                    "players": [pdata["nickname"] for pdata in game_state["players"].values()]
                }
                # Envia também o score atual do jogador, se ele já existia
                if sid in game_state["players"]:
                    payload["currentPlayer"] = {
                        "sid": sid,
                        "score": game_state["players"][sid].get("score", 0)
                    }
                emit('quiz_state_on_connect', payload, room=sid)
                logger.info(f"Quiz ativo. Estado enviado para {sid}.")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    logger.info(f"Cliente desconectado: {sid}")
    with game_lock:
        if sid in game_state["players"]:
            nickname = game_state["players"][sid]["nickname"]
            del game_state["players"][sid]
            logger.info(f"Jogador '{nickname}' (SID: {sid}) removido.")
            socketio.emit('player_left', {
                "nickname": nickname, "sid": sid,
                "remainingPlayers": [pdata["nickname"] for pdata in game_state["players"].values()]
                }, room=game_state["quiz_room"])
        if not game_state["players"] and game_state["quiz_active"]:
            logger.info("Último jogador desconectou. Resetando o quiz.")
            reset_quiz_state() # Reseta se não houver mais jogadores

@socketio.on('join_quiz')
def handle_join_quiz(data):
    sid = request.sid
    nickname = data.get('nickname', f'Jogador_{sid[:4]}').strip()[:25]
    should_start_quiz_now = False
    with game_lock:
        if sid not in game_state["players"]:
             game_state["players"][sid] = {"nickname": nickname, "score": 0, "answers": {}}
        else: # Atualiza nickname se já existia
            game_state["players"][sid]['nickname'] = nickname
        
        logger.info(f"Jogador '{nickname}' (SID: {sid}) processado no 'join_quiz'.")
        emit('join_ack', {"success": True, "nickname": nickname, "sid": sid, "room": game_state["quiz_room"]}, room=sid)
        
        socketio.emit('player_joined', {
            "nickname": nickname, "sid": sid,
            "allPlayers": [pdata["nickname"] for pdata in game_state["players"].values()]
            }, room=game_state["quiz_room"])

        # Se for o primeiro jogador e o quiz não estiver ativo, marca para iniciar
        if len(game_state["players"]) > 0 and not game_state["quiz_active"]:
            logger.info(f"Jogador '{nickname}' entrou. Quiz não ativo e há jogadores. Marcando para iniciar.")
            should_start_quiz_now = True # Inicia automaticamente com o primeiro jogador
            
    if should_start_quiz_now:
        logger.info("Chamando _start_quiz_logic() de handle_join_quiz.")
        with game_lock: # Garante que o lock seja adquirido antes de chamar _start_quiz_logic
            _start_quiz_logic()


@socketio.on('start_quiz') # Mantemos este evento caso queiramos um botão de start explícito no futuro
def handle_start_quiz(data=None):
    sid = request.sid
    with game_lock:
        if game_state["quiz_active"]:
            logger.info(f"Quiz já ativo. {sid} tentou iniciar.")
            emit('error_message', {'message': 'O quiz já está em andamento!'}, room=sid)
            return
        
        if not game_state["players"]:
             logger.warning(f"{sid} tentou iniciar quiz sem jogadores.")
             emit('error_message', {'message': 'Não há jogadores para iniciar o quiz.'}, room=sid)
             return

        logger.info(f"Evento 'start_quiz' recebido de {sid}. Iniciando o quiz...")
        _start_quiz_logic()


@socketio.on('submit_answer')
def handle_submit_answer(data):
    sid = request.sid
    with game_lock:
        if not game_state["quiz_active"] or sid not in game_state["players"]:
            emit('answer_ack', {"success": False, "error": "Quiz inativo ou jogador não reconhecido."}, room=sid)
            return
        player = game_state["players"][sid]
        question_id = data.get('questionId')
        selected_option_id = data.get('selectedOptionId')
        current_q = get_current_question()

        if not current_q or current_q.id != question_id:
            emit('answer_ack', {"success": False, "error": "Resposta para pergunta incorreta."}, room=sid)
            return
        if player.get("answered_current_question"):
            emit('answer_ack', {"success": False, "error": "Você já respondeu."}, room=sid)
            return

        is_correct = (selected_option_id == current_q.correct_option_id)
        points_earned = 0
        if is_correct:
            base_points = 100; time_taken = time.time() - game_state["question_start_time"]
            time_limit = game_state["time_per_question"]
            bonus_percentage = max(0, (time_limit - time_taken) / time_limit)
            max_bonus_points = 50; bonus_points = int(max_bonus_points * bonus_percentage)
            points_earned = base_points + bonus_points
            player["score"] += points_earned
        
        player["answers"][current_q.id] = {
            "answer_id": selected_option_id, "is_correct": is_correct,
            "skill": current_q.skill_area, "points_earned": points_earned
        }
        player["answered_current_question"] = True
        logger.info(f"'{player['nickname']}' respondeu Q'{current_q.id}': {'Correto' if is_correct else 'Errado'}. Pts: {points_earned}. Total: {player['score']}")
        
        emit('answer_feedback', {
            "questionId": current_q.id, "selectedOptionId": selected_option_id,
            "correctOptionId": current_q.correct_option_id, "isCorrect": is_correct,
            "pointsEarned": points_earned, "currentScore": player["score"]
        }, room=sid)
        
        scores_overview = sorted(
            [{"nickname": p_data["nickname"], "score": p_data["score"]} for p_data in game_state["players"].values()],
            key=lambda x: x["score"], reverse=True
        )
        socketio.emit('scores_update', {"scores": scores_overview[:10]}, room=game_state["quiz_room"])

        all_answered = all(p_data.get("answered_current_question") for p_data in game_state["players"].values())
        if all_answered:
            logger.info(f"Todos os {len(game_state['players'])} jogadores responderam. Avançando...")
            advance_question()

# --- Inicialização ---
if __name__ == '__main__':
    logger.info("Iniciando servidor Flask-SocketIO para Quiz Vocacional HTML...")
    socketio.run(app, debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5001))
#teste commit
