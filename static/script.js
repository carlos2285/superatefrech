document.addEventListener("DOMContentLoaded", function() {
    const asistenciaForm = document.querySelector("#asistenciaForm");
    const notasForm = document.querySelector("#notasForm");

    if (asistenciaForm) {
        asistenciaForm.addEventListener("submit", function(event) {
            let fecha = document.querySelector("input[name='fecha']").value;
            if (!fecha) {
                event.preventDefault();
                alert("Por favor, selecciona una fecha.");
            }
        });
    }

    if (notasForm) {
        notasForm.addEventListener("submit", function(event) {
            let inputs = document.querySelectorAll("input[type='number']");
            for (let input of inputs) {
                if (input.value === "" || input.value < 0 || input.value > 100) {
                    event.preventDefault();
                    alert("Asegúrate de que todas las notas sean valores entre 0 y 100.");
                    return;
                }
            }
        });
    }
});
