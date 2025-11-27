const API_URL = 'http://localhost:8080';
let currentStep = 0;
let stream = null;
let mediaRecorder = null;
let recordedChunks = [];
let timerInterval = null;
let recordingStartTime = 0;
let recordingDuration = 0;

const videoQuestions = [
  { title: 'Question 1', prompt: 'System Design: Design a Video Streaming Platform Like YouTube.' },
  { title: 'Question 2', prompt: 'Explain the Trade-offs Between Monolithic vs Microservices Architecture.' },
  { title: 'Question 3', prompt: 'How Would You Handle Authentication and Authorization in a Full Stack Application?' },
  { title: 'Question 4', prompt: 'Describe Your Approach to Optimizing the Performance of a Slow Web Application.' },
  { title: 'Question 5', prompt: 'How Would You Design a Real-time Notification System?' }
];

let currentVideoIndex = 0;
const collectedData = { videos: [], uploadedVideos: [] };

function nextStep() {
  const steps = document.querySelectorAll('.step');
  steps[currentStep].classList.add('hidden');
  currentStep++;
  steps[currentStep].classList.remove('hidden');
  updateProgress();
  
  if (currentStep === 2) loadVideoQuestion();
}

function updateProgress() {
  const progress = ((currentStep + 1) / 7) * 100;
  document.getElementById('progressFill').style.width = progress + '%';
  document.getElementById('stepIndicator').textContent = `Step ${currentStep + 1} of 7`;
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
    recordingDuration = 0;
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
    
    // Enable next only if >= 15 seconds
    if (recordingDuration >= 15) {
      document.getElementById('nextVideoBtn').disabled = false;
    } else {
      alert(`Recording too short! Please record at least 15 seconds. (Recorded: ${recordingDuration}s)`);
      document.getElementById('nextVideoBtn').disabled = true;
    }
  };
  
  mediaRecorder.start();
  recordingStartTime = Date.now();
  document.getElementById('recordBtn').textContent = 'Stop Recording';
  document.getElementById('recordBtn').classList.remove('bg-red-600', 'hover:bg-red-700');
  document.getElementById('recordBtn').classList.add('bg-gray-600', 'hover:bg-gray-700');
  
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
    recordingDuration = elapsed;
    const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
    const secs = (elapsed % 60).toString().padStart(2, '0');
    const timerEl = document.getElementById('timer');
    timerEl.textContent = `${mins}:${secs}`;
    
    // Highlight when 15s reached
    if (elapsed >= 15) {
      timerEl.classList.add('text-green-600', 'font-bold');
    }
  }, 1000);
}

function stopRecording() {
  if (recordingDuration < 15) {
    if (!confirm(`Recording is only ${recordingDuration}s. Minimum is 15s. Stop anyway?`)) {
      return;
    }
  }
  
  mediaRecorder.stop();
  clearInterval(timerInterval);
  document.getElementById('recordBtn').textContent = 'Start Recording';
  document.getElementById('recordBtn').classList.remove('bg-gray-600', 'hover:bg-gray-700');
  document.getElementById('recordBtn').classList.add('bg-red-600', 'hover:bg-red-700');
}

function retakeVideo() {
  document.getElementById('playbackVideo').classList.add('hidden');
  document.getElementById('recordingVideo').classList.remove('hidden');
  document.getElementById('retakeVideoBtn').classList.add('hidden');
  document.getElementById('nextVideoBtn').disabled = true;
  document.getElementById('timer').classList.remove('text-green-600', 'font-bold');
  recordingDuration = 0;
  startCamera('video');
}

async function nextVideoStep() {
  // Show uploading indicator
  const nextBtn = document.getElementById('nextVideoBtn');
  const originalText = nextBtn.textContent;
  nextBtn.disabled = true;
  nextBtn.textContent = 'Uploading...';
  
  try {
    // Upload current video to backend
    const formData = new FormData();
    formData.append('video', collectedData.videos[currentVideoIndex], `video_q${currentVideoIndex + 1}.webm`);
    formData.append('video_index', currentVideoIndex + 1);
    formData.append('user_id', collectedData.temp_user_id || 'temp');
    
    const response = await fetch(`${API_URL}/upload-video`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error('Upload failed');
    }
    
    const result = await response.json();
    collectedData.uploadedVideos.push(result.path);
    
    // Move to next question
    currentVideoIndex++;
    if (currentVideoIndex < videoQuestions.length) {
      loadVideoQuestion();
    } else {
      submitInterview();
    }
  } catch (error) {
    alert('Failed to upload video: ' + error.message);
    nextBtn.disabled = false;
    nextBtn.textContent = originalText;
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
    formData.append(`video_q${i + 1}`, video, `video_q${i + 1}.webm`);
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
