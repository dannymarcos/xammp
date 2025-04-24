export default async function add_order(addOrder,orderType, type, volume, pair){

    const d = document;
    const $addOrder = d.getElementById(addOrder);
    const $orderType =d.getElementById(orderType);
    const $type = d.getElementById(type);
    const $volume = d.getElementById(volume);
    

    $addOrder.addEventListener("click", async (e)=>{
          e.preventDefault();

          const orderData = {

            orderType: $orderType.value,
            type:$type.value,
            volume:$volume.value,
            symbol: pair,

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
            console.log("Orden enviada:", result);
            // Aquí puedes actualizar la interfaz de usuario, mostrar un mensaje, etc.
          } catch (error) {
            console.error("Error al enviar la orden:", error);
          }

    });


}