// Variáveis globais de estado e configuração
let socket = null;
let currentRoomData = {
    roomPin: null,
    mySid: null,
    myNickname: '',
    isHost: false,
    players: [],
    quizActive: false,
    currentQuestion: null,
    questionNumber: 0,
    totalQuestions: 0,
    timeLimit: 20,
    currentScore: 0,
};
let questionTimerInterval = null;
let selectedOptionId = null;

// --- Seletores de Elementos (agrupados por página) ---
function getIndexPageElements() {
    return {
        nicknameInput: document.getElementById('nickname'),
        createRoomBtn: document.getElementById('createRoomBtn'),
        roomPinInput: document.getElementById('roomPinInput'),
        joinRoomBtn: document.getElementById('joinRoomBtn'),
        statusMessage: document.getElementById('statusMessage'),
    };
}

function getLobbyPageElements() {
    return {
        roomPinDisplay: document.getElementById('roomPinDisplay'),
        copyPinBtn: document.getElementById('copyPinBtn'),
        playerCount: document.getElementById('playerCount'),
        playerListLobby: document.getElementById('playerListLobby'),
        hostControls: document.getElementById('hostControls'),
        startQuizForRoomBtn: document.getElementById('startQuizForRoomBtn'),
        playerWaitingMessage: document.getElementById('playerWaitingMessage'),
        lobbyStatusMessage: document.getElementById('lobbyStatusMessage'),
    };
}

function getQuizPageElements() {
    return {
        quizArea: document.getElementById('quizArea'),
        nicknameDisplay: document.getElementById('nicknameDisplay'),
        scoreDisplay: document.getElementById('scoreDisplay'),
        questionNumberDisplay: document.getElementById('questionNumber'),
        totalQuestionsDisplay: document.getElementById('totalQuestions'),
        activePlayersDisplay: document.getElementById('activePlayers'), // Para a lista de jogadores no quiz
        timerDisplay: document.getElementById('timerDisplay'),
        questionText: document.getElementById('questionText'),
        optionsContainer: document.getElementById('optionsContainer'),
        feedbackText: document.getElementById('feedbackText'),
        waitingScreen: document.getElementById('waitingScreen'), // Reutilizado
        waitingTitle: document.getElementById('waitingTitle'),
        waitingMessage: document.getElementById('waitingMessage'),
    };
}

function getResultsPageElements() {
    return {
        userNicknameResult: document.getElementById('userNicknameResult'),
        finalScoreDisplay: document.getElementById('finalScore'),
        recommendationText: document.getElementById('recommendationText'),
        rankingList: document.getElementById('rankingList'),
        playAgainBtn: document.getElementById('playAgainBtn'),
    };
}


