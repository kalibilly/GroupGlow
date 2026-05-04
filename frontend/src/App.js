import React, { useEffect, useMemo, useState, useRef } from 'react';
import { Routes, Route, useNavigate, useParams, useLocation, Link } from 'react-router-dom';
import axios from 'axios';
import StageScene from './components/StageScene';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api`;

const backendHostname = process.env.REACT_APP_API_URL.replace(/^https?:\/\//, '');
const WS_BASE = API_URL.startsWith('https')
  ? API_URL.replace(/^https/, 'wss') + '/ws/quiz'
  : API_URL.replace(/^http/, 'ws') + '/ws/quiz';

const getStoredParticipant = () => {
  try {
    return JSON.parse(localStorage.getItem('groupglow_participant')) || null;
  } catch {
    return null;
  }
};

const saveStoredParticipant = (data) => {
  localStorage.setItem('groupglow_participant', JSON.stringify(data));
};

const removeStoredParticipant = () => {
  localStorage.removeItem('groupglow_participant');
};

const getAuthToken = () => localStorage.getItem('groupglow_token');
const setAuthToken = (token) => localStorage.setItem('groupglow_token', token);
const clearAuthToken = () => localStorage.removeItem('groupglow_token');

const fetchApi = async (url, method = 'GET', token, body) => {
  const config = {
    method,
    url,
    headers: {
      'Content-Type': 'application/json',
    },
    data: body ? JSON.stringify(body) : undefined,
  };
  if (token) config.headers.Authorization = `Token ${token}`;
  const response = await axios(config);
  return response.data;
};

function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="logo" to="/">GroupGlow</Link>
        <Link className="host-link" to="/host/login">Host Portal</Link>
      </header>
      <div className="app-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/quiz/:roomCode" element={<QuizRoom />} />
          <Route path="/host/login" element={<HostLogin />} />
          <Route path="/host/dashboard" element={<HostDashboard />} />
          <Route path="/host/room/:roomCode" element={<HostRoom />} />
        </Routes>
      </div>
    </div>
  );
}

function HomePage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [roomCode, setRoomCode] = useState('');
  const [avatar, setAvatar] = useState('avatar1');
  const [error, setError] = useState('');

  const handleJoin = (event) => {
    event.preventDefault();
    if (!name || !roomCode) {
      setError('Enter your name and room code.');
      return;
    }
    saveStoredParticipant({ name, avatar, roomCode });
    navigate(`/quiz/${roomCode}`);
  };

  return (
    <div className="home-page card-grid">
      <div className="panel">
        <h1>Join a Quiz</h1>
        <p>Enter your display name and room code to join instantly.</p>
        <form onSubmit={handleJoin} className="form-stack">
          <label>
            Your Name
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Student name" />
          </label>
          <label>
            Room Code
            <input value={roomCode} onChange={(e) => setRoomCode(e.target.value)} placeholder="6-character code" />
          </label>
          <label>
            Avatar
            <select value={avatar} onChange={(e) => setAvatar(e.target.value)}>
              <option value="avatar1">Blue Explorer</option>
              <option value="avatar2">Red Pilot</option>
              <option value="avatar3">Green Maker</option>
              <option value="avatar4">Yellow Star</option>
              <option value="avatar5">Purple Sage</option>
            </select>
          </label>
          {error && <div className="error-box">{error}</div>}
          <button type="submit" className="primary-button">Join Room</button>
        </form>
      </div>
      <div className="panel info-card">
        <h2>How it works</h2>
        <ul>
          <li>Students join instantly with name and code.</li>
          <li>Host controls the quiz flow in real time.</li>
          <li>3D interface shows the question board and score panel.</li>
          <li>Live leaderboard updates for every participant.</li>
        </ul>
        <p>Need a room? Log in as a host and create a quiz with your own questions.</p>
      </div>
    </div>
  );
}

function QuizRoom() {
  const { roomCode } = useParams();
  const navigate = useNavigate();
  const stored = useMemo(getStoredParticipant, []);
  const [participant, setParticipant] = useState(stored);
  const [status, setStatus] = useState('connecting');
  const [question, setQuestion] = useState(null);
  const [selected, setSelected] = useState('');
  const [feedback, setFeedback] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [timer, setTimer] = useState(30);
  const [retryCount, setRetryCount] = useState(0);
  const socketRef = useRef(null);
  const reconnectRef = useRef(null);
  const timerRef = useRef(null);
  const manualCloseRef = useRef(false);

  const scheduleReconnect = () => {
    if (reconnectRef.current) {
      return;
    }

    const delay = Math.min(20000, 1000 * 2 ** retryCount);
    reconnectRef.current = window.setTimeout(() => {
      setRetryCount((count) => Math.min(5, count + 1));
      connectWebSocket();
      reconnectRef.current = null;
    }, delay);

    setStatus(`reconnecting in ${delay / 1000}s`);
  };

  const connectWebSocket = () => {
    if (!participant) {
      return;
    }

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus('connecting');
    const ws = new WebSocket(`${WS_BASE}/${roomCode}/`);
    socketRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      setRetryCount(0);
      ws.send(JSON.stringify({
        type: 'join',
        name: participant.name,
        avatar: participant.avatar,
        role: 'student',
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'join_success') {
        setStatus('ready');
      }
      if (data.type === 'quiz_started' || data.type === 'next_question') {
        setQuestion(data.question);
        setCurrentQuestionIndex(data.question_index + 1);
        setTotalQuestions(data.total_questions);
        setSelected('');
        setFeedback(null);
        setTimer(30);
      }
      if (data.type === 'answer_processed') {
        setFeedback({
          correct: data.is_correct,
          answer: data.correct_answer,
          points: data.points,
          score: data.new_score,
        });
      }
      if (data.type === 'leaderboard_updated' || data.type === 'leaderboard') {
        setLeaderboard(data.leaderboard);
      }
      if (data.type === 'quiz_ended') {
        setQuestion(null);
        setStatus('ended');
        setLeaderboard(data.final_leaderboard || leaderboard);
      }
      if (data.type === 'participant_joined') {
        setLeaderboard((prev) => [...prev]);
      }
    };

    ws.onclose = (event) => {
      if (!manualCloseRef.current) {
        setStatus('disconnected');
        scheduleReconnect();
      }
    };

    ws.onerror = () => {
      setStatus('error');
    };
  };

  useEffect(() => {
    if (!participant || participant.roomCode !== roomCode) {
      navigate('/');
      return;
    }

    manualCloseRef.current = false;
    connectWebSocket();

    return () => {
      manualCloseRef.current = true;
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.close();
      }
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
      }
      clearInterval(timerRef.current);
    };
  }, [navigate, participant, roomCode]);

  useEffect(() => {
    if (!question) return;
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setTimer((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [question]);

  const submitAnswer = () => {
    const ws = socketRef.current;
    if (!selected || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({
      type: 'submit_answer',
      answer: selected,
    }));
  };

  return (
    <div className="quiz-page">
      <div className="quiz-left panel">
        <div className="quiz-header">
          <div>
            <h2>{participant?.name || 'Guest'}</h2>
            <div className="badge">Student</div>
          </div>
          <div className="status-chip">{status.toUpperCase()}</div>
        </div>

        <div className="three-card">
          <StageScene question={question} />
        </div>

        <div className="question-panel">
          <div className="question-meta">
            <span>Room {roomCode}</span>
            <span>{status === 'ended' ? 'Quiz complete' : `Question ${currentQuestionIndex} / ${totalQuestions}`}</span>
          </div>
          {question ? (
            <>
              <div className="question-text">{question.text}</div>
              <div className="options-grid">
                {Object.entries(question.options).map(([key, value]) => (
                  <button
                    key={key}
                    onClick={() => setSelected(key)}
                    className={selected === key ? 'option selected' : 'option'}
                    disabled={feedback?.score !== undefined || timer === 0}
                  >
                    <span>{key}</span> {value}
                  </button>
                ))}
              </div>
              <div className="room-footer">
                <div className={`timer-pill ${timer <= 10 ? 'low' : ''}`}>{timer}s</div>
                <button className="primary-button" onClick={submitAnswer} disabled={!selected || feedback?.score !== undefined || timer === 0}>
                  Submit Answer
                </button>
              </div>
            </>
          ) : (
            <div className="empty-state">
              {status === 'ended' ? 'The quiz has ended.' : 'Waiting for the host to start the quiz...'}
            </div>
          )}
          {feedback && (
            <div className={`feedback ${feedback.correct ? 'success' : 'error'}`}>
              {feedback.correct ? 'Correct!' : 'Wrong answer.'} Correct answer: {feedback.answer}. Score {feedback.points > 0 ? `+${feedback.points}` : feedback.points}.
            </div>
          )}
        </div>
      </div>

      <div className="quiz-right panel leaderboard-card">
        <h3>Live Leaderboard</h3>
        <ol className="leaderboard-list">
          {leaderboard.length ? leaderboard.map((item) => (
            <li key={item.name}>
              <span>{item.rank}. {item.name}</span>
              <span>{item.score}</span>
            </li>
          )) : <li className="empty-state">No scores yet.</li>}
        </ol>
      </div>
    </div>
  );
}

function HostLogin() {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const endpoint =
        mode === 'login'
          ? `${API_BASE}/auth/login/`
          : `${API_BASE}/auth/register/`;

      const body =
        mode === 'login'
          ? { username, password }
          : { username, email, password, password_confirm: confirmPassword };

      const data = await fetchApi(endpoint, 'POST', null, body);

      setAuthToken(data.token);
      navigate('/host/dashboard');

    } catch (err) {
      setError(err.message); // Display the error message from the server if available
    }
  };

  return (
    <div className="auth-panel card-grid">
      <div className="panel auth-box">
        <h2>{mode === 'login' ? 'Host Login' : 'Host Signup'}</h2>
        <form onSubmit={handleSubmit} className="form-stack">
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />
          </label>
          {mode === 'signup' && (
            <label>
              Email
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" />
            </label>
          )}
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" />
          </label>
          {mode === 'signup' && (
            <label>
              Confirm Password
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="confirm password" />
            </label>
          )}
          {error && <div className="error-box">{error}</div>}
          <button className="primary-button" type="submit">{mode === 'login' ? 'Login' : 'Register'}</button>
        </form>
        <button className="secondary-button" onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}>
          {mode === 'login' ? 'Create a new host account' : 'Back to login'}
        </button>
      </div>
    </div>
  );
}

function HostDashboard() {
  const navigate = useNavigate();
  const [token, setToken] = useState(getAuthToken());
  const [quizTitle, setQuizTitle] = useState('');
  const [quizDescription, setQuizDescription] = useState('');
  const [quizId, setQuizId] = useState(null);
  const [questionText, setQuestionText] = useState('');
  const [optionA, setOptionA] = useState('');
  const [optionB, setOptionB] = useState('');
  const [optionC, setOptionC] = useState('');
  const [optionD, setOptionD] = useState('');
  const [correctAnswer, setCorrectAnswer] = useState('A');
  const [roomCode, setRoomCode] = useState('');
  const [status, setStatus] = useState('');
  const [myQuizzes, setMyQuizzes] = useState([]);
  const [questionList, setQuestionList] = useState([]);
  const [selectedQuizId, setSelectedQuizId] = useState(null);

  useEffect(() => {
    if (!token) {
      navigate('/host/login');
      return;
    }
    fetchQuizList();
  }, [navigate, token]);

  const fetchQuizList = async () => {
    try {
      const data = await fetchApi(`${API_BASE}/quizzes/`, 'GET', token);
      setMyQuizzes(data.quizzes);
      if (data.quizzes.length && !selectedQuizId) {
        setSelectedQuizId(data.quizzes[0].id);
      }
    } catch (err) {
      setStatus(err.response?.data?.error || 'Unable to load quizzes');
    }
  };

  const fetchQuestions = async (quizIdToLoad) => {
    try {
      const data = await fetchApi(`${API_BASE}/quizzes/${quizIdToLoad}/questions/list/`, 'GET', token);
      setQuestionList(data.quiz.questions);
      setSelectedQuizId(data.quiz.id);
      setStatus(`Loaded ${data.quiz.questions.length} questions for ${data.quiz.title}`);
    } catch (err) {
      setStatus(err.response?.data?.error || 'Unable to load quiz details');
    }
  };

  const handleCreateQuiz = async () => {
    try {
      const data = await fetchApi(`${API_BASE}/quizzes/create/`, 'POST', token, {
        title: quizTitle,
        description: quizDescription,
      });
      setQuizId(data.quiz.id);
      setSelectedQuizId(data.quiz.id);
      setMyQuizzes((prev) => [
        { id: data.quiz.id, title: data.quiz.title, description: data.quiz.description, question_count: 0, created_at: new Date().toISOString() },
        ...prev,
      ]);
      setStatus('Quiz created successfully');
      setRoomCode('');
      setQuestionList([]);
    } catch (err) {
      setStatus(err.response?.data?.error || 'Unable to create quiz');
    }
  };

  const handleAddQuestion = async () => {
    try {
      const activeQuizId = selectedQuizId || quizId;
      if (!activeQuizId) {
        setStatus('Create a quiz first.');
        return;
      }
      await fetchApi(`${API_BASE}/quizzes/${activeQuizId}/questions/`, 'POST', token, {
        question_text: questionText,
        option_a: optionA,
        option_b: optionB,
        option_c: optionC,
        option_d: optionD,
        correct_answer: correctAnswer,
      });
      setStatus('Question added');
      setQuestionText('');
      setOptionA('');
      setOptionB('');
      setOptionC('');
      setOptionD('');
      await fetchQuestions(activeQuizId);
      setMyQuizzes((prev) => prev.map((quiz) => quiz.id === activeQuizId ? { ...quiz, question_count: quiz.question_count + 1 } : quiz));
    } catch (err) {
      setStatus(err.response?.data?.error || 'Unable to add question');
    }
  };

  const handleSelectQuiz = (event) => {
    const selectedId = Number(event.target.value);
    setSelectedQuizId(selectedId);
    fetchQuestions(selectedId);
  };

  const handleCreateRoom = async () => {
    try {
      const activeQuizId = selectedQuizId || quizId;
      if (!activeQuizId) {
        setStatus('Create a quiz first.');
        return;
      }
      const data = await fetchApi(`${API_BASE}/quizzes/${activeQuizId}/room/`, 'POST', token);
      setRoomCode(data.room.room_code);
      setStatus(`Room ${data.room.room_code} ready`);
    } catch (err) {
      setStatus(err.response?.data?.error || 'Unable to create room');
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    navigate('/host/login');
  };

  return (
    <div className="host-dashboard page-grid">
      <div className="panel dashboard-card">
        <div className="dashboard-top">
          <h2>Host Dashboard</h2>
          <button className="secondary-button" onClick={handleLogout}>Logout</button>
        </div>
        <div className="form-stack">
          <label>
            Select Quiz
            <select value={selectedQuizId || ''} onChange={handleSelectQuiz}>
              <option value="">Start new quiz</option>
              {myQuizzes.map((quiz) => (
                <option key={quiz.id} value={quiz.id}>
                  {quiz.title} ({quiz.question_count} questions)
                </option>
              ))}
            </select>
          </label>
          <label>
            Quiz Title
            <input value={quizTitle} onChange={(e) => setQuizTitle(e.target.value)} placeholder="Enter quiz title" />
          </label>
          <label>
            Description
            <textarea value={quizDescription} onChange={(e) => setQuizDescription(e.target.value)} placeholder="Describe your quiz" />
          </label>
          <button className="primary-button" onClick={handleCreateQuiz}>Create Quiz</button>
        </div>
      </div>

      <div className="panel dashboard-card">
        <h3>Add Quiz Question</h3>
        <div className="form-stack">
          <label>
            Question Text
            <textarea value={questionText} onChange={(e) => setQuestionText(e.target.value)} placeholder="Type your question" />
          </label>
          <label>
            Option A
            <input value={optionA} onChange={(e) => setOptionA(e.target.value)} />
          </label>
          <label>
            Option B
            <input value={optionB} onChange={(e) => setOptionB(e.target.value)} />
          </label>
          <label>
            Option C
            <input value={optionC} onChange={(e) => setOptionC(e.target.value)} />
          </label>
          <label>
            Option D
            <input value={optionD} onChange={(e) => setOptionD(e.target.value)} />
          </label>
          <label>
            Correct Answer
            <select value={correctAnswer} onChange={(e) => setCorrectAnswer(e.target.value)}>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
              <option value="D">D</option>
            </select>
          </label>
          <button className="primary-button" onClick={handleAddQuestion}>Add Question</button>
        </div>
      </div>

      <div className="panel dashboard-card">
        <h3>Question Preview</h3>
        {questionList.length ? (
          <div className="question-preview-list">
            {questionList.map((question, index) => (
              <div key={question.id} className="question-preview-card">
                <strong>{index + 1}. {question.question_text}</strong>
                <p>A: {question.option_a}</p>
                <p>B: {question.option_b}</p>
                <p>C: {question.option_c}</p>
                <p>D: {question.option_d}</p>
                <div className="question-badge">Answer: {question.correct_answer}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">No questions added yet.</div>
        )}
      </div>

      <div className="panel dashboard-card">
        <h3>Room Control</h3>
        <div className="room-card">
          <p><strong>Room Code</strong></p>
          <p>{roomCode || 'Not created yet'}</p>
          <button className="primary-button" onClick={handleCreateRoom}>Create Room</button>
          {roomCode && (
            <Link className="secondary-button" to={`/host/room/${roomCode}`}>Open Host Room</Link>
          )}
        </div>
        <div className="status-box">{status}</div>
      </div>
    </div>
  );
}

function HostRoom() {
  const { roomCode } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('connecting');
  const [question, setQuestion] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [leaderboard, setLeaderboard] = useState([]);
  const [messages, setMessages] = useState([]);
  const [retryCount, setRetryCount] = useState(0);
  const token = getAuthToken();
  const socketRef = useRef(null);
  const reconnectRef = useRef(null);
  const manualCloseRef = useRef(false);

  const scheduleReconnect = () => {
    if (reconnectRef.current) {
      return;
    }
    const delay = Math.min(20000, 1000 * 2 ** retryCount);
    reconnectRef.current = window.setTimeout(() => {
      setRetryCount((count) => Math.min(5, count + 1));
      connectWebSocket();
      reconnectRef.current = null;
    }, delay);
    setStatus(`reconnecting in ${delay / 1000}s`);
  };

  const connectWebSocket = () => {
    if (!token) {
      return;
    }

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus('connecting');
    const ws = new WebSocket(`${WS_BASE}/${roomCode}/?token=${token}`);
    socketRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      setRetryCount(0);
      ws.send(JSON.stringify({ type: 'join', name: 'Host', avatar: 'avatar1', role: 'host' }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages((prev) => [...prev, JSON.stringify(data)]);
      if (data.type === 'quiz_started' || data.type === 'next_question') {
        setQuestion(data.question);
        setCurrentQuestionIndex(data.question_index + 1);
        setTotalQuestions(data.total_questions);
      }
      if (data.type === 'leaderboard_updated' || data.type === 'leaderboard') {
        setLeaderboard(data.leaderboard);
      }
      if (data.type === 'quiz_ended') {
        setStatus('ended');
        setLeaderboard(data.final_leaderboard || leaderboard);
      }
    };

    ws.onclose = (event) => {
      if (!manualCloseRef.current) {
        setStatus('disconnected');
        scheduleReconnect();
      }
    };

    ws.onerror = () => {
      setStatus('error');
    };
  };

  useEffect(() => {
    if (!token) {
      navigate('/host/login');
      return;
    }

    manualCloseRef.current = false;
    connectWebSocket();

    return () => {
      manualCloseRef.current = true;
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.close();
      }
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
      }
    };
  }, [navigate, roomCode, token]);

  const sendEvent = (type) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type }));
  };

  return (
    <div className="host-room page-grid">
      <div className="panel panel-panel">
        <div className="quiz-header">
          <div>
            <h2>Host Control</h2>
            <p>Room {roomCode}</p>
          </div>
          <div className="status-chip">{status.toUpperCase()}</div>
        </div>
        <div className="control-row">
          <button className="primary-button" onClick={() => sendEvent('start_quiz')}>Start Quiz</button>
          <button className="primary-button" onClick={() => sendEvent('next_question')}>Next Question</button>
          <button className="secondary-button" onClick={() => sendEvent('end_quiz')}>End Quiz</button>
        </div>
        <div className="question-summary">
          <h3>Current Question</h3>
          <p>{question ? question.text : 'No active question yet.'}</p>
          <small>{question ? `${currentQuestionIndex} / ${totalQuestions}` : ''}</small>
        </div>
      </div>

      <div className="panel leaderboard-card">
        <h3>Live Scores</h3>
        <ol className="leaderboard-list">
          {leaderboard.length ? leaderboard.map((item) => (
            <li key={item.name}>
              <span>{item.rank}. {item.name}</span>
              <span>{item.score}</span>
            </li>
          )) : <li className="empty-state">Waiting for scores...</li>}
        </ol>
      </div>

      <div className="panel panel-card">
        <h3>Event Log</h3>
        <div className="log-panel">
          {messages.slice(-8).map((line, index) => (<div key={index}>{line}</div>))}
        </div>
      </div>
    </div>
  );
}

export default App;
