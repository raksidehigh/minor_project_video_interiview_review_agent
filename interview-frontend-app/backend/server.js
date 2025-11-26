const express = require('express');
const multer = require('multer');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');
const { Storage } = require('@google-cloud/storage');
const axios = require('axios');
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

app.use(cors());
app.use(express.json());

// Config
const BUCKET_NAME = 'virtual-interview-agent';
const ASSESSMENT_API_URL = 'https://video-interview-api-wm2yb4fdna-uc.a.run.app/api/v1/assess';
const CREDENTIALS_PATH = path.join(__dirname, '../../service-account-key.json');

// Initialize GCS
const storage = fs.existsSync(CREDENTIALS_PATH)
  ? new Storage({ keyFilename: CREDENTIALS_PATH })
  : new Storage();

// Initialize SQLite
const db = new Database('interview.db');
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    dob TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    result JSON NOT NULL,
    gcs_path TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
`);

app.post('/submit-interview', upload.fields([
  { name: 'profile_photo', maxCount: 1 },
  { name: 'video_intro', maxCount: 1 },
  { name: 'video_q1', maxCount: 1 },
  { name: 'video_q2', maxCount: 1 },
  { name: 'video_q3', maxCount: 1 },
  { name: 'video_q4', maxCount: 1 },
  { name: 'video_q5', maxCount: 1 }
]), async (req, res) => {
  try {
    const { name, email, dob } = req.body;
    const userId = uuidv4();

    // Insert user
    db.prepare('INSERT INTO users (id, name, email, dob) VALUES (?, ?, ?, ?)').run(userId, name, email, dob);

    const bucket = storage.bucket(BUCKET_NAME);

    // Upload files
    const uploadFile = async (file, destPath) => {
      await bucket.file(destPath).save(file.buffer, { contentType: file.mimetype });
    };

    await uploadFile(req.files.profile_photo[0], `${userId}/profile_pic.jpg`);

    const videos = ['video_intro', 'video_q1', 'video_q2', 'video_q3', 'video_q4', 'video_q5'];
    for (let i = 0; i < videos.length; i++) {
      if (req.files[videos[i]]) {
        const ext = req.files[videos[i]][0].originalname.split('.').pop() || 'webm';
        await uploadFile(req.files[videos[i]][0], `${userId}/video${i + 1}.${ext}`);
      }
    }

    // Call assessment API
    const { data } = await axios.post(ASSESSMENT_API_URL, { user_id: userId, username: name });

    // Save result to GCS
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const resultPath = `all-api-results/${userId}-${timestamp}.json`;
    await bucket.file(resultPath).save(JSON.stringify(data, null, 2), { contentType: 'application/json' });

    // Save to DB
    const assessmentId = uuidv4();
    db.prepare('INSERT INTO assessments (id, user_id, result, gcs_path) VALUES (?, ?, ?, ?)').run(
      assessmentId, userId, JSON.stringify(data), resultPath
    );

    res.json({ ...data, user_id: userId, result_path: resultPath });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: error.message });
  }
});

app.get('/users', (req, res) => {
  const users = db.prepare('SELECT * FROM users ORDER BY created_at DESC').all();
  res.json(users);
});

app.get('/assessments/:userId', (req, res) => {
  const assessments = db.prepare('SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC').all(req.params.userId);
  res.json(assessments.map(a => ({ ...a, result: JSON.parse(a.result) })));
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
