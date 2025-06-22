export default async function get_historical_data(symbol) {
    const d = document;
    const $historicTableBody = d.getElementById("historic-table-body");
    const $h2 = d.getElementById('historic-data-h2');

    if (!$historicTableBody) {
        console.error("No se encontró el cuerpo de la tabla histórica.");
        return;
    }
    // console.log("Estamos dentro de la funcion get_historical_data_1", symbol);
    try {
        $h2.textContent = "Cargando datos para el par " + symbol;
        $historicTableBody.innerHTML = `<h2>Cargando...</h2>`;
        // Obtener los datos históricos desde la API de Kraken
        const response = await fetch(`/fetch_historical_data?symbol=${symbol}`);
        const json = await response.json();

        // console.log("Estamos dentro de la funcion get_historical_data_2", json);
        // Verificar si hay errores en la respuesta
        if (json.error && json.error.length > 0) {
            console.error('Error en la respuesta de la API de Kraken:', json.error);
            $historicTableBody.innerHTML = `<h2 class="text-red-500 font-bold">${json.error}</h2>`;
            return;
        }

        // Limpiar la tabla antes de agregar nuevos datos
        $historicTableBody.innerHTML = '';
        $h2.textContent = `Historial de Mercado para el par ${symbol}`;
        // Llenar la tabla con los datos históricos
        json.forEach((el) => {
            const row = d.createElement("tr");
            // console.log("Estamos dentro de la funcion get_historical_data_3", el);

            row.innerHTML = `
                <td class="py-3 px-4 border-b">${new Date(el[0] * 1000).toLocaleString()}</td>
                <td class="py-3 px-4 border-b">${el[1]}</td>
                <td class="py-3 px-4 border-b">${el[2]}</td>
                <td class="py-3 px-4 border-b">${el[3]}</td>
                <td class="py-3 px-4 border-b">${el[4]}</td>
                <td class="py-3 px-4 border-b">${el[5]}</td>
                <td class="py-3 px-4 border-b">${el[6]}</td>
                <td class="py-3 px-4 border-b">${el[7]}</td>
            `;

            $historicTableBody.appendChild(row);
        });

        // // Obtener el ultimo registro
        const latestData = json[json.length-1];
        // // Creamos un arreglo para enviar al modelo
        const symbolData = latestData[4];

        // console.log("Datos históricos cargados correctamente.");
    } catch (error) {
        console.error('Error al obtener los datos históricos:', error);
    }
}

