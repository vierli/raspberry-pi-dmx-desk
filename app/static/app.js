const PRESETS = ["#ff3b4f", "#ff9d2e", "#f4df3b", "#50df72", "#36b9ff", "#9b65ff"];
const fixtureRoot = document.querySelector("#fixtures");
const connection = document.querySelector("#connection");
const connectionLabel = document.querySelector("#connection-label");
const errorBanner = document.querySelector("#error-banner");
const errorDetail = document.querySelector("#error-detail");
const blackoutButton = document.querySelector("#blackout");
const masterColor = document.querySelector("#master-color");
const masterColorValue = document.querySelector("#master-color-value");
const toast = document.querySelector("#toast");
let state = null;
let toastTimer = null;
let pollTimer = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2200);
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = "Die Änderung konnte nicht gesendet werden.";
    try { detail = (await response.json()).detail || detail; } catch (_) { /* keep fallback */ }
    throw new Error(detail);
  }
  return response.json();
}

function fixtureMarkup(fixture, index) {
  const selected = fixture.color.toLowerCase();
  const presets = PRESETS.map((color) => `
    <button class="preset ${selected === color ? "is-selected" : ""}" style="--preset:${color}"
      data-action="preset" data-id="${fixture.id}" data-color="${color}"
      type="button" aria-label="Farbe ${color}"></button>`).join("");
  return `
    <article class="fixture-card ${fixture.enabled ? "is-on" : ""}" style="--fixture-color:${fixture.color}">
      <div class="fixture-heading">
        <div>
          <span class="fixture-number">FIXTURE 0${index + 1}</span>
          <h3>${escapeHtml(fixture.name)}</h3>
          <div class="dmx-address">DMX ${fixture.address}–${fixture.last_channel}</div>
        </div>
        <label class="toggle">
          <input type="checkbox" data-action="toggle" data-id="${fixture.id}" ${fixture.enabled ? "checked" : ""}
            aria-label="${escapeHtml(fixture.name)} ein- oder ausschalten" />
          <span class="toggle-track"></span>
        </label>
      </div>
      <div class="color-stage">
        <div class="color-halo"></div>
        <input class="color-input" type="color" value="${fixture.color}" data-action="color" data-id="${fixture.id}"
          aria-label="Farbe für ${escapeHtml(fixture.name)} wählen" />
      </div>
      <div class="color-readout">
        <span class="color-chip"></span>
        <span class="color-hex">${fixture.color.toUpperCase()}</span>
      </div>
      <div class="presets" aria-label="Schnellfarben">${presets}</div>
    </article>`;
}

function render(nextState) {
  state = nextState;
  fixtureRoot.innerHTML = state.fixtures.map(fixtureMarkup).join("");
  blackoutButton.setAttribute("aria-pressed", String(state.blackout));
  blackoutButton.querySelector("strong").textContent = state.blackout ? "Blackout aktiv" : "Blackout";
  document.querySelector("#refresh-rate").textContent = `${state.dmx.refresh_hz} Hz`;
  document.querySelector("#dmx-port").textContent = state.dmx.mode === "simulation" ? "Simulation" : state.dmx.port;

  connection.className = `connection ${state.dmx.connected ? "is-live" : "is-error"}`;
  connectionLabel.textContent = state.dmx.mode === "simulation"
    ? "Simulation aktiv"
    : state.dmx.connected ? "DMX verbunden" : "DMX getrennt";
  errorBanner.hidden = state.dmx.connected || state.dmx.mode === "simulation";
  errorDetail.textContent = state.dmx.last_error || "Prüfe UART, Rechte und Verkabelung.";
  document.querySelector("#last-sync").textContent = `Synchronisiert ${new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
}

async function updateFixture(id, payload, quiet = false) {
  try {
    render(await request(`/api/fixtures/${id}`, { method: "PATCH", body: JSON.stringify(payload) }));
    if (!quiet) showToast("Scheinwerfer aktualisiert");
  } catch (error) {
    showToast(error.message);
    await loadState();
  }
}

fixtureRoot.addEventListener("change", (event) => {
  const control = event.target.closest("[data-action]");
  if (!control) return;
  const id = Number(control.dataset.id);
  if (control.dataset.action === "toggle") updateFixture(id, { enabled: control.checked });
  if (control.dataset.action === "color") updateFixture(id, { color: control.value, enabled: true });
});

fixtureRoot.addEventListener("click", (event) => {
  const control = event.target.closest('[data-action="preset"]');
  if (control) updateFixture(Number(control.dataset.id), { color: control.dataset.color, enabled: true });
});

masterColor.addEventListener("input", () => { masterColorValue.textContent = masterColor.value.toUpperCase(); });
document.querySelector("#all-on").addEventListener("click", async () => {
  try {
    render(await request("/api/all", { method: "POST", body: JSON.stringify({ enabled: true, color: masterColor.value }) }));
    showToast("Beide Scheinwerfer eingeschaltet");
  } catch (error) { showToast(error.message); }
});
document.querySelector("#all-off").addEventListener("click", async () => {
  try {
    render(await request("/api/all", { method: "POST", body: JSON.stringify({ enabled: false }) }));
    showToast("Beide Scheinwerfer ausgeschaltet");
  } catch (error) { showToast(error.message); }
});
blackoutButton.addEventListener("click", async () => {
  try {
    const enabled = !state.blackout;
    render(await request("/api/blackout", { method: "POST", body: JSON.stringify({ enabled }) }));
    showToast(enabled ? "Blackout aktiviert" : "Blackout aufgehoben");
  } catch (error) { showToast(error.message); }
});

async function loadState() {
  try {
    render(await request("/api/state"));
  } catch (error) {
    connection.className = "connection is-error";
    connectionLabel.textContent = "Webdienst getrennt";
    errorBanner.hidden = false;
    errorDetail.textContent = error.message;
  }
}

loadState();
pollTimer = setInterval(loadState, 5000);
window.addEventListener("beforeunload", () => clearInterval(pollTimer));
