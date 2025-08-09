 // --- Configuration ---
const API_ENDPOINTS = {
    getBalance: '/get_account_balance',
    addOrder: '/add_order',
    getSymbolPrice: '/get_symbol_price',
    getUserTrades: '/trades',
};

    // Get settings from localStorage, fallback to defaults
const getTradingSymbol = () => localStorage.getItem('symbol') || 'XBTUSD';
const getTradingMode = () => localStorage.getItem('method') || 'spot';

 // --- Helper Functions ---
function showAlert(message, type = 'info') {
    // Simple alert for now, can be replaced with a nicer notification system
    alert(`[${type.toUpperCase()}] ${message}`);
}


function renderUserTrades(trades) {
    const tbody = document.getElementById('user-trade-history-body');
    
    if (!tbody) {
        console.error('Trade history table body not found');
        return;
    }
    
    if (!trades || trades.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="11" class="text-center">No trades found</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = trades.map(trade => {
        const directionClass = trade.order_direction === 'buy' ? 'text-success' : 'text-danger';
        const formattedDate = trade.timestamp ? new Date(trade.timestamp).toLocaleString() : 'N/A';
        
        return `
        <tr>
            <td>${formattedDate}</td>
            <td>${trade.order_type || 'N/A'}</td>
            <td class="${directionClass}">${trade.order_direction?.toUpperCase() || ''}</td>
            <td>${trade.symbol || ''}</td>
            <td class="text-end">${trade.price ? parseFloat(trade.price).toFixed(2) : '0.00'}</td>
            <td class="text-end">${trade.volume ? parseFloat(trade.volume).toFixed(8) : '0.00000000'}</td>
            <td>${trade.status || ''}</td>
            <td>${trade.exchange || ''}</td>
            <td>${trade.stop_loss || ''}</td>
            <td>${trade.take_profit || ''}</td>
            <td>${trade.leverage || ''}</td>
            <td title="${trade.comment || ''}">${trade.comment ? trade.comment.substring(0, 15) + (trade.comment.length > 15 ? '...' : '') : ''}</td>
        </tr>
        `;
    }).join('');
}

function updateAvailableOptionsToBuy(balance) {
    const availableCurrencies = Object.keys(balance).filter(currency => currency !== 'ZUSD' && currency !== 'XXBT');
    const buyCurrencySelect = document.getElementById('buy-currency'); // e.g., USDT
    buyCurrencySelect.innerHTML = availableCurrencies.map(currency => `<option value="${currency}">${currency}</option>`).join('');
    
    // update for first render
    updateCurrentAvailableBalance(balance[buyCurrencySelect.value], buyCurrencySelect.value);  
    
    // add event listener
    buyCurrencySelect.addEventListener('change', async (e) => {
        const currentCurrentSymbol = e.target.value;
        const balance = await fetchAccountBalance();
        const currentCurrentSymbolBalance = balance[currentCurrentSymbol];
        updateCurrentAvailableBalance(currentCurrentSymbolBalance, currentCurrentSymbol);
    });
}

function updateAvailableOptionsToSell(balance) {
    // Filter for crypto assets (typically prefixed with 'X' in Kraken API)
    // We want to show crypto assets that can be sold
    const availableCryptos = Object.keys(balance).filter(currency => 
        // Exclude fiat currencies like 'USDT'
        !currency.includes("USD")
    );
    
    const sellCurrencySelect = document.getElementById('sell-currency');
    if (!sellCurrencySelect) {
        console.error('Sell currency select element not found');
        return;
    }
    
    // Populate the dropdown with available crypto options
    sellCurrencySelect.innerHTML = availableCryptos.map(currency => 
        `<option value="${currency}">${currency}</option>`
    ).join('');
    
    // Update the available balance display for the initially selected crypto
    if (sellCurrencySelect.value && balance[sellCurrencySelect.value]) {
        updateSellAvailableBalance(balance[sellCurrencySelect.value], sellCurrencySelect.value);
    } else if (availableCryptos.length > 0 && balance[availableCryptos[0]]) {
        // If nothing is selected but we have options, use the first one
        updateSellAvailableBalance(balance[availableCryptos[0]], availableCryptos[0]);
    } else {
        // Fallback if no crypto balance is found
        updateSellAvailableBalance('0.00000000', 'BTC');
    }
    
    // Add event listener to update balance when selection changes
    sellCurrencySelect.addEventListener('change', async (e) => {
        const selectedCrypto = e.target.value;
        const balance = await fetchAccountBalance();
        const cryptoBalance = balance[selectedCrypto] || '0.00000000';
        updateSellAvailableBalance(cryptoBalance, selectedCrypto);
    });
}

function updateSellAvailableBalance(availableBalance, currencySymbol) {
    const sellAvblSpan = document.querySelector('#sell-avbl');
    if (sellAvblSpan) {
        sellAvblSpan.textContent = `${availableBalance} ${currencySymbol}`;
        sellAvblSpan.setAttribute('data-currency', currencySymbol);
        sellAvblSpan.setAttribute('data-amount', availableBalance);
    } else {
        console.error('Sell available balance span not found');
    }
}

async function fetchUserTrades() {
    try {
        const res = await fetch(API_ENDPOINTS.getUserTrades);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        const data = await res.json();
        console.log('Fetched trades:', data);
        return data.trades || [];
    } catch (error) {
        showAlert('Error fetching trades', 'error');
        console.error('Error fetching trades:', error);
        return [];
    }
}

async function getSymbolPrice(symbol, exchange="futures") {
    try {
        console.log("#".repeat(50));
        console.log({symbol, exchange});
        if (!symbol) {
            console.warn("Symbol not provided");
            return;
        }
        const res = await fetch(`${API_ENDPOINTS.getSymbolPrice}?symbol=${symbol}&exchange=${exchange}`);
        console.log(res);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        
        const json = await res.json();
        console.log(json);
        // console.log("Symbol price response:", json);
        
        // Check if the response has the expected structure
        if (json && json.price) {
            return json.price;
        } else {
            // If the API doesn't return a price yet, return a dummy price for testing
            console.warn("API didn't return a price, using dummy value");
            return "97001.74";
        }
    } catch (error) {
        console.error('Error getting symbol price:', error);
        // Return a dummy price for testing if the API fails
        return "97001.74";
    }
}

function updateCurrentAvailableBalance(availableBalance, currencySymbol) {
    const buyAvblSpan = document.querySelector('#buy-avbl'); 
    buyAvblSpan.textContent = `${availableBalance} ${currencySymbol}`;
    buyAvblSpan.setAttribute('data-currency', currencySymbol);
    buyAvblSpan.setAttribute('data-amount', availableBalance);
}

function calculateAmountToBuy(e) {
    const amountOfCurrency = parseFloat(e.target.value); // money => USD | USDT | EUR
    let price = document.getElementById('buy-price-currency').textContent;

    let currentCurrencySymbol = getTradingSymbol();
    // remove USD/USDT/EUR if exits
    currentCurrencySymbol = currentCurrencySymbol.replace(/USD|USDT|EUR/g, '');
    
    // remove currency symbol and convert to number
    price.replace(/[^\d.]/g, '');
    price = parseFloat(price);

    const total = amountOfCurrency / price;
    document.getElementById('buy-amount-recived').textContent = `${total} ${currentCurrencySymbol}`;
}

document.addEventListener('DOMContentLoaded', () => {

    // --- UI Element References ---
    // Buy Section
    const buyTotalInput = document.getElementById('buy-total');
    const buyCurrencySelect = document.getElementById('buy-currency'); // e.g., USDT
    const buyAvblSpan = document.querySelector('#buy-avbl'); 
    const buyButton = document.querySelector('#spot-tab-pane .col-lg-6:nth-child(1) .btn-success');
    // TODO: Add references for Max Buy, Est Fee if needed later

    // Sell Section
    const sellAmountInput = document.getElementById('sell-amount');
    const sellCurrencySelect = document.getElementById('sell-currency'); // e.g., BTC (XBT)
    const sellAvblSpan = document.querySelector('#sell-avbl'); // Second col, first font-monospace
    const sellButton = document.querySelector('#spot-tab-pane .col-lg-6:nth-child(2) .btn-danger');
    // TODO: Add references for Max Sell, Est Fee if needed later

   
    // --- API Functions ---
    async function renderAccountBalance() {
        try {
           
            const balance = await fetchAccountBalance();

            if (!balance) throw new Error(balance);
            
            // --- Update UI with Balance ---
            // NOTE: Adjust the keys based on the actual API response structure
            // Example assumes response like: { result: { ZUSD: '1000.00', XXBT: '0.5' } } or similar
            // Kraken uses 'Z' prefix for fiat (like ZUSD) and 'X' prefix for crypto (like XXBT for BTC)
            const quoteCurrency = 'USD'; // Assuming USDT is represented as ZUSD in Kraken API balance
            const baseCurrency = 'XBT'; // Assuming BTC is represented as XXBT
            const quoteCurrencyAvailableBalance = balance[quoteCurrency]
            const baseCurrencyAvailableBalance = balance[baseCurrency]
            const availableCurrencies = Object.keys(balance).filter(currency => currency !== quoteCurrency && currency !== baseCurrency);

            // We no longer need to directly update the balance displays here
            // as the updateAvailableOptionsToBuy and updateAvailableOptionsToSell functions will handle that
            
            // Update UI with available options for both buy and sell
            updateAvailableOptionsToBuy(balance);
            updateAvailableOptionsToSell(balance);

        } catch (error) {
            console.error('Error fetching account balance:', error);
            showAlert(`Failed to fetch account balance: ${error.message || error}`, 'error');
            // Set default values on error
             if (buyAvblSpan) buyAvblSpan.textContent = `0.00 ${buyCurrencySelect ? buyCurrencySelect.value : 'USDT'}`;
             if (sellAvblSpan) sellAvblSpan.textContent = `0.00000000 ${sellCurrencySelect ? sellCurrencySelect.value : 'BTC'}`;
        }
    }

    async function placeOrder(direction) {
        const isBuy = direction === 'buy';
        const volumeInput = sellAmountInput;
        const volume = sellAmountInput.value;
        let moneyWantedToSpend = 0;
        if (isBuy) {
            moneyWantedToSpend = buyTotalInput.value; // example 10 USD
            if (!moneyWantedToSpend) showAlert('Please enter a valid amount of USD to spend.', 'warning');
        } else {
            if (!volume || volume <= 0) showAlert('Please enter a valid amount to sell.', 'warning');
        }
       

        // Note: For a market buy order, Kraken often expects the amount in the *quote* currency (e.g., USDT amount to spend).
        // For a market sell order, it expects the amount in the *base* currency (e.g., BTC amount to sell).
        // The 'volume' parameter might need adjustment based on Kraken's specific requirements for market orders vs limit orders.
        // We are assuming the input fields correspond directly to the required 'volume' for a market order here.

        const orderData = {
            orderType: 'market', // Market order as planned
            orderDirection: direction,
            volume: volume,
            symbol: getTradingSymbol(), // Use dynamic symbol
            trading_mode: getTradingMode(), // Use dynamic mode
            // price: null // Not needed for market order
            return_all_trades: true,
            order_made_by: 'user',
            money_wanted_to_spend: moneyWantedToSpend
        };

        console.info(`Placing ${direction} order:`, orderData);
        // Add loading indicator maybe?
        const button = isBuy ? buyButton : sellButton;
        const originalButtonText = button.textContent;
        button.disabled = true;
        button.textContent = 'Placing...';

        try {
            const response = await fetch(API_ENDPOINTS.addOrder, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(orderData)
            });

            const result = await response.json(); // Expecting JSON response
            const errorIsNonEmptyArray = Array.isArray(result?.error) && result?.error?.length > 0;
            const errorIsNonEmptyString = result?.error?.length > 0;
            if (!response.ok || errorIsNonEmptyArray || errorIsNonEmptyString) {
                 let errorMessage = `HTTP error! status: ${response.status}`;
                 // Kraken API often returns errors in an 'error' array
                 if(Array.isArray(result.error)) errorMessage = result.error.join(', ');
                 else errorMessage = result.error;
               
                throw new Error(errorMessage);
            }
            
            console.log({result});
            console.log('Order placement result:', result);
            showAlert(`${direction.charAt(0).toUpperCase() + direction.slice(1)} order placed successfully!`, 'success');

            // Clear input and refresh balance
            volumeInput.value = '';
            // renderAccountBalance(); // Refresh balance after successful order
            renderUserTrades(result.all_trades);

        } catch (error) {
            console.error(`Error placing ${direction} order:`, error);
            showAlert(`Failed to place ${direction} order: ${error.message}`, 'error');
        } finally {
             // Remove loading indicator
             button.disabled = false;
             button.textContent = originalButtonText;
        }
    }

    // --- Event Listeners ---
    if (buyButton) buyButton.addEventListener('click', () => placeOrder('buy'));
    if (sellButton) sellButton.addEventListener('click', () => placeOrder('sell'));
    if (buyTotalInput) buyTotalInput.addEventListener('input', calculateAmountToBuy);

    // --- Initial Load ---
    // renderAccountBalance();
    fetchUserTrades().then(renderUserTrades);
    
    // Update market price with the current trading symbol
    const currentSymbol = getTradingSymbol();
    console.log("Initial load with symbol:", currentSymbol);

    // 1. UI Element References
    const futuresOrderType = document.getElementById('futures-order-type');
    const futuresLeverage = document.getElementById('futures-leverage');
    const futuresMarginRequired = document.getElementById('futures-margin-required');
    const futuresSymbol = document.getElementById('futures-symbol');
    const futuresEntryPrice = document.getElementById('futures-entry-price');
    const futuresAmount = document.getElementById('futures-amount');
    const futuresStopLoss = document.getElementById('futures-stop-loss');
    const futuresTakeProfit = document.getElementById('futures-take-profit');
    const futuresOpenLongBtn = document.getElementById('futures-open-long');
    const futuresOpenShortBtn = document.getElementById('futures-open-short');
    const futuresCloseLongBtn = document.getElementById('futures-close-long');
    const futuresCloseShortBtn = document.getElementById('futures-close-short');
    const futuresInfoAlert = document.getElementById('futures-info-alert');

    // 3. Action Handlers
    function getFuturesFormData() {
        return {
            orderType: futuresOrderType.value,
            leverage: futuresLeverage?.value || 1,
            symbol: futuresSymbol.value,
            // entryPrice: futuresEntryPrice.value,
            amount: futuresAmount.value,
            stopLoss: futuresStopLoss.value,
            takeProfit: futuresTakeProfit.value,
           // marginRequired: futuresMarginRequired.value
        };
    }

    async function handleFuturesOpenLong() {
        // disable btns
        futuresOpenLongBtn.disabled = true;
        futuresOpenShortBtn.disabled = true;
        const data = getFuturesFormData();
        
        const res = await fetch("/add_order", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                ...data,
                trading_mode: "futures",
                order_made_by:"user",
                orderDirection: "buy",
                symbol: localStorage.getItem("symbol-original"),
            })
        })
        const result = await res.json();
        futuresOpenLongBtn.disabled = false;
        futuresOpenShortBtn.disabled = false;
        if (result.error) {
            showAlert("Error: " + result.error, "error");
        } else {
            showAlert("Order placed successfully", "info");
            // Update trade history with the returned trades
            if (result.all_trades) {
                renderUserTrades(result.all_trades);
            } else {
                // Fallback to fetching trades if all_trades is not provided
                fetchUserTrades().then(renderUserTrades);
            }
        }
    }

    async function handleFuturesOpenShort() {
        futuresOpenLongBtn.disabled = true;
        futuresOpenShortBtn.disabled = true;
        const data = getFuturesFormData();
        
        const res = await fetch("/add_order", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                ...data,
                trading_mode: "futures",
                order_made_by:"user",
                orderDirection: "sell",
                symbol: localStorage.getItem("symbol-original"),
            })
        })
        const result = await res.json();
        futuresOpenLongBtn.disabled = false;
        futuresOpenShortBtn.disabled = false;
        if (result.error) {
            showAlert("Error: " + result.error, "error");
        } else {
            showAlert("Order placed successfully", "info");
            // Update trade history with the returned trades
            if (result.all_trades) {
                renderUserTrades(result.all_trades);
            } else {
                // Fallback to fetching trades if all_trades is not provided
                fetchUserTrades().then(renderUserTrades);
            }
        }
    }

    async function handleFuturesCloseLong() {
        futuresCloseLongBtn.disabled = true;
        futuresCloseShortBtn.disabled = true;
        const data = getFuturesFormData();
        const res = await fetch("/close_order", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                ...data,
                trading_mode: "futures",
                order_made_by:"user",
                orderDirection: "sell",
                symbol: localStorage.getItem("symbol-original"),
                params: {
                    
                }
            })
        })
        const result = await res.json();
        futuresCloseLongBtn.disabled = false;
        futuresCloseShortBtn.disabled = false;
        if (result.error) {
            showAlert("Error: " + result.error, "error");
        } else {
            showAlert("Order placed successfully", "info");
            // Update trade history with the returned trades
            if (result.all_trades) {
                renderUserTrades(result.all_trades);
            } else {
                // Fallback to fetching trades if all_trades is not provided
                fetchUserTrades().then(renderUserTrades);
            }
        }
    }

    function handleFuturesCloseShort() {
        const data = getFuturesFormData();
        console.log("[FUTURES] Close Short Position", data);
        showAlert("Simulated: Close Short Position\n" + JSON.stringify(data, null, 2), "info");
    }

    // 4. Event Listeners
    if (futuresOpenLongBtn) futuresOpenLongBtn.addEventListener('click', handleFuturesOpenLong);
    if (futuresOpenShortBtn) futuresOpenShortBtn.addEventListener('click', handleFuturesOpenShort);
    if (futuresCloseLongBtn) futuresCloseLongBtn.addEventListener('click', handleFuturesCloseLong);
    if (futuresCloseShortBtn) futuresCloseShortBtn.addEventListener('click', handleFuturesCloseShort);

    // Update margin required dynamically
    // if (futuresLeverage) futuresLeverage.addEventListener('change', updateFuturesMarginRequired);
    // if (futuresAmount) futuresAmount.addEventListener('input', updateFuturesMarginRequired);
    // if (futuresEntryPrice) futuresEntryPrice.addEventListener('input', updateFuturesMarginRequired);

    // Initialize margin required on load
    // updateFuturesMarginRequired();

});
