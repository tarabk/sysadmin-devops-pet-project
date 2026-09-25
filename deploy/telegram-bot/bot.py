#!/usr/bin/env python3
"""Read-only Telegram menus for Taskboard. Python standard library only."""
import json
import logging
import math
import os
import re
import signal
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger("taskboard-bot")
PROJECT = "container_label_com_docker_compose_project"
SERVICE = "container_label_com_docker_compose_service"
GROUPS = {
    "app": ("Application", "sysadmin-devops-pet-project", ("backend", "frontend", "db")),
    "mon": ("Monitoring", "taskboard-monitoring", (
        "prometheus", "node-exporter", "cadvisor", "blackbox", "grafana", "alertmanager", "telegram-bot")),
}
DOMAIN = "tarabk-pet.polandcentral.cloudapp.azure.com"
JOBS = {"dns": "taskboard_dns", "https": "taskboard_home", "ready": "taskboard_ready", "api": "taskboard_https"}
VM_NAMES = {"cpu": "CPU Usage", "memory": "Memory", "disk": "Disk", "inodes": "Inodes"}
STOP = False


class ServiceError(Exception):
    """Deliberately contains no request URL, token or upstream response body."""
    def __init__(self, message, fatal=False, retry_after=5):
        super().__init__(message)
        self.fatal = fatal
        self.retry_after = retry_after


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ServiceError("HTTP redirect refused")


def http_json(url, payload=None, timeout=8, service="Service"):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ServiceError(service + " response too large")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        retry = 5
        try:
            body = json.loads(exc.read(8192))
            description = body.get("description", "")
            if service == "Telegram" and exc.code == 400 and "message is not modified" in description:
                return {"ok": True, "result": None}
            retry = max(1, min(30, int(body.get("parameters", {}).get("retry_after", 5))))
        except (ValueError, TypeError, AttributeError):
            pass
        raise ServiceError(f"{service} HTTP {exc.code}",
                           fatal=service == "Telegram" and exc.code in (401, 409),
                           retry_after=retry) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ServiceError(service + " request failed (" + type(exc).__name__ + ")") from None


def load_config(path):
    cfg = json.loads(Path(path).read_text())
    chat = cfg.get("allowed_chat_id")
    if type(chat) is not int or chat <= 0:
        raise ValueError("allowed_chat_id must be a positive private chat ID")
    url = cfg.get("prometheus_url", "").rstrip("/")
    if url != "http://127.0.0.1:9090":
        raise ValueError("prometheus_url must be http://127.0.0.1:9090 for this deployment")
    token = Path(cfg["token_file"]).read_text().strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
        raise ValueError("Token file must contain only a Telegram bot token")
    return chat, url, token


class Telegram:
    def __init__(self, token):
        self.base = "https://api.telegram.org/bot" + token + "/"

    def call(self, method, payload=None, timeout=8):
        result = http_json(self.base + method, payload or {}, timeout, "Telegram")
        if not isinstance(result, dict) or not result.get("ok"):
            raise ServiceError("Telegram rejected the request")
        return result.get("result")


class Prometheus:
    def __init__(self, base):
        self.base = base

    def query(self, expression, now):
        args = urllib.parse.urlencode({"query": expression, "time": now, "timeout": "3s"})
        result = http_json(self.base + "/api/v1/query?" + args, timeout=5, service="Prometheus")
        try:
            if result["status"] != "success" or result["data"]["resultType"] != "vector":
                raise ServiceError("Prometheus returned an unexpected result")
            return result["data"]["result"]
        except (KeyError, TypeError):
            raise ServiceError("Prometheus returned an invalid response") from None


class Snapshot:
    def __init__(self, prometheus, now=None):
        self.prometheus = prometheus
        self.now = time.time() if now is None else now
        self.cache = {}

    def rows(self, expression):
        if expression not in self.cache:
            self.cache[expression] = self.prometheus.query(expression, self.now)
        return self.cache[expression]

    def number(self, expression):
        rows = self.rows(expression)
        if len(rows) != 1:
            return None
        try:
            stamp, raw = rows[0]["value"]
            number = float(raw)
            if not math.isfinite(number) or not -5 <= self.now - float(stamp) <= 120:
                return None
            return number
        except (KeyError, TypeError, ValueError):
            return None

    def fresh(self, expression):
        # timestamp() inspects the original sample, not the query evaluation time.
        stamp = self.number("timestamp(" + expression + ")")
        return stamp is not None and -5 <= self.now - stamp <= 120

    def metric(self, expression):
        return self.number(expression) if self.fresh(expression) else None


