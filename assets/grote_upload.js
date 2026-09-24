/*
 * Upload van het (mogelijk zeer grote) 1CHO-bestand.
 *
 * dcc.Upload leest een bestand in de browser in als één base64-tekst; boven
 * ~380 MB kan Chrome dat niet en gebeurt er niets. Dit script stuurt het
 * bestand in plaats daarvan gestreamd naar de eigen route /upload-bestand
 * (zie bestandsopslag.py) en geeft alleen het teruggegeven token door aan
 * Dash, via de store 'cho-bestand'.
 */
(function () {
    function mb(bytes) {
        return (bytes / 1e6).toFixed(bytes < 1e7 ? 1 : 0);
    }

    function zetVoortgang(tekst, fout) {
        var el = document.getElementById("cho-upload-voortgang");
        if (!el) return;
        el.textContent = tekst;
        el.style.color = fout ? "#b91c1c" : "";
    }

    function uploadBestand(bestand) {
        var form = new FormData();
        form.append("bestand", bestand);
        var xhr = new XMLHttpRequest();
        xhr.open("POST", "upload-bestand");
        xhr.upload.onprogress = function (e) {
            if (e.lengthComputable) {
                zetVoortgang(
                    "Uploaden: " + Math.round((e.loaded / e.total) * 100) +
                    "% van " + mb(e.total) + " MB"
                );
            }
        };
        xhr.onload = function () {
            var antwoord = {};
            try {
                antwoord = JSON.parse(xhr.responseText);
            } catch (err) {
                antwoord = {};
            }
            if (xhr.status === 200 && antwoord.token) {
                zetVoortgang(
                    bestand.name + " geüpload (" + mb(antwoord.grootte) +
                    " MB). Bestand wordt ingelezen, dit kan bij een groot bestand even duren..."
                );
                window.dash_clientside.set_props("cho-bestand", {data: antwoord});
            } else {
                zetVoortgang(
                    "Upload mislukt: " + (antwoord.fout || xhr.statusText || "onbekende fout"),
                    true
                );
            }
        };
        xhr.onerror = function () {
            zetVoortgang("Upload mislukt: geen verbinding met de app.", true);
        };
        zetVoortgang("Uploaden: 0% van " + mb(bestand.size) + " MB");
        xhr.send(form);
    }

    function dropzone(e) {
        return e.target && e.target.closest ? e.target.closest("#cho-dropzone") : null;
    }

    function kiesBestand() {
        // Een los bestandsveld (Dash 4 heeft geen html.Input meer).
        var input = document.createElement("input");
        input.type = "file";
        input.accept = ".csv,.txt,.xlsx,.xls";
        input.id = "cho-bestand-input";
        input.style.display = "none";
        input.addEventListener("change", function () {
            if (input.files && input.files.length) uploadBestand(input.files[0]);
            input.remove();
        });
        document.body.appendChild(input);
        input.click();
    }

    document.addEventListener("click", function (e) {
        if (dropzone(e)) kiesBestand();
    });
    document.addEventListener("keydown", function (e) {
        if (dropzone(e) && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            kiesBestand();
        }
    });

    document.addEventListener("dragover", function (e) {
        if (dropzone(e)) {
            e.preventDefault();
            dropzone(e).classList.add("upload-zone-actief");
        }
    });
    document.addEventListener("dragleave", function (e) {
        if (dropzone(e)) dropzone(e).classList.remove("upload-zone-actief");
    });
    document.addEventListener("drop", function (e) {
        var zone = dropzone(e);
        if (zone && e.dataTransfer && e.dataTransfer.files.length) {
            e.preventDefault();
            zone.classList.remove("upload-zone-actief");
            uploadBestand(e.dataTransfer.files[0]);
        }
    });

    // Zodra de validatie klaar is (cho-status verandert), is de tekst
    // 'wordt ingelezen' niet meer nodig.
    new MutationObserver(function () {
        var status = document.getElementById("cho-status");
        var el = document.getElementById("cho-upload-voortgang");
        if (status && el && status.textContent && /ingelezen/.test(el.textContent)) {
            el.textContent = "";
        }
    }).observe(document.documentElement, {childList: true, subtree: true});
})();
