// Variáveis globais de estado e configuração
let socket = null;
let currentQuizData = {
    question: null,
    questionNumber: 0,
    totalQuestions: 0,
    timeLimit: 20,
    mySid: null,
    myNickname: '',
    currentScore: 0,
    activePlayers: []
};
let questionTimerInterval = null;
let selectedOptionId = null;

// Elementos da UI
const nicknameInput = document.getElementById('nickname');
const joinQuizBtn = document.getElementById('joinQuizBtn');
// const startQuizBtn = document.getElementById('startQuizBtn'); // Removido
const statusMessage = document.getElementById('statusMessage');

const quizArea = document.getElementById('quizArea');
const nicknameDisplay = document.getElementById('nicknameDisplay');
const scoreDisplay = document.getElementById('scoreDisplay');
const questionNumberDisplay = document.getElementById('questionNumber');
const totalQuestionsDisplay = document.getElementById('totalQuestions');
const activePlayersDisplay = document.getElementById('activePlayers');
const timerDisplay = document.getElementById('timerDisplay');
const questionText = document.getElementById('questionText');
const optionsContainer = document.getElementById('optionsContainer');
const feedbackText = document.getElementById('feedbackText');
const waitingScreen = document.getElementById('waitingScreen');
const waitingTitle = document.getElementById('waitingTitle');
const waitingMessage = document.getElementById('waitingMessage');

const userNicknameResult = document.getElementById('userNicknameResult');
const finalScoreDisplay = document.getElementById('finalScore');
const recommendationText = document.getElementById('recommendationText');
const rankingList = document.getElementById('rankingList');
const playAgainBtn = document.getElementById('playAgainBtn');

function connectSocket() {
    if (!socket || !socket.connected) {
        console.log('Tentando conectar ao servidor Socket.IO...');
        socket = io();
        setupSocketListeners();
    } else {
        console.log('Socket já conectado ou em processo de conexão.');
    }
}

