export default async function add_order(addOrder,orderType, type, volume, pair){

    const d = document;
    const $addOrder = d.getElementById(addOrder);
    const $orderType =d.getElementById(orderType);
    const $type = d.getElementById(type);
    const $volume = d.getElementById(volume);
    const tradingMode = localStorage.getItem("method");
    

    $addOrder.addEventListener("click", async (e)=>{
          e.preventDefault();

          // check valid values
          if (!$orderType.value || !$type.value || !$volume.value || !pair) {
            console.log({
              orderType: $orderType.value,
              orderDirection:$type.value,
              volume:$volume.value,
              symbol: pair,
              trading_mode: tradingMode
            })
            alert("Por favor, complete todos los campos.");
            return;
          }

          const orderData = {

            orderType: $orderType.value,
            orderDirection:$type.value,
            volume:$volume.value,
            symbol: pair,
            trading_mode: tradingMode

          }

          try {
            // Enviar la orden mediante fetch a la ruta de backend
            const response = await fetch("/add_order", {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify(orderData)
            });

            const result = await response.json();


            if (result.error) {
              throw new Error(result.error);
            }

            alert("Orden enviada exitosamente.");
            // Aquí puedes actualizar la interfaz de usuario, mostrar un mensaje, etc.
          } catch (error) {
            alert(error)
            console.error("Error al enviar la orden:", error);
          }

    });


}