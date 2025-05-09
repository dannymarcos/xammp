/**
 * Trading Bot Component JavaScript
 * Handles the functionality for the trading bot component
 * 
 * This refactored version separates UI concerns from business logic
 * and makes it easier to modify the UI independently.
 */

// ===== STATE MANAGEMENT =====
// Global state variables
const state = {
    isBotRunning: false,
    configInputIds: ["bot-symbol", "bot-timeframe", "bot-amount", "bot-trading-mode"],
    uiElements: {
        toggleButton: "toggle-bot",
        statusBadge: "bot-status",
        tradeHistoryBody: "trade-history-body"
    },
    timeframeIntervals: {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400
    },
    refreshInterval: 10000, // 10 seconds
    lastTradeTimestamp: null, // Track the timestamp of the newest trade
    newTradeHighlightDuration: 30000 // Highlight new trades for 30 seconds (30000ms)
};

// ===== UI HELPER FUNCTIONS =====

/**
 * Helper function to get translated text
 * Falls back to the original text if translation function is not available
 * @param {string} text - The text to translate
 * @returns {string} - The translated text
 */
function getTranslatedText(text) {
    return (typeof window._ === 'function') ? window._(text) : text;
}

/**
 * Gets a DOM element by ID with error handling
 * @param {string} id - The element ID
 * @returns {HTMLElement|null} - The DOM element or null if not found
 */
function getElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.error(`Element with ID "${id}" not found`);
    }
    return element;
}

/**
 * Updates the toggle button appearance based on status
 * @param {string} status - The current status of the bot
 */
function updateToggleButton(status) {
    const button = getElement(state.uiElements.toggleButton);
    if (!button) return;
    
    // Reset all possible classes first
    button.classList.remove("btn-success", "btn-danger", "btn-warning");
    button.disabled = false;
    
    // Set appropriate classes and text based on status
    if (status.includes("running")) {
        button.classList.add("btn-danger");
        button.innerHTML = `<i class="bi bi-stop-fill"></i> ${getTranslatedText('Stop Bot')}`;
    } 
    else if (status.includes("loading")) {
        button.classList.add("btn-warning");
        button.innerHTML = `<i class="bi bi-hourglass-split"></i> ${getTranslatedText('Loading...')}`;
        button.disabled = true;
    }
    else {
        // Default state (stopped or error)
        button.classList.add("btn-success");
        button.innerHTML = `<i class="bi bi-play-fill"></i> ${getTranslatedText('Start Bot')}`;
    }
}

/**
 * Updates the status badge appearance based on status
 * @param {string} status - The current status of the bot
 */
function updateStatusBadge(status) {
    const badge = getElement(state.uiElements.statusBadge);
    if (!badge) return;
    
    // Reset all possible classes first
    badge.classList.remove("bg-success", "bg-secondary", "bg-warning", "bg-danger");
    
    // Set appropriate classes and text based on status
    if (status.includes("running")) {
        badge.classList.add("bg-success");
        badge.textContent = getTranslatedText('Running');
    } 
    else if (status.includes("loading")) {
        badge.classList.add("bg-warning");
        badge.textContent = getTranslatedText('Processing...');
    }
    else if (status.includes("error")) {
        badge.classList.add("bg-danger");
        badge.textContent = getTranslatedText('Error');
    }
    else {
        // Default state (stopped)
        badge.classList.add("bg-secondary");
        badge.textContent = getTranslatedText('Stopped');
    }
}

/**
 * Updates the entire UI based on the bot's status
 * @param {string} status - The current status of the bot (running, stopped, loading, error)
 */
function updateBotUI(status) {
    // Update individual UI components
    console.log({status});
    updateToggleButton(status.bot_status);
    updateStatusBadge(status.bot_status);
    updateErrorMessage(status.last_error_message || "");
    
    // Update state and configuration inputs
    if (status.bot_status.includes("running")) {
        state.isBotRunning = true;
        toggleConfigInputs(false);
    } 
    else if (!status.bot_status.includes("loading")) {
        state.isBotRunning = false;
        toggleConfigInputs(true);
    }
}

/**
 * Toggles the enabled state of bot configuration inputs
 * @param {boolean} enabled - Whether the inputs should be enabled
 */
function toggleConfigInputs(enabled) {
    state.configInputIds.forEach(id => {
        const input = getElement(id);
        if (input) {
            input.disabled = !enabled;
        }
    });
}

/**
 * Shows an error message to the user
 * @param {string} message - The error message to display
 */
function showError(message) {
    alert(getTranslatedText(message));
    console.error(message);
}

// ===== API INTERACTION FUNCTIONS =====

/**
 * Fetches the current status of the bot
 * @returns {Promise<string>} - The current status of the bot
 */
async function getBotStatus() {
    try {
        const response = await fetch("/bot/status");
        const data = await response.json();
        return {
            bot_status: data.bot_status,
            last_error_message: data.last_error_message
        };
    } catch (error) {
        console.error("Error fetching bot status:", error);
        return {
            bot_status: "error",
            last_error_message: getTranslatedText("Error fetching bot status")
        };
    }
}

/**
 * Updates the last error message in the UI
 * @param {string} message - The error message to display
 */
function updateErrorMessage(message) {
    const errorMessageSpan = getElement("last_error_message");
    if (!errorMessageSpan) return;
    errorMessageSpan.textContent = getTranslatedText(message);
}

/**
 * Fetches the trade history
 * @returns {Promise<Array>} - The trade history
 */
async function getTrades() {
    try {
        const response = await fetch("/trades?by=bot");
        const data = await response.json();
        return data.trades || [];
    } catch (error) {
        console.error("Error fetching trades:", error);
        return [];
    }
}

/**
 * Starts the trading bot
 * @returns {Promise<void>}
 */
async function startBot() {
    try {
        // Get configuration values
        const config = getBotConfig();
        if (!config) return;

        console.log({bot_config: config});
        
        // Send request to start the bot
        const response = await fetch("/bot/start_bot_trading", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.error) {
            showError("Error starting bot: " + data.error);
            throw new Error(data.error);
        }
        
        // Update UI with the new status
        updateBotUI(data);
        
    } catch (error) {
        console.error("Error starting trading bot:", error);
        updateBotUI({bot_status: "error"});
    }
}

/**
 * Stops the trading bot
 * @returns {Promise<void>}
 */
async function stopBot() {
    try {
        // Send request to stop the bot
        const response = await fetch("/bot/stop_bot_trading", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        
        const data = await response.json();
        
        if (data.error) {
            showError("Error stopping bot: " + data.error);
            throw new Error(data.error);
        }
        
        // Update UI with the new status
        updateBotUI(data);
        
    } catch (error) {
        console.error("Error stopping trading bot:", error);
        updateBotUI({bot_status: "error"});
    }
}

// ===== HELPER FUNCTIONS =====

/**
 * Gets and validates the bot configuration from the UI
 * @returns {Object|null} - The bot configuration or null if validation fails
 */
function getBotConfig() {
    const symbol = getElement("bot-symbol")?.value;
    const timeframe = getElement("bot-timeframe")?.value;
    const amount = getElement("bot-amount")?.value;
    const tradingMode = getElement("bot-trading-mode")?.value;
    // Advanced settings
    const maxActiveTrades = getElement("bot-max-active-trades")?.value;
    const stopLossPct = getElement("bot-stop-loss-pct")?.value;
    const takeProfitPct = getElement("bot-take-profit-pct")?.value;
    
    // Validate inputs
    if (!symbol || !timeframe || !amount || amount <= 0) {
        showError("Please fill in all configuration fields correctly.");
        return null;
    }
    
    // Get interval in seconds from the timeframe
    const interval = state.timeframeIntervals[timeframe] || 3600; // Default to 1 hour
    
    return {
        symbol: symbol,
        timeframe: timeframe,
        amount: parseFloat(amount),
        interval: interval,
        trading_mode: tradingMode,
        max_active_trades: maxActiveTrades,
        stop_loss_pct: stopLossPct,
        take_profit_pct: takeProfitPct
    };
}

/**
 * Renders the trade history in the table
 * @param {Array} trades - The trades to render
 */
function renderTrades(trades) {
    const tradeHistoryBody = getElement(state.uiElements.tradeHistoryBody);
    if (!tradeHistoryBody) return;
    
    // Clear existing rows
    tradeHistoryBody.innerHTML = "";
    
    // If no trades, show a message
    if (!trades || trades.length === 0) {
        const emptyRow = document.createElement("tr");
        emptyRow.innerHTML = `<td colspan="6" class="text-center">${getTranslatedText("No trades found")}</td>`;
        tradeHistoryBody.appendChild(emptyRow);
        return;
    }
    
    // Sort trades by timestamp (newest first)
    const sortedTrades = [...trades].sort((a, b) => {
        const timestampA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
        const timestampB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
        return timestampB - timestampA; // Descending order (newest first)
    });
    
    // Get the newest trade timestamp
    const newestTrade = sortedTrades[0];
    const newestTimestamp = newestTrade && newestTrade.timestamp 
        ? new Date(newestTrade.timestamp).getTime() 
        : 0;
    
    // Check if we have a new trade
    const hasNewTrade = state.lastTradeTimestamp !== null && 
                        newestTimestamp > state.lastTradeTimestamp;
    
    // Update the last trade timestamp
    if (newestTimestamp > 0 && (state.lastTradeTimestamp === null || newestTimestamp > state.lastTradeTimestamp)) {
        state.lastTradeTimestamp = newestTimestamp;
    }
    
    // Create document fragment for better performance
    const fragment = document.createDocumentFragment();
    
    // Add each trade to the table
    sortedTrades.forEach((trade, index) => {
        const row = document.createElement("tr");
        
        // Format timestamp if it exists
        const tradeTimestamp = trade.timestamp ? new Date(trade.timestamp).getTime() : 0;
        const formattedDate = trade.timestamp 
            ? new Date(trade.timestamp).toLocaleString() 
            : 'N/A';
        
        // Format price as currency
        const formattedPrice = trade.price 
            ? parseFloat(trade.price).toFixed(2) 
            : '0.00';
        
        // Color direction text
        const directionClass = trade.order_direction === 'buy' 
            ? 'text-success' 
            : 'text-danger';
        
        // Determine if this is a new trade (newest trade or within the last 30 seconds)
        const isNewest = index === 0;
        const isRecent = tradeTimestamp > 0 && 
                         Date.now() - tradeTimestamp < state.newTradeHighlightDuration;
        
        // Add highlight class if this is the newest trade
        if (isNewest && hasNewTrade) {
            row.classList.add('table-success', 'new-trade-highlight');
            
            // Add animation class that will fade out
            row.classList.add('new-trade-animation');
            
            // Remove the animation class after the animation completes
            setTimeout(() => {
                const rowElement = document.querySelector('.new-trade-animation');
                if (rowElement) {
                    rowElement.classList.remove('new-trade-animation');
                }
            }, 3000); // 3 seconds animation
        }
        // Add a softer highlight for recent trades that aren't the newest
        else if (isRecent && !isNewest) {
            row.classList.add('table-info');
        }

        const actual_profit = trade.actual_profit || 0;
        const actual_profit_usd = trade.actual_profit_in_usd || 0;
        
        // Add badge for newest trade
        const newestBadge = isNewest && hasNewTrade 
            ? `<span class="badge bg-success ms-2">${getTranslatedText('New')}</span>` 
            : '';
        row.innerHTML = `
            <td>${trade.order_type || 'N/A'} ${newestBadge}</td>
            <td>${formattedDate}</td>
            <td class="${directionClass}">${trade.order_direction?.toUpperCase() || ''}</td>
            <td>${trade.symbol || ''}</td>
            <td class="text-end">${trade.price ? parseFloat(trade.price).toFixed(2) : '0.00'}</td>
            <td class="text-end">${trade.volume ? parseFloat(trade.volume).toFixed(4) : '0.0000'}</td>
            <td class="text-end ${trade.status === 'closed' ? 'text-gray' : 'text-success'}">${trade.status || ''}</td>
            <td class="text-end">${trade.stop_loss ? parseFloat(trade.stop_loss).toFixed(2) : '-'}</td>
            <td class="text-end">${trade.take_profit ? parseFloat(trade.take_profit).toFixed(2) : '-'}</td>
            <td class="text-end ${actual_profit > 0 ? 'text-success' : 'text-danger'}">${actual_profit}</td>
            <td class="text-end ${actual_profit_usd > 0 ? 'text-success' : 'text-danger'}">${actual_profit_usd}$</td>
            <td>${trade.order_close_condition || ''}</td>
            <td title="${trade.comment || ''}">${trade.comment ? trade.comment.substring(0, 15) + (trade.comment.length > 15 ? '...' : '') : ''}</td>
        `;
        
        fragment.appendChild(row);
    });
    
    tradeHistoryBody.appendChild(fragment);
    
    // Add CSS for the animation if it doesn't exist yet
    if (!document.getElementById('trade-highlight-styles')) {
        const styleElement = document.createElement('style');
        styleElement.id = 'trade-highlight-styles';
        styleElement.textContent = `
            .new-trade-highlight {
                position: relative;
            }
            .new-trade-animation {
                animation: highlightFade 3s ease-out;
            }
            @keyframes highlightFade {
                0% { background-color: rgba(25, 135, 84, 0.7); }
                100% { background-color: rgba(25, 135, 84, 0.2); }
            }
        `;
        document.head.appendChild(styleElement);
    }
}

/**
 * Toggles the bot state (start/stop)
 * @returns {Promise<void>}
 */
async function toggleBot() {
    // Show loading state
    updateBotUI({
        bot_status: "loading",});
    
    // Start or stop the bot based on current state
    if (state.isBotRunning) {
        await stopBot();
    } else {
        await startBot();
    }
}

// ===== INITIALIZATION =====

/**
 * Initializes the trading bot component
 */
async function initTradingBot() {
    const toggleBotButton = getElement(state.uiElements.toggleButton);
    if (!toggleBotButton) return;
    
    // Get current bot status and update UI
    const status = await getBotStatus();
    updateBotUI(status);
    
    // Set up event listener for the toggle button
    toggleBotButton.addEventListener("click", toggleBot);
    
    // Fetch and render initial trade history
    const trades = await getTrades("bot");
    renderTrades(trades);
    
    // Set up interval to refresh trade history if bot is running
    setInterval(async () => {
        if (state.isBotRunning) {
            console.log("Refreshing trade history...");
            const trades = await getTrades();
            renderTrades(trades);
        }
    }, state.refreshInterval);
}

// Initialize when the DOM is loaded
document.addEventListener("DOMContentLoaded", initTradingBot);