// --- Conexão Socket.IO e Lógica Geral ---
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
    if (!socket) { console.error("!! ERRO CRÍTICO: Socket nulo em setupSocketListeners."); return; }

    socket.on('connect', () => {
        console.log('Socket.IO: Conectado! SID:', socket.id);
        currentRoomData.mySid = socket.id;
        // Tenta recuperar estado da sala se já estava em uma (ex: refresh)
        const storedRoomPin = sessionStorage.getItem('currentRoomPin');
        const storedNickname = localStorage.getItem('quizNickname');
        if (storedRoomPin && storedNickname) {
            console.log(`Recuperando sala ${storedRoomPin} para ${storedNickname} após conexão.`);
            // Tenta re-entrar na sala. O backend deve lidar com isso graciosamente.
            // O evento 'join_room_pin' é mais apropriado para isso.
            // Se estiver na página de lobby ou quiz, o setup da página tentará re-entrar.
        }
    });

    socket.on('disconnect', (reason) => {
        console.warn('Socket.IO: Desconectado:', reason);
        const ui = getQuizPageElements(); // Tenta pegar elementos do quiz
        if (ui.quizArea && window.location.pathname.includes('/quiz')) {
            showWaitingScreen("Conexão perdida", "Tentando reconectar...", ui);
        } else if (getLobbyPageElements().roomPinDisplay && window.location.pathname.includes('/lobby')) {
             const lobbyUI = getLobbyPageElements();
             if(lobbyUI.lobbyStatusMessage) lobbyUI.lobbyStatusMessage.textContent = "Desconectado. Verifique sua conexão.";
        } else {
            const indexUI = getIndexPageElements();
            if(indexUI.statusMessage) indexUI.statusMessage.textContent = "Desconectado.";
        }
    });

    socket.on('connect_error', (err) => {
        console.error('Socket.IO: Erro de conexão:', err);
        // Lógica similar ao disconnect para exibir erro na UI correta
    });

    // --- Listeners específicos das Salas ---
    socket.on('room_created', (data) => {
        console.log('Socket.IO: Evento "room_created":', data);
        if (data.roomPin) {
            currentRoomData.roomPin = data.roomPin;
            currentRoomData.myNickname = data.nickname;
            currentRoomData.isHost = data.isHost;
            currentRoomData.players = data.players || [data.nickname];
            sessionStorage.setItem('currentRoomPin', data.roomPin);
            sessionStorage.setItem('isHost', data.isHost);
            localStorage.setItem('quizNickname', data.nickname); // Salva para persistência
            console.log(`Redirecionando para /lobby para a sala ${data.roomPin}`);
            window.location.href = '/lobby';
        } else {
            const indexUI = getIndexPageElements();
            if(indexUI.statusMessage) indexUI.statusMessage.textContent = "Erro ao criar sala.";
        }
    });

    socket.on('room_joined', (data) => {
        console.log('Socket.IO: Evento "room_joined":', data);
        currentRoomData.roomPin = data.roomPin;
        currentRoomData.myNickname = data.nickname; // Nickname confirmado pelo backend
        currentRoomData.isHost = data.isHost;
        currentRoomData.players = data.players || [];
        sessionStorage.setItem('currentRoomPin', data.roomPin);
        sessionStorage.setItem('isHost', data.isHost);
        localStorage.setItem('quizNickname', data.nickname);

        if (window.location.pathname.includes('/index') || window.location.pathname === '/') {
            console.log(`Redirecionando para /lobby para a sala ${data.roomPin} após join.`);
            window.location.href = '/lobby';
        } else if (window.location.pathname.includes('/lobby')) {
            console.log("Atualizando lobby após 'room_joined'.");
            updateLobbyUI(); // Atualiza a UI do lobby se já estiver lá
        }
        if(data.quizActive && !currentRoomData.isHost){ // Se entrei numa sala com quiz ativo
            console.log("Quiz já ativo na sala, redirecionando para /quiz");
            window.location.href = '/quiz';
        }

    });
    
    socket.on('player_joined_room', (data) => { // Alguém (outro jogador) entrou na sala
        console.log('Socket.IO: Evento "player_joined_room":', data);
        if (currentRoomData.roomPin === data.roomPin) {
            currentRoomData.players = data.players || [];
            if (window.location.pathname.includes('/lobby')) {
                updateLobbyUI();
            } else if (window.location.pathname.includes('/quiz')) {
                const quizUI = getQuizPageElements();
                updatePlayerListQuiz(quizUI); // Atualiza lista de jogadores na tela do quiz
            }
        }
    });

    socket.on('player_left', (data) => {
        console.log('Socket.IO: Evento "player_left":', data);
        if (currentRoomData.roomPin === data.roomPin) {
            currentRoomData.players = data.remainingPlayers || [];
            if (window.location.pathname.includes('/lobby')) {
                updateLobbyUI();
            } else if (window.location.pathname.includes('/quiz')) {
                 const quizUI = getQuizPageElements();
                 updatePlayerListQuiz(quizUI);
            }
        }
    });
    
    socket.on('host_left', (data) => {
        console.log('Socket.IO: Evento "host_left":', data);
        if (currentRoomData.roomPin === data.roomPin) {
            currentRoomData.isHost = false; // O host original saiu
            sessionStorage.setItem('isHost', 'false');
            const lobbyUI = getLobbyPageElements();
            if (lobbyUI.lobbyStatusMessage) {
                lobbyUI.lobbyStatusMessage.textContent = "O líder da sala saiu. O quiz não pode ser iniciado.";
            }
            if (lobbyUI.hostControls) lobbyUI.hostControls.classList.add('hidden');
            if (lobbyUI.playerWaitingMessage) lobbyUI.playerWaitingMessage.textContent = "O líder saiu. Aguardando um novo líder ou ação.";
        }
    });

    socket.on('room_error', (data) => {
        console.error('Socket.IO: Erro de Sala:', data.message);
        const path = window.location.pathname;
        if (path.includes('/lobby')) {
            const ui = getLobbyPageElements();
            if(ui.lobbyStatusMessage) ui.lobbyStatusMessage.textContent = `Erro: ${data.message}`;
        } else {
            const ui = getIndexPageElements();
            if(ui.statusMessage) ui.statusMessage.textContent = `Erro: ${data.message}`;
        }
    });

    // --- Listeners do Quiz (adaptados para salas) ---
    socket.on('quiz_started', (data) => {
        console.log('Socket.IO: Evento "quiz_started":', data);
        if (currentRoomData.roomPin === data.roomPin) {
            currentRoomData.quizActive = true;
            currentRoomData.currentScore = 0; // Reseta score no início do quiz
            if (window.location.pathname.includes('/lobby')) {
                console.log("Quiz iniciado, redirecionando do lobby para /quiz");
                window.location.href = '/quiz';
            } else if (window.location.pathname.includes('/quiz')) {
                const ui = getQuizPageElements();
                if(ui.scoreDisplay) ui.scoreDisplay.textContent = '0';
                hideWaitingScreen(ui);
            }
        }
    });

    socket.on('new_question', (data) => {
        console.log('Socket.IO: Evento "new_question":', data);
        // Não precisa verificar roomPin aqui, pois o backend emite para a sala correta
        const ui = getQuizPageElements();
        if (!ui.quizArea) return; 
        hideWaitingScreen(ui);
        selectedOptionId = null;
        currentRoomData.currentQuestion = data.question;
        currentRoomData.questionNumber = data.questionNumber;
        currentRoomData.totalQuestions = data.totalQuestions;
        currentRoomData.timeLimit = data.timeLimit;
        updateQuizUI(ui);
        startClientTimer(data.timeLimit, ui);
    });

    socket.on('answer_feedback', (data) => {
        console.log('Socket.IO: Evento "answer_feedback":', data);
        const ui = getQuizPageElements();
        if (!ui.quizArea) return;
        currentRoomData.currentScore = data.currentScore;
        if(ui.scoreDisplay) ui.scoreDisplay.textContent = currentRoomData.currentScore;

        const buttons = ui.optionsContainer.querySelectorAll('button.quiz-option-button');
        buttons.forEach(button => {
            button.disabled = true;
            button.classList.remove('correct', 'incorrect', 'selected'); // Limpa classes de estado
            if (button.dataset.optionId === data.correctOptionId) button.classList.add('correct');
            if (button.dataset.optionId === data.selectedOptionId && !data.isCorrect) button.classList.add('incorrect');
        });
        if(ui.feedbackText) ui.feedbackText.textContent = data.isCorrect ? `Correto! +${data.pointsEarned} pontos` : 'Incorreto!';
        if(ui.feedbackText) ui.feedbackText.className = `font-medium ${data.isCorrect ? 'text-emerald-400' : 'text-red-400'}`;
    });
    
    socket.on('scores_update', (data) => { // Recebe scores de todos na sala
        console.log('Socket.IO: Evento "scores_update":', data);
        // Poderia ser usado para um ranking em tempo real na tela do quiz, se desejado.
        // Por enquanto, a lista de jogadores é atualizada por 'player_joined_room' e 'player_left'.
    });

    socket.on('time_up', (data) => {
        console.log('Socket.IO: Evento "time_up" para questão:', data.questionId);
        const ui = getQuizPageElements();
        if (!ui.quizArea) return;
        if (currentRoomData.currentQuestion && currentRoomData.currentQuestion.id === data.questionId) {
            if(ui.feedbackText) ui.feedbackText.textContent = 'Tempo esgotado!';
            if(ui.feedbackText) ui.feedbackText.className = 'font-medium text-amber-400';
            const buttons = ui.optionsContainer.querySelectorAll('button.quiz-option-button');
            buttons.forEach(button => {
                button.disabled = true;
                button.classList.remove('selected');
                if (currentRoomData.currentQuestion && button.dataset.optionId === currentRoomData.currentQuestion.correctOptionId) {
                    button.classList.add('correct');
                }
            });
        }
        if (questionTimerInterval) clearInterval(questionTimerInterval);
    });

    socket.on('quiz_ended', (data) => {
        console.log('Socket.IO: Evento "quiz_ended":', data);
        if (currentRoomData.roomPin === data.roomPin) {
            sessionStorage.setItem('quizResults_room_' + data.roomPin, JSON.stringify(data.results));
            sessionStorage.setItem('myNickname', currentRoomData.myNickname);
            sessionStorage.setItem('mySid', currentRoomData.mySid);
            sessionStorage.setItem('lastRoomPinForResults', data.roomPin); // Para saber qual resultado carregar

            if (window.location.pathname.includes('/quiz') || window.location.pathname.includes('/lobby')) {
                const ui = getQuizPageElements() || getLobbyPageElements();
                showWaitingScreen("Quiz Finalizado!", "Calculando seus resultados...", ui);
                setTimeout(() => {
                    window.location.href = '/results';
                }, 1500);
            } else if (window.location.pathname.includes('/results')) {
                populateResultsPage(); // Se já estiver na página, apenas atualiza
            }
        }
    });
}


