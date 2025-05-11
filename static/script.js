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

// --- Seletores de Elementos ---
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
        activePlayersDisplay: document.getElementById('activePlayers'),
        timerDisplay: document.getElementById('timerDisplay'),
        questionText: document.getElementById('questionText'),
        optionsContainer: document.getElementById('optionsContainer'),
        feedbackText: document.getElementById('feedbackText'),
        waitingScreen: document.getElementById('waitingScreen'),
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
        socket = io({
            reconnectionAttempts: 5, // Tenta reconectar 5 vezes
            reconnectionDelay: 2000  // Espera 2s entre tentativas
        });
        setupSocketListeners();
    } else {
        console.log('Socket já conectado ou em processo de conexão.');
    }
}

function setupSocketListeners() {
    if (!socket) { console.error("!! ERRO CRÍTICO: Socket nulo em setupSocketListeners."); return; }

    socket.on('connect', () => {
        console.log('Socket.IO: Conectado! SID:', socket.id);
        const oldSid = currentRoomData.mySid;
        currentRoomData.mySid = socket.id; 
        
        const path = window.location.pathname;
        const storedRoomPin = sessionStorage.getItem('currentRoomPin');
        const storedNickname = localStorage.getItem('quizNickname');

        if (storedRoomPin && storedNickname && (path.includes('/lobby') || path.includes('/quiz') || path.includes('/results'))) {
            console.log(`Socket.IO: Conectado/Reconectado (SID: ${socket.id}). Enviando 'rejoin_room_check' para sala ${storedRoomPin} como ${storedNickname}.`);
            socket.emit('rejoin_room_check', { 
                roomPin: storedRoomPin, 
                nickname: storedNickname,
            });
        } else {
            const indexUI = getIndexPageElements();
            if(indexUI.statusMessage && (path === '/' || path.endsWith('index.html'))) {
                 indexUI.statusMessage.textContent = 'Conectado ao servidor!';
            }
        }
    });

    socket.on('disconnect', (reason) => {
        console.warn('Socket.IO: Desconectado:', reason);
        const uiQuiz = getQuizPageElements(); 
        const uiLobby = getLobbyPageElements();
        const uiIndex = getIndexPageElements();

        if (uiQuiz.quizArea && window.location.pathname.includes('/quiz')) {
            showWaitingScreen("Conexão perdida", `Motivo: ${reason}. Tentando reconectar...`, uiQuiz);
        } else if (uiLobby.roomPinDisplay && window.location.pathname.includes('/lobby')) {
             if(uiLobby.lobbyStatusMessage) uiLobby.lobbyStatusMessage.textContent = "Desconectado: " + reason;
        } else if (uiIndex.statusMessage) {
            uiIndex.statusMessage.textContent = "Desconectado: " + reason;
        }
    });

    socket.on('connect_error', (err) => {
        console.error('Socket.IO: Erro de conexão:', err);
        // Adicionar feedback visual para o usuário
    });

    socket.on('room_created', (data) => {
        console.log('Socket.IO: Evento "room_created":', data);
        if (data.roomPin) {
            currentRoomData.roomPin = data.roomPin;
            currentRoomData.myNickname = data.nickname;
            currentRoomData.isHost = data.isHost;
            currentRoomData.players = data.players || [data.nickname];
            sessionStorage.setItem('currentRoomPin', data.roomPin);
            sessionStorage.setItem('isHost', data.isHost.toString()); 
            localStorage.setItem('quizNickname', data.nickname); 
            console.log(`Redirecionando para /lobby para a sala ${data.roomPin}`);
            window.location.href = '/lobby';
        } else {
            const indexUI = getIndexPageElements();
            if(indexUI.statusMessage) indexUI.statusMessage.textContent = "Erro ao criar sala.";
        }
    });

    socket.on('room_joined', (data) => {
        console.log('Socket.IO: Evento "room_joined" (confirmação para mim):', data);
        currentRoomData.roomPin = data.roomPin;
        currentRoomData.myNickname = data.nickname; 
        currentRoomData.isHost = data.isHost;
        currentRoomData.players = data.players || []; 
        sessionStorage.setItem('currentRoomPin', data.roomPin);
        sessionStorage.setItem('isHost', data.isHost.toString());
        localStorage.setItem('quizNickname', data.nickname); 

        const path = window.location.pathname;
        if (path.includes('/index') || path === '/') {
            console.log(`Redirecionando para /lobby para a sala ${data.roomPin} após join.`);
            window.location.href = '/lobby';
        } else if (path.includes('/lobby')) {
            console.log("Atualizando lobby após 'room_joined'.");
            updateLobbyUI(); 
            if(data.quizActive && !currentRoomData.isHost){ 
                console.log("Quiz já ativo na sala, e não sou host. Redirecionando do lobby para /quiz");
                window.location.href = '/quiz';
            }
        } else if (path.includes('/quiz')) {
            console.log("Recebido 'room_joined' na página do quiz. Atualizando dados.");
            updatePlayerListQuiz(getQuizPageElements());
            // Se o quiz estiver ativo, o backend enviará 'new_question' ou 'quiz_state_on_connect'
        }
    });
    
    socket.on('player_joined_room', (data) => { 
        console.log('Socket.IO: Evento "player_joined_room" (outro jogador entrou):', data);
        if (currentRoomData.roomPin === data.roomPin) {
            currentRoomData.players = data.players || [];
            if (window.location.pathname.includes('/lobby')) {
                updateLobbyUI();
            } else if (window.location.pathname.includes('/quiz')) {
                const quizUI = getQuizPageElements();
                updatePlayerListQuiz(quizUI); 
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
            currentRoomData.isHost = false; 
            sessionStorage.setItem('isHost', 'false');
            const lobbyUI = getLobbyPageElements();
            if (lobbyUI.lobbyStatusMessage) {
                lobbyUI.lobbyStatusMessage.textContent = "O líder da sala saiu. O quiz não pode ser iniciado.";
            }
            if (lobbyUI.hostControls) lobbyUI.hostControls.classList.add('hidden');
            if (lobbyUI.playerWaitingMessage) lobbyUI.playerWaitingMessage.textContent = "O líder saiu.";
        }
    });

    socket.on('room_error', (data) => {
        console.error('Socket.IO: Erro de Sala:', data.message);
        const path = window.location.pathname;
        const lobbyUI = getLobbyPageElements();
        const indexUI = getIndexPageElements();

        if (path.includes('/lobby') && lobbyUI.lobbyStatusMessage) {
            lobbyUI.lobbyStatusMessage.textContent = `Erro: ${data.message}`;
        } else if (indexUI.statusMessage) {
            indexUI.statusMessage.textContent = `Erro: ${data.message}`;
            if(indexUI.joinRoomBtn) indexUI.joinRoomBtn.disabled = false; // Reabilita botão de entrar
            if(indexUI.createRoomBtn) indexUI.createRoomBtn.disabled = false; // Reabilita botão de criar
        }
    });

    socket.on('room_not_found_on_rejoin', (data) => {
        console.warn(`Socket.IO: Evento 'room_not_found_on_rejoin' para sala ${data.roomPin}. Mensagem: ${data.message}`);
        alert(`A sala ${data.roomPin} não existe mais ou foi encerrada. Você será redirecionado para a página inicial.`);
        sessionStorage.removeItem('currentRoomPin');
        sessionStorage.removeItem('isHost');
        sessionStorage.removeItem('lastRoomPinForResults'); 
        
        const path = window.location.pathname;
        if (path.includes('/lobby') || path.includes('/quiz') || path.includes('/results')) { 
            window.location.href = '/';
        }
    });


    socket.on('quiz_started', (data) => {
        console.log('Socket.IO: Evento "quiz_started":', data);
        if (currentRoomData.roomPin === data.roomPin) {
            currentRoomData.quizActive = true;
            currentRoomData.currentScore = 0; 
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
        const ui = getQuizPageElements();
        if (!ui.quizArea) {
            console.warn("new_question recebido, mas não na página do quiz. Ignorando.");
            return;
        }
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
        // ... (mesma lógica de antes)
        console.log('Socket.IO: Evento "answer_feedback":', data);
        const ui = getQuizPageElements();
        if (!ui.quizArea) return;
        currentRoomData.currentScore = data.currentScore;
        if(ui.scoreDisplay) ui.scoreDisplay.textContent = currentRoomData.currentScore;

        const buttons = ui.optionsContainer.querySelectorAll('button.quiz-option-button');
        buttons.forEach(button => {
            button.disabled = true;
            button.classList.remove('correct', 'incorrect', 'selected'); 
            if (button.dataset.optionId === data.correctOptionId) button.classList.add('correct');
            if (button.dataset.optionId === data.selectedOptionId && !data.isCorrect) button.classList.add('incorrect');
        });
        if(ui.feedbackText) ui.feedbackText.textContent = data.isCorrect ? `Correto! +${data.pointsEarned} pontos` : 'Incorreto!';
        if(ui.feedbackText) ui.feedbackText.className = `font-medium ${data.isCorrect ? 'text-emerald-400' : 'text-red-400'}`;
    });
    
    socket.on('scores_update', (data) => { 
        console.log('Socket.IO: Evento "scores_update":', data);
    });

    socket.on('time_up', (data) => {
        // ... (mesma lógica de antes)
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
        // ... (mesma lógica de antes)
        console.log('Socket.IO: Evento "quiz_ended":', data);
        if (currentRoomData.roomPin === data.roomPin) {
            sessionStorage.setItem('quizResults_room_' + data.roomPin, JSON.stringify(data.results));
            sessionStorage.setItem('myNickname', currentRoomData.myNickname);
            sessionStorage.setItem('mySid', currentRoomData.mySid);
            sessionStorage.setItem('lastRoomPinForResults', data.roomPin); 

            if (window.location.pathname.includes('/quiz') || window.location.pathname.includes('/lobby')) {
                const ui = getQuizPageElements() || getLobbyPageElements();
                showWaitingScreen("Quiz Finalizado!", "Calculando seus resultados...", ui);
                setTimeout(() => {
                    window.location.href = '/results';
                }, 1500);
            } else if (window.location.pathname.includes('/results')) {
                populateResultsPage(); 
            }
        }
    });
}

// --- Lógica da Página Inicial (index.html) ---
function setupIndexPage() {
    // ... (mesma lógica de antes)
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
            currentRoomData.myNickname = nick; 
            console.log(`IndexPage: Emitindo 'create_room' com nickname: ${nick}`);
            socket.emit('create_room', { nickname: nick });
            ui.statusMessage.textContent = 'Criando sala...';
        } else {
            ui.statusMessage.textContent = 'Não conectado. Tentando conectar...';
            console.warn("IndexPage: createRoom - Socket não conectado. Tentando conectar...");
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
            currentRoomData.myNickname = nick; 
            console.log(`IndexPage: Emitindo 'join_room_pin' com nickname: ${nick}, PIN: ${pin}`);
            socket.emit('join_room_pin', { nickname: nick, roomPin: pin });
            ui.statusMessage.textContent = `Entrando na sala ${pin}...`;
        } else {
            ui.statusMessage.textContent = 'Não conectado. Tentando conectar...';
            console.warn("IndexPage: joinRoomBtn - Socket não conectado. Tentando conectar...");
            connectSocket();
        }
    });
}

