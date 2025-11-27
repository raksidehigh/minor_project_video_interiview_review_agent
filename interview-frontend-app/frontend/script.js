const API_URL = 'https://interview-backend-wm2yb4fdna-uc.a.run.app';
const MIN_RECORDING_DURATION = 15;

const QUESTIONS = [
  {
    text: 'How would you design a Video Streaming Platform Like YouTube.',
    hints: [
      'Discuss upload, storage, and CDN for video delivery',
      'Mention database design for metadata',
      'Consider scalability and load balancing',
      'Talk about video transcoding and formats'
    ]
  },
  {
    text: 'Explain the Trade-offs Between Monolithic vs Microservices Architecture.',
    hints: [
      'Compare simplicity vs complexity',
      'Discuss deployment and scaling differences',
      'Mention team size and organizational impact',
      'Consider when to use each approach'
    ]
  },
  {
    text: 'How Would You Handle Authentication and Authorization in a Full Stack Application?',
    hints: [
      'Explain difference between authentication and authorization',
      'Discuss JWT, sessions, or OAuth',
      'Mention security best practices (HTTPS, token storage)',
      'Talk about role-based access control (RBAC)'
    ]
  },
  {
    text: 'Describe Your Approach to Optimizing the Performance of a Slow Web Application.',
    hints: [
      'Start with measuring and profiling',
      'Discuss caching strategies',
      'Mention database optimization (indexing, queries)',
      'Consider frontend optimization (lazy loading, code splitting)'
    ]
  },
  {
    text: 'How Would You Design a Real-time Notification System?',
    hints: [
      'Choose technology: WebSockets, SSE, or polling',
      'Discuss message queues (Redis, Kafka)',
      'Consider scalability and reliability',
      'Mention handling offline users'
    ]
  }
];

// State Management
const state = {
  user: null,
  currentStep: 1,
  totalSteps: 8,
  currentQuestion: 0,
  recordings: {
    profile: null,
    identity: null,
    questions: []
  },
  streams: {},
  recorders: {},
  timers: {},
  uploadedFiles: {
    profile: false,
    identity: false,
    questions: [false, false, false, false, false]
  }
};

// Save state to localStorage
function saveSession() {
  const sessionData = {
    user: state.user,
    currentStep: state.currentStep,
    currentQuestion: state.currentQuestion,
    uploadedFiles: state.uploadedFiles,
    timestamp: Date.now()
  };
  localStorage.setItem('interview_session', JSON.stringify(sessionData));
}

// Load state from localStorage
function loadSession() {
  const session = localStorage.getItem('interview_session');
  if (session) {
    const data = JSON.parse(session);
    // Check if session is less than 24 hours old
    if (Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
      return data;
    } else {
      localStorage.removeItem('interview_session');
    }
  }
  return null;
}

// Utility Functions
function showLoading(message = 'Processing...') {
  document.getElementById('loadingOverlay').classList.add('active');
  document.getElementById('loadingText').textContent = message;
}

function hideLoading() {
  document.getElementById('loadingOverlay').classList.remove('active');
}

function updateProgress() {
  const progress = (state.currentStep / state.totalSteps) * 100;
  document.getElementById('progressBar').style.width = progress + '%';
  document.getElementById('progressText').textContent = `Step ${state.currentStep} of ${state.totalSteps}`;
}

function goToStep(step) {
  // Hide all steps
  document.querySelectorAll('.step-card').forEach(el => el.classList.remove('active'));

  // Show target step
  if (step <= 2) {
    document.getElementById(`step${step}`).classList.add('active');
  } else if (step <= 7) {
    document.getElementById('step3').classList.add('active');
  } else {
    document.getElementById('stepResults').classList.add('active');
  }

  state.currentStep = step;
  updateProgress();
  saveSession();

  // Populate identity name when showing step 2
  if (step === 2 && state.user) {
    document.getElementById('identityName').textContent = state.user.name;
  }

  // Load question if in question steps
  if (step >= 3 && step <= 7) {
    loadQuestion(step - 3);
  }
}

