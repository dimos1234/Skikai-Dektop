const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');
const pvp = require('mineflayer-pvp').plugin;
const armorManager = require('mineflayer-armor-manager');
const { plugin: toolPlugin } = require('mineflayer-tool');
const collectBlock = require('mineflayer-collectblock').plugin;
const dgram = require('dgram');

let autoEatLoader = null;
import('mineflayer-auto-eat').then(mod => {
    autoEatLoader = mod.loader || mod.default;
}).catch(err => {
    console.warn('[Minecraft] Could not load mineflayer-auto-eat:', err.message);
});

// --- UDP SETUP ---
const SKIKAI_HOST = '127.0.0.1';
const SKIKAI_PORT = 5007;
const skikaiClient = dgram.createSocket('udp4');

const BOT_PORT = 5008;
const botServer = dgram.createSocket('udp4');

// --- BOT STATE TRACKER ---
let currentTask = "idle";
let sessionGoal = null;
let sessionGoalAchieved = false;

// --- STUCK DETECTION ---
let lastPosition = null;
let stuckCheckStart = 0;
const STUCK_TIMEOUT_MS = 60000;

// --- PERIODIC SESSION SUMMARY ---
let lastSummaryTime = 0;
const SUMMARY_INTERVAL_MS = 5 * 60 * 1000;

setInterval(() => {
    // Body status reminder
    if (currentTask !== "idle") {
        sendSensoryEvent(`[Body Status]: I am currently ${currentTask}.`);
    }

    // Session summary
    const now = Date.now();
    if (now - lastSummaryTime > SUMMARY_INTERVAL_MS && bot.entity) {
        lastSummaryTime = now;
        const health = bot.health != null ? `${Math.round(bot.health)}/20` : "?";
        const food = bot.food != null ? `${bot.food}/20` : "?";
        const tod = bot.time ? getTimeOfDayString(bot.time.timeOfDay) : "unknown";
        const inv = bot.inventory.items().length;
        const goalStr = sessionGoal ? `Goal: ${sessionGoal}${sessionGoalAchieved ? " (ACHIEVED)" : ""}` : "No session goal set";
        sendSensoryEvent(
            `[Session Summary] Task: ${currentTask} | HP: ${health} | Food: ${food} | Time: ${tod} | Items: ${inv} | ${goalStr}`
        );
    }
}, 20000);

function getTimeOfDayString(ticks) {
    if (ticks >= 0 && ticks < 6000) return "morning";
    if (ticks >= 6000 && ticks < 12000) return "afternoon";
    if (ticks >= 12000 && ticks < 13000) return "sunset";
    if (ticks >= 13000 && ticks < 23000) return "night";
    return "dawn";
}

// Stuck detection: check every 5s if pathfinder is active but position hasn't changed
setInterval(() => {
    if (currentTask === "idle" || !bot.entity) {
        lastPosition = null;
        stuckCheckStart = 0;
        return;
    }
    const pos = bot.entity.position;
    if (lastPosition) {
        const dist = pos.distanceTo(lastPosition);
        if (dist < 1.5) {
            if (stuckCheckStart === 0) {
                stuckCheckStart = Date.now();
            } else if (Date.now() - stuckCheckStart > STUCK_TIMEOUT_MS) {
                sendSensoryEvent(`I got stuck trying to ${currentTask}. I'm giving up and waiting for new instructions.`);
                bot.pathfinder.setGoal(null);
                bot.pvp.stop();
                bot.clearControlStates();
                currentTask = "idle";
                stuckCheckStart = 0;
            }
        } else {
            stuckCheckStart = 0;
        }
    }
    lastPosition = pos.clone();
}, 5000);

// --- MINECRAFT BOT SETUP ---
const bot = mineflayer.createBot({
  host: '127.0.0.1', 
  port: 52873,       // <--- UPDATE THIS EVERY TIME!
  username: 'Skikai',
});

// Helper to send events to Skikai
function sendSensoryEvent(eventText) {
    const payload = JSON.stringify({
        type: "GAME_EVENT",
        app: "Minecraft",
        event: eventText
    });
    skikaiClient.send(payload, SKIKAI_PORT, SKIKAI_HOST);
}