// --- Lógica da Página de Lobby (lobby.html) ---
function setupLobbyPage() {
    // ... (mesma lógica de antes, com logs adicionados)
    const ui = getLobbyPageElements();
    if (!ui.roomPinDisplay || !ui.playerListLobby) {
        console.error("LobbyPage: Elementos essenciais não encontrados.");
        if (!sessionStorage.getItem('currentRoomPin')) {
            console.warn("LobbyPage: Sem PIN no sessionStorage, redirecionando para home.");
            window.location.href = '/';
        }
        return;
    }
    console.log("LobbyPage: Configurando...");
    connectSocket(); 

    currentRoomData.roomPin = sessionStorage.getItem('currentRoomPin');
    currentRoomData.isHost = sessionStorage.getItem('isHost') === 'true';
    currentRoomData.myNickname = localStorage.getItem('quizNickname') || 'Jogador Lobby';

    if (!currentRoomData.roomPin) {
        console.warn("LobbyPage: Sem PIN de sala no sessionStorage após tentativa de recuperação. Redirecionando para home.");
        window.location.href = '/';
        return;
    }
    console.log(`LobbyPage: Recuperado do sessionStorage - PIN: ${currentRoomData.roomPin}, É host? ${currentRoomData.isHost}, Nickname: ${currentRoomData.myNickname}`);

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
        console.log("LobbyPage: Usuário é o HOST. Mostrando controles do host.");
        if(ui.hostControls) ui.hostControls.classList.remove('hidden');
        if(ui.playerWaitingMessage) ui.playerWaitingMessage.classList.add('hidden');
        if(ui.startQuizForRoomBtn) {
            ui.startQuizForRoomBtn.addEventListener('click', () => {
                const pinToStart = currentRoomData.roomPin || sessionStorage.getItem('currentRoomPin'); 
                console.log(`LobbyPage: Botão 'Iniciar Quiz para Sala' clicado. PIN a ser usado: ${pinToStart}`);
                
                if (!pinToStart) {
                    console.error("LobbyPage: ERRO CRÍTICO - roomPin é nulo ou indefinido ao tentar iniciar o quiz!");
                    if(ui.lobbyStatusMessage) ui.lobbyStatusMessage.textContent = "Erro: PIN da sala não definido. Tente recriar a sala.";
                    return;
                }

                if (socket && socket.connected) {
                    console.log(`LobbyPage: Emitindo 'start_quiz_for_room' para sala ${pinToStart}`);
                    socket.emit('start_quiz_for_room', { roomPin: pinToStart });
                    if(ui.lobbyStatusMessage) ui.lobbyStatusMessage.textContent = "Iniciando quiz...";
                } else {
                     if(ui.lobbyStatusMessage) ui.lobbyStatusMessage.textContent = "Não conectado para iniciar.";
                     console.warn("LobbyPage: startQuizForRoomBtn - Socket não conectado.");
                }
            });
        } else {
            console.error("LobbyPage: Botão startQuizForRoomBtn NÃO encontrado no DOM!");
        }
    } else {
        console.log("LobbyPage: Usuário NÃO é o host. Escondendo controles do host.");
        if(ui.hostControls) ui.hostControls.classList.add('hidden');
        if(ui.playerWaitingMessage) ui.playerWaitingMessage.classList.remove('hidden');
    }
    updateLobbyUI(); 
}