// --- Lógica da Página Inicial (index.html) ---
function setupIndexPage() {
    const ui = getIndexPageElements();
    if (!ui.createRoomBtn || !ui.nicknameInput || !ui.joinRoomBtn || !ui.roomPinInput || !ui.statusMessage) {
        console.error("IndexPage: Elementos essenciais não encontrados.");
        return;
    }
    console.log("IndexPage: Configurando...");
    connectSocket();

    const savedNickname = localStorage.getItem('quizNickname');
    if (savedNickname) ui.nicknameInput.value = savedNickname;

    ui.createRoomBtn.addEventListener('click', () => {
        console.log("IndexPage: Botão 'Criar Sala' clicado.");
        const nick = ui.nicknameInput.value.trim();
        if (!nick) { ui.statusMessage.textContent = 'Por favor, insira um apelido para criar a sala.'; return; }
        if (socket && socket.connected) {
            localStorage.setItem('quizNickname', nick);
            socket.emit('create_room', { nickname: nick });
            ui.statusMessage.textContent = 'Criando sala...';
        } else {
            ui.statusMessage.textContent = 'Não conectado. Tentando conectar...';
            connectSocket();
        }
    });

    ui.joinRoomBtn.addEventListener('click', () => {
        console.log("IndexPage: Botão 'Entrar com PIN' clicado.");
        const nick = ui.nicknameInput.value.trim();
        const pin = ui.roomPinInput.value.trim().toUpperCase();
        if (!nick) { ui.statusMessage.textContent = 'Insira seu apelido.'; return; }
        if (!pin) { ui.statusMessage.textContent = 'Insira o PIN da sala.'; return; }
        if (socket && socket.connected) {
            localStorage.setItem('quizNickname', nick);
            socket.emit('join_room_pin', { nickname: nick, roomPin: pin });
            ui.statusMessage.textContent = `Entrando na sala ${pin}...`;
        } else {
            ui.statusMessage.textContent = 'Não conectado. Tentando conectar...';
            connectSocket();
        }
    });
}

