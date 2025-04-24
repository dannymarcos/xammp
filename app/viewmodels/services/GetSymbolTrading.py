# app/viewmodels/services/GetSymbolTrading.py
from flask import current_app



class GetSymbolTrading: 

    def __init__(self):

        self.symbol = None

    
    def get_symbol(self):

        #Obtener el simbolo del trading por defecto desde la configuracion de la aplicacion con XBTUSD como valor predeterminado
        self.symbol = current_app.config.get("SYMBOL", "XBTUSD")

        return self.symbol()