function setupSocketListeners() {
    if (!socket) {
        console.error("!! ERRO CRÍTICO: Tentativa de configurar listeners sem objeto socket.");
        return;
    }

    socket.on('connect', () => {
        console.log('Socket.IO: Conectado ao servidor! SID:', socket.id);
        currentQuizData.mySid = socket.id;
        if (statusMessage) statusMessage.textContent = 'Conectado ao servidor!';
    });

    socket.on('disconnect', (reason) => {
        console.warn('Socket.IO: Desconectado do servidor:', reason);
        if (statusMessage) statusMessage.textContent = 'Desconectado. Verifique sua conexão.';
        if (quizArea && !document.getElementById('resultsArea')) {
            showWaitingScreen("Conexão perdida", "Tentando reconectar ao servidor...");
        }
    });

    socket.on('connect_error', (err) => {
        console.error('Socket.IO: Erro de conexão:', err);
        if (statusMessage) statusMessage.textContent = 'Falha ao conectar ao servidor.';
        if (quizArea && !document.getElementById('resultsArea')) {
            showWaitingScreen("Erro de Conexão", `Não foi possível conectar: ${err.message}. Recarregue.`);
        }
    });

    socket.on('join_ack', (data) => {
        console.log('Socket.IO: Evento "join_ack" recebido:', data);
        if (data.success) {
            currentQuizData.myNickname = data.nickname;
            currentQuizData.mySid = data.sid;
            // Não precisa mais mostrar o botão startQuizBtn
            // if (startQuizBtn) startQuizBtn.classList.remove('hidden'); 
            
            console.log("Redirecionando para /quiz após join_ack...");
            window.location.href = '/quiz';
        } else {
            if (statusMessage) statusMessage.textContent = data.error || 'Falha ao entrar no quiz.';
            if (joinQuizBtn) joinQuizBtn.disabled = false;
        }
    });

    socket.on('player_joined', (data) => {
        console.log('Socket.IO: Evento "player_joined":', data);
        currentQuizData.activePlayers = data.allPlayers || [];
        updatePlayerList();
    });

    socket.on('player_left', (data) => {
        console.log('Socket.IO: Evento "player_left":', data);
        currentQuizData.activePlayers = data.remainingPlayers || [];
        updatePlayerList();
    });
    
    socket.on('quiz_state_on_connect', (data) => {
        console.log('Socket.IO: Evento "quiz_state_on_connect":', data);
        if (window.location.pathname.includes('/quiz')) {
            hideWaitingScreen();
            currentQuizData.question = data.question;
            currentQuizData.questionNumber = data.questionNumber;
            currentQuizData.totalQuestions = data.totalQuestions;
            currentQuizData.timeLimit = data.timeLimit;
            currentQuizData.activePlayers = data.players || [];
            if (data.currentPlayer && data.currentPlayer.sid === currentQuizData.mySid) {
                currentQuizData.currentScore = data.currentPlayer.score || 0;
            }
            updateQuizUI();
            startClientTimer(data.timeLimit); 
        }
    });

    socket.on('quiz_started', (data) => {
        console.log('Socket.IO: Evento "quiz_started":', data);
        if (window.location.pathname.includes('/quiz')) {
            currentQuizData.currentScore = 0;
            if(scoreDisplay) scoreDisplay.textContent = '0';
            hideWaitingScreen();
            // A primeira pergunta deve vir com 'new_question' logo após 'quiz_started'
        } else if (window.location.pathname === '/' || window.location.pathname.endsWith('index.html')) {
             if(currentQuizData.myNickname) {
                console.log("Quiz começou, redirecionando da home para /quiz...");
                window.location.href = '/quiz';
             }
        }
    });

    socket.on('new_question', (data) => {
        console.log('Socket.IO: Evento "new_question":', data);
        if (!quizArea) return;
        hideWaitingScreen();
        selectedOptionId = null;
        currentQuizData.question = data.question;
        currentQuizData.questionNumber = data.questionNumber;
        currentQuizData.totalQuestions = data.totalQuestions;
        currentQuizData.timeLimit = data.timeLimit;
        updateQuizUI();
        startClientTimer(data.timeLimit);
    });

    socket.on('answer_feedback', (data) => {
        console.log('Socket.IO: Evento "answer_feedback":', data);
        if (!quizArea) return;
        currentQuizData.currentScore = data.currentScore;
        if(scoreDisplay) scoreDisplay.textContent = currentQuizData.currentScore;

        const buttons = optionsContainer.querySelectorAll('button.quiz-option-button');
        buttons.forEach(button => {
            button.disabled = true;
            button.classList.remove('correct', 'incorrect', 'selected');
            if (button.dataset.optionId === data.correctOptionId) button.classList.add('correct');
            if (button.dataset.optionId === data.selectedOptionId && !data.isCorrect) button.classList.add('incorrect');
        });
        if(feedbackText) feedbackText.textContent = data.isCorrect ? `Correto! +${data.pointsEarned} pontos` : 'Incorreto!';
        if(feedbackText) feedbackText.className = data.isCorrect ? 'text-emerald-400 font-medium' : 'text-red-400 font-medium';
    });

    socket.on('scores_update', (data) => {
        console.log('Socket.IO: Evento "scores_update":', data.scores);
        if (data.allPlayers) {
            currentQuizData.activePlayers = data.allPlayers;
            updatePlayerList();
        }
    });

    socket.on('time_up', (data) => {
        console.log('Socket.IO: Evento "time_up" para questão:', data.questionId);
        if (!quizArea) return;
        if (currentQuizData.question && currentQuizData.question.id === data.questionId) {
            if(feedbackText) feedbackText.textContent = 'Tempo esgotado!';
            if(feedbackText) feedbackText.className = 'text-amber-400 font-medium';
            const buttons = optionsContainer.querySelectorAll('button.quiz-option-button');
            buttons.forEach(button => {
                button.disabled = true;
                button.classList.remove('selected');
                if (button.dataset.optionId === currentQuizData.question.correctOptionId) button.classList.add('correct');
            });
        }
        if (questionTimerInterval) clearInterval(questionTimerInterval);
    });

    socket.on('quiz_ended', (data) => {
        console.log('Socket.IO: Evento "quiz_ended":', data);
        sessionStorage.setItem('quizResults', JSON.stringify(data.results));
        sessionStorage.setItem('myNickname', currentQuizData.myNickname);
        sessionStorage.setItem('mySid', currentQuizData.mySid);

        if (window.location.pathname.includes('/quiz')) {
            showWaitingScreen("Quiz Finalizado!", "Calculando seus resultados...");
            setTimeout(() => {
                window.location.href = '/results';
            }, 1500);
        } else {
            if (window.location.pathname.includes('/results')) {
                populateResultsPage();
            }
        }
    });

    socket.on('error_message', (data) => {
        console.error('Socket.IO: Mensagem de erro do Servidor:', data.message);
        if (statusMessage) statusMessage.textContent = `Erro: ${data.message}`;
        else if (feedbackText) feedbackText.textContent = `Erro: ${data.message}`;
        else alert(`Erro do servidor: ${data.message}`);
    });
}

