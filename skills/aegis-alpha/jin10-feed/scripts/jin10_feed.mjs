#!/usr/bin/env node
/**
 * Jin10 important news fetcher (Playwright-based).
 * Modes:
 *   --once: snapshot and exit
 *   --daemon: loop and append to jsonl
 */

import fs from "fs";
import os from "os";
import path from "path";
import crypto from "crypto";

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch (err) {
  console.error("playwright_not_available");
  process.exit(2);
}

const args = process.argv.slice(2);
const isOnce = args.includes("--once");
const isDaemon = args.includes("--daemon");
const limitArg = args.find((a) => a.startsWith("--limit="));
const intervalArg = args.find((a) => a.startsWith("--interval="));
const dedupArg = args.find((a) => a.startsWith("--dedup-hours="));

const limit = limitArg ? parseInt(limitArg.split("=")[1], 10) : 50;
const intervalMs = intervalArg ? parseInt(intervalArg.split("=")[1], 10) : (parseInt(process.env.JIN10_INTERVAL_MS || "60000", 10));
const dedupHours = dedupArg ? parseInt(dedupArg.split("=")[1], 10) : 72;

const workspace = process.env.AEGIS_ALPHA_WORKSPACE || path.join(os.homedir(), ".aegis-alpha", "workspace");
const outDir = path.join(workspace, "memory", "jin10");
const dedupPath = path.join(outDir, "dedup.json");
const logPath = path.join(outDir, "news.jsonl");
const snapshotPath = path.join(outDir, "snapshot.json");

const baseUrl = process.env.JIN10_URL || "https://www.jin10.com/";

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

function loadDedup() {
  if (!fs.existsSync(dedupPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(dedupPath, "utf-8"));
  } catch {
    return {};
  }
}

function saveDedup(data) {
  try {
    fs.writeFileSync(dedupPath, JSON.stringify(data, null, 2), "utf-8");
  } catch {
    // ignore
  }
}

function cleanDedup(dedup) {
  const now = Date.now();
  const cutoff = now - dedupHours * 3600 * 1000;
  for (const [key, ts] of Object.entries(dedup)) {
    if (typeof ts !== "number" || ts < cutoff) {
      delete dedup[key];
    }
  }
}

function hashItem(item) {
  const base = `${item.time || ""}-${item.title || ""}-${(item.content || "").slice(0, 120)}`;
  return crypto.createHash("md5").update(base).digest("hex");
}

async function fetchImportantNews(page) {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  const items = await page.evaluate(() => {
    const containers = Array.from(document.querySelectorAll(".jin-flash-item-container"));
    return containers.map((container) => {
      const isImportant = container.querySelector(".jin-flash-item.is-important") !== null;
      const timeEl = container.querySelector(".item-time");
      const titleEl = container.querySelector(".right-common-title");
      const contentEl = container.querySelector(".right-content");
      return {
        time: timeEl ? timeEl.textContent.trim() : null,
        title: titleEl ? titleEl.textContent.trim() : null,
        content: contentEl ? contentEl.textContent.trim() : null,
        isImportant,
      };
    }).filter((x) => x.isImportant);
  });
  return items.slice(0, limit);
}

async function runOnce() {
  ensureDir(outDir);
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  const page = await browser.newPage();
  try {
    const items = await fetchImportantNews(page);
    const dedup = loadDedup();
    cleanDedup(dedup);
    const newItems = [];
    for (const item of items) {
      const h = hashItem(item);
      if (!dedup[h]) {
        dedup[h] = Date.now();
        newItems.push(item);
      }
    }
    saveDedup(dedup);
    const payload = {
      source: "jin10",
      fetched_at: new Date().toISOString(),
      items,
      new_items: newItems,
    };
    fs.writeFileSync(snapshotPath, JSON.stringify(payload, null, 2), "utf-8");
    console.log(JSON.stringify(payload));
  } finally {
    await browser.close();
  }
}

async function runDaemon() {
  ensureDir(outDir);
  let dedup = loadDedup();
  cleanDedup(dedup);
  saveDedup(dedup);

  const startBrowser = async () => {
    const browser = await chromium.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    });
    const page = await browser.newPage();
    return { browser, page };
  };

  let { browser, page } = await startBrowser();

  while (true) {
    try {
      const items = await fetchImportantNews(page);
      const newItems = [];
      for (const item of items) {
        const h = hashItem(item);
        if (!dedup[h]) {
          dedup[h] = Date.now();
          newItems.push(item);
        }
      }
      if (newItems.length) {
        for (const item of newItems) {
          const line = JSON.stringify({ ts: new Date().toISOString(), ...item });
          fs.appendFileSync(logPath, line + "\n", "utf-8");
        }
      }
      const snapshot = {
        source: "jin10",
        fetched_at: new Date().toISOString(),
        items,
        new_items: newItems,
      };
      fs.writeFileSync(snapshotPath, JSON.stringify(snapshot, null, 2), "utf-8");
      cleanDedup(dedup);
      saveDedup(dedup);
    } catch (err) {
      try { await browser.close(); } catch {}
      try {
        ({ browser, page } = await startBrowser());
      } catch {
        // wait and retry
      }
    }
    try {
      await page.waitForTimeout(intervalMs);
    } catch {
      try { await browser.close(); } catch {}
      ({ browser, page } = await startBrowser());
    }
  }
}

if (isOnce) {
  await runOnce();
} else if (isDaemon) {
  await runDaemon();
} else {
  console.error("usage: jin10_feed.mjs --once|--daemon [--limit=50] [--interval=60000]");
  process.exit(1);
}