// Authentication
document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  const name = document.getElementById('loginName').value.trim();
  const email = document.getElementById('loginEmail').value.trim();
  const dob = document.getElementById('loginDob').value;

  if (!name || !email || !dob) {
    alert('Please fill in all fields');
    return;
  }

  showLoading('Validating email...');

  try {
    const res = await fetch(`${API_URL}/check-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });

    const result = await res.json();

    if (!result.available) {
      hideLoading();
      alert('This email has already been used. Please use a different email address.');
      return;
    }

    state.user = {
      id: `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name,
      email,
      dob
    };

    saveSession();

    hideLoading();
    document.getElementById('loginScreen').classList.remove('active');
    document.getElementById('interviewScreen').classList.add('active');
    document.getElementById('userName').textContent = name;

    // Start with profile photo
    startCamera('photo');

  } catch (error) {
    hideLoading();
    alert('Network error. Please try again.');
    console.error(error);
  }
});

function logout() {
  if (confirm('Are you sure you want to exit? Your progress will be lost.')) {
    localStorage.removeItem('interview_session');
    stopAllStreams();
    location.reload();
  }
}

// Camera & Recording Functions
async function startCamera(type) {
  try {
    const constraints = {
      video: { width: 1280, height: 720 },
      audio: type !== 'photo'
    };

    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    state.streams[type] = stream;

    const videoEl = document.getElementById(
      type === 'photo' ? 'photoVideo' :
        type === 'identity' ? 'identityVideo' :
          'questionVideo'
    );

    videoEl.srcObject = stream;

  } catch (error) {
    alert('Camera access denied. Please allow camera access to continue.');
    console.error(error);
  }
}

function stopAllStreams() {
  Object.values(state.streams).forEach(stream => {
    if (stream) stream.getTracks().forEach(track => track.stop());
  });
  state.streams = {};
}

// Profile Photo
function capturePhoto() {
  const video = document.getElementById('photoVideo');
  const canvas = document.getElementById('photoCanvas');
  const preview = document.getElementById('photoPreview');

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);

  canvas.toBlob(async (blob) => {
    state.recordings.profile = blob;
    preview.src = URL.createObjectURL(blob);
    preview.classList.remove('hidden');
    video.classList.add('hidden');

    if (state.streams.photo) {
      state.streams.photo.getTracks().forEach(t => t.stop());
    }

    document.getElementById('captureBtn').classList.add('hidden');
    document.getElementById('retakePhotoBtn').classList.remove('hidden');

    // Upload photo
    showLoading('Uploading profile photo...');
    try {
      const formData = new FormData();
      formData.append('photo', blob, 'profile_pic.jpg');
      formData.append('user_id', state.user.id);

      await fetch(`${API_URL}/upload-photo`, {
        method: 'POST',
        body: formData
      });

      state.uploadedFiles.profile = true;
      saveSession();

      hideLoading();
      document.getElementById('nextPhotoBtn').classList.remove('hidden');
    } catch (error) {
      hideLoading();
      alert('Upload failed. Please try again.');
    }
  }, 'image/jpeg');
}

function retakePhoto() {
  document.getElementById('photoPreview').classList.add('hidden');
  document.getElementById('photoVideo').classList.remove('hidden');
  document.getElementById('captureBtn').classList.remove('hidden');
  document.getElementById('retakePhotoBtn').classList.add('hidden');
  document.getElementById('nextPhotoBtn').classList.add('hidden');
  startCamera('photo');
}

