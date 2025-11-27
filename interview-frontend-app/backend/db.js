const { Pool } = require('pg');

// Cloud SQL connection configuration
const pool = new Pool({
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME || 'interview_db',
  host: process.env.DB_HOST || '/cloudsql/interview-agent-479316:us-central1:interview-db',
  port: 5432,
});

// Initialize database tables
async function initDatabase() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        dob TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS assessments (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        result JSONB NOT NULL,
        gcs_path TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
      );
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
      CREATE INDEX IF NOT EXISTS idx_assessments_user_id ON assessments(user_id);
    `);

    console.log('✅ Database tables initialized');
  } catch (error) {
    console.error('❌ Database initialization error:', error);
    throw error;
  } finally {
    client.release();
  }
}

// Database operations
const db = {
  async checkEmail(email) {
    const result = await pool.query('SELECT id, email FROM users WHERE email = $1', [email]);
    return result.rows[0];
  },

  async getUserById(userId) {
    const result = await pool.query('SELECT * FROM users WHERE id = $1', [userId]);
    return result.rows[0];
  },

  async createUser(id, name, email, dob) {
    await pool.query(
      'INSERT INTO users (id, name, email, dob) VALUES ($1, $2, $3, $4)',
      [id, name, email, dob]
    );
  },

  async getLatestAssessment(userId) {
    const result = await pool.query(
      'SELECT result, gcs_path FROM assessments WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1',
      [userId]
    );
    return result.rows[0];
  },

  async createAssessment(id, userId, result, gcsPath) {
    await pool.query(
      'INSERT INTO assessments (id, user_id, result, gcs_path) VALUES ($1, $2, $3, $4)',
      [id, userId, JSON.stringify(result), gcsPath]
    );
  },

  async getAllUsers() {
    const result = await pool.query('SELECT * FROM users ORDER BY created_at DESC');
    return result.rows;
  },

  async getAllAssessments() {
    const result = await pool.query(`
      SELECT 
        a.id,
        a.user_id,
        u.name,
        u.email,
        a.gcs_path,
        a.created_at,
        a.result->>'decision' as decision,
        (a.result->>'final_score')::float as final_score
      FROM assessments a
      LEFT JOIN users u ON a.user_id = u.id
      ORDER BY a.created_at DESC
    `);
    return result.rows;
  },

  async getUserAssessments(userId) {
    const result = await pool.query(
      'SELECT * FROM assessments WHERE user_id = $1 ORDER BY created_at DESC',
      [userId]
    );
    return result.rows;
  }
};

module.exports = { db, initDatabase, pool };
