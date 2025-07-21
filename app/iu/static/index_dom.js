
import TvWidget from "./js/TvWidget.js";
import get_cryptos from "./js/get_cryptos.js";

import get_method from "./js/get_method.js";
import get_symbol from "./js/get_symbol.js";
import send_strategy from "./js/send_strategy.js";
import get_historical_data from "./js/get_historical_data.js";
// import add_order from "./js/add_order.js";
// import get_account_balance from "./js/get_account_balance.js";

const d = document;
const ls = localStorage;

d.addEventListener("DOMContentLoaded", async (e)=>{
    window.tvWidget = new TvWidget();
    window.get_historical_data = get_historical_data;
    
    let method = ls.getItem('method');

    
    // Si el localStorage esta vacio, obtiene el método por defecto desde el backend y lo almacena
    if(!method){
        method = await get_method();
        if(method){
            ls.setItem('method',method);
        }else{
         //Si no se pudo obtener el método por algun error. usar "spot" como callback
         method = 'spot';
         ls.setItem('method',method)
        }
    }

    //Si el localstorage esta vacio, obtiene el simbolo por defecto desde el backend y lo almacena
    let symbol = ls.getItem('symbol');

    if(!symbol){
        symbol = await get_symbol();
        if(symbol){
            console.log("Estamos dentro de la funcion index_dom, y el simbolo es 1: ",symbol)
            ls.setItem('symbol',symbol);
        }else{

            //Si no se puede obtener el simbolo por algun error, usar "XBTUSD"
            symbol = 'XBTUSD';
            ls.setItem('symbol',symbol);
        }
    }

    // check if it is in valid format (without :)
    if (symbol.includes(':')) {
        symbol = symbol.replace(':', '');
    }
    console.log("Estamos dentro de la funcion index_dom, y el simbolo es 1: ",symbol)

    //Clase que permite cargar el widget de trading view en el cuerpo del documento
    tvWidget.loadTradingSymbol().then(() => {
        // console.log(`El símbolo actual es: ${tvWidget.getCurrentTradingSymbol()}`); 
        
        // console.log(`El símbolo actual guardado en localStorage es: ${localStorage.getItem("symbol")}`);
    });
    
    //Funcion que permite obtener una lista detallada de los pares de divisas disponibles en la API de kraken, dependiendo del metodo
    // de trading que este almacenado en la variable method
    get_cryptos(method,'fetchCryptos','crypto-list','crypto-search');
   
    //Esta funcion permite mediante el boton 'trading-mode-button' cambiar entre los controles
    // para operar en spot y en futuros, dependiendo del metodo en el que se encuentre
    // method_trading('trading-mode-button','manual-trading-controls','ai-trading-controls');

    send_strategy(null,'send-strategy','chat-input','strategy-mode-button','chat-messages');

    // let symbol = ls.getItem('symbol');

    get_historical_data(symbol);

    // add_order('add-order','order-type','type','amount',symbol)
});