function setupIndexPage() {
    console.log("setupIndexPage: Iniciando configuração da página inicial.");
    // Removida referência a startQuizBtn
    if (!joinQuizBtn || !nicknameInput || !statusMessage) {
        console.error("setupIndexPage: Elementos essenciais não encontrados. Abortando setup.");
        return;
    }
    console.log("setupIndexPage: Todos os elementos da UI da home foram encontrados.");

    connectSocket();

    const savedNickname = localStorage.getItem('quizNickname');
    if (savedNickname) {
        nicknameInput.value = savedNickname;
        console.log(`setupIndexPage: Nickname recuperado do localStorage: ${savedNickname}`);
    }

    joinQuizBtn.addEventListener('click', () => {
        console.log("joinQuizBtn: Botão 'Entrar no Quiz' clicado.");
        const nick = nicknameInput.value.trim();
        console.log(`joinQuizBtn: Nickname digitado: '${nick}'`);

        if (!nick) {
            statusMessage.textContent = 'Por favor, insira um apelido.';
            console.warn("joinQuizBtn: Apelido vazio.");
            return;
        }
        if (!socket || !socket.connected) {
            statusMessage.textContent = 'Não conectado ao servidor. Tentando conectar...';
            console.warn("joinQuizBtn: Socket não conectado ou nulo. Chamando connectSocket().");
            connectSocket(); 
            setTimeout(() => {
                if (socket && socket.connected) {
                    console.log("joinQuizBtn: Socket conectado após tentativa. Emitindo join_quiz.");
                    emitJoinQuiz(nick);
                } else {
                    console.error("joinQuizBtn: Falha ao conectar socket mesmo após tentativa.");
                    statusMessage.textContent = 'Falha na conexão. Tente recarregar.';
                }
            }, 1000);
            return;
        }
        emitJoinQuiz(nick);
    });

    function emitJoinQuiz(nick) {
        console.log(`joinQuizBtn: Emitindo 'join_quiz' com nickname: ${nick}`);
        localStorage.setItem('quizNickname', nick);
        currentQuizData.myNickname = nick;
        socket.emit('join_quiz', { nickname: nick });
        statusMessage.textContent = 'Entrando no quiz...';
        joinQuizBtn.disabled = true;
    }
    // Removido listener para startQuizBtn
    console.log("setupIndexPage: Configuração da página inicial concluída.");
}

function setupQuizPage() {
    console.log("setupQuizPage: Iniciando configuração.");
    if (!quizArea) {
        console.log("setupQuizPage: Elemento quizArea não encontrado. Abortando.");
        return;
    }
    connectSocket();

    if (!currentQuizData.myNickname) {
        currentQuizData.myNickname = localStorage.getItem('quizNickname') || 'Jogador Anônimo';
        console.log(`setupQuizPage: Nickname definido como: ${currentQuizData.myNickname}`);
    }
    if(nicknameDisplay) nicknameDisplay.textContent = `Jogador: ${currentQuizData.myNickname}`;
    if(scoreDisplay) scoreDisplay.textContent = currentQuizData.currentScore;

    // Se o quiz não estiver ativo no backend, o frontend mostrará a tela de espera.
    // O backend enviará 'quiz_started' e 'new_question' quando estiver pronto.
    if (!currentQuizData.question) { // Verifica se já tem uma questão (ex: reconexão)
        console.log("setupQuizPage: Sem questão atual. Mostrando tela de espera.");
        showWaitingScreen("Aguardando Quiz", "Esperando o início ou a próxima pergunta...");
    }
    console.log("setupQuizPage: Configuração concluída.");
}