// --- Lógica da Página de Lobby (lobby.html) ---
function setupLobbyPage() {
    const ui = getLobbyPageElements();
    if (!ui.roomPinDisplay || !ui.playerListLobby) {
        console.error("LobbyPage: Elementos essenciais não encontrados.");
        // Tenta redirecionar para home se não tiver dados da sala
        if (!sessionStorage.getItem('currentRoomPin')) window.location.href = '/';
        return;
    }
    console.log("LobbyPage: Configurando...");
    connectSocket(); // Garante conexão

    currentRoomData.roomPin = sessionStorage.getItem('currentRoomPin');
    currentRoomData.isHost = sessionStorage.getItem('isHost') === 'true';
    currentRoomData.myNickname = localStorage.getItem('quizNickname') || 'Jogador';

    if (!currentRoomData.roomPin) {
        console.warn("LobbyPage: Sem PIN de sala no sessionStorage. Redirecionando para home.");
        window.location.href = '/';
        return;
    }

    ui.roomPinDisplay.textContent = currentRoomData.roomPin;
    if (ui.copyPinBtn) {
        ui.copyPinBtn.onclick = () => {
            navigator.clipboard.writeText(currentRoomData.roomPin).then(() => {
                ui.copyPinBtn.textContent = "Copiado!";
                setTimeout(() => { ui.copyPinBtn.textContent = "Copiar PIN"; }, 2000);
            }).catch(err => console.error('Falha ao copiar PIN:', err));
        };
    }


    if (currentRoomData.isHost) {
        if(ui.hostControls) ui.hostControls.classList.remove('hidden');
        if(ui.playerWaitingMessage) ui.playerWaitingMessage.classList.add('hidden');
        if(ui.startQuizForRoomBtn) {
            ui.startQuizForRoomBtn.addEventListener('click', () => {
                if (socket && socket.connected && currentRoomData.roomPin) {
                    console.log(`LobbyPage: Host iniciando quiz para sala ${currentRoomData.roomPin}`);
                    socket.emit('start_quiz_for_room', { roomPin: currentRoomData.roomPin });
                    if(ui.lobbyStatusMessage) ui.lobbyStatusMessage.textContent = "Iniciando quiz...";
                } else {
                     if(ui.lobbyStatusMessage) ui.lobbyStatusMessage.textContent = "Não conectado para iniciar.";
                }
            });
        }
    } else {
        if(ui.hostControls) ui.hostControls.classList.add('hidden');
        if(ui.playerWaitingMessage) ui.playerWaitingMessage.classList.remove('hidden');
    }
    // Solicita a lista de jogadores atual ao entrar no lobby ou se reconectar
    // O backend já envia 'player_joined_room' ou 'room_joined' com a lista.
    // Se precisar forçar um update, poderia emitir um evento 'get_room_details'
    // e o backend responderia com os jogadores. Por ora, confiamos nos eventos existentes.
    // Se currentRoomData.players estiver vazio, tentamos pegar do session storage (menos ideal)
    // ou esperamos o primeiro 'player_joined_room'.
    updateLobbyUI();
}