// Identity Video
function startIdentityRecording() {
  if (!state.streams.identity) {
    startCamera('identity').then(() => startIdentityRecording());
    return;
  }

  const recorder = new MediaRecorder(state.streams.identity);
  const chunks = [];
  let recordingSeconds = 0;

  recorder.ondataavailable = e => chunks.push(e.data);
  recorder.onstop = async () => {
    // Check minimum duration
    if (recordingSeconds < MIN_RECORDING_DURATION) {
      alert(`Recording too short! Please record at least ${MIN_RECORDING_DURATION} seconds. (Recorded: ${recordingSeconds}s)`);
      document.getElementById('startIdentityBtn').classList.remove('hidden');
      document.getElementById('stopIdentityBtn').classList.add('hidden');
      document.getElementById('identityTimer').textContent = '00:00';
      document.getElementById('identityTimer').classList.remove('active');
      startCamera('identity');
      return;
    }

    const blob = new Blob(chunks, { type: 'video/webm' });
    state.recordings.identity = blob;

    const playback = document.getElementById('identityPlayback');
    playback.src = URL.createObjectURL(blob);
    playback.classList.remove('hidden');
    document.getElementById('identityVideo').classList.add('hidden');
    document.getElementById('identityRecIndicator').classList.add('hidden');

    if (state.streams.identity) {
      state.streams.identity.getTracks().forEach(t => t.stop());
    }

    document.getElementById('stopIdentityBtn').classList.add('hidden');
    document.getElementById('retakeIdentityBtn').classList.remove('hidden');

    // Upload identity video
    showLoading('Uploading identity video...');
    try {
      const formData = new FormData();
      formData.append('video', blob, 'video_0.webm');
      formData.append('video_index', 0);
      formData.append('user_id', state.user.id);

      await fetch(`${API_URL}/upload-video`, {
        method: 'POST',
        body: formData
      });

      state.uploadedFiles.identity = true;
      saveSession();

      hideLoading();
      document.getElementById('nextIdentityBtn').classList.remove('hidden');
    } catch (error) {
      hideLoading();
      alert('Upload failed. Please try again.');
    }
  };

  recorder.start();
  state.recorders.identity = recorder;

  document.getElementById('startIdentityBtn').classList.add('hidden');
  document.getElementById('stopIdentityBtn').classList.remove('hidden');
  document.getElementById('stopIdentityBtn').disabled = true;
  document.getElementById('identityRecIndicator').classList.remove('hidden');

  // Timer
  recordingSeconds = 0;
  state.timers.identity = setInterval(() => {
    recordingSeconds++;
    const mins = Math.floor(recordingSeconds / 60).toString().padStart(2, '0');
    const secs = (recordingSeconds % 60).toString().padStart(2, '0');
    const timerEl = document.getElementById('identityTimer');
    timerEl.textContent = `${mins}:${secs}`;

    if (recordingSeconds >= MIN_RECORDING_DURATION) {
      timerEl.classList.add('active');
      document.getElementById('stopIdentityBtn').disabled = false;
    }
  }, 1000);
}

function stopIdentityRecording() {
  if (state.recorders.identity) {
    state.recorders.identity.stop();
    clearInterval(state.timers.identity);
  }
}

function retakeIdentity() {
  document.getElementById('identityPlayback').classList.add('hidden');
  document.getElementById('identityVideo').classList.remove('hidden');
  document.getElementById('startIdentityBtn').classList.remove('hidden');
  document.getElementById('retakeIdentityBtn').classList.add('hidden');
  document.getElementById('nextIdentityBtn').classList.add('hidden');
  document.getElementById('identityTimer').textContent = '00:00';
  document.getElementById('identityTimer').classList.remove('active');
  startCamera('identity');
}

