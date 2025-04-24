export default async function get_symbol(){

    try {

        let response = await fetch('/get_symbol_trading');
        let json = await response.json();
        
        console.log(`Respuesta desde /get_symbol_trading en routes.py:`, json);

        // Verificar si hay errores en la respuesta
        if (json.error && json.error.length > 0) {
            console.error('Error en la respuesta de la API de Kraken:', json.error);
            return;
        }

        return json.get_symbol;
    } catch (error) {

        console.error('Error:', error)
        return null;
        
    }
}