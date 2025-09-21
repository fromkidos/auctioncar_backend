const path = require('path');
const dotenv = require('dotenv');

// Load .env from parent directory
const envPath = path.resolve(__dirname, '..', '.env');
dotenv.config({ path: envPath });

module.exports = {
  // Add any additional Prisma configuration here
};