// Question Recording
function loadQuestion(index) {
  state.currentQuestion = index;
  const question = QUESTIONS[index];

  document.getElementById('questionTitle').textContent = `Question ${index + 1}`;
  document.getElementById('questionText').textContent = question.text;

  // Display hints
  const hintsEl = document.getElementById('questionHints');
  hintsEl.innerHTML = '';
  question.hints.forEach(hint => {
    const li = document.createElement('li');
    li.textContent = hint;
    hintsEl.appendChild(li);
  });

  // Reset UI
  document.getElementById('questionPlayback').classList.add('hidden');
  document.getElementById('questionVideo').classList.remove('hidden');
  document.getElementById('startQuestionBtn').classList.remove('hidden');
  document.getElementById('stopQuestionBtn').classList.add('hidden');
  document.getElementById('retakeQuestionBtn').classList.add('hidden');
  document.getElementById('nextQuestionBtn').classList.add('hidden');
  document.getElementById('questionTimer').textContent = '00:00';
  document.getElementById('questionTimer').classList.remove('active');

  startCamera('question');
}

function startQuestionRecording() {
  if (!state.streams.question) {
    startCamera('question').then(() => startQuestionRecording());
    return;
  }

  const recorder = new MediaRecorder(state.streams.question);
  const chunks = [];
  let recordingSeconds = 0;

  recorder.ondataavailable = e => chunks.push(e.data);
  recorder.onstop = async () => {
    // Check minimum duration
    if (recordingSeconds < MIN_RECORDING_DURATION) {
      alert(`Recording too short! Please record at least ${MIN_RECORDING_DURATION} seconds. (Recorded: ${recordingSeconds}s)`);
      document.getElementById('startQuestionBtn').classList.remove('hidden');
      document.getElementById('stopQuestionBtn').classList.add('hidden');
      document.getElementById('questionTimer').textContent = '00:00';
      document.getElementById('questionTimer').classList.remove('active');
      startCamera('question');
      return;
    }

    const blob = new Blob(chunks, { type: 'video/webm' });
    state.recordings.questions[state.currentQuestion] = blob;

    const playback = document.getElementById('questionPlayback');
    playback.src = URL.createObjectURL(blob);
    playback.classList.remove('hidden');
    document.getElementById('questionVideo').classList.add('hidden');
    document.getElementById('questionRecIndicator').classList.add('hidden');

    if (state.streams.question) {
      state.streams.question.getTracks().forEach(t => t.stop());
    }

    document.getElementById('stopQuestionBtn').classList.add('hidden');
    document.getElementById('retakeQuestionBtn').classList.remove('hidden');

    // Upload question video
    const videoNumber = state.currentQuestion + 1;
    showLoading(`Uploading video ${videoNumber}/5...`);
    try {
      const formData = new FormData();
      formData.append('video', blob, `video_${videoNumber}.webm`);
      formData.append('video_index', videoNumber);
      formData.append('user_id', state.user.id);

      await fetch(`${API_URL}/upload-video`, {
        method: 'POST',
        body: formData
      });

      state.uploadedFiles.questions[state.currentQuestion] = true;
      saveSession();

      hideLoading();
      document.getElementById('nextQuestionBtn').classList.remove('hidden');
    } catch (error) {
      hideLoading();
      alert('Upload failed. Please try again.');
    }
  };

  recorder.start();
  state.recorders.question = recorder;

  document.getElementById('startQuestionBtn').classList.add('hidden');
  document.getElementById('stopQuestionBtn').classList.remove('hidden');
  document.getElementById('stopQuestionBtn').disabled = true;
  document.getElementById('questionRecIndicator').classList.remove('hidden');

  // Timer
  recordingSeconds = 0;
  state.timers.question = setInterval(() => {
    recordingSeconds++;
    const mins = Math.floor(recordingSeconds / 60).toString().padStart(2, '0');
    const secs = (recordingSeconds % 60).toString().padStart(2, '0');
    const timerEl = document.getElementById('questionTimer');
    timerEl.textContent = `${mins}:${secs}`;

    if (recordingSeconds >= MIN_RECORDING_DURATION) {
      timerEl.classList.add('active');
      document.getElementById('stopQuestionBtn').disabled = false;
    }
  }, 1000);
}

function stopQuestionRecording() {
  if (state.recorders.question) {
    state.recorders.question.stop();
    clearInterval(state.timers.question);
  }
}

