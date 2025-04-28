export default class TvWidget {
    constructor() {
        this.currentTradingSymbol = "";
    }

    loadTradingSymbol = async function(symbolToUse) {
        // let symbolToUse;

        // Verificar si hay un símbolo guardado en localStorage
        const storedSymbol = localStorage.getItem('symbol');
        if (storedSymbol) {
            symbolToUse = storedSymbol;
            // console.log(`Usando símbolo guardado en localStorage: ${symbolToUse}`);
        } else {
            // Obtener el símbolo por defecto desde el backend
            const response = await fetch('/get_current_symbol');
            const data = await response.json();
            symbolToUse = data.symbol;  
            // console.log(`Símbolo por defecto desde el backend: ${symbolToUse}`);
        }

        // check if it is in valid format (without :)
        if (symbolToUse.includes(':')) {
            symbolToUse = symbolToUse.split(':')[0];
        }

        console.log(`Símbolo a usar: ${symbolToUse}`);

        // Asegurarse de que symbolToUse no es undefined
        if (symbolToUse) {
            this.initializeWidget(symbolToUse);
        } else {
            console.error('No se pudo determinar un símbolo válido.');
        }
    }

    initializeWidget = function(symbol) {
       this.widget = new TradingView.widget({
            "width": "100%",
            "height": 500,
            "symbol": `${symbol}`,
            "interval": "1",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "withdateranges": true,
            "hide_side_toolbar": false,
            "allow_symbol_change": false,
            "studies": [
                "RSI@tv-basicstudies",
                "MACD@tv-basicstudies",
                "StochasticRSI@tv-basicstudies"
            ],
            "container_id": "tradingview_chart",
            "autosize": false,
            "hide_top_toolbar": false,
            "save_image": true,
            "show_popup_button": true
        });

        this.currentTradingSymbol = symbol;
        window.tradingViewWidget = this.widget; // Also store globally for debugging
    }

    updateChartSymbol = function(symbol) {
        if (this.widget) {
            this.loadTradingSymbol(symbol);
        }
    }

    handleSymbolChange = function(newSymbol) {
        this.currentTradingSymbol = newSymbol;
        this.saveCurrentTradingSymbol(localStorage, "symbol", newSymbol);
        this.updateTradingSymbol(newSymbol);
        this.updateChartSymbol(newSymbol);
    }

    updateTradingSymbol = async function(symbol) {
        this.currentTradingSymbol = symbol;
        this.saveCurrentTradingSymbol(localStorage, "symbol", symbol);

        // Enviar el símbolo actualizado al servidor
        try {
            await fetch('/update_current_symbol', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ symbol: symbol })
            });
        } catch (error) {
            console.error('Error updating symbol:', error);
        }
    }

    getCurrentTradingSymbol() {
        return this.currentTradingSymbol;
    }

    saveCurrentTradingSymbol(ls, nombre, symbol) {
        if (symbol) {
            ls.setItem(nombre, symbol);
            // console.log(`Símbolo ${symbol} guardado en localStorage con el nombre ${nombre}`);
        } else {
            console.error('No se puede guardar un símbolo undefined en localStorage.');
        }
    }
}
