const API_URL = 'http://localhost:8080';
let currentStep = 0;
let stream = null;
let mediaRecorder = null;
let recordedChunks = [];
let timerInterval = null;
let recordingStartTime = 0;

const videoQuestions = [
  { title: 'Introduction', prompt: 'Introduce yourself and tell us about your academic background.' },
  { title: 'Question 1', prompt: 'What motivated you to apply for our Ambassador Program?' },
  { title: 'Question 2', prompt: 'Describe a time when you helped someone learn something new.' },
  { title: 'Question 3', prompt: 'How do you handle challenging situations or difficult students?' },
  { title: 'Question 4', prompt: 'What are your goals as a mentor and how do you plan to achieve them?' }
];

let currentVideoIndex = 0;
const collectedData = { videos: [] };

function nextStep() {
  const steps = document.querySelectorAll('.step');
  steps[currentStep].classList.add('hidden');
  currentStep++;
  steps[currentStep].classList.remove('hidden');
  updateProgress();
  
  if (currentStep === 2) loadVideoQuestion();
}

function updateProgress() {
  const progress = ((currentStep + 1) / 8) * 100;
  document.getElementById('progressFill').style.width = progress + '%';
  document.getElementById('stepIndicator').textContent = `Step ${currentStep + 1} of 8`;
}

async function startCamera(type) {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: type === 'video' });
    const video = type === 'photo' ? document.getElementById('photoVideo') : document.getElementById('recordingVideo');
    video.srcObject = stream;
    
    if (type === 'photo') {
      document.getElementById('captureBtn').disabled = false;
    } else {
      document.getElementById('recordBtn').disabled = false;
    }
  } catch (err) {
    alert('Camera access denied: ' + err.message);
  }
}

function capturePhoto() {
  const video = document.getElementById('photoVideo');
  const canvas = document.getElementById('photoCanvas');
  const preview = document.getElementById('photoPreview');
  
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  
  canvas.toBlob(blob => {
    collectedData.profile_photo = blob;
    preview.src = URL.createObjectURL(blob);
    preview.classList.remove('hidden');
    video.classList.add('hidden');
    stream.getTracks().forEach(t => t.stop());
    
    document.getElementById('captureBtn').classList.add('hidden');
    document.getElementById('retakePhotoBtn').classList.remove('hidden');
    document.getElementById('nextPhotoBtn').disabled = false;
  });
}

function retakePhoto() {
  document.getElementById('photoPreview').classList.add('hidden');
  document.getElementById('photoVideo').classList.remove('hidden');
  document.getElementById('captureBtn').classList.remove('hidden');
  document.getElementById('retakePhotoBtn').classList.add('hidden');
  document.getElementById('nextPhotoBtn').disabled = true;
  startCamera('photo');
}

function loadVideoQuestion() {
  if (currentVideoIndex < videoQuestions.length) {
    const q = videoQuestions[currentVideoIndex];
    document.getElementById('videoTitle').textContent = q.title;
    document.getElementById('videoPrompt').textContent = q.prompt;
    document.getElementById('timer').textContent = '00:00';
    document.getElementById('recordBtn').textContent = 'Start Recording';
    document.getElementById('recordBtn').disabled = true;
    document.getElementById('nextVideoBtn').disabled = true;
    document.getElementById('retakeVideoBtn').classList.add('hidden');
    document.getElementById('recordingVideo').classList.remove('hidden');
    document.getElementById('playbackVideo').classList.add('hidden');
  }
}

function toggleRecording() {
  if (!mediaRecorder || mediaRecorder.state === 'inactive') {
    startRecording();
  } else {
    stopRecording();
  }
}

function startRecording() {
  recordedChunks = [];
  mediaRecorder = new MediaRecorder(stream);
  
  mediaRecorder.ondataavailable = e => {
    if (e.data.size > 0) recordedChunks.push(e.data);
  };
  
  mediaRecorder.onstop = () => {
    const blob = new Blob(recordedChunks, { type: 'video/webm' });
    collectedData.videos[currentVideoIndex] = blob;
    
    const playback = document.getElementById('playbackVideo');
    playback.src = URL.createObjectURL(blob);
    playback.classList.remove('hidden');
    document.getElementById('recordingVideo').classList.add('hidden');
    
    stream.getTracks().forEach(t => t.stop());
    document.getElementById('retakeVideoBtn').classList.remove('hidden');
    document.getElementById('nextVideoBtn').disabled = false;
  };
  
  mediaRecorder.start();
  recordingStartTime = Date.now();
  document.getElementById('recordBtn').textContent = 'Stop Recording';
  
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
    const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
    const secs = (elapsed % 60).toString().padStart(2, '0');
    document.getElementById('timer').textContent = `${mins}:${secs}`;
  }, 1000);
}

function stopRecording() {
  mediaRecorder.stop();
  clearInterval(timerInterval);
  document.getElementById('recordBtn').textContent = 'Start Recording';
}

function retakeVideo() {
  document.getElementById('playbackVideo').classList.add('hidden');
  document.getElementById('recordingVideo').classList.remove('hidden');
  document.getElementById('retakeVideoBtn').classList.add('hidden');
  document.getElementById('nextVideoBtn').disabled = true;
  startCamera('video');
}

function nextVideoStep() {
  currentVideoIndex++;
  if (currentVideoIndex < videoQuestions.length) {
    loadVideoQuestion();
  } else {
    submitInterview();
  }
}

async function submitInterview() {
  const steps = document.querySelectorAll('.step');
  steps[currentStep].classList.add('hidden');
  document.getElementById('step-results').classList.remove('hidden');
  
  const formData = new FormData();
  formData.append('name', document.getElementById('name').value);
  formData.append('email', document.getElementById('email').value);
  formData.append('dob', document.getElementById('dob').value);
  formData.append('profile_photo', collectedData.profile_photo);
  
  collectedData.videos.forEach((video, i) => {
    const name = i === 0 ? 'video_intro' : `video_q${i}`;
    formData.append(name, video, `${name}.webm`);
  });
  
  try {
    const res = await fetch(`${API_URL}/submit-interview`, { method: 'POST', body: formData });
    const result = await res.json();
    
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('resultsContent').classList.remove('hidden');
    
    const badge = document.getElementById('decisionBadge');
    badge.textContent = result.decision;
    badge.className = `inline-block px-4 py-2 rounded-full text-white font-semibold mb-4 ${
      result.decision === 'PASS' ? 'bg-green-600' : result.decision === 'REVIEW' ? 'bg-yellow-600' : 'bg-red-600'
    }`;
    
    document.getElementById('finalScore').textContent = result.final_score;
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
  } catch (err) {
    alert('Submission failed: ' + err.message);
  }
}