// --- Restante do script.js (updateLobbyUI, setupQuizPage, etc.) ---
// ... (COPIE E COLE O RESTANTE DAS FUNÇÕES DA VERSÃO js_script_v8_rejoin_fix AQUI)
function updateLobbyUI() {
    const ui = getLobbyPageElements();
    if (!ui.playerListLobby || !ui.playerCount) {
        console.warn("updateLobbyUI: Elementos da lista de jogadores não encontrados.");
        return;
    }
    console.log("updateLobbyUI: Atualizando lista de jogadores no lobby:", currentRoomData.players);

    ui.playerListLobby.innerHTML = ''; 
    if (currentRoomData.players && currentRoomData.players.length > 0) {
        currentRoomData.players.forEach(nick => {
            const li = document.createElement('li');
            li.className = 'p-2 bg-slate-600/50 rounded text-slate-200 text-sm'; 
            li.textContent = nick;
            if (nick === currentRoomData.myNickname) {
                li.innerHTML += ' <span class="text-xs text-sky-400">(Você)</span>';
            }
            ui.playerListLobby.appendChild(li);
        });
    } else {
        ui.playerListLobby.innerHTML = '<li class="text-slate-400 italic">Aguardando jogadores...</li>';
    }
    ui.playerCount.textContent = currentRoomData.players.length;
}