// ... (resto do script.js permanece o mesmo: updateQuizUI, handleOptionClick, etc.) ...
function updateQuizUI() {
    console.log("updateQuizUI: Atualizando UI do quiz.");
    if (!currentQuizData.question || !quizArea) {
        console.warn("updateQuizUI: Sem dados da questão ou não está na página do quiz.");
        if (quizArea && !currentQuizData.quiz_active && currentQuizData.questionNumber === 0) {
             showWaitingScreen("Aguardando Início", "O quiz ainda não começou ou está aguardando jogadores.");
        }
        return;
    }

    if(questionText) questionText.textContent = currentQuizData.question.text;
    if(questionNumberDisplay) questionNumberDisplay.textContent = currentQuizData.questionNumber;
    if(totalQuestionsDisplay) totalQuestionsDisplay.textContent = currentQuizData.totalQuestions;
    if(feedbackText) feedbackText.textContent = '';
    if(feedbackText) feedbackText.className = 'font-medium';

    if(optionsContainer) optionsContainer.innerHTML = '';
    currentQuizData.question.options.forEach(option => {
        const button = document.createElement('button');
        button.textContent = option.text;
        button.className = 'quiz-option-button w-full p-3 md:p-4 text-left rounded-lg bg-slate-700 hover:bg-sky-600 border-2 border-slate-600 hover:border-sky-500 text-slate-200 font-medium transition-all duration-200 ease-in-out shadow-md';
        button.dataset.optionId = option.id;
        button.addEventListener('click', handleOptionClick);
        if(optionsContainer) optionsContainer.appendChild(button);
    });
    updatePlayerList();
    console.log("updateQuizUI: UI do quiz atualizada.");
}

function handleOptionClick(event) {
    console.log("handleOptionClick: Opção clicada.");
    if (!socket || !socket.connected || !currentQuizData.question || selectedOptionId) {
        console.warn("handleOptionClick: Condições não atendidas para processar clique (socket, questão, ou já selecionado).");
        return;
    }

    selectedOptionId = event.target.dataset.optionId;
    console.log(`handleOptionClick: Opção selecionada: ${selectedOptionId} para questão ${currentQuizData.question.id}`);

    const buttons = optionsContainer.querySelectorAll('button.quiz-option-button');
    buttons.forEach(btn => {
        btn.disabled = true;
        if(btn.dataset.optionId === selectedOptionId) {
            btn.classList.add('ring-2', 'ring-offset-2', 'ring-offset-slate-800', 'ring-amber-400');
        }
    });

    socket.emit('submit_answer', {
        questionId: currentQuizData.question.id,
        selectedOptionId: selectedOptionId
    });
    if (questionTimerInterval) clearInterval(questionTimerInterval);
}

function startClientTimer(duration) {
    console.log(`startClientTimer: Iniciando timer de ${duration}s.`);
    if (questionTimerInterval) clearInterval(questionTimerInterval);
    let timeLeft = duration;
    if(timerDisplay) timerDisplay.textContent = formatTime(timeLeft);
    if(timerDisplay) {
        timerDisplay.classList.remove('text-orange-400', 'animate-pulse');
        timerDisplay.classList.add('text-red-400');
    }

    questionTimerInterval = setInterval(() => {
        timeLeft--;
        if(timerDisplay) timerDisplay.textContent = formatTime(timeLeft);
        if (timeLeft <= 0) {
            clearInterval(questionTimerInterval);
            if(timerDisplay) timerDisplay.textContent = "00:00";
            console.log("startClientTimer: Timer chegou a zero.");
        }
        if (timeLeft <= 5 && timeLeft > 0) {
            if(timerDisplay) {
                timerDisplay.classList.replace('text-red-400', 'text-orange-400');
                timerDisplay.classList.add('animate-pulse');
            }
        } else if (timeLeft > 5) {
             if(timerDisplay) {
                timerDisplay.classList.replace('text-orange-400', 'text-red-400');
                timerDisplay.classList.remove('animate-pulse');
            }
        }
    }, 1000);
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
}

