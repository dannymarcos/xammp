// app/iu/static/js/validaciones_formulario.js
const d = document;

export default function loginFormValidations(){
    const $form = d.querySelector(".login-form"),
          $loader = d.querySelector(".login-form-loader"),
          $response = d.querySelector(".login-form-response");

    d.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        $loader.classList.remove("none");
        $form.style.pointerEvents = "none";
        $form.style.opacity = "0.7";

        try {
            const formData = new FormData($form);
            console.log("Form: ",$form);
            console.log("Form Data: ",formData);

            // Convertir a objeto (opcional)
            const data = Object.fromEntries(formData);

            console.log("formData: ", data)
            
            const response = await fetch('/login', {
                method: 'POST',
                headers: {
                    'Accept': 'application/json'
                },
                body: formData
            });

            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.message || 'Error en el servidor');
            }
            
            // Redirección exitosa
            window.location.href = result.redirect || '/';
            
        } catch (error) {
            console.error("Error:", error);
            $response.textContent = error.message;
            $response.classList.remove("none");
        } finally {
            $loader.classList.add("none");
            $form.style.pointerEvents = "auto";
            $form.style.opacity = "1";
            
            setTimeout(() => {
                $response.classList.add("none");
            }, 3000);
        }
    });
}

d.addEventListener("DOMContentLoaded", (e) => {
    loginFormValidations();
});