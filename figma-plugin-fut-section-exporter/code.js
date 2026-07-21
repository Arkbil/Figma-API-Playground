figma.showUI(__html__, { width: 600, height: 720, themeColors: true });

const EXPORTABLE_TYPES = new Set(["SECTION", "FRAME"]);

async function loadPagesIfNeeded() {
  if (typeof figma.loadAllPagesAsync === "function") {
    await figma.loadAllPagesAsync();
  }
}

function getBounds(node) {
  return node.absoluteBoundingBox || { x: 0, y: 0, width: 0, height: 0 };
}

function nodeSummary(node, page, section) {
  const box = getBounds(node);
  return {
    id: node.id,
    name: node.name || node.id,
    type: node.type,
    pageId: page.id,
    pageName: page.name,
    sectionId: section ? section.id : "",
    sectionName: section ? section.name : "",
    x: Math.round(box.x || 0),
    y: Math.round(box.y || 0),
    width: Math.round(box.width || 0),
    height: Math.round(box.height || 0),
  };
}

function pageSummary(page) {
  return { id: page.id, name: page.name };
}

function collectExportables(pageIds) {
  const selectedIds = Array.isArray(pageIds) && pageIds.length ? new Set(pageIds) : new Set([figma.currentPage.id]);
  const targetPages = Array.from(figma.root.children).filter((page) => selectedIds.has(page.id));
  const items = [];

  function walk(node, page, currentFrame, currentSection) {
    if (!node || !node.type) return;

    let sectionContext = currentSection;
    let frameContext = currentFrame;

    if (node.type === "SECTION" && node.absoluteBoundingBox) {
      sectionContext = { id: node.id, name: node.name || "" };
      items.push(nodeSummary(node, page, null));
    }

    const isStandaloneFrame = node.type === "FRAME"
      && node.absoluteBoundingBox
      && !frameContext
      && !sectionContext;

    if (isStandaloneFrame) {
      frameContext = { id: node.id, name: node.name || "", type: node.type };
      items.push(nodeSummary(node, page, null));
    } else if (node.type === "FRAME" && !frameContext) {
      frameContext = { id: node.id, name: node.name || "", type: node.type };
    }

    if ("children" in node) {
      for (const child of node.children) walk(child, page, frameContext, sectionContext);
    }
  }

  for (const page of targetPages) {
    for (const child of page.children) walk(child, page, null, null);
  }

  items.sort((a, b) => {
    if (a.pageName !== b.pageName) return a.pageName.localeCompare(b.pageName);
    if (a.type !== b.type) return a.type === "SECTION" ? -1 : 1;
    return a.y === b.y ? a.x - b.x : a.y - b.y;
  });
  return items;
}

function safeFilePart(value) {
  const cleaned = String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return cleaned || "figma-node";
}

function pageNameForIds(pageIds) {
  if (!Array.isArray(pageIds) || !pageIds.length) return figma.currentPage.name;
  if (pageIds.length === 1) {
    const page = figma.root.children.find((item) => item.id === pageIds[0]);
    return page ? page.name : figma.currentPage.name;
  }
  return `${pageIds.length} selected pages`;
}

async function findNodeById(id) {
  if (typeof figma.getNodeByIdAsync === "function") {
    return await figma.getNodeByIdAsync(id);
  }
  return figma.getNodeById(id);
}

function findOwningPage(node) {
  let parent = node && node.parent;
  while (parent) {
    if (parent.type === "PAGE") return parent;
    parent = parent.parent;
  }
  return figma.currentPage;
}
async function sendItems(pageIds) {
  await loadPagesIfNeeded();
  const selectedPageIds = Array.isArray(pageIds) && pageIds.length ? pageIds : [figma.currentPage.id];
  figma.ui.postMessage({
    type: "items",
    currentPageId: figma.currentPage.id,
    pageIds: selectedPageIds,
    pageName: pageNameForIds(selectedPageIds),
    pages: figma.root.children.map(pageSummary),
    items: collectExportables(selectedPageIds),
  });
}

async function exportItems(ids, scale) {
  await loadPagesIfNeeded();
  const selectedNodes = await Promise.all(ids.map(findNodeById));
  const selected = selectedNodes.filter((node) => node && EXPORTABLE_TYPES.has(node.type));
  if (!selected.length) {
    figma.ui.postMessage({ type: "error", message: "Pilih minimal satu section atau frame yang bisa diexport." });
    return;
  }

  const exports = [];
  const normalizedScale = Number.isFinite(scale) && scale > 0 ? scale : 0.5;
  const pageCounters = new Map();

  for (let index = 0; index < selected.length; index += 1) {
    const item = selected[index];
    const page = findOwningPage(item);
    const pageKey = page.id;
    const nextPageIndex = (pageCounters.get(pageKey) || 0) + 1;
    pageCounters.set(pageKey, nextPageIndex);
    figma.ui.postMessage({ type: "progress", message: `Export ${index + 1}/${selected.length}: ${page.name} / ${item.name}` });
    const bytes = await item.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: normalizedScale } });
    exports.push({
      filename: `flow-${String(nextPageIndex).padStart(2, "0")}-${safeFilePart(item.name)}.png`,
      bytes: Array.from(bytes),
      item: nodeSummary(item, page, null),
    });
  }

  figma.ui.postMessage({
    type: "export-complete",
    exportedAt: new Date().toISOString(),
    scale: normalizedScale,
    exports,
  });
  figma.notify(`Exported ${exports.length} FUT image${exports.length === 1 ? "" : "s"}.`);
}

figma.ui.onmessage = async (msg) => {
  try {
    if (msg.type === "scan-items") {
      await sendItems(msg.pageIds || []);
      return;
    }
    if (msg.type === "export-items") {
      await exportItems(msg.ids || [], Number(msg.scale));
      return;
    }
    if (msg.type === "cancel") figma.closePlugin();
  } catch (error) {
    figma.ui.postMessage({ type: "error", message: error instanceof Error ? error.message : String(error) });
  }
};

sendItems([figma.currentPage.id]);