bot.on('login', () => {
    console.log('✅ Connected to server. Loading plugins...');
    bot.loadPlugin(pathfinder);
    bot.loadPlugin(pvp);
    bot.loadPlugin(armorManager);
    bot.loadPlugin(toolPlugin);
    bot.loadPlugin(collectBlock);
    if (autoEatLoader) {
        bot.loadPlugin(autoEatLoader);
    } else {
        console.warn('[Minecraft] auto-eat not loaded yet, retrying in 2s...');
        setTimeout(() => {
            if (autoEatLoader) bot.loadPlugin(autoEatLoader);
            else console.error('[Minecraft] auto-eat failed to load — skipping.');
        }, 2000);
    }
});

bot.once('spawn', () => {
    console.log('[Minecraft] Skikai has spawned in the world!');
    sendSensoryEvent("You just logged into the Minecraft server.");
    
    const defaultMove = new Movements(bot);
    defaultMove.canDig = true;
    defaultMove.allowFreeClearance = true;
    bot.pathfinder.setMovements(defaultMove);
    
    if (bot.autoEat) {
        bot.autoEat.options = {
            priority: 'foodPoints',
            startAt: 14,
            bannedFood: ['rotten_flesh', 'spider_eye', 'poisonous_potato', 'pufferfish']
        };
    }

    // --- IDLE BEHAVIOR: Look at nearby players ---
    setInterval(() => {
        if (currentTask === "idle") {
            const entity = bot.nearestEntity(e => e.type === 'player' || e.type === 'mob');
            if (entity) {
                bot.lookAt(entity.position.offset(0, entity.height, 0));
            }
        }
    }, 3000);
});

// Helper to simulate "real player" jumping while running
bot.on('move', () => {
    if (bot.controlState.sprint && !bot.controlState.jump && bot.entity.onGround) {
        if (Math.random() < 0.05) {
            bot.setControlState('jump', true);
            setTimeout(() => bot.setControlState('jump', false), 100);
        }
    }
});

// --- ADVANCED SENSORY EVENTS ---
bot.on('chat', (username, message) => {
    if (username === bot.username) return;
    sendSensoryEvent(`${username} said in chat: "${message}"`);
});

bot.on('death', () => {
    sendSensoryEvent("You died.");
});

bot.on('health', () => {
    if (bot.health < 10) {
        sendSensoryEvent(`Warning: Your health is critically low! (${bot.health}/20)`);
    }
});

bot.on('playerCollect', (collector, itemDrop) => {
    if (collector !== bot.entity) return;
    setTimeout(() => {
        const item = bot.inventory.items().find(i => i.name === itemDrop.metadata[8]?.name);
        if (item) {
            sendSensoryEvent(`You just picked up a ${item.name}.`);
        } else {
            sendSensoryEvent(`You picked up an item.`);
        }
    }, 100);
});

bot.on('rain', () => {
    if (bot.isRaining) {
        sendSensoryEvent("It just started raining in Minecraft.");
    } else {
        sendSensoryEvent("The rain in Minecraft stopped.");
    }
});

bot.on('time', () => {
    // 12000 is dusk, 24000 is dawn
    if (bot.time.timeOfDay === 13000) {
        sendSensoryEvent("The sun just set in Minecraft. It is now night time. Monsters will spawn.");
    } else if (bot.time.timeOfDay === 23000) {
        sendSensoryEvent("The sun is rising in Minecraft. It is morning.");
    }
});

bot.on('error', (err) => {
    console.error(`[Minecraft Error]: ${err.message}`);
});

bot.on('kicked', (reason) => {
    console.warn(`[Minecraft Kicked]: ${reason}`);
});

