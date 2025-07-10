export default async function get_account_balance(method) {
    const d = document;
    let metodo = method;

    try {
        console.log({ metodo });
        // Configurar la solicitud POST
        const response = await fetch("/get_account_balance", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ trading_mode: metodo, exchange_name: metodo }),
        });

        // Verificar si la respuesta es exitosa
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Procesar la respuesta JSON
        const json = await response.json();

        console.log("Estamos dentro de la función get_account_balance");
        console.log("Balance de la cuenta obtenido:", json);

        // Acceder a los datos dentro de "result"
        const balances = json.balance;

        // Obtener el elemento <select>
        const $balanceSelect = d.getElementById('get-balance');

        // Limpiar el contenido actual del <select>
        $balanceSelect.innerHTML = '';

        // Verificar si hay datos en "result"
        if (Object.keys(balances).length === 0) {
            // Si no hay fondos, mostrar un mensaje
            const $option = d.createElement('option');
            $option.textContent = "No hay fondos disponibles";
            $balanceSelect.appendChild($option);
        } else {
            // Si hay fondos, iterar sobre los símbolos y precios
            balances.forEach(({amount, currency}) => {
                const $option = d.createElement('option');
                $option.setAttribute('value', currency);
                $option.textContent = `${currency}: ${amount}`; // Mostrar símbolo y precio
                $balanceSelect.appendChild($option);
            });
        }

    } catch (error) {
        console.error("Error al obtener los datos del balance de cuenta:", error);

        // Mostrar un mensaje de error en el <select>
        const $balanceSelect = d.getElementById('get-balance');
        $balanceSelect.innerHTML = '';
        const $option = d.createElement('option');
        $option.textContent = "Error al cargar los fondos";
        $balanceSelect.appendChild($option);
    }
}