function updatePlayerList() {
    if (activePlayersDisplay) {
        activePlayersDisplay.textContent = currentQuizData.activePlayers.join(', ') || 'Nenhum';
    }
}

function showWaitingScreen(title, message) {
    if (waitingScreen && waitingTitle && waitingMessage) {
        waitingTitle.textContent = title;
        waitingMessage.textContent = message;
        waitingScreen.classList.remove('hidden');
        waitingScreen.classList.add('flex');
    }
}

function hideWaitingScreen() {
    if (waitingScreen) {
        waitingScreen.classList.add('hidden');
        waitingScreen.classList.remove('flex');
    }
}

function setupResultsPage() {
    console.log("setupResultsPage: Iniciando configuração.");
    if (!finalScoreDisplay) {
        console.log("setupResultsPage: Elemento finalScoreDisplay não encontrado. Abortando.");
        return;
    }
    connectSocket();
    populateResultsPage();

    if(playAgainBtn) {
        playAgainBtn.addEventListener('click', () => {
            console.log("playAgainBtn: Clicado.");
            sessionStorage.removeItem('quizResults');
            sessionStorage.removeItem('myNickname');
            sessionStorage.removeItem('mySid');
            window.location.href = '/';
        });
    }
    console.log("setupResultsPage: Configuração concluída.");
}

function populateResultsPage() {
    console.log("populateResultsPage: Preenchendo dados dos resultados.");
    const resultsDataString = sessionStorage.getItem('quizResults');
    const userNick = sessionStorage.getItem('myNickname') || 'Jogador';
    const mySidSession = sessionStorage.getItem('mySid');

    if(userNicknameResult) userNicknameResult.textContent = userNick;

    if (resultsDataString) {
        const allResults = JSON.parse(resultsDataString);
        const myResult = allResults.find(r => r.sid === mySidSession || r.nickname === userNick);

        if (myResult) {
            if(finalScoreDisplay) finalScoreDisplay.textContent = myResult.score;
            if(recommendationText) recommendationText.textContent = myResult.recommendation;
        } else {
            console.warn("populateResultsPage: Resultado do jogador atual não encontrado na lista de resultados.");
            if(finalScoreDisplay) finalScoreDisplay.textContent = '-';
            if(recommendationText) recommendationText.textContent = 'Seus resultados não foram encontrados. Tente jogar novamente.';
        }

        if(rankingList) {
            rankingList.innerHTML = '';
            if (allResults.length > 0) {
                allResults.forEach((player, index) => {
                    const li = document.createElement('li');
                    li.className = `flex justify-between items-center p-3 rounded-md ${player.sid === mySidSession || player.nickname === userNick ? 'bg-sky-600/70' : 'bg-slate-600/50'}`;
                    li.innerHTML = `
                        <span class="font-semibold">${index + 1}. ${player.nickname}</span>
                        <span class="text-amber-400 font-bold">${player.score} pts</span>
                    `;
                    rankingList.appendChild(li);
                });
            } else {
                rankingList.innerHTML = '<p class="text-slate-400">Nenhum resultado no ranking.</p>';
            }
        }
    } else {
        console.warn("populateResultsPage: Nenhum dado de resultado encontrado no sessionStorage.");
        if(recommendationText) recommendationText.textContent = 'Não foi possível carregar os resultados.';
    }
    console.log("populateResultsPage: Preenchimento concluído.");
}

document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    console.log("DOM Carregado. Path:", path);

    if (path === '/' || path.endsWith('index.html') || path.endsWith('index')) {
        console.log("Configurando página inicial...");
        setupIndexPage();
    } else if (path.includes('/quiz')) {
        console.log("Configurando página do quiz...");
        setupQuizPage();
    } else if (path.includes('/results')) {
        console.log("Configurando página de resultados...");
        setupResultsPage();
    }
});
