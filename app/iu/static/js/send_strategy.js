export default function send_strategy(metodo=null,boton,chatInput,strategyMode,chatMessages){

    const d = document;
    
    const $sendStrategyButton = d.getElementById(boton);
    const $strategyInput = d.getElementById(chatInput);
    const $strategyModeButton = d.getElementById(strategyMode);
    const $chatMessages = d.getElementById(chatMessages);


    console.log("Estamos dentro de la funcion send_strategy");
    if($sendStrategyButton){
        $sendStrategyButton.addEventListener("click",(e)=>{

            console.log("Estamos dentro de la funcion send_strategy y dentro del boton 'send-strategy'", e);

            if ($strategyInput.value.trim().toLowerCase()) {
                let customStrategy = $strategyInput.value;
                let useCustomStrategies = true;
                
                // Update strategy mode button
                if ($strategyModeButton) {
                    $strategyModeButton.textContent = 'Using Custom Strategy';
                    $strategyModeButton.classList.remove('bg-green-500', 'hover:bg-green-700');
                    $strategyModeButton.classList.add('bg-blue-500', 'hover:bg-blue-700');
                }
                
               
                if ($chatMessages) {
                    const $messageDiv = document.createElement('div');
                    $messageDiv.className = 'text-right';
                    $messageDiv.textContent = customStrategy;
                    $chatMessages.appendChild($messageDiv);
                    // $chatMessages.scrollTop = $chatMessages.scrollHeight;
                }
                
                // Clear input
                $strategyInput.value = '';
                
                console.log('Strategy saved:', customStrategy);
                console.log('Using custom strategies:', useCustomStrategies);
            }


        })
    }

}