function updateLobbyUI() {
    const ui = getLobbyPageElements();
    if (!ui.playerListLobby || !ui.playerCount) return;

    ui.playerListLobby.innerHTML = ''; // Limpa lista
    if (currentRoomData.players && currentRoomData.players.length > 0) {
        currentRoomData.players.forEach(nick => {
            const li = document.createElement('li');
            li.className = 'p-2 bg-slate-600/50 rounded text-slate-200';
            li.textContent = nick;
            if (nick === currentRoomData.myNickname) {
                li.innerHTML += ' <span class="text-xs text-sky-400">(Você)</span>';
            }
            if (currentRoomData.isHost && nick === currentRoomData.myNickname) { // Assumindo que o primeiro a criar é o host e tem seu nick na lista
                 li.innerHTML += ' <span class="text-xs text-amber-400">(Líder)</span>';
            }
            ui.playerListLobby.appendChild(li);
        });
    } else {
        ui.playerListLobby.innerHTML = '<li class="text-slate-400 italic">Aguardando jogadores...</li>';
    }
    ui.playerCount.textContent = currentRoomData.players.length;
}


// --- Lógica da Página do Quiz (quiz.html) ---
function setupQuizPage() {
    const ui = getQuizPageElements();
    if (!ui.quizArea) { console.log("QuizPage: Elemento quizArea não encontrado."); return; }
    console.log("QuizPage: Configurando...");
    connectSocket();

    currentRoomData.roomPin = sessionStorage.getItem('currentRoomPin');
    currentRoomData.myNickname = localStorage.getItem('quizNickname') || 'Jogador';
    currentRoomData.isHost = sessionStorage.getItem('isHost') === 'true'; // Pode não ser relevante aqui

    if (!currentRoomData.roomPin) {
        console.warn("QuizPage: Sem PIN de sala. Redirecionando para home.");
        window.location.href = '/'; // Se não tem PIN, não deveria estar aqui
        return;
    }

    if(ui.nicknameDisplay) ui.nicknameDisplay.textContent = `Jogador: ${currentRoomData.myNickname}`;
    if(ui.scoreDisplay) ui.scoreDisplay.textContent = currentRoomData.currentScore;

    if (!currentRoomData.currentQuestion) { // Se não recebeu uma questão ainda
        showWaitingScreen("Aguardando Quiz", "Esperando a próxima pergunta...", ui);
    }
}

function updateQuizUI(ui) { // ui = getQuizPageElements()
    if (!currentRoomData.currentQuestion || !ui.quizArea) {
        console.warn("updateQuizUI: Sem dados da questão ou UI não encontrada.");
        if (ui.quizArea && !currentRoomData.quizActive && currentRoomData.questionNumber === 0) {
             showWaitingScreen("Aguardando Início", "O quiz ainda não começou.", ui);
        }
        return;
    }

    if(ui.questionText) ui.questionText.textContent = currentRoomData.currentQuestion.text;
    if(ui.questionNumberDisplay) ui.questionNumberDisplay.textContent = currentRoomData.questionNumber;
    if(ui.totalQuestionsDisplay) ui.totalQuestionsDisplay.textContent = currentRoomData.totalQuestions;
    if(ui.feedbackText) ui.feedbackText.textContent = '';
    if(ui.feedbackText) ui.feedbackText.className = 'font-medium';

    if(ui.optionsContainer) ui.optionsContainer.innerHTML = '';
    currentRoomData.currentQuestion.options.forEach(option => {
        const button = document.createElement('button');
        button.textContent = option.text;
        button.className = 'quiz-option-button w-full p-3 md:p-4 text-left rounded-lg bg-slate-700 hover:bg-sky-600 border-2 border-slate-600 hover:border-sky-500 text-slate-200 font-medium transition-all duration-200 ease-in-out shadow-md';
        button.dataset.optionId = option.id;
        button.addEventListener('click', handleOptionClick);
        if(ui.optionsContainer) ui.optionsContainer.appendChild(button);
    });
    updatePlayerListQuiz(ui); // Atualiza lista de jogadores na tela do quiz
}

function handleOptionClick(event) {
    if (!socket || !socket.connected || !currentRoomData.currentQuestion || selectedOptionId || !currentRoomData.roomPin) return;
    selectedOptionId = event.target.dataset.optionId;
    const ui = getQuizPageElements();
    const buttons = ui.optionsContainer.querySelectorAll('button.quiz-option-button');
    buttons.forEach(btn => {
        btn.disabled = true;
        if(btn.dataset.optionId === selectedOptionId) {
            btn.classList.add('ring-2', 'ring-offset-2', 'ring-offset-slate-800', 'ring-amber-400');
        }
    });
    socket.emit('submit_answer', {
        roomPin: currentRoomData.roomPin,
        questionId: currentRoomData.currentQuestion.id,
        selectedOptionId: selectedOptionId
    });
    if (questionTimerInterval) clearInterval(questionTimerInterval);
}

function startClientTimer(duration, ui) { // ui = getQuizPageElements()
    if (questionTimerInterval) clearInterval(questionTimerInterval);
    let timeLeft = duration;
    if(ui.timerDisplay) ui.timerDisplay.textContent = formatTime(timeLeft);
    if(ui.timerDisplay) {
        ui.timerDisplay.classList.remove('text-orange-400', 'animate-pulse');
        ui.timerDisplay.classList.add('text-red-400');
    }
    questionTimerInterval = setInterval(() => {
        timeLeft--;
        if(ui.timerDisplay) ui.timerDisplay.textContent = formatTime(timeLeft);
        if (timeLeft <= 0) {
            clearInterval(questionTimerInterval);
            if(ui.timerDisplay) ui.timerDisplay.textContent = "00:00";
        }
        if (timeLeft <= 5 && timeLeft > 0) {
            if(ui.timerDisplay) {
                ui.timerDisplay.classList.replace('text-red-400', 'text-orange-400');
                ui.timerDisplay.classList.add('animate-pulse');
            }
        } else if (timeLeft > 5) {
             if(ui.timerDisplay) {
                ui.timerDisplay.classList.replace('text-orange-400', 'text-red-400');
                ui.timerDisplay.classList.remove('animate-pulse');
            }
        }
    }, 1000);
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
}

function updatePlayerListQuiz(ui) { // ui = getQuizPageElements()
    if (ui.activePlayersDisplay) {
        // Mostra apenas a contagem para não poluir muito a tela do quiz
        ui.activePlayersDisplay.textContent = `${currentRoomData.players.length} jogador(es)`;
    }
}