// --- COMMAND LISTENER FROM SKIKAI ---
botServer.on('message', async (msg, rinfo) => {
    const commandStr = msg.toString().trim();
    console.log(`[Command Received]: ${commandStr}`);

    // Handle SESSION_GOAL:text format from Python side
    if (commandStr.startsWith('SESSION_GOAL:')) {
        sessionGoal = commandStr.slice('SESSION_GOAL:'.length).trim();
        sessionGoalAchieved = false;
        sendSensoryEvent(`Our goal for this session is: ${sessionGoal}`);
        return;
    }
    
    const args = commandStr.split(' ');
    const action = args[0].toLowerCase();
    
    if (action === 'say') {
        bot.chat(args.slice(1).join(' '));
    } 
    else if (action === 'follow' || action === 'goto') {
        const targetName = args[1];
        
        const player = Object.values(bot.players).find(p => p.username.toLowerCase() === targetName.toLowerCase());
        const target = player?.entity;
        
        if (target) {
            currentTask = `following ${targetName}`;
            
            const defaultMove = new Movements(bot);
            defaultMove.allowFreeClearance = true;
            defaultMove.canDig = true;
            bot.pathfinder.setMovements(defaultMove);
            
            bot.pathfinder.setGoal(new goals.GoalFollow(target, 2), true);
            sendSensoryEvent(`You are now following ${targetName}.`);

            // Re-apply follow goal every 10s so it tracks moving players
            const followRefresh = setInterval(() => {
                if (currentTask !== `following ${targetName}`) {
                    clearInterval(followRefresh);
                    return;
                }
                const freshPlayer = Object.values(bot.players).find(p => p.username.toLowerCase() === targetName.toLowerCase());
                const freshTarget = freshPlayer?.entity;
                if (freshTarget) {
                    bot.pathfinder.setGoal(new goals.GoalFollow(freshTarget, 2), true);
                }
            }, 10000);
        } else {
            sendSensoryEvent(`Cannot find ${targetName} to follow. They might be too far away to see.`);
        }
    }
    else if (action === 'attack') {
        bot.pathfinder.setGoal(null); // Clear manual goals!
        const targetName = args[1];
        
        const player = Object.values(bot.players).find(p => p.username.toLowerCase() === targetName.toLowerCase());
        // Added displayName check for mobs
        const target = player?.entity || bot.nearestEntity(e => e.name?.toLowerCase().includes(targetName.toLowerCase()) || e.displayName?.toLowerCase().includes(targetName.toLowerCase()));
        
        if (target) {
            const tName = target.username || target.name || target.displayName;
            currentTask = `attacking ${tName}`;
            sendSensoryEvent(`Target locked. I am attacking ${tName}!`);
            
            // Just call attack, the plugin handles the running and jumping
            bot.pvp.attack(target);

            const attackCheck = setInterval(() => {
                if (currentTask !== `attacking ${tName}`) { clearInterval(attackCheck); return; }
                if (!target.isValid || target.health <= 0) { 
                    bot.pvp.stop();
                    currentTask = "idle";
                    sendSensoryEvent(`${tName} is defeated or gone. I stopped attacking.`);
                    clearInterval(attackCheck);
                }
            }, 2000);
        } else {
            sendSensoryEvent(`Cannot find anything named ${targetName} to attack.`);
        }
    }
    else if (action === 'mine' || action === 'collect') {
        // 1. Stop any current movement before trying to mine!
        bot.pathfinder.setGoal(null);
        bot.clearControlStates();

        // 2. Clean up the LLM's hallucinated text
        let rawName = args.slice(1).join('_').toLowerCase();
        rawName = rawName.replace('minecraft:', '').replace('some_', '').replace('a_', '');

        try {
            const mcData = require('minecraft-data')(bot.version);
            let blockIds = [];

            // 3. Broaden the search parameters
            if (rawName.includes('wood') || rawName.includes('log') || rawName.includes('tree')) {
                blockIds = Object.values(mcData.blocks).filter(b => b.name.endsWith('_log')).map(b => b.id);
                rawName = 'wood'; 
            } else if (rawName.includes('dirt')) {
                blockIds = [mcData.blocksByName['dirt']?.id, mcData.blocksByName['grass_block']?.id].filter(Boolean);
            } else if (rawName.includes('stone')) {
                blockIds = [mcData.blocksByName['stone']?.id, mcData.blocksByName['cobblestone']?.id].filter(Boolean);
            } else {
                // Fuzzy match for anything else (e.g., 'diamond' matches 'diamond_ore')
                let exactBlock = Object.values(mcData.blocks).find(b => b.name.includes(rawName));
                if (exactBlock) blockIds = [exactBlock.id];
            }

            if (blockIds.length === 0) {
                sendSensoryEvent(`I don't know how to find or mine a block called '${rawName}'.`);
                return;
            }

            // 4. Reduce max distance and count so she doesn't time out pathfinding
            const blocks = bot.findBlocks({ matching: blockIds, maxDistance: 32, count: 3 });

            if (blocks.length === 0) {
                sendSensoryEvent(`I couldn't find any ${rawName} nearby to mine.`);
                return;
            }

            currentTask = `mining ${rawName}`;
            sendSensoryEvent(`I spotted some ${rawName} nearby. Heading over to mine it!`);

            const targets = blocks.map(pos => bot.blockAt(pos));

            bot.collectBlock.collect(targets, err => {
                if (err) {
                    sendSensoryEvent(`I ran into a problem while mining ${rawName}: ${err.message}`);
                } else {
                    sendSensoryEvent(`I successfully finished mining the ${rawName}!`);
                }
                currentTask = "idle";
            });

        } catch (err) {
            sendSensoryEvent(`Error trying to mine: ${err.message}`);
            currentTask = "idle";
        }
    }
    else if (action === 'dance') {
        currentTask = "dancing";
        sendSensoryEvent("You started dancing.");
        let dances = 0;
        const danceInterval = setInterval(() => {
            bot.setControlState('sneak', !bot.controlState.sneak);
            dances++;
            if (dances > 10) {
                clearInterval(danceInterval);
                currentTask = "idle";
            }
        }, 300);
    }
    else if (action === 'inventory') {
        const items = bot.inventory.items().map(item => `${item.count}x ${item.name}`).join(', ');
        sendSensoryEvent(items ? `Your inventory contains: ${items}` : "Your inventory is currently empty.");
    }
    else if (action === 'build' || action === 'place') {
        const blockName = args[1];
        
        try {
            const mcData = require('minecraft-data')(bot.version);
            const item = bot.inventory.items().find(i => i.name.includes(blockName));
            
            if (!item) {
                sendSensoryEvent(`I don't have any ${blockName} in my inventory to build with.`);
                return;
            }
            
            await bot.equip(item, 'hand');
            
            // Find a block in front of us to place it on
            const referenceBlock = bot.blockAtCursor(4);
            
            if (!referenceBlock) {
                sendSensoryEvent(`I'm not looking at a block I can build on. Come closer and tell me exactly where to place it.`);
                return;
            }
            
            // Try to place the block on the top face of the reference block
            const faceVector = { x: 0, y: 1, z: 0 }; 
            
            bot.placeBlock(referenceBlock, faceVector, (err) => {
                if (err) {
                    sendSensoryEvent(`I tried to place the ${blockName}, but I couldn't: ${err.message}`);
                } else {
                    sendSensoryEvent(`I just placed a ${blockName} block down.`);
                }
            });
            
        } catch (err) {
            sendSensoryEvent(`Build Error: ${err.message}`);
        }
    }
    else if (action === 'drop') {
        const itemName = args[1];
        const item = bot.inventory.items().find(i => i.name.includes(itemName));
        if (item) {
            bot.tossStack(item, (err) => {
                if (err) sendSensoryEvent(`I tried to drop the ${itemName} but failed: ${err.message}`);
                else sendSensoryEvent(`I just dropped all my ${item.name} on the floor.`);
            });
        } else {
            sendSensoryEvent(`I don't have any ${itemName} to drop.`);
        }
    }
    else if (action === 'troll') {
        const targetName = args[1] || 'grus_left_arm';
        const player = Object.values(bot.players).find(p => p.username.toLowerCase() === targetName.toLowerCase());
        const target = player?.entity;
        
        if (target) {
            currentTask = "trolling";
            sendSensoryEvent(`I am going to sneak up on ${targetName} and punch them once, then run away.`);
            
            const defaultMove = new Movements(bot);
            defaultMove.canDig = true;
            bot.pathfinder.setMovements(defaultMove);
            bot.pathfinder.setGoal(new goals.GoalFollow(target, 1), true);
            
            bot.once('goal_reached', () => {
                bot.pvp.attack(target);
                setTimeout(() => {
                    bot.pvp.stop();
                    // Run away in a random direction
                    bot.setControlState('sprint', true);
                    bot.setControlState('jump', true);
                    bot.setControlState('back', true);
                    setTimeout(() => { bot.clearControlStates(); currentTask = "idle"; }, 2000);
                }, 500);
            });
        } else {
            sendSensoryEvent(`I wanted to troll ${targetName} but I can't find them.`);
        }
    }
    else if (action === 'build_hut' || action === 'shelter') {
        currentTask = "building a shelter";
        sendSensoryEvent("I'm going to build a 3x3 dirt shelter to survive the night. Give me a moment.");
        
        try {
            const buildItem = bot.inventory.items().find(i =>
                i.name.includes('dirt') || i.name.includes('cobblestone') || i.name.includes('planks')
            );
            
            if (!buildItem || buildItem.count < 20) {
                sendSensoryEvent(`I need at least 20 blocks to build a shelter. I only have ${buildItem ? buildItem.count : 0}. I'll mine some dirt first.`);
                currentTask = "idle";
                return;
            }
            
            await bot.equip(buildItem, 'hand');
            
            const origin = bot.entity.position.floored();
            // 3x3 shelter: walls 3 high, leave front open (z+2) as a door
            const wallBlocks = [];
            for (let y = 0; y < 3; y++) {
                for (let x = -1; x <= 1; x++) {
                    for (let z = -1; z <= 1; z++) {
                        const isWall = (x === -1 || x === 1 || z === -1 || z === 1);
                        const isDoor = (z === 1 && x === 0 && y < 2);
                        const isRoof = (y === 2 && (x >= -1 && x <= 1) && (z >= -1 && z <= 1));
                        if (isRoof || (isWall && !isDoor)) {
                            wallBlocks.push({ x: origin.x + x, y: origin.y + y, z: origin.z + z });
                        }
                    }
                }
            }
            
            let placed = 0;
            let failed = 0;
            for (const pos of wallBlocks) {
                if (currentTask !== "building a shelter") break;
                try {
                    const existingBlock = bot.blockAt(new (require('vec3'))(pos.x, pos.y, pos.z));
                    if (existingBlock && existingBlock.name !== 'air') continue;
                    
                    // Find an adjacent solid block to place against
                    const neighbors = [
                        { x: 0, y: -1, z: 0 }, { x: 0, y: 1, z: 0 },
                        { x: 1, y: 0, z: 0 }, { x: -1, y: 0, z: 0 },
                        { x: 0, y: 0, z: 1 }, { x: 0, y: 0, z: -1 }
                    ];
                    let refBlock = null;
                    let faceVec = null;
                    for (const n of neighbors) {
                        const nb = bot.blockAt(new (require('vec3'))(pos.x + n.x, pos.y + n.y, pos.z + n.z));
                        if (nb && nb.name !== 'air') {
                            refBlock = nb;
                            faceVec = new (require('vec3'))(-n.x, -n.y, -n.z);
                            break;
                        }
                    }
                    
                    if (refBlock && faceVec) {
                        const inv = bot.inventory.items().find(i =>
                            i.name.includes('dirt') || i.name.includes('cobblestone') || i.name.includes('planks')
                        );
                        if (!inv) break;
                        await bot.equip(inv, 'hand');
                        
                        const goal = new goals.GoalNear(pos.x, pos.y, pos.z, 4);
                        bot.pathfinder.setGoal(goal, false);
                        await new Promise(r => {
                            const timeout = setTimeout(() => { r(); }, 8000);
                            bot.once('goal_reached', () => { clearTimeout(timeout); r(); });
                        });
                        
                        await bot.placeBlock(refBlock, faceVec);
                        placed++;
                    }
                } catch (placeErr) {
                    failed++;
                }
            }
            
            sendSensoryEvent(`Shelter done! Placed ${placed} blocks (${failed} failed). It's a basic 3x3 box with a doorway.`);
            currentTask = "idle";
            
        } catch (err) {
            sendSensoryEvent(`Build Error: ${err.message}`);
            currentTask = "idle";
        }
    }
    else if (action === 'session_goal') {
        const goalText = args.slice(1).join(' ');
        if (goalText) {
            sessionGoal = goalText;
            sessionGoalAchieved = false;
            sendSensoryEvent(`Session goal set: "${sessionGoal}". Let's do this!`);
        } else {
            sendSensoryEvent(sessionGoal ? `Current session goal: "${sessionGoal}"` : "No session goal set.");
        }
    }
    else if (action === 'goal_done' || action === 'goal_achieved') {
        if (sessionGoal) {
            sessionGoalAchieved = true;
            sendSensoryEvent(`Session goal achieved: "${sessionGoal}"! What should we do next?`);
        }
    }
    else if (action === 'stop') {
        bot.pathfinder.setGoal(null);
        bot.pvp.stop();
        bot.clearControlStates();
        currentTask = "idle";
        sendSensoryEvent("You stopped whatever you were doing.");
    }
    else if (action === 'parkour') {
        currentTask = "doing parkour";
        sendSensoryEvent("You started running around and jumping randomly like you're doing parkour.");
        let jumps = 0;
        const jumpInterval = setInterval(() => {
            if (currentTask !== "doing parkour") {
                clearInterval(jumpInterval);
                bot.clearControlStates();
                return;
            }
            // Pick random direction
            const dirs = ['forward', 'back', 'left', 'right'];
            bot.clearControlStates();
            bot.setControlState(dirs[Math.floor(Math.random() * dirs.length)], true);
            bot.setControlState('sprint', true);
            bot.setControlState('jump', true);
            
            setTimeout(() => bot.setControlState('jump', false), 200);
            jumps++;
            if (jumps > 12) {
                clearInterval(jumpInterval);
                bot.clearControlStates();
                currentTask = "idle";
                sendSensoryEvent("You got tired of parkour and stopped.");
            }
        }, 800);
    }
    else if (action === 'spin') {
        currentTask = "spinning";
        sendSensoryEvent("You started spinning rapidly in circles.");
        let spins = 0;
        const spinInterval = setInterval(() => {
            if (currentTask !== "spinning") {
                clearInterval(spinInterval);
                return;
            }
            bot.look(bot.entity.yaw + Math.PI / 4, bot.entity.pitch);
            spins++;
            if (spins > 20) {
                clearInterval(spinInterval);
                currentTask = "idle";
                sendSensoryEvent("You stopped spinning because you got dizzy.");
            }
        }, 100);
    }
    else if (action === 'wander') {
        currentTask = "wandering";
        sendSensoryEvent("You decided to just wander around aimlessly for a bit.");
        
        const defaultMove = new Movements(bot);
        defaultMove.canDig = true;
        bot.pathfinder.setMovements(defaultMove);
        
        let wanderCount = 0;
        const wanderInterval = setInterval(() => {
            if (currentTask !== "wandering") {
                clearInterval(wanderInterval);
                return;
            }
            wanderCount++;
            if (wanderCount > 10) { // Stop wandering after a while
                clearInterval(wanderInterval);
                currentTask = "idle";
                sendSensoryEvent("You got bored of wandering and stopped.");
                return;
            }
            
            // Pick a random block within a 15 block radius
            const x = bot.entity.position.x + (Math.random() * 30 - 15);
            const z = bot.entity.position.z + (Math.random() * 30 - 15);
            const y = bot.entity.position.y; // Keep roughly same y for target
            bot.pathfinder.setGoal(new goals.GoalNear(x, y, z, 2), true);
        }, 8000); // Try a new spot every 8 seconds
    }
    else if (action === 'hoard') {
        const itemName = args.slice(1).join('_');
        hoardItem(itemName);
    }
    else if (action === 'status') {
        const health = bot.health != null ? `${Math.round(bot.health)}/20` : "?";
        const food = bot.food != null ? `${bot.food}/20` : "?";
        const tod = bot.time ? getTimeOfDayString(bot.time.timeOfDay) : "unknown";
        const pos = bot.entity ? `(${Math.round(bot.entity.position.x)}, ${Math.round(bot.entity.position.y)}, ${Math.round(bot.entity.position.z)})` : "?";
        const inv = bot.inventory.items().map(i => `${i.count}x ${i.name}`).join(', ') || "empty";
        const goalStr = sessionGoal ? `"${sessionGoal}"${sessionGoalAchieved ? " (DONE)" : ""}` : "none";
        sendSensoryEvent(`[Full Status] HP: ${health} | Food: ${food} | Time: ${tod} | Pos: ${pos} | Task: ${currentTask} | Goal: ${goalStr} | Inventory: ${inv}`);
    }
    else if (action === 'equip') {
        const itemName = args.slice(1).join('_');
        const item = bot.inventory.items().find(i => i.name.includes(itemName));
        if (item) {
            await bot.equip(item, 'hand');
            sendSensoryEvent(`Equipped ${item.name}.`);
        } else {
            sendSensoryEvent(`I don't have any ${itemName} to equip.`);
        }
    }
    else if (action === 'eat') {
        const foodItem = bot.inventory.items().find(i => {
            const mcData = require('minecraft-data')(bot.version);
            const fd = mcData.foodsByName?.[i.name] || mcData.itemsByName?.[i.name];
            return fd && fd.foodPoints > 0;
        });
        if (foodItem) {
            await bot.equip(foodItem, 'hand');
            await bot.consume();
            sendSensoryEvent(`I ate a ${foodItem.name}. Yum.`);
        } else {
            sendSensoryEvent("I don't have any food to eat.");
        }
    }
    else if (action === 'look') {
        const targetName = args[1];
        if (targetName) {
            const player = Object.values(bot.players).find(p => p.username.toLowerCase() === targetName.toLowerCase());
            const target = player?.entity || bot.nearestEntity(e => e.name?.toLowerCase().includes(targetName.toLowerCase()));
            if (target) {
                await bot.lookAt(target.position.offset(0, target.height || 1, 0));
                sendSensoryEvent(`Looking at ${target.username || target.name}.`);
            } else {
                sendSensoryEvent(`Can't see ${targetName} anywhere.`);
            }
        }
    }
    else {
        sendSensoryEvent(`I don't know how to '${action}'. Available commands: say, follow, attack, mine, dance, inventory, build, drop, troll, build_hut, stop, parkour, spin, wander, hoard, session_goal, goal_done, status, equip, eat, look.`);
    }
});

