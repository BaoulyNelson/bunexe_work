document.addEventListener("DOMContentLoaded", () => {
  const candidateCodePattern = /^(?:0[1-9]|10)[0-9]{8}$/;
  for (const input of document.querySelectorAll("[data-candidate-code]")) {
    const updateValidity = () => {
      input.setCustomValidity(
        candidateCodePattern.test(input.value)
          ? ""
          : "Le matricule doit contenir 10 chiffres et commencer par 01 à 10.",
      );
    };

    input.addEventListener("input", () => {
      let digits = input.value.replace(/[^0-9]/g, "").slice(0, 10);
      if (digits && !/^[01]/.test(digits)) digits = "";
      if (digits.length > 1 && !/^(?:0[1-9]|10)/.test(digits)) {
        digits = digits.slice(0, 1);
      }
      if (digits !== input.value) {
        const cursor = Math.min(input.selectionStart ?? digits.length, digits.length);
        input.value = digits;
        input.setSelectionRange(cursor, cursor);
      }
      updateValidity();
    });

    input.form?.addEventListener("submit", (event) => {
      updateValidity();
      if (!input.checkValidity()) {
        event.preventDefault();
        input.reportValidity();
        input.focus();
      }
    });
  }

  for (const input of document.querySelectorAll('input[type="password"]')) {
    input.classList.add("form-control");

    const field = document.createElement("div");
    field.className = "password-field";
    input.parentNode.insertBefore(field, input);
    field.append(input);

    const toggle = document.createElement("button");
    toggle.className = "password-visibility-toggle";
    toggle.type = "button";
    toggle.setAttribute("aria-label", "Afficher le mot de passe");
    toggle.setAttribute("aria-pressed", "false");
    toggle.title = "Afficher le mot de passe";
    toggle.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path class="password-eye-slash" d="m4 4 16 16"/></svg>';
    toggle.addEventListener("click", () => {
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      toggle.setAttribute("aria-pressed", String(visible));
      toggle.setAttribute(
        "aria-label",
        visible ? "Masquer le mot de passe" : "Afficher le mot de passe",
      );
      toggle.title = visible
        ? "Masquer le mot de passe"
        : "Afficher le mot de passe";
    });
    field.append(toggle);
  }

  for (const details of document.querySelectorAll("[data-focus-on-open]")) {
    const focusCode = () => {
      if (details.open) {
        requestAnimationFrame(() => {
          details.querySelector('input[name="code"]')?.focus();
        });
      }
    };

    details.querySelector("summary")?.addEventListener("click", focusCode);
    details.addEventListener("toggle", () => {
      focusCode();
    });
  }
});