function showWaitingScreen(title, message, uiElements) { // uiElements é opcional, para pegar waitingScreen
    const ws = uiElements?.waitingScreen || document.getElementById('waitingScreen');
    const wt = uiElements?.waitingTitle || document.getElementById('waitingTitle');
    const wm = uiElements?.waitingMessage || document.getElementById('waitingMessage');
    if (ws && wt && wm) {
        wt.textContent = title;
        wm.textContent = message;
        ws.classList.remove('hidden');
        ws.classList.add('flex');
    }
}

function hideWaitingScreen(uiElements) {
    const ws = uiElements?.waitingScreen || document.getElementById('waitingScreen');
    if (ws) {
        ws.classList.add('hidden');
        ws.classList.remove('flex');
    }
}

// --- Lógica da Página de Resultados (results.html) ---
function setupResultsPage() {
    const ui = getResultsPageElements();
    if (!ui.finalScoreDisplay) { console.log("ResultsPage: Elementos não encontrados."); return; }
    console.log("ResultsPage: Configurando...");
    connectSocket(); // Conecta para o caso de querer implementar "jogar novamente" sem refresh total
    populateResultsPage(ui);

    if(ui.playAgainBtn) {
        ui.playAgainBtn.addEventListener('click', () => {
            sessionStorage.removeItem('quizResults_room_' + sessionStorage.getItem('lastRoomPinForResults'));
            sessionStorage.removeItem('myNickname'); // Ou localStorage.removeItem('quizNickname')
            sessionStorage.removeItem('mySid');
            sessionStorage.removeItem('currentRoomPin');
            sessionStorage.removeItem('isHost');
            sessionStorage.removeItem('lastRoomPinForResults');
            window.location.href = '/';
        });
    }
}

function populateResultsPage(ui) { // ui = getResultsPageElements()
    const lastRoomPin = sessionStorage.getItem('lastRoomPinForResults');
    const resultsDataString = sessionStorage.getItem('quizResults_room_' + lastRoomPin);
    const userNick = localStorage.getItem('quizNickname') || 'Jogador'; // Usa localStorage para nickname
    const mySidSession = sessionStorage.getItem('mySid');

    if(ui.userNicknameResult) ui.userNicknameResult.textContent = userNick;

    if (resultsDataString) {
        const allResults = JSON.parse(resultsDataString);
        const myResult = allResults.find(r => r.sid === mySidSession); // Prioriza SID para resultado pessoal

        if (myResult) {
            if(ui.finalScoreDisplay) ui.finalScoreDisplay.textContent = myResult.score;
            if(ui.recommendationText) ui.recommendationText.textContent = myResult.recommendation;
        } else {
            if(ui.finalScoreDisplay) ui.finalScoreDisplay.textContent = '-';
            if(ui.recommendationText) ui.recommendationText.textContent = 'Seus resultados não foram encontrados.';
        }

        if(ui.rankingList) {
            ui.rankingList.innerHTML = '';
            if (allResults.length > 0) {
                allResults.forEach((player, index) => {
                    const li = document.createElement('li');
                    li.className = `flex justify-between items-center p-3 rounded-md ${player.sid === mySidSession ? 'bg-sky-600/70' : 'bg-slate-600/50'}`;
                    li.innerHTML = `
                        <span class="font-semibold">${index + 1}. ${player.nickname}</span>
                        <span class="text-amber-400 font-bold">${player.score} pts</span>
                    `;
                    ui.rankingList.appendChild(li);
                });
            } else {
                ui.rankingList.innerHTML = '<p class="text-slate-400">Nenhum resultado no ranking.</p>';
            }
        }
    } else {
        if(ui.recommendationText) ui.recommendationText.textContent = 'Não foi possível carregar os resultados.';
    }
}

// --- Inicialização da Página ---
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    console.log("DOM Carregado. Path:", path);

    if (path === '/' || path.endsWith('index.html') || path.endsWith('index')) {
        setupIndexPage();
    } else if (path.includes('/lobby')) {
        setupLobbyPage();
    } else if (path.includes('/quiz')) {
        setupQuizPage();
    } else if (path.includes('/results')) {
        setupResultsPage();
    }
});