function setupQuizPage() {
    const ui = getQuizPageElements();
    if (!ui.quizArea) { console.log("QuizPage: Elemento quizArea não encontrado."); return; }
    console.log("QuizPage: Configurando...");
    connectSocket();

    currentRoomData.roomPin = sessionStorage.getItem('currentRoomPin');
    currentRoomData.myNickname = localStorage.getItem('quizNickname') || 'Jogador';
    currentRoomData.isHost = sessionStorage.getItem('isHost') === 'true'; 

    if (!currentRoomData.roomPin) {
        console.warn("QuizPage: Sem PIN de sala. Redirecionando para home.");
        window.location.href = '/'; 
        return;
    }
    console.log(`QuizPage: Recuperado do sessionStorage/localStorage - PIN: ${currentRoomData.roomPin}, Nickname: ${currentRoomData.myNickname}`);


    if(ui.nicknameDisplay) ui.nicknameDisplay.textContent = `Jogador: ${currentRoomData.myNickname}`;
    if(ui.scoreDisplay) ui.scoreDisplay.textContent = currentRoomData.currentScore;

    if (!currentRoomData.currentQuestion) { 
        showWaitingScreen("Aguardando Quiz", "Esperando a próxima pergunta...", ui);
    } else {
        updateQuizUI(ui);
    }
}

function updateQuizUI(ui) { 
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
    updatePlayerListQuiz(ui); 
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

function startClientTimer(duration, ui) { 
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

function updatePlayerListQuiz(ui) { 
    if (ui.activePlayersDisplay) {
        ui.activePlayersDisplay.textContent = `${currentRoomData.players.length} jogador(es)`;
    }
}

function showWaitingScreen(title, message, uiElements) { 
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

function setupResultsPage() {
    const ui = getResultsPageElements();
    if (!ui.finalScoreDisplay) { console.log("ResultsPage: Elementos não encontrados."); return; }
    console.log("ResultsPage: Configurando...");
    connectSocket(); 
    populateResultsPage(ui);

    if(ui.playAgainBtn) {
        ui.playAgainBtn.addEventListener('click', () => {
            sessionStorage.removeItem('quizResults_room_' + sessionStorage.getItem('lastRoomPinForResults'));
            sessionStorage.removeItem('mySid');
            sessionStorage.removeItem('currentRoomPin');
            sessionStorage.removeItem('isHost');
            sessionStorage.removeItem('lastRoomPinForResults');
            window.location.href = '/';
        });
    }
}

function populateResultsPage(ui) { 
    const lastRoomPin = sessionStorage.getItem('lastRoomPinForResults');
    const resultsDataString = sessionStorage.getItem('quizResults_room_' + lastRoomPin);
    const userNick = localStorage.getItem('quizNickname') || 'Jogador'; 
    const mySidSession = sessionStorage.getItem('mySid');

    if(ui.userNicknameResult) ui.userNicknameResult.textContent = userNick;

    if (resultsDataString) {
        const allResults = JSON.parse(resultsDataString);
        const myResult = allResults.find(r => r.sid === mySidSession); 

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
