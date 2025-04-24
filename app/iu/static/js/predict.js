export default async function predict(symbolData){
    console.log("Estamos dentro de la funcion predict js");
    try{

        const response = await fetch ('/predict',{
            method:'POST',
            headers:{
                'Content-Type':'application/json'
            },
            body: JSON.stringify(symbolData)
        });

        const data = await response.json();
        console.log("Prediccion:", data.prediction);

        document.getElementById('prediction-result').innerText = `Predicción: ${data.prediction}`;

    }catch (e){
        console.error('Error al obtener la prediccion: ', e)
    }
}