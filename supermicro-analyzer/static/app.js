const form = document.querySelector("#lookup-form");
const modelInput = document.querySelector("#model");
const startButton = document.querySelector("#start-button");
const clearButton = document.querySelector("#clear-button");
const sourceButton = document.querySelector("#source-button");
const status = document.querySelector("#status");
const result = document.querySelector("#result");
const emptyState = document.querySelector("#empty-state");
const sideBySide = window.matchMedia("(min-width: 1000px)");
const progressPanel = document.querySelector("#progress");
const progressMessage = document.querySelector("#progress-message");
const progressPercent = document.querySelector("#progress-percent");
const progressTrack = document.querySelector("#progress-track");
const progressFill = document.querySelector("#progress-fill");
let activeEvents = null;

const fields = {
  category: document.querySelector("#category"),
  model: document.querySelector("#result-model"),
  name: document.querySelector("#product-name"),
  motherboardCard: document.querySelector("#motherboard-card"),
  motherboardModel: document.querySelector("#motherboard-model"),
  cpu: document.querySelector("#cpu"),
  memory: document.querySelector("#memory"),
  bmc: document.querySelector("#bmc"),
  rot: document.querySelector("#rot"),
  biosVersion: document.querySelector("#bios-version"),
  bmcVersion: document.querySelector("#bmc-version"),
};

function setSource(url = "") {
  if (url) {
    sourceButton.href = url;
    sourceButton.classList.remove("disabled");
    sourceButton.setAttribute("aria-disabled", "false");
    return;
  }
  sourceButton.href = "#";
  sourceButton.classList.add("disabled");
  sourceButton.setAttribute("aria-disabled", "true");
}

function resetResult() {
  result.classList.add("hidden");
  emptyState.classList.remove("hidden");
  progressPanel.classList.add("hidden");
  updateProgress(0, "準備查詢");
  status.textContent = "";
  status.classList.remove("error");
  setSource();
}

function showError(message) {
  result.classList.add("hidden");
  emptyState.classList.remove("hidden");
  progressPanel.classList.add("hidden");
  status.textContent = message;
  status.classList.add("error");
  setSource();
}

function updateProgress(percent, message) {
  const safePercent = Math.max(0, Math.min(100, Number(percent)));
  progressFill.style.width = `${safePercent}%`;
  progressPercent.textContent = `${safePercent}%`;
  progressMessage.textContent = message;
  progressTrack.setAttribute("aria-valuenow", String(safePercent));
}

function finishRequest() {
  activeEvents?.close();
  activeEvents = null;
  startButton.disabled = false;
  startButton.textContent = "開始";
}

function showProduct(product) {
  fields.category.textContent = product.category;
  fields.model.textContent = product.model;
  fields.name.textContent = product.name;
  const isSystem = product.category === "系統";
  fields.motherboardModel.textContent =
    product.motherboard_model ?? "官網未提供";
  fields.motherboardCard.classList.toggle("hidden", !isSystem);
  fields.cpu.textContent = product.cpu;
  fields.memory.replaceChildren(
    ...product.memory.map((item) => {
      const listItem = document.createElement("li");
      listItem.textContent = item;
      return listItem;
    }),
  );
  fields.bmc.textContent = product.bmc ? "有" : "沒有";
  fields.rot.textContent = product.rot ? "有" : "沒有";
  fields.biosVersion.textContent = product.bios_version ?? "官網未提供";
  fields.bmcVersion.textContent = product.bmc_version ?? "官網未提供";
  status.textContent = "";
  status.classList.remove("error");
  setSource(product.sources[0]);
  emptyState.classList.add("hidden");
  result.classList.remove("hidden");
  if (!sideBySide.matches) {
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const model = modelInput.value.trim();
  if (!model) {
    showError("再次確認型號");
    return;
  }

  startButton.disabled = true;
  startButton.textContent = "查詢中";
  resetResult();
  progressPanel.classList.remove("hidden");
  updateProgress(0, "準備查詢");

  activeEvents?.close();
  activeEvents = new EventSource(
    `/api/products/progress?model=${encodeURIComponent(model)}`,
  );

  activeEvents.addEventListener("progress", (progressEvent) => {
    const payload = JSON.parse(progressEvent.data);
    updateProgress(payload.percent, payload.message);
  });

  activeEvents.addEventListener("result", (resultEvent) => {
    showProduct(JSON.parse(resultEvent.data));
    finishRequest();
  });

  activeEvents.addEventListener("lookup-error", () => {
    showError("再次確認型號");
    finishRequest();
  });

  activeEvents.onerror = () => {
    if (!activeEvents) {
      return;
    }
    showError("再次確認型號");
    finishRequest();
  };
});

clearButton.addEventListener("click", () => {
  finishRequest();
  modelInput.value = "";
  resetResult();
  modelInput.focus();
});
