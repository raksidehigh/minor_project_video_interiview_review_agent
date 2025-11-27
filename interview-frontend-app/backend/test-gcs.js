const { Storage } = require('@google-cloud/storage');
const path = require('path');
const fs = require('fs');

const CREDENTIALS_PATH = path.join(__dirname, '../../service-account-key.json');
const BUCKET_NAME = 'virtual-interview-agent';

console.log('🧪 Testing GCS Connection...\n');

// Check credentials file
if (!fs.existsSync(CREDENTIALS_PATH)) {
  console.error('❌ service-account-key.json not found at:', CREDENTIALS_PATH);
  process.exit(1);
}
console.log('✅ Credentials file found');

// Initialize storage
const storage = new Storage({ keyFilename: CREDENTIALS_PATH });
console.log('✅ Storage client initialized');

// Test bucket access
async function testBucket() {
  try {
    const bucket = storage.bucket(BUCKET_NAME);
    const [exists] = await bucket.exists();

    if (!exists) {
      console.error(`❌ Bucket ${BUCKET_NAME} does not exist`);
      process.exit(1);
    }
    console.log(`✅ Bucket ${BUCKET_NAME} exists`);

    // Test upload
    const testFile = 'test-upload.txt';
    const testContent = `Test upload at ${new Date().toISOString()}`;

    console.log('\n📤 Testing file upload...');
    await bucket.file(testFile).save(testContent);
    console.log(`✅ Test file uploaded: gs://${BUCKET_NAME}/${testFile}`);

    // Test read
    console.log('\n📥 Testing file read...');
    const [content] = await bucket.file(testFile).download();
    console.log(`✅ Test file read: ${content.toString()}`);

    // Cleanup
    console.log('\n🧹 Cleaning up...');
    await bucket.file(testFile).delete();
    console.log('✅ Test file deleted');

    console.log('\n🎉 All GCS tests passed!');
  } catch (error) {
    console.error('\n❌ GCS test failed:', error.message);
    process.exit(1);
  }
}

testBucket();
