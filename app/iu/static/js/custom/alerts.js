/**
 * Se ha modificado la alerta nativa de JS para usar la libreria sweetalert2
 * Esto permitira la compatbiilidad con todo el codigo actual con el fin de
 * tener alertas mas amigable para el usuario
 * 
 * Documentación oficial: https://sweetalert2.github.io/#usage
 */


alert = (msg) => {
  Swal.fire({
    position: 'center',
    icon: msg.toUpperCase().includes("ERROR")?"error":"success",
    title: msg,
    showConfirmButton: false,
    timer: msg.toUpperCase().includes("ERROR")?10000:3000,
    customClass: {
      popup: 'swal2-toast-custom'
    }
  });
}