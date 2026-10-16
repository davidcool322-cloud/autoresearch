const form = document.querySelector("#lookup-form");
const modelInput = document.querySelector("#model");
const startButton = document.querySelector("#start-button");
const clearButton = document.querySelector("#clear-button");
const sourceButton = document.querySelector("#source-button");
const status = document.querySelector("#status");
const result = document.querySelector("#result");

const fields = {
  category: document.querySelector("#category"),
  model: document.querySelector("#result-model"),
  name: document.querySelector("#product-name"),
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
  status.textContent = "";
  status.classList.remove("error");
  setSource();
}

function showError(message) {
  result.classList.add("hidden");
  status.textContent = message;
  status.classList.add("error");
  setSource();
}

function showProduct(product) {
  fields.category.textContent = product.category;
  fields.model.textContent = product.model;
  fields.name.textContent = product.name;
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
  result.classList.remove("hidden");
  result.scrollIntoView({ behavior: "smooth", block: "start" });
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
  status.textContent = "正在確認 Supermicro 官網資料…";

  try {
    const response = await fetch(
      `/api/products?model=${encodeURIComponent(model)}`,
      { headers: { Accept: "application/json" } },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error);
    }
    showProduct(payload);
  } catch {
    showError("再次確認型號");
  } finally {
    startButton.disabled = false;
    startButton.textContent = "開始";
  }
});

clearButton.addEventListener("click", () => {
  modelInput.value = "";
  resetResult();
  modelInput.focus();
});