async function hoardItem(itemName) {
    try {
        const mcData = require('minecraft-data')(bot.version);
        const item = mcData.itemsByName[itemName];

        if (!item) {
            sendSensoryEvent(`I don't know what a ${itemName} is.`);
            return;
        }

        const block = mcData.blocksByName[itemName];
        if (!block) {
            sendSensoryEvent(`I can't find any ${itemName} blocks to mine.`);
            return;
        }

        const blocks = bot.findBlocks({
            matching: block.id,
            maxDistance: 128,
            count: 1
        });

        if (blocks.length === 0) {
            sendSensoryEvent(`I couldn't find any ${itemName} nearby to hoard.`);
            return;
        }

        currentTask = `hoarding ${itemName}`;
        sendSensoryEvent(`I'm going to collect some ${itemName} for my hoard.`);

        const targets = [];
        for (let i = 0; i < blocks.length; i++) {
            targets.push(bot.blockAt(blocks[i]));
        }

        bot.collectBlock.collect(targets, err => {
            if (err) {
                sendSensoryEvent(`I ran into a problem while hoarding ${itemName}: ${err.message}`);
            } else {
                sendSensoryEvent(`I successfully hoarded some ${itemName}!`);
                // Let the python side know we have a new item
                skikaiClient.send(`HOARD_ADD ${itemName} 1`, SKIKAI_PORT, SKIKAI_HOST);
            }
            currentTask = "idle";
        });

    } catch (err) {
        sendSensoryEvent(`Error trying to hoard: ${err.message}`);
        currentTask = "idle";
    }
}

botServer.bind(BOT_PORT, () => {
    console.log(`[Minecraft Bot Listener] Active on UDP ${BOT_PORT}`);
});
