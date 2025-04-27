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
            const email = $form.email.value;
            const password = $form.password.value;

            if (!email || !password) {
                throw new Error("Todos los campos son obligatorios");
            }
        
            
            const response = await fetch('/login', {
                method: 'POST',
                 headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({email, password})
            });

            const result = await response.json();
            
            console.log({result})
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