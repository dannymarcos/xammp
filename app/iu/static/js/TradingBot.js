/**
 * Trading Bot Component JavaScript
 * Reusable class for trading bot instances
 */
export class TradingBot {
	constructor(botId) {
		this.botId = botId;
		this.container = document.getElementById(botId);

		// Instance state
		this.state = {
			isBotRunning: false,
			timeframeIntervals: {
				"1m": 60,
				"5m": 300,
				"15m": 900,
				"30m": 1800,
				"1h": 3600,
				"4h": 14400,
				"1d": 86400,
			},
			refreshInterval: 10000,
			lastTradeTimestamp: null,
			newTradeHighlightDuration: 30000,
		};

		// Cache DOM elements
		this.uiElements = {
			toggleButton: this.container.querySelector(".toggle-bot"),
			statusBadge: this.container.querySelector(".bot-status"),
			tradeHistoryBody: this.container.querySelector(".trade-history-body"),
			lastErrorMessage: this.container.querySelector(".last-error-message"),
			selectedStrategy: this.container.querySelector(".strategy-list"),
		};

		// Config inputs
		this.configInputs = this.container.querySelectorAll(".bot-config-input");
	}

	/**
	 * Gets translated text
	 * @param {string} text - Text to translate
	 * @returns {string} Translated text
	 */
	getTranslatedText(text) {
		return typeof window._ === "function" ? window._(text) : text;
	}

	/**
	 * Updates the toggle button appearance
	 * @param {string} status - Current bot status
	 */
	updateToggleButton(status) {
		const button = this.uiElements.toggleButton;
		if (!button) return;

		button.classList.remove("btn-success", "btn-danger", "btn-warning");
		button.disabled = false;

		if (status.includes("running")) {
			button.classList.add("btn-danger");
			button.innerHTML = `<i class="bi bi-stop-fill"></i> ${this.getTranslatedText(
				"Stop Bot"
			)}`;
		} else if (status.includes("loading")) {
			button.classList.add("btn-warning");
			button.innerHTML = `<i class="bi bi-hourglass-split"></i> ${this.getTranslatedText(
				"Loading..."
			)}`;
			button.disabled = true;
		} else {
			button.classList.add("btn-success");
			button.innerHTML = `<i class="bi bi-play-fill"></i> ${this.getTranslatedText(
				"Start Bot"
			)}`;
		}
	}

	/**
	 * Updates the status badge
	 * @param {string} status - Current bot status
	 */
	updateStatusBadge(status) {
		const badge = this.uiElements.statusBadge;
		if (!badge) return;

		badge.classList.remove(
			"bg-success",
			"bg-secondary",
			"bg-warning",
			"bg-danger"
		);

		if (status.includes("running")) {
			badge.classList.add("bg-success");
			badge.textContent = this.getTranslatedText("Running");
		} else if (status.includes("loading")) {
			badge.classList.add("bg-warning");
			badge.textContent = this.getTranslatedText("Processing...");
		} else if (status.includes("error")) {
			badge.classList.add("bg-danger");
			badge.textContent = this.getTranslatedText("Error");
		} else {
			badge.classList.add("bg-secondary");
			badge.textContent = this.getTranslatedText("Stopped");
		}
	}

	/**
	 * Updates the entire UI based on the bot's status
	 * @param {Object} status - Current bot status {bot_status, last_error_message}
	 */
	updateBotUI(status) {
		this.updateToggleButton(status.bot_status);
		this.updateStatusBadge(status.bot_status);
		this.updateErrorMessage(status.last_error_message || "");

		if (status.bot_status.includes("running")) {
			this.state.isBotRunning = true;
			this.toggleConfigInputs(false);
		} else if (!status.bot_status.includes("loading")) {
			this.state.isBotRunning = false;
			this.toggleConfigInputs(true);
		}
	}

	/**
	 * Toggles configuration inputs enabled state
	 * @param {boolean} enabled - Whether inputs should be enabled
	 */
	toggleConfigInputs(enabled) {
		this.configInputs.forEach(input => {
			input.disabled = !enabled;
		});
	}

	/**
	 * Shows an error message
	 * @param {string} message - Error message to display
	 */
	showError(message) {
		alert(this.getTranslatedText(message));
		console.error(message);
	}

