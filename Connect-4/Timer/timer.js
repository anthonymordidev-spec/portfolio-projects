const timer = document.getElementById("timer");
const button = document.getElementById("startStop");

// Preload beep
const beep = new Audio(
  "https://actions.google.com/sounds/v1/alarms/beep_short.ogg",
);
beep.preload = "auto";

let startTime;
let interval;
let running = false;

function updateTimer() {
  const elapsed = Date.now() - startTime;

  const seconds = Math.floor(elapsed / 1000);
  const hundredths = Math.floor((elapsed % 1000) / 10);

  timer.textContent = `${String(seconds).padStart(2, "0")}.${String(
    hundredths,
  ).padStart(2, "0")}`;
}

button.addEventListener("click", () => {
  if (!running) {
    // Beep when starting
    beep.currentTime = 0;
    beep.play().catch(() => {});

    startTime = Date.now();
    interval = setInterval(updateTimer, 10);

    button.textContent = "Stop";
    button.style.background = "#ff453a";

    running = true;
  } else {
    clearInterval(interval);
    updateTimer();

    // Beep when stopping
    beep.currentTime = 0;
    beep.play().catch(() => {});

    button.textContent = "Start";
    button.style.background = "#30d158";

    running = false;
  }
});
