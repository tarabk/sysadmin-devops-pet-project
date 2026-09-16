const API = (window.APP_CONFIG?.API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const tasksNode = document.querySelector("#tasks");
const emptyNode = document.querySelector("#empty");
const form = document.querySelector("#task-form");
const errorNode = document.querySelector("#form-error");
const statusNode = document.querySelector("#api-status");

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* no JSON body */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.status === 204 ? null : response.json();
}

function taskCard(task) {
  const article = document.createElement("article");
  article.className = `task${task.completed ? " done" : ""}`;

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = task.completed;
  checkbox.setAttribute("aria-label", "Toggle task completion");
  checkbox.addEventListener("change", async () => {
    try { await api(`/api/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ completed: checkbox.checked }) }); await loadTasks(); }
    catch (error) { checkbox.checked = !checkbox.checked; alert(error.message); }
  });

  const body = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = task.title;
  const description = document.createElement("p");
  description.textContent = task.description;
  body.append(title, description);

  const remove = document.createElement("button");
  remove.className = "delete";
  remove.textContent = "Delete";
  remove.addEventListener("click", async () => {
    try { await api(`/api/tasks/${task.id}`, { method: "DELETE" }); await loadTasks(); }
    catch (error) { alert(error.message); }
  });

  article.append(checkbox, body, remove);
  return article;
}

async function loadTasks() {
  try {
    const tasks = await api("/api/tasks");
    tasksNode.replaceChildren(...tasks.map(taskCard));
    emptyNode.hidden = tasks.length !== 0;
    statusNode.textContent = "API: available";
    statusNode.className = "status ok";
  } catch (error) {
    statusNode.textContent = "API: unavailable";
    statusNode.className = "status bad";
    tasksNode.replaceChildren();
    emptyNode.hidden = false;
    emptyNode.textContent = `Failed to load tasks: ${error.message}`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorNode.textContent = "";
  const title = document.querySelector("#title").value.trim();
  const description = document.querySelector("#description").value.trim();
  try {
    await api("/api/tasks", { method: "POST", body: JSON.stringify({ title, description }) });
    form.reset();
    await loadTasks();
  } catch (error) { errorNode.textContent = `Error: ${error.message}`; }
});

document.querySelector("#refresh").addEventListener("click", loadTasks);
loadTasks();

