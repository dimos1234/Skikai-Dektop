const mineflayer = require('mineflayer');

// --- BARE MINIMUM TEST SCRIPT ---
// Run this with: node test_connection.js
// ⚠️ ADAM: UPDATE THE PORT BELOW TO THE ONE IN YOUR MINECRAFT CHAT!

const bot = mineflayer.createBot({
  host: '127.0.0.1', 
  port: 62822,       // <--- CHANGE THIS !!
  username: 'Skikai_Test',
  // version: '1.21.1' // Try leaving this commented out first
});

bot.on('login', () => {
    console.log('✅ LOGIN SUCCESSFUL');
});

bot.on('spawn', () => {
    console.log('✅ SPAWN SUCCESSFUL');
    bot.chat("Connection test successful!");
    process.exit(0);
});

bot.on('error', (err) => {
    console.log('❌ CONNECTION ERROR:', err);
});

bot.on('kicked', (reason) => {
    console.log('❌ KICKED:', reason);
});

setTimeout(() => {
    console.log("⏱️ Connection timed out after 15 seconds.");
    process.exit(1);
}, 15000);