function retakeQuestion() {
  document.getElementById('questionPlayback').classList.add('hidden');
  document.getElementById('questionVideo').classList.remove('hidden');
  document.getElementById('startQuestionBtn').classList.remove('hidden');
  document.getElementById('retakeQuestionBtn').classList.add('hidden');
  document.getElementById('nextQuestionBtn').classList.add('hidden');
  document.getElementById('questionTimer').textContent = '00:00';
  document.getElementById('questionTimer').classList.remove('active');
  startCamera('question');
}

function nextQuestion() {
  // Stop playback
  const playback = document.getElementById('questionPlayback');
  playback.pause();
  playback.src = '';

  if (state.currentQuestion < 4) {
    goToStep(state.currentStep + 1);
  } else {
    submitInterview();
  }
}

// Submit Interview
async function submitInterview() {
  goToStep(8);

  const payload = {
    user_id: state.user.id,
    name: state.user.name,
    email: state.user.email,
    dob: state.user.dob
  };

  try {
    const res = await fetch(`${API_URL}/submit-interview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await res.json();

    if (!res.ok) {
      showError(result.message || result.error || 'Submission failed');
      return;
    }

    showResults(result);

  } catch (error) {
    showError(`Network error: ${error.message}`);
  }
}

function showError(message) {
  document.getElementById('processingState').classList.add('hidden');
  document.getElementById('errorState').classList.remove('hidden');
  document.getElementById('errorMessage').textContent = message;
}

function showResults(result) {
  document.getElementById('processingState').classList.add('hidden');
  document.getElementById('resultsContent').classList.remove('hidden');

  const badge = document.getElementById('decisionBadge');
  badge.textContent = result.decision;
  badge.className = `decision-badge ${result.decision.toLowerCase()}`;

  document.getElementById('finalScore').textContent = Math.round(result.final_score);
  document.getElementById('recommendationText').textContent = result.recommendation || result.reasoning;

  const strengthsList = document.getElementById('strengthsList');
  strengthsList.innerHTML = '';
  (result.strengths || []).forEach(s => {
    const li = document.createElement('li');
    li.textContent = s;
    strengthsList.appendChild(li);
  });

  const concernsList = document.getElementById('concernsList');
  concernsList.innerHTML = '';
  (result.concerns || []).forEach(c => {
    const li = document.createElement('li');
    li.textContent = c;
    concernsList.appendChild(li);
  });
}

async function retryAssessment() {
  document.getElementById('errorState').classList.add('hidden');
  document.getElementById('processingState').classList.remove('hidden');

  const payload = {
    user_id: state.user.id,
    name: state.user.name,
    email: state.user.email,
    dob: state.user.dob,
    is_retry: true
  };

  try {
    const res = await fetch(`${API_URL}/submit-interview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await res.json();

    if (!res.ok) {
      showError(result.message || result.error || 'Retry failed');
      return;
    }

    showResults(result);

  } catch (error) {
    showError(`Network error: ${error.message}`);
  }
}

// Initialize
window.addEventListener('DOMContentLoaded', () => {
  const sessionData = loadSession();
  if (sessionData) {
    state.user = sessionData.user;
    state.currentStep = sessionData.currentStep;
    state.currentQuestion = sessionData.currentQuestion;
    state.uploadedFiles = sessionData.uploadedFiles;

    document.getElementById('loginScreen').classList.remove('active');
    document.getElementById('interviewScreen').classList.add('active');
    document.getElementById('userName').textContent = state.user.name;

    // Resume from where user left off
    goToStep(state.currentStep);

    // Show resume message
    const stepName = state.currentStep === 1 ? 'Profile Photo' :
      state.currentStep === 2 ? 'Identity Video' :
        `Question ${state.currentQuestion + 1}`;

    setTimeout(() => {
      if (confirm(`Welcome back, ${state.user.name}!\n\nResume from: ${stepName}?`)) {
        // Continue
      } else {
        logout();
      }
    }, 500);
  }
});