	/**
	 * Fetches the current bot status
	 * @returns {Promise<Object>} - {bot_status, last_error_message}
	 */
	async getBotStatus() {
		try {
			const response = await fetch(`/bot/status?bot_id=${this.botId}`);
			const data = await response.json();
			return {
				bot_status: data.bot_status,
				last_error_message: data.last_error_message,
			};
		} catch (error) {
			console.error("Error fetching bot status:", error);
			return {
				bot_status: "error",
				last_error_message: this.getTranslatedText("Error fetching bot status"),
			};
		}
	}

	/**
	 * Updates the error message display
	 * @param {string} message - Error message to display
	 */
	updateErrorMessage(message) {
		if (this.uiElements.lastErrorMessage) {
			this.uiElements.lastErrorMessage.textContent =
				this.getTranslatedText(message);
		}
	}

	/**
	 * Fetches trade history for this bot
	 * @returns {Promise<Array>} - Array of trades
	 */
	async getTrades() {
		try {
			const response = await fetch(`/trades?by=bot&bot_id=${this.botId}`);
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
	async startBot() {
		try {
			const config = this.getBotConfig();
			if (!config) return;

      console.info(`Starting trading bot ${this.botId} with config:`, config);

			const response = await fetch("/bot/start_bot_trading", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ ...config, bot_id: this.botId }),
			});

			const data = await response.json();

			if (data.error) {
				this.showError("Error starting bot: " + data.error);
				throw new Error(data.error);
			}

			this.updateBotUI(data);
		} catch (error) {
			console.error("Error starting trading bot:", error);
			this.updateBotUI({ bot_status: "error" });
		}
	}

	/**
	 * Stops the trading bot
	 * @returns {Promise<void>}
	 */
	async stopBot() {
		try {
			const response = await fetch("/bot/stop_bot_trading", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ bot_id: this.botId }),
			});

			const data = await response.json();

			if (data.error) {
				this.showError("Error stopping bot: " + data.error);
				throw new Error(data.error);
			}

			this.updateBotUI(data);
		} catch (error) {
			console.error("Error stopping trading bot:", error);
			this.updateBotUI({ bot_status: "error" });
		}
	}

	// ===== HELPER FUNCTIONS =====

	/**
	 * Gets and validates bot configuration from UI
	 * @returns {Object|null} - Configuration object or null if invalid
	 */
	getBotConfig() {
		const config = {};

		// Get values from inputs
		this.configInputs.forEach(input => {
			const name = input.getAttribute("name");
			if (name) {
				config[name.replace("-", "_")] = input.value;
			}
		});

		// Validate required fields
		if (
			!config.symbol ||
			!config.timeframe ||
			!config.amount ||
			config.amount <= 0
		) {
			this.showError("Please fill in all configuration fields correctly.");
			return null;
		}

		// FIXME: remove this to handle better select values
		config.symbol = config.exchange === "bingx" ? "BTC/USDT" : config.symbol;

		// if there is a selected strategy, add it to the config
		if (this.uiElements.selectedStrategy) 
			config.strategy_id = this.uiElements.selectedStrategy.value;

		// Add interval from timeframe
		config.interval = this.state.timeframeIntervals[config.timeframe] || 3600;

		return config;
	}

	/**
	 * Renders trade history in the table
	 * @param {Array} trades - Trades to render
	 */
	renderTrades(trades) {
		const tradeHistoryBody = this.uiElements.tradeHistoryBody;
		if (!tradeHistoryBody) return;

		// Clear existing rows
		tradeHistoryBody.innerHTML = "";

		// If no trades, show a message
		if (!trades || trades.length === 0) {
			const emptyRow = document.createElement("tr");
			emptyRow.innerHTML = `<td colspan="6" class="text-center">${this.getTranslatedText(
				"No trades found"
			)}</td>`;
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
		const newestTimestamp =
			newestTrade && newestTrade.timestamp
				? new Date(newestTrade.timestamp).getTime()
				: 0;

		// Check if we have a new trade
		const hasNewTrade =
			this.state.lastTradeTimestamp !== null &&
			newestTimestamp > this.state.lastTradeTimestamp;

		// Update the last trade timestamp
		if (
			newestTimestamp > 0 &&
			(this.state.lastTradeTimestamp === null ||
				newestTimestamp > this.state.lastTradeTimestamp)
		) {
			this.state.lastTradeTimestamp = newestTimestamp;
		}

		// Create document fragment for better performance
		const fragment = document.createDocumentFragment();

		// Add each trade to the table
		sortedTrades.forEach((trade, index) => {
			const row = document.createElement("tr");

			// Format timestamp if it exists
			const tradeTimestamp = trade.timestamp
				? new Date(trade.timestamp).getTime()
				: 0;
			const formattedDate = trade.timestamp
				? new Date(trade.timestamp).toLocaleString()
				: "N/A";

			// Format price as currency
			const formattedPrice = trade.price
				? parseFloat(trade.price).toFixed(2)
				: "0.00";

			// Color direction text
			const directionClass =
				trade.order_direction === "buy" ? "text-success" : "text-danger";

			// Determine if this is a new trade (newest trade or within the last 30 seconds)
			const isNewest = index === 0;
			const isRecent =
				tradeTimestamp > 0 &&
				Date.now() - tradeTimestamp < this.state.newTradeHighlightDuration;

			// Add highlight class if this is the newest trade
			if (isNewest && hasNewTrade) {
				row.classList.add("table-success", "new-trade-highlight");

				// Add animation class that will fade out
				row.classList.add("new-trade-animation");

				// Remove the animation class after the animation completes
				setTimeout(() => {
					const rowElement = this.container.querySelector(
						".new-trade-animation"
					);
					if (rowElement) {
						rowElement.classList.remove("new-trade-animation");
					}
				}, 3000); // 3 seconds animation
			}
			// Add a softer highlight for recent trades that aren't the newest
			else if (isRecent && !isNewest) {
				row.classList.add("table-info");
			}

			const actual_profit = trade.actual_profit || 0;
			const actual_profit_usd = trade.actual_profit_in_usd || 0;

			// Add badge for newest trade
			const newestBadge =
				isNewest && hasNewTrade
					? `<span class="badge bg-success ms-2">${this.getTranslatedText(
							"New"
					  )}</span>`
					: "";
			row.innerHTML = `
                <td>${trade.order_type || "N/A"} ${newestBadge}</td>
                <td>${formattedDate}</td>
                <td class="${directionClass}">${
				trade.order_direction?.toUpperCase() || ""
			}</td>
                <td>${trade.symbol || ""}</td>
                <td class="text-end">${
									trade.price ? parseFloat(trade.price).toFixed(2) : "0.00"
								}</td>
                <td class="text-end">${
									trade.volume ? parseFloat(trade.volume).toFixed(4) : "0.0000"
								}</td>
                <td class="text-end ${
									trade.status === "closed" ? "text-gray" : "text-success"
								}">${trade.status || ""}</td>
                <td class="text-end ${
									actual_profit > 0 ? "text-success" : "text-danger"
								}">${actual_profit || 0}</td>
                <td class="text-end ${
									actual_profit_usd > 0 ? "text-success" : "text-danger"
								}">${actual_profit_usd || 0}$</td>
                <td>${trade.trading_mode}</td>
                <td>${trade.exchange}</td>
                <td title="${trade.comment || ""}">${
				trade.comment
					? trade.comment.substring(0, 15) +
					  (trade.comment.length > 15 ? "..." : "")
					: ""
			}</td>
            `;

			fragment.appendChild(row);
		});

		tradeHistoryBody.appendChild(fragment);

		// Add CSS for the animation if it doesn't exist yet
		if (!document.getElementById("trade-highlight-styles")) {
			const styleElement = document.createElement("style");
			styleElement.id = "trade-highlight-styles";
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
	 * Toggles bot state (start/stop)
	 * @returns {Promise<void>}
	 */
	async toggleBot() {
		// Show loading state
		this.updateBotUI({
			bot_status: "loading",
		});

		// Start or stop based on current state
		if (this.state.isBotRunning) {
			await this.stopBot();
		} else {
			await this.startBot();
		}
	}

	/**
	 * Initializes the trading bot instance
	 */
	async init() {
		if (!this.uiElements.toggleButton) return;

		console.info(`Initializing trading bot ${this.botId}...`);

		// Get current status and update UI
		const status = await this.getBotStatus();
		this.updateBotUI(status);

		// Set up event listener
		this.uiElements.toggleButton.addEventListener("click", () =>
			this.toggleBot()
		);

		// Fetch and render initial trade history
		const trades = await this.getTrades();
		this.renderTrades(trades);

		// Set up refresh interval
		setInterval(async () => {
			if (this.state.isBotRunning) {
				console.log("Refreshing trade history...");
				const trades = await this.getTrades();
				this.renderTrades(trades);
			}
		}, this.state.refreshInterval);
	}
}
