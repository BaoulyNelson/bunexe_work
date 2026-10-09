document.addEventListener("DOMContentLoaded", () => {
  const language = document.querySelector("#language");
  if (language) language.value = document.documentElement.lang;

  const cards = document.querySelectorAll("[data-payment-card]");
  const submit = document.querySelector("[data-payment-submit]");
  for (const card of cards) {
    const input = card.querySelector("input[type='radio']");
    card.addEventListener("click", () => {
      for (const other of cards) other.classList.remove("is-selected");
      card.classList.add("is-selected");
      input.checked = true;
      if (submit) submit.hidden = false;
    });
  }
});