def fmt(value, unit="%", digits=1):
    return "No data" if value is None else f"{value:.{digits}f}{unit}"


def capacity(value):
    return "No data" if value is None else f"{value / 1024 ** 3:.2f} GiB"


def button(text, route):
    return {"text": text, "callback_data": route}


def keyboard(rows, route="home", parent="home", refresh=False):
    result = [[button(title, dest) for title, dest in row] for row in rows]
    if refresh:
        result.append([button("Refresh", route)])
    if route != "home":
        result.append([button("Back", parent), button("Main Menu", "home")])
    return {"inline_keyboard": result}


def record(name, selector=""):
    return "taskboard:" + name + ("{" + selector + "}" if selector else "")


def render(route, snap):
    """Only predefined routes can select fixed PromQL expressions."""
    now = datetime.fromtimestamp(snap.now, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    footer = "\n\nRequested: " + now + "\nMetrics refresh every 30 seconds."
    root_rows = [[("VM", "vm"), ("Containers", "containers")], [("Website", "site")]]
    if route == "home":
        return "Taskboard Monitoring\nChoose a section.", keyboard(root_rows)
    if route == "vm":
        rows = [[("CPU Usage", "vm:cpu"), ("Memory", "vm:memory")], [("Disk", "vm:disk"), ("Inodes", "vm:inodes")]]
        return "VM / vm-lab\nChoose a metric.", keyboard(rows, route)
    if route.startswith("vm:") and route[3:] in VM_NAMES:
        name = route[3:]
        metric = {"cpu": "vm_cpu_usage:percent", "memory": "vm_memory_usage:percent",
                  "disk": "vm_disk_usage:percent", "inodes": "vm_inode_usage:percent"}[name]
        value = snap.metric(record(metric))
        lines = ["VM / vm-lab / " + VM_NAMES[name], "Usage: " + fmt(value)]
        if name == "cpu":
            lines.append("CPU usage is averaged over 1 minute.")
        elif name == "memory":
            total = snap.metric(record("vm_memory_total:bytes"))
            free = snap.metric(record("vm_memory_available:bytes"))
            lines.extend(["Available: " + capacity(free), "Total: " + capacity(total)])
        else:
            stem = "vm_disk" if name == "disk" else "vm_inode"
            unit = ":bytes" if name == "disk" else ":count"
            total = snap.metric(record(stem + "_total" + unit))
            free = snap.metric(record(stem + "_free" + unit))
            format_value = capacity if name == "disk" else lambda n: "No data" if n is None else f"{n:,.0f}"
            lines.extend(["Filesystem: /", "Free: " + format_value(free), "Total: " + format_value(total)])
        lines.append("Alert: usage >95% continuously for 5 minutes.")
        return "\n".join(lines) + footer, keyboard([], route, "vm", True)
    if route == "containers":
        return "Containers\nChoose a group.", keyboard([[("Application", "g:app"), ("Monitoring", "g:mon")]], route)
    if route.startswith("g:") and route[2:] in GROUPS:
        key = route[2:]
        label, _, services = GROUPS[key]
        rows = [[(service, "c:" + key + ":" + service)] for service in services]
        return "Containers / " + label + "\nChoose a service.", keyboard(rows, route, "containers")
    if route.startswith("c:"):
        parts = route.split(":")
        if len(parts) not in (3, 4) or parts[1] not in GROUPS:
            return render("home", snap)
        key, service = parts[1:3]
        _, project, services = GROUPS[key]
        if service not in services:
            return render("home", snap)
        base = "c:" + key + ":" + service
        if len(parts) == 3:
            rows = [[("CPU Usage", base + ":cpu"), ("Memory", base + ":memory")], [("Status", base + ":status")]]
            return "Containers / " + service, keyboard(rows, route, "g:" + key)
        item = parts[3]
        if item not in ("cpu", "memory", "status"):
            return render("home", snap)
        selector = f'{PROJECT}="{project}",{SERVICE}="{service}"'
        lines = ["Containers / " + service + " / " + {"cpu": "CPU Usage", "memory": "Memory", "status": "Status"}[item]]
        if item == "status":
            up = snap.metric('up{job="cadvisor"}')
            seen = snap.metric(record("container_last_seen:seconds", selector))
            if up != 1:
                lines.append("Unknown: cAdvisor metrics are unavailable.")
            elif seen is None or snap.now - seen > 120:
                lines.append("Not observed in recent cAdvisor samples.")
            else:
                lines.append("Present: observed by cAdvisor.")
                lines.append("Last observed: " + datetime.fromtimestamp(seen, timezone.utc).strftime("%H:%M:%S UTC"))
            lines.append("Presence does not confirm application readiness.")
        else:
            stem = "container_" + item
            percent = snap.metric(record(stem + "_usage:percent", selector))
            unit = ":cores" if item == "cpu" else ":bytes"
            usage = snap.metric(record(stem + "_usage" + unit, selector))
            limit = snap.metric(record(stem + "_limit" + unit, selector))
            formatter = (lambda n: fmt(n, " cores", 3)) if item == "cpu" else capacity
            lines.extend(["Usage: " + formatter(usage), "Limit: " + formatter(limit), "Of limit: " + fmt(percent)])
            lines.append("CPU averaged over 1 minute." if item == "cpu" else "Memory uses the cAdvisor working set.")
            if limit is None:
                lines.append("Percentage needs an exported, positive resource limit.")
            lines.append("Alert: usage >95% of limit for 5 minutes.")
        return "\n".join(lines) + footer, keyboard([], route, base, True)
    if route == "site":
        rows = [[("DNS", "s:dns"), ("HTTPS", "s:https")], [("Backend / API", "site:api")],
                [("Response Time", "s:latency"), ("TLS Certificate", "s:certificate")]]
        return "Website\n" + DOMAIN, keyboard(rows, route)
    if route == "site:api":
        return "Website / Backend and API", keyboard([[("Backend Readiness", "s:ready")], [("API via HTTPS", "s:api")]], route, "site")
    if route.startswith("s:"):
        name = route[2:]
        if name not in (*JOBS, "latency", "certificate"):
            return render("home", snap)
        lines = ["Website / " + {"dns": "DNS", "https": "HTTPS", "ready": "Backend Readiness", "api": "API via HTTPS",
                                 "latency": "Response Time", "certificate": "TLS Certificate"}[name]]
        if name in JOBS:
            job = JOBS[name]
            val = snap.metric('probe_success{job="' + job + '"}')
            lines.append("Status: " + ({1: "OK", 0: "FAILED"}.get(val, "No recent data")))
            duration = snap.metric('probe_duration_seconds{job="' + job + '"}')
            lines.append("Probe duration: " + fmt(duration, " s", 3))
            if name == "dns":
                lines.append("DNS A lookup using the Azure resolver.")
                lines.append(DOMAIN)
            else:
                code = snap.metric('probe_http_status_code{job="' + job + '"}')
                lines.append("HTTP status: " + fmt(code, "", 0))
                lines.append("Checked from inside vm-lab (loopback).")
            lines.append("Alert: failed checks for 5 minutes.")
        elif name == "latency":
            for key, label in (("https", "Homepage"), ("api", "API via HTTPS"), ("ready", "Readiness")):
                job = JOBS[key]
                duration = snap.metric('probe_duration_seconds{job="' + job + '"}')
                ok = snap.metric('probe_success{job="' + job + '"}')
                suffix = "" if ok == 1 else " (check failed or unavailable)"
                lines.append(label + ": " + fmt(duration, " s", 3) + suffix)
            lines.append("Alert: successful HTTP probes >3 s for 5 minutes.")
            lines.append("All HTTP probes run inside vm-lab.")
        else:
            expiry = snap.metric('probe_ssl_earliest_cert_expiry{job="taskboard_https"}')
            if expiry is None:
                lines.append("No recent certificate data.")
            else:
                lines.extend(["Days remaining: " + fmt((expiry - snap.now) / 86400, "", 2),
                              "Expires: " + datetime.fromtimestamp(expiry, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])
            lines.append("Alert: certificate expires in 7 days or less.")
        return "\n".join(lines) + footer, keyboard([], route, "site:api" if name in ("ready", "api") else "site", True)
    return render("home", snap)


class Bot:
    def __init__(self, telegram, prometheus, chat_id):
        self.telegram = telegram
        self.prometheus = prometheus
        self.chat_id = chat_id
        self.last_callback = 0.0

    def authorized(self, message, sender):
        chat = message.get("chat", {})
        return (chat.get("type") == "private" and chat.get("id") == self.chat_id
                and sender.get("id") == self.chat_id and not sender.get("is_bot", False))

    def handle(self, update):
        callback = update.get("callback_query")
        if callback:
            message = callback.get("message", {})
            if not self.authorized(message, callback.get("from", {})):
                self.telegram.call("answerCallbackQuery", {"callback_query_id": callback["id"], "text": "Access denied."})
                return
            stamp = time.monotonic()
            if stamp - self.last_callback < 1:
                self.telegram.call("answerCallbackQuery", {"callback_query_id": callback["id"], "text": "Please wait a moment."})
                return
            self.last_callback = stamp
            self.telegram.call("answerCallbackQuery", {"callback_query_id": callback["id"]})
            route = callback.get("data", "home")
            if not isinstance(route, str) or len(route) > 64:
                route = "home"
            try:
                text, markup = render(route, Snapshot(self.prometheus))
            except ServiceError:
                text = "Metrics are temporarily unavailable. Please try Refresh."
                markup = keyboard([], route, "home", True)
            self.telegram.call("editMessageText", {"chat_id": self.chat_id, "message_id": message["message_id"],
                                                     "text": text, "reply_markup": markup})
        else:
            message = update.get("message", {})
            if not self.authorized(message, message.get("from", {})):
                return
            command = message.get("text", "").split(maxsplit=1)
            if not command or command[0].split("@")[0] not in ("/start", "/menu", "/status"):
                return
            text, markup = render("home", Snapshot(self.prometheus))
            self.telegram.call("sendMessage", {"chat_id": self.chat_id, "text": text, "reply_markup": markup})


def stop(signum, frame):
    global STOP
    STOP = True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        chat, prom_url, token = load_config(os.getenv("BOT_CONFIG", "/etc/taskboard-bot/config.json"))
    except (OSError, ValueError, KeyError, TypeError):
        LOG.error("Invalid configuration or unreadable credential file")
        return 1
    telegram = Telegram(token)
    bot = Bot(telegram, Prometheus(prom_url), chat)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        webhook = telegram.call("getWebhookInfo")
        if webhook.get("url"):
            LOG.error("A webhook is configured. Review it before starting polling; nothing was changed.")
            return 1
        telegram.call("setMyCommands", {"commands": [
            {"command": "menu", "description": "Open monitoring menu"},
            {"command": "status", "description": "Choose VM, containers or website"}]})
        # Skip pre-installation messages. Send /menu after the service starts.
        pending = telegram.call("getUpdates", {"offset": -1, "limit": 1, "timeout": 0,
                                               "allowed_updates": ["message", "callback_query"]})
        offset = pending[-1]["update_id"] + 1 if pending else 0
    except ServiceError as exc:
        LOG.error("Startup failed: %s", exc)
        return 1
    LOG.info("Monitoring menu started")
    while not STOP:
        try:
            updates = telegram.call("getUpdates", {"offset": offset, "timeout": 25, "limit": 20,
                                                    "allowed_updates": ["message", "callback_query"]}, timeout=35)
            for update in updates:
                if STOP:
                    break
                offset = update["update_id"] + 1
                try:
                    bot.handle(update)
                except ServiceError as exc:
                    if exc.fatal:
                        raise
                    LOG.warning("Update could not be completed: %s", exc)
                except (KeyError, ValueError, TypeError):
                    LOG.warning("Invalid update ignored")
        except ServiceError as exc:
            LOG.warning("Polling interrupted: %s", exc)
            if exc.fatal:
                return 1
            for _ in range(exc.retry_after):
                if STOP:
                    break
                time.sleep(1)
    LOG.info("Monitoring menu stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
