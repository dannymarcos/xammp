// obsoleto

class ExchangeComponentManager {
    constructor(exchangeId) {
        if (!exchangeId) {
            throw new Error("Exchange ID is required for ExchangeComponentManager.");
        }
        this.exchangeId = exchangeId;
        this.priceUpdateInterval = null;
        this.currentSymbol = null; // Stores the symbol currently being tracked

        // Bind methods to ensure 'this' context is correct if they are used as callbacks
        this._performPriceUpdate = this._performPriceUpdate.bind(this);
    }

    /**
     * Fetches the price for a given symbol.
     * THIS IS A PLACEHOLDER. Replace with your actual API call.
     * @param {string} symbol - The trading symbol (e.g., "BTC/USD:USD").
     * @returns {Promise<string>} - A promise that resolves to the price as a string.
     */
    async fetchPrice(symbol) {
        // console.log(`Fetching price for ${symbol} on exchange ${this.exchangeId}... (Placeholder)`);
        try {
            const response = await fetch(`/get_symbol_price?symbol=${encodeURIComponent(symbol)}&exchange=${this.exchangeId}`);
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            const data = await response.json();
            return data.price;
        } catch (error) {
            // console.error(`Failed to fetch price for ${symbol}:`, error);
            throw error;
        }
    }

    /**
     * Updates the price display in the DOM.
     * @param {string} price - The price to display. Can also be "N/A" or "Error".
     */
    updatePriceDisplay(price) {
        const priceElementId = `symbol-price-${this.exchangeId}`;
        const priceElement = document.getElementById(priceElementId);

        if (priceElement) {
            priceElement.textContent = price;
        } else {
            console.warn(`Price display element '${priceElementId}' not found in the DOM.`);
        }
    }

    /**
     * Core logic for a single price update cycle.
     * Retrieves symbol, fetches price, and updates display.
     * @private
     */
    async _performPriceUpdate() {
        this.currentSymbol = localStorage.getItem("symbol-original");

        if (!this.currentSymbol) {
            console.warn(`'symbol-original' not found in localStorage for exchange '${this.exchangeId}'. Price updates paused.`);
            this.updatePriceDisplay("N/A");
            // Optionally stop the interval if the symbol is consistently missing
            // this.stopPriceUpdater(); 
            return;
        }

        try {
            const price = await this.fetchPrice(this.currentSymbol);
            this.updatePriceDisplay(price);
        } catch (error) {
            console.error(`Error fetching price for ${this.currentSymbol} on ${this.exchangeId}:`, error.message);
            this.updatePriceDisplay("Error");
        }
    }

    /**
     * Starts the periodic price updater.
     * Fetches and displays the price immediately, then every 10 seconds.
     */
    startPriceUpdater() {
        if (this.priceUpdateInterval) {
            console.log(`Price updater is already running for exchange '${this.exchangeId}'.`);
            return;
        }

        this.currentSymbol = localStorage.getItem("symbol-original");
        if (!this.currentSymbol) {
            console.warn(`Cannot start price updater for exchange '${this.exchangeId}': 'symbol-original' not found in localStorage.`);
            this.updatePriceDisplay("N/A"); // Show N/A if no symbol at start
            return;
        }
        
        console.log(`Starting price updater for symbol '${this.currentSymbol}' on exchange '${this.exchangeId}'.`);
        
        // Perform an initial update immediately
        this._performPriceUpdate(); 
        
        // Set up the interval for subsequent updates
        this.priceUpdateInterval = setInterval(this._performPriceUpdate, 10000); // 10000 ms = 10 seconds
    }

    /**
     * Stops the periodic price updater.
     */
    stopPriceUpdater() {
        if (this.priceUpdateInterval) {
            clearInterval(this.priceUpdateInterval);
            this.priceUpdateInterval = null;
            console.log(`Stopped price updater for symbol '${this.currentSymbol || 'N/A'}' on exchange '${this.exchangeId}'.`);
        }
    }

    /**
     * Call this method if the 'symbol-original' in localStorage might have changed,
     * to ensure the updater tracks the correct symbol.
     */
    handleSymbolChange() {
        const newSymbol = localStorage.getItem("symbol-original");
        if (newSymbol !== this.currentSymbol) {
            console.log(`Symbol changed from '${this.currentSymbol}' to '${newSymbol}' for exchange '${this.exchangeId}'. Restarting updater.`);
            this.stopPriceUpdater(); // Stop current updates
            if (newSymbol) {
                this.currentSymbol = newSymbol; // Update internal tracking
                this.startPriceUpdater();     // Start with the new symbol
            } else {
                this.currentSymbol = null;
                this.updatePriceDisplay("N/A"); // No symbol, display N/A
            }
        }
    }
}

// const futuresExchangeManager = new ExchangeComponentManager('futures');
// futuresExchangeManager.startPriceUpdater();

/*
// Example Usage (typically in another JS file where you initialize your page components):

// 1. When your page loads, or a specific component initializes:
// const futuresExchangeManager = new ExchangeComponentManager('futures'); // Replace 'futures' with actual exchangeId
// futuresExchangeManager.startPriceUpdater();

// const spotExchangeManager = new ExchangeComponentManager('spot');
// spotExchangeManager.startPriceUpdater();


// 2. To handle changes to 'symbol-original' in localStorage (e.g., user selects a new symbol):
// You might have a global function or event listener that calls handleSymbolChange:

// function onSymbolChangedByUser() {
//     // Assuming futuresExchangeManager and spotExchangeManager are accessible
//     if (window.futuresExchangeManager) {
//         window.futuresExchangeManager.handleSymbolChange();
//     }
//     if (window.spotExchangeManager) {
//         window.spotExchangeManager.handleSymbolChange();
//     }
// }

// Or, listen to storage events (more advanced, might have cross-tab implications):
// window.addEventListener('storage', (event) => {
//    if (event.key === 'symbol-original') {
//        onSymbolChangedByUser(); // Or directly call manager.handleSymbolChange()
//    }
// });

// Make sure the HTML element exists, e.g.:
// <span id="symbol-price-futures">--.--</span>
// <span id="symbol-price-spot">--.--</